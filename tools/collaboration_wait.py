"""Wait briefly for mailbox filenames; never read messages or wake an idle agent.

The CLI uses this repository's collaboration/messages directory only. An active
agent may call it again after a heartbeat; this tool never starts a daemon.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Callable

PROJECT_ROOT = Path(__file__).absolute().parent.parent
MAX_ENTRIES = 4096
MAX_MESSAGES = 256


def validate(recipient: str, after: int, timeout: float, interval: float) -> None:
    if recipient not in ("claude", "codex"):
        raise ValueError("Recipient must be claude or codex")
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise ValueError("After must be a nonnegative integer")
    for value, minimum, maximum, label in (
        (timeout, 0, 60, "Timeout"), (interval, 1, 60, "Interval")
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(label + " must be finite")
        if not minimum <= value <= maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum} seconds")


def _open_mailbox(root: Path) -> int:
    """Open each existing directory without following symlinks."""
    parts = root.absolute().parts
    if ".." in parts:
        raise ValueError("Parent traversal is not supported")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(parts[0], flags)
    try:
        for component in (*parts[1:], "collaboration", "messages"):
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _scan(descriptor: int, recipient: str, after: int) -> list[dict]:
    pattern = re.compile(r"to-" + recipient + r"-([0-9]{3})\.md\Z")
    messages = []
    # scandir duplicates the supplied descriptor and does not close our copy.
    with os.scandir(descriptor) as entries:
        for count, entry in enumerate(entries, 1):
            if count > MAX_ENTRIES:
                raise ValueError("Mailbox directory exceeds the entry limit")
            match = pattern.fullmatch(entry.name)
            if match is None:
                continue
            sequence = int(match.group(1))
            if sequence <= after:
                continue
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except FileNotFoundError:
                # A concurrently removed entry is no longer an arrival.
                continue
            if not stat.S_ISREG(mode):
                raise ValueError("New message candidates must be regular files, never symlinks")
            messages.append({"filename": entry.name, "sequence": sequence})
            if len(messages) > MAX_MESSAGES:
                raise ValueError("Too many new messages; inspect the mailbox explicitly")
    return sorted(messages, key=lambda message: message["sequence"])


def wait_for_messages(
    recipient: str,
    after: int,
    timeout: float = 30,
    interval: float = 2,
    *,
    _root: Path = PROJECT_ROOT,
    _monotonic: Callable[[], float] = time.monotonic,
    _sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Observe filenames until an arrival or deadline; injected hooks are for tests.

    Names have exactly three sequence digits. max_sequence advances only over
    returned filenames, not over ignored entries. Missing/unsafe mailboxes fail
    without creating directories. Timeout bounds scheduled waiting; filesystem
    calls and process scheduling are not a hard real-time guarantee.
    """
    validate(recipient, after, timeout, interval)
    started = _monotonic()
    deadline = started + timeout
    descriptor = _open_mailbox(_root)
    try:
        while True:
            messages = _scan(descriptor, recipient, after)
            now = _monotonic()
            if messages or now >= deadline:
                return {
                    "status": "messages" if messages else "timeout",
                    "recipient": recipient,
                    "after": after,
                    "messages": messages,
                    "max_sequence": messages[-1]["sequence"] if messages else after,
                    "elapsed_seconds": round(max(0.0, now - started), 3),
                }
            _sleep(min(interval, deadline - now))
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", required=True, choices=("claude", "codex"))
    parser.add_argument("--after", required=True, type=int, help="Last observed sequence, nonnegative")
    parser.add_argument("--timeout", type=float, default=30,
                        help="Maximum requested wait in seconds, 0 to 60 (default: 30)")
    parser.add_argument("--interval", type=float, default=2,
                        help="Polling interval in seconds, 1 to 60 (default: 2)")
    args = parser.parse_args(argv)
    try:
        report = wait_for_messages(args.recipient, args.after, args.timeout, args.interval)
    except (OSError, ValueError) as error:
        # Do not include arbitrary filesystem paths or any message contents.
        detail = error.strerror if isinstance(error, OSError) else str(error)
        print(json.dumps({"status": "error", "error": detail}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
