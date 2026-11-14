# Bounded LZ4P decoding: kernel and RELEASE identified

Date: 2026-11-14. This follow-up resolves the outer-format uncertainties in [boot-package-triage.md](boot-package-triage.md). All operations were local static data processing. No target code was executed and no TV state changed.

## Results

CONFIRMED (local): both LZ4P containers decode to their exact declared output sizes. The kernel's legacy uImage header and payload CRCs verify. The application package decodes to LG CramFS; its filesystem CRC verifies. Its root directory identifies `RELEASE`, whose exact file extent contains a valid ARM ELF executable.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Decoded kernel image | 5,191,748 | `8d9e62e1e5272bdbbadd8cd0925a5f3ac55a04693cd90429621f3af67c19226e` |
| Decoded `lgap` CramFS | 23,601,152 | `bcbd777a23d628e5e85837333141d3ac38d1481b009c5ad609cd51b4a8b11971` |
| Exact `RELEASE` ELF extent | 23,591,000 | `e37751653de2b79744f1246361439e8a6b37694e2c345ec87c2445c9281a556c` |

All three data files are mode `0444` under ignored `artifacts/boot-triage/decoded/`. Existing original package hashes remain those recorded in the preceding triage. CRC validates reconstruction/integrity, not publisher identity; EPK signature verification belongs to the separate extraction record.

## Decoder and boundaries

`tools/lz4p_inspect.py` uses only Python's standard library and the project's static ELF reader. Limits are 64 MiB input, 64 MiB output, 1 MiB output per block, 4,096 blocks and 1 MiB trailer. Header fields, chunk count, compressed-size table, total output and every literal/match range are checked before the corresponding allocation/copy. Back-references cannot point before their independent block; overlapping matches repeat only already-decoded data.

The source review covered the pinned [LZ4P reader](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/lz4/lz4demo.c) and [legacy block decoder](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/lz4/lz4.c). The first implementation rejected a block ending with a match. Inspection of the legacy decoder's explicit output-end branch explained that case. The revised parser accepts it only if both compressed input and exact output are exhausted; it does not relax buffer bounds. A synthetic fixture covers this behavior.

Each package's 5,376-byte trailer is excluded from decompression but remains intact in the unchanged source package. The report records its size and hash. Its semantics remain PENDING. No claim is made that this is ordinary padding or removable metadata.

Input is opened without following a final symlink. Output creation is exclusive in an existing directory, refuses an existing file/symlink and marks successful binary output read-only. Header inspection happens before output creation. No shell, `ldd`, emulator, firmware script or executable loader is invoked.

## Kernel

CONFIRMED (local): the reconstructed 64-byte legacy uImage header has magic `0x27051956`, header CRC `0x42b200dc`, data CRC `0x95484c73`, payload size 5,191,684, and load/entry fields both `0x7fc0`. Its OS/architecture/type/compression IDs are `5/2/2/0`: Linux, ARM, kernel, uncompressed in the reviewed [legacy image definitions](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/u-boot/image.h). These are firmware metadata, not permission to jump to an address or a physical memory map measurement.

The kernel banner begins at decoded-image offset `0x39f044`. It identifies Linux 3.0.13, GCC 4.5.1 and build `#1 SMP PREEMPT Thu Jan 11 11:06:33 KST 2018`. This matches the device's previously reported kernel version but does not prove that every installed component is byte-identical to the downloaded firmware. No ARM zImage magic or `IKCFG_ST` marker was found in the decoded image. These negative marker searches do not establish that a kernel configuration, device tree or initramfs is impossible to recover.

PENDING: kernel configuration, exact board machine definition, complete command line, driver interfaces, watchdog ownership and recovery behavior. The earlier apparent entry `0x400ff00` and raw-header CRC mismatch are superseded: those arose from incorrectly reading compressed tokens as header fields.

## Application filesystem and executable

CONFIRMED (local/source): decoded `lgap` starts with CramFS magic `0x28cd3d45`, signature `Compressed ROMFS`, declared size matching the output and flags `3`. Zeroing its CRC field and checksumming the complete image reproduces the stored CRC. Its root has six entries; only `RELEASE` content was selected for inspection.

