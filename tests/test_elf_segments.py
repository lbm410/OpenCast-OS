"""Segment evidence for host-side artifact checks; never execute the fixture."""

import io
import struct
import unittest

from tests.test_elf_inventory import fixture
from tools.elf_inventory import inspect_stream


class SegmentEvidenceTests(unittest.TestCase):
    def test_both_classes_and_byte_orders_preserve_segment_fields(self):
        for bits in (32, 64):
            for endian in ("<", ">"):
                with self.subTest(bits=bits, endian=endian):
                    data = fixture(bits, endian)
                    result = inspect_stream(io.BytesIO(data), len(data))
                    self.assertEqual(result["program_headers"], len(result["segments"]))
                    self.assertEqual(result["segments"][0], {
                        "type": 1, "offset": 0, "address": 0x1000,
                        "file_size": 1024, "memory_size": 1024,
                        "flags": 5, "alignment": 4})
                    self.assertEqual([s["type"] for s in result["segments"]], [1, 2, 3])

    def test_zero_fill_and_permissions_remain_declarations(self):
        data = fixture()
        struct.pack_into("<I", data, 52 + 20, 4096)
        struct.pack_into("<I", data, 52 + 24, 7)
        segment = inspect_stream(io.BytesIO(data), len(data))["segments"][0]
        self.assertEqual((segment["file_size"], segment["memory_size"]), (1024, 4096))
        self.assertEqual(segment["flags"], 7)  # Report W+X; do not label it safe.

    def test_object_without_program_headers_reports_empty_list(self):
        data = fixture()
        struct.pack_into("<H", data, 16, 1)
        struct.pack_into("<H", data, 44, 0)
        result = inspect_stream(io.BytesIO(data), len(data))
        self.assertEqual(result["elf_type"], 1)
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["program_headers"], 0)

    def test_out_of_bounds_load_is_rejected_before_reporting(self):
        data = fixture()
        struct.pack_into("<I", data, 52 + 16, len(data) + 1)
        with self.assertRaisesRegex(ValueError, "file bounds"):
            inspect_stream(io.BytesIO(data), len(data))
