"""Synthetic UDAP fixtures and loopback-only HTTP; never contact a television."""

from collections import deque
from contextlib import redirect_stderr, redirect_stdout
import getpass
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
import threading
import time
import unittest
from unittest.mock import patch
import warnings
import xml.etree.ElementTree as ET

from tools import udap


def count_xml(number=2, category=1):
    return ('<envelope><dataList name="App List"><data><type>%s</type><number>%s</number></data></dataList></envelope>' % (category, number)).encode()


def apps_xml(count=2):
    rows = ''.join('<data><auid>%08x</auid><name>Fixture app %d</name><type>2</type><cpid>fixture</cpid><adult>false</adult><icon_name>icon.png</icon_name></data>' % (i + 1, i) for i in range(count))
    return ('<envelope><dataList name="App List">' + rows + '</dataList></envelope>').encode()


def callback(name, **fields):
    return udap._xml('event', name, tuple(fields.items()))


class ScriptedTransport:
    def __init__(self, replies=()):
        self.config = udap.PeerConfig('192.168.50.2', 8080, '192.168.50.3', '192.168.50.0/24', True)
        self.replies = deque(replies)
        self.seen = []

    def exchange(self, request):
        self.seen.append(request)
        value = self.replies.popleft() if self.replies else b''
        if isinstance(value, Exception):
            raise value
        return udap.WireResponse(200, value)


def paired_session(replies=(), clock=lambda: 100.0):
    transport = ScriptedTransport((b'', b'', *replies))
    session = udap.Session(transport, 8767, callback_ready=lambda: True, clock=clock)
    session.request_pairing_code(owner_approved=True)
    session.pair_interactive(pin_reader=lambda: '123456')  # Synthetic fixture, not a device credential.
    return session, transport


def observe_field(session, value=''):
    peer = session.transport.config.peer
    session.receive_callback(peer, udap.EVENT_PATH, callback('KeyboardVisible', value='true', mode='default'))
    session.receive_callback(peer, udap.EVENT_PATH, callback('TextEdited', state='Editing', value=value))


