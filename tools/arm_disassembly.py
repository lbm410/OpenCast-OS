"""Inspect one bounded ARM ELF address range with an explicitly trusted host LLVM tool.

This wrapper never loads, links, emulates or executes the input. It does not infer
function boundaries, runtime addresses, CPU identity or PLT symbol contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time

from tools import elf_inventory

MAX_INPUT = 64 * 1024**2
MAX_TOOL = 128 * 1024**2
MAX_RANGE = 64 * 1024
MAX_OUTPUT = 4 * 1024**2
MAX_VERSION_OUTPUT = 16 * 1024


def _open_regular(path: Path, limit: int):
    """Open an existing file through nonsymlink directory components."""
    parts = path.absolute().parts
    if ".." in parts:
        raise ValueError("Parent traversal is not supported")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(parts[0], directory_flags)
    try:
        for component in parts[1:-1]:
            child = os.open(component, directory_flags, dir_fd=parent)
            os.close(parent)
            parent = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= limit:
            raise ValueError("File must be regular, nonempty and within the size limit")
        return stream, info
    except BaseException:
        stream.close()
        raise


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_input(path: Path) -> bytes:
    stream, before = _open_regular(path, MAX_INPUT)
    with stream:
        data = stream.read(MAX_INPUT + 1)
        if len(data) != before.st_size or _identity(before) != _identity(os.fstat(stream.fileno())):
            raise ValueError("Input changed while reading")
    return data


def validate_range(data: bytes, start: int, end: int) -> dict:
    """Require a unique, file-backed executable PT_LOAD mapping for the range."""
    if not 52 <= len(data) <= MAX_INPUT:
        raise ValueError("ELF input size is outside limits")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end)):
        raise ValueError("Addresses must be integers")
    if not 0 <= start < end <= 2**32 or start % 4 or end % 4:
        raise ValueError("Addresses must define a nonempty, four-byte-aligned 32-bit range")
    if end - start > MAX_RANGE:
        raise ValueError("Requested range exceeds 64 KiB")
    metadata = elf_inventory.inspect_stream(io.BytesIO(data), len(data))
    if (metadata["bits"], metadata["byte_order"], metadata["machine_id"]) != (32, "little", 40):
        raise ValueError("Only ELF32 little-endian ARM inputs are supported")
    if metadata["elf_type"] not in (2, 3):
        raise ValueError("Only ET_EXEC or ET_DYN inputs have supported linked-address ranges")
    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    phoff, phsize, phnum = header[4], header[8], header[9]
    mappings = []
    overlaps = []
    for index in range(phnum):
        kind, offset, address, _, filesz, memsz, flags, _ = struct.unpack_from("<8I", data, phoff + index * phsize)
        if kind != 1:
            continue
        if address + memsz > 2**32:
            raise ValueError("PT_LOAD address range wraps the 32-bit address space")
        if start < address + memsz and address < end:
            overlaps.append(index)
        if flags & 1 and address <= start and end <= address + filesz:
            mappings.append((index, offset + start - address))
    if len(mappings) != 1 or overlaps != [mappings[0][0]]:
        raise ValueError("Range requires one unambiguous, file-backed executable PT_LOAD")
    index, offset = mappings[0]
    selected = data[offset:offset + end - start]
    return {"elf_type": metadata["elf_type"], "flags": metadata["flags_hex"],
            "start": start, "end_exclusive": end, "bytes": len(selected),
            "file_offset": offset, "program_header_index": index,
            "sha256": hashlib.sha256(selected).hexdigest()}


def host_tool_provenance(path: Path) -> dict:
    """Record an explicit trusted host executable; reject obvious target binaries."""
    if not path.is_absolute():
        raise ValueError("Provide an absolute path to the trusted host llvm-objdump executable")
    stream, before = _open_regular(path, MAX_TOOL)
    with stream:
        if not before.st_mode & 0o111:
            raise ValueError("Host tool lacks executable permission")
        prefix = stream.read(64)
        if prefix[:4] == b"\x7fELF":
            host_machine = {"x86_64": 62, "amd64": 62, "aarch64": 183, "arm64": 183}.get(platform.machine().lower())
            endian = "<" if prefix[5:6] == b"\x01" else ">"
            machine = struct.unpack_from(endian + "H", prefix, 18)[0] if len(prefix) >= 20 else None
            if sys.platform != "linux" or host_machine is None or machine != host_machine:
                raise ValueError("ELF tool does not match the supported host architecture")
        elif not (prefix.startswith(b"#!") or prefix[:4] in (
                b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe",
                b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf")):
            raise ValueError("Host tool is not a recognized native executable or trusted script")
        digest = hashlib.sha256(prefix)
        consumed = len(prefix)
        while chunk := stream.read(1024**2):
            consumed += len(chunk)
            if consumed > MAX_TOOL:
                raise ValueError("Host tool grew beyond the size limit")
            digest.update(chunk)
        if consumed != before.st_size or _identity(before) != _identity(os.fstat(stream.fileno())):
            raise ValueError("Host tool changed during inspection")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def _run_limited(argv: list[str], timeout: float, cap: int) -> bytes:
    """Drain both pipes under one deadline and byte cap; terminate on failure."""
    if timeout <= 0:
        raise ValueError("Host disassembler timeout")
    deadline = time.monotonic() + timeout
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "TZ": "UTC", "DEBUGINFOD_URLS": ""}
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment, start_new_session=True,
                               shell=False)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    needs_cleanup = True
    try:
        with selectors.DefaultSelector() as selector:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("Host disassembler timeout")
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fd, min(65536, cap - total + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(chunk)
                    if total > cap:
                        raise ValueError("Host disassembler output exceeds the byte limit")
                    output[key.data].extend(chunk)
        try:
            code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise ValueError("Host disassembler timeout") from None
        # Both pipes reached EOF and wait() reaped the leader. Never signal its
        # former group ID afterward: the OS may already have recycled it.
        needs_cleanup = False
        if code != 0:
            raise ValueError(f"Host disassembler failed with exit code {code}")
        if output["stderr"]:
            raise ValueError("Host disassembler emitted diagnostics; output is not accepted")
        return bytes(output["stdout"])
    finally:
        if needs_cleanup:
            # The leader has not been reaped here; this also stops descendants
            # retaining pipes after the leader exits. A trusted tool that exits
            # successfully after detaching children is outside this guarantee.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.stdout.close()
        process.stderr.close()


def disassemble(path: Path, objdump: Path, start: int, end: int, timeout: float = 10) -> dict:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("Timeout must be finite, greater than zero and at most 30 seconds")
    data = _read_input(path)
    selected = validate_range(data, start, end)
    tool = host_tool_provenance(objdump)
    if tool["sha256"] == hashlib.sha256(data).hexdigest():
        raise ValueError("The selected input must never be used as the host tool")
    deadline = time.monotonic() + timeout
    version = _run_limited([str(objdump), "--version"], deadline - time.monotonic(), MAX_VERSION_OUTPUT)
    if b"LLVM" not in version:
        raise ValueError("The explicit host tool did not identify as LLVM")
    with tempfile.TemporaryDirectory(prefix="opencast-static-disassembly-") as directory:
        snapshot = Path(directory) / "selected-input.elf"
        with snapshot.open("xb") as stream:
            stream.write(data)
        snapshot.chmod(0o400)
        options = ["-d", "--arch-name=arm", "--mattr=+v7", "--disassemble-zeroes",
                   "--start-address=" + hex(start), "--stop-address=" + hex(end)]
        # Apple's LLVM objdump rejects "--". The snapshot is our own absolute
        # path, so an untrusted input filename cannot become an option.
        output = _run_limited([str(objdump), *options, str(snapshot)],
                              deadline - time.monotonic(), MAX_OUTPUT)
    text = output.decode("utf-8", "replace")
    addresses = [int(match.group(1), 16) for match in re.finditer(r"^\s*([0-9a-fA-F]+):\s", text, re.MULTILINE)]
    if not addresses or any(not start <= address < end for address in addresses):
        raise ValueError("No addressed output in range, or disassembler printed outside the requested range")
    # Stable display text omits the random snapshot location; raw hash remains available.
    display = text.replace(str(snapshot), "<validated-input.elf>")
    return {"input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(),
            "range": selected, "host_tool": {**tool, "version": version.decode("utf-8", "replace").strip()},
            "options": options, "stdout_bytes": len(output), "stdout_sha256": hashlib.sha256(output).hexdigest(),
            "display_utf8_bytes": len(display.encode("utf-8")),
            "display_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
            "disassembly": display,
            "scope": "Static linked addresses only; no target execution, function inference or PLT annotations"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--objdump", required=True, type=Path, help="Absolute path to a trusted host LLVM objdump")
    parser.add_argument("--start", required=True, type=lambda value: int(value, 0), help="Linked start address")
    parser.add_argument("--end", required=True, type=lambda value: int(value, 0), help="Exclusive linked end address")
    parser.add_argument("--timeout", type=float, default=10, help="Shared subprocess deadline, up to 30 seconds")
    args = parser.parse_args(argv)
    try:
        report = disassemble(args.input, args.objdump, args.start, args.end, args.timeout)
    except (OSError, ValueError, struct.error) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
