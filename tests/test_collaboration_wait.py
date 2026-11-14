"""Fast synthetic mailbox tests; no agent process or real waiting is required."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import collaboration_wait as mailbox


class Clock:
    def __init__(self, arrival=None):
        self.now = 0.0
        self.sleeps = []
        self.arrival = arrival

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration
        if self.arrival is not None:
            self.arrival(self.now)


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / "collaboration" / "messages"
        self.directory.mkdir(parents=True)

    def wait(self, recipient="claude", after=0, timeout=30, interval=2, clock=None):
        clock = clock or Clock()
        return mailbox.wait_for_messages(recipient, after, timeout, interval, _root=self.root,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)

    def test_immediate_sorted_arrivals_do_not_read_bodies(self):
        for filename in ("to-claude-013.md", "to-claude-011.md", "to-claude-010.md",
                         "to-codex-999.md", "to-claude-12.md", "to-claude-014.md.tmp",
                         "to-claude-999.md\n", "to-claude-1000.md"):
            (self.directory / filename).write_text("PRIVATE BODY MUST NOT BE RETURNED")
        with patch.object(Path, "read_text", side_effect=AssertionError("body read")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("body read")):
            result = self.wait(after=10)
        self.assertEqual(result["messages"], [
            {"filename": "to-claude-011.md", "sequence": 11},
            {"filename": "to-claude-013.md", "sequence": 13},
        ])
        self.assertEqual(result["max_sequence"], 13)
        self.assertEqual(result["elapsed_seconds"], 0)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_arrival_after_two_polls(self):
        def arrival(now):
            if now == 4:
                (self.directory / "to-codex-002.md").touch()
        clock = Clock(arrival)
        result = self.wait("codex", 1, clock=clock)
        self.assertEqual(result["status"], "messages")
        self.assertEqual(result["max_sequence"], 2)
        self.assertEqual(clock.sleeps, [2, 2])

    def test_timeout_shortens_last_sleep_and_preserves_cursor(self):
        clock = Clock()
        result = self.wait(after=15, timeout=2.5, interval=2, clock=clock)
        self.assertEqual(clock.sleeps, [2, 0.5])
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["max_sequence"], 15)
        self.assertEqual(result["elapsed_seconds"], 2.5)
        self.assertEqual(result["messages"], [])

    def test_zero_timeout_does_not_sleep(self):
        clock = Clock()
        self.assertEqual(self.wait(timeout=0, clock=clock)["status"], "timeout")
        self.assertEqual(clock.sleeps, [])

    def test_maximum_requested_wait_is_sixty_seconds(self):
        clock = Clock()
        self.wait(timeout=60, interval=60, clock=clock)
        self.assertEqual(clock.sleeps, [60])

    def test_invalid_inputs_fail_before_opening_mailbox(self):
        cases = [("../claude", 0, 1, 1), ("CLAUDE", 0, 1, 1),
                 ("claude", -1, 1, 1), ("claude", True, 1, 1), ("claude", 1.5, 1, 1),
                 ("claude", 0, -1, 1), ("claude", 0, 61, 1),
                 ("claude", 0, float("nan"), 1), ("claude", 0, float("inf"), 1),
                 ("claude", 0, 1, 0.9), ("claude", 0, 1, float("nan")),
                 ("claude", 0, 1, 61), ("claude", 0, True, 1)]
        with patch.object(mailbox, "_open_mailbox", side_effect=AssertionError("opened mailbox")):
            for values in cases:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    mailbox.wait_for_messages(*values)

    def test_message_symlink_and_fifo_are_rejected_without_opening(self):
        secret = self.root / "outside"
        secret.write_text("PRIVATE")
        candidate = self.directory / "to-claude-001.md"
        candidate.symlink_to(secret)
        with self.assertRaises(ValueError):
            self.wait()
        candidate.unlink()
        os.mkfifo(candidate)
        with self.assertRaises(ValueError):
            self.wait()

    def test_symlinked_parent_and_mailbox_directory_are_rejected(self):
        link = self.root / "linked-root"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            mailbox.wait_for_messages("claude", 0, 0, _root=link)
        self.directory.rmdir()
        self.directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            self.wait(timeout=0)

    def test_missing_mailbox_is_not_created(self):
        self.directory.rmdir()
        with self.assertRaises(FileNotFoundError):
            self.wait(timeout=0)
        self.assertFalse(self.directory.exists())

    def test_entry_and_new_message_limits_fail_without_advancing_cursor(self):
        for index in range(1, 4):
            (self.directory / f"to-claude-{index:03}.md").touch()
        with patch.object(mailbox, "MAX_ENTRIES", 2), self.assertRaisesRegex(ValueError, "entry limit"):
            self.wait(timeout=0)
        with patch.object(mailbox, "MAX_MESSAGES", 2), self.assertRaisesRegex(ValueError, "Too many"):
            self.wait(timeout=0)

    def test_cli_has_fixed_root_and_only_structured_metadata(self):
        report = {"status": "messages", "messages": [{"filename": "to-claude-001.md", "sequence": 1}],
                  "max_sequence": 1}
        with patch.object(mailbox, "wait_for_messages", return_value=report) as wait, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(mailbox.main(["--recipient", "claude", "--after", "0"]), 0)
        wait.assert_called_once_with("claude", 0, 30, 2)
        self.assertEqual(json.loads(output.getvalue()), report)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            mailbox.main(["--recipient", "claude", "--after", "0", "--root", str(self.root)])

    def test_cli_validation_error_is_json_without_body(self):
        with redirect_stderr(io.StringIO()) as output:
            self.assertEqual(mailbox.main(["--recipient", "codex", "--after", "0", "--timeout", "nan"]), 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "error")


if __name__ == "__main__":
    unittest.main()
