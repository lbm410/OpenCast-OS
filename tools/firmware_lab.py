"""Bounded, offline historical EPK2 inventory and explicitly selected package copying.

No filesystem recursion, firmware execution, network calls or embedded key values.
Requires cryptography only for this optional firmware laboratory workflow.
The data layout is documented in docs/firmware-extraction.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import struct
from typing import BinaryIO

MAX_FILE = 2 * 1024**3
MAX_ROWS = 4096
MAX_SEGMENT = 128 * 1024**2
HEADER_OFFSET = 128
HEADER_SIZE = 1332
HEADER_SIGNED_SIZE = 1588
FIRST_PACKAGE_OFFSET = 1748
LOCATION = struct.Struct("<II4sII")
PAK_HEADER = struct.Struct("<4sI64sIIIIII4s24sI")


class LabError(ValueError):
    """Invalid or unsupported input; fail without extraction."""


def read_at(stream: BinaryIO, offset: int, size: int, limit: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > limit:
        raise LabError("Read exceeds input bounds")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise LabError("Truncated input")
    return data


def field_text(data: bytes) -> str:
    raw = data.split(b"\0", 1)[0]
    if any(byte < 32 or byte > 126 for byte in raw):
        raise LabError("Non-printable metadata")
    return raw.decode("ascii")


def decrypt(data: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    # Legacy EPK copies a trailing partial block without decrypting it.
    blocks = len(data) // 16 * 16
    decoder = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return decoder.update(data[:blocks]) + decoder.finalize() + data[blocks:]


def select_key(key_file: Path, encrypted_header: bytes) -> tuple[bytes, int]:
    if key_file.stat().st_size > 65536:
        raise LabError("Key list exceeds bound")
    for number, line in enumerate(key_file.read_text().splitlines(), 1):
        match = re.match(r"^([0-9A-Fa-f]{32}|[0-9A-Fa-f]{48}|[0-9A-Fa-f]{64})(?:\s|$)", line)
        if not match:
            continue
        candidate = bytes.fromhex(match.group(1))
        if decrypt(encrypted_header, candidate)[12:16] == b"EPK2":
            return candidate, number
    raise LabError("No supplied key matches the historical EPK2 header")


def verify_signature(public_key: object, signature: bytes, data: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        # Reviewed upstream scheme: RSA PKCS#1 v1.5 of SHA1(SHA1(data)).
        public_key.verify(signature, hashlib.sha1(data).digest(), padding.PKCS1v15(), hashes.SHA1())
        return True
    except InvalidSignature:
        return False


def parse_packages(stream: BinaryIO, header: bytes, key: bytes, file_size: int) -> list[dict]:
    file_type, declared_size, count, magic, version, ota_raw = struct.unpack_from("<4sII4s4s32s", header)
    if file_type != b"epak" or magic != b"EPK2" or not 0 < count <= 64:
        raise LabError("Invalid EPK2 header")
    packages: list[dict] = []
    signatures = 0
    previous_end = FIRST_PACKAGE_OFFSET
    for index in range(count):
        offset, image_size, name_raw, image_version, max_segment = LOCATION.unpack_from(header, 52 + index * LOCATION.size)
        name = field_text(name_raw)
        if not re.fullmatch(r"[A-Za-z0-9]{4}", name):
            raise LabError("Unsafe package name")
        if any(item["name"] == name for item in packages):
            raise LabError("Duplicate package name")
        cursor = 128 + offset + signatures * 128
        padding = cursor - previous_end
        if not 0 <= padding <= 3:
            raise LabError("Unexpected gap or overlap between packages")
        if not 128 < image_size <= MAX_FILE or not 0 < max_segment <= MAX_SEGMENT:
            raise LabError("Package or segment size exceeds bounds")
        segments = []
        declared_segments = None
        image_data_size = None
        model = None
        build = None
        while declared_segments is None or len(segments) < declared_segments:
            if len(segments) >= MAX_ROWS:
                raise LabError("Too many segments")
            raw = read_at(stream, cursor + 128, PAK_HEADER.size, file_size)
            fields = PAK_HEADER.unpack(decrypt(raw, key))
            (pak_name, total_size, model_raw, sw_version, sw_date, dev_mode,
             segment_count, segment_size, segment_index, pak_magic, reserved, crc) = fields
            if pak_magic != b"MPAK" or pak_name != name_raw or sw_version != image_version:
                raise LabError("Invalid package header or version")
            if not 0 < segment_count <= MAX_ROWS or segment_index != len(segments):
                raise LabError("Invalid segment sequence")
            if not 0 < segment_size <= max_segment or cursor + 256 + segment_size > file_size:
                raise LabError("Segment data exceeds bounds")
            if declared_segments is None:
                declared_segments, image_data_size = segment_count, total_size
                model, build = field_text(model_raw), dev_mode
            elif segment_count != declared_segments or total_size != image_data_size or field_text(model_raw) != model:
                raise LabError("Inconsistent package segment metadata")
            segments.append({"index": segment_index, "signature_offset": cursor,
                             "signed_offset": cursor + 128, "signed_size": 128 + segment_size,
                             "data_offset": cursor + 256, "size": segment_size,
                             "declared_crc32": f"{crc:08x}"})
            cursor += 256 + segment_size
            signatures += 1
        if sum(item["size"] for item in segments) != image_data_size:
            raise LabError("Package data length mismatch")
        if image_data_size + 128 * len(segments) != image_size:
            raise LabError("Package container length mismatch")
        packages.append({"name": name, "version": f"{image_version:08x}", "model_label": model,
                         "size": image_data_size, "container_size_without_signatures": image_size,
                         "build_type": build, "segment_count": declared_segments,
                         "alignment_bytes_before": padding, "segments": segments})
        previous_end = cursor
    if previous_end != file_size:
        raise LabError("Unaccounted trailing bytes")
    if sum(item["container_size_without_signatures"] for item in packages) != declared_size:
        raise LabError("Declared aggregate package size mismatch")
    return packages


def inspect(stream: BinaryIO, key_file: Path, public_key_file: Path) -> tuple[dict, bytes, object]:
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    size = os.fstat(stream.fileno()).st_size
    if not FIRST_PACKAGE_OFFSET <= size <= MAX_FILE:
        raise LabError("Input size outside bounds")
    encrypted_header = read_at(stream, HEADER_OFFSET, HEADER_SIZE, size)
    key, key_line = select_key(key_file, encrypted_header)
    header = decrypt(encrypted_header, key)
    file_type, declared_size, count, magic, version, ota_raw = struct.unpack_from("<4sII4s4s32s", header)
    if public_key_file.stat().st_size > 16384:
        raise LabError("Public key file exceeds bound")
    public_key = load_pem_public_key(public_key_file.read_bytes())
    if not isinstance(public_key, RSAPublicKey) or public_key.key_size != 1024:
        raise LabError("Unsupported signature key")
    header_valid = verify_signature(public_key, read_at(stream, 0, 128, size),
                                   read_at(stream, 128, HEADER_SIGNED_SIZE, size))
    if not header_valid:
        raise LabError("Header signature failed; refusing to interpret package table")
    packages = parse_packages(stream, header, key, size)
    stream.seek(0)
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {"format": "EPK2 (historical layout without reserved word)",
                "input_size": size, "input_sha256": digest, "declared_file_size": declared_size,
                "version": ".".join(f"{part:02x}" for part in reversed(version)),
                "ota_id": field_text(ota_raw),
                "platform_version": field_text(read_at(stream, 1716, 16, size)),
                "sdk_version": field_text(read_at(stream, 1732, 16, size)),
                "package_count": count,
                "key_source": {"file": key_file.name, "entry_line": key_line},
                "signature": {"scheme": "RSA-1024 PKCS1v15 SHA1(SHA1(ciphertext))",
                              "public_key_file": public_key_file.name,
                              "header_verified": header_valid, "header_covered_bytes": HEADER_SIGNED_SIZE,
                              "package_segments": "not checked"},
                "packages": packages}
    return manifest, key, public_key


def audit_signatures(stream: BinaryIO, manifest: dict, public_key: object) -> dict:
    """Verify every exact declared ciphertext span without extracting packages.

    The manifest must come from inspect(). A one-bit mutation in memory checks
    rejection without changing the input. Success is relative to the supplied
    public key, never a claim about publisher identity or runtime enforcement.
    """
    if not manifest["signature"]["header_verified"]:
        raise LabError("Audit requires a valid header signature")
    verified = 0
    packages = []
    negative_control = None
    for package in manifest["packages"]:
        if not package["segments"]:
            raise LabError("Empty segment list")
        for segment in package["segments"]:
            size = segment["signed_size"]
            if not 128 < size <= MAX_SEGMENT + 128:
                raise LabError("Signed span exceeds bounds")
            signature = read_at(stream, segment["signature_offset"], 128, manifest["input_size"])
            signed = read_at(stream, segment["signed_offset"], size, manifest["input_size"])
            if not verify_signature(public_key, signature, signed):
                raise LabError("Package segment signature failed during audit")
            if negative_control is None:
                altered = bytes([signed[0] ^ 1]) + signed[1:]
                if verify_signature(public_key, signature, altered):
                    raise LabError("Signature negative control was accepted")
                negative_control = {"package": package["name"], "index": segment["index"],
                                    "signed_offset": segment["signed_offset"],
                                    "mutation": "first ciphertext byte XOR 1, in memory only",
                                    "rejected": True}
            verified += 1
        packages.append({"name": package["name"], "verified_segments": len(package["segments"])})
    if not verified:
        raise LabError("No signatures available to audit")
    return {"verified_segments": verified, "packages": packages,
            "negative_control": negative_control,
            "scope": "Exact declared spans; consistency with supplied public key only"}


def extract_selected(stream: BinaryIO, manifest: dict, key: bytes, public_key: object,
                     names: list[str], output: Path) -> list[dict]:
    if len(names) != len(set(names)):
        raise LabError("Duplicate package selection")
    selected = [item for item in manifest["packages"] if item["name"] in names]
    if len(selected) != len(names):
        raise LabError("Unknown package selection")
    if not manifest["signature"]["header_verified"]:
        raise LabError("Extraction requires a valid header signature")
    # A new directory avoids collisions and pre-existing symlink traversal.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    results = []
    for package in selected:
        destination = output / (package["name"] + ".pak")
        digest = hashlib.sha256()
        try:
            with destination.open("xb") as writer:
                for segment in package["segments"]:
                    encrypted = read_at(stream, segment["data_offset"], segment["size"], manifest["input_size"])
                    signature = read_at(stream, segment["signature_offset"], 128, manifest["input_size"])
                    signed_data = read_at(stream, segment["signed_offset"], segment["signed_size"], manifest["input_size"])
                    if not verify_signature(public_key, signature, signed_data):
                        raise LabError("Package segment signature failed")
                    decoded = decrypt(encrypted, key)
                    digest.update(decoded)
                    writer.write(decoded)
            destination.chmod(0o444)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        results.append({"name": package["name"], "file": destination.name,
                        "size": package["size"], "sha256": digest.hexdigest(),
                        "verified_segments": len(package["segments"])})
    return results


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.alarm(180)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--key-file", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-all", action="store_true",
                        help="Audit every segment signature without requiring package extraction")
    args = parser.parse_args()
    if bool(args.package) != bool(args.output_dir):
        parser.error("Package selection and output directory must be supplied together")
    try:
        if args.input.is_symlink() or not stat.S_ISREG(args.input.stat().st_mode):
            raise LabError("Input must be a regular non-symlink file")
        with args.input.open("rb") as stream:
            manifest, key, public_key = inspect(stream, args.key_file, args.public_key)
            if args.verify_all:
                manifest["signature_audit"] = audit_signatures(stream, manifest, public_key)
                manifest["signature"]["package_segments"] = "all exact declared spans verified"
                manifest["signature"]["verified_segments"] = manifest["signature_audit"]["verified_segments"]
            if args.package:
                manifest["extracted"] = extract_selected(stream, manifest, key, public_key, args.package, args.output_dir)
                if not args.verify_all:
                    manifest["signature"]["package_segments"] = "verified for explicitly extracted packages only"
                    manifest["signature"]["verified_segments"] = sum(item["verified_segments"] for item in manifest["extracted"])
        print(json.dumps(manifest, indent=2))
    except (LabError, OSError) as error:
        parser.exit(1, f"Firmware laboratory error: {error}\n")


if __name__ == "__main__":
    main()
