"""Inspect a local NetCast portal ZIP without extracting or executing its contents."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import unicodedata
import zipfile
import zlib

MAX_ZIP = 10 * 1024 * 1024
MAX_ENTRIES = 100
MAX_EXPANDED = 20 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_RATIO = 200
MAX_CENTRAL = 128 * 1024
SOURCE_ASSETS = frozenset(("index.html", "style.css", "navigation.js", "capabilities.js",
                           "shell.js", "assets/landscape-v2.jpg"))


class PackageError(ValueError):
    """A fixed diagnostic deliberately excludes private paths and file contents."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise PackageError(code, message)


def _read_local(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            stream = os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_ZIP:
                fail("zip_file_bounds", "Input must be a regular ZIP file of at most 10 MiB.")
            data = stream.read(MAX_ZIP + 1)
            after = os.fstat(stream.fileno())
            if len(data) != before.st_size or len(data) > MAX_ZIP or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                fail("input_changed", "Input changed during the bounded read.")
            return data
    except OSError:
        fail("input_unreadable", "Unable to read the local input as a regular non-symlink file.")


def _preflight(data: bytes) -> int:
    # Bound central-directory allocation before ZipFile constructs ZipInfo objects.
    offset = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
    if offset < 0 or len(data) - offset < 22:
        fail("invalid_zip", "ZIP end record is missing or truncated.")
    _, disk, central_disk, disk_count, count, size, start, comment = struct.unpack_from("<4s4H2LH", data, offset)
    if offset + 22 + comment != len(data) or not data.startswith(b"PK\x03\x04"):
        fail("invalid_zip", "ZIP framing or trailing data is unsupported.")
    if disk or central_disk or disk_count != count or count == 65535 or size == 0xffffffff or start == 0xffffffff:
        fail("unsupported_zip", "Split and ZIP64 archives are unsupported.")
    if not 0 < count <= MAX_ENTRIES or size > MAX_CENTRAL:
        fail("metadata_bounds", "ZIP entry count or central-directory size exceeds its limit.")
    if start + size != offset or data[start:start + 4] != b"PK\x01\x02":
        fail("invalid_zip", "ZIP central-directory boundaries are inconsistent.")
    return count


def _path(info: zipfile.ZipInfo) -> tuple[str, bool]:
    name = info.orig_filename
    if not name or len(name.encode("utf-8")) > 512 or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        fail("unsafe_path", "ZIP contains an unsafe or oversized member path.")
    if any(unicodedata.category(char).startswith("C") for char in name):
        fail("unsafe_path", "ZIP member paths cannot contain control characters.")
    directory = name.endswith("/")
    parts = (name[:-1] if directory else name).split("/")
    if any(not part or part in (".", "..") or part.endswith((".", " ")) or len(part.encode("utf-8")) > 128 for part in parts):
        fail("unsafe_path", "ZIP contains empty, traversal or ambiguous path segments.")
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if file_type not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
        fail("nonregular_entry", "ZIP contains a symlink or nonregular entry.")
    if info.external_attr & 0x10 and not directory:
        fail("nonregular_entry", "ZIP directory attributes conflict with its member path.")
    return "/".join(parts), directory


def _inventory(data: bytes) -> tuple[dict[str, bytes], int, set[str]]:
    count = _preflight(data)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != count:
                fail("invalid_zip", "ZIP entry count disagrees with its directory.")
            seen: dict[str, bool] = {}
            planned = []
            total = 0
            for info in entries:
                name, directory = _path(info)
                normalized = unicodedata.normalize("NFC", name).casefold()
                if normalized in seen:
                    fail("duplicate_path", "ZIP contains duplicate or case/Unicode-colliding paths.")
                seen[normalized] = directory
                if info.flag_bits & (1 | 64):
                    fail("encrypted_zip_entry", "ZIP encryption is unsupported; the opaque LG manifest is not ZIP encryption.")
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    fail("unsupported_compression", "Only stored and deflated ZIP members are accepted.")
                if info.file_size > MAX_FILE or info.compress_size > MAX_ZIP or info.file_size > MAX_RATIO * max(1, info.compress_size):
                    fail("member_bounds", "ZIP member size or compression ratio exceeds its limit.")
                if directory and info.file_size:
                    fail("nonregular_entry", "ZIP directory entries must not carry data.")
                total += info.file_size
                if total > MAX_EXPANDED:
                    fail("expanded_bounds", "ZIP expanded size exceeds 20 MiB.")
                planned.append((info, name, directory))
            for name in seen:
                parts = name.split("/")
                if any(seen.get("/".join(parts[:i])) is False for i in range(1, len(parts))):
                    fail("path_conflict", "A ZIP file is also used as a parent directory.")
            files = {}
            for info, name, directory in planned:
                # Reading to EOF verifies CRC and local/central metadata agreement.
                with archive.open(info) as stream:
                    content = stream.read(MAX_FILE + 1)
                if len(content) != info.file_size or len(content) > MAX_FILE:
                    fail("member_bounds", "Expanded member size disagrees with ZIP metadata.")
                if not directory:
                    files[name] = content
            return files, len(entries), {name for _, name, _ in planned}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError, EOFError, ValueError, zlib.error) as error:
        if isinstance(error, PackageError):
            raise
        fail("invalid_zip", "ZIP member validation or CRC verification failed.")


