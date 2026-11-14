# Controlled firmware extraction

Updated: 2026-11-14. Level 0 only. No television access, firmware execution, installation, privileged operation or persistent change occurred during this workstream.

## Result

**CONFIRMED (local, cryptographic and structural):** the official 04.28.17 EPK is **EPK2 using the historical layout without the extra reserved word**, not EPK3. The protected header decrypts to `epak` and `EPK2`. Its 24 image entries describe 118 segments. Every image boundary, segment sequence, package length and the final file boundary is accounted for.

The header signature verifies over exactly 1,588 ciphertext bytes, using RSA-1024 PKCS#1 v1.5 and SHA1(SHA1(ciphertext)), with the public `mtk5398.pem` file from the pinned upstream source. Eleven explicitly selected packages were copied after **all 77 of their segment signatures verified over their exact declared header-plus-data spans**. No decrementing-length retry, ignored verification error or permissive truth-value check is used.

This verifies consistency against the supplied public key. It is not an independently established LG certificate chain, an assurance that all other segments were verified, or permission to install this image. Version strings outside the signed span are recorded as metadata, not authenticated fields.

**CONFIRMED (local ELF metadata):** the selected `busybox`, dynamic loader, libc, `lginit` and `lginit_app` files are ARM32, little-endian, EABI5. Dynamically linked examples request `/lib/ld-linux.so.3`. The loader/libc files are named `ld-2.12.2.so` and `libc-2.12.2.so`; `lginit` is statically linked. This identifies binaries in the applicable official firmware, not a direct physical silicon or RAM measurement. The DLNA `i686` banner is unsuitable as evidence of the firmware CPU architecture.

## Provenance and preservation

The original ZIP and explicitly copied EPK remain mode `0444`, ignored by Git. Their hashes were recomputed after this work and remain unchanged:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Original ZIP | 638858259 | `3fcf21d2e899eb587171335d52bde86aa672837797037a51b1916f117c838695` |
| Original EPK and deliberate lab copy | 640043464 | `b8c15b5f3eefa3c4064bbf1b4da9dd857572e313a8a41a3c5cef89acdb024a7e` |

The lab copy is `firmware/lab/input.epk`. The preserved source paths and official applicability evidence are in [firmware.md](firmware.md). The preservation report is `artifacts/firmware-lab/preservation.json`.

The upstream checkout is confined to ignored `artifacts/vendor/epk2extract`, pinned to `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`. Publicly distributed container-analysis keys stay there. No key values are embedded in project files, reports or documentation. The matching AES entry is identified only by the upstream label `mtk5398 (a2)` and its source location. No DRM/PVR content was processed.

## Why a small independent reader

Reviewed source: [generic EPK processing](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk.c), [EPK2 layout](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk2.h), [EPK2 extraction](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk2.c), [key handling](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/util_crypto.c), and main dispatch.

The upstream general-purpose extractor was **not built or executed**. Its reviewed paths print key bytes, use untrusted package names for output paths, recurse into extracted formats, and contain a signature wrapper which reduces the candidate signed length and treats nonzero OpenSSL results as success. Its `-n` flag only suppresses automatic SquashFS extraction. These behaviors are unsuitable for the first bounded analysis.

`tools/firmware_lab.py` instead implements only the observed EPK2 layout. It validates the signed header before interpreting package locations, bounds all reads, rejects gaps larger than three alignment bytes, duplicate/unsafe names, inconsistent segments, overflows, unexpected trailers and aggregate-size mismatches. Extraction requires explicit package names and a new output directory. Failed current-file writes are removed; previously completed verified files may remain. Extracted content becomes read-only regular files. There is no recursive filesystem extraction or firmware execution.

The optional cryptographic dependency and transitive dependencies are pinned in `requirements-firmware.txt`; installed only in ignored `artifacts/firmware-lab/venv`. Host diagnostics do not acquire this dependency. The CLI imposes CPU, output-file, descriptor and wall-clock limits. The observed run also used a macOS sandbox denying networking and writes outside lab directories. The reader intentionally does not support every historical/new EPK variant.

## Actual header and layout

