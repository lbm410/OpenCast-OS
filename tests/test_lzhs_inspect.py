"""Synthetic LZHS tests; no vendor firmware or proprietary tables are fixtures."""

import contextlib
import hashlib
import io
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock

from tools import lzhs_inspect as lzhs


def tables():
    # Fixed-width synthetic prefix codes keep fixture construction independent.
    return (lzhs.CodeTable([(i, 9) for i in range(288)], 9),
            lzhs.CodeTable([(i, 5) for i in range(32)], 5))


def token_bits(tokens):
    bits = ""
    for token in tokens:
        if isinstance(token, int):
            bits += format(token, "09b")
        else:
            length, distance = token
            bits += format(256 + length - 3, "09b")
            bits += format(distance >> 7, "05b") + format(distance & 127, "07b")
    return bits


def container(tokens, output, *, suffix_bits="", checksum=None):
    bits = token_bits(tokens) + suffix_bits
    # The reference encoder always writes its last byte, even when aligned.
    bits += "0" * (8 - len(bits) % 8)
    payload = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    checksum = sum(output) & 255 if checksum is None else checksum
    return struct.pack("<IIH6s", len(output), len(payload), checksum, bytes(6)) + payload


class LzhsTests(unittest.TestCase):
    def test_literals_offset_and_alignment_padding(self):
        for output in (b"A", b"ABCDEFGH"):
            decoded, report = lzhs.decode_container(b"prefix" + container(output, output) + b"suffix", 6, tables())
            self.assertEqual(decoded, output)
            self.assertEqual(report["zero_padding_bits"], 8 - (9 * len(output)) % 8)
            self.assertTrue(report["checksum_valid"])

    def test_overlap_match_and_zero_initialized_ring(self):
        for tokens, output in (([65, (34, 1)], b"A" * 35), ([(3, 0)], bytes(3)),
                               ([(3, 4095)], bytes(3)), ([65, 66, (6, 2)], b"ABABABAB")):
            self.assertEqual(lzhs.decode_container(container(tokens, output), 0, tables())[0], output)

    def test_ring_wrap_and_distance_zero(self):
        # Avoid incidental Thumb BL signatures in this dictionary-only test.
        output = bytes(range(128)) * 32
        expected = output + output[:3]
        self.assertEqual(lzhs.decode_container(container(list(output) + [(3, 0)], expected),
                                              0, tables())[0], expected)

    def test_thumb_branch_conversion_and_scan_stride(self):
        # Encoded absolute target 4 at position 0 becomes relative target 0.
        data = bytearray(b"\x00\xf0\x02\xf8\x00\x00\x00\xf0\x05\xf8x")
        self.assertEqual(lzhs.thumb_decode(data), 2)
        self.assertEqual(data, b"\x00\xf0\x00\xf8\x00\x00\x00\xf0\x00\xf8x")
        wrapping = bytearray(b"\x00\xf0\x00\xf8")
        lzhs.thumb_decode(wrapping)
        self.assertEqual(wrapping, b"\xff\xf7\xfe\xff")

    def test_checksum_is_after_thumb_transform(self):
        encoded = b"\x00\xf0\x02\xf8"
        expected = b"\x00\xf0\x00\xf8"
        self.assertEqual(lzhs.decode_container(container(encoded, expected), 0, tables())[0], expected)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            lzhs.decode_container(container(encoded, encoded), 0, tables())

    def test_size_offset_reserved_and_checksum_rejections(self):
        good = container([65], b"A")
        bad = [b"", good[:15], struct.pack("<IIH6s", 0, 1, 0, bytes(6)),
               struct.pack("<IIH6s", lzhs.MAX_OUTPUT + 1, 1, 0, bytes(6)),
               struct.pack("<IIH6s", 1, lzhs.MAX_COMPRESSED + 1, 0, bytes(6)),
               struct.pack("<IIH6s", 1, 0, 0, bytes(6)),
               good[:8] + b"\x00\x01" + good[10:],
               good[:10] + b"\x01" + good[11:], good[:-1],
               container([65], b"A", checksum=66)]
        for data in bad:
            with self.subTest(data=data[:16]), self.assertRaises(ValueError):
                lzhs.decode_container(data, 0, tables())
        for offset in (-1, len(good) - 15, 10**100):
            with self.assertRaises(ValueError):
                lzhs.decode_container(good, offset, tables())

    def test_truncated_huffman_position_and_raw_distance(self):
        for bits in ("0", format(256, "09b"), format(256, "09b") + "00000"):
            payload = int(bits.ljust(((len(bits) + 7) // 8) * 8, "0"), 2).to_bytes((len(bits) + 7) // 8, "big")
            data = struct.pack("<IIH6s", 3, len(payload), 0, bytes(6)) + payload
            with self.assertRaisesRegex(ValueError, "Truncated"):
                lzhs.decode_container(data, 0, tables())

    def test_output_overrun_nonzero_and_excessive_padding(self):
        with self.assertRaisesRegex(ValueError, "exceeds declared output"):
            lzhs.decode_container(container([(3, 0)], b"\0\0"), 0, tables())
        for suffix in ("1", "00000000"):
            with self.assertRaisesRegex(ValueError, "padding"):
                lzhs.decode_container(container([65], b"A", suffix_bits=suffix), 0, tables())

    def test_huffman_table_validation(self):
        for entries, maximum in (([], 9), ([(0, 0)], 9), ([(4, 2)], 9),
                                 ([(0, 1), (0, 1)], 9), ([(0, 1), (0, 2)], 9),
                                 ([(0, 14)], 14), ([(0, 1)] * 289, 9)):
            with self.assertRaises(ValueError):
                lzhs.CodeTable(entries, maximum)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            lzhs.CodeTable([(0, 1)], 1).decode(lzhs.BitReader(b"\x80"))
        with self.assertRaisesRegex(ValueError, "dimensions"):
            lzhs.decode_container(container([65], b"A"), 0,
                                  (lzhs.CodeTable([(0, 1)], 1), tables()[1]))

    def test_pinned_table_source_rejects_modified_or_oversized_data(self):
        for data in (b"anything", b"x" * (lzhs.MAX_TABLE_FILE + 1)):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                lzhs.parse_tables(data)

    def test_table_initializer_parser_with_synthetic_pinned_fixture(self):
        sections = []
        for name, count, bits in (("charlen_table", 288, 9), ("pos_table", 32, 5)):
            raw = b"".join(struct.pack("<II", index, bits) for index in range(count))
            sections.append("static uint8_t " + name + "[" + str(len(raw)) + "] = {" +
                            ", ".join("0x%02x" % value for value in raw) + "};")
        source = "\n".join(sections).encode("ascii")
        with mock.patch.object(lzhs, "TABLE_SHA256", hashlib.sha256(source).hexdigest()):
            parsed = lzhs.parse_tables(source)
            self.assertEqual(lzhs.decode_container(container([65], b"A"), 0, parsed)[0], b"A")
        bad = source.replace(b"0x00", b"danger()", 1)
        with mock.patch.object(lzhs, "TABLE_SHA256", hashlib.sha256(bad).hexdigest()):
            with self.assertRaisesRegex(ValueError, "initializer"):
                lzhs.parse_tables(bad)

    def test_files_are_bounded_regular_and_outputs_exclusive_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            source = directory / "source"
            source.write_bytes(b"1234")
            self.assertEqual(lzhs.read_bounded(source, 4), b"1234")
            with self.assertRaises(ValueError):
                lzhs.read_bounded(source, 3)
            for candidate in (directory,):
                with self.assertRaises((OSError, ValueError)):
                    lzhs.read_bounded(candidate, 20)
            output = directory / "output"
            lzhs.write_exclusive(output, b"ok")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o444)
            with self.assertRaises(FileExistsError):
                lzhs.write_exclusive(output, b"replace")
            self.assertEqual(output.read_bytes(), b"ok")
            link = directory / "link"
            link.symlink_to(source)
            with self.assertRaises(OSError):
                lzhs.read_bounded(link, 20)
            with self.assertRaises(OSError):
                lzhs.write_exclusive(link, b"replace")
            sublink = directory / "sublink"
            sublink.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(OSError):
                lzhs.read_bounded(sublink / "source", 20)
            fifo = directory / "fifo"
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                lzhs.read_bounded(fifo, 20)

    def test_invalid_payload_does_not_create_cli_output(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            source = directory / "source"
            source.write_bytes(container([65], b"A", checksum=0))
            output = directory / "output"
            with mock.patch.object(lzhs, "parse_tables", return_value=tables()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                result = lzhs.main([str(source), "--tables", str(source), "--offset", "0", "--output", str(output)])
            self.assertEqual(result, 1)
            self.assertIn("checksum mismatch", errors.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
