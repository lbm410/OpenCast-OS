# Reviewed LZHS boot-stage analysis

Date: 2026-11-14. Scope: local static analysis of the officially sourced 04.28.17 update. **CONFIRMED (local, firmware-static):** two compressed boot stages have been independently decoded with exact sizes, additive checksums and SHA-256 hashes matching the earlier scratch results. No firmware bytes, upstream decoder or scratch decoder were executed. No television, network or Git operation was performed for this experiment.

This promotes the decoded byte/string findings from the independent scratch review from unreviewed scratch leads to reproducible local evidence. It does **not** validate that report's inferred runtime branches. No installed replacement, running boot-console access, active command line or recovery capability follows from this result.

## Provenance and source review

Input: `firmware/lab/packages/boot.pak`, 811,536 bytes, SHA-256 `458d1fba9fb696319678f443935a701a37b56e8c0b8a19b3e0480abeed3a6dd2`. Its hash was checked again after decoding and remained identical. The package remains read-only. Earlier extraction/signature evidence belongs to [the firmware report](firmware.md); this experiment does not repeat or expand its authentication claims.

The scratch decoder identified in `collaboration/messages/to-codex-003.md` was read as source, not run. Its SHA-256 is `988d2722521092126fc7714caaf585b2b81efc9863edbd22cb5b59d31d75200a`. Review found a comprehensible Huffman/LZSS/Thumb implementation, but its assertions disappear under Python optimization, it expands compressed bytes into a large bit string, accepts partial EOF, clips oversized output, merely reports a checksum mismatch, and overwrites destinations. Those weaknesses motivated an independent bounded implementation.

Format references were read from the existing source snapshot of `openlgtv/epk2extract` at commit `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`:

- [Header and constants](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/lzhs/lzhs.h): 16-byte header, 4,096-byte dictionary, maximum match length 34.
- [Huffman/LZSS source](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/lzhs/lzhs.c): `huff` line 235, `unhuff` line 274, `unlzss` line 439; the encoder emits a final zero-padded byte even when already aligned.
- [Filter and checksum](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/lzhs/lzhs_lib.c): `ARMThumb_Convert` line 54, additive checksum line 120, decode/filter/checksum order around lines 289–317.
- [Code tables](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/lzhs/tables.h), SHA-256 `fef168a1b235a43f5886151d4b89b86d9b885308692340ee83b5356088eb8b17`. The host tool reads this exact file as data and refuses a different digest. It does not evaluate C or run vendored code.

## Supported decoder profile

`tools/lzhs_inspect.py` uses only Python's standard library. It accepts an explicit header offset; it does not scan for or automatically extract further objects. Header fields are little-endian `uint32 uncompressedSize`, `uint32 compressedSize`, `uint16 checksum`, followed by six reserved bytes. This **boot-stage profile** requires the checksum's upper byte and all reserved bytes to be zero; other upstream uses of that field as a segment number are outside scope.

The decoder reads MSB-first Huffman bits directly. Literal symbols are 0–255; symbols 256–287 encode match lengths 3–34. A position symbol supplies the upper five distance bits and seven raw bits supply the remainder. The 4,096-byte circular dictionary begins filled with zeros. Distance zero is valid for this format and references the current ring slot, including already wrapped dictionary content. Matches may overlap. The final Thumb BL transform is reversed before computing the 8-bit byte-sum checksum.

Bounds: input 16 MiB, compressed stream 4 MiB, declared output 16 MiB, table source 64 KiB. Sizes are checked before output allocation. Prefix tables must have the reviewed dimensions, valid bounded codes and no ambiguous prefixes. The decoder rejects truncated tokens, output overshoot, checksum mismatch and more than eight residual bits or nonzero residual padding. Only the two reviewed blocks have been exercised with real firmware; this is not a claim of universal LZHS support.

Input and output path traversal uses directory descriptors with `O_NOFOLLOW`; symlinks, parent traversal and nonregular inputs are rejected. Output is optional, exclusively created, non-executable and changed to mode `0444` after successful writing. No destination is overwritten. An I/O failure during output writing can leave an incomplete artifact; a successful decode report is required before using a saved file. Run the tool against trusted local directories, not concurrently modified trees.

