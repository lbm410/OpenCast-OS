"""Read bounded ELF metadata without executing a target binary or invoking ldd."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys

MAX_FILE = 1024**3
MAX_PROGRAM_HEADERS = 1024
MAX_DYNAMIC_ENTRIES = 4096
MAX_STRING_TABLE = 8 * 1024**2
MACHINES = {3: "Intel 80386", 8: "MIPS", 40: "ARM", 62: "x86-64", 183: "AArch64"}


class ElfReader:
    def __init__(self, stream, size):
        self.stream, self.size = stream, size

    def read(self, offset, length):
        if offset < 0 or length < 0 or offset > self.size or length > self.size - offset:
            raise ValueError("ELF range exceeds input bounds")
        self.stream.seek(offset)
        data = self.stream.read(length)
        if len(data) != length:
            raise ValueError("ELF input changed or was truncated")
        return data

    def unpack(self, fmt, offset):
        return struct.unpack(fmt, self.read(offset, struct.calcsize(fmt)))


def cstring(data: bytes, offset: int) -> str:
    if not 0 <= offset < len(data):
        raise ValueError("ELF string offset is out of range")
    end = data.find(b"\0", offset, min(len(data), offset + 4096))
    if end < 0:
        raise ValueError("ELF string is unterminated or exceeds the size limit")
    return data[offset:end].decode("utf-8", "replace")


def inspect_stream(stream, size: int) -> dict:
    if not 16 <= size <= MAX_FILE:
        raise ValueError("ELF file size is outside the allowed range")
    reader = ElfReader(stream, size)
    ident = reader.read(0, 16)
    if ident[:4] != b"\x7fELF" or ident[6] != 1:
        raise ValueError("Not a supported ELF identification header")
    bits = {1: 32, 2: 64}.get(ident[4])
    endian = {1: "<", 2: ">"}.get(ident[5])
    if not bits or not endian:
        raise ValueError("Unsupported ELF class or byte order")
    header_fmt = endian + ("HHIIIIIHHHHHH" if bits == 32 else "HHIQQQIHHHHHH")
    header = reader.unpack(header_fmt, 16)
    file_type, machine, version, entry, phoff, _, flags, ehsize, phsize, phnum, _, _, _ = header
    expected_header = 52 if bits == 32 else 64
    expected_ph = 32 if bits == 32 else 56
    if version != 1 or ehsize != expected_header:
        raise ValueError("Invalid ELF header version or size")
    if phnum > MAX_PROGRAM_HEADERS or phnum == 65535:
        raise ValueError("Too many or extended ELF program headers")
    if phnum and (phsize != expected_ph or phoff < ehsize):
        raise ValueError("Invalid ELF program-header layout")
    segments = []
    for index in range(phnum):
        values = reader.unpack(endian + ("8I" if bits == 32 else "II6Q"), phoff + index * phsize)
        if bits == 32:
            kind, offset, address, _, filesz, memsz, permissions, alignment = values
        else:
            kind, permissions, offset, address, _, filesz, memsz, alignment = values
        if filesz and (offset > size or filesz > size - offset):
            raise ValueError("ELF segment exceeds file bounds")
        if kind == 1 and filesz > memsz:
            raise ValueError("ELF load segment is larger on disk than in memory")
        segments.append({"type": kind, "offset": offset, "address": address,
                         "file_size": filesz, "memory_size": memsz,
                         "flags": permissions, "alignment": alignment})
    interpreters = [s for s in segments if s["type"] == 3]
    if len(interpreters) > 1:
        raise ValueError("Multiple ELF interpreters")
    interpreter = None
    if interpreters:
        segment = interpreters[0]
        if not 1 <= segment["file_size"] <= 512:
            raise ValueError("Invalid ELF interpreter length")
        interpreter = cstring(reader.read(segment["offset"], segment["file_size"]), 0)
    dynamic_segments = [s for s in segments if s["type"] == 2]
    if len(dynamic_segments) > 1:
        raise ValueError("Multiple ELF dynamic segments")
    dynamic = []
    if dynamic_segments:
        segment = dynamic_segments[0]
        width = 8 if bits == 32 else 16
        count, remainder = divmod(segment["file_size"], width)
        if remainder or count > MAX_DYNAMIC_ENTRIES:
            raise ValueError("Invalid or oversized ELF dynamic table")
        terminated = False
        for index in range(count):
            tag, value = reader.unpack(endian + ("iI" if bits == 32 else "qQ"),
                                       segment["offset"] + width * index)
            if tag == 0:
                terminated = True
                break
            dynamic.append((tag, value))
        if not terminated:
            raise ValueError("Unterminated ELF dynamic table")
    strings = {}
    for tag in (5, 10):
        values = [value for candidate, value in dynamic if candidate == tag]
        if len(values) > 1:
            raise ValueError("Duplicate ELF string-table metadata")
        if values:
            strings[tag] = values[0]
    names = {"needed": [], "soname": [], "rpath": [], "runpath": []}
    name_bytes = 0
    string_tags = {1: "needed", 14: "soname", 15: "rpath", 29: "runpath"}
    if any(tag in string_tags for tag, _ in dynamic):
        if set(strings) != {5, 10} or not 1 <= strings[10] <= MAX_STRING_TABLE:
            raise ValueError("Missing or oversized ELF dynamic string table")
        address, length = strings[5], strings[10]
        mappings = [s for s in segments if s["type"] == 1 and s["address"] <= address
                    and address - s["address"] < s["file_size"]
                    and length <= s["file_size"] - (address - s["address"])]
        if len(mappings) != 1:
            raise ValueError("Ambiguous or missing ELF virtual-address mapping")
        segment = mappings[0]
        table = reader.read(segment["offset"] + address - segment["address"], length)
        for tag, value in dynamic:
            if tag in string_tags:
                name = cstring(table, value)
                name_bytes += len(name.encode("utf-8"))
                if name_bytes > 256 * 1024:
                    raise ValueError("Expanded ELF names exceed metadata budget")
                names[string_tags[tag]].append(name)
    report = {"bits": bits, "byte_order": "little" if endian == "<" else "big",
              "machine_id": machine, "machine": MACHINES.get(machine, "unknown"),
              "osabi": ident[7], "abi_version": ident[8], "elf_type": file_type,
              "entry_hex": hex(entry), "flags_hex": hex(flags),
              "interpreter": interpreter, "program_headers": len(segments), **names}
    if machine == 40:
        report["arm_eabi_version"] = (flags >> 24) & 255
        report["arm_float_abi_flags"] = ("conflicting" if flags & 0x600 == 0x600 else
                                          "hard" if flags & 0x400 else
                                          "soft" if flags & 0x200 else "unspecified")
    return report


def _open_regular(path: Path):
    """Transfer descriptor ownership only after fdopen succeeds."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("Only regular files are supported")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def inspect_file(path: Path) -> dict:
    with _open_regular(path) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Only regular files are supported")
        report = inspect_stream(stream, before.st_size)
        stream.seek(0)
        digest = hashlib.sha256()
        consumed = 0
        while True:
            chunk = stream.read(1024**2)
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_FILE:
                raise ValueError("ELF grew beyond the size limit")
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if consumed != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise ValueError("ELF changed during inspection")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest(), **report}


