"""Regression cases derived from the independent hostile-metadata review."""

import io
import os
from pathlib import Path
import struct
import tempfile
import unittest

from tools import elf_inventory as elf
from test_elf_inventory import fixture


def repeated_name_fixture(count):
    """An ELF with repeated references to one long string, not vendor material."""
    data = fixture() + bytes(65536 - 1024)
    struct.pack_into("<H", data, 44, 2)  # No interpreter segment.
    struct.pack_into("<II", data, 52 + 16, len(data), len(data))
    dynamic = [(5, 0x1000 + 40000), (10, 4096)] + [(1, 0)] * count + [(0, 0)]
    struct.pack_into("<II", data, 84 + 16, len(dynamic) * 8, len(dynamic) * 8)
    data[40000:44096] = b"A" * 4095 + b"\0"
    for index, pair in enumerate(dynamic):
        struct.pack_into("<iI", data, 256 + index * 8, *pair)
    return data


class ElfReviewTests(unittest.TestCase):
    def test_repeated_string_references_cannot_expand_one_file_unboundedly(self):
        data = repeated_name_fixture(4093)
        with self.assertRaisesRegex(ValueError, "metadata budget"):
            elf.inspect_stream(io.BytesIO(data), len(data))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "amplifier").write_bytes(data)
            report = elf.scan_tree(root)
            self.assertEqual(report["status"], "partial")
            self.assertFalse(report["complete"])
            self.assertEqual(report["files"], [])
            self.assertIn("metadata budget", report["errors"][0]["error"])

    def test_aggregate_metadata_budget_stops_many_individually_valid_files(self):
        data = repeated_name_fixture(64)
        self.assertEqual(len(elf.inspect_stream(io.BytesIO(data), len(data))["needed"]), 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(65):
                (root / ("sample-%03d" % index)).write_bytes(data)
            report = elf.scan_tree(root)
            self.assertEqual(report["status"], "metadata_limit_reached")
            self.assertFalse(report["complete"])
            self.assertLess(len(report["files"]), 65)
            self.assertLessEqual(report["accounted_bytes"], 65 * len(data))

    def test_unreadable_directory_is_partial_not_a_complete_empty_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            denied = root / "denied"
            denied.mkdir()
            (denied / "sample").write_bytes(fixture())
            denied.chmod(0)
            try:
                if os.access(denied, os.R_OK):
                    self.skipTest("Current account bypasses directory read permissions")
                report = elf.scan_tree(root)
                self.assertEqual(report["status"], "partial")
                self.assertFalse(report["complete"])
                self.assertEqual(report["files"], [])
                self.assertEqual(report["errors"][0]["path"], "denied")
            finally:
                denied.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
