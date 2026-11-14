# Boot, kernel and application package triage

Date: 2026-11-14. This is read-only static inspection of the decrypted packages already produced by the firmware workstream. No firmware code, extractor, decompressor or target instruction was executed in this task. Package files were not modified. Reports are under ignored `artifacts/boot-triage/`.

## Package identities

| Package | Bytes | SHA-256 |
| --- | ---: | --- |
| `kern.pak` | 3,252,849 | `991fed18aada3055711637452f0bedb2997b361f1a2d10f7c99f80f082a3b6a2` |
| `lgap.pak` | 11,664,770 | `3155b3033a9996fe0ca974d6bca01be15987eb59b87e310248b952bcf62cdbe2` |
| `boot.pak` | 811,536 | `458d1fba9fb696319678f443935a701a37b56e8c0b8a19b3e0480abeed3a6dd2` |

CONFIRMED (local): these files exist under `firmware/lab/packages/`. The extraction workstream reports that each package is the exact concatenation of its declared segment payloads, with segment signatures verified and inter-package alignment excluded. This note independently hashes the resulting files; it does not repeat their cryptographic verification.

## LZ4P wrappers, not DOS executables

CONFIRMED (local/source): both `kern` and `lgap` start with `LZ4P`. The pinned epk2extract source recognizes that magic in `src/util.c`; its `src/lz4/lz4demo.c` reads a 32-byte header, a table of 32-bit compressed chunk sizes and successive compressed blocks. The header supplies the output block size and table length. This is a custom wrapper, not the standard LZ4 frame magic. See [recognition](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/util.c) and [decoder source](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/lz4/lz4demo.c).

| Field / structural check | `kern.pak` | `lgap.pak` |
| --- | ---: | ---: |
| Header word 1, interpreted as total output size | 5,191,748 | 23,601,152 |
| Header word 2 | 3,247,473 | 11,659,394 |
| Header word 3, output chunk size | 65,536 | 65,536 |
| Header word 4, chunk count | 80 | 361 |
| Compressed data begins | `0x160` | `0x5c4` |
| Sum of compressed chunk sizes | 3,247,121 | 11,657,918 |
| Data start + compressed-size sum | 3,247,473 | 11,659,394 |
| Remaining bytes after declared container | 5,376 (`0x1500`) | 5,376 (`0x1500`) |

CONFIRMED (local): header word 2 equals the table-derived container end in both files. Word 1 is consistent with the chunk count and implies final output chunks of 14,404 and 8,192 bytes respectively. LIKELY: word 1 describes total decompressed bytes; this interpretation awaits full bounded decoding. The reviewed legacy decoder does not itself validate those total-size words.

Both trailers contain nonzero data and all 256 possible byte values. Their hashes are recorded in `trailer-and-uimage-candidate.json`; their contents were not printed. The extraction workstream confirms these bytes belong to the original signed package payload, not padding appended by its extractor. PENDING: trailer format and purpose. Do not silently discard them from preserved package copies or classify them as a signature/key store without evidence.

RULED OUT (as a sufficient identification): treating an incidental `file` result suggesting DOS as proof of a DOS executable. The explicit wrapper and internally consistent size table are stronger format evidence.

## Kernel header clue and a false parsing trap

CONFIRMED (local): a U-Boot legacy-image magic occurs at compressed-file offset `0x162`. Parsing only the first LZ4 token shows that this begins a **20-byte literal run**, ending at `0x176`; the next bytes encode a back-reference. Thus it is incorrect to parse 64 contiguous source bytes there as a complete uncompressed image header.

The actual first literal establishes candidate header magic `0x27051956`, stored header CRC `0x42b200dc`, timestamp integer `1515636399`, declared image data size 5,191,684 and load field `0x00007fc0`. The data size plus a conventional 64-byte legacy header equals LZ4P word 1 exactly. LIKELY: the decoded kernel starts with a legacy uImage wrapper. Header/data CRC verification, architecture, entry point and compression fields remain PENDING until decoding reconstructs the complete header.

