"""Offline tests: hostile inputs, network scope and wall-clock deadlines."""

import contextlib
import http.client
import io
import json
import signal
import time
import unittest
from unittest.mock import MagicMock, patch

from tools import discovery as d


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.network = d.local_network("192.168.1.0/24")
        self.target = "192.168.1.40"
        self.url = "http://192.168.1.40:8080/udap/api/data?target=netrcu.xml"

    def test_scope_rejects_public_large_and_non_network_addresses(self):
        for value in ("8.8.8.0/24", "127.0.0.0/24", "192.168.0.0/16", "192.168.1.2/24"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                d.local_network(value)
        for value in ("192.168.2.1", "192.168.1.0", "192.168.1.255", "::1", "localhost"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                d.local_host(value, self.network)

    def test_location_only_literal_confirmed_target(self):
        self.assertEqual(d.validate_location(self.url, self.target, self.network), self.url)
        for url in ("http://example.com/a", "http://192.168.1.41/a", "https://192.168.1.40/a",
                    "http://user@192.168.1.40/a", "http://192.168.1.40/a#b",
                    "http://192.168.1.40:0/a", "http://192.168.1.40:65536/a",
                    "http://192.168.1.40/a\r\nInjected: x", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                d.validate_location(url, self.target, self.network)

    def test_ssdp_packet_and_parse_without_identifiers(self):
        packet = d.search_packet("udap:rootservice")
        self.assertTrue(packet.endswith(b"\r\n\r\n"))
        self.assertIn(b"USER-AGENT: UDAP/2.0", packet)
        parsed = d.parse_ssdp(b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.40/a\r\n"
                              b"USN: private-identifier\r\nSERVER: LG\r\n\r\n")
        self.assertEqual(parsed, {"location": "http://192.168.1.40/a", "server": "LG"})

    def test_ssdp_rejects_malformed_and_oversized(self):
        for value in (b"HTTP/1.1 500 Error\r\n\r\n", b"x" * 8193,
                      b"HTTP/1.1 200 OK\r\nSERVER: x\r\nserver: y\r\n\r\n",
                      b"HTTP/1.1 200 OK\r\nnot-a-header\r\n\r\n"):
            with self.subTest(value=value[:50]), self.assertRaises(ValueError):
                d.parse_ssdp(value)

    def test_xml_namespaces_and_privacy(self):
        fields = d.parse_description(b'<root xmlns="urn:test"><device><modelName>47LA620S</modelName>'
                                      b'<serialNumber>PRIVATE</serialNumber></device></root>')
        self.assertEqual(fields, {"modelName": ["47LA620S"]})

    def test_xml_rejects_entities_utf16_and_size(self):
        xml = '<!DOCTYPE root [<!ENTITY e "test">]><root>&e;</root>'
        for data in (xml.encode(), xml.encode("utf-16"), xml.encode("utf-16-le"),
                     b"x" * (d.MAX_BODY + 1)):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                d.parse_description(data)

    def test_udap_service_attributes_are_preserved(self):
        data = (b'<envelope><serviceList><service name="netrcu"><apiList>'
                b'<api type="query"><name>volume_info</name></api>'
                b'</apiList></service></serviceList></envelope>')
        self.assertEqual(d.parse_description(data)["udapServices"],
                         [{"name": "netrcu", "apis": [{"type": "query", "names": ["volume_info"]}]}])

    def test_redirect_never_followed(self):
        with self.assertRaises(ValueError):
            d.NoRedirect().redirect_request(None, None, 302, "", {}, "http://8.8.8.8/")

    def test_get_disables_proxies_and_limits_body(self):
        response = MagicMock()
        response.status = 200
        response.read1.side_effect = [b"<root><modelName>test</modelName></root>", b""]
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(d.urllib.request, "build_opener", return_value=opener) as build:
            result = d.describe(self.url, self.target, self.network)
        self.assertEqual(result["fields"]["modelName"], ["test"])
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], d.NoRedirect)
        self.assertEqual(opener.open.call_args.args[0].get_method(), "GET")
        self.assertTrue(all(c.args[0] <= 8192 for c in response.read1.call_args_list))

    def test_timeout_covers_opener_and_restores_signal(self):
        previous = signal.getsignal(signal.SIGALRM)
        opener = MagicMock()
        opener.open.side_effect = lambda *a, **kw: time.sleep(2)
        start = time.monotonic()
        with patch.object(d.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(TimeoutError):
                d.describe(self.url, self.target, self.network, timeout=0.05)
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_http_errors_are_structured(self):
        args = ["discovery", "describe", "--confirmed-target", self.target,
                "--network", str(self.network), "--location", self.url]
        for error in (http.client.BadStatusLine("bad"), http.client.LineTooLong("header"),
                      http.client.IncompleteRead(b"part", 100)):
            output = io.StringIO()
            with patch("sys.argv", args), patch.object(d, "describe", side_effect=error):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(d.main(), 2)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "blocked_or_error")
            self.assertIn("observed_at", result)


if __name__ == "__main__":
    unittest.main()