class ConfigAndXMLTests(unittest.TestCase):
    def test_target_must_be_confirmed_literal_private_host_on_explicit_subnet(self):
        valid = dict(peer='192.168.50.2', port=8080, controller='192.168.50.3', network='192.168.50.0/24', confirmed=True)
        self.assertNotIn(valid['peer'], repr(udap.PeerConfig(**valid)))
        mutations = ({'confirmed': False}, {'confirmed': 1}, {'peer': 'tv.local'}, {'peer': '8.8.8.8'},
                     {'peer': '192.168.51.2'}, {'peer': '192.168.50.255'}, {'peer': '192.168.50.0'},
                     {'peer': valid['controller']}, {'controller': '0.0.0.0'}, {'network': '192.168.0.0/16'},
                     {'port': True}, {'port': 0}, {'port': 65536}, {'timeout': float('nan')},
                     {'timeout': float('inf')}, {'timeout': 11}, {'timeout': True})
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(udap.UDAPError):
                udap.PeerConfig(**(valid | change))
        with self.assertRaises(udap.UDAPError):
            udap.PeerConfig('127.0.0.1', 8080, '127.0.0.1', '127.0.0.0/30', True)
        self.assertTrue(udap.PeerConfig.loopback_fixture(8080).lab_loopback)

    def test_pairing_code_is_ascii_six_digits_and_request_repr_excludes_it(self):
        request = udap.hello_request('123456', 8767)
        self.assertNotIn('123456', repr(request))
        self.assertEqual(ET.fromstring(request.body).findtext('api/value'), '123456')
        for bad in ('12 34 56', '１２３４５６', '12345', '1234567', '<secret>', None):
            with self.subTest(kind=type(bad)), self.assertRaises(udap.UDAPError) as error:
                udap.hello_request(bad, 8767)
            self.assertNotIn(str(bad), str(error.exception))

    def test_xml_escaping_and_private_callback_value_discard(self):
        secret = 'unrelated <private> & field'
        data = callback('TextEdited', state='Editing', value=secret)
        self.assertIn(b'&lt;private&gt;', data)
        event = udap.parse_callback(udap.EVENT_PATH, data)
        self.assertTrue(event.text_present)
        self.assertNotIn(secret, repr(event))
        self.assertFalse(hasattr(event, 'value'))

    def test_malicious_and_ambiguous_xml_are_rejected_without_echo(self):
        invalid = [b'<!DOCTYPE envelope [<!ENTITY x "private">]><envelope>&x;</envelope>',
                   b'<envelope><dataList name="App List"/><dataList name="App List"/></envelope>',
                   b'<envelope><api type="event"><name>KeyboardVisible</name><value>true</value><value>false</value><mode>default</mode></api></envelope>',
                   b'<envelope><api type="event"><name>KeyboardVisible</name><value><x>secret</x></value><mode>default</mode></api></envelope>',
                   b'<envelope>\0</envelope>', '<envelope/>'.encode('utf-16'),
                   b'<envelope>' + b'<x>' * 8 + b'</x>' * 8 + b'</envelope>',
                   b'x' * (udap.MAX_CALLBACK + 1)]
        for data in invalid:
            with self.subTest(length=len(data)), self.assertRaises(udap.UDAPError) as error:
                udap.parse_callback(udap.EVENT_PATH, data)
            self.assertNotIn('secret', str(error.exception))
            self.assertNotIn('private', str(error.exception))

    def test_inventory_schema_limits_and_identifier_preservation(self):
        self.assertEqual(udap.parse_app_count(count_xml(0)), 0)
        apps = udap.parse_app_list(apps_xml(), 2)
        self.assertEqual(apps[0].auid, '00000001')
        self.assertNotIn('Fixture app', repr(apps))
        for data, requested in ((apps_xml(3), 2), (apps_xml().replace(b'<type>2</type>', b'<type>1</type>'), 2),
                                (apps_xml().replace(b'00000002', b'00000001'), 2),
                                (apps_xml().replace(b'00000001', b'http://evil'), 2)):
            with self.assertRaises(udap.UDAPError):
                udap.parse_app_list(data, requested)
        for number in (-1, 2049):
            with self.assertRaises(udap.UDAPError):
                udap.parse_app_count(count_xml(number))
        with self.assertRaises(udap.UDAPError):
            udap.parse_app_count(count_xml(2, category=2), category=1)

    def test_request_surface_excludes_arbitrary_urls_keys_and_unbounded_lists(self):
        invalid = [udap.WireRequest('GET', 'http://127.0.0.1/'), udap.WireRequest('POST', '/udap/api/command', b'<secret/>'),
                   udap.WireRequest('GET', '/udap/api/data?target=applist_get&type=1&index=0&number=0'),
                   udap.WireRequest('GET', '/udap/api/data?target=appnum_get&type=1&type=2'),
                   udap.WireRequest('GET', '/udap/api/data\r\nsecret'), udap.WireRequest('POST', udap.PAIRING_PATH, None)]
        transport = udap.Transport(udap.PeerConfig.loopback_fixture(1))
        with patch('http.client.HTTPConnection') as connection:
            for request in invalid:
                with self.assertRaises(udap.UDAPError):
                    transport.exchange(request)
            connection.assert_not_called()

    def test_hidden_input_never_falls_back_to_echo(self):
        def unavailable(prompt):
            warnings.warn('echo would expose input', getpass.GetPassWarning)
            self.fail('Echo fallback must not execute')
        with patch.object(getpass, 'getpass', unavailable), self.assertRaises(udap.UDAPError) as error:
            udap.read_pairing_pin()
        self.assertEqual(error.exception.code, 'hidden_pairing_input_unavailable')

    def test_cli_is_offline_and_does_not_echo_unrecognized_secret_arguments(self):
        for mode in ('pairing', 'inventory', 'smarttext'):
            output = io.StringIO()
            with patch('http.client.HTTPConnection') as connection, redirect_stdout(output):
                self.assertEqual(udap.main(['--dry-run', mode]), 0)
            self.assertEqual(json.loads(output.getvalue())['network_requests'], 0)
            connection.assert_not_called()
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            udap.main(['--pin', 'synthetic-secret'])
        self.assertNotIn('synthetic-secret', stderr.getvalue())


