#!/usr/bin/env python3
"""Build and inspect our ARM probe locally; never execute the resulting image."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import arm_attributes, arm_disassembly, elf_inventory  # noqa: E402

SOURCE = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts" / "native-probe"
CODE_BYTES = 44


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def validate_contract(metadata: dict, attributes: dict) -> None:
    """Check this probe's narrow static contract, not general ELF loadability."""
    if (metadata["bits"], metadata["byte_order"], metadata["machine_id"],
            metadata["elf_type"], metadata.get("arm_eabi_version")) != (32, "little", 40, 2, 5):
        raise ValueError("Expected a linked ELF32 little-endian ARM EABI5 executable")
    if metadata["interpreter"] is not None or metadata["needed"]:
        raise ValueError("The probe must not depend on a dynamic loader or libraries")
    if metadata["arm_float_abi_flags"] != "soft":
        raise ValueError("Expected the explicit base-PCS ELF flag")
    segments = metadata["segments"]
    if len(segments) != 2 or {s["type"] for s in segments} != {1, 0x6474E551}:
        raise ValueError("Expected only one LOAD segment and one GNU_STACK header")
    load = next(s for s in segments if s["type"] == 1)
    stack = next(s for s in segments if s["type"] == 0x6474E551)
    if load["flags"] != 5 or stack["flags"] != 6:
        raise ValueError("Expected an RX image and an RW non-executable stack")
    if (load["offset"] != 0 or load["address"] != 0x10000 or
            load["alignment"] != 4096 or
            not 0 < load["file_size"] == load["memory_size"] <= 4096):
        raise ValueError("Unexpected fixed image layout or zero-fill storage")
    if stack["file_size"] or stack["memory_size"]:
        raise ValueError("The stack header must not contain image data")
    entry = int(metadata["entry_hex"], 16)
    if entry % 4 or not load["address"] <= entry < entry + CODE_BYTES <= load["address"] + load["file_size"]:
        raise ValueError("Entry/code must be aligned and fully inside the file-backed RX image")
    summary = attributes["summary"]
    if (attributes["status"] != "ok" or summary["contradictions"] or
            summary["float_calling_convention"] != "base" or
            summary["fp_arch"]["value"] != 0 or
            summary["advanced_simd_arch"]["value"] != 0 or
            summary["entry_point_isa"] != "arm"):
        raise ValueError("Expected coherent ARM/base-PCS attributes without FP/SIMD")


def run_host(arguments: list[str]) -> str:
    """Run an explicitly supplied trusted host build tool, with a finite deadline."""
    completed = subprocess.run(arguments, check=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=30)
    if len(completed.stdout) > 64 * 1024:
        raise ValueError("Unexpected host-tool output size")
    return completed.stdout.decode("utf-8", errors="replace")


def build(clang: Path, linker: Path, objdump: Path, output: Path) -> dict:
    output = output.absolute()
    base = ARTIFACTS.resolve()
    if not output.resolve().is_relative_to(base) or output.resolve() == base:
        raise ValueError("Output must be a new directory beneath artifacts/native-probe")
    # Tools are explicit host executables. Resolve installed symlinks, record identity.
    tool_paths = {name: path.resolve(strict=True) for name, path in
                  (("clang", clang), ("linker", linker), ("objdump", objdump))}
    for path in tool_paths.values():
        if not path.is_file():
            raise ValueError("Host tool must be a regular file")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)  # Never overwrite an earlier build.
    tools = {}
    for name, path in tool_paths.items():
        version_args = [str(path)] + (["-flavor", "gnu"] if name == "linker" else []) + ["--version"]
        tools[name] = {"path": str(path), "sha256": digest(path), "version": run_host(version_args).strip()}
    source_hashes = {name: digest(SOURCE / name) for name in ("probe.S", "probe.ld", "build.py")}
    obj, elf = output / "probe.o", output / "probe.elf"
    commands = [
        [str(tool_paths["clang"]), "--target=arm-linux-gnueabi", "-march=armv6kz",
         "-marm", "-mfloat-abi=soft", "-c", str(SOURCE / "probe.S"), "-o", str(obj)],
        [str(tool_paths["linker"]), "-flavor", "gnu", "-m", "armelf_linux_eabi",
         "-static", "--no-undefined", "--fatal-warnings", "--build-id=none",
         "-z", "noexecstack", "-z", "max-page-size=4096", "-T", str(SOURCE / "probe.ld"),
         str(obj), "-o", str(elf)],
    ]
    for index, command in enumerate(commands):
        (output / ("host-step-%d.txt" % index)).write_text(run_host(command), encoding="utf-8")
    elf.chmod(0o600)  # Build evidence, not an executable command for the host/user.
    metadata = elf_inventory.inspect_file(elf)
    attributes = arm_attributes.inspect_file(elf)
    validate_contract(metadata, attributes)
    entry = int(metadata["entry_hex"], 16)
    disassembly = arm_disassembly.disassemble(elf, tool_paths["objdump"], entry, entry + CODE_BYTES, timeout=10)
    if disassembly["input_sha256"] != metadata["sha256"]:
        raise ValueError("Image changed during inspection")
    for name, path in tool_paths.items():
        if digest(path) != tools[name]["sha256"]:
            raise ValueError("Host tool changed during the build")
    if any(digest(SOURCE / name) != value for name, value in source_hashes.items()):
        raise ValueError("Probe source changed during the build")
    report = {"scope": "Local build/static inspection only; target code was not executed",
              "tools": tools, "commands": commands,
              "sources": source_hashes,
              "readers": {name: digest(ROOT / "tools" / name) for name in
                          ("elf_inventory.py", "arm_attributes.py", "arm_disassembly.py")},
              "object": elf_inventory.inspect_file(obj), "elf": metadata,
              "attributes": attributes, "disassembly": disassembly}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True, help="Explicit trusted host Clang executable")
    parser.add_argument("--linker", type=Path, required=True, help="Explicit trusted host LLD executable")
    parser.add_argument("--objdump", type=Path, required=True, help="Explicit trusted host LLVM objdump")
    parser.add_argument("--output", type=Path, required=True, help="New directory under artifacts/native-probe")
    args = parser.parse_args()
    try:
        result = build(args.clang, args.linker, args.objdump, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Build/inspection failed: %s" % error, file=sys.stderr)
        return 1
    print("Built and inspected only: %s bytes; SHA-256 %s" % (result["elf"]["bytes"], result["elf"]["sha256"]))
    print("No target execution, deployment or compatibility claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
