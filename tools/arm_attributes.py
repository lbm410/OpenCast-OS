"""Read bounded ARM ELF build attributes and ABI header flags without executing the target.

The reader locates the ``SHT_ARM_ATTRIBUTES`` section of a 32-bit ARM ELF file, decodes the
public ``aeabi`` subsection and reports the ELF ``e_flags`` ABI bits. It is a static host
parser: the input is opened read-only, never loaded, linked or run.

Tag numbers, parameter types and value meanings are transcribed from the Arm ABI sources
pinned in ``SPEC``. Anything those sources do not define is reported as unknown or
unsupported; the reader does not guess an ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import sys

try:
    from tools import elf_inventory
except ModuleNotFoundError:  # isolated mode (-I) or direct script execution
    _spec = importlib.util.spec_from_file_location(
        "elf_inventory", Path(__file__).resolve().with_name("elf_inventory.py"))
    elf_inventory = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(elf_inventory)

SPEC = {
    "repository": "https://github.com/ARM-software/abi-aa",
    "commit": "a1b53459479e88f3492ca9b11a161313764ab138",
    "build_attributes": "addenda32/addenda32.rst (Addenda to, and Errata in, the ABI for the Arm "
                        "Architecture), chapter 'Build attributes'",
    "elf": "aaelf32/aaelf32.rst (ELF for the Arm Architecture), sections 'ELF Header' and "
           "'Build Attributes'",
}

MAX_FILE = elf_inventory.MAX_FILE
MAX_SECTIONS = 4096
MAX_SECTION_NAMES = 1024**2
MAX_ATTRIBUTES_SECTION = 1024**2
MAX_VENDOR_NAME = 64
MAX_NTBS = 4096
MAX_ULEB_BYTES = 5
# The next four limits are totals for one complete attributes section, not per subsection.
MAX_RECORDS = 4096
MAX_INDEXES = 65536
MAX_SUBSECTIONS = 64
MAX_SCOPES = 256

# The only uses of Tag_also_compatible_with the pinned specification defines, as
# (Tag_CPU_arch of the file, nested Tag_CPU_arch value); every other use is reserved.
ALSO_COMPATIBLE_DEFINED = {(2, 11), (11, 2), (14, 15), (15, 14)}

EM_ARM = 40
SHT_STRTAB = 3
SHT_ARM_ATTRIBUTES = 0x70000003
SHN_XINDEX = 0xFFFF
ATTRIBUTES_NAME = ".ARM.attributes"

EF_ARM_ABIMASK = 0xFF000000
EF_ARM_BE8 = 0x00800000
EF_ARM_GCCMASK = 0x00400FFF
EF_ARM_ABI_FLOAT_HARD = 0x00000400
EF_ARM_ABI_FLOAT_SOFT = 0x00000200

TAG_FILE, TAG_SECTION, TAG_SYMBOL = 1, 2, 3
SCOPES = {TAG_FILE: "file", TAG_SECTION: "section", TAG_SYMBOL: "symbol"}

ULEB, NTBS, COMPATIBILITY, ALSO_COMPATIBLE, NODEFAULTS = (
    "uleb128", "ntbs", "uleb128+ntbs", "ntbs(tag,value)", "uleb128(ignored)")

_ARCH = {
    0: "Pre-v4", 1: "Arm v4", 2: "Arm v4T", 3: "Arm v5T", 4: "Arm v5TE", 5: "Arm v5TEJ",
    6: "Arm v6", 7: "Arm v6KZ", 8: "Arm v6T2", 9: "Arm v6K", 10: "Arm v7", 11: "Arm v6-M",
    12: "Arm v6S-M", 13: "Arm v7E-M", 14: "Arm v8-A", 15: "Arm v8-R",
    16: "Arm v8-M.baseline", 17: "Arm v8-M.mainline", 18: "Arm v8.1-A", 19: "Arm v8.2-A",
    20: "Arm v8.3-A", 21: "Arm v8.1-M.mainline", 22: "Arm v9-A",
}
_GOALS = {
    0: "no particular goal, or no information recorded",
    1: "speed, size and debug illusion preserved", 2: "aggressively for speed",
    3: "small size, speed and debugging preserved", 4: "aggressively for small size",
    5: "good debugging, speed and size preserved", 6: "best debugging illusion",
}
_FP_GOALS = {
    0: "no particular FP goal, or no information recorded",
    1: "speed, size and accuracy preserved", 2: "aggressively for speed",
    3: "small size, speed and accuracy preserved", 4: "aggressively for small size",
    5: "accuracy, speed and size preserved", 6: "best accuracy",
}

# tag -> (name, parameter type, {value: meaning} or None)
TAGS = {
    4: ("Tag_CPU_raw_name", NTBS, None),
    5: ("Tag_CPU_name", NTBS, None),
    6: ("Tag_CPU_arch", ULEB, _ARCH),
    7: ("Tag_CPU_arch_profile", ULEB, {
        0: "not applicable, or indicated by Tag_CPU_arch",
        0x41: "A: application profile", 0x52: "R: real-time profile",
        0x4D: "M: microcontroller profile",
        0x53: "S: application or real-time profile (classic programmer's model)"}),
    8: ("Tag_ARM_ISA_use", ULEB, {
        0: "Arm instructions not permitted", 1: "Arm instructions permitted"}),
    9: ("Tag_THUMB_ISA_use", ULEB, {
        0: "Thumb instructions not permitted",
        1: "16-bit Thumb instructions permitted, including BL (deprecated value)",
        2: "32-bit Thumb instructions permitted, implies 16-bit (deprecated value)",
        3: "Thumb permitted; instruction set determined by Tag_CPU_arch and "
           "Tag_CPU_arch_profile"}),
    10: ("Tag_FP_arch", ULEB, {
        0: "instructions requiring FP hardware not permitted",
        1: "FP ISA v1 permitted", 2: "FP ISA v2 permitted (implies v1)",
        3: "FP ISA v3 permitted (implies v2)",
        4: "FP ISA v3 permitted, registers D0-D15/S0-S31 only",
        5: "FP ISA v4 permitted (implies non-vector v3)",
        6: "FP ISA v4 permitted, registers D0-D15/S0-S31 only",
        7: "Arm v8-A FP ISA permitted",
        8: "Arm v8-A FP ISA permitted, registers D0-D15/S0-S31 only"}),
    11: ("Tag_WMMX_arch", ULEB, {
        0: "WMMX not permitted", 1: "WMMX v1 permitted", 2: "WMMX v2 permitted"}),
    12: ("Tag_Advanced_SIMD_arch", ULEB, {
        0: "Advanced SIMD (Neon) not permitted", 1: "Advanced SIMDv1 permitted",
        2: "Advanced SIMDv2 permitted (half-precision FP and fused MAC)",
        3: "Arm v8-A Advanced SIMD permitted", 4: "Arm v8.1-A Advanced SIMD permitted"}),
    13: ("Tag_PCS_config", ULEB, {
        0: "no standard configuration used, or no information recorded",
        1: "bare platform configuration", 2: "Linux application configuration",
        3: "Linux DSO configuration", 4: "Palm OS 2004 configuration",
        5: "reserved to future Palm OS configuration", 6: "Symbian OS 2004 configuration",
        7: "reserved to future Symbian OS configuration"}),
    14: ("Tag_ABI_PCS_R9_use", ULEB, {
        0: "R9 used as V6, a callee-saved register", 1: "R9 used as SB, a static base register",
        2: "R9 used as a thread-local-storage pointer", 3: "R9 not used"}),
    15: ("Tag_ABI_PCS_RW_data", ULEB, {
        0: "RW static data may be addressed absolutely", 1: "RW static data PC-relative only",
        2: "RW static data SB-relative only", 3: "RW static data not permitted"}),
    16: ("Tag_ABI_PCS_RO_data", ULEB, {
        0: "RO static data may be addressed absolutely", 1: "RO static data PC-relative only",
        2: "RO static data not permitted"}),
    17: ("Tag_ABI_PCS_GOT_use", ULEB, {
        0: "importing static data not permitted", 1: "imported data addressed directly",
        2: "imported data addressed indirectly (for example via a GOT)"}),
    18: ("Tag_ABI_PCS_wchar_t", ULEB, {
        0: "wchar_t use prohibited", 2: "wchar_t size 2", 4: "wchar_t size 4"}),
    19: ("Tag_ABI_FP_rounding", ULEB, {
        0: "IEEE 754 round to nearest", 1: "rounding mode chosen at run time"}),
    20: ("Tag_ABI_FP_denormal", ULEB, {
        0: "denormal numbers might be flushed to (+) zero",
        1: "may depend on IEEE 754 denormal numbers",
        2: "may depend on the sign of a flushed-to-zero number being preserved"}),
    21: ("Tag_ABI_FP_exceptions", ULEB, {
        0: "does not check for inexact results", 1: "may check the IEEE 754 inexact exception"}),
    22: ("Tag_ABI_FP_user_exceptions", ULEB, {
        0: "does not enable or use IEEE user exceptions",
        1: "may enable and use IEEE 754 user exceptions"}),
    23: ("Tag_ABI_FP_number_model", ULEB, {
        0: "floating point numbers not used", 1: "IEEE 754 format normal numbers only",
        2: "numbers, infinities and one quiet NaN", 3: "all IEEE 754-defined FP encodings"}),
    24: ("Tag_ABI_align_needed", ULEB, {
        0: "does not depend on alignment of 8-byte data or extended alignment",
        1: "may depend on 8-byte alignment of 8-byte data",
        2: "may depend on 4-byte alignment of 8-byte data", 3: "reserved"}),
    25: ("Tag_ABI_align_preserved", ULEB, {
        0: "8-byte alignment of 8-byte data not required to be preserved",
        1: "preserves 8-byte alignment of 8-byte data",
        2: "preserves 8-byte alignment of 8-byte data and (SP MOD 8) = 0 at all "
           "instruction boundaries", 3: "reserved"}),
    26: ("Tag_ABI_enum_size", ULEB, {
        0: "enum use prohibited", 1: "enums occupy the smallest sufficient container",
        2: "enum containers are 32-bit",
        3: "every enum visible across an ABI-complying interface needs 32 bits"}),
    27: ("Tag_ABI_HardFP_use", ULEB, {
        0: "FP use implied by Tag_FP_arch",
        1: "single-precision variant derived from Tag_FP_arch", 2: "reserved",
        3: "FP use implied by Tag_FP_arch (deprecated duplicate of 0)"}),
    28: ("Tag_ABI_VFP_args", ULEB, {
        0: "FP parameters/results follow AAPCS, base variant",
        1: "FP parameters/results follow AAPCS, VFP variant",
        2: "FP parameters/results follow toolchain-specific conventions",
        3: "compatible with both base and VFP variants; non-variadic functions pass no "
           "FP parameters/results"}),
    29: ("Tag_ABI_WMMX_args", ULEB, {
        0: "WMMX parameters/results follow AAPCS, base variant",
        1: "WMMX parameters/results follow Intel WMMX conventions",
        2: "WMMX parameters/results follow toolchain-specific conventions"}),
    30: ("Tag_ABI_optimization_goals", ULEB, _GOALS),
    31: ("Tag_ABI_FP_optimization_goals", ULEB, _FP_GOALS),
    32: ("Tag_compatibility", COMPATIBILITY, None),
    34: ("Tag_CPU_unaligned_access", ULEB, {
        0: "unaligned data accesses not intended",
        1: "v6-style unaligned data accesses may be made"}),
    36: ("Tag_FP_HP_extension", ULEB, {
        0: "half-precision instructions only as present in the indicated FP/ASIMD sets",
        1: "half-precision extension to VFPv3/Advanced SIMDv1 permitted",
        2: "half-precision extension to Armv8.2-A FP and Advanced SIMD permitted"}),
    38: ("Tag_ABI_FP_16bit_format", ULEB, {
        0: "16-bit floating point numbers not used", 1: "IEEE 754 16-bit format permitted",
        2: "VFPv3/Advanced SIMD alternative 16-bit format permitted"}),
    42: ("Tag_MPextension_use", ULEB, {
        0: "Arm v7 MP extension not permitted, or no information",
        1: "Arm v7 MP extension permitted"}),
    44: ("Tag_DIV_use", ULEB, {
        0: "divide instructions may be used if guaranteed present in the architecture, "
           "or no information", 1: "SDIV/UDIV explicitly not permitted",
        2: "SDIV/UDIV permitted as an optional extension above the base architecture"}),
    46: ("Tag_DSP_extension", ULEB, {
        0: "DSP instructions may be used if guaranteed present in the architecture",
        1: "Thumb DSP permitted as an optional extension above the base architecture"}),
    48: ("Tag_MVE_arch", ULEB, {
        0: "M-profile Vector Extension not permitted", 1: "integer MVE permitted",
        2: "integer and floating-point MVE permitted"}),
    50: ("Tag_PAC_extension", ULEB, {
        0: "PAC/AUT instructions not permitted", 1: "PAC/AUT permitted in the NOP space",
        2: "PAC/AUT permitted in the NOP and non-NOP space"}),
    52: ("Tag_BTI_extension", ULEB, {
        0: "BTI instructions not permitted", 1: "BTI permitted in the NOP space",
        2: "BTI permitted in the NOP and non-NOP space"}),
    64: ("Tag_nodefaults", NODEFAULTS, None),
    65: ("Tag_also_compatible_with", ALSO_COMPATIBLE, None),
    66: ("Tag_T2EE_use", ULEB, {
        0: "T2EE not permitted, or no information", 1: "T2EE permitted"}),
    67: ("Tag_conformance", NTBS, None),
    68: ("Tag_Virtualization_use", ULEB, {
        0: "no virtualization extension permitted, or no information",
        1: "TrustZone extension permitted", 2: "virtualization extensions permitted",
        3: "TrustZone and virtualization extensions permitted"}),
    70: ("Tag_MPextension_use (legacy encoding, recoded to 42)", ULEB, {
        0: "Arm v7 MP extension not permitted, or no information",
        1: "Arm v7 MP extension permitted"}),
    72: ("Tag_FramePointer_use", ULEB, {
        0: "no claim about frame-pointer rules",
        1: "creates a frame record for all functions that may modify LR",
        2: "creates no frame records but preserves FP"}),
    74: ("Tag_BTI_use", ULEB, {
        0: "compiled without branch target enforcement",
        1: "compiled with branch target enforcement"}),
    76: ("Tag_PACRET_use", ULEB, {
        0: "compiled without return address signing", 1: "compiled with return address signing"}),
}

DEFAULT_RULE = ("addenda32 'Default values for public tags': omitting a public tag in file "
                "scope is identical to including it with a value of 0 or the empty string")


class AttributesError(ValueError):
    """The attributes section violates the pinned format or a bound of this reader."""


def _meaning(tag: int, value: int):
    table = TAGS[tag][2]
    if table is None:
        return None
    if tag in (24, 25) and 4 <= value <= 12:
        return ("8-byte alignment of 8-byte data, plus extended alignment with parameter "
                f"n={value} as defined for this tag")
    return table.get(value)


class Cursor:
    """Bounded forward reader over one byte range of the attributes section."""

    def __init__(self, data: bytes, start: int, end: int, endian: str):
        if not 0 <= start <= end <= len(data):
            raise AttributesError("attribute range exceeds section bounds")
        self.data, self.pos, self.end, self.endian = data, start, end, endian

    def remaining(self) -> int:
        return self.end - self.pos

    def byte(self) -> int:
        if self.pos >= self.end:
            raise AttributesError(f"truncated data at section offset {self.pos:#x}")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def uint32(self) -> int:
        if self.remaining() < 4:
            raise AttributesError(f"truncated 32-bit length at section offset {self.pos:#x}")
        (value,) = struct.unpack_from(self.endian + "I", self.data, self.pos)
        self.pos += 4
        return value

    def uleb128(self) -> int:
        start, value = self.pos, 0
        for index in range(MAX_ULEB_BYTES):
            current = self.byte()
            value |= (current & 0x7F) << (7 * index)
            if not current & 0x80:
                if value > 0xFFFFFFFF:
                    raise AttributesError(f"ULEB128 at section offset {start:#x} exceeds 32 bits")
                return value
        raise AttributesError(f"ULEB128 at section offset {start:#x} exceeds {MAX_ULEB_BYTES} bytes")

    def ntbs(self, limit: int = MAX_NTBS) -> bytes:
        start = self.pos
        stop = self.data.find(b"\0", start, min(self.end, start + limit + 1))
        if stop < 0:
            raise AttributesError(
                f"string at section offset {start:#x} is unterminated or longer than {limit} bytes")
        self.pos = stop + 1
        return self.data[start:stop]


class Budget:
    """Running totals shared by every subsection of one attributes section."""

    def __init__(self):
        self.used = {"records": 0, "indexes": 0, "subsections": 0, "scopes": 0}
        self.limits = {"records": MAX_RECORDS, "indexes": MAX_INDEXES,
                       "subsections": MAX_SUBSECTIONS, "scopes": MAX_SCOPES}

    def take(self, kind: str, label: str):
        self.used[kind] += 1
        if self.used[kind] > self.limits[kind]:
            raise AttributesError(f"too many {label} in the attributes section")


def _text(raw: bytes) -> str:
    return raw.decode("ascii", "backslashreplace")


def _parse_also_compatible(cursor: Cursor) -> dict:
    """Decode Tag_also_compatible_with: a nested tag, then a value in that tag's own encoding.

    A numeric inner value is followed by one extra NUL byte; a string inner value supplies its
    own terminator. Unknown inner tags follow the parity convention used for unknown tags.
    """
    inner = cursor.uleb128()
    result = {"inner_tag": inner, "inner_known": inner in TAGS}
    kind = TAGS[inner][1] if inner in TAGS else (ULEB if inner > 32 and inner % 2 == 0 else NTBS)
    if inner in TAGS:
        result["inner_name"] = TAGS[inner][0]
    if kind == ULEB:
        value = cursor.uleb128()
        if cursor.byte() != 0:
            raise AttributesError("Tag_also_compatible_with numeric value lacks its NUL terminator")
        result["inner_value"] = value
        result["inner_meaning"] = _meaning(inner, value) if inner in TAGS else None
    elif kind == NTBS:
        result["inner_value"] = _text(cursor.ntbs())
    else:
        raise AttributesError(
            f"Tag_also_compatible_with nests tag {inner}, whose encoding cannot be nested")
    return result


def _parse_attribute(cursor: Cursor, base: int) -> dict:
    offset = cursor.pos
    tag = cursor.uleb128()
    record = {"tag": tag, "section_offset": offset, "file_offset": base + offset}
    if tag in TAGS:
        name, kind, _ = TAGS[tag]
        record.update(name=name, type=kind, known=True)
        if kind == ULEB:
            value = cursor.uleb128()
            meaning = _meaning(tag, value)
            record.update(value=value, meaning=meaning, value_defined=meaning is not None)
        elif kind == NTBS:
            record.update(value=_text(cursor.ntbs()))
        elif kind == NODEFAULTS:
            record.update(value=cursor.uleb128(), meaning="parameter ignored by the specification")
        elif kind == COMPATIBILITY:
            flag = cursor.uleb128()
            record.update(value={"flag": flag, "vendor": _text(cursor.ntbs())})
        else:  # ALSO_COMPATIBLE
            nested = _parse_also_compatible(cursor)
            record.update(value=[nested["inner_tag"], nested["inner_value"]], **nested)
        return record
    if tag <= 32:
        # Tags 1-32 must be comprehended individually; 0-3 are not attribute tags.
        raise AttributesError(f"tag {tag} at section offset {offset:#x} is not a valid attribute tag")
    # Unknown tag above 32: even tags carry ULEB128, odd tags a NUL-terminated string.
    record.update(name=None, known=False, must_comprehend=(tag % 128) < 64)
    if tag % 2 == 0:
        record.update(type=ULEB, value=cursor.uleb128())
    else:
        record.update(type=NTBS, value=_text(cursor.ntbs()))
    return record


def _parse_public_subsection(data: bytes, start: int, end: int, endian: str, base: int,
                             budget: Budget) -> list:
    scopes, cursor = [], Cursor(data, start, end, endian)
    while cursor.remaining():
        budget.take("scopes", "sub-subsections")
        scope_start = cursor.pos
        scope_tag = cursor.byte()
        size = cursor.uint32()
        if size < 5 or size > end - scope_start:
            raise AttributesError(
                f"sub-subsection at section offset {scope_start:#x} has invalid size {size}")
        scope_end = scope_start + size
        scope = {"scope_tag": scope_tag, "scope": SCOPES.get(scope_tag),
                 "section_offset": scope_start, "size": size}
        if scope_tag not in SCOPES:
            scope["skipped"] = "unknown sub-subsection tag; contents not interpreted"
            scopes.append(scope)
            cursor = Cursor(data, scope_end, end, endian)
            continue
        inner = Cursor(data, cursor.pos, scope_end, endian)
        if scope_tag != TAG_FILE:
            indexes = []
            while True:
                index = inner.uleb128()
                if index == 0:
                    break
                budget.take("indexes", "section or symbol indexes")
                indexes.append(index)
            scope["indexes"] = indexes
        attributes = []
        while inner.remaining():
            budget.take("records", "attribute records")
            attributes.append(_parse_attribute(inner, base))
        scope["attributes"] = attributes
        scopes.append(scope)
        cursor = Cursor(data, scope_end, end, endian)
    return scopes


def parse_attributes(data: bytes, endian: str = "<", base: int = 0) -> dict:
    """Decode a complete attributes section. ``base`` is its file offset, for reporting."""
    if endian not in ("<", ">"):
        raise AttributesError("unsupported byte order")
    if not 1 <= len(data) <= MAX_ATTRIBUTES_SECTION:
        raise AttributesError("attributes section size is outside the allowed range")
    if data[0] != 0x41:
        raise AttributesError(f"unsupported attributes format version {data[0]:#04x}")
    subsections, position, budget = [], 1, Budget()
    while position < len(data):
        budget.take("subsections", "subsections")
        cursor = Cursor(data, position, len(data), endian)
        length = cursor.uint32()
        if length < 6 or length > len(data) - position:
            raise AttributesError(
                f"subsection at section offset {position:#x} has invalid length {length}")
        end = position + length
        named = Cursor(data, cursor.pos, end, endian)
        vendor = named.ntbs(MAX_VENDOR_NAME)
        entry = {"vendor": _text(vendor), "section_offset": position, "length": length}
        if vendor == b"aeabi":
            entry["scopes"] = _parse_public_subsection(data, named.pos, end, endian, base, budget)
        else:
            body = data[named.pos:end]
            entry.update(interpreted=False, data_bytes=len(body),
                         data_sha256=hashlib.sha256(body).hexdigest())
        subsections.append(entry)
        position = end
    return {"format_version": "A", "subsections": subsections}


def collect_file_scope(parsed: dict) -> dict:
    """Merge file-scope public attributes and record everything that limits conclusions."""
    values, conflicts, unknown_required, unknown_ignored, undefined_values = {}, [], [], [], []
    nested = []
    public = [s for s in parsed["subsections"] if s["vendor"] == "aeabi"]
    file_scopes = [scope for s in public for scope in s["scopes"] if scope["scope"] == "file"]
    other_scopes = [scope for s in public for scope in s["scopes"] if scope["scope"] != "file"]
    for scope in file_scopes:
        for record in scope["attributes"]:
            tag = record["tag"]
            if not record["known"]:
                (unknown_required if record["must_comprehend"] else unknown_ignored).append(
                    {"tag": tag, "section_offset": record["section_offset"]})
                continue
            if record["type"] == ULEB and not record["value_defined"]:
                undefined_values.append({"tag": tag, "name": record["name"],
                                         "value": record["value"],
                                         "section_offset": record["section_offset"]})
            if tag == 65:
                nested.append({"inner_tag": record["inner_tag"],
                               "inner_name": record.get("inner_name"),
                               "inner_value": record["inner_value"],
                               "inner_known": record["inner_known"],
                               "inner_value_defined": record.get("inner_meaning") is not None,
                               "section_offset": record["section_offset"]})
            if tag in values and values[tag]["value"] != record["value"]:
                conflicts.append({"tag": tag, "name": record["name"],
                                  "values": [values[tag]["value"], record["value"]],
                                  "section_offsets": [values[tag]["section_offset"],
                                                      record["section_offset"]]})
                continue
            values.setdefault(tag, record)
    return {
        "has_public_file_scope": bool(file_scopes),
        "values": values,
        "conflicting_tags": conflicts,
        "unknown_must_comprehend_tags": unknown_required,
        "unknown_ignorable_tags": unknown_ignored,
        "undefined_values": undefined_values,
        "also_compatible_with": nested,
        "nodefaults_in_file_scope": 64 in values,
        "non_file_scopes": [{"scope": s["scope"] or f"unknown tag {s['scope_tag']}",
                             "section_offset": s["section_offset"]} for s in other_scopes],
        "private_vendors": [s["vendor"] for s in parsed["subsections"] if s["vendor"] != "aeabi"],
    }


def describe_flags(flags: int, file_type: int) -> dict:
    """Report the Arm e_flags bits defined by the pinned AAELF32 revision."""
    version = (flags & EF_ARM_ABIMASK) >> 24
    hard, soft = bool(flags & EF_ARM_ABI_FLOAT_HARD), bool(flags & EF_ARM_ABI_FLOAT_SOFT)
    report = {"e_flags_hex": f"{flags:#010x}", "eabi_version": version,
              "be8": bool(flags & EF_ARM_BE8)}
    if version >= 5:
        other = flags & ~(EF_ARM_ABIMASK | EF_ARM_BE8 | EF_ARM_ABI_FLOAT_HARD | EF_ARM_ABI_FLOAT_SOFT)
        report["bits_not_allocated_by_pinned_spec_hex"] = f"{other:#010x}"
        report["float_bits_hex"] = f"{flags & (EF_ARM_ABI_FLOAT_HARD | EF_ARM_ABI_FLOAT_SOFT):#06x}"
        if file_type in (2, 3):
            # AAELF32 defines the two float bits for ET_EXEC and ET_DYN headers only.
            report["float_flags"] = ("conflicting" if hard and soft else "hard" if hard else
                                     "soft" if soft else "neither")
            report["float_flags_scope"] = "defined for executable file headers (ET_EXEC or ET_DYN)"
        else:
            report["float_flags"] = "not applicable"
            report["float_flags_scope"] = ("not defined for this ELF file type; the raw bits are "
                                           "reported and no calling convention is derived from them")
    else:
        report["float_flags"] = "not interpreted"
        report["legacy_gcc_bits_hex"] = f"{flags & EF_ARM_GCCMASK:#010x}"
        report["note"] = ("ABI version 4 or earlier, or unknown conformance: the low bits are "
                          "legacy producer-specific flags and are not interpreted")
    return report


def _field(collected, tag: int, usable: bool) -> dict:
    name = TAGS[tag][0]
    if not usable:
        return {"tag": tag, "name": name, "source": "unavailable", "value": None,
                "meaning": None, "defined": False}
    record = collected["values"].get(tag)
    if any(conflict["tag"] == tag for conflict in collected["conflicting_tags"]):
        return {"tag": tag, "name": name, "source": "conflicting", "value": None,
                "meaning": None, "defined": False}
    numeric = TAGS[tag][1] == ULEB
    if record is None:
        default = 0 if numeric else ""
        meaning = _meaning(tag, 0) if numeric else None
        return {"tag": tag, "name": name, "source": "default", "value": default,
                "meaning": meaning, "defined": True}
    return {"tag": tag, "name": name, "source": "explicit", "value": record["value"],
            "meaning": record.get("meaning"),
            "defined": record.get("value_defined", True) if numeric else True,
            "section_offset": record["section_offset"], "file_offset": record["file_offset"]}


def _decided(field: dict):
    """Return a value only if it is present (explicit or default) and defined by the spec."""
    if field["source"] in ("explicit", "default") and field.get("defined"):
        return field["value"]
    return None


def _origin(field: dict) -> str:
    return "omitted, default 0" if field["source"] == "default" else "explicit"


def summarize(elf: dict, flags: dict, collected, attributes_error) -> dict:
    """Derive toolchain-planning facts, keeping each ABI dimension separate."""
    usable = collected is not None and collected["has_public_file_scope"]
    limits, contradictions, notes = [], [], []
    if attributes_error:
        limits.append(f"attributes section rejected: {attributes_error}")
    elif collected is None:
        limits.append("no attributes section: the file carries no build attributes, and public "
                      "tag defaults do not apply to an unattributed file")
    elif not usable:
        limits.append("attributes section has no public file-scope attributes")
    if usable:
        for unknown in collected["unknown_must_comprehend_tags"]:
            limits.append(f"unknown tag {unknown['tag']} is in the must-comprehend range; "
                          "conclusions from this file are incomplete")
        for undefined in collected["undefined_values"]:
            limits.append(f"{undefined['name']} has value {undefined['value']}, which the pinned "
                          "specification does not define")
        for conflict in collected["conflicting_tags"]:
            contradictions.append(f"{conflict['name']} is given different values "
                                  f"{conflict['values']} in file scope")
        if collected["non_file_scopes"]:
            limits.append("section- or symbol-scope attributes are present and are not merged "
                          "into the file-scope summary")

    def field(tag):
        return _field(collected, tag, usable)

    arch, profile, cpu_name = field(6), field(7), field(5)
    arm, thumb = field(8), field(9)
    fp_arch, simd, hardfp, vfp_args = field(10), field(12), field(27), field(28)

    if usable:
        arch_value = _decided(arch)
        for item in collected["also_compatible_with"]:
            where = f"at section offset {item['section_offset']:#x}"
            if not item["inner_known"]:
                limits.append(f"Tag_also_compatible_with {where} nests unknown tag "
                              f"{item['inner_tag']}; it is not interpreted")
            elif not item["inner_value_defined"] and item["inner_tag"] != 6:
                limits.append(f"Tag_also_compatible_with {where} nests {item['inner_name']}, a use "
                              "the pinned specification reserves")
            elif not item["inner_value_defined"]:
                limits.append(f"Tag_also_compatible_with {where} nests Tag_CPU_arch value "
                              f"{item['inner_value']}, which the pinned specification does not define")
            elif (item["inner_tag"] != 6
                  or (arch_value, item["inner_value"]) not in ALSO_COMPATIBLE_DEFINED):
                limits.append(f"Tag_also_compatible_with {where} is a use the pinned specification "
                              "reserves (only v4T with v6-M and v8-A with v8-R are defined); it "
                              "is reported but not interpreted")

    float_flags = flags["float_flags"]
    float_conflicts = []
    if float_flags == "conflicting":
        float_conflicts.append("e_flags sets both EF_ARM_ABI_FLOAT_HARD and EF_ARM_ABI_FLOAT_SOFT")
    args_value, fp_value = _decided(vfp_args), _decided(fp_arch)
    if args_value == 0 and float_flags == "hard":
        float_conflicts.append("e_flags claims the hardware floating-point procedure-call "
                              f"standard but Tag_ABI_VFP_args ({_origin(vfp_args)}) is the base "
                              "variant")
    if args_value == 1 and float_flags == "soft":
        float_conflicts.append("e_flags claims the software floating-point procedure-call "
                              "standard but Tag_ABI_VFP_args is the VFP variant")
    # The specification keeps argument passing and instruction permission independent, so the
    # following pairs are reported as declarations to check, not as contradictions.
    if args_value == 1 and fp_value == 0:
        notes.append("Tag_ABI_VFP_args declares the VFP variant while Tag_FP_arch "
                     f"({_origin(fp_arch)}) permits no FP hardware instructions; the "
                     "specification does not prohibit this combination")
    if _decided(hardfp) == 1 and fp_value == 0:
        notes.append("Tag_ABI_HardFP_use selects the single-precision variant derived from "
                     f"Tag_FP_arch, while Tag_FP_arch ({_origin(fp_arch)}) permits no FP "
                     "hardware instructions")
    entry = int(elf["entry_hex"], 16)
    if entry:
        entry_isa = "thumb" if entry & 1 else "arm" if entry & 3 == 0 else "reserved"
        if entry_isa == "reserved":
            contradictions.append("e_entry has the reserved bit[1:0] = 0b10 combination")
        # An omitted tag is identical to value 0, so explicit and defaulted zeros are treated alike.
        if entry_isa == "thumb" and _decided(thumb) == 0:
            contradictions.append("e_entry marks a Thumb entry point but Tag_THUMB_ISA_use "
                                  f"({_origin(thumb)}) does not permit Thumb")
        if entry_isa == "arm" and _decided(arm) == 0:
            contradictions.append("e_entry marks an Arm entry point but Tag_ARM_ISA_use "
                                  f"({_origin(arm)}) does not permit Arm instructions")
    else:
        entry_isa = "no entry point"

    contradictions.extend(float_conflicts)
    basis = []
    present = vfp_args["source"] in ("explicit", "default")
    if float_conflicts or vfp_args["source"] == "conflicting":
        convention = "contradictory"
    elif present and args_value is None:
        convention = "undetermined"
        basis.append(f"Tag_ABI_VFP_args = {vfp_args['value']} is not defined by the pinned "
                     "specification")
    elif args_value is None:
        if float_flags == "hard":
            convention, basis = "vfp", ["e_flags EF_ARM_ABI_FLOAT_HARD only; no usable attribute"]
        elif float_flags == "soft":
            convention, basis = "base", ["e_flags EF_ARM_ABI_FLOAT_SOFT only; no usable attribute"]
        else:
            convention = "undetermined"
            basis = ["no usable Tag_ABI_VFP_args and no applicable explicit e_flags float bit"]
    else:
        convention = {0: "base", 1: "vfp", 2: "toolchain-specific", 3: "compatible-with-both"}[
            args_value]
        basis.append(f"Tag_ABI_VFP_args = {args_value} ({vfp_args['source']})")
        if float_flags in ("hard", "soft"):
            basis.append(f"e_flags float bit: {float_flags}")
    if float_flags == "neither":
        basis.append("both e_flags float bits clear: the pinned AAELF32 text implies the base "
                     "standard, but the bits were only added in AAELF32 revision E (2012), so a "
                     "producer older than that could not set them; weak evidence on its own")
    elif float_flags == "not applicable":
        basis.append("e_flags float bits are not defined for this ELF file type and were not used")

    if fp_value is None:
        fp_use = "undetermined"
    elif fp_value == 0:
        fp_use = "no FP hardware instructions permitted"
    else:
        fp_use = "FP hardware instructions permitted"
    return {
        "eabi_version": flags["eabi_version"],
        "byte_order": elf["byte_order"],
        "be8": flags["be8"],
        "cpu_arch": arch, "cpu_arch_profile": profile, "cpu_name": cpu_name,
        "arm_isa_use": arm, "thumb_isa_use": thumb, "entry_point_isa": entry_isa,
        "fp_arch": fp_arch, "advanced_simd_arch": simd, "hardfp_use": hardfp,
        "fp_instruction_use": fp_use,
        "vfp_args": vfp_args,
        "e_flags_float": float_flags,
        "float_calling_convention": convention,
        "float_calling_convention_basis": basis,
        "wchar_t": field(18), "enum_size": field(26),
        "align_needed": field(24), "align_preserved": field(25),
        "conformance": field(67),
        "contradictions": contradictions,
        "notes": notes,
        "limits": limits,
        "complete": usable and not limits and not contradictions,
        "default_rule": DEFAULT_RULE if usable else None,
    }


def _section_name(names, offset: int):
    if names is None or not 0 <= offset < len(names):
        return None
    end = names.find(b"\0", offset, min(len(names), offset + 256))
    return None if end < 0 else _text(names[offset:end])


def locate_attributes(stream, size: int) -> dict:
    """Find the attributes section through the section header table, with explicit bounds."""
    reader = elf_inventory.ElfReader(stream, size)
    ident = reader.read(0, 16)
    endian = {1: "<", 2: ">"}[ident[5]]
    shoff, _flags, _ehsize, _phentsize, _phnum, shentsize, shnum, shstrndx = reader.unpack(
        endian + "IIHHHHHH", 32)
    if shoff == 0:
        return {"status": "absent", "reason": "the file has no section header table"}
    if shnum == 0 or shstrndx == SHN_XINDEX:
        return {"status": "unsupported", "reason": "extended section numbering is not supported"}
    if shentsize != 40:
        return {"status": "unsupported", "reason": f"unexpected section header size {shentsize}"}
    if shnum > MAX_SECTIONS:
        return {"status": "unsupported", "reason": f"section count {shnum} exceeds {MAX_SECTIONS}"}
    if shoff > size or shnum * 40 > size - shoff:
        raise ValueError("ELF section header table exceeds file bounds")
    headers = []
    for index in range(shnum):
        name, kind, _f, _addr, offset, length, _link, _info, _align, _entsize = reader.unpack(
            endian + "10I", shoff + 40 * index)
        headers.append({"index": index, "name_offset": name, "type": kind,
                        "offset": offset, "size": length})
    names = None
    if 0 < shstrndx < shnum and headers[shstrndx]["type"] == SHT_STRTAB:
        table = headers[shstrndx]
        if (0 < table["size"] <= MAX_SECTION_NAMES and table["offset"] <= size
                and table["size"] <= size - table["offset"]):
            names = reader.read(table["offset"], table["size"])
    for header in headers:
        header["name"] = _section_name(names, header["name_offset"])
    typed = [h for h in headers if h["type"] == SHT_ARM_ATTRIBUTES]
    misnamed = [h["index"] for h in headers
                if h["name"] == ATTRIBUTES_NAME and h["type"] != SHT_ARM_ATTRIBUTES]
    if len(typed) > 1:
        return {"status": "unsupported", "section_count": shnum,
                "reason": "more than one SHT_ARM_ATTRIBUTES section",
                "candidates": [h["index"] for h in typed]}
    if not typed:
        result = {"status": "absent", "section_count": shnum,
                  "reason": "no section of type SHT_ARM_ATTRIBUTES"}
        if misnamed:
            result["sections_named_like_attributes_with_other_type"] = misnamed
        return result
    header = typed[0]
    if not 1 <= header["size"] <= MAX_ATTRIBUTES_SECTION:
        return {"status": "unsupported", "section_count": shnum, "section_index": header["index"],
                "reason": f"attributes section size {header['size']} is outside the allowed range"}
    if header["offset"] > size or header["size"] > size - header["offset"]:
        raise ValueError("ELF attributes section exceeds file bounds")
    data = reader.read(header["offset"], header["size"])
    return {"status": "found", "section_count": shnum, "section_index": header["index"],
            "section_name": header["name"],
            "name_matches_spec": header["name"] == ATTRIBUTES_NAME if header["name"] else None,
            "file_offset": header["offset"], "size": header["size"],
            "sha256": hashlib.sha256(data).hexdigest(), "endian": endian, "data": data}


def inspect_stream(stream, size: int) -> dict:
    elf = elf_inventory.inspect_stream(stream, size)
    if elf["bits"] != 32 or elf["machine_id"] != EM_ARM:
        return {"status": "unsupported", "elf": elf,
                "reason": "only 32-bit EM_ARM ELF files carry AArch32 build attributes"}
    flags = describe_flags(int(elf["flags_hex"], 16), elf["elf_type"])
    location = locate_attributes(stream, size)
    data = location.pop("data", None)
    endian = location.pop("endian", "<")
    parsed, collected, error = None, None, None
    if location["status"] == "found":
        try:
            parsed = parse_attributes(data, endian, location["file_offset"])
            collected = collect_file_scope(parsed)
        except AttributesError as failure:
            error = str(failure)
    elif location["status"] == "unsupported":
        error = location["reason"]
    summary = summarize(elf, flags, collected, error)
    status = "error" if error else "ok" if summary["complete"] else "limited"
    report = {"status": status, "elf": elf, "e_flags": flags, "attributes_section": location,
              "attributes": parsed, "summary": summary}
    if collected is not None:
        report["file_scope"] = {key: value for key, value in collected.items() if key != "values"}
    if error:
        report["attributes_error"] = error
    return report


def inspect_file(path: Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Only regular files are supported")
        report = inspect_stream(stream, before.st_size)
        stream.seek(0)
        digest, consumed = hashlib.sha256(), 0
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path, help="ARM ELF files to inspect statically")
    parser.add_argument("--output", type=Path,
                        help="write the JSON report to a new file; an existing file is refused")
    args = parser.parse_args(argv)
    if len(args.paths) > 256:
        parser.error("at most 256 files per run")
    files, failed = [], False
    for path in args.paths:
        try:
            files.append(inspect_file(path))
        except (OSError, ValueError, struct.error, KeyError) as error:
            failed = True
            files.append({"path": str(path), "status": "error", "error": str(error)})
    report = {"tool": "tools.arm_attributes", "spec": SPEC, "files": files}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        try:
            with open(args.output, "x", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError as error:
            print(json.dumps({"status": "error", "error": f"cannot create output: {error}"}))
            return 2
    else:
        print(text)
    if failed or any(entry["status"] == "error" for entry in files):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