An intentionally rejected contiguous-header interpretation produced a mismatched CRC and an implausible entry value. That is a **parsing error caused by reading compressed tokens as header bytes**, not evidence of firmware corruption. The rejected candidate remains labeled as such in the local JSON evidence; do not promote its later fields to architecture facts.

Other magic matches, including ELF at `0x9b16f` and `0x2db60f`, and SquashFS at `0xe33ba`, are merely occurrences inside compressed data. They do not establish embedded files at those offsets. The literal text `Linux version 3.0.13` starts at `0x2631d2`; several `mtk5398_linux/kernel/` fragments are also present. These corroborate earlier platform clues but cannot substitute for the decoded kernel banner/configuration.

## Application and boot package clues

CONFIRMED (local): `lgap` has an ELF magic occurrence at `0x6d4`, within its compressed payload. Its first literal at `0x5c5` is only ten bytes and does not start with ELF. Therefore, neither direct parsing of the compressed ELF occurrence nor assuming the eventual output begins at an ELF header is justified. PENDING: the decoded application's outer wrapper, executable offset, interpreter, ABI, dynamic dependencies and entry semantics.

`boot.pak` has no leading LZ4P, ELF, standard LZ4, gzip, xz or uImage signature in the tested set. Its first 32-bit little-endian words are consistent with an ARM branch/vector-stub pattern (including `0xea000071` and repeated `0xe59ff018`). LIKELY: a raw ARM-oriented boot stage; this limited pattern analysis is not an instruction trace, physical CPU identification or complete bootloader classification.

Selected complete printable strings in `boot` are:

| Offset | String | Limit |
| --- | --- | --- |
| `0x43a8` | `EMMC boot` | A boot-path string, not proof of this unit's storage layout. |
| `0x4487` | `mt5398lge1_eu_linux` | Firmware build/platform identifier. |
| `0x33320` | `mt5398_LGE_linux` | Corroborates the MT5398 family hypothesis. |

No U-Boot version string was found by the bounded allowlist search. This does not prove U-Boot is absent, and an apparent uImage kernel wrapper does not prove which bootloader consumes it. Compressed or custom secondary boot stages remain PENDING. No credentials, keys, certificates or unrestricted string dumps were collected.

## Next safe analysis

1. Review a bounded LZ4 block decoder and validate all table ranges, per-block limits, cumulative output limits and exact declared output size. Decode only to an isolated local copy or bounded memory; preserve the trailers separately as uninterpreted data. The legacy epk2extract decoder trusts several sizes and is not the preferred unchecked parser for this experiment.
2. For the reconstructed kernel, validate the actual legacy header and data CRCs before recording architecture/entry fields; then identify the kernel payload and any configuration/initramfs without running it.
3. For reconstructed `lgap`, determine its wrapper before invoking `tools/elf_inventory.py` on a validated ELF boundary. That tool currently expects ELF at input offset zero and must not be pointed at the compressed file or an arbitrary magic occurrence.
4. Correlate the application interpreter/libraries with the mounted root/library packages and startup scripts. Boot strings alone establish neither a safe standalone renderer nor a recoverable launcher-replacement mechanism.

This task resolves outer formats and highlights exact next offsets; it does not authorize firmware rewriting, bootloader commands, root execution, autostart changes or any on-TV experiment.

## Reproducibility record

`format-inventory.json` contains package hashes and bounded magic matches. `wrapper-and-markers.json` records little-endian header/table calculations and selected platform markers. `first-literal-runs.json` records the initial LZ4 token interpretation. `trailer-and-uimage-candidate.json` records container boundaries, trailer hashes and the rejected raw-header interpretation. `boot-allowlisted-strings.json` contains only selected technical strings with offsets. All reads were bounded to packages smaller than 200 MiB, and files were opened read-only; no extracted content was executed.