def scan_tree(root: Path, limit: int = 10000, byte_limit: int = 2 * 1024**3) -> dict:
    if root.is_symlink() or not root.is_dir() or not 1 <= limit <= 50000:
        raise ValueError("Provide a real directory and a limit between 1 and 50000")
    if not 1 <= byte_limit <= 8 * 1024**3:
        raise ValueError("Invalid cumulative byte limit")
    files, errors, visited, accounted, metadata_bytes = [], [], 0, 0, 0
    pending = [root]

    def summary(status, complete):
        return {"status": status, "files": files, "errors": errors,
                "visited": visited, "accounted_bytes": accounted, "complete": complete}

    while pending:
        directory = pending.pop()
        if directory.is_symlink():
            continue
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if visited >= limit:
                        return summary("limit_reached", False)
                    visited += 1
                    path = Path(entry.path)
                    try:
                        mode = entry.stat(follow_symlinks=False).st_mode
                        if stat.S_ISDIR(mode):
                            pending.append(path)
                            continue
                        if not stat.S_ISREG(mode):
                            continue
                        with _open_regular(path) as stream:
                            metadata = os.fstat(stream.fileno())
                            if not stat.S_ISREG(metadata.st_mode):
                                raise ValueError("File changed type during inspection")
                            if metadata.st_size > byte_limit - accounted:
                                return summary("byte_limit_reached", False)
                            accounted += metadata.st_size
                            magic = stream.read(4)
                        if magic == b"\x7fELF":
                            result = inspect_file(path)
                            result["path"] = str(path.relative_to(root))
                            metadata_bytes += len(json.dumps(result).encode("utf-8"))
                            if metadata_bytes > 16 * 1024**2:
                                return summary("metadata_limit_reached", False)
                            files.append(result)
                    except (OSError, ValueError) as error:
                        errors.append({"path": str(path.relative_to(root)), "error": str(error)})
        except OSError as error:
            errors.append({"path": str(directory.relative_to(root)), "error": str(error)})
    return summary("partial" if errors else "ok", not errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--tree", action="store_true")
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()
    try:
        report = scan_tree(args.path, args.limit) if args.tree else inspect_file(args.path)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("complete", True) else 2
    except (OSError, ValueError, struct.error) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
