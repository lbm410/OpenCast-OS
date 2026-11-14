# EPK header layout and detection notes

Updated: 2026-11-14. Level 0 investigation: read public source/history and a bounded local firmware header. No extractor was compiled or executed, no cryptographic key values were read, and no TV operation occurred.

## Supported conclusion

The four-byte difference reported during FW-001 is real, but **does not demonstrate an upstream detection failure**. The observed version-string offsets match both an older EPK2 declaration and the current legacy EPK3 declaration. The pinned extractor can reach its generic EPK processing path through its EPK3 heuristic even when its EPK2 heuristic rejects this sample.

**CONFIRMED (source inspection and local data):** the pinned source's EPK3 version predicate matches the sample. **PENDING:** determine the actual container version from the protected header and validate its structure. The filename suffix `usb_V2_SECURED` alone cannot resolve the EPK2/EPK3 ambiguity. This note refines the earlier uncertainty in [firmware.md](firmware.md); it does not claim successful decryption, signature validation, or extraction.

## Sample and bounded observations

The input is the single EPK member of the official 04.28.17 distribution, preserved under `firmware/working/`. Its full filename and provenance are recorded in [firmware.md](firmware.md).

- Size: 640043464 bytes.
- SHA-256 from FW-001: `b8c15b5f3eefa3c4064bbf1b4da9dd857572e313a8a41a3c5cef89acdb024a7e`.
- This investigation read only its first 4096 bytes; it did not recompute the full-file hash.

| Offset | Observed field-sized bytes | Interpretation |
| --- | --- | --- |
| `0x6b0` | Four zero bytes | No preceding ASCII `V` or other visible version prefix. Whether this is reserved storage or part of a different preceding field remains unknown. |
| `0x6b4` | `0004.0022.1000` followed by two zero bytes | Exactly 16 bytes, containing two periods. |
| `0x6c4` | `03.05.000` followed by seven zero bytes | Exactly 16 bytes, containing two periods. |

These strings are not shifted by decoding, whitespace trimming, or a missing leading `V`. Their byte offsets are directly observed. Neither the EPK2 plaintext magic at `0x8c` nor the legacy EPK3 plaintext magic at `0x80` is present. That does not distinguish protected EPK formats.

## Source layout arithmetic

Current source is pinned to `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`. The sizes below follow the declared fixed-width fields; they were calculated without compiling the extractor.

| Source declaration | Bytes before `platformVersion` | Platform offset | SDK offset |
| --- | --- | --- | --- |
| Current EPK2, 64 image entries | 128-byte signature + (52 + 64 × 20)-byte header + 64 × 4-byte CRC block + 4-byte reserved field | `0x6b8` | `0x6c8` |
| Historical EPK2 before the reserved field was added | 128 + (52 + 64 × 20) + 64 × 4 | `0x6b4` | `0x6c4` |
| Current legacy EPK3 | 128-byte signature + 48-byte header + 384 × 4-byte CRC block + 4-byte reserved field | `0x6b4` | `0x6c4` |

