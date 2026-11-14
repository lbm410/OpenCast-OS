"""Synthetic tests for the bounded ARM build-attributes reader. No firmware is used or executed."""

import contextlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from tools import arm_attributes as aa

ATTR_TYPE = aa.SHT_ARM_ATTRIBUTES


def uleb(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def attr(tag, value):
    """Encode one attribute; integers become ULEB128, strings NUL-terminated bytes."""
    if isinstance(value, int):
        return uleb(tag) + uleb(value)
    return uleb(tag) + value.encode() + b"\0"


def scope(tag, body, endian="<", size=None):
    total = 5 + len(body) if size is None else size
    return bytes([tag]) + struct.pack(endian + "I", total) + body


def subsection(vendor, body, endian="<", length=None):
    name = vendor.encode() + b"\0"
    total = 4 + len(name) + len(body) if length is None else length
    return struct.pack(endian + "I", total) + name + body


def section(*attributes, endian="<"):
    return b"A" + subsection("aeabi", scope(1, b"".join(attributes), endian), endian)


def make_elf(attributes=None, *, flags=0x05000000, entry=0, endian="<", machine=40,
             file_type=2, attr_type=ATTR_TYPE, attr_name=b".ARM.attributes",
             extra_attr_sections=0, shentsize=40, shnum=None, attr_size=None,
             attr_offset=None, with_sections=True):
    """Build a minimal ELF32 file: header, optional attribute sections and a name table."""
    names = b"\0" + attr_name + b"\0.shstrtab\0"
    attr_name_off, strtab_name_off = 1, 1 + len(attr_name) + 1
    payloads, headers = [], [(0, 0, 0, 0)]
    cursor = 52
    if attributes is not None:
        for _ in range(1 + extra_attr_sections):
            offset = cursor if attr_offset is None else attr_offset
            size = len(attributes) if attr_size is None else attr_size
            headers.append((attr_name_off, attr_type, offset, size))
            payloads.append(attributes)
            cursor += len(attributes)
    headers.append((strtab_name_off, 3, cursor, len(names)))
    payloads.append(names)
    cursor += len(names)
    shoff = cursor if with_sections else 0
    count = len(headers) if shnum is None else shnum
    header = b"\x7fELF" + bytes([1, 1 if endian == "<" else 2, 1, 0]) + bytes(8)
    header += struct.pack(endian + "HHIIIIIHHHHHH", file_type, machine, 1, entry, 0, shoff,
                          flags, 52, 32, 0, shentsize, count if with_sections else 0,
                          len(headers) - 1 if with_sections else 0)
    table = b"".join(struct.pack(endian + "10I", name, kind, 0, 0, offset, size, 0, 0, 1, 0)
                     for name, kind, offset, size in headers)
    return header + b"".join(payloads) + (table if with_sections else b"")


def inspect(blob):
    return aa.inspect_stream(io.BytesIO(blob), len(blob))


SOFTFP = (attr(5, "7-A"), attr(6, 10), attr(7, 0x41), attr(8, 1), attr(9, 2), attr(10, 3),
          attr(12, 1), attr(18, 4), attr(26, 2))


class ParsingTests(unittest.TestCase):
    def test_softfp_file_separates_fp_instructions_from_calling_convention(self):
        report = inspect(make_elf(section(*SOFTFP), entry=0x8000))
        summary = report["summary"]
        self.assertEqual(report["status"], "ok")
        self.assertEqual(summary["cpu_arch"]["meaning"], "Arm v7")
        self.assertEqual(summary["cpu_arch_profile"]["value"], 0x41)
        self.assertEqual(summary["cpu_name"]["value"], "7-A")
        self.assertEqual(summary["fp_arch"]["source"], "explicit")
        self.assertEqual(summary["fp_instruction_use"], "FP hardware instructions permitted")
        self.assertEqual(summary["vfp_args"]["source"], "default")
        self.assertEqual(summary["float_calling_convention"], "base")
        self.assertEqual(summary["entry_point_isa"], "arm")
        self.assertEqual(summary["contradictions"], [])
        self.assertTrue(summary["complete"])

    def test_offsets_are_reported_relative_to_section_and_file(self):
        blob = make_elf(section(*SOFTFP))
        report = inspect(blob)
        location = report["attributes_section"]
        self.assertEqual(location["file_offset"], 52)
        self.assertTrue(location["name_matches_spec"])
        first = report["attributes"]["subsections"][0]["scopes"][0]["attributes"][0]
        self.assertEqual(first["section_offset"], 16)
        self.assertEqual(first["file_offset"], 52 + 16)
        self.assertEqual(blob[first["file_offset"]], 5)

    def test_big_endian_lengths_follow_elf_byte_order(self):
        report = inspect(make_elf(section(attr(6, 4), endian=">"), endian=">"))
        self.assertEqual(report["summary"]["cpu_arch"]["meaning"], "Arm v5TE")
        self.assertEqual(report["summary"]["byte_order"], "big")

    def test_hard_float_agreement_between_flags_and_attributes(self):
        report = inspect(make_elf(section(attr(10, 3), attr(28, 1)), flags=0x05000400))
        self.assertEqual(report["summary"]["float_calling_convention"], "vfp")
        self.assertEqual(report["summary"]["contradictions"], [])

    def test_vfp_args_value_three_is_compatible_with_both(self):
        report = inspect(make_elf(section(attr(28, 3))))
        self.assertEqual(report["summary"]["float_calling_convention"], "compatible-with-both")

    def test_toolchain_specific_convention_is_not_mapped_to_a_standard(self):
        report = inspect(make_elf(section(attr(10, 2), attr(28, 2))))
        self.assertEqual(report["summary"]["float_calling_convention"], "toolchain-specific")

    def test_string_compatibility_conformance_and_nested_tags(self):
        body = (attr(67, "2.09") + uleb(32) + uleb(1) + b"gnu\0"
                + uleb(65) + uleb(6) + uleb(11) + b"\0" + attr(64, 0) + attr(6, 2))
        report = inspect(make_elf(section(body)))
        records = report["attributes"]["subsections"][0]["scopes"][0]["attributes"]
        by_tag = {record["tag"]: record for record in records}
        self.assertEqual(by_tag[67]["value"], "2.09")
        self.assertEqual(by_tag[32]["value"], {"flag": 1, "vendor": "gnu"})
        self.assertEqual(by_tag[65]["inner_name"], "Tag_CPU_arch")
        self.assertEqual(by_tag[65]["inner_meaning"], "Arm v6-M")
        self.assertTrue(report["file_scope"]["nodefaults_in_file_scope"])
        self.assertEqual(report["summary"]["conformance"]["value"], "2.09")

    def test_nested_zero_value_is_not_confused_with_terminator(self):
        body = uleb(65) + uleb(6) + uleb(0) + b"\0" + attr(6, 10)
        report = inspect(make_elf(section(body)))
        records = report["attributes"]["subsections"][0]["scopes"][0]["attributes"]
        self.assertEqual(records[0]["inner_value"], 0)
        self.assertEqual(records[1]["value"], 10)

    def test_private_vendor_subsection_is_reported_not_interpreted(self):
        data = b"A" + subsection("acme", b"\x01\x02\x03") + subsection(
            "aeabi", scope(1, attr(6, 10)))
        report = inspect(make_elf(data))
        self.assertEqual(report["file_scope"]["private_vendors"], ["acme"])
        private = report["attributes"]["subsections"][0]
        self.assertFalse(private["interpreted"])
        self.assertEqual(private["data_bytes"], 3)
        self.assertEqual(report["summary"]["cpu_arch"]["value"], 10)

    def test_section_and_symbol_scopes_are_not_merged_into_file_scope(self):
        scoped = scope(2, uleb(4) + uleb(7) + b"\0" + attr(6, 4))
        data = b"A" + subsection("aeabi", scope(1, attr(6, 10)) + scoped)
        report = inspect(make_elf(data))
        scopes = report["attributes"]["subsections"][0]["scopes"]
        self.assertEqual(scopes[1]["indexes"], [4, 7])
        self.assertEqual(report["summary"]["cpu_arch"]["value"], 10)
        self.assertEqual(report["status"], "limited")
        self.assertTrue(any("not merged" in text for text in report["summary"]["limits"]))

    def test_unknown_scope_tag_is_skipped_by_its_declared_size(self):
        data = b"A" + subsection("aeabi", scope(9, b"\xff\xff") + scope(1, attr(6, 10)))
        report = inspect(make_elf(data))
        scopes = report["attributes"]["subsections"][0]["scopes"]
        self.assertIn("skipped", scopes[0])
        self.assertEqual(report["summary"]["cpu_arch"]["value"], 10)
        self.assertEqual(report["status"], "limited")


class UnknownAndDefaultTests(unittest.TestCase):
    def test_unknown_ignorable_tags_are_skipped_by_parity(self):
        body = attr(78, 5) + attr(79, "opaque") + attr(200, 1) + attr(6, 10)
        report = inspect(make_elf(section(body)))
        ignored = [entry["tag"] for entry in report["file_scope"]["unknown_ignorable_tags"]]
        self.assertEqual(ignored, [78, 79, 200])
        self.assertEqual(report["summary"]["cpu_arch"]["value"], 10)
        self.assertEqual(report["status"], "ok")

    def test_unknown_must_comprehend_tag_limits_conclusions(self):
        report = inspect(make_elf(section(attr(54, 1), attr(6, 10))))
        required = report["file_scope"]["unknown_must_comprehend_tags"]
        self.assertEqual([entry["tag"] for entry in required], [54])
        self.assertEqual(report["status"], "limited")
        self.assertFalse(report["summary"]["complete"])

    def test_high_tag_takes_properties_of_tag_modulo_128(self):
        report = inspect(make_elf(section(attr(128 + 40, 1))))
        required = report["file_scope"]["unknown_must_comprehend_tags"]
        self.assertEqual([entry["tag"] for entry in required], [168])

    def test_undefined_value_of_known_tag_is_not_given_a_meaning(self):
        report = inspect(make_elf(section(attr(6, 99))))
        self.assertIsNone(report["summary"]["cpu_arch"]["meaning"])
        self.assertEqual(report["file_scope"]["undefined_values"][0]["value"], 99)
        self.assertEqual(report["status"], "limited")

    def test_omitted_tags_default_to_zero_only_when_public_scope_exists(self):
        present = inspect(make_elf(section(attr(6, 10))))["summary"]
        self.assertEqual(present["fp_arch"]["source"], "default")
        self.assertEqual(present["fp_arch"]["value"], 0)
        self.assertEqual(present["cpu_name"]["value"], "")
        self.assertIsNotNone(present["default_rule"])
        absent = inspect(make_elf(None))["summary"]
        self.assertEqual(absent["fp_arch"]["source"], "unavailable")
        self.assertIsNone(absent["default_rule"])

    def test_unspecified_flags_without_attributes_are_not_proof_of_soft_float(self):
        report = inspect(make_elf(None, flags=0x05000002))
        summary = report["summary"]
        self.assertEqual(report["attributes_section"]["status"], "absent")
        self.assertEqual(summary["e_flags_float"], "neither")
        self.assertEqual(summary["float_calling_convention"], "undetermined")
        self.assertEqual(report["e_flags"]["bits_not_allocated_by_pinned_spec_hex"], "0x00000002")
        self.assertEqual(report["status"], "limited")

    def test_explicit_flag_alone_is_reported_with_its_basis(self):
        summary = inspect(make_elf(None, flags=0x05000200))["summary"]
        self.assertEqual(summary["float_calling_convention"], "base")
        self.assertIn("EF_ARM_ABI_FLOAT_SOFT", summary["float_calling_convention_basis"][0])

    def test_pre_v5_flags_are_not_interpreted_as_float_abi(self):
        report = inspect(make_elf(None, flags=0x04000400))
        self.assertEqual(report["e_flags"]["float_flags"], "not interpreted")
        self.assertEqual(report["summary"]["float_calling_convention"], "undetermined")

    def test_aligned_extended_values_keep_parameter_without_inventing_bytes(self):
        report = inspect(make_elf(section(attr(24, 5))))
        self.assertIn("n=5", report["summary"]["align_needed"]["meaning"])


class ContradictionTests(unittest.TestCase):
    def assert_contradictory(self, report, fragment):
        summary = report["summary"]
        self.assertEqual(summary["float_calling_convention"], "contradictory")
        self.assertTrue(any(fragment in text for text in summary["contradictions"]),
                        summary["contradictions"])
        self.assertEqual(report["status"], "limited")

    def test_hard_flag_against_base_attribute(self):
        self.assert_contradictory(inspect(make_elf(section(attr(10, 3)), flags=0x05000400)),
                                  "hardware floating-point")

    def test_soft_flag_against_vfp_attribute(self):
        self.assert_contradictory(
            inspect(make_elf(section(attr(10, 3), attr(28, 1)), flags=0x05000200)),
            "software floating-point")

    def test_both_float_flags_set(self):
        self.assert_contradictory(inspect(make_elf(section(attr(6, 10)), flags=0x05000600)),
                                  "both EF_ARM_ABI_FLOAT_HARD")

    def test_vfp_convention_without_fp_hardware_is_two_declarations_not_a_contradiction(self):
        # Review issue 6: argument convention and instruction permission are independent.
        for attributes in (section(attr(28, 1)), section(attr(28, 1), attr(10, 0))):
            with self.subTest(attributes=attributes):
                report = inspect(make_elf(attributes))
                summary = report["summary"]
                self.assertEqual(summary["float_calling_convention"], "vfp")
                self.assertEqual(summary["contradictions"], [])
                self.assertTrue(any("does not prohibit" in text for text in summary["notes"]))
                self.assertEqual(summary["fp_instruction_use"],
                                 "no FP hardware instructions permitted")
                self.assertEqual(report["status"], "ok")

    def test_single_precision_selection_without_fp_hardware_is_a_note(self):
        summary = inspect(make_elf(section(attr(27, 1))))["summary"]
        self.assertEqual(summary["contradictions"], [])
        self.assertTrue(any("single-precision" in text for text in summary["notes"]))

    def test_same_tag_with_two_values_is_not_resolved(self):
        report = inspect(make_elf(section(attr(28, 0), attr(28, 1), attr(10, 3))))
        self.assertEqual(report["summary"]["vfp_args"]["source"], "conflicting")
        self.assertEqual(report["summary"]["float_calling_convention"], "contradictory")
        self.assertEqual(report["file_scope"]["conflicting_tags"][0]["values"], [0, 1])

    def test_repeated_identical_value_is_accepted(self):
        report = inspect(make_elf(section(attr(6, 10), attr(6, 10))))
        self.assertEqual(report["status"], "ok")

    def test_entry_point_instruction_set_against_isa_tags(self):
        thumb = inspect(make_elf(section(attr(8, 1), attr(9, 0)), entry=0x8001))["summary"]
        self.assertEqual(thumb["entry_point_isa"], "thumb")
        self.assertTrue(any("Thumb entry point" in text for text in thumb["contradictions"]))
        arm = inspect(make_elf(section(attr(8, 0), attr(9, 3)), entry=0x8000))["summary"]
        self.assertTrue(any("Arm entry point" in text for text in arm["contradictions"]))

    def test_omitted_isa_tag_is_treated_exactly_like_explicit_zero(self):
        # Review issue 4: omission in file scope is identical to value 0.
        explicit = inspect(make_elf(section(attr(8, 0), attr(9, 3)), entry=0x8000))
        omitted = inspect(make_elf(section(attr(9, 3)), entry=0x8000))
        for report, origin in ((explicit, "explicit"), (omitted, "omitted, default 0")):
            texts = report["summary"]["contradictions"]
            self.assertEqual(len(texts), 1, texts)
            self.assertIn("Arm entry point", texts[0])
            self.assertIn(origin, texts[0])
            self.assertEqual(report["status"], "limited")
        thumb = inspect(make_elf(section(attr(8, 1)), entry=0x8001))["summary"]
        self.assertTrue(any("Thumb entry point" in text and "omitted" in text
                            for text in thumb["contradictions"]))

    def test_entry_point_is_not_weighed_when_attributes_are_missing_entirely(self):
        summary = inspect(make_elf(None, entry=0x8000))["summary"]
        self.assertEqual(summary["entry_point_isa"], "arm")
        self.assertEqual(summary["contradictions"], [])
        self.assertEqual(summary["arm_isa_use"]["source"], "unavailable")

    def test_file_without_entry_point_has_no_entry_contradiction(self):
        summary = inspect(make_elf(section(attr(6, 10))))["summary"]
        self.assertEqual(summary["entry_point_isa"], "no entry point")
        self.assertEqual(summary["contradictions"], [])
        reserved = inspect(make_elf(section(attr(8, 1)), entry=0x8002))["summary"]
        self.assertTrue(any("reserved" in text for text in reserved["contradictions"]))


class MalformedSectionTests(unittest.TestCase):
    def assert_rejected(self, data, fragment):
        report = inspect(make_elf(data))
        self.assertEqual(report["status"], "error")
        self.assertIn(fragment, report["attributes_error"])
        summary = report["summary"]
        self.assertEqual(summary["cpu_arch"]["source"], "unavailable")
        self.assertEqual(summary["float_calling_convention"], "undetermined")
        self.assertIsNone(report["attributes"])

    def test_unsupported_format_version(self):
        self.assert_rejected(b"B" + section(attr(6, 10))[1:], "format version")

    def test_subsection_length_beyond_section(self):
        self.assert_rejected(b"A" + subsection("aeabi", scope(1, attr(6, 10)), length=4096),
                             "invalid length")

    def test_subsection_length_too_small(self):
        self.assert_rejected(b"A" + struct.pack("<I", 3) + b"aeabi\0", "invalid length")

    def test_truncated_subsection_length(self):
        self.assert_rejected(b"A\x10\x00", "truncated 32-bit length")

    def test_unterminated_vendor_name(self):
        self.assert_rejected(b"A" + struct.pack("<I", 4 + 6) + b"aeabix", "unterminated")

    def test_overlong_vendor_name(self):
        name = b"v" * (aa.MAX_VENDOR_NAME + 1) + b"\0"
        self.assert_rejected(b"A" + struct.pack("<I", 4 + len(name)) + name, "unterminated")

    def test_scope_size_beyond_subsection(self):
        self.assert_rejected(b"A" + subsection("aeabi", scope(1, attr(6, 10), size=64)),
                             "invalid size")

    def test_scope_size_too_small(self):
        self.assert_rejected(b"A" + subsection("aeabi", scope(1, b"", size=4)), "invalid size")

    def test_truncated_uleb128_value(self):
        self.assert_rejected(section(uleb(6) + b"\x80"), "truncated data")

    def test_overlong_uleb128(self):
        self.assert_rejected(section(uleb(6) + b"\x80" * 5 + b"\x00"), "exceeds 5 bytes")

    def test_uleb128_wider_than_32_bits(self):
        self.assert_rejected(section(uleb(6) + b"\xff\xff\xff\xff\x7f"), "exceeds 32 bits")

    def test_unterminated_string_value(self):
        self.assert_rejected(section(uleb(5) + b"7-A"), "unterminated")

    def test_string_longer_than_limit(self):
        self.assert_rejected(section(uleb(5) + b"x" * (aa.MAX_NTBS + 1) + b"\0"), "unterminated")

    def test_scope_tags_are_not_valid_attributes(self):
        for tag in (0, 1, 2, 3):
            with self.subTest(tag=tag):
                self.assert_rejected(section(uleb(tag) + uleb(0)), "not a valid attribute tag")

    def test_nested_numeric_value_without_terminator(self):
        self.assert_rejected(section(uleb(65) + uleb(6) + uleb(11) + uleb(1)), "NUL terminator")

    def test_unterminated_index_list(self):
        self.assert_rejected(b"A" + subsection("aeabi", scope(2, uleb(4) + uleb(7))),
                             "truncated data")

    def test_too_many_attribute_records(self):
        body = attr(6, 10) * (aa.MAX_RECORDS + 1)
        self.assert_rejected(section(body), "too many attribute records")

    def test_record_budget_is_total_across_subsections(self):
        # Review issue 3: two public subsections must share one budget.
        half = scope(1, attr(6, 10) * aa.MAX_RECORDS)
        data = b"A" + subsection("aeabi", half) + subsection("aeabi", scope(1, attr(6, 10)))
        self.assert_rejected(data, "too many attribute records")
        exact = b"A" + subsection("aeabi", scope(1, attr(6, 10) * (aa.MAX_RECORDS - 1))
                                  ) + subsection("aeabi", scope(1, attr(6, 10)))
        self.assertEqual(inspect(make_elf(exact))["status"], "ok")

    def test_record_budget_is_total_across_sub_subsections(self):
        scopes = scope(1, attr(6, 10) * aa.MAX_RECORDS) + scope(1, attr(6, 10))
        self.assert_rejected(b"A" + subsection("aeabi", scopes), "too many attribute records")

    def test_subsection_count_limit(self):
        data = b"A" + subsection("acme", b"") * (aa.MAX_SUBSECTIONS + 1)
        self.assert_rejected(data, "too many subsections")

    def test_sub_subsection_count_limit_is_total(self):
        many = scope(1, b"") * aa.MAX_SCOPES
        data = b"A" + subsection("aeabi", many) + subsection("aeabi", scope(1, b""))
        self.assert_rejected(data, "too many sub-subsections")

    def test_index_budget_is_total_across_scopes(self):
        half = scope(2, uleb(1) * aa.MAX_INDEXES + b"\0")
        data = b"A" + subsection("aeabi", half + scope(3, uleb(1) + b"\0"))
        self.assert_rejected(data, "too many section or symbol indexes")

    def test_parse_attributes_rejects_empty_and_oversized_input(self):
        with self.assertRaises(aa.AttributesError):
            aa.parse_attributes(b"")
        with self.assertRaises(aa.AttributesError):
            aa.parse_attributes(b"A" + bytes(aa.MAX_ATTRIBUTES_SECTION))
        with self.assertRaises(aa.AttributesError):
            aa.parse_attributes(b"A", endian="=")


class ReviewRegressionTests(unittest.TestCase):
    """Targeted regressions for the integration review of the first version."""

    def test_relocatable_file_float_flags_do_not_decide_the_convention(self):
        # Review issue 1: the float bits are defined for ET_EXEC and ET_DYN headers only.
        for flags, bits in ((0x05000400, "0x0400"), (0x05000200, "0x0200"), (0x05000600, "0x0600")):
            with self.subTest(flags=flags):
                report = inspect(make_elf(None, flags=flags, file_type=1))
                self.assertEqual(report["e_flags"]["float_flags"], "not applicable")
                self.assertEqual(report["e_flags"]["float_bits_hex"], bits)
                summary = report["summary"]
                self.assertEqual(summary["float_calling_convention"], "undetermined")
                self.assertEqual(summary["contradictions"], [])

    def test_relocatable_file_flags_do_not_contradict_its_attributes(self):
        report = inspect(make_elf(section(attr(6, 10)), flags=0x05000400, file_type=1))
        summary = report["summary"]
        self.assertEqual(summary["float_calling_convention"], "base")
        self.assertEqual(summary["contradictions"], [])
        self.assertTrue(any("not defined for this ELF file type" in text
                            for text in summary["float_calling_convention_basis"]))

    def test_shared_object_float_flags_are_interpreted(self):
        report = inspect(make_elf(section(attr(10, 3), attr(28, 1)), flags=0x05000400, file_type=3))
        self.assertEqual(report["e_flags"]["float_flags"], "hard")
        self.assertEqual(report["summary"]["float_calling_convention"], "vfp")

    def test_undefined_fp_arch_value_establishes_no_hardware_requirement(self):
        # Review issue 2.
        report = inspect(make_elf(section(attr(10, 99))))
        summary = report["summary"]
        self.assertEqual(summary["fp_instruction_use"], "undetermined")
        self.assertFalse(summary["fp_arch"]["defined"])
        self.assertIsNone(summary["fp_arch"]["meaning"])
        self.assertEqual(report["status"], "limited")
        self.assertEqual(summary["notes"], [])

    def test_undefined_vfp_args_value_leaves_convention_undetermined(self):
        report = inspect(make_elf(section(attr(28, 7)), flags=0x05000400))
        summary = report["summary"]
        self.assertEqual(summary["float_calling_convention"], "undetermined")
        self.assertEqual(summary["contradictions"], [])
        self.assertEqual(report["status"], "limited")

    def test_undefined_isa_value_is_not_weighed_against_entry_point(self):
        summary = inspect(make_elf(section(attr(8, 9)), entry=0x8000))["summary"]
        self.assertEqual(summary["contradictions"], [])
        self.assertTrue(any("does not define" in text for text in summary["limits"]))

    def also(self, arch, inner_tag, inner_value):
        body = attr(6, arch) + uleb(65) + uleb(inner_tag) + uleb(inner_value) + b"\0"
        return inspect(make_elf(section(body)))

    def test_defined_also_compatible_pairs_are_accepted(self):
        for arch, inner in ((2, 11), (11, 2), (14, 15), (15, 14)):
            with self.subTest(arch=arch, inner=inner):
                report = self.also(arch, 6, inner)
                self.assertEqual(report["status"], "ok", report["summary"]["limits"])

    def test_unknown_nested_architecture_value_is_surfaced(self):
        # Review issue 5.
        report = self.also(2, 6, 99)
        self.assertEqual(report["status"], "limited")
        self.assertTrue(any("does not define" in text for text in report["summary"]["limits"]))
        self.assertFalse(report["file_scope"]["also_compatible_with"][0]["inner_value_defined"])

    def test_reserved_also_compatible_combinations_are_not_claimed_as_interpreted(self):
        for report in (self.also(10, 6, 11), self.also(2, 6, 4), self.also(2, 10, 3)):
            self.assertEqual(report["status"], "limited")
            self.assertTrue(any("reserves" in text for text in report["summary"]["limits"]),
                            report["summary"]["limits"])

    def test_unknown_nested_tag_is_surfaced(self):
        body = attr(6, 2) + uleb(65) + uleb(90) + uleb(1) + b"\0"
        report = inspect(make_elf(section(body)))
        self.assertEqual(report["status"], "limited")
        self.assertTrue(any("unknown tag 90" in text for text in report["summary"]["limits"]))


class ElfBoundsTests(unittest.TestCase):
    def test_file_without_section_headers(self):
        report = inspect(make_elf(section(attr(6, 10)), with_sections=False))
        self.assertEqual(report["attributes_section"]["status"], "absent")
        self.assertEqual(report["summary"]["cpu_arch"]["source"], "unavailable")

    def test_section_data_beyond_file_is_rejected(self):
        blob = make_elf(section(attr(6, 10)), attr_offset=10**6)
        with self.assertRaisesRegex(ValueError, "exceeds file bounds"):
            inspect(blob)

    def test_section_header_table_beyond_file_is_rejected(self):
        blob = make_elf(section(attr(6, 10)), shnum=400)
        with self.assertRaisesRegex(ValueError, "exceeds file bounds"):
            inspect(blob)

    def test_oversized_attributes_section_is_unsupported(self):
        report = inspect(make_elf(section(attr(6, 10)), attr_size=aa.MAX_ATTRIBUTES_SECTION + 1))
        self.assertEqual(report["status"], "error")
        self.assertIn("outside the allowed range", report["attributes_error"])

    def test_unexpected_section_header_size_is_unsupported(self):
        report = inspect(make_elf(section(attr(6, 10)), shentsize=48))
        self.assertEqual(report["attributes_section"]["status"], "unsupported")
        self.assertEqual(report["status"], "error")

    def test_section_count_limit(self):
        report = inspect(make_elf(section(attr(6, 10)), shnum=aa.MAX_SECTIONS + 1))
        self.assertIn("exceeds", report["attributes_error"])

    def test_multiple_attribute_sections_are_unsupported(self):
        report = inspect(make_elf(section(attr(6, 10)), extra_attr_sections=1))
        self.assertIn("more than one", report["attributes_error"])
        self.assertEqual(report["summary"]["cpu_arch"]["source"], "unavailable")

    def test_named_section_with_wrong_type_is_not_parsed(self):
        report = inspect(make_elf(section(attr(6, 10)), attr_type=1))
        location = report["attributes_section"]
        self.assertEqual(location["status"], "absent")
        self.assertEqual(location["sections_named_like_attributes_with_other_type"], [1])

    def test_typed_section_with_unexpected_name_is_flagged(self):
        report = inspect(make_elf(section(attr(6, 10)), attr_name=b".note.other"))
        self.assertFalse(report["attributes_section"]["name_matches_spec"])
        self.assertEqual(report["summary"]["cpu_arch"]["value"], 10)

    def test_non_arm_and_64_bit_files_are_unsupported(self):
        report = inspect(make_elf(section(attr(6, 10)), machine=8))
        self.assertEqual(report["status"], "unsupported")
        self.assertNotIn("summary", report)
        wide = bytearray(make_elf(None))
        wide[4] = 2
        with self.assertRaises((ValueError, struct.error)):
            inspect(bytes(wide))

    def test_non_elf_input_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect(b"not an elf file at all" * 4)


class FileAndCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def write(self, name, blob):
        path = self.root / name
        path.write_bytes(blob)
        return path

    def test_inspect_file_reports_hash_and_refuses_symlink_and_directory(self):
        path = self.write("sample.elf", make_elf(section(*SOFTFP)))
        report = aa.inspect_file(path)
        self.assertEqual(report["bytes"], path.stat().st_size)
        self.assertEqual(len(report["sha256"]), 64)
        link = self.root / "link.elf"
        os.symlink(path, link)
        with self.assertRaises(OSError):
            aa.inspect_file(link)
        with self.assertRaises((OSError, ValueError)):
            aa.inspect_file(self.root)

    def test_cli_writes_new_output_and_refuses_overwrite(self):
        path = self.write("sample.elf", make_elf(section(*SOFTFP)))
        output = self.root / "report.json"
        self.assertEqual(aa.main([str(path), "--output", str(output)]), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["spec"]["commit"], aa.SPEC["commit"])
        self.assertEqual(report["files"][0]["summary"]["float_calling_convention"], "base")
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(aa.main([str(path), "--output", str(output)]), 2)
        self.assertIn("cannot create output", captured.getvalue())

    def test_cli_reports_errors_per_file_with_nonzero_exit(self):
        good = self.write("good.elf", make_elf(section(*SOFTFP)))
        bad = self.write("bad.bin", b"\0" * 64)
        output = self.root / "mixed.json"
        self.assertEqual(aa.main([str(good), str(bad), "--output", str(output)]), 2)
        files = json.loads(output.read_text(encoding="utf-8"))["files"]
        self.assertEqual([entry["status"] for entry in files], ["ok", "error"])

    def test_module_runs_in_isolated_mode_without_package_import(self):
        path = self.write("sample.elf", make_elf(section(*SOFTFP)))
        script = Path(aa.__file__).resolve()
        result = subprocess.run([sys.executable, "-I", "-B", str(script), str(path)],
                                capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["files"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
