"""Read-only LG partinfo v2 ARM32 disk-layout inventory.

Parses update metadata, not a live device. No mounting, flash access or writes.
Explicit little-endian wire structures avoid host pointer/alignment assumptions.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct

HEADER = struct.Struct("<IIIB3x32sQQIIII")
ENTRY = struct.Struct("<32sQQ32sIIBB2xI")
CAPACITY = 128
FILE_SIZE = HEADER.size + CAPACITY * ENTRY.size
FLAGS = {1: "FIXED", 2: "MASTER", 4: "IDKEY", 8: "CACHE", 16: "DATA", 32: "SECURED", 64: "ERASE"}


class PartitionError(ValueError):
    """Unrecognized or inconsistent partition-map data."""


def string_field(data: bytes) -> str:
    if b"\0" not in data:
        raise PartitionError("String field is not terminated")
    value, padding = data.split(b"\0", 1)
    if any(byte < 32 or byte > 126 for byte in value) or any(padding):
        raise PartitionError("Invalid string field or padding")
    return value.decode("ascii")


def inventory(data: bytes) -> dict:
    if len(data) != FILE_SIZE:
        raise PartitionError(f"Expected exactly {FILE_SIZE} bytes for partinfo v2 ARM32")
    magic, current, old, count, device_raw, device_size, physical, virtual, cached, bankwidth, used = HEADER.unpack_from(data)
    if magic != 0x20120716:
        raise PartitionError("Unsupported partinfo magic")
    if not 0 < count <= CAPACITY or not 0 < device_size <= (1 << 64) - 1 or used not in {0, 1}:
        raise PartitionError("Invalid partition count or device fields")
    if any(data[13:16]) or any(data[HEADER.size + count * ENTRY.size:]):
        raise PartitionError("Nonzero header padding or undeclared partition slots")
    device_name = string_field(device_raw)
    if device_name != "mtk3598-emmc":
        raise PartitionError("Unsupported device-layout label")
    records = []
    gaps = []
    last_end = 0
    groups: dict[str, list[int]] = defaultdict(list)
    for index in range(count):
        record_offset = HEADER.size + index * ENTRY.size
        raw = data[record_offset:record_offset + ENTRY.size]
        name_raw, offset, size, filename_raw, file_size, version, part_used, valid, flags = ENTRY.unpack(raw)
        name, filename = string_field(name_raw), string_field(filename_raw)
        if not name or not size or part_used not in {0, 1} or valid not in {0, 1} or any(raw[90:92]):
            raise PartitionError("Invalid partition fields")
        end = offset + size
        if end > (1 << 64) - 1 or offset < last_end:
            raise PartitionError("Partition extent overflow or overlap")
        if file_size > size:
            raise PartitionError("Declared payload exceeds partition size")
        if offset > last_end:
            gaps.append({"start": last_end, "end_exclusive": offset, "size": offset - last_end})
        records.append({"index": index, "record_offset": record_offset, "name": name,
                        "offset": offset, "size": size, "end_exclusive": end,
                        "offset_hex": f"0x{offset:x}", "size_hex": f"0x{size:x}", "end_exclusive_hex": f"0x{end:x}",
                        "filename": filename, "declared_file_size": file_size,
                        "software_version": f"0x{version:08x}", "used": part_used, "valid": valid,
                        "flags": flags, "flag_labels": [label for bit, label in FLAGS.items() if flags & bit],
                        "unknown_flag_bits": flags & ~sum(FLAGS),
                        "within_declared_device_size": end <= device_size})
        groups[name].append(index)
        last_end = end
    repeated = [{"name": name, "indices": indices,
                 "equal_sizes": len({records[i]["size"] for i in indices}) == 1,
                 "equal_filenames": len({records[i]["filename"] for i in indices}) == 1}
                for name, indices in groups.items() if len(indices) > 1]
    return {"format": "LG partinfo v2, ARM32 layout, little endian", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "magic": f"0x{magic:08x}",
            "current_epk_version": current, "old_epk_version": old, "declared_partitions": count,
            "entry_capacity": CAPACITY, "header_size": HEADER.size, "entry_size": ENTRY.size,
            "unused_zero_slots": CAPACITY - count,
            "device": {"label": device_name, "declared_size": device_size, "declared_size_hex": f"0x{device_size:x}",
                       "physical_base": physical, "virtual_field": virtual, "cached_field": cached,
                       "bankwidth": bankwidth, "used": used},
            "partitions": records, "repeated_names": repeated, "unassigned_gaps": gaps,
            "maximum_described_end": last_end,
            "outside_device_bound_indices": [item["index"] for item in records if not item["within_declared_device_size"]],
            "scope": "Static update metadata only; does not identify active partitions, physical capacity or working recovery"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        if args.input.is_symlink() or not args.input.is_file():
            raise PartitionError("Input must be a regular non-symlink file")
        with args.input.open("rb") as source:
            report = inventory(source.read(FILE_SIZE + 1))
        print(json.dumps(report, indent=2))
    except (OSError, PartitionError) as error:
        parser.exit(1, f"Partition inventory error: {error}\n")


if __name__ == "__main__":
    main()
