# Chromium subtree ABI: a VFP loader is not a second complete userland

Evidence date: 2026-11-14. **CONFIRMED (local static)** describes the inspected
official firmware files, not loaded processes or the physical processor.

The `webbrowser/lib/ld-linux-armhf.so.3` file really declares the **VFP calling
convention**. However, the selected `webbrowser/chrome` executable and its
adjacent `libstdc++.so.6` declare the **base calling convention**. Chrome's
`PT_INTERP` is `/lib/ld-linux.so.3`, and no matching libc member was found under
`webbrowser/` in the verified base image inventory. These results do not support
calling this subtree a complete, separate hard-float Chromium userland.

This resolves the filename-only lead in [arm-abi.md](arm-abi.md) without changing
that report's original 18-file sample. It also demonstrates why that sample must
not be generalized to every ELF in the firmware.

## Selection and provenance

Source: preserved `firmware/lab/packages/base.pak`, 325559552 bytes, mode `0444`,
SHA-256 `12182a1b2ea9113b2308f3627832b18b38da490f5bfe7acb3dd9297bea967337`.
This matches the established extraction manifest. Only three exact, confirmed
regular members were copied through the reviewed bounded SquashFS helper.

| Source member | Bytes | SHA-256 |
| --- | ---: | --- |
| `webbrowser/lib/ld-linux-armhf.so.3` | 97472 | `7a1ee28e0c10c94eb4f9ccaa857da668cbec72f97d8453a1de6fb86bb78b13a6` |
| `webbrowser/lib/libstdc++.so.6` | 636940 | `be5f8fbac2d210b5a4bf032660db62cd47082f53364c202ed2895b547d839411` |
| `webbrowser/chrome` | 66835212 | `38d9831c27342071c7b9f6d5d7688a28b79736c7acc493bbe25d934cb9524f00` |

The two small members were selected first. They disagreed in calling convention,
and the inventory contained no `webbrowser/` libc candidate. Chrome was therefore
selected next specifically to inspect its interpreter and build attributes. Its
66.8 MB size is below the helper's 256 MiB single-file limit and the ELF readers'
1 GiB input limit. No bulk extraction or target execution occurred.

Selections are read-only under `firmware/lab/chromium-abi-selected/`; Chrome is
under the additional `executable/` subdirectory. Ignored
`artifacts/chromium-abi/` contains selection manifests, both attribute reports,
ELF inventories and the independent small-section cross-check.

## Observed ABI declarations

All three files are ARM32 little-endian EABI5 and declare Arm v7 application
profile. All parsed with status `ok`, without reported contradictions or limits.

| File | `Tag_ABI_VFP_args` | FP instruction permission | Interpreter / relevant dependency |
| --- | --- | --- | --- |
| Loader named `ld-linux-armhf.so.3` | Explicit 1: VFP variant | `Tag_FP_arch=2`, FP ISA v2; no SIMD permission | No `PT_INTERP` or `DT_NEEDED`; SONAME is `ld-linux-armhf.so.3` |
| `libstdc++.so.6` | Omitted: default 0, base variant | FP tag omitted: default 0 | Needs `libm.so.6`, `libc.so.6`, `ld-linux.so.3`, `libgcc_s.so.1` |
| `chrome` | Omitted: default 0, base variant | `Tag_FP_arch=3`, FP ISA v3; SIMD tag 1 | `PT_INTERP=/lib/ld-linux.so.3`; 49 direct dependencies, including vendor APIs, SCF, D-Bus, libc and libstdc++ |

The omission rule comes from the pinned Arm ABI specification used by
`tools.arm_attributes`; it applies here because each file contains a valid
public file-scope attribute list. The float header bits alone remain unspecified
for all three and do not decide the convention.

Attribute-section evidence:

| File | Section file offset | Section bytes | Decisive detail |
| --- | ---: | ---: | --- |
| Loader | 96304 | 55 | Tag 28 at file offset 96351 is followed by value 1 (`1c 01`) |
| libstdc++ | 635468 | 47 | Complete public file-scope list has no tag 28 |
| Chrome | 66833620 | 49 | Complete public file-scope list has no tag 28 |

