# Reproducible bounded ARM disassembly

`tools.arm_disassembly` replaces the basic range-disassembly operation previously available only in ignored research helpers. The versioned tool and its tests work without vendor firmware. A researcher supplies a separately obtained, already selected ELF and a trusted installed host LLVM disassembler. The tool never loads, links, emulates or executes the input.

## Contract and use

Supported input: a regular, nonempty ELF32 little-endian ARM `ET_EXEC` or `ET_DYN` file, at most 64 MiB. Supply linked virtual addresses, not file offsets. The end is exclusive. Both addresses must be aligned to four bytes, and the range must be nonempty and at most 64 KiB. Every selected byte must be backed by one executable `PT_LOAD`; overlapping mappings, gaps, non-executable mappings and zero-fill-only tails are rejected.

```sh
python3 -m tools.arm_disassembly /absolute/path/to/selected.elf \
  --objdump /absolute/path/to/llvm-objdump \
  --start 0x1a410 --end 0x1a478 --timeout 10
```

The disassembler path is mandatory, absolute and not searched through `PATH`. On this Mac the verified executable was:

```text
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump
```

Use a trusted installed host tool; supplying a path authorizes execution of that host tool, not the selected ELF. Version text and file SHA-256 are recorded for provenance, but are not a signature audit. Symlinks in input/tool paths or their directory components are refused; supply actual nonsymlink paths. Obvious non-host ELF executables are rejected as tools. The implementation supports the project's macOS/Linux hosts, not Windows.

Only standard-library Python is required by the wrapper. LLVM itself is an external host prerequisite; this command neither downloads nor installs it. GNU objdump is not interchangeable with the selected LLVM options.

## Safety and output boundaries

- The input is opened with no-follow/nonblocking flags, checked for regular-file type and size, read under a fixed limit and checked for change during reading. A private temporary read-only snapshot is passed to LLVM, avoiding an input-path replacement between validation and disassembly. The original is untouched; the temporary directory is removed afterward.
- ELF metadata validation reuses `tools.elf_inventory`. No input-defined commands, plugins, symbol-resolution scripts or loaders are invoked. Raw ARM wrapping, `ET_REL` address inference and automatic function discovery are outside this version's scope.
- The tool uses an argument list with `shell=False`, `stdin` closed and a minimal environment. `DEBUGINFOD_URLS` is empty; no remote symbol lookup or network operation is requested. This is not an OS sandbox against a malicious host executable or a vulnerable LLVM parser.
- The two host invocations—version and disassembly—share the requested deadline, default 10 seconds and maximum 30 seconds. Output is drained incrementally, with a combined stdout/stderr cap of 16 KiB for version and 4 MiB for disassembly. Failure before both pipes close and the leader is reaped terminates the process group, including descendants retaining pipes. A completed/reaped group is never signalled, avoiding a recycled-ID hazard. This does not guarantee cleanup of a malicious host tool's detached children after successful completion. Filesystem delays, process creation and operating-system cleanup are not hard real-time guarantees.
- Nonzero exit, any stderr diagnostic, no addressed output, or addressed lines outside the requested range cause an explicit error. There is no silent partial-success report.
- The disassembly invocation uses `-d`, a start/end range and ARM decoding attributes; never `-D`/disassemble-all. Apple's LLVM rejects a standalone `--`; the operand is instead the wrapper's own absolute snapshot path, so a supplied input filename cannot inject an option.

Successful stdout is one JSON object. It contains input size/SHA-256, ELF type/flags, linked range, mapped file offset, selected-byte count/SHA-256, host executable size/hash/version, fixed decoding options, disassembly text and output hashes. No firmware bytes are separately exported. Original tool-output size/hash describe the actual capture; `display_sha256` hashes the normalized UTF-8 display text, replacing the random snapshot path with `<validated-input.elf>` for comparison between runs. Different LLVM builds can still produce different disassembly text.

Errors are JSON on stderr with exit code 2. The wrapper creates no permanent output file by default. If preserving a report, choose a new ignored artifact destination and review it before publication: selected code may contain symbols and literal words. Narrow address selection is not proof that output contains no proprietary or sensitive information.

## Interpretation limits

Executable segments can contain literal pools and tables. The wrapper validates address coverage; it does not prove that each decoded word is an instruction. LLVM may display the nearest exported symbol as an enclosing label even when it is not the selected function's identity. Branch destinations printed by LLVM are linked addresses, not observed runtime execution.

`--arch-name=arm --mattr=+v7` is an explicit decoder profile, not evidence of the TV's exact CPU. ELF mapping symbols may affect ARM/Thumb decoding; a four-byte-aligned range does not establish instruction state. Ambiguous or mixed instruction-state cases require separate review, and two-byte-only Thumb ranges are not supported by this interface.

This version deliberately adds no PLT annotations, demangled API contracts, call signatures or control-flow interpretation. The older scratch helper's relocation/PLT logic has not been copied. Symbol-boundary selection and named-call conclusions in existing reports still need their own evidence; this tool only makes the selected-address operation reproducible.

## Validation

Run the public synthetic suite:

```sh
python3 -m unittest discover -s tests -p test_arm_disassembly.py -v
```

**CONFIRMED (local, 2026-11-14):** 15 tests pass. They use generated ELF data and a fake host tool only, covering successful snapshot/hash output, `ET_DYN`, unsupported architecture/type/byte order, alignment and size bounds, non-executable/BSS/overlapping loads, malformed program headers, input/tool symlinks, FIFO and empty inputs, tool identity, deadlines, stdout/stderr/version caps, diagnostics, output range checks and CLI behavior. A focused regression checks that completed/reaped processes are not signalled, while the timeout case still terminates the group. No proprietary fixture or target execution is required.

A separate narrow real-input check succeeded against the previously selected `procmgr`:

| Item | Observation |
| --- | --- |
| Input | 435,528 bytes; SHA-256 `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5` |
| Linked range | `[0x1a410, 0x1a478)`, 104 bytes |
| Mapping | Executable program header index 3, file offset `0x12410` |
| Selected-byte SHA-256 | `1ab3ce29e19a1f973415cd75133cd5215d6589316d1163050f325b296078d5f5` |
| Host tool | Apple LLVM 17.0.0, 33,914,912 bytes; SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4` |
| Normalized disassembly SHA-256 | `730e2b4e0ecb35373a986196d59219c1669940f153b19f8213e83f94321f0c32` |

The output's enclosing label is `PM_SEND_GetProcessStatus`, while the independently bounded lookup starts later at `0x1a410`; that label is not adopted as its identity. The last selected word is a literal-pool candidate, not proof of another instruction. This confirms the wrapper's local operation against real ELF metadata, not execution of `procmgr` or its behavior on the TV. The initial check exposed Apple's rejection of `--`; the fixed absolute-snapshot invocation then succeeded.

Next: existing evidence reports can state explicit address ranges and invoke this versioned reader, retaining their separate symbol and branch analysis. Raw boot images remain outside this interface and require the separately justified address mapping documented in [boot selection](boot-selection.md).