| Field | Observed value |
| --- | --- |
| Decrypted file/header magic | `epak` / `EPK2` |
| Internal four-byte version | `04.28.17.01` |
| OTA ID | `HE_DTV_NC4M_AFAAABAA` |
| Image count / total segment count | 24 / 118 |
| Declared aggregate image bytes | 640026604 |
| Platform version at `0x6b4` | `0004.0022.1000` |
| SDK string at `0x6c4` | `03.05.000` |
| First package signature offset | 1748 / `0x6d4` |
| Aggregate inter-package alignment | 8 bytes |

The whole-file equation is `1748 + 640026604 + (118 × 128) + 8 = 640043464`. The aggregate image size includes package headers and excludes signatures. This resolves the earlier EPK2/EPK3 ambiguity in [epk-format-notes.md](epk-format-notes.md): EPK3's version heuristic happens to match, but the actual decrypted format is historical EPK2.

## Package inventory

Sizes below are decoded package payload bytes, excluding EPK signatures and package headers. An extracted package is still a container/image; it has not been installed, mounted or executed.

| Package | Payload bytes | Segments | Locally copied / format |
| --- | ---: | ---: | --- |
| part | 12368 | 1 | Yes; partition metadata candidate |
| swue | 29144320 | 5 | Yes; SquashFS4 zlib |
| crc3 | 256 | 1 | No |
| mode | 4096 | 1 | No |
| lgap | 11664770 | 2 | Yes; compressed application candidate; separate triage |
| lgin | 263424 | 1 | Yes; SquashFS4 zlib; `lginit`, `lginit_app` |
| lgre | 43745280 | 7 | No |
| lgfo | 40964096 | 7 | No |
| logo | 87645 | 1 | No |
| patc | 9472 | 1 | No |
| vend | 5436672 | 1 | Yes; SquashFS4 zlib |
| pqld | 53248 | 1 | No |
| open | 25974016 | 5 | Yes; SquashFS4 zlib |
| estr | 11031808 | 2 | No |
| eman | 98645248 | 16 | No |
| lgli | 33629440 | 6 | Yes; SquashFS4 zlib |
| base | 325559552 | 52 | Yes; SquashFS4 zlib |
| tpli | 8192 | 1 | No |
| tzfw | 488328 | 1 | No |
| extr | 9472 | 1 | No |
| boot | 811536 | 1 | Yes; separate boot triage |
| kern | 3252849 | 1 | Yes; compressed kernel candidate; separate triage |
| root | 9028864 | 2 | Yes; SquashFS4 LZO |
| mico | 186548 | 1 | No |

Most package headers label the model `DVB-BB-MTK5398`; `boot`, `kern` and `root` use `MTK_BOOT`, `MTK_KER` and `BCM_ROOT`. Those are actual strings, not separate proofs of the silicon vendor. In particular, `BCM_ROOT` must not override ARM ELF evidence or the other MTK metadata.

## Filesystem handling

The host had no `unsquashfs`. Homebrew fetched and verified the **SquashFS tools 4.7.5 ARM64 Tahoe bottle**. Only its explicitly named regular-file `bin/unsquashfs` member was copied into the ignored lab. Four library paths were relocated to already installed Homebrew dependencies and the local host executable was ad-hoc signed. No package was installed globally. Host-tool provenance/hashes are in `artifacts/firmware-lab/host-tool.json`.

`tools/firmware_lab_squashfs.py` uses **list and cat modes only**, one worker, 64 MiB caches, a 30-second CPU/45-second wall bound, bounded output, and a macOS sandbox denying all path writes, network access and execution of other binaries. The parent captures stdout, checks a selected regular file against the preceding inventory, creates a new output tree and writes it mode `0444`. No vendor symlink, device node, ownership, executable permission or extended attribute is recreated. Symlink targets are retained as inventory metadata only. The helper is currently macOS-specific because it relies on `sandbox-exec`.

Selected copies:

- `firmware/lab/root-selected/`: `inittab`, initial scripts, DirectFB/SaWMan configuration, `busybox`, loader and libc.
- `firmware/lab/root-startup/`: the regular files in `etc/init.d/` and `etc/scripts/`, selected individually after listing.
- `firmware/lab/lgin-selected/`: `lginit` and `lginit_app`.
- `firmware/lab/base-selected/`: home manifest, SU2 launcher/application XML and `browser/bin/lb6wk`.

