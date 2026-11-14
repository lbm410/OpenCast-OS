"""Host-only negative checks for the deliberately narrow probe image contract."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_probe_build", ROOT / "prototypes/native-probe/build.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def declared_image():
    return {
        "bits": 32, "byte_order": "little", "machine_id": 40, "elf_type": 2,
        "arm_eabi_version": 5, "interpreter": None, "needed": [],
        "arm_float_abi_flags": "soft", "entry_hex": "0x10074",
        "segments": [
            {"type": 1, "offset": 0, "address": 0x10000, "file_size": 184,
             "memory_size": 184, "flags": 5, "alignment": 4096},
            {"type": 0x6474E551, "offset": 0, "address": 0, "file_size": 0,
             "memory_size": 0, "flags": 6, "alignment": 0},
        ],
    }


def declared_attributes():
    return {"status": "ok", "summary": {"contradictions": [],
            "float_calling_convention": "base", "fp_arch": {"value": 0},
            "advanced_simd_arch": {"value": 0}, "entry_point_isa": "arm"}}


class NativeProbeContractTests(unittest.TestCase):
    def test_accepts_expected_image_contract(self):
        probe.validate_contract(declared_image(), declared_attributes())

    def test_rejects_object_dynamic_foreign_or_hard_float(self):
        for field, value in (("elf_type", 1), ("elf_type", 3), ("machine_id", 183),
                             ("byte_order", "big"), ("arm_eabi_version", 4),
                             ("interpreter", "/lib/ld-linux.so.3"), ("needed", ["libc.so.6"]),
                             ("arm_float_abi_flags", "hard"), ("arm_float_abi_flags", "conflicting")):
            with self.subTest(field=field, value=value):
                image = declared_image()
                image[field] = value
                with self.assertRaises(ValueError):
                    probe.validate_contract(image, declared_attributes())

    def test_rejects_writable_code_executable_stack_and_extra_segments(self):
        for segment, flags in ((0, 7), (0, 6), (1, 7)):
            with self.subTest(segment=segment, flags=flags):
                image = declared_image()
                image["segments"][segment]["flags"] = flags
                with self.assertRaises(ValueError):
                    probe.validate_contract(image, declared_attributes())
        for extra in (2, 3, 1):
            image = declared_image()
            image["segments"].append({"type": extra})
            with self.assertRaises(ValueError):
                probe.validate_contract(image, declared_attributes())

    def test_rejects_unmapped_thumb_truncated_and_oversized_image(self):
        for value in ("0x10075", "0x100b8", "0x100a0", "0xfffc"):
            image = declared_image()
            image["entry_hex"] = value
            with self.assertRaises(ValueError):
                probe.validate_contract(image, declared_attributes())
        for field, value in (("offset", 1), ("alignment", 8192), ("memory_size", 185),
                             ("file_size", 4097)):
            image = declared_image()
            image["segments"][0][field] = value
            with self.assertRaises(ValueError):
                probe.validate_contract(image, declared_attributes())

    def test_rejects_conflicting_or_fp_attributes(self):
        for field, value in (("contradictions", ["conflict"]), ("float_calling_convention", "vfp"),
                             ("fp_arch", {"value": 3}), ("advanced_simd_arch", {"value": 1}),
                             ("entry_point_isa", "thumb")):
            attributes = declared_attributes()
            attributes["summary"][field] = copy.deepcopy(value)
            with self.assertRaises(ValueError):
                probe.validate_contract(declared_image(), attributes)

    def test_output_outside_artifacts_rejected_before_host_execution(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(probe, "run_host") as run:
            with self.assertRaises(ValueError):
                probe.build(Path("missing-clang"), Path("missing-linker"), Path("missing-objdump"), Path(directory) / "build")
            run.assert_not_called()

    def test_existing_output_preserved_without_running_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            existing = base / "existing"
            existing.mkdir()
            sentinel = existing / "owner.txt"
            sentinel.write_text("preserve")
            tool = base / "host-tool"
            tool.write_text("not executable")
            with mock.patch.object(probe, "ARTIFACTS", base), mock.patch.object(probe, "run_host") as run:
                with self.assertRaises(FileExistsError):
                    probe.build(tool, tool, tool, existing)
                run.assert_not_called()
            self.assertEqual(sentinel.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
