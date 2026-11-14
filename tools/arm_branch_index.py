"""Index candidate ARM-state immediate B/BL encodings in one bounded ELF slice.

This is not a control-flow graph: executable segments may contain literal data,
conditions are not evaluated, and indirect branches/instruction-state changes
are unresolved. No disassembler, loader, target code or network is invoked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

from tools import arm_disassembly

MAX_OUTPUT = 4 * 1024 * 1024
CONDITIONS = ("EQ", "NE", "CS", "CC", "MI", "PL", "VS", "VC",
              "HI", "LS", "GE", "LT", "GT", "LE", "AL")
LIMITS = (
    "Raw encoding candidates only; literal data may decode as branches.",
    "ARM state is asserted by the caller, not inferred from alignment or ELF metadata.",
    "Conditions are not evaluated; calls, returns and reachability are not recovered.",
    "BLX-immediate encodings are counted and excluded; indirect branches and ARM/Thumb transitions are unresolved.",
    "Targets are linked 32-bit addresses; in-range means only inside the selected half-open interval.",
)


def _deadline(timeout: float, arm_state: bool) -> float:
    if arm_state is not True:
        raise ValueError("Explicit ARM-state assertion is required; Thumb/mixed decoding is unsupported")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or
            not math.isfinite(timeout) or not 0 < timeout <= 30):
        raise ValueError("Timeout must be finite, greater than zero and at most 30 seconds")
    return time.monotonic() + timeout


def _check_time(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ValueError("Branch index processing deadline exceeded")


def _index(data: bytes, start: int, end: int, deadline: float) -> dict:
    _check_time(deadline)
    selected = arm_disassembly.validate_range(data, start, end)
    _check_time(deadline)
    offset = selected["file_offset"]
    candidates = []
    excluded_blx = 0
    for index in range(selected["bytes"] // 4):
        if index % 256 == 0:
            _check_time(deadline)
        word = struct.unpack_from("<I", data, offset + index * 4)[0]
        if word & 0x0E000000 != 0x0A000000:
            continue
        condition = word >> 28
        if condition == 15:
            # A32 BLX immediate has 1111:101:H:imm24, not condition-NV B/BL.
            excluded_blx += 1
            continue
        immediate = word & 0xFFFFFF
        if immediate & 0x800000:
            immediate -= 1 << 24
        displacement = immediate * 4
        source = start + index * 4
        target = (source + 8 + displacement) & 0xFFFFFFFF
        candidates.append({
            "source": "0x%08x" % source, "word": "0x%08x" % word,
            "target": "0x%08x" % target, "offset_bytes": displacement,
            "condition": CONDITIONS[condition], "condition_bits": condition,
            "kind": "call" if word & 0x01000000 else "jump",
            "target_relation": "in-range" if start <= target < end else "outside",
        })
    result = {
        "schema": "arm-branch-index-v1", "instruction_state_assumption": "ARM",
        "input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(),
        "range": selected, "word_count": selected["bytes"] // 4,
        "candidate_count": len(candidates), "excluded_blx_immediate_count": excluded_blx,
        "truncated": False, "candidates": candidates, "limits": list(LIMITS),
    }
    _check_time(deadline)
    return result


def index_bytes(data: bytes, start: int, end: int, *, arm_state: bool = False,
                timeout: float = 10) -> dict:
    """Index an immutable ELF snapshot, primarily for host synthetic fixtures."""
    deadline = _deadline(timeout, arm_state)
    if not isinstance(data, bytes):
        raise ValueError("The ELF snapshot must be immutable bytes")
    return _index(data, start, end, deadline)


def index_file(path: Path, start: int, end: int, *, arm_state: bool = False,
               timeout: float = 10) -> dict:
    """Reuse the reviewed bounded no-follow reader and its descriptor checks."""
    deadline = _deadline(timeout, arm_state)
    _check_time(deadline)
    data = arm_disassembly._read_input(path)
    return _index(data, start, end, deadline)


def encode_report(report: dict) -> str:
    encoded = json.dumps(report, separators=(",", ":"), ensure_ascii=True)
    if len(encoded) + 1 > MAX_OUTPUT:
        raise ValueError("Branch index output exceeds the 4-MiB limit")
    return encoded + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--end", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--arm-state", action="store_true", required=True,
                        help="Assert ARM-state interpretation; this does not prove code/data identity")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args(argv)
    try:
        report = index_file(args.input, args.start, args.end,
                            arm_state=args.arm_state, timeout=args.timeout)
        output = encode_report(report)
    except (OSError, ValueError, struct.error) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