Sources: [signature sizes](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk.h), [current EPK2 declaration](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk2.h), [current EPK3 declaration](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk3.h), and [historical EPK2 declaration](https://github.com/openlgtv/epk2extract/blob/119a914778975a166d6ae020a38051574a726907/include/epk2.h).

**CONFIRMED (documentary):** commit [`b80fad9c5d63f61642492503838c93d5e07b4017`](https://github.com/openlgtv/epk2extract/commit/b80fad9c5d63f61642492503838c93d5e07b4017), dated 2018-04-12, added `uint32_t reserved` between the EPK2 CRC array and the version fields. Its parent is `119a914778975a166d6ae020a38051574a726907`. This explains the source-history offset change. It does **not** establish that every older file omits the field, that every later file includes it, or that our 2019 firmware uses historical EPK2.

The later [2020 version-string commit](https://github.com/openlgtv/epk2extract/commit/0914ee8ade32c03f70b9d69d837e57ef851a6431) changed the four-byte `epakVersion` array from `char` to `uint8_t` and adjusted formatting; it did not move these string fields.

## What the current detector actually checks

The [current version predicate](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk.c#L278) counts periods across 16 bytes. Despite its descriptive comment, it does not validate that all other characters are digits. Its [counting helper](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/util.c#L101) also does not stop at a NUL byte.

Applying that predicate to the actual sample gives:

| Candidate fields | Periods in platform window | Periods in SDK window | Both windows pass |
| --- | --- | --- | --- |
| Current EPK2: `0x6b8`, `0x6c8` | 3 | 1 | No |
| Historical EPK2: `0x6b4`, `0x6c4` | 2 | 2 | Yes |
| Current legacy EPK3: `0x6b4`, `0x6c4` | 2 | 2 | Yes |

The current EPK2 platform window begins inside the first string and extends into the second string; this explains its three periods. The current EPK2 SDK window starts at `5.000` and has one period. This is a deterministic mismatch at those fixed offsets, not a cryptographic result.

The [main dispatch](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/main.c#L68) tests `isFileEPK2(file) || isFileEPK3(file)` before calling generic EPK processing. The [EPK2 detector](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk2.c#L38) and [EPK3 detector](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk3.c#L34) each accept either a matching plaintext header or their version-string heuristic. This sample is large enough for both minimum-size checks. Under the reviewed source logic, EPK2 detection returns false and EPK3 detection passes its version heuristic.

Passing that gate does not fix the final format to EPK3. [Generic EPK processing](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk.c#L285) attempts header identification/decryption and then dispatches using the actual recognized EPK2/EPK3 variant. The [header comparison function](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk.c#L34) checks the supported variants separately. This path was inspected only; no cryptographic operation was run.

## Decision and remaining uncertainty

- **RULED OUT:** treating the four-byte discrepancy alone as proof that current upstream cannot detect this file.
- **RULED OUT:** explaining the observed offsets as a removed leading `V`; the preceding four bytes are zero and the fields are read directly.
- **HYPOTHESIS:** legacy EPK3, because its current version-field layout matches exactly.
- **HYPOTHESIS:** an EPK2 variant matching the historical no-reserved-field declaration. The same version offsets support this alternative too.
- **PENDING:** actual protected-header magic, image/package table interpretation, declared model/OTA fields, signature coverage, and cryptographic validity. No partition, ABI, or boot conclusion follows from the heuristic alone.

Do not patch a global offset or choose an old extractor solely to make the version strings line up. A future controlled analysis should first establish the protected header's format, then validate table sizes/offsets against the complete file before extracting internal images. Any extractor evaluation must remain pinned, reviewed, resource-bounded, unprivileged, and separate from installation or device access.

## Experiment FW-002

- **Objective:** resolve the concrete version-field offset discrepancy and determine its effect on current detection.
- **Hypothesis:** source layout history or another supported detector path explains why the observed strings start four bytes earlier.
- **Environment:** local preserved EPK; first 4096 bytes only; public GitHub source/history at pinned commits; 2026-11-14.
- **Procedure:** calculate fixed-field offsets → inspect the 2018 and 2020 diffs → read current detector/helper/dispatch code → count periods in the exact candidate windows using local Python.
- **Expected result:** a source-supported explanation or a precisely bounded unresolved format question.
- **Observed result:** the 2018 EPK2 change adds four bytes; current legacy EPK3 and historical EPK2 both match the sample offsets. Current EPK3's heuristic passes, while current EPK2's does not. Generic dispatch remains reachable by source logic.
- **Conclusion:** the detection-offset concern is explained; the actual protected container variant remains unverified. No extractor failure or success has been observed at runtime.
- **Risks:** interpreting heuristic recognition as authentic format validation, or changing offsets before validating protected metadata. No keys, decryption, compilation, TV writes, or extracted-code execution were involved.
- **Next step:** assess a separate bounded protected-header verification workflow; only after structure validation should internal image inventory begin.
