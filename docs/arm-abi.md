# ARM ABI evidence for native toolchain planning

Updated: 2026-11-14. Level 0 only: local static reading of official firmware files already copied
into the ignored lab. No firmware code was executed, loaded or emulated; no television or LAN
contact; no credentials. Task CLAUDE-002.

## Result

**CONFIRMED (static official-firmware evidence):** the 18 ELF files selected into the lab so far
are ARM 32-bit little-endian EABI version 5 and carry a well-formed `.ARM.attributes` section.
Seventeen declare **Arm v7, application profile**, with Arm and 32-bit Thumb instructions permitted
and **floating-point hardware instructions permitted**. None declares the VFP variant of the
procedure-call standard: `Tag_ABI_VFP_args` is omitted in every file, which the specification
defines as the **base variant** (floating-point arguments and results in core registers). The
eighteenth, `/sbin/init`, is an Arm v6KZ build with no floating-point hardware use and the same
base variant.

These are 18 files chosen by several workstreams for other reasons, not a census of the firmware;
later selections will add files. The observations about these files are separate from the
correctness of the reader, which is established by synthetic tests (see Tool).

In toolchain terms: the 18 inspected files use the base calling convention with VFP instructions
allowed (what GCC calls `softfp`), not the hard-float calling convention. Code built for the VFP
variant passes floating-point arguments and results differently from these files, so a call across
that boundary that carries floating-point values in a non-variadic interface would not agree.
This is a statement about the inspected sample; another program tree with a different convention
may exist in the firmware (see the Chromium loader lead below).

This describes what the producers were **permitted** to use in the firmware image. It is not a
measurement of the processor in the owner's television, and it does not prove that any particular
instruction is actually present in a file.

## Four separate questions

These are independent and must not be merged into one "soft/hard float" label.

| Question | Where it is recorded | Notes |
| --- | --- | --- |
| ABI version | `e_flags` bits 31–24 (`EF_ARM_ABIMASK`) | 5 in every file. Says nothing about floating point. |
| CPU architecture and instruction sets | `Tag_CPU_arch`, `Tag_CPU_arch_profile`, `Tag_ARM_ISA_use`, `Tag_THUMB_ISA_use` | The architecture the user allowed the producer to target. |
| Floating-point **instructions** | `Tag_FP_arch`, `Tag_Advanced_SIMD_arch`, `Tag_ABI_HardFP_use` | Whether code may execute FP hardware instructions, and which register set. |
| Floating-point **calling convention** | `Tag_ABI_VFP_args`; `e_flags` bits `EF_ARM_ABI_FLOAT_HARD`/`_SOFT` | How FP values cross function boundaries. This decides link compatibility. |

A file can permit VFP instructions and still use the base calling convention. That is the case
here.

## Specification and defaults

Tag numbers, parameter encodings and value meanings in `tools/arm_attributes.py` are transcribed
from the Arm ABI sources at <https://github.com/ARM-software/abi-aa>, commit
`a1b53459479e88f3492ca9b11a161313764ab138`:

- `addenda32/addenda32.rst`, chapter "Build attributes" — section syntax, public tags, defaults.
- `aaelf32/aaelf32.rst`, "ELF Header" and "Build Attributes" — `e_flags`, `e_entry`,
  `SHT_ARM_ATTRIBUTES` (`0x70000003`), section name `.ARM.attributes`.

Rules taken from those sources and applied by the tool:

- **Omitted tags have a defined value.** "The effect of omitting a public tag in file scope is
  identical to including it with a value of 0 or the empty string" (addenda32, "Default values for
  public tags"). The tool reports such values with `source: "default"`, distinct from
  `"explicit"`. The default applies only when a public file-scope attribute list exists. A file
  with no attributes section is unattributed: its values are `"unavailable"`, not zero.
- **Unknown tags.** Tags 0–63 (and any tag whose value modulo 128 is in that range) must be
  comprehended; an unknown one makes the report `limited` and its conclusions incomplete. Tags
  64–127 may be ignored. Above tag 32, even tags carry a ULEB128 value and odd tags a
  NUL-terminated string, which lets the reader skip them without interpreting them.
