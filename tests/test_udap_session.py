"""Complete session fixtures on 127.0.0.1 only; no actual TV pairing or LAN bind."""

from contextlib import redirect_stderr, redirect_stdout
import datetime as dt
import errno
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import socket
import threading
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import udap, udap_session as live
from test_udap import apps_xml, callback, count_xml


def post(port, body, path=udap.EVENT_PATH, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('POST', path, body, headers or {'Content-Type': 'text/xml'})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.receiver = live.CallbackReceiver(udap.PeerConfig.loopback_fixture(1), lifetime=5, request_seconds=0.25).start()

    def tearDown(self):
        self.receiver.stop()

    def test_callback_state_discards_text_and_invalidates_password_and_hide(self):
        self.assertEqual(post(self.receiver.port, callback('KeyboardVisible', value='true', mode='default'))[0], 200)
        self.assertEqual(post(self.receiver.port, callback('TextEdited', state='Editing', value='synthetic private history'))[0], 200)
        summary = self.receiver.state.summary()
        self.assertTrue(summary['editing_observed'])
        self.assertNotIn('private history', repr(vars(self.receiver.state)))
        post(self.receiver.port, callback('KeyboardVisible', value='true', mode='password'))
        post(self.receiver.port, callback('TextEdited', state='Editing', value='synthetic private password'))
        self.assertFalse(self.receiver.state.summary()['editing_observed'])
        self.assertNotIn('private password', repr(vars(self.receiver.state)))
        post(self.receiver.port, callback('KeyboardVisible', value='false', mode='default'))
        self.assertFalse(self.receiver.state.summary()['keyboard_visible'])

    def test_peer_paths_body_and_methods_are_restricted(self):
        self.assertFalse(self.receiver.server.verify_request(None, ('192.168.1.99', 10)))
        self.assertEqual(post(self.receiver.port, b'<secret/>', path='/anything')[0], 404)
        self.assertEqual(post(self.receiver.port, b'<secret/>')[0], 400)
        self.assertEqual(post(self.receiver.port, b'x' * (udap.MAX_CALLBACK + 1))[0], 413)
        self.assertEqual(post(self.receiver.port, callback('KeyboardVisible', value='true', mode='default'), headers={'Content-Type': 'text/plain'})[0], 400)
        conn = http.client.HTTPConnection('127.0.0.1', self.receiver.port, timeout=2)
        try:
            conn.request('GET', '/'); response = conn.getresponse()
            self.assertEqual(response.status, 405); self.assertEqual(response.read(), b'')
        finally: conn.close()

    def raw(self, request):
        with socket.create_connection(('127.0.0.1', self.receiver.port), timeout=2) as connection:
            connection.sendall(request)
            return connection.recv(2048)

    def test_duplicate_headers_and_header_budget_fail_closed_without_echo(self):
        prefix = ('POST /udap/api/event HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Type: text/xml\r\n' % self.receiver.port).encode()
        for headers in (b'Content-Length: 1\r\nContent-Length: 1\r\n',
                        b'Content-Length: 1\r\nTransfer-Encoding: chunked\r\n',
                        b'Content-Length: 1\r\nContent-Type: text/plain\r\n'):
            response = self.raw(prefix + headers + b'\r\nx')
            self.assertIn(b'400', response)
        response = self.raw(prefix + b'X-Private: ' + b'private' * 800 + b'\r\n\r\n')
        self.assertNotIn(b'private', response)
        self.assertFalse(self.receiver.state.summary()['editing_observed'])

    def test_hard_request_deadline_bounds_a_dripping_body(self):
        prefix = ('POST /udap/api/event HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Type: text/xml\r\nContent-Length: 100\r\n\r\n' % self.receiver.port).encode()
        began = time.monotonic()
        with socket.create_connection(('127.0.0.1', self.receiver.port), timeout=1) as connection:
            connection.sendall(prefix)
            for _ in range(12):
                try:
                    connection.sendall(b'x'); time.sleep(0.06)
                except (BrokenPipeError, ConnectionResetError):
                    break
            try: reply = connection.recv(100)
            except (ConnectionResetError, OSError): reply = b''
        self.assertLess(time.monotonic() - began, 0.7)
        self.assertNotIn(b'200', reply)
        self.assertGreater(self.receiver.state.summary()['invalid'], 0)

    def test_remote_disconnect_prevents_a_guarded_request_before_connection(self):
        post(self.receiver.port, udap.byebye_request(8080).body, udap.PAIRING_PATH)
        self.assertTrue(self.receiver.state.summary()['remote_closed'])
        transport = live.GuardedTransport(udap.Transport(udap.PeerConfig.loopback_fixture(1)), self.receiver)
        with patch('http.client.HTTPConnection') as connection, self.assertRaisesRegex(udap.UDAPError, 'remote_session_ended'):
            transport.exchange(udap.inventory_request())
        connection.assert_not_called()

    def test_finite_receiver_lifetime_and_idempotent_cleanup(self):
        with live.CallbackReceiver(udap.PeerConfig.loopback_fixture(1), lifetime=0.12, request_seconds=0.1) as receiver:
            port = receiver.port
            time.sleep(0.25)
            self.assertFalse(receiver.ready())
            self.assertTrue(receiver.state.summary()['expired'])
        receiver.stop()
        with self.assertRaises(OSError): socket.create_connection(('127.0.0.1', port), timeout=0.2)

    def test_concurrent_stop_waits_for_completed_socket_cleanup(self):
        entered, release, follower_done = threading.Event(), threading.Event(), threading.Event()
        original = self.receiver.server.shutdown
        def paused_shutdown():
            entered.set(); release.wait(1); original()
        with patch.object(self.receiver.server, 'shutdown', paused_shutdown):
            first = threading.Thread(target=self.receiver.stop); first.start()
            self.assertTrue(entered.wait(1))
            second = threading.Thread(target=lambda: (self.receiver.stop(), follower_done.set())); second.start()
            time.sleep(0.05)
            self.assertFalse(follower_done.is_set())
            release.set(); first.join(2); second.join(2)
        self.assertTrue(follower_done.is_set())
        with self.assertRaises(OSError): socket.create_connection(('127.0.0.1', self.receiver.port), timeout=0.2)

    def test_worker_start_failure_closes_already_bound_socket(self):
        receiver = live.CallbackReceiver(udap.PeerConfig.loopback_fixture(1))
        with patch.object(threading.Thread, 'start', side_effect=RuntimeError('synthetic start failure')):
            with self.assertRaisesRegex(udap.UDAPError, 'callback_start_failed'):
                receiver.start()
        self.assertFalse(receiver.ready())
        with self.assertRaises(OSError): socket.create_connection(('127.0.0.1', receiver.port), timeout=0.2)

    def test_connection_budget_stops_receiver(self):
        with self.receiver.state.lock:
            self.receiver.state.connections = live.MAX_CALLBACK_CONNECTIONS
        try: self.raw(b'GET / HTTP/1.0\r\n\r\n')
        except (ConnectionResetError, OSError): pass
        limit = time.monotonic() + 1
        while self.receiver.ready() and time.monotonic() < limit: time.sleep(0.01)
        self.assertFalse(self.receiver.ready())
        self.assertTrue(self.receiver.state.summary()['expired'])


class SessionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.names, self.callback_port, self.reject_pin, self.disconnect_during_count = [], None, False, False
        owner = self
        class TVFixture(BaseHTTPRequestHandler):
            def do_POST(self):
                data = self.rfile.read(int(self.headers['Content-Length']))
                root = ET.fromstring(data)
                name = root.findtext('api/name'); owner.names.append(name)
                if name == 'hello':
                    owner.callback_port = int(root.findtext('api/port'))
                    post(owner.callback_port, callback('KeyboardVisible', value='true', mode='default'))
                    post(owner.callback_port, callback('TextEdited', state='Editing', value='fixture private address'))
                status = 401 if name == 'hello' and owner.reject_pin else 200
                self.send_response(status); self.send_header('Content-Length', '0'); self.end_headers()
            def do_GET(self):
                owner.names.append('count' if 'appnum_get' in self.path else 'list')
                if owner.disconnect_during_count and 'appnum_get' in self.path:
                    post(owner.callback_port, udap.byebye_request(8080).body, udap.PAIRING_PATH)
                body = count_xml(2) if 'appnum_get' in self.path else apps_xml(2)
                self.send_response(200); self.send_header('Content-Type', 'text/xml'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args): pass
        self.server = HTTPServer(('127.0.0.1', 0), TVFixture)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.config = udap.PeerConfig.loopback_fixture(self.server.server_port, timeout=1)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def run_session(self, pin_reader=lambda: '123456'):
        return live.run_inventory(self.config, approve_effects=lambda: True, pin_reader=pin_reader, lifetime=5)

    def assert_listener_closed(self):
        with self.assertRaises(OSError): socket.create_connection(('127.0.0.1', self.callback_port), timeout=0.2)

    def test_receiver_starts_before_hello_and_finally_disconnects_and_closes(self):
        result = self.run_session()
        self.assertIsNone(result.error)
        self.assertTrue(result.paired)
        self.assertTrue(result.disconnect_acknowledged)
        self.assertEqual(self.names, ['showKey', 'hello', 'count', 'list', 'byebye'])
        self.assertEqual(result.callback_summary['events'], 2)
        summary = result.summary()
        self.assertEqual(summary['apps_received'], 2)
        self.assertFalse(summary['physical_tv_confirmed'])
        self.assertFalse(summary['smarttext_transmission'])
        self.assertNotIn('fixture private address', repr(result))
        self.assertNotIn('Fixture app', json.dumps(summary))
        self.assert_listener_closed()

    def test_failed_pairing_has_no_retry_but_still_attempts_disconnect(self):
        self.reject_pin = True
        result = self.run_session()
        self.assertEqual(result.error, 'http_rejected')
        self.assertFalse(result.paired)
        self.assertEqual(self.names, ['showKey', 'hello', 'byebye'])
        self.assert_listener_closed()

    def test_peer_byebye_between_count_and_list_prevents_next_query(self):
        self.disconnect_during_count = True
        result = self.run_session()
        self.assertEqual(result.error, 'remote_session_ended')
        self.assertEqual(self.names, ['showKey', 'hello', 'count'])
        self.assertTrue(result.callback_summary['remote_closed'])
        self.assertFalse(result.disconnect_acknowledged)
        self.assert_listener_closed()

    def test_interrupt_during_disconnect_still_closes_listener(self):
        with patch.object(udap.Session, 'close', side_effect=KeyboardInterrupt):
            result = self.run_session()
        self.assertEqual(result.error, 'session_interrupted_during_disconnect')
        self.assertTrue(result.callback_summary['listener_stopped'])
        self.assert_listener_closed()

    def test_owner_decline_does_not_bind_or_contact_anything(self):
        with patch.object(live.CallbackReceiver, 'start') as start, self.assertRaises(udap.UDAPError):
            live.run_inventory(self.config, approve_effects=lambda: False)
        start.assert_not_called(); self.assertEqual(self.names, [])

    def test_preview_and_noninteractive_cli_do_not_open_sockets_or_echo_pin(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(live.CallbackReceiver, 'start') as start:
            self.assertEqual(live.main(['preview']), 0)
        self.assertEqual(json.loads(output.getvalue())['network_requests'], 0)
        start.assert_not_called()
        stderr = io.StringIO()
        with redirect_stderr(stderr), patch.object(live.CallbackReceiver, 'start') as start, patch('sys.stdin.isatty', return_value=False):
            code = live.main(['inventory', '--confirmed-target', '192.168.50.2', '--port', '8080', '--bind', '192.168.50.3', '--network', '192.168.50.0/24'])
        self.assertEqual(code, 2); start.assert_not_called()
        with redirect_stderr(stderr), self.assertRaises(SystemExit): live.main(['inventory', '--pin', 'synthetic-secret'])
        self.assertNotIn('synthetic-secret', stderr.getvalue())


class PrivateInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inventory = udap.Inventory(1, (udap.App('00000001', 'Fixture app', 2),), False)
        self.stamp = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.temporary.cleanup()

    def test_private_exclusive_report_retains_only_inventory_fields(self):
        relative = live.save_inventory(self.inventory, project_root=self.root, stamp=self.stamp)
        path = self.root / relative
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        report = json.loads(path.read_text())
        self.assertEqual(set(report), {'captured_at', 'total', 'partial', 'apps'})
        self.assertEqual(report['apps'], [{'auid': '00000001', 'name': 'Fixture app', 'category': 2}])
        before = path.read_bytes()
        with self.assertRaises(udap.UDAPError):
            live.save_inventory(self.inventory, project_root=self.root, stamp=self.stamp)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_symlinked_output_directory_is_rejected_without_external_writes(self):
        elsewhere = self.root / 'elsewhere'; elsewhere.mkdir()
        (self.root / 'artifacts').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(udap.UDAPError): live.save_inventory(self.inventory, project_root=self.root)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_final_symlink_is_not_overwritten_or_followed(self):
        directory = self.root / 'artifacts/diagnostics'; directory.mkdir(parents=True)
        target = self.root / 'owner-file'; target.write_text('preserve')
        filename = self.stamp.strftime('udap-inventory-%Y%m%dT%H%M%S-%fZ.json')
        (directory / filename).symlink_to(target)
        with self.assertRaises(udap.UDAPError): live.save_inventory(self.inventory, project_root=self.root, stamp=self.stamp)
        self.assertEqual(target.read_text(), 'preserve')
        self.assertTrue((directory / filename).is_symlink())
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_failed_publication_removes_private_temporary_output(self):
        with patch.object(os, 'link', side_effect=OSError(errno.ENOSPC, 'synthetic full disk')):
            with self.assertRaises(udap.UDAPError): live.save_inventory(self.inventory, project_root=self.root)
        self.assertEqual(list((self.root / 'artifacts/diagnostics').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
