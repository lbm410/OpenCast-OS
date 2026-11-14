"""Synthetic ELF fixtures only: no vendor binaries and no target execution."""

import io
import os
from pathlib import Path
import struct
import tempfile
import unittest

from tools import elf_inventory as elf


def fixture(bits=32, endian="<", machine=40):
    data = bytearray(1024)
    data[:16] = b"\x7fELF" + bytes((1 if bits == 32 else 2, 1 if endian == "<" else 2,
                                     1, 0, 0)) + bytes(7)
    size, phsize = (52, 32) if bits == 32 else (64, 56)
    fmt = endian + ("HHIIIIIHHHHHH" if bits == 32 else "HHIQQQIHHHHHH")
    struct.pack_into(fmt, data, 16, 2, machine, 1, 0x1000, size, 0, 0x05000200,
                     size, phsize, 3, 0, 0, 0)
    string_table = b"\0libc.so.6\0libvendor.so\0sample.so\0"
    data[600:600+len(string_table)] = string_table
    interpreter = b"/lib/ld-linux.so.3\0"
    data[500:500+len(interpreter)] = interpreter
    width = 8 if bits == 32 else 16
    dynamic = [(5, 0x1000+600), (10, len(string_table)), (1, 1), (1, 11), (14, 24), (0, 0)]
    # The exact offsets are checked below rather than assuming the fixture is valid.
    dynamic[4] = (14, string_table.index(b"sample.so"))
    for index, pair in enumerate(dynamic):
        struct.pack_into(endian + ("iI" if bits == 32 else "qQ"), data, 256 + index*width, *pair)
    segments = [(1, 0, 0x1000, len(data), len(data), 5),
                (2, 256, 0x1100, len(dynamic)*width, len(dynamic)*width, 6),
                (3, 500, 0x1000+500, len(interpreter), len(interpreter), 4)]
    for index, (kind, offset, address, filesz, memsz, flags) in enumerate(segments):
        values = ((kind, offset, address, address, filesz, memsz, flags, 4) if bits == 32 else
                  (kind, flags, offset, address, address, filesz, memsz, 4))
        struct.pack_into(endian + ("8I" if bits == 32 else "II6Q"), data, size+index*phsize, *values)
    return data


class ElfTests(unittest.TestCase):
    def test_conflicting_float_flags_are_not_reported_as_hard_float(self):
        data = fixture()
        struct.pack_into("<I", data, 36, 0x05000600)
        self.assertEqual(elf.inspect_stream(io.BytesIO(data), len(data))["arm_float_abi_flags"], "conflicting")

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fifo"
            os.mkfifo(path)
            with self.assertRaises(ValueError):
                elf.inspect_file(path)

    def test_directory_and_cumulative_byte_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                (root / str(index)).mkdir()
            result = elf.scan_tree(root, limit=1)
            self.assertFalse(result["complete"])
            self.assertEqual(result["visited"], 1)
            (root / "sample").write_bytes(fixture())
            self.assertEqual(elf.scan_tree(root, byte_limit=10)["status"], "byte_limit_reached")

    def test_architecture_endianness_and_dependencies(self):
        for bits, endian, machine in ((32, "<", 40), (32, ">", 8), (64, "<", 183)):
            with self.subTest(bits=bits, endian=endian):
                data = fixture(bits, endian, machine)
                result = elf.inspect_stream(io.BytesIO(data), len(data))
                self.assertEqual(result["bits"], bits)
                self.assertEqual(result["machine_id"], machine)
                self.assertEqual(result["needed"], ["libc.so.6", "libvendor.so"])
                self.assertEqual(result["interpreter"], "/lib/ld-linux.so.3")
                self.assertEqual(result["soname"], ["sample.so"])
                if machine == 40:
                    self.assertEqual(result["arm_eabi_version"], 5)
                    self.assertEqual(result["arm_float_abi_flags"], "soft")

    def test_segment_bounds_and_bad_string_offset(self):
        data = fixture()
        struct.pack_into("<I", data, 52+16, len(data)+1)
        with self.assertRaises(ValueError):
            elf.inspect_stream(io.BytesIO(data), len(data))
        data = fixture()
        struct.pack_into("<I", data, 256+2*8+4, 999999)
        with self.assertRaises(ValueError):
            elf.inspect_stream(io.BytesIO(data), len(data))

    def test_truncated_or_non_elf(self):
        for data in (b"", b"not ELF"*20, fixture()[:30]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                elf.inspect_stream(io.BytesIO(data), len(data))

    def test_missing_dynamic_terminator(self):
        data = fixture()
        struct.pack_into("<iI", data, 256+5*8, 1, 1)
        with self.assertRaises(ValueError):
            elf.inspect_stream(io.BytesIO(data), len(data))

    def test_tree_hashes_and_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample"
            target.write_bytes(fixture())
            (root/"link").symlink_to(target)
            (root/"text").write_text("not an executable")
            result = elf.scan_tree(root)
            self.assertTrue(result["complete"])
            self.assertEqual([entry["path"] for entry in result["files"]], ["sample"])
            self.assertEqual(len(result["files"][0]["sha256"]), 64)
            with self.assertRaises(OSError):
                elf.inspect_file(root/"link")


if __name__ == "__main__":
    unittest.main()