class SessionTests(unittest.TestCase):
    def test_pairing_requires_overlay_approval_and_live_callback_readiness(self):
        transport = ScriptedTransport()
        session = udap.Session(transport, 8767, callback_ready=lambda: False)
        for approved in (False, True):
            with self.assertRaises(udap.UDAPError):
                session.request_pairing_code(owner_approved=approved)
        self.assertEqual(transport.seen, [])
        with self.assertRaises(udap.UDAPError):
            session.pair_interactive(pin_reader=lambda: '123456')

    def test_failed_pairing_is_not_retried_and_explicit_close_sends_one_byebye(self):
        transport = ScriptedTransport((b'', udap.UDAPError('http_rejected', 401), b''))
        session = udap.Session(transport, 8767, callback_ready=lambda: True)
        session.request_pairing_code(owner_approved=True)
        with self.assertRaises(udap.UDAPError):
            session.pair_interactive(pin_reader=lambda: '123456')
        with self.assertRaises(udap.UDAPError):
            session.pair_interactive(pin_reader=lambda: self.fail('No PIN retry'))
        self.assertEqual(session.state, 'failed')
        session.close(); session.close()
        self.assertEqual(len(transport.seen), 3)
        self.assertEqual(ET.fromstring(transport.seen[-1].body).findtext('api/name'), 'byebye')
        self.assertNotIn('123456', repr(session))
        self.assertFalse(hasattr(session, 'pin'))

    def test_inventory_counts_first_and_returns_one_partial_page(self):
        session, transport = paired_session((count_xml(20), apps_xml(16)))
        result = session.inventory()
        self.assertEqual(result.total, 20)
        self.assertEqual(len(result.apps), 16)
        self.assertTrue(result.partial)
        self.assertEqual(transport.seen[-2].path, '/udap/api/data?target=appnum_get&type=1')
        self.assertEqual(transport.seen[-1].path, '/udap/api/data?target=applist_get&type=1&index=1&number=16')
        self.assertEqual(len(transport.seen), 4)
        empty, empty_transport = paired_session((count_xml(0),))
        self.assertFalse(empty.inventory().partial)
        self.assertEqual(len(empty_transport.seen), 3)

    def test_filtered_inventory_rejects_other_category_records(self):
        session, transport = paired_session((count_xml(1, category=2), apps_xml(1).replace(b'<type>2</type>', b'<type>3</type>')))
        with self.assertRaisesRegex(udap.UDAPError, 'category_filter_mismatch'):
            session.inventory(category=2)
        self.assertEqual(session.state, 'failed')
        self.assertEqual(len(transport.seen), 4)

    def test_query_error_fails_session_without_automatic_retry(self):
        session, transport = paired_session((udap.UDAPError('http_rejected', 401),))
        with self.assertRaises(udap.UDAPError): session.inventory()
        with self.assertRaises(udap.UDAPError): session.inventory()
        self.assertEqual(len(transport.seen), 3)
        self.assertEqual(session.state, 'failed')

    def test_smarttext_needs_observed_normal_keyboard_editing_and_owner_confirmation(self):
        session, transport = paired_session()
        with self.assertRaises(udap.UDAPError): session.confirm_browser_address_field(owner_confirmed=True)
        with self.assertRaises(udap.UDAPError): session.prepare_local_url('http://192.168.50.3:8765/')
        observe_field(session, '')
        session.confirm_browser_address_field(owner_confirmed=True)
        plan = session.prepare_local_url('http://192.168.50.3:8765/')
        self.assertEqual([ET.fromstring(r.body).findtext('api/state') for r in plan.requests], ['EditStart', 'Editing', 'EditEnd'])
        self.assertFalse(plan.transmission_enabled)
        self.assertNotIn('192.168.50.3', repr(plan))
        self.assertEqual(len(transport.seen), 2)
        with self.assertRaises(udap.UDAPError): session.prepare_local_url('http://192.168.50.3:8765/')
        with self.assertRaisesRegex(udap.UDAPError, 'not_integrated'):
            udap.Transport(udap.PeerConfig.loopback_fixture(1)).exchange(plan.requests[0])

    def test_nonempty_field_plan_starts_editing_but_does_not_retain_original_text(self):
        session, _ = paired_session()
        observe_field(session, 'private history')
        session.confirm_browser_address_field(owner_confirmed=True)
        plan = session.prepare_local_url('http://192.168.50.3:8765/shell/')
        self.assertEqual(len(plan.requests), 2)
        self.assertNotIn('private history', repr(vars(session)))
        self.assertNotIn(b'private history', b''.join(r.body for r in plan.requests))

    def test_password_hide_wrong_peer_and_field_change_revoke_or_reject(self):
        for mode, visible in (('password', 'true'), ('default', 'false')):
            session, _ = paired_session(); observe_field(session)
            session.confirm_browser_address_field(owner_confirmed=True)
            session.receive_callback(session.transport.config.peer, udap.EVENT_PATH, callback('KeyboardVisible', value=visible, mode=mode))
            event = session.receive_callback(session.transport.config.peer, udap.EVENT_PATH, callback('TextEdited', state='Editing', value='private password'))
            self.assertIsNone(event.text_present)
            with self.assertRaises(udap.UDAPError): session.prepare_local_url('http://192.168.50.3:8765/')
        session, _ = paired_session()
        with self.assertRaises(udap.UDAPError): session.receive_callback('192.168.50.99', udap.EVENT_PATH, callback('KeyboardVisible', value='true', mode='default'))
        observe_field(session); session.confirm_browser_address_field(owner_confirmed=True)
        session.receive_callback(session.transport.config.peer, udap.EVENT_PATH, callback('TextEdited', state='Editing', value='new field'))
        with self.assertRaises(udap.UDAPError): session.prepare_local_url('http://192.168.50.3:8765/')

    def test_stale_confirmation_and_nonlocal_urls_fail_without_sending(self):
        now = [100.0]
        session, transport = paired_session(clock=lambda: now[0]); observe_field(session)
        session.confirm_browser_address_field(owner_confirmed=True); now[0] += 16
        with self.assertRaises(udap.UDAPError): session.prepare_local_url('http://192.168.50.3:8765/')
        for url in ('https://192.168.50.3:8765/', 'http://example.com/', 'http://192.168.50.3/', 'http://user:pass@192.168.50.3:8765/', 'http://192.168.50.3:8765/?private=value'):
            observe_field(session); session.confirm_browser_address_field(owner_confirmed=True)
            with self.assertRaises(udap.UDAPError): session.prepare_local_url(url)
        self.assertEqual(len(transport.seen), 2)

    def test_remote_byebye_closes_session_and_callback_budget_is_finite(self):
        session, transport = paired_session()
        session.receive_callback(transport.config.peer, udap.PAIRING_PATH, udap._xml('pairing', 'byebye', (('port', '8080'),)))
        self.assertEqual(session.state, 'closed')
        session.close()
        self.assertEqual(len(transport.seen), 2)
        another, _ = paired_session()
        event = callback('KeyboardVisible', value='false', mode='default')
        for _ in range(64): another.receive_callback(another.transport.config.peer, udap.EVENT_PATH, event)
        with self.assertRaises(udap.UDAPError): another.receive_callback(another.transport.config.peer, udap.EVENT_PATH, event)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.replies = deque()
        self.seen = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def handle_request(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                owner.seen.append((self.command, self.path, body))
                status, payload, headers, delay = owner.replies.popleft()
                if delay == 'drip':
                    try:
                        self.connection.sendall(b'HTTP/1.1 200 OK\r\n')
                        for _ in range(12):
                            self.connection.sendall(b'X-Fixture: bounded\r\n')
                            time.sleep(0.07)
                        self.connection.sendall(b'Content-Length: 0\r\n\r\n')
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    return
                if delay: time.sleep(delay)
                try:
                    self.send_response(status)
                    for key, value in headers: self.send_header(key, value)
                    if not any(k.lower() == 'content-length' for k, _ in headers): self.send_header('Content-Length', str(len(payload)))
                    self.end_headers(); self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError): pass
            do_GET = do_POST = handle_request
            def log_message(self, *args): pass
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.transport = udap.Transport(udap.PeerConfig.loopback_fixture(self.server.server_port, timeout=0.3))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def reply(self, payload=b'', status=200, headers=(), delay=0):
        self.replies.append((status, payload, list(headers), delay))

    def test_direct_http_ignores_proxy_environment_and_builds_exact_query(self):
        self.reply(count_xml(), headers=(('Content-Type', 'text/xml; charset=utf-8'),))
        with patch.dict(os.environ, {'http_proxy': 'http://192.0.2.1:1', 'HTTP_PROXY': 'http://192.0.2.1:1', 'ALL_PROXY': 'http://192.0.2.1:1'}):
            response = self.transport.exchange(udap.inventory_request())
        self.assertEqual(udap.parse_app_count(response.body), 2)
        self.assertEqual(self.seen[0][:2], ('GET', '/udap/api/data?target=appnum_get&type=1'))

    def test_redirect_and_auth_failure_are_not_followed_or_retried_or_echoed(self):
        for status in (302, 401, 503):
            self.reply(b'synthetic-private-response', status, (('Location', 'http://192.0.2.1/private'),))
            with self.assertRaises(udap.UDAPError) as error: self.transport.exchange(udap.show_key_request())
            self.assertEqual(error.exception.status, status)
            self.assertNotIn('private', str(error.exception))
        self.assertEqual(len(self.seen), 3)

    def test_response_size_framing_encoding_and_acknowledgement_limits(self):
        cases = [(b'', [('Content-Length', str(udap.MAX_BODY + 1))]),
                 (b'', [('Content-Length', '0'), ('Content-Length', '0')]),
                 (b'', [('Transfer-Encoding', 'chunked')]),
                 (b'', [('Content-Encoding', 'gzip')]),
                 (b'not-an-empty-ack', []),
                 (b'x', [('Content-Length', '10')])]
        for payload, headers in cases:
            self.reply(payload, headers=headers)
            with self.subTest(headers=headers), self.assertRaises(udap.UDAPError):
                self.transport.exchange(udap.show_key_request())
        self.assertEqual(len(self.seen), len(cases))

    def test_total_deadline_bounds_headers_that_keep_arriving(self):
        self.transport.config = udap.PeerConfig.loopback_fixture(self.server.server_port, timeout=0.2)
        self.reply(delay='drip')
        began = time.monotonic()
        with self.assertRaises(udap.UDAPError):
            self.transport.exchange(udap.show_key_request())
        self.assertLess(time.monotonic() - began, 0.6)
        self.assertEqual(len(self.seen), 1)

    def test_request_budget_reserves_one_disconnect_attempt(self):
        self.transport.requests = udap.MAX_REQUESTS - 1
        with patch('http.client.HTTPConnection') as connection, self.assertRaises(udap.UDAPError):
            self.transport.exchange(udap.show_key_request())
        connection.assert_not_called()
        self.reply()
        self.assertEqual(self.transport.exchange(udap.byebye_request(8767)).status, 200)
        self.assertEqual(self.transport.requests, udap.MAX_REQUESTS)
        self.assertEqual(len(self.seen), 1)

    def test_timeout_has_no_retry_and_budget_prevents_new_connection(self):
        self.reply(delay=0.5)
        began = time.monotonic()
        with self.assertRaises(udap.UDAPError): self.transport.exchange(udap.show_key_request())
        self.assertLess(time.monotonic() - began, 1)
        self.assertEqual(len(self.seen), 1)
        self.transport.requests = udap.MAX_REQUESTS
        with patch('http.client.HTTPConnection') as connection, self.assertRaises(udap.UDAPError):
            self.transport.exchange(udap.show_key_request())
        connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
