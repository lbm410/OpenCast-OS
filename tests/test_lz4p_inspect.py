"""Synthetic compression fixtures; no vendor content or target execution."""

from pathlib import Path
import os
import struct
import tempfile
import unittest
import zlib

from tools import lz4p_inspect as lz


def literals(data):
    size = len(data)
    block = bytes((min(size, 15) << 4,))
    if size >= 15:
        remaining = size - 15
        block += b"\xff" * (remaining // 255) + bytes((remaining % 255,))
    return block + data


def container(data, block_size=64, trailer=b""):
    blocks = [literals(data[i:i + block_size]) for i in range(0, len(data), block_size)]
    count = len(blocks)
    size = 32 + 4 * count + sum(map(len, blocks))
    return (struct.pack("<8I", 0x50345A4C, len(data), size, block_size, count, 0, 0, 0)
            + struct.pack("<" + "I" * count, *map(len, blocks)) + b"".join(blocks) + trailer)


def uimage(payload=b"kernel fixture"):
    header = bytearray(struct.pack(">7I4B32s", 0x27051956, 0, 1, len(payload),
                                  0x8000, 0x8000, zlib.crc32(payload), 5, 2, 2, 0, b"test"))
    struct.pack_into(">I", header, 4, zlib.crc32(header))
    return bytes(header) + payload


def cramfs():
    elf = (b"\x7fELF\x01\x01\x01" + bytes(9)
           + struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, 0x8000, 0, 0,
                         0x05000000, 52, 32, 0, 0, 0, 0))
    data = bytearray(4096 + len(elf))
    struct.pack_into("<4I16s", data, 0, 0x28cd3d45, len(data), 3, 0, b"Compressed ROMFS")
    struct.pack_into("<3I", data, 64, 0o40755, 20, (76 // 4) << 6)
    struct.pack_into("<3I8s", data, 76, 0o101755, len(elf), (96 // 4) << 6 | 2, b"RELEASE")
    data[4096:] = elf
    struct.pack_into("<I", data, 32, zlib.crc32(data))
    return data


def fix_cramfs_crc(data):
    struct.pack_into("<I", data, 32, 0)
    struct.pack_into("<I", data, 32, zlib.crc32(data))


class Lz4pTests(unittest.TestCase):
    def test_literals_multi_block_and_preserved_trailer(self):
        data = bytes(range(256)) * 4
        decoded, report = lz.decode_container(container(data, 300, b"opaque trailer"))
        self.assertEqual(decoded, data)
        self.assertEqual(report["blocks"], 4)
        self.assertEqual(report["trailer_bytes"], 14)

    def test_overlapping_match_and_extended_lengths(self):
        # Two literals, an overlapping 20-byte match, and five final literals.
        block = b"\x2fab\x02\x00\x01\x50cdefg"
        self.assertEqual(lz.decode_block(block, 27), b"ab" * 11 + b"cdefg")
        self.assertEqual(lz.decode_block(literals(b"a" * 600), 600), b"a" * 600)
        self.assertEqual(lz.decode_block(b"\x10a\x01\0", 5), b"aaaaa")

    def test_bad_offsets_truncation_and_expansion(self):
        for block, size in [(b"\x10a\0\0", 5), (b"\x10a\x02\0", 5),
                            (b"\x10a\x01", 5), (b"\xf0\xff", 1000),
                            (b"\x20a", 2), (b"\x1fa\x01\0\xff\0", 10),
                            (b"\x10a\x01\0", 6), (b"\x10a", 2)]:
            with self.subTest(block=block), self.assertRaises(ValueError):
                lz.decode_block(block, size)

    def test_header_bounds_and_table_consistency(self):
        original = container(b"small fixture")
        for offset, value in [(0, 0), (4, lz.MAX_OUTPUT + 1), (8, len(original) + 1),
                              (12, 0), (12, lz.MAX_BLOCK + 1), (16, 0),
                              (16, lz.MAX_BLOCKS + 1), (20, 1), (32, 0xffffffff)]:
            changed = bytearray(original)
            struct.pack_into("<I", changed, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                lz.decode_container(changed)
        with self.assertRaises(ValueError):
            lz.decode_container(original[:34])

    def test_uimage_crc_and_size(self):
        image = uimage()
        report = lz.inspect_uimage(image)
        self.assertTrue(report["data_crc_verified"])
        self.assertEqual(report["architecture_id"], 2)
        for offset in (12, 64):
            bad = bytearray(image)
            bad[offset] ^= 1
            with self.assertRaises(ValueError):
                lz.inspect_uimage(bad)
        with self.assertRaises(ValueError):
            lz.inspect_uimage(image + b"extra")

    def test_exclusive_readonly_output_and_input_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "decoded"
            source.write_bytes(container(uimage(), 128))
            report = lz.decode_file(source, target)
            self.assertTrue(report["uimage"]["header_crc_verified"])
            self.assertEqual(target.stat().st_mode & 0o777, 0o444)
            with self.assertRaises(FileExistsError):
                lz.decode_file(source, target)
            link = root / "link"
            link.symlink_to(source)
            with self.assertRaises(OSError):
                lz.decode_file(link, root / "other")
            out_link = root / "outlink"
            out_link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                lz.decode_file(source, out_link)
            directory_link = root / "dirlink"
            directory_link.symlink_to(root)
            with self.assertRaises(OSError):
                lz.decode_file(source, directory_link / "other")

    def test_malformed_data_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source", Path(directory) / "out"
            source.write_bytes(bytes(40))
            with self.assertRaises(ValueError):
                lz.decode_file(source, target)
            self.assertFalse(target.exists())

    def test_nonregular_input_is_rejected_without_waiting(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "pipe"
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                lz.decode_file(fifo, Path(directory) / "out")

    def test_cramfs_crc_xip_extent_and_elf(self):
        data = cramfs()
        report = lz.inspect_decoded(data)["cramfs"]
        self.assertTrue(report["crc_verified"])
        self.assertEqual(report["release"]["offset"], 4096)
        self.assertEqual(report["release"]["elf"]["machine"], "ARM")
        data[-1] ^= 1
        with self.assertRaises(ValueError):
            lz.inspect_cramfs_release(data)
        for offset, value in [(68, 0xffffff), (76, 0o100755), (80, 0xffffff),
                              (84, 0xffffffc2), (8, 0x100)]:
            data = cramfs()
            struct.pack_into("<I", data, offset, value)
            fix_cramfs_crc(data)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                lz.inspect_cramfs_release(data)


if __name__ == "__main__":
    unittest.main()