A separate fixed-shape byte walk checked section/subsection lengths and decoded
the tags in these three small sections. It agreed with the reader on explicit
versus omitted tag 28. This is a narrow cross-check, not a second general ELF
parser. Its first attempt stopped on tag 44 missing from the scratch allowlist;
after checking that tag's encoding, the complete walks succeeded. The production
reader was unchanged. Section hashes and decoded tag lists are retained in
`attribute-crosscheck.json`.

## What follows, and what does not

- **CONFIRMED:** at least one shipped ELF outside the original 18-file sample
  declares VFP PCS. The loader's filename now has corroborating attributes.
- **CONFIRMED:** the selected Chrome executable requests the base-tree loader
  path, not the adjacent armhf filename. The existing launch script invokes
  `./chrome` directly; it does not explicitly invoke that adjacent loader.
- **RULED OUT for this static claim:** treating these three files as evidence of
  a uniformly VFP-convention Chromium subtree. Two declare base PCS.
- **PENDING:** why the armhf loader is shipped, whether another program uses it,
  and whether runtime invocation or loader-path redirection differs. An unused
  packaging residue is only a hypothesis, not a finding.
- **PENDING:** the actual libc provider and complete runtime dependency closure.
  No libc was selected because there is no matching member under `webbrowser/`
  in this image. That is not proof that libc is unavailable through other mounts
  or library search paths.
- **PENDING:** processor features, actual instruction use, runtime loader
  acceptance and per-function ABI interoperability. Build attributes alone do
  not prove these, nor do they prove that a VFP-declaring loader could never
  service any particular base-PCS program.

For a future vendor-linked native shell, the base-PCS planning direction remains
supported by the inspected core clients and Chrome. Do not select a hard-float
toolchain or substitute a loader merely because this file exists. Compatibility
must be checked per selected dependency and actual call boundary.

## Reproduction

Run from the repository root, using fresh output paths. The helper refuses an
existing destination. It lists/copies only; it does not restore vendor executable
modes or links. The selected target files must never be executed or passed to
`ldd`.

```sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/base.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/chromium-abi-selected \
  --select webbrowser/lib/ld-linux-armhf.so.3 \
  --select webbrowser/lib/libstdc++.so.6
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/base.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/chromium-abi-selected/executable \
  --select webbrowser/chrome
python3 -B -m tools.arm_attributes \
  firmware/lab/chromium-abi-selected/webbrowser/lib/ld-linux-armhf.so.3 \
  firmware/lab/chromium-abi-selected/webbrowser/lib/libstdc++.so.6 \
  firmware/lab/chromium-abi-selected/executable/webbrowser/chrome
python3 -B -m tools.elf_inventory --tree firmware/lab/chromium-abi-selected
```

## Experiment CHROMIUM-ABI-001

- **Objective:** test whether the named armhf loader establishes a second ABI
  tree and identify the matching libc if present.
- **Hypothesis:** the filename may identify VFP PCS, but neighboring files and
  the executable's interpreter must corroborate a coherent runtime tree.
- **Environment:** official base image, existing inventory and reviewed host
  readers; no network, TV, loading, linking or target execution.
- **Procedure:** verify source hash/mode, inspect exact inventory entries, select
  loader and libstdc++, then Chrome to resolve their disagreement; parse ELF
  metadata/attributes and independently walk the three attribute sections.
- **Expected result:** evidence-backed ABI declarations and interpreter, or an
  explicit unresolved result rather than inference from filenames.
- **Observed result:** VFP loader, base-PCS libstdc++ and Chrome, base-loader
  interpreter path, no libc candidate under the inspected subtree.
- **Conclusion:** VFP-declaring material exists, but a complete second Chromium
  hard-float userland is not demonstrated.
- **Risks:** attributing one ELF's convention to its directory or conflating
  declarations with runtime use; avoided by file-specific results.
- **Next step:** add these exact nodes to the independent static dependency
  graph and resolve provider/search-path evidence without running the loader.