- **Float flags in `e_flags`.** AAELF32 defines the two float bits as "set in executable file
  headers (e_type = ET_EXEC or ET_DYN)". For any other file type (for example a relocatable
  object) the tool reports the raw bits as `not applicable` and derives nothing from them.
  For executables and shared objects, the pinned text says that with both float bits clear,
  "conformance to the base procedure-call standard is implied". Those two bits were added in
  AAELF32 revision E (30 November 2012), so a producer older than that could not set them.
  Clear bits are therefore weak evidence on their own, and the tool reports
  `float_calling_convention: "undetermined"` for a file that has clear bits and no usable
  attributes. Here the attributes exist and agree with the implied reading.
- **`e_entry`.** Bit 0 set marks a Thumb entry point; bits `[1:0] = 00` an Arm entry point;
  `10` is reserved. An entry point whose instruction set the file-scope attributes do not permit
  is reported as a contradiction. Because an omitted tag is identical to value 0, an omitted
  `Tag_ARM_ISA_use` or `Tag_THUMB_ISA_use` is treated exactly like an explicit 0 here; the
  message says which it was. A file with no attributes at all is not weighed.
- **Undefined values.** A known tag carrying a value the pinned specification does not define
  gets no meaning and establishes nothing: an undefined `Tag_FP_arch` leaves FP instruction use
  `undetermined`, an undefined `Tag_ABI_VFP_args` leaves the calling convention `undetermined`.
- **Independent declarations.** The specification describes argument passing
  (`Tag_ABI_VFP_args`) and instruction permission (`Tag_FP_arch`) separately and contains no rule
  forbidding the VFP variant together with "no FP hardware instructions". The tool lists that
  pair under `notes` and does not call it a contradiction. `contradictions` is reserved for two
  declarations of the same property that cannot both hold (both float flags set; float flag
  against `Tag_ABI_VFP_args`; one tag with two values; entry point against instruction-set tag;
  reserved `e_entry` bits).
- **`Tag_also_compatible_with`.** The pinned text defines only two uses (v4T with v6-M, v8-A with
  v8-R, either way round) and reserves all others. Anything else — another nested tag, an
  undefined nested value, another architecture pair — is decoded syntactically, reported, and
  marks the file `limited`; it is not interpreted.

Bit `0x00000002` is set in every file's `e_flags` (`0x05000002`). The pinned specification does
not allocate that bit for ABI version 5; the tool reports it and does not interpret it.

## Evidence

Ignored report: `artifacts/arm-abi/attributes.json` (per-file SHA-256, section file offset and
size, section SHA-256, every attribute with its section and file offset, summary, limits).
Values marked `*` are omitted in the file and take the specification default.

| File (under `firmware/lab/` unless noted) | SHA-256 (first 16) | Section offset / bytes | CPU name / arch / profile | Arm / Thumb | FP arch | SIMD | HardFP use | VFP args | wchar / enum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `artifacts/boot-triage/decoded/RELEASE.elf` | `e37751653de2b797` | `0x167f248` / 53 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `app-lifecycle/open/bin/fxui` | `98e05ccd63771c26` | `0x1ca340` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `app-lifecycle/open/bin/appctrl` | `630bfe0e7ab3c93e` | `0x434b0` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `app-lifecycle/lgli/libafopenapi.so.0.0.0` | `bbbfaa4c51c0fdb5` | `0x35cf0` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `service-selected/swue/SWUE` | `10fc93711d78bdab` | `0x3ba858` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `lgin-selected/lginit` | `0c2cb0c07849d4fe` | `0x7cdf8` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `lgin-selected/lginit_app` | `a5bd53970c284498` | `0x6eb0` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `lgli-api-selected/libapiwrapper.so` | `28ed343a42443bae` | `0x8a5e0` / 53 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `base-api-selected/addon/lib/libncg_agent.so` | `554e1189be94c89f` | `0x24514` / 53 | 7-A / 10 / 0x41 | 1 / 2 | 3 | 1 | 3 | 0* | 4 / 2 |
| `lgli-api-selected/libauitv.so` | `5edd456d20e02959` | `0x89b50` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `lgli-api-selected/liblgopenapi.so.0.0.0` | `538ec51bd5bee6c3` | `0x142d6c` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `service-selected/open/bin/procmgr` | `00cc453a3dd9cdf2` | `0x69fc4` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 4 | 0* | 3 | 0* | 4 / 2 |
| `root-selected/bin/busybox` | `264a4085fbc8926d` | `0x90b32` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 2 | 0* | 3 | 0* | 4 / 2 |
| `root-selected/lib/libc-2.12.2.so` | `bdcaa27d7c62aed5` | `0x122954` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 2 | 0* | 3 | 0* | 4 / 2 |
| `root-selected/lib/ld-2.12.2.so` | `6077709a05643d69` | `0x1d874` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 2 | 0* | 3 | 0* | 4 / 2 |
| `base-selected/browser/bin/lb6wk` | `0b9f18180a95c6ad` | `0x42c80` / 49 | 7-A / 10 / 0x41 | 1 / 2 | 2 | 0* | 3 | 0* | 4 / 2 |
| `base-api-selected/browser/lib/libtv.so` | `09138fc3920e4d3e` | `0x3c080` / 51 | 7-A / 10 / 0x41 | 1 / 2 | 2 | 0* | 3 | 0* | 4 / 2 |
| `root-review-selected/sbin/init` | `595696e55a908ccb` | `0x6928` / 40 | 6Z / 7 / 0* | 1 / 1 | 0* | 0* | 0* | 0* | 4 / 2 |

