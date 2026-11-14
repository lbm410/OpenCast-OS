"""Synthetic ELF and fake host-tool tests; no vendor fixture or ARM execution."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import arm_disassembly as dis


def elf(*, machine=40, kind=2, flags=5, filesz=16, memsz=16, second=False, base=0x1000):
    data = bytearray(512)
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    data[:52] = struct.pack("<16sHHIIIIIHHHHHH", ident, kind, machine, 1, base,
                           52, 0, 0x5000000, 52, 32, 2 if second else 1, 0, 0, 0)
    struct.pack_into("<8I", data, 52, 1, 256, base, base, filesz, memsz, flags, 4)
    if second:
        struct.pack_into("<8I", data, 84, 1, 272, base + 4, base + 4, 8, 8, 4, 4)
    data[256:272] = bytes.fromhex("0000a0e11eff2fe10000a0e11eff2fe1")
    return bytes(data)


class DisassemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "target.elf"
        self.source.write_bytes(elf())
        self.tool = self.root / "llvm-objdump"
        self.host_tool()

    def host_tool(self, body=None, version="LLVM version synthetic-fixture"):
        if body is None:
            body = "print(sys.argv[-1] + ': file format elf32-littlearm')\nprint('1000: e1a00000 mov r0, r0')\n"
        source = "#!" + sys.executable + "\nimport sys,time,os\n"
        source += "if '--version' in sys.argv:\n    print(" + repr(version) + ")\n    sys.exit(0)\n"
        source += body
        self.tool.write_text(source)
        self.tool.chmod(0o700)

    def test_valid_snapshot_report_and_exact_hashes(self):
        original = self.source.read_bytes()
        report = dis.disassemble(self.source, self.tool, 0x1000, 0x1010)
        self.assertEqual(report["range"]["file_offset"], 256)
        self.assertEqual(report["range"]["bytes"], 16)
        self.assertEqual(report["range"]["sha256"], dis.hashlib.sha256(original[256:272]).hexdigest())
        self.assertEqual(report["input_sha256"], dis.hashlib.sha256(original).hexdigest())
        self.assertIn("<validated-input.elf>", report["disassembly"])
        self.assertNotIn(str(self.source), report["disassembly"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(report["options"][0], "-d")
        self.assertNotIn("-D", report["options"])

    def test_et_dyn_is_supported_without_runtime_address_claims(self):
        self.assertEqual(dis.validate_range(elf(kind=3), 0x1000, 0x1004)["elf_type"], 3)

    def test_completed_host_process_is_not_signalled(self):
        with patch.object(dis.os, "killpg", side_effect=AssertionError("completed group signalled")):
            dis.disassemble(self.source, self.tool, 0x1000, 0x1010)
        # A reaped nonzero exit likewise needs no process-group cleanup.
        self.host_tool("sys.exit(4)\n")
        with patch.object(dis.os, "killpg", side_effect=AssertionError("reaped group signalled")), \
                self.assertRaisesRegex(ValueError, "exit code 4"):
            dis.disassemble(self.source, self.tool, 0x1000, 0x1010)

    def test_architecture_type_and_endian_rejected(self):
        for data in (elf(machine=62), elf(kind=1), elf()[:5] + b"\x02" + elf()[6:], b"raw ARM bytes"):
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                dis.validate_range(data, 0x1000, 0x1010)

    def test_range_limits_and_alignment(self):
        for start, end in ((0x1000, 0x1000), (0x1004, 0x1000), (0x1001, 0x1004),
                           (0x1000, 0x1006), (-4, 4), (0x1000, 0x11004),
                           (0, 2**32 + 4), (True, 4), (0x1000, 0x1014)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                dis.validate_range(elf(), start, end)

    def test_permissions_bss_and_overlapping_loads_rejected(self):
        for data in (elf(flags=4), elf(filesz=4, memsz=16), elf(second=True)):
            with self.assertRaisesRegex(ValueError, "PT_LOAD"):
                dis.validate_range(data, 0x1000, 0x1010)
        with self.assertRaisesRegex(ValueError, "wraps"):
            dis.validate_range(elf(base=0xFFFFFFFC), 0xFFFFFFFC, 2**32)

    def test_truncated_program_headers_and_input_limit(self):
        with self.assertRaises((ValueError, struct.error)):
            dis.validate_range(elf()[:60], 0x1000, 0x1004)
        with patch.object(dis, "MAX_INPUT", 128), self.assertRaises(ValueError):
            dis.disassemble(self.source, self.tool, 0x1000, 0x1004)

    def test_input_symlink_parent_symlink_fifo_and_empty_file(self):
        link = self.root / "link"
        link.symlink_to(self.source)
        parent_link = self.root / "parent-link"
        parent_link.symlink_to(self.root, target_is_directory=True)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        empty = self.root / "empty"
        empty.touch()
        for path in (link, parent_link / self.source.name, fifo, empty):
            with self.subTest(path=path.name), self.assertRaises((OSError, ValueError)):
                dis.disassemble(path, self.tool, 0x1000, 0x1004)

    def test_host_requires_absolute_regular_executable_and_rejects_arm_target(self):
        with self.assertRaises(ValueError):
            dis.host_tool_provenance(Path("llvm-objdump"))
        self.tool.chmod(0o600)
        with self.assertRaises(ValueError):
            dis.host_tool_provenance(self.tool)
        self.source.chmod(0o700)
        with self.assertRaisesRegex(ValueError, "host architecture"):
            dis.host_tool_provenance(self.source)
        link = self.root / "tool-link"
        link.symlink_to(self.tool)
        with self.assertRaises(OSError):
            dis.host_tool_provenance(link)

    def test_host_must_identify_as_llvm(self):
        self.host_tool(version="Other disassembler")
        with self.assertRaisesRegex(ValueError, "identify as LLVM"):
            dis.disassemble(self.source, self.tool, 0x1000, 0x1010)

    def test_timeout_terminates_host_process(self):
        self.host_tool("time.sleep(5)\n")
        started = time.monotonic()
        with patch.object(dis.os, "killpg", wraps=os.killpg) as kill_group:
            with self.assertRaisesRegex(ValueError, "timeout"):
                dis.disassemble(self.source, self.tool, 0x1000, 0x1010, timeout=0.2)
            self.assertEqual(kill_group.call_count, 1)
        self.assertLess(time.monotonic() - started, 2)

    def test_stdout_stderr_and_version_output_caps(self):
        for body in ("os.write(1, b'x' * 8192)\n", "os.write(2, b'x' * 8192)\n"):
            self.host_tool(body)
            with patch.object(dis, "MAX_OUTPUT", 1024), self.assertRaisesRegex(ValueError, "byte limit"):
                dis.disassemble(self.source, self.tool, 0x1000, 0x1010)
        self.host_tool(version="LLVM" + "x" * 8192)
        with patch.object(dis, "MAX_VERSION_OUTPUT", 1024), self.assertRaisesRegex(ValueError, "byte limit"):
            dis.disassemble(self.source, self.tool, 0x1000, 0x1010)

    def test_diagnostics_nonzero_and_out_of_range_output_are_rejected(self):
        for body in ("sys.exit(4)\n", "print('warning', file=sys.stderr)\n",
                     "print('2000: e1a00000 mov r0,r0')\n", "print('No code')\n"):
            self.host_tool(body)
            with self.assertRaises(ValueError):
                dis.disassemble(self.source, self.tool, 0x1000, 0x1010)

    def test_invalid_timeouts_rejected_before_subprocess(self):
        for value in (0, -1, 31, float("nan"), float("inf"), True):
            with patch.object(dis.subprocess, "Popen", side_effect=AssertionError("process started")), \
                    self.assertRaises(ValueError):
                dis.disassemble(self.source, self.tool, 0x1000, 0x1004, value)

    def test_cli_json_success_and_validation_failure(self):
        argv = [str(self.source), "--objdump", str(self.tool), "--start", "0x1000", "--end", "0x1010"]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(dis.main(argv), 0)
        self.assertIn("disassembly", json.loads(output.getvalue()))
        with redirect_stderr(io.StringIO()) as output:
            self.assertEqual(dis.main(argv[:-1] + ["0x1001"]), 2)
        self.assertIn("error", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
