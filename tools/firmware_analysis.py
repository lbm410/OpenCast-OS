"""Bounded static firmware triage; never executes, decrypts, or installs content.

Inventories classic ZIP archives and copies only an explicitly requested member.
Never uses extractall or overwrites output; checks CRC after reading the complete member.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import zipfile
import zlib

MAX_FILE = 2 * 1024**3
MAX_MEMBER = 1024**3
MAX_MEMBERS = 256
MAX_DIRECTORY = 4 * 1024**2
CHUNK = 1024**2
HEADER_SIZE = 4096
EOCD = struct.Struct("<4s4H2LH")


def regular_file(path: Path, maximum: int = MAX_FILE) -> int:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Input must be a regular file, not a link or device")
    if info.st_size > maximum:
        raise ValueError("File exceeds the analysis size limit")
    return info.st_size


def sha256_file(path: Path) -> str:
    regular_file(path)
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(CHUNK), b""):
            total += len(data)
            if total > MAX_FILE:
                raise ValueError("File grew beyond the size limit")
            digest.update(data)
    return digest.hexdigest()


def zip_directory(path: Path) -> dict:
    """Bounds the directory BEFORE ZipFile loads it into memory."""
    size = regular_file(path)
    with path.open("rb") as stream:
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
    position = tail.rfind(b"PK\x05\x06")
    if position < 0 or len(tail) - position < EOCD.size:
        raise ValueError("ZIP has no valid classic EOCD")
    _, disk, cd_disk, count_disk, count, cd_size, cd_offset, comment = EOCD.unpack_from(tail, position)
    if position + EOCD.size + comment != len(tail):
        raise ValueError("ZIP has trailing data after EOCD or an inconsistent comment")
    if disk or cd_disk or count_disk != count:
        raise ValueError("Multidisk ZIP is not supported")
    if count == 65535 or cd_size == 0xffffffff or cd_offset == 0xffffffff:
        raise ValueError("ZIP64 is not supported by this triage tool")
    if count > MAX_MEMBERS or cd_size > MAX_DIRECTORY:
        raise ValueError("ZIP directory exceeds limits")
    eocd_offset = size - len(tail) + position
    if cd_offset + cd_size != eocd_offset:
        raise ValueError("Inconsistent ZIP offsets or unsupported structure")
    return {"entries": count, "directory_bytes": cd_size, "directory_offset": cd_offset}


def safe_member(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if (not name or "\\" in name or ":" in name or any(ord(c) < 32 for c in name)
            or name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError("Unsafe ZIP name or unsupported directory entry")
    if info.orig_filename != name:
        raise ValueError("Truncated ZIP name")
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFREG) or info.is_dir():
        raise ValueError("Only regular members are allowed, never links or devices")
    if info.flag_bits & 1:
        raise ValueError("Encrypted ZIP is not supported")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise ValueError("ZIP compression method is not supported")
    if not 0 <= info.file_size <= MAX_MEMBER or info.compress_size < 0:
        raise ValueError("ZIP member exceeds limits")
    if info.file_size > max(1, info.compress_size) * 1000:
        raise ValueError("Excessive compression ratio")
    return PurePosixPath(name).name


def members(archive: zipfile.ZipFile, expected_count: int) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    if len(entries) != expected_count:
        raise ValueError("Inconsistent member count")
    names: set[str] = set()
    for entry in entries:
        safe_member(entry)
        if entry.filename in names:
            raise ValueError("Duplicate ZIP name")
        names.add(entry.filename)
    return entries


def inspect_header(header: bytes) -> dict:
    """Indicators, not cryptographic detection or a compatibility claim."""
    sample = header[:HEADER_SIZE]
    counts = [sample.count(value) for value in range(256)]
    entropy = (-sum((count / len(sample)) * math.log2(count / len(sample))
                    for count in counts if count) if sample else 0.0)
    versions = [{"offset": match.start(), "offset_hex": hex(match.start()),
                 "text": match.group().decode("ascii")}
                for match in re.finditer(rb"(?<![0-9.])[0-9]{1,4}(?:\.[0-9]{1,4}){2,3}(?![0-9.])", sample)]
    return {"sample_bytes": len(sample), "prefix_16_hex": sample[:16].hex(),
            "sample_entropy_bits_per_byte": round(entropy, 5),
            "epk2_magic_at_0x8c": sample[0x8c:0x90] == b"EPK2",
            "version_like_strings": versions[:32],
            "interpretation": "Static indicators; entropy does not prove encryption, strings do not prove installed versions",
            "signature_verified": False}


def inspect_file(path: Path) -> dict:
    size = regular_file(path)
    report = {"path": str(path), "bytes": size, "sha256": sha256_file(path)}
    with path.open("rb") as stream:
        header = stream.read(HEADER_SIZE)
    report["header"] = inspect_header(header)
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):
        directory = zip_directory(path)
        report["format"] = "zip"
        report["zip_directory"] = directory
        inventory = []
        with zipfile.ZipFile(path) as archive:
            for entry in members(archive, directory["entries"]):
                with archive.open(entry) as stream:
                    member_header = stream.read(HEADER_SIZE)
                inventory.append({"name": entry.filename, "bytes": entry.file_size,
                                  "compressed_bytes": entry.compress_size,
                                  "method": entry.compress_type, "flags": entry.flag_bits,
                                  "crc32_declared": f"{entry.CRC:08x}",
                                  "crc32_verified": False, "header": inspect_header(member_header)})
        report["members"] = inventory
    else:
        report["format"] = "unclassified_binary"
    return report


def extract_member(path: Path, name: str, output_dir: Path) -> dict:
    directory = zip_directory(path)
    if output_dir.is_symlink():
        raise ValueError("Output directory must not be a symbolic link")
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        candidates = members(archive, directory["entries"])
        selected = [entry for entry in candidates if entry.filename == name]
        if len(selected) != 1:
            raise ValueError("Select exactly one member from the inventory")
        entry = selected[0]
        destination = output_dir / safe_member(entry)
        digest = hashlib.sha256()
        written = 0
        # x: fails if the destination exists (including symlinks). Never overwrites a sample.
        output = destination.open("xb")
        try:
            with output, archive.open(entry) as stream:
                while True:
                    data = stream.read(CHUNK)
                    if not data:
                        break
                    written += len(data)
                    if written > entry.file_size or written > MAX_MEMBER:
                        raise ValueError("Decompressed content exceeds limits")
                    output.write(data)
                    digest.update(data)
                if written != entry.file_size:
                    raise ValueError("Inconsistent member length")
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            # Only removes the new incomplete output created by this call.
            destination.unlink(missing_ok=True)
            raise
        destination.chmod(0o444)
    return {"archive": str(path), "member": name, "output": str(destination),
            "bytes": written, "sha256": digest.hexdigest(), "crc32_verified": True,
            "crc32": f"{entry.CRC:08x}", "signature_verified": False,
            "note": "Decompressed copy of one member; not executed, not decrypted, not installable by this tool"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("path", type=Path)
    extract = commands.add_parser("extract-member")
    extract.add_argument("path", type=Path)
    extract.add_argument("--member", required=True)
    extract.add_argument("--output-dir", type=Path, default=Path("firmware/working"))
    args = parser.parse_args()
    try:
        report = (inspect_file(args.path) if args.command == "inspect" else
                  extract_member(args.path, args.member, args.output_dir))
        report["status"] = "ok"
        code = 0
    except (OSError, ValueError, zipfile.BadZipFile, zlib.error, RuntimeError, EOFError) as error:
        report = {"status": "error", "error_type": type(error).__name__, "error": str(error)}
        code = 2
    report["observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