Value meanings in the pinned specification:

- `Tag_CPU_arch` 10 = Arm v7; 7 = Arm v6KZ. `Tag_CPU_arch_profile` 0x41 = application profile.
- `Tag_THUMB_ISA_use` 2 = 32-bit Thumb instructions permitted (a deprecated value; implies
  16-bit); 1 = 16-bit Thumb permitted (deprecated value).
- `Tag_FP_arch` 2 = v2 of the FP instruction set; 3 = v3; 4 = v3 restricted to registers
  D0–D15/S0–S31; 0 = no instructions requiring FP hardware.
- `Tag_Advanced_SIMD_arch` 1 = Advanced SIMDv1 (Neon) permitted.
- `Tag_ABI_HardFP_use` 3 = FP use implied by `Tag_FP_arch` (a deprecated duplicate of 0).
- `Tag_ABI_VFP_args` 0 = AAPCS base variant.
- `Tag_ABI_PCS_wchar_t` 4 = 4-byte `wchar_t`; `Tag_ABI_enum_size` 2 = 32-bit enum containers.

Other explicit tags, identical where present: `Tag_ABI_align_needed` = 1 and
`Tag_ABI_align_preserved` = 1 in all 18 files (8-byte alignment of 8-byte data);
`Tag_ABI_FP_denormal` = 1, `Tag_ABI_FP_exceptions` = 1, `Tag_ABI_FP_number_model` = 3 in all 18;
`Tag_DIV_use` = 1 (SDIV/UDIV explicitly not permitted) in the 17 Arm v7 files;
`Tag_CPU_unaligned_access` = 1 in `RELEASE.elf` only. In `RELEASE.elf` the deciding tags sit at
file offsets `0x167f25d` (`Tag_CPU_arch`), `0x167f263` (`Tag_THUMB_ISA_use`), `0x167f265`
(`Tag_FP_arch`), `0x167f267` (`Tag_Advanced_SIMD_arch`) and `0x167f277` (`Tag_ABI_HardFP_use`).

Every file has `e_flags` = `0x05000002`, an Arm entry point with `Tag_ARM_ISA_use` = 1, no
private vendor subsection, no section- or symbol-scope attributes, no unknown tags, no undefined
values, no notes and no contradictions; the tool reports all 18 as `ok`. No file carries `Tag_conformance`, so none makes the explicit
conformance claim the specification associates with that tag.

Control input: `artifacts/native-toolchain/integer_probe.arm.o` (SHA-256 `90de028d6a1897da…`),
a synthetic relocatable object produced on the host by the platform workstream with an
intentionally conservative Arm v5TE soft-float profile — not a television file and not a chosen
target profile. The reader reports `Tag_conformance` "2.09", `Tag_CPU_arch` = 4 (Arm v5TE),
`Tag_FP_arch` omitted, base convention from the attributes, and the `e_flags` float bits as
`not applicable` because the file is `ET_REL`. Report: `artifacts/arm-abi/control-object.json`.
It exercises a producer and a file type that the firmware files do not.

Cross-check: no second attribute reader exists on this host (`llvm-readobj` is absent), so the
decoder was checked by hand against a hex dump of two sections (`/sbin/init`, 40 bytes, and
`RELEASE.elf`, 53 bytes); both decode byte-for-byte to the values above. That is a manual check,
not an independent implementation.

## Compatibility matrix for a native toolchain

Compiler option names below are GCC conventions, given for orientation; they do not come from the
ABI specification and must be confirmed against the manual of the compiler actually chosen.