## Reproduced results

Offsets below refer to the uncompressed **package file**, not flash addresses. Decoded offsets in the next section refer to the respective output, not to the compressed package.

| Header offset | Compressed payload range, end exclusive | Compressed bytes | Decoded bytes | Checksum | Residual padding |
| --- | --- | ---: | ---: | --- | ---: |
| `0xA040` | `0xA050`–`0x330E0` | 168,080 | 337,704 | `0x4d`, matches | 5 zero bits |
| `0x80000` | `0x80010`–`0xC600C` | 286,716 | 545,624 | `0xa6`, matches | 5 zero bits |

| Stage | SHA-256 of compressed payload | SHA-256 of decoded bytes |
| --- | --- | --- |
| `0xA040` | `cf9eef8c3ccef08afd572fc5474ceb382d4353fc1eceb1a0f8a9c5d704769dce` | `256e09dbb59a8ecd1900b49b8199a1c92720e71d6a21d14b6ab3215d85bcda00` |
| `0x80000` | `c4bc8559e150b6929b4eb4a4988427a9fa2311f640808bb594ba618c7637e4b9` | `11d6616752416c42b40d167de92ae48a190f16d24f9c33dbc2b8ba93ef7a20c7` |

The first stage consumes 1,344,635 Huffman bits, 102,187 literal tokens and 32,388 match tokens; 7,382 Thumb patterns are converted. The second consumes 2,293,723 bits, 130,820 literal tokens and 74,725 match tokens; 143 Thumb patterns are converted. Pattern-conversion counts describe the transform, not an instruction-level census.

Ignored, read-only evidence under `artifacts/bootloader-analysis/`:

- `boot-a040.bin`, `boot-80000.bin`: independently produced decoded bytes; not redistributed.
- `boot-a040.json`, `boot-80000.json`: bounds, hashes, checksum, padding, token counts, decoder hash and capture time.
- `markers.json`: bounded allowlisted printable contexts and exact offsets.
- `service-marker-counts.json`: exact case-sensitive counts for the small documented service vocabulary.

An additive checksum is an error-detection field, **not** a signature or authentication mechanism. Matching the independently reported SHA-256 values confirms reproduction of the earlier output; it does not prove live-device state.

## Embedded identity and boot options

All rows are **CONFIRMED (local, firmware-static)** as string bytes. A string's presence alone is not control-flow evidence.

| Decoded stage | Match offset | String or bounded context | Meaning and limit |
| --- | --- | --- | --- |
| `0xA040` | `0x3e041` | `MT5398 Boot Loader v%u.%u` | Loader-family label in this shipped image; not physical CPU identification. |
| `0x80000` | `0x642dc` | `U-Boot 1.3.4-svn (Mar 20 2014 - 07:58:10)` | Embedded version/build banner; not proof of an available console or running version. |
| `0x80000` | `0x6ea15` | `Enable Watchdog` | A watchdog-related diagnostic exists; activation, timeout and ownership remain unresolved. |
| `0x80000` | `0x6eccd` | `should be verify before bootm` within the string starting at `0x6eca4`, naming `Kernel/lgapp/lginit` | Suggests a verification path worth tracing; does not establish enforcement, keys, failure behavior or active secure state. |
| `0x80000` | `0x7bdeb` | `rootfstype=squashfs`; enclosing string at `0x7bddc`: `root=/dev/%s%d rootfstype=squashfs ` | A formatted root-selection fragment exists; substitutions and chosen partition are unknown. |
| `0x80000` | `0x7be09` | `bootdev=emmc`; enclosing string at `0x7be00`: `rootwait bootdev=emmc ` | eMMC boot argument fragment; not an observed command line. |
| `0x80000` | `0x7be17` | `lginit=/dev/%s%d ` | Another formatted partition argument; no live mapping established. |
| `0x80000` | `0x7be5a` | `bootmode=%s ` | Mode placeholder exists; selected value and selector remain untraced. |
| `0x80000` | `0x7be67` | `init=/sbin/init ` | A PID-1 selection fragment exists; runtime PID 1 remains unobserved. |
| `0x80000` | `0x74764`, `0x7476c`, `0x74784`, `0x7be80` | `swumode`, `swumode`, `swumode [on/off]`, `swumode ` | Mode vocabulary/help/argument fragments exist; reachable update or recovery behavior is unproven. |
| `0x80000` | `0x6456a`, `0x7291a`, `0x72972` | `env_nvm`, `env_nvm`, `env_nvm partition not found.` | Environment-partition references exist; no stored environment was read. |