Full metadata inventories for root, lgin, base, lgli, open and vend are in `artifacts/firmware-lab/*-inventory.json`. Their presence alone does not establish which paths/processes are active on the owner's running TV. The update image may contain generic or unused files.

## Reproduction

After separately reviewing/downloading the official image and the pinned public key source:

```sh
python3 -m venv artifacts/firmware-lab/venv
artifacts/firmware-lab/venv/bin/pip install -r requirements-firmware.txt

# Read-only manifest. Use the offline sandbox profile recorded in the lab.
/usr/bin/sandbox-exec -f artifacts/firmware-lab/offline.sb \
  artifacts/firmware-lab/venv/bin/python -B -m tools.firmware_lab firmware/lab/input.epk \
  --key-file artifacts/vendor/epk2extract/keys/AES.key \
  --public-key artifacts/vendor/epk2extract/keys/mtk5398.pem

# Deliberate package copying; destination MUST NOT already exist.
/usr/bin/sandbox-exec -f artifacts/firmware-lab/offline.sb \
  artifacts/firmware-lab/venv/bin/python -B -m tools.firmware_lab firmware/lab/input.epk \
  --key-file artifacts/vendor/epk2extract/keys/AES.key \
  --public-key artifacts/vendor/epk2extract/keys/mtk5398.pem \
  --package root --package lgin --output-dir firmware/lab/reproduction-packages

python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/root.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --select etc/inittab --output-dir firmware/lab/reproduction-root

artifacts/firmware-lab/venv/bin/python -B -m unittest discover -s tests -p 'test_firmware_lab.py' -v
```

The sandbox profile and host tool are local lab artifacts, not automatically installed by these commands. Review their provenance and paths before recreating a lab on another host. The profile permits only lab-directory writes and denies networking. Do not substitute an unrestricted recursive extraction command.

## Experiment FW-003

- **Objective:** classify the protected container, verify integrity and expose selected startup/ELF files without modifying the TV.
- **Hypothesis:** one of the documented EPK layouts and public container-analysis key entries can produce a bounded, internally consistent image table.
- **Environment:** Apple M4 macOS 26.6.2; preserved official EPK; pinned upstream source; isolated Python cryptography 50.0.2; local ARM64 unsquashfs 4.7.5; offline parsing sandbox.
- **Procedure:** inspect source → deliberately copy EPK → try bounded header decryption without printing keys → recognize EPK2 → verify exact header signature → validate all 24 image/118 segment boundaries → explicitly select eleven packages → verify 77 segment signatures → copy payloads → inventory SquashFS → copy selected regular files via cat → inspect ELF headers → rehash originals.
- **Expected result:** verified format/table and selected static evidence, or precise refusal before unsafe extraction.
- **Observed result:** initial EPK3-only hypothesis was rejected without writing packages; EPK2 magic and historical offsets matched. Header and selected segment signatures passed, all structural sizes reconciled, originals remained unchanged, and ARM32 startup binaries/configuration became available. No privileged or firmware code ran.
- **Conclusion:** native architecture and startup dependencies can now be studied from authenticated image spans. This materially advances platform analysis; it does not establish a deployable custom launcher, physical SoC/RAM measurement, autostart path available to an app, or recovery.
- **Risks:** malformed native parser inputs, misidentifying unused update contents as active runtime behavior, overclaiming public-key provenance, and accidental vendor redistribution. Mitigations were bounded list/cat execution, strict signatures, ignored read-only artifacts and explicit scope labels.
- **Validation:** eight synthetic tests passed in the optional venv (bounds, malformed metadata, path traversal, symlink metadata, invalid segments, aggregate lengths, exact signature mutation/wrong-key rejection and destination preservation). Standard-library-only runs pass four boundary tests and explicitly skip four cryptography-dependent tests. Validated the real manifest again after adding aggregate-size checks.
- **Next step:** correlate `lginit`, startup scripts, launcher XML, graphics/input libraries and the compressed `lgap`/kernel/boot payloads. Establish recovery independently before proposing any privileged or persistent device experiment.
