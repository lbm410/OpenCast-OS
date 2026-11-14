"""Loopback-only report persistence failure tests; no device contact."""

import errno
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools import probe_server as probe
from test_probe_server import sample_v2


class PersistenceReviewTests(unittest.TestCase):
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

    def submit(self, report=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request("POST", "/report", json.dumps(report or sample_v2()))
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def assert_clean_failure_and_retry(self):
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(self.server.reports_saved, 0)
        self.assertEqual(self.submit()[0], 201)
        paths = list(self.output.iterdir())
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text())["probeVersion"], "input-001-v2")
        self.assertEqual(self.server.reports_saved, 1)

    def test_failed_atomic_publication_leaves_no_temporary_or_partial_report(self):
        with patch.object(probe.os, "link", side_effect=OSError(errno.ENOSPC, "synthetic disk full")):
            self.assertEqual(self.submit()[0], 500)
        self.assert_clean_failure_and_retry()

    def test_failure_response_is_sent_only_after_temporary_cleanup(self):
        # Observe the reply boundary in the handler thread, not a timing-based
        # directory snapshot after the client happens to receive the response.
        cleaned = threading.Event()
        snapshots = []
        original_unlink = Path.unlink
        handler = self.server.RequestHandlerClass
        original_reply = handler.reply
        output = self.output

        def tracked_unlink(path, *args, **kwargs):
            result = original_unlink(path, *args, **kwargs)
            if path.parent == output and path.name.startswith(".pending-"):
                cleaned.set()
            return result

        def observed_reply(request, status, *args, **kwargs):
            if status == 500:
                snapshots.append((cleaned.is_set(), tuple(output.iterdir()),
                                  request.server.reports_saved))
            return original_reply(request, status, *args, **kwargs)

        with patch.object(probe.os, "link", side_effect=OSError(errno.ENOSPC, "synthetic disk full")), \
                patch.object(Path, "unlink", tracked_unlink), \
                patch.object(handler, "reply", observed_reply):
            self.assertEqual(self.submit()[0], 500)
            # Keep patches alive until cleanup completes even on the old buggy
            # implementation, which sends its failure response first.
            self.assertTrue(cleaned.wait(2), "temporary cleanup did not complete")
        self.assertEqual(snapshots, [(True, (), 0)])
        self.assert_clean_failure_and_retry()

    def test_partial_temporary_write_is_cleaned_before_retry(self):
        original = probe.tempfile.NamedTemporaryFile

        class FailAfterPartialWrite:
            def __init__(self, *args, **kwargs):
                self.file = original(*args, **kwargs)
                self.name = self.file.name

            def __enter__(self):
                self.file.__enter__()
                return self

            def write(self, payload):
                self.file.write(payload[:10])
                raise OSError(errno.ENOSPC, "synthetic disk full")

            def __exit__(self, *args):
                return self.file.__exit__(*args)

        with patch.object(probe.tempfile, "NamedTemporaryFile", FailAfterPartialWrite):
            self.assertEqual(self.submit()[0], 500)
        self.assert_clean_failure_and_retry()

    def test_surrogate_request_creates_no_file_and_does_not_poison_next_request(self):
        report = sample_v2()
        report["userAgent"] = "invalid\ud800"
        self.assertEqual(self.submit(report)[0], 400)
        self.assert_clean_failure_and_retry()


if __name__ == "__main__":
    unittest.main()
