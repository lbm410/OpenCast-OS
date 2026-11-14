"""Bounded static decoding of the reviewed LG boot-package LZHS profile.

Format reference: epk2extract a0ccd8a4b4f48d05675a4cddd233f8780ee36767,
src/lzhs/lzhs.c and lzhs_lib.c. The pinned code tables are read as data;
neither the upstream implementation nor decoded target bytes are executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys

MAX_INPUT = 16 * 1024**2
MAX_COMPRESSED = 4 * 1024**2
MAX_OUTPUT = 16 * 1024**2
MAX_TABLE_FILE = 64 * 1024
TABLE_SHA256 = "fef168a1b235a43f5886151d4b89b86d9b885308692340ee83b5356088eb8b17"
DEFAULT_TABLES = "artifacts/vendor/epk2extract/include/lzhs/tables.h"


class BitReader:
    """MSB-first bits without expanding the input into a bit string."""

    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def read(self, count: int) -> int:
        if not 0 <= count <= 16 or self.position + count > len(self.data) * 8:
            raise ValueError("Truncated or invalid LZHS bit field")
        value = 0
        for _ in range(count):
            value = (value << 1) | ((self.data[self.position // 8] >>
                                       (7 - self.position % 8)) & 1)
            self.position += 1
        return value


class CodeTable:
    """A bounded, prefix-free Huffman table; entries are (code, bit count)."""

    def __init__(self, entries: list[tuple[int, int]], max_bits: int):
        if not 1 <= len(entries) <= 288 or not 1 <= max_bits <= 13:
            raise ValueError("Invalid Huffman table bounds")
        self.codes: dict[tuple[int, int], int] = {}
        self.max_bits = max_bits
        for symbol, (code, bits) in enumerate(entries):
            if not 1 <= bits <= max_bits or not 0 <= code < (1 << bits):
                raise ValueError("Invalid Huffman code")
            key = (bits, code)
            if key in self.codes:
                raise ValueError("Duplicate Huffman code")
            self.codes[key] = symbol
        for bits, code in self.codes:
            for shorter in range(1, bits):
                if (shorter, code >> (bits - shorter)) in self.codes:
                    raise ValueError("Ambiguous Huffman prefix")

    def decode(self, reader: BitReader) -> int:
        code = 0
        for bits in range(1, self.max_bits + 1):
            code = (code << 1) | reader.read(1)
            symbol = self.codes.get((bits, code))
            if symbol is not None:
                return symbol
        raise ValueError("Unknown Huffman code")


def parse_tables(data: bytes) -> tuple[CodeTable, CodeTable]:
    """Accept only the reviewed source snapshot; do not evaluate C source."""
    if len(data) > MAX_TABLE_FILE or hashlib.sha256(data).hexdigest() != TABLE_SHA256:
        raise ValueError("Code-table source does not match the reviewed SHA-256")
    source = data.decode("ascii")
    tables = []
    for name, byte_count, max_bits in (("charlen_table", 2304, 13), ("pos_table", 256, 6)):
        matches = list(re.finditer(r"\b" + name + r"\[" + str(byte_count) +
                                  r"\]\s*=\s*\{([^}]+)\};", source))
        if len(matches) != 1:
            raise ValueError("Missing or repeated code-table declaration")
        body = re.sub(r"//[^\n]*", "", matches[0].group(1))
        tokens = re.findall(r"0x[0-9a-fA-F]{2}\b", body)
        if len(tokens) != byte_count or re.sub(r"0x[0-9a-fA-F]{2}\b|[\s,]", "", body):
            raise ValueError("Unsupported code-table initializer")
        raw = bytes(int(token, 16) for token in tokens)
        tables.append(CodeTable(list(struct.iter_unpack("<II", raw)), max_bits))
    return tables[0], tables[1]


def thumb_decode(data: bytearray) -> int:
    """Reverse the reviewed Thumb BL transform in place, with 32-bit wrap."""
    position = 0
    converted = 0
    while position + 4 <= len(data):
        if data[position + 1] & 0xF8 == 0xF0 and data[position + 3] & 0xF8 == 0xF8:
            encoded = (((data[position + 1] & 7) << 19) | (data[position] << 11) |
                       ((data[position + 3] & 7) << 8) | data[position + 2]) << 1
            relative = ((encoded - (position + 4)) & 0xFFFFFFFF) >> 1
            data[position:position + 4] = bytes(((relative >> 11) & 255,
                                                0xF0 | ((relative >> 19) & 7),
                                                relative & 255,
                                                0xF8 | ((relative >> 8) & 7)))
            converted += 1
            position += 2
        position += 2
    return converted


def decode_container(data: bytes, offset: int, tables: tuple[CodeTable, CodeTable]) -> tuple[bytes, dict]:
    """Decode exactly one explicit header; trailing package data is not scanned."""
    if not 16 <= len(data) <= MAX_INPUT or not 0 <= offset <= len(data) - 16:
        raise ValueError("Input or header offset is outside limits")
    expected, compressed, checksum, spare = struct.unpack_from("<IIH6s", data, offset)
    if checksum > 255 or any(spare):
        raise ValueError("Unsupported boot LZHS checksum or reserved fields")
    if not 1 <= expected <= MAX_OUTPUT or not 1 <= compressed <= MAX_COMPRESSED:
        raise ValueError("LZHS size exceeds configured limits")
    start = offset + 16
    end = start + compressed
    if end > len(data):
        raise ValueError("Truncated LZHS compressed payload")
    charlen, positions = tables
    if len(charlen.codes) != 288 or len(positions.codes) != 32:
        raise ValueError("Unsupported LZHS code-table dimensions")
    reader = BitReader(data[start:end])
    ring = bytearray(4096)
    output = bytearray()
    ring_position = 0
    literals = matches = 0
    while len(output) < expected:
        symbol = charlen.decode(reader)
        if symbol < 256:
            output.append(symbol)
            ring[ring_position] = symbol
            ring_position = (ring_position + 1) & 4095
            literals += 1
        else:
            count = symbol - 256 + 3
            if count > expected - len(output):
                raise ValueError("LZHS match exceeds declared output")
            distance = (positions.decode(reader) << 7) | reader.read(7)
            # The format starts with a zero-filled ring and permits distance 0.
            for _ in range(count):
                value = ring[(ring_position - distance) & 4095]
                output.append(value)
                ring[ring_position] = value
                ring_position = (ring_position + 1) & 4095
            matches += 1
    consumed = reader.position
    padding = compressed * 8 - consumed
    # The reviewed encoder unconditionally emits a final byte, including when
    # aligned. Accept at most one byte of zero padding, never extra tokens.
    if not 0 <= padding <= 8 or reader.read(padding) != 0:
        raise ValueError("Unexpected nonzero or excessive LZHS padding")
    converted = thumb_decode(output)
    actual_checksum = sum(output) & 255
    if actual_checksum != checksum:
        raise ValueError("LZHS decoded checksum mismatch")
    result = bytes(output)
    report = {
        "format": "LG boot LZHS (reviewed profile)", "header_offset": offset,
        "payload_offset": start, "payload_end_exclusive": end,
        "input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(),
        "compressed_bytes": compressed, "compressed_sha256": hashlib.sha256(data[start:end]).hexdigest(),
        "decoded_bytes": len(result), "decoded_sha256": hashlib.sha256(result).hexdigest(),
        "checksum_expected": checksum, "checksum_actual": actual_checksum,
        "checksum_valid": True, "checksum_kind": "8-bit additive; not authentication",
        "huffman_bits_consumed": consumed, "zero_padding_bits": padding,
        "literal_tokens": literals, "match_tokens": matches, "thumb_bl_conversions": converted,
    }
    return result, report


def _parent_fd(path: Path) -> tuple[int, str]:
    """Open existing directories without following symlinks, component by component."""
    parts = path.absolute().parts
    if ".." in parts:
        raise ValueError("Parent traversal is not supported")
    descriptor = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def read_bounded(path: Path, limit: int) -> bytes:
    parent, name = _parent_fd(path)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        source = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= limit:
            raise ValueError("Input must be a bounded regular file")
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
        if len(data) != before.st_size or len(data) > limit or (
                before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Input changed during reading or exceeded its bound")
    return data


def write_exclusive(path: Path, data: bytes) -> None:
    """Create a new non-executable, read-only artifact; never replace a file."""
    parent, name = _parent_fd(path)
    try:
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        try:
            destination = os.fdopen(descriptor, "wb")
        except BaseException:
            os.close(descriptor)
            raise
        with destination:
            destination.write(data)
            destination.flush()
            os.fchmod(destination.fileno(), 0o444)
    finally:
        os.close(parent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Existing boot package; never executed")
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True,
                        help="Explicit LZHS header offset, decimal or 0x-prefixed")
    parser.add_argument("--tables", type=Path, default=Path(DEFAULT_TABLES),
                        help="Pinned epk2extract tables.h source, read only as data")
    parser.add_argument("--output", type=Path, help="Optional NEW decoded artifact in an existing directory")
    args = parser.parse_args(argv)
    try:
        tables = parse_tables(read_bounded(args.tables, MAX_TABLE_FILE))
        output, report = decode_container(read_bounded(args.input, MAX_INPUT), args.offset, tables)
        report["table_source_sha256"] = TABLE_SHA256
        if args.output is not None:
            write_exclusive(args.output, output)
            report["output"] = str(args.output)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