The reviewed [CramFS inode definitions](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/cramfs/cramfs_fs.h) and [LG-aware reader](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/cramfs/uncramfs.c) explain two relevant extensions: sticky-mode files use page-aligned uncompressed XIP storage; file GID above directory GID carries high size bits. For `RELEASE`, mode is `0101755`, its encoded data offset aligns to `0x1000`, and reconstructed size is 23,591,000. The tool validates that exact extent before the ELF reader sees it. It neither opens other root-file payloads nor recursively extracts the filesystem.

| ELF property | Verified value |
| --- | --- |
| Class / byte order / machine | 32-bit / little-endian / ARM (`EM_ARM=40`) |
| File type | Executable (`ET_EXEC=2`) |
| Entry | `0x221ea0` |
| EABI | Version 5 |
| Floating-point ABI header flags | Unspecified; do not infer soft/hard float from this field alone |
| Interpreter | `/lib/ld-linux.so.3` |
| Program headers | 9 |
| Direct `DT_NEEDED` libraries | 43 |
| RPATH / RUNPATH | None declared |

Dependencies include `libmtk5398.so`, `libgal.so`, `libmtal.so`, audio/video decode APIs, `libauitv.so`, `libapiwrapper.so`, `liblgopenapi.so`, native-player APIs, GStreamer 0.10, GLib, D-Bus, OpenSSL 1.0.0, SQLite and glibc components. The complete list is in the ignored ELF report. Library names are dependency evidence, not proof of an API's behavior, license, stability or suitability for reuse.

LIKELY: `RELEASE` participates in several essential TV functions and cannot safely be treated as a disposable visual launcher. Correlate its dependencies with startup scripts, process ownership and exported interfaces before designing separation. A separately compilable ARM binary remains insufficient evidence that an independent graphical process can own display/input while preserving HDMI, tuner and power management.

## Experiment LZ4P-001

- **Objective:** reconstruct known LZ4P packages and validate their inner identities without execution.
- **Hypothesis:** declared chunk tables yield a uImage kernel and an application filesystem containing the main executable.
- **Environment:** native macOS Python, synthetic tests, unchanged local package files; no third-party runtime dependency.
- **Procedure:** test malformed-input handling; decode each explicitly chosen package; validate exact output sizes and inner CRCs; parse the CramFS root; copy only the validated `RELEASE` extent to an exclusive read-only file; inspect that file using `tools.elf_inventory`.
- **Expected result:** bounded deterministic outputs or an explicit error before use.
- **Observed result:** both containers decoded; uImage header/data and CramFS CRCs passed; exact `RELEASE` ELF inspected. Nine decoder tests and eight existing ELF tests passed. Decoder cases cover overlapping matches, extensions, malformed lengths/offsets, oversized declarations, CRC failures, XIP extent bounds, symlinks, overwrite refusal and nonblocking rejection of FIFO input.
- **Conclusion:** firmware kernel architecture and principal executable ABI/dependencies are now measured from validated decoded files. Physical SoC identification and runtime integration remain separate questions.
- **Risks:** hostile parser inputs and accidental firmware execution. Bounds, isolated ignored outputs, read-only files and static inspection reduce those risks; these controls are not a recovery mechanism for the TV.
- **Next step:** join these results with root/init/library analysis; inspect ABI attributes and selected imported/exported symbols without executing `RELEASE`. Investigate kernel/boot dependency mapping separately.

## Reproduce

Create a new ignored output directory, then run from the repository root. Existing outputs are intentionally refused.

```sh
python3 -m unittest tests.test_lz4p_inspect -v
python3 -m tools.lz4p_inspect firmware/lab/packages/kern.pak artifacts/boot-triage/decoded/kern.decoded
python3 -m tools.lz4p_inspect firmware/lab/packages/lgap.pak artifacts/boot-triage/decoded/lgap.decoded
python3 -m tools.elf_inventory artifacts/boot-triage/decoded/RELEASE.elf
```

The LZ4P tool reports the exact RELEASE offset, size and hash and inspects it in memory. The last command requires the separately copied exact extent; the tool does not automatically carve executable files. This run retained `kern.report.json`, `lgap.report.json`, `RELEASE.elf.report.json` and `kernel-markers.json` alongside the decoded artifacts. No firmware outputs or vendor contents belong in Git.