| Decision | Firmware evidence | Verdict | Label |
| --- | --- | --- | --- |
| Byte order, word size, ABI version | 18/18 little-endian ELF32, EABI 5 | Target little-endian AArch32 EABI | CONFIRMED static |
| Calling convention: base (`soft` or `softfp`) | 18/18 `Tag_ABI_VFP_args` omitted, default 0 | Required to call these vendor libraries or be called by them | CONFIRMED static (specification default) |
| Calling convention: VFP variant (`hard`, "armhf") | 0/18 | Disagrees with these files at non-variadic interfaces that pass floating-point parameters or results. Interfaces that pass no floating-point values are not affected by this difference alone. Whether a VFP-variant program could use this loader or parts of this C library was not examined | CONFIRMED static for the declared convention of the inspected files; wider compatibility not assessed |
| Architecture: Arm v7-A | 17/18 declare v7 application profile | Matches the inspected userland | CONFIRMED static; processor itself unobserved |
| Thumb-2 code with interworking | 17/18 permit 32-bit Thumb; entry points are Arm | Permitted by the inspected userland | CONFIRMED static |
| FP instructions, registers D0–D15 only | Lowest v7 level present is FP v2 (5 files); 6 files declare v3 restricted to D0–D15, among them `fxui`, `appctrl` and `procmgr` | The conservative choice if FP instructions are used at all | LIKELY safe; actual processor features unobserved |
| FP v3 with D16–D31, and Neon | Permitted in 6 files, including `RELEASE.elf` and `SWUE` | The main application was built with permission to use them, so the intended hardware LIKELY provides them | LIKELY; permission is not proof of use or of hardware |
| No FP instructions at all | `/sbin/init` only | Same base convention, so the declared calling conventions match; this says nothing about symbol versions, library availability or speed, none of which was measured | CONFIRMED for the declared convention only |
| Integer divide instructions | `Tag_DIV_use` = 1 in 17 files | Do not assume SDIV/UDIV | CONFIRMED static (explicit prohibition in the build) |
| `wchar_t` width, enum size | 18/18: 4 bytes, 32-bit containers | Do not use short-`wchar_t` or short-enum modes | CONFIRMED static |
| 8-byte stack/data alignment | 18/18 | Keep the standard AAPCS alignment | CONFIRMED static |
| C library | `libc-2.12.2.so`, loader `ld-linux.so.3` | Build against a sysroot whose symbol versions do not exceed this library, or link statically | Filename and SONAME CONFIRMED; symbol-version inventory PENDING |

### Reconciling other evidence

- **Community build configuration.** `docs/platform-research.md` records a community buildroot
  configuration described as "soft-float ABI". That is consistent with these files at the level
  that matters for linking: the base calling convention. It is not evidence that the firmware
  avoids FP instructions — 17 of 18 files permit them.
- **`elf_inventory` output.** `tools/elf_inventory.py` reports `arm_float_abi_flags:
  "unspecified"` for these files because both `e_flags` float bits are clear. That remains
  correct for the flags alone. The calling convention is settled by the attributes, not by
  promoting the clear bits.
- **A possible second userland (lead, not inspected).** `artifacts/firmware-lab/base-list.txt`
  line 8053 lists `webbrowser/lib/ld-linux-armhf.so.3` (97,472 bytes) inside the Chromium tree.
  The name suggests a self-contained VFP-variant loader. A name is not evidence of an ABI: the
  file is not in the lab and has not been read. If its attributes show `Tag_ABI_VFP_args` = 1, it
  would show the firmware itself ships a hard-float program tree beside the base-variant one,
  each with its own loader and libraries. Requested for inspection: `webbrowser/chrome`,
  `webbrowser/lib/ld-linux-armhf.so.3` and the C library in that directory.

## Tool

`tools/arm_attributes.py` uses only the Python standard library and imports the existing
`tools/elf_inventory.py` unchanged for ELF header and program-header validation.

```sh
python3 -m unittest tests.test_arm_attributes -v
python3 -m tools.arm_attributes artifacts/boot-triage/decoded/RELEASE.elf
python3 -m tools.arm_attributes FILE [FILE ...] --output artifacts/arm-abi/NEW-NAME.json
```

`--output` creates a new file and refuses an existing one. The script also runs directly under
isolated mode (`python3 -I tools/arm_attributes.py FILE`). Exit status is 2 if any file could not
be read or its attributes section was rejected.

Bounds and refusals:

- Input is opened read-only without following a final symlink; only regular files up to 1 GiB;
  the file is hashed and must not change during inspection.