def inspect_package(path: Path, source_zip: Path | None = None) -> dict:
    data = _read_local(Path(path))
    files, entries, paths = _inventory(data)
    roots = {name.split("/")[0] for name in paths}
    if len(roots) != 1 or not re.fullmatch(r"[0-9]{1,32}", next(iter(roots), "")):
        fail("ambiguous_app_root", "Package must contain exactly one numeric application directory.")
    root = next(iter(roots))
    if any("/" not in name for name in files):
        fail("ambiguous_app_root", "Package files must be inside the numeric application directory.")
    relative = {name[len(root) + 1:]: content for name, content in files.items()}
    if any(re.fullmatch(r"[0-9]{1,32}/(?:index\.html|manifest\.xml|developer\.test)", name) for name in relative):
        fail("nested_app_root", "Nested application directory detected. Re-upload the original source ZIP and verify the entry tree.")
    if "index.html" not in relative:
        fail("missing_root_entry", "Application root has no index.html; verify source ZIP root and portal entry value.")
    if not relative["index.html"]:
        fail("empty_root_entry", "Application root index.html is empty.")
    if "manifest.xml" not in relative or "developer.test" not in relative:
        fail("missing_portal_metadata", "Application root must contain manifest.xml and developer.test.")
    if not relative["manifest.xml"].startswith(b"NCGFILE_HEADER"):
        fail("manifest_signature", "Manifest does not have the expected opaque NCGFILE_HEADER prefix.")
    report = {
        "schema": "netcast-package-v1", "structurally_valid": True,
        "entry_path": "<app-id>/index.html", "entry_in_manifest_verified": False,
        "entitlement_verified": False, "manifest": "opaque NCGFILE_HEADER; not decrypted",
        "zip_bytes": len(data), "zip_sha256": hashlib.sha256(data).hexdigest(),
        "entries": entries, "file_count": len(relative),
        "expanded_file_bytes": sum(map(len, relative.values())),
        "files": [{"path": "<app-id>/" + name, "bytes": len(content),
                   "sha256": hashlib.sha256(content).hexdigest()} for name, content in sorted(relative.items())]
    }
    if source_zip is not None:
        source_data = _read_local(Path(source_zip))
        source_files, _, _ = _inventory(source_data)
        if set(source_files) != SOURCE_ASSETS:
            fail("source_asset_set", "Source comparison requires exactly the six current launcher assets at the ZIP root.")
        missing = sorted(SOURCE_ASSETS - relative.keys())
        changed = sorted(name for name in SOURCE_ASSETS & relative.keys() if source_files[name] != relative[name])
        report["source_comparison"] = {
            "sha256": hashlib.sha256(source_data).hexdigest(), "matches": not missing and not changed,
            "missing": missing, "changed": changed,
            "matching": sorted(SOURCE_ASSETS - set(missing) - set(changed))
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Local portal-generated ZIP")
    parser.add_argument("--source-zip", type=Path, help="Explicit original six-asset launcher source ZIP")
    args = parser.parse_args(argv)
    try:
        report = inspect_package(args.package, args.source_zip)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0 if report.get("source_comparison", {}).get("matches", True) else 2
    except PackageError as error:
        print(json.dumps({"structurally_valid": False, "error": error.code, "message": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
