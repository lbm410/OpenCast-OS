"""Loopback-only integration tests; never contact the TV or other LAN devices."""

import http.client
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from tools import probe_server as probe


def sample_report():
    return {"userAgent": "Synthetic unit-test client", **{n: 1 for n in probe.NUMBER_FIELDS},
            "features": {n: False for n in probe.FEATURE_FIELDS}}


def sample_v2():
    return {**sample_report(), "probeVersion": "input-001-v2",
            "features": {n: False for n in probe.V2_FEATURES},
            "eventCounts": {n: 1 for n in probe.EVENT_TYPES},
            "activeElement": "focusButton", "droppedEvents": 0,
            "events": [{"type": "keydown", "key": 37, "target": "card0",
                        "active": "card0", "phase": "capture", "elapsedMs": 4}]}


class ReportTests(unittest.TestCase):
    def test_legacy_and_v2_are_accepted_without_schema_mixing(self):
        for report in (sample_report(), sample_v2()):
            self.assertEqual(probe.validate_report(json.dumps(report).encode()), report)
        report = sample_report()
        report["probeVersion"] = "input-001-v2"
        with self.assertRaises(ValueError):
            probe.validate_report(json.dumps(report).encode())

    def test_v2_rejects_unbounded_or_private_event_fields(self):
        mutations = (
            lambda r: r.update(events=r["events"] * 17),
            lambda r: r.update(activeElement="input containing private text"),
            lambda r: r.update(droppedEvents=True),
            lambda r: r.update(keyEvents=2),
            lambda r: r.update(probeVersion="unknown"),
            lambda r: r["events"][0].update(value="private text"),
            lambda r: r["events"][0].update(key=65536),
            lambda r: r["events"][0].update(target="a\n"),
            lambda r: r["events"][0].update(phase="unknown"),
            lambda r: r["events"][0].update(elapsedMs=-1),
            lambda r: r["eventCounts"].update(click=False),
        )
        for mutate in mutations:
            report = copy.deepcopy(sample_v2())
            mutate(report)
            with self.subTest(report=report), self.assertRaises(ValueError):
                probe.validate_report(json.dumps(report).encode())

    def test_parser_rejects_duplicate_fields_and_excessive_nesting(self):
        for data in (b'{"userAgent":"first","userAgent":"second"}',
                     b"[" * 2000 + b"]" * 2000, b" " * (probe.MAX_REPORT_BYTES + 1)):
            with self.assertRaises(ValueError):
                probe.validate_report(data)

    def test_unpaired_surrogate_is_rejected_before_storage(self):
        report = sample_report()
        report["userAgent"] = "invalid\ud800"
        with self.assertRaises(ValueError):
            probe.validate_report(json.dumps(report).encode())

    def test_report_schema_rejects_arbitrary_or_oversized_data(self):
        for data in (b"x" * 4097, b"[]", b'{}', b'{"secret":"do not store"}'):
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                probe.validate_report(data)
        report = sample_report()
        report["loadMs"] = float("nan")
        with self.assertRaises(ValueError):
            probe.validate_report(json.dumps(report).encode())

    def test_public_or_wildcard_bind_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for bind, allowed in (("0.0.0.0", "192.168.1.40"), ("8.8.8.8", "8.8.8.8"),
                                  ("127.0.0.1", "192.168.1.40")):
                with self.subTest(bind=bind), self.assertRaises(ValueError):
                    probe.make_server(bind, 0, allowed, Path(directory))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.output = Path(self.directory.name)
        self.server = probe.make_server("127.0.0.1", 0, "127.0.0.1", self.output)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_static_allowlist_and_no_repo_exposure(self):
        status, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Hello, OpenCast.", data)
        for path in ("/../../AGENTS.md", "/.git/config", "/firmware/", "/%2e%2e/README.md"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("GET", "/shell/")[0], 404)

    def test_report_roundtrip_is_not_physical_confirmation(self):
        status, _ = self.request("POST", "/report", json.dumps(sample_report()))
        self.assertEqual(status, 201)
        report = json.loads(next(self.output.glob("*.json")).read_text())
        self.assertFalse(report["physical_tv_confirmed"])
        self.assertEqual(report["userAgent"], "Synthetic unit-test client")

    def test_v2_report_roundtrip(self):
        self.assertEqual(self.request("POST", "/report", json.dumps(sample_v2()))[0], 201)
        report = json.loads(next(self.output.glob("*.json")).read_text())
        self.assertEqual(report["probeVersion"], "input-001-v2")
        self.assertFalse(report["physical_tv_confirmed"])

    def test_cross_origin_and_unexpected_post_are_rejected(self):
        self.assertEqual(self.request("POST", "/report", json.dumps(sample_report()),
                                      {"Origin": "http://unrelated.example"})[0], 403)
        self.assertEqual(self.request("POST", "/command", "")[0], 404)
        self.assertFalse(list(self.output.glob("*.json")))

    def test_other_peers_fail_before_request_processing(self):
        self.assertFalse(self.server.verify_request(None, ("192.168.1.99", 1000)))


class ShellRouteTests(unittest.TestCase):
    def test_opt_in_serves_complete_shell_and_only_current_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            with probe.make_server("127.0.0.1", 0, "127.0.0.1", Path(directory),
                                   include_shell=True) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    for path, (filename, mime) in probe.SHELL_ASSETS.items():
                        connection = http.client.HTTPConnection(*server.server_address, timeout=2)
                        try:
                            connection.request("GET", path)
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200)
                            self.assertEqual(response.read(), (probe.SHELL_ROOT / filename).read_bytes())
                            self.assertTrue(response.getheader("Content-Type").startswith(mime))
                        finally:
                            connection.close()
                    for path in ("/shell/../README.md", "/shell/assets/landscape.jpg", "/shell/assets/",
                                 "/shell/%2e%2e/.git/config", "/shell/../../firmware/lab/input.epk"):
                        connection = http.client.HTTPConnection(*server.server_address, timeout=2)
                        try:
                            connection.request("GET", path)
                            response = connection.getresponse()
                            self.assertEqual(response.status, 404)
                            response.read()
                        finally:
                            connection.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
