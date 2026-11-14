"""Decode bounded LG LZ4P data and inspect headers without executing target code."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import zlib

from tools import elf_inventory

MAX_INPUT = 64 * 1024**2
MAX_OUTPUT = 64 * 1024**2
MAX_BLOCK = 1024**2
MAX_BLOCKS = 4096
MAX_TRAILER = 1024**2


def decode_block(data: bytes, expected: int) -> bytes:
    """Decode one independent LZ4 block with an exact output bound."""
    if not 1 <= expected <= MAX_BLOCK or not data:
        raise ValueError("Invalid LZ4 block size")
    if len(data) > expected + expected // 255 + 16:
        raise ValueError("Compressed block exceeds LZ4 size bound")
    output = bytearray()
    position = 0

    def length(base: int) -> int:
        nonlocal position
        value = base
        if base == 15:
            while True:
                if position >= len(data):
                    raise ValueError("Truncated LZ4 length extension")
                extension = data[position]
                position += 1
                value += extension
                if value > expected:
                    raise ValueError("LZ4 length exceeds output bound")
                if extension != 255:
                    break
        return value

    while position < len(data):
        token = data[position]
        position += 1
        literals = length(token >> 4)
        if literals > len(data) - position or literals > expected - len(output):
            raise ValueError("LZ4 literal range exceeds input or output")
        output.extend(data[position:position + literals])
        position += literals
        if position == len(data):
            if len(output) != expected:
                raise ValueError("LZ4 output length does not match declaration")
            return bytes(output)
        if position + 2 > len(data):
            raise ValueError("Truncated LZ4 match offset")
        distance = int.from_bytes(data[position:position + 2], "little")
        position += 2
        if not 1 <= distance <= len(output):
            raise ValueError("LZ4 match points outside decoded block")
        match = length(token & 15) + 4
        if match > expected - len(output):
            raise ValueError("LZ4 match exceeds output bound")
        # Overlapping matches repeat the preceding distance-byte pattern.
        pattern = output[-distance:]
        count, remainder = divmod(match, distance)
        output.extend(pattern * count)
        output.extend(pattern[:remainder])
    # The reviewed legacy LG decoder also permits a match to finish the output
    # block. Accept it only when both input and exact output are exhausted.
    if len(output) == expected:
        return bytes(output)
    raise ValueError("LZ4 output length does not match declaration")


def decode_container(data: bytes) -> tuple[bytes, dict]:
    if not 32 <= len(data) <= MAX_INPUT:
        raise ValueError("LZ4P input size is outside limits")
    magic, output_size, container_size, block_size, count, *reserved = struct.unpack_from("<8I", data)
    if magic != 0x50345A4C or any(reserved):
        raise ValueError("Unsupported LZ4P header")
    if not 1 <= output_size <= MAX_OUTPUT or not 1 <= block_size <= MAX_BLOCK:
        raise ValueError("LZ4P output or block size exceeds limits")
    if not 1 <= count <= MAX_BLOCKS or count != (output_size + block_size - 1) // block_size:
        raise ValueError("Inconsistent LZ4P block count")
    start = 32 + count * 4
    if not start < container_size <= len(data) or len(data) - container_size > MAX_TRAILER:
        raise ValueError("Invalid LZ4P container or trailer bounds")
    sizes = struct.unpack_from("<" + "I" * count, data, 32)
    if sum(sizes) != container_size - start:
        raise ValueError("LZ4P chunk table does not reach declared end")
    for index, size in enumerate(sizes):
        expected = min(block_size, output_size - index * block_size)
        if not 1 <= size <= expected + expected // 255 + 16:
            raise ValueError("Invalid compressed chunk size")
    output = bytearray()
    position = start
    for index, size in enumerate(sizes):
        expected = min(block_size, output_size - index * block_size)
        output.extend(decode_block(data[position:position + size], expected))
        position += size
    trailer = data[container_size:]
    return bytes(output), {"format": "LG LZ4P", "block_size": block_size,
                           "blocks": count, "container_bytes": container_size,
                           "output_bytes": output_size, "trailer_bytes": len(trailer),
                           "trailer_sha256": hashlib.sha256(trailer).hexdigest()}


def inspect_uimage(data: bytes) -> dict:
    if len(data) < 64 or data[:4] != b"\x27\x05\x19\x56":
        raise ValueError("Not a complete legacy uImage header")
    fields = struct.unpack_from(">7I4B32s", data)
    _, header_crc, timestamp, size, load, entry, data_crc, os_id, arch, kind, compression, name = fields
    header = bytearray(data[:64])
    header[4:8] = bytes(4)
    if zlib.crc32(header) != header_crc:
        raise ValueError("uImage header CRC mismatch")
    if size != len(data) - 64:
        raise ValueError("uImage payload size mismatch")
    if zlib.crc32(data[64:]) != data_crc:
        raise ValueError("uImage payload CRC mismatch")
    return {"format": "legacy uImage", "header_crc_verified": True,
            "data_crc_verified": True, "timestamp": timestamp, "payload_bytes": size,
            "load_hex": hex(load), "entry_hex": hex(entry), "os_id": os_id,
            "architecture_id": arch, "type_id": kind, "compression_id": compression,
            "name": name.split(b"\0", 1)[0].decode("ascii", "replace")}


def inspect_decoded(data: bytes) -> dict:
    report: dict = {}
    if data.startswith(b"\x27\x05\x19\x56"):
        report["uimage"] = inspect_uimage(data)
    if data.startswith(b"\x45\x3d\xcd\x28"):
        report["cramfs"] = inspect_cramfs_release(data)
    # Inspect only early candidate boundaries, never arbitrary full-file carving.
    candidates = []
    position = 0
    while len(candidates) < 16:
        position = data.find(b"\x7fELF", position, min(len(data), 4096))
        if position < 0:
            break
        candidate = {"offset": position}
        try:
            candidate["elf"] = elf_inventory.inspect_stream(io.BytesIO(data[position:]), len(data) - position)
        except (ValueError, struct.error) as error:
            candidate["error"] = str(error)
        candidates.append(candidate)
        position += 4
    report["early_elf_candidates"] = candidates
    return report


def inspect_cramfs_release(data: bytes) -> dict:
    """Validate the observed LG CramFS variant and inspect only its XIP RELEASE.

    No recursive extraction, credential files, symlinks or compressed files are
    opened. LG encodes size bits above 24 in the file GID relative to root GID.
    """
    if len(data) < 76 or len(data) > MAX_OUTPUT:
        raise ValueError("Invalid CramFS image size")
    magic, size, flags, future = struct.unpack_from("<4I", data)
    if (magic != 0x28cd3d45 or size != len(data) or flags != 3 or future
            or data[16:32] != b"Compressed ROMFS"):
        raise ValueError("Unsupported CramFS header variant")
    checksum = struct.unpack_from("<I", data, 32)[0]
    crc = zlib.crc32(data[:32])
    crc = zlib.crc32(bytes(4), crc)
    crc = zlib.crc32(data[36:], crc)
    if crc != checksum:
        raise ValueError("CramFS image CRC mismatch")
    mode, size_gid, name_offset = struct.unpack_from("<3I", data, 64)
    if not stat.S_ISDIR(mode & 0xffff):
        raise ValueError("CramFS root is not a directory")
    root_gid = size_gid >> 24
    directory_size = size_gid & 0xffffff
    position = (name_offset >> 6) * 4
    end = position + directory_size
    if position < 76 or end > size or directory_size > 65536:
        raise ValueError("CramFS root directory exceeds bounds")
    selected = None
    entries = 0
    while position < end:
        entries += 1
        if entries > 64 or position + 12 > end:
            raise ValueError("Invalid CramFS root directory")
        mode, size_gid, name_offset = struct.unpack_from("<3I", data, position)
        length = (name_offset & 63) * 4
        if not length or position + 12 + length > end:
            raise ValueError("Invalid CramFS entry name bounds")
        name = data[position + 12:position + 12 + length].rstrip(b"\0")
        if b"\0" in name or b"/" in name or name in (b".", b".."):
            raise ValueError("Invalid CramFS root entry name")
        if name == b"RELEASE":
            if selected is not None or not stat.S_ISREG(mode & 0xffff) or not mode & stat.S_ISVTX:
                raise ValueError("RELEASE must be one regular XIP file")
            gid = size_gid >> 24
            if gid < root_gid:
                raise ValueError("Unsupported LG file size encoding")
            file_size = (size_gid & 0xffffff) + (gid - root_gid) * 0x1000000
            offset = (name_offset >> 6) * 4
            offset = (offset + 4095) & ~4095
            if not file_size or offset < end or file_size > size - offset:
                raise ValueError("RELEASE extent exceeds CramFS bounds")
            content = data[offset:offset + file_size]
            selected = {"name": "RELEASE", "offset": offset, "bytes": file_size,
                        "mode_octal": oct(mode & 0xffff),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "elf": elf_inventory.inspect_stream(io.BytesIO(content), len(content))}
        position += 12 + length
    return {"format": "LG CramFS with XIP support", "crc_verified": True,
            "bytes": size, "flags": flags, "root_entries": entries, "release": selected}


def decode_file(source: Path, destination: Path) -> dict:
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        stream = os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise
    with stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 32 <= before.st_size <= MAX_INPUT:
            raise ValueError("Input must be a bounded regular file")
        data = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
        if len(data) != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise ValueError("Input changed during inspection")
    decoded, report = decode_container(data)
    report.update(inspect_decoded(decoded))
    # Open the containing directory without following its final symlink, then use
    # an exclusive relative creation. Existing files and symlinks are never replaced.
    parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent_fd)
        try:
            stream = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            stream.write(decoded)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
    finally:
        os.close(parent_fd)
    return {"source": str(source), "output": str(destination),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "output_sha256": hashlib.sha256(decoded).hexdigest(), **report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="New file in an existing output directory")
    args = parser.parse_args()
    try:
        print(json.dumps(decode_file(args.source, args.destination), indent=2))
        return 0
    except (OSError, ValueError, struct.error) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