- Only ELF32 `EM_ARM` is interpreted. Other machines return `unsupported` with no ABI summary.
- Section headers: entry size must be 40, at most 4,096 sections, table and section data inside
  the file; extended section numbering is unsupported. The section is selected by type
  `SHT_ARM_ATTRIBUTES`, not by name; a name mismatch is flagged; more than one such section is
  unsupported; a section merely named `.ARM.attributes` with another type is not parsed.
- Attributes: section at most 1 MiB; format version must be `A`; every subsection and
  sub-subsection length is checked against its container; vendor names at most 64 bytes; strings
  at most 4,096 bytes and terminated inside their scope; ULEB128 values at most 5 bytes and
  32 bits. Four budgets are **totals for the whole section**, shared by all subsections:
  4,096 attribute records, 65,536 section/symbol indexes, 64 subsections and 256
  sub-subsections. (A file with more than one attributes section is refused outright, so there
  is no cross-section total to enforce.)
- Private vendor subsections are reported by name, size and hash, never interpreted.
  Section- and symbol-scope attributes (deprecated by the specification) are decoded but not
  merged into the file summary, and mark the report `limited`.
- The same tag given two different values in file scope is reported as `conflicting` and is not
  resolved. A float flag that disagrees with `Tag_ABI_VFP_args`, or both float flags set, makes
  the calling convention `contradictory`. An entry point that disagrees with the instruction-set
  tags is listed as a contradiction without changing the calling-convention field.
- A malformed attributes section yields `status: "error"`, no decoded attributes and an
  `unavailable` summary; partial results from a rejected section are discarded.

Validation: 79 synthetic tests in `tests/test_arm_attributes.py` (no firmware involved) cover
both byte orders, defaults, unknown and undefined tags, contradictions and notes, every length,
string and total-budget bound, malformed ELF section tables, relocatable versus executable file
types, symlink refusal and the command line. Nineteen of them are targeted regressions for the
six issues found by the integration review of the first version.

## Limits

- Build attributes record what the user **permitted** the producer to use. They do not list the
  instructions present, and a linker merges them across inputs. Confirming actual Neon or
  D16–D31 use would need instruction-level static analysis of the code sections.
- Eighteen files were inspected, selected by other workstreams for other reasons. Vendor driver
  libraries in `vend` (for example `libmtk5398.so`) and the Chromium tree are not in the lab.
- Unsupported by the reader, and reported as such rather than interpreted: ELF64 and non-Arm
  files; extended section numbering; more than one attributes section; private vendor
  subsections; section- and symbol-scope attributes (decoded, not merged); reserved uses of
  `Tag_also_compatible_with`; pre-version-5 `e_flags` low bits.
- Attributes are unauthenticated metadata inside files whose signatures were checked only
  against a community-distributed key (see `docs/firmware-extraction.md`).
- Nothing here identifies the physical processor, its features, or the kernel's handling of
  floating-point state on the owner's unit.

## Experiment ABI-001

- **Objective:** determine CPU architecture, instruction-set use, floating-point instruction
  requirements and procedure-call convention of the selected firmware files for toolchain planning.
- **Hypothesis:** the firmware's ELF files carry public build attributes that settle the
  calling convention which `e_flags` alone leaves unspecified.
- **Environment:** Apple Silicon macOS host, Python 3.13 standard library; official 04.28.17
  firmware files already in the ignored lab; pinned Arm ABI sources.
- **Procedure:** transcribe tag definitions from the pinned specification; implement a bounded
  reader; test it on synthetic files; run it read-only on the 18 selected lab ELF files and one
  host-built control object; hand-check two sections against hex dumps; revise after an
  independent review and re-run.
- **Expected result:** per-file attributes with offsets, or an explicit refusal.
- **Observed result:** 18 of 18 parsed without limits, notes or contradictions; base calling
  convention in all; FP hardware instructions permitted in 17; Neon permitted in 6. The review
  found six reader defects on synthetic inputs; none changed a firmware observation.
- **Conclusion:** to exchange floating-point values with the 18 inspected files through
  non-variadic interfaces, native code must use the base (soft-float) calling convention. FP
  instructions are optional, with a D0–D15 register set as the conservative level. A VFP-variant
  build disagrees with these files at such interfaces; nothing wider is claimed.
- **Risks:** treating permission as proof of hardware; generalising from 18 selected files;
  hostile parser input (bounded and tested).
- **Next step:** inspect the Chromium tree's loader and `vend` driver libraries once selected;
  inventory glibc symbol versions; only then choose a compiler configuration.
