"""Synthetic ELF only: no private firmware, external tools or target execution."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import arm_branch_index as branch
from tools import arm_disassembly as reader


def elf(words, base=0x1000, kind=2, flags=5, extra_mapping=False):
    payload = b"".join(struct.pack("<I", word) for word in words)
    data = bytearray(256 + len(payload))
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    data[:52] = struct.pack("<16sHHIIIIIHHHHHH", ident, kind, 40, 1, base,
                           52, 0, 0x5000000, 52, 32, 2 if extra_mapping else 1, 0, 0, 0)
    struct.pack_into("<8I", data, 52, 1, 256, base, base, len(payload), len(payload), flags, 4)
    if extra_mapping:
        struct.pack_into("<8I", data, 84, 1, 256, base, base, len(payload), len(payload), 4, 4)
    data[256:] = payload
    return bytes(data)


def index(data, start=0x1000, end=None):
    return branch.index_bytes(data, start, end if end is not None else start + len(data) - 256,
                              arm_state=True)


class BranchIndexTests(unittest.TestCase):
    def test_forward_conditional_and_backward_rejoin_regression(self):
        # Literal encodings from the reviewed addresses; all other fixture words are NOP.
        words = [0xE1A00000] * ((0x167E4 - 0x16580) // 4)
        words[0] = 0x1A000090       # 0x16580 BNE -> 0x167c8
        words[-1] = 0xEAFFFF67      # 0x167e0 B -> 0x16584
        report = index(elf(words, base=0x16580), 0x16580, 0x167E4)
        first, rejoin = report["candidates"]
        self.assertEqual((first["source"], first["target"], first["condition"], first["kind"]),
                         ("0x00016580", "0x000167c8", "NE", "jump"))
        self.assertEqual((rejoin["source"], rejoin["target"], rejoin["offset_bytes"]),
                         ("0x000167e0", "0x00016584", -612))
        self.assertEqual(first["target_relation"], "in-range")
        self.assertEqual(rejoin["target_relation"], "in-range")
        narrow = index(elf([0x1A000090], base=0x16580), 0x16580)
        self.assertEqual(narrow["candidates"][0]["target_relation"], "outside")

    def test_signed_extremes_and_32_bit_wrapping(self):
        report = index(elf([0xEA800000, 0xEB7FFFFF]))
        low, high = report["candidates"]
        self.assertEqual((low["offset_bytes"], low["target"]), (-33554432, "0xfe001008"))
        self.assertEqual((high["offset_bytes"], high["target"], high["kind"]),
                         (33554428, "0x02001008", "call"))
        high_pc = index(elf([0xEA000000], base=0xFFFFFFFC), 0xFFFFFFFC, 2**32)
        self.assertEqual(high_pc["candidates"][0]["target"], "0x00000004")

    def test_all_conditions_and_blx_h_variants_excluded(self):
        words = [(condition << 28) | 0x0A000000 for condition in range(15)]
        words += [0xFA000000, 0xFB000000, 0xFAFFFFFF, 0xFBFFFFFF, 0xE12FFF1E, 0xE12FFF30]
        report = index(elf(words))
        self.assertEqual([row["condition"] for row in report["candidates"]], list(branch.CONDITIONS))
        self.assertEqual([row["condition_bits"] for row in report["candidates"]], list(range(15)))
        self.assertEqual(report["excluded_blx_immediate_count"], 4)
        self.assertEqual(report["candidate_count"], 15)
        self.assertTrue(all(row["kind"] == "jump" for row in report["candidates"]))

    def test_half_open_range_and_zero_displacement(self):
        report = index(elf([0xEAFFFFFE, 0xEBFFFFFF, 0xEA000000]))
        self.assertEqual([row["target"] for row in report["candidates"]],
                         ["0x00001000", "0x00001008", "0x00001010"])
        exact_end = index(elf([0xEAFFFFFF]))["candidates"][0]
        self.assertEqual(exact_end["target"], "0x00001004")
        self.assertEqual(exact_end["target_relation"], "outside")

    def test_literal_data_cannot_be_distinguished_from_instruction(self):
        # A literal pool containing this number must be reported as a candidate, not proven code.
        data = elf([0xEA000000])
        report = index(data)
        self.assertEqual(report["candidate_count"], 1)
        self.assertTrue(any("literal data" in caveat for caveat in report["limits"]))
        self.assertEqual(report["instruction_state_assumption"], "ARM")
        self.assertFalse(report["truncated"])
        self.assertEqual(report["input_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(report["range"]["sha256"], hashlib.sha256(data[256:]).hexdigest())

    def test_empty_candidate_set_and_et_dyn(self):
        report = index(elf([0xE1A00000, 0xE12FFF1E], kind=3))
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["range"]["elf_type"], 3)

    def test_alignment_mapping_and_size_bounds(self):
        data = elf([0xE1A00000] * 4)
        for start, end in ((0x1001, 0x1004), (0x1000, 0x1002), (0x1000, 0x1000),
                           (True, 0x1004), (-4, 4), (0x1000, 0x1014), (0, 2**32 + 4),
                           (0x1000, 0x11004)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                index(data, start, end)
        for malformed in (elf([0], kind=1), elf([0], flags=4), elf([0], extra_mapping=True),
                          data[:60], b"raw ARM bytes"):
            with self.assertRaises((ValueError, struct.error)):
                index(malformed, 0x1000, 0x1004)
        for position, value in ((5, 2), (18, 62)):
            altered = bytearray(data)
            altered[position] = value
            with self.assertRaises((ValueError, struct.error)):
                index(bytes(altered), 0x1000, 0x1004)
        with self.assertRaises(ValueError):
            branch.index_bytes(bytearray(data), 0x1000, 0x1004, arm_state=True)

    def test_full_range_output_cap_has_no_silent_truncation(self):
        report = index(elf([0xEAFFFFFE] * (65536 // 4)))
        self.assertEqual(report["candidate_count"], 16384)
        self.assertLess(len(branch.encode_report(report)), branch.MAX_OUTPUT)
        with patch.object(branch, "MAX_OUTPUT", 100), self.assertRaisesRegex(ValueError, "output exceeds"):
            branch.encode_report(report)

    def test_explicit_state_and_invalid_timeouts_before_read(self):
        with patch.object(reader, "_read_input", side_effect=AssertionError("input opened")):
            for state in (False, None, 1, "ARM"):
                with self.assertRaises(ValueError):
                    branch.index_file(Path("unused"), 0x1000, 0x1004, arm_state=state)
            for timeout in (0, -1, 31, float("nan"), float("inf"), True, "10"):
                with self.assertRaises(ValueError):
                    branch.index_file(Path("unused"), 0x1000, 0x1004, arm_state=True, timeout=timeout)

    def test_deadline_failure_during_scan_returns_no_partial_report(self):
        clock = iter([0, 0, 0, 0, 11])
        with patch.object(branch.time, "monotonic", side_effect=lambda: next(clock)):
            with self.assertRaisesRegex(ValueError, "deadline"):
                index(elf([0xEAFFFFFE] * 300))

    def test_file_io_reuses_nofollow_regular_file_and_change_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "input.elf"
            source.write_bytes(elf([0xEA000000]))
            report = branch.index_file(source, 0x1000, 0x1004, arm_state=True)
            self.assertEqual(report["candidate_count"], 1)
            link = root / "link"
            link.symlink_to(source)
            fifo = root / "fifo"
            os.mkfifo(fifo)
            for path in (link, fifo, root):
                with self.assertRaises((OSError, ValueError)):
                    branch.index_file(path, 0x1000, 0x1004, arm_state=True)
            with patch.object(reader, "_identity", side_effect=[(1,), (2,)]):
                with self.assertRaisesRegex(ValueError, "changed"):
                    branch.index_file(source, 0x1000, 0x1004, arm_state=True)

    def test_cli_json_and_error_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "input.elf"
            source.write_bytes(elf([0xEA000000]))
            args = [str(source), "--start", "0x1000", "--end", "0x1004", "--arm-state"]
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(branch.main(args), 0)
            self.assertEqual(json.loads(output.getvalue())["candidate_count"], 1)
            with redirect_stderr(io.StringIO()) as error, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(branch.main(args + ["--timeout", "0"]), 2)
            self.assertIn("error", json.loads(error.getvalue()))
            self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