The command-line items are separate null-terminated fragments. Their proximity supports investigating a command-line builder, but does not prove that every fragment is combined in one invocation or that the owner's unit takes that path. The exact markers `procmgr`, `svclist` and `/usr/local/bin/procmgr` occur zero times in each decoded stage. That bounded negative finding does not rule out service control indirectly; service selection remains a userspace dependency question in [boot dependencies](boot-dependencies.md).

**LIKELY:** this shipped boot image contains a MediaTek-family loader and an older U-Boot-derived next stage, consistent with the independently identified firmware family. **PENDING:** actual branch order, load/entry addresses, stored environment values, partition selectors, secure-boot decisions, watchdog policy and physical hardware identity. No command in the strings should be treated as an authorized or safe procedure.

## Reproduction and validation

From the repository root, with the existing pinned source snapshot available:

```sh
python3 -m unittest tests.test_lzhs_inspect -v
python3 -m tools.lzhs_inspect firmware/lab/packages/boot.pak --offset 0xa040
python3 -m tools.lzhs_inspect firmware/lab/packages/boot.pak --offset 0x80000
```

These invocations only report JSON. To save independently decoded bytes, supply `--output` with a **new** filename in an existing ignored artifact directory. The already saved evidence filenames must not be reused; the tool will refuse them. No shell, emulator or executable loader is involved.

Observed result: **13 tests passed**. Tests use synthetic prefix tables and payloads, not vendor firmware fixtures. Coverage includes literal/aligned padding, overlapping matches, zero-filled and wrapped dictionary references, Thumb conversion and checksum order, malformed headers/sizes/offsets, truncated Huffman/position/raw-bit fields, output overflow, bad padding, ambiguous tables, pinned-source rejection, safe input types, symlink refusal, exclusive read-only output and failure before artifact creation. One initial dictionary test accidentally contained Thumb instruction signatures; its fixture was corrected to isolate dictionary behavior. This was a test-fixture issue, not a relaxed decoder check.

## Experiment record and next step

- **Objective:** reproduce the two reported boot-stage outputs with a reviewed, bounded tool and validate the cited boot-option strings.
- **Hypothesis:** the known offsets contain the boot LZHS profile implemented by the pinned source, and complete output can be obtained without permissive truncation.
- **Environment:** existing local officially sourced package, existing pinned source tables, host Python standard library; no TV connection.
- **Procedure:** inspect untrusted scratch/source; implement and test independent direct-token decoding; decode both explicit offsets; require exact lengths, padding and checksums; compare hashes; save read-only artifacts; perform only bounded marker inspection; recheck original hash.
- **Expected result:** either exact reproduction or a precise format/validation failure, with no execution or mutation of original firmware.
- **Observed result:** both hashes and checksums match, both have five zero padding bits, cited strings are present at the reported offsets, original unchanged.
- **Conclusion:** decoded-byte evidence is now reproducible. Runtime claims and recovery remain open.
- **Risks:** malformed-input resource use is bounded, but this small parser is not a general firmware security audit; output is still untrusted target data. No on-device risk was introduced.
- **Next step:** statically locate references to command-line fragments, `swumode` and the watchdog/verification messages, then trace their branch conditions and inputs against the partition and userspace evidence. Do not infer recovery until an independently usable path is demonstrated for this exact television. No boot modification, command invocation or environment write is proposed by this report.
