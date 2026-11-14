# Official firmware 04.28.17

Updated: 2026-11-14. Scope: level 0 local analysis. Nothing has been installed or executed on the television.

## Current result (supersedes initial triage limitations below)

See [controlled extraction](firmware-extraction.md), [kernel/RELEASE decoding](lz4p-analysis.md), and [boot dependency map](boot-dependencies.md). Historical EPK2 is now confirmed; a separate full audit verifies the header and all118 segments against the supplied upstream public key. Historical extraction verified77 segments of11 selected packages. Selected files were copied for static inspection. Kernel Linux3.0.13 and ARM32 little-endian EABI5 userspace are confirmed in the firmware. Original hashes remain unchanged. Public-key consistency is not independent LG trust-root attestation, and no device recovery is demonstrated. The following sections preserve the earlier FW-001 investigation and its then-current uncertainties.

## Provenance and integrity

**CONFIRMED (documentary):** the [official LG Croatia reference](https://www.lg.com/hr/podrska/proizvod/lg-47LA620S.AEE) explicitly includes `47LA620S-ZA` in the applicable model list for 04.28.17, published on 2019-04-11. This establishes the manufacturer's declared applicability, not the physical identity or partition layout of the unit.

Official download URL, obtained from that support page:

`https://gscs-b2c.lge.com/downloadFile?fileId=sUBHf2CanZ7Vf6ITuCow`

The integration agent downloaded the original over HTTPS on 2026-11-14 after the analysis agent's first attempt failed because DNS access was restricted. The successful download used the integration session's effective permissions, without circumventing restrictions in the analysis session. The original is preserved with mode `0444`. Headers from the successful HTTP download were not retained; `artifacts/firmware/download-headers.txt` is an empty file from the failed attempt, not provenance evidence.

| Local artifact excluded from Git | Size | SHA-256 |
| --- | --- | --- |
| `firmware/originals/Software_File_04.28.17.zip` | 638858259 bytes | `3fcf21d2e899eb587171335d52bde86aa672837797037a51b1916f117c838695` |
| EPK member copied into `firmware/working/` | 640043464 bytes | `b8c15b5f3eefa3c4064bbf1b4da9dd857572e313a8a41a3c5cef89acdb024a7e` |

Hashes were calculated from complete file reads and match between download/inventory for the ZIP and extraction/inspection for the EPK. They support reproducibility and change detection; **they do not constitute verified digital signatures**. No signed reference hash published by LG has been obtained.

## Observed results

**CONFIRMED (local):** classic ZIP, one regular member, deflate compression, no ZIP encryption, and no duplicate names. Its central directory is 147 bytes long at offset 638858090. Exact member name:

```text
NC4_DVB_EU_MP1_SU2_mtk5398_A2_official-build-nc40-eu-m13-42817RevNo62064_V04.28.17_usb_V2_SECURED.epk
```

Compressed member size: 638857959 bytes. CRC32 declared and verified by reading the entire member: `f7aec78e`. Only that member was copied, without `extractall`, and its mode was set to `0444`. No internal partitions have been extracted.

**LIKELY:** the distributor's naming points to MTK5398/M13, revision A2, NetCast 4.0, and a secured V2 USB package. The name is actual metadata from the official archive, but does not independently identify the television's silicon, RAM, ABI, or board revision. Cross-check against internal metadata and device evidence.

**CONFIRMED (device, self-reported):** the integration agent subsequently received a UDAP announcement identifying `47LA620S-ZA/04.28.17` and `Linux/3.0.13`. A DLNA announcement contains the contradictory architecture label `Linux/i686`. Evidence: `artifacts/diagnostics/ssdp-retry.json` and the UDAP/DLNA descriptor reports in the same ignored directory. These unauthenticated service declarations corroborate the model/firmware report and provide a kernel-version lead; they do not prove the physical CPU architecture. Do not let the DLNA banner override firmware ELF or hardware evidence that has yet to be collected.

**CONFIRMED (local):** `file` identifies the ZIP and classifies the EPK as `data`. Its first 16 bytes are `c04ce583ff7c2f13aef1ddc4dba688d6`; they do not contain a directly recognized filesystem header. `EPK2` is absent at offset `0x8c` in the sample. The first 4096 bytes contain:

| EPK offset | Readable text | Interpretation |
| --- | --- | --- |
| `0x6b4` / 1716 | `0004.0022.1000` | Candidate platform-version metadata; exact semantics pending. |
| `0x6c4` / 1732 | `03.05.000` | Candidate internal SDK version; consistent with the user's reported 03.05, without establishing equivalence to public SDK 3.0.1. |

Sample entropy is 7.6082 bits/byte. This is a small-window measurement, not proof of encryption, its algorithm, or security strength. **HYPOTHESIS:** a protected/encrypted EPK2 container, based on the naming and metadata arrangement. This hypothesis has not been cryptographically validated.

Local execution reports, excluded from Git:

- `artifacts/firmware/original-inventory.json`: ZIP, hash, member, and header sample.
- `artifacts/firmware/member-extraction.json`: complete member copy, hash, and CRC verification.
- `artifacts/firmware/epk-header.json`: independent hash and observed offsets.

## epk2extract assessment

Source reviewed without building or executing it: commit `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`. The review covered README, build.sh, EPK/EPK2 headers, identification and extraction paths, header history, and the issues listed in [platform-research.md](platform-research.md). Manufacturer key values were not read or stored during this assessment.

The initial offset discrepancy has now been explained at the detector level; see [the follow-up format investigation](epk-format-notes.md). Full container classification still requires header validation. The [EPK2 structure](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk2.h), combined with the [128-byte signature](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk.h), places `platformVersion` and `sdkVersion` at `0x6b8` and `0x6c8` for the 64-entry table. In our sample both strings start four bytes earlier. The structure includes a four-byte `reserved` field after the CRC block; its presence in this specific variant needs verification.

**CONFIRMED (local/documentary):** the offsets differ from the current EPK2 structure, but match both its older layout and the current legacy EPK3 layout. The current EPK3 predicate supplies a route into generic encrypted-header processing. No parser failure has been reproduced. **PENDING:** validate the actual container type and integrity; do not globally patch offsets or infer the format from the filename.

Upstream detection uses version strings and decryption/verification paths, so the absence of a plaintext magic value does not rule out EPK2. Further evaluation must use a copy, a pinned commit, reviewed dependencies, and bounded CPU/memory/output without privileges. Do not follow instructions requesting sudo to create device nodes. Signature verification, content decryption, and generating an installable package are separate operations.

## Reproducible project tool

`tools/firmware_analysis.py` uses only the Python standard library. Limits: 2 GiB per input file, 1 GiB per member, 4 MiB for the central directory, and 256 entries. It rejects ZIP64, multidisk archives, special file types, symlinks, dangerous paths, unsupported methods, and compression ratios above 1000. A valid structure outside those limits requires explicit review, not automatic relaxation.

Inventory and triage without extraction:

```sh
python3 -m tools.firmware_analysis inspect firmware/originals/Software_File_04.28.17.zip
```

Deliberately copy one member; the command fails if its destination already exists:

```sh
python3 -m tools.firmware_analysis extract-member firmware/originals/Software_File_04.28.17.zip \
  --member 'NC4_DVB_EU_MP1_SU2_mtk5398_A2_official-build-nc40-eu-m13-42817RevNo62064_V04.28.17_usb_V2_SECURED.epk' \
  --output-dir firmware/working
```

Offline validation:

```sh
python3 -m unittest discover -s tests -p 'test_firmware_analysis.py' -v
```

**CONFIRMED (local):** all 10 tests passed on 2026-11-14, covering corrupt CRC, incomplete-output cleanup, destination preservation, unsafe names, symlinks, duplicates, limits, and rejected ZIP variants. These test the analysis tool, not firmware operation on hardware.

The tool does not treat discovered strings as hardware identification, verify signatures, decrypt content, execute firmware, or contact the television. CRC verification is reported only after the complete member has been consumed.

## Experiment FW-001

- **Objective:** establish a reproducible original and identify the container without modifying the TV.
- **Hypothesis:** the official ZIP contains a NetCast update whose header provides platform metadata.
- **Environment:** ARM64 Mac, Python 3.13.5; official original downloaded by the integrator, offline analysis; 2026-11-14.
- **Procedure:** verify size/hash → preflight EOCD and ZIP directory → inventory → validate member → copy only that member with CRC → independently hash it → inspect the first 4096 bytes and compare the public structure.
- **Expected result:** unchanged original, traceable copy, platform leads, and a justified extraction plan.
- **Observed result:** the hashes and sizes above; one member; valid CRC; MTK5398/M13 name; two version strings; a four-byte difference from the reviewed EPK2 structure.
- **Conclusion:** a specific official sample is now available for reverse engineering. Partitions, ABI, kernel contents, and launcher have not been identified by this firmware analysis. Documentary model compatibility and CRC do not validate installation.
- **Risks:** untrusted-file parsers, mistaking naming for hardware proof, and confusing encryption with corruption. Mitigations: limits, immutable originals, offline tests, and no execution of extracted files.
- **Next step:** use the detector findings in FW-002 to evaluate controlled header classification and cryptographic verification separately. Then inventory init, ELF files, libraries, graphics, power/watchdog services, and recovery mechanisms. This analysis grants no authorization to write to the TV.

## Pending before native execution or boot integration

Authentic partitions and offsets; storage type; bootloader and signature policy; kernel/configuration; init; ELF-verified architecture and ABI; libc and dynamic interpreter; graphics/input ownership; HDMI/tuner/audio dependencies; MICOM/watchdog; updater and an independent recovery path. A firmware update ZIP is not a complete device backup.

## Additional extractor execution review

The pinned [src/main.c](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/main.c) defaults signature checking to disabled; `-s` enables checking and `-S` requests signature-only mode. `-n` disables automatic SquashFS unpacking, not every recursive extraction path. Generic handlers also process compressed/kernel/filesystem data and some output paths are removed before extraction. Therefore `-n` alone is not an adequate boundary for arbitrary firmware analysis. A future run must use an isolated fresh working copy, constrained output paths/resources, reviewed key provenance and explicit choices about recursion and signature verification. No such extractor run has occurred.

The reviewed top-level and src CMake files select OpenSSL, LZO, zlib, threads and bundled format libraries. Host inspection found CMake4.3.4, LZO2.10 and OpenSSL3 installed; no separate Homebrew zlib package was listed. This is an availability check, not a successful build. The source has not been compiled locally.
