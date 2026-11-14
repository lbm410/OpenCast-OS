# Partition-map format and redundancy evidence

Updated: 2026-11-14. Read-only static analysis of the signed official update's `part.pak`. No television access, device dump, mount, firmware execution or flash operation occurred.

## Supported result

**CONFIRMED (local/source):** `part.pak` is an exact match for the **LG partinfo v2 structure using ARM32 layout and little-endian integers**: an 80-byte header followed by 128 slots of 96 bytes. The 12,368-byte file declares 64 entries; the remaining 64 slots are entirely zero. Magic is `0x20120716`, and the literal device label is `mtk3598-emmc`. That spelling is preserved; the pinned upstream detector associates it with the MTK5398 family.

**CONFIRMED (local):** twenty partition names occur twice, at distinct non-overlapping locations, with equal sizes and filenames. First members have `used=1`, `valid=1`, `MASTER`; second members have `used=0`, `valid=1`, no flags. This is concrete evidence that the **update's map describes paired storage regions**. It does not establish the owner's active bank, that both copies exist intact on the physical unit, the update transaction algorithm, or automatic fallback after a failed modification.

**PENDING:** reliable recovery. There is only one entry named `boot`. `partinfo` and `mapbak` are separate entries with the same filename and version, but no execution trace or source-level selection path demonstrates which copy is trusted or when recovery is entered. Paired application/kernel files do not by themselves protect the boot chain, unique configuration, identity material, partition metadata or power-loss update handling.

## Provenance and boundaries

Input: `firmware/lab/packages/part.pak`, mode `0444`, SHA-256 `7289a31801401caa02c02ecfc36f9fdc3cdfcc2b74832ff0457f3f879c93ace8`. The parent EPK's header and this package's exact segment were cryptographically verified during [controlled extraction](firmware-extraction.md). This task recalculated the decoded payload hash and only read it.

Evidence reports:

- `artifacts/partition-analysis/partinfo-v2.json`: parsed fields, exact byte/extent bounds, flags, duplicates, gaps and input hash.
- `artifacts/partition-analysis/boot-recovery-markers.json`: narrow complete-printable-string search in `boot.pak`, with byte offsets and input hash. No raw string dump or secrets were collected.

`tools/partition_inventory.py` uses only the Python standard library. It reads at most the expected file size plus one byte and rejects wrong size/magic/device label, bad padding, unterminated/nonprintable strings, invalid booleans/counts, nonzero undeclared slots, oversized payload fields, overlapping extents and 64-bit extent overflow. Repeated names are intentionally retained. Extents outside the **declared device-size field** are explicitly flagged rather than silently removed or treated as live accessible storage. The current parser intentionally accepts only this verified format/label.

Sources at pinned epk2extract commit `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`:

- [partinfov2.h](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/u-boot/partinfov2.h): structures and 128-entry capacity.
- [partcommon.h](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/u-boot/partcommon.h): field lengths and flag labels.
- [util.c](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/util.c): device-label/version selection.
- [partinfo.c](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/partinfo.c): display interpretations.

The upstream C declarations substitute 32-bit pointer fields only under `__x86_64__`; an unmodified native ARM64 host build can use eight-byte pointers and the wrong structure size. Our parser uses explicit wire offsets and never uses the host's pointer size or C `sizeof` to interpret the file.

## Wire layout

| Header offset | Bytes | Field |
| --- | ---: | --- |
| `0x00` | 4 | Magic `0x20120716` |
| `0x04`, `0x08` | 4 each | Current and old EPK version fields; both zero |
| `0x0c` | 1 | Partition count, 64 |
| `0x0d` | 3 | Zero alignment padding |
| `0x10` | 32 | NUL-terminated device label |
| `0x30` | 8 | Declared device-size field, `0xe7000000` |
| `0x38` | 8 | Physical-base field, zero |
| `0x40`, `0x44` | 4 each | Target virtual/cached fields, both zero |
| `0x48`, `0x4c` | 4 each | Bankwidth zero, device used=1 |
| `0x50` | 128 × 96 | Partition-entry array |

Within each 96-byte entry: name32 at `+0x00`, offset64 at `+0x20`, size64 at `+0x28`, filename32 at `+0x30`, file-size32 at `+0x50`, software-version32 at `+0x54`, used8 at `+0x58`, valid8 at `+0x59`, zero padding2 at `+0x5a`, flags32 at `+0x5c`.

The source flag labels are `FIXED=0x01`, `MASTER=0x02`, `IDKEY=0x04`, `CACHE=0x08`, `DATA=0x10`, `SECURED=0x20`, `ERASE=0x40`. These are metadata bits; their names do not establish Linux partition type, a filesystem, encryption, cryptographic enforcement or physical write protection. In particular, absence of the `SECURED` map flag does not negate the observed signed update container.

There is **no explicit filesystem-type field**. Filenames such as `rootfs.squashfs` are format hints; actual package magic confirms several selected files separately. No sensitive partition payloads were obtained: identity/security-related names below are only map entries from the public update.

## Complete declared map

Offsets and sizes are hexadecimal bytes, with end-exclusive arithmetic. `U/V` records the file's used/valid bits, not live runtime state. Every declared file-size field is zero. The software version is zero except `partinfo` and `mapbak`, which are `0x22`.

| Index | Name | Start | Size | U/V | Flags | Filename hint |
| ---: | --- | --- | --- | --- | --- | --- |
| 0 | boot | `0x0` | `0x100000` | 1/1 | FIXED, MASTER | boot.bin |
| 1 | partinfo | `0x100000` | `0x40000` | 1/1 | FIXED, MASTER | PART.INFO |
| 2 | mapbak | `0x140000` | `0x40000` | 1/1 | FIXED, MASTER | PART.INFO |
| 3 | swue | `0x180000` | `0x2000000` | 1/1 | MASTER | swue.squashfs |
| 4 | swue | `0x2180000` | `0x2000000` | 0/1 | — | swue.squashfs |
| 5 | crc32info | `0x4180000` | `0x40000` | 1/1 | MASTER | CRC32.INFO |
| 6 | macadr | `0x41c0000` | `0x40000` | 1/0 | FIXED, IDKEY | — |
| 7 | env_nvm | `0x4200000` | `0x40000` | 1/1 | FIXED, IDKEY | — |
| 8 | widevine | `0x4240000` | `0x80000` | 1/1 | IDKEY | widevine.squashfs |
| 9 | idfile | `0x42c0000` | `0x80000` | 1/1 | IDKEY | idfile.squashfs |
| 10 | cert | `0x4340000` | `0x80000` | 1/1 | IDKEY | cert.squashfs |
| 11 | authcxt | `0x43c0000` | `0x600000` | 0/0 | IDKEY | — |
| 12 | nvram | `0x49c0000` | `0x600000` | 1/1 | IDKEY | — |
| 13 | marlin | `0x4fc0000` | `0x40000` | 1/1 | IDKEY | marlin.squashfs |
| 14 | hdcp | `0x5000000` | `0x200000` | 1/1 | IDKEY | — |
| 15 | rootfs | `0x5200000` | `0xa00000` | 1/1 | MASTER | rootfs.squashfs |
| 16 | lginit | `0x5c00000` | `0x80000` | 1/1 | MASTER | lginit.squashfs |
| 17 | model | `0x5c80000` | `0x40000` | 1/1 | MASTER | model.squashfs |
| 18 | cfginfo | `0x5cc0000` | `0x40000` | 1/1 | MASTER | CFG.INFO |
| 19 | logo | `0x5d00000` | `0x80000` | 1/1 | MASTER | logo.img |
| 20 | kernel | `0x6000000` | `0x800000` | 1/1 | MASTER | uImage |
| 21 | lgapp | `0x6800000` | `0xd00000` | 1/1 | MASTER | lgapp.lz4 |
| 22 | lgres | `0x7500000` | `0x3400000` | 1/1 | MASTER | lgres.squashfs |
| 23 | lglib | `0xa900000` | `0x2500000` | 1/1 | MASTER | lglib.squashfs |
| 24 | lgfont | `0xce00000` | `0x3000000` | 1/1 | MASTER | lgfont.img |
| 25 | opensrc | `0xfe00000` | `0x2a00000` | 1/1 | MASTER | opensrc.squashfs |
| 26 | emanual | `0x12800000` | `0x6400000` | 1/1 | MASTER | emanual.squashfs |
| 27 | tzfw | `0x18c00000` | `0x100000` | 1/1 | MASTER | tzfw.bin |
| 28 | base | `0x18d00000` | `0x15a00000` | 1/1 | MASTER | base.squashfs |
| 29 | patch | `0x2e700000` | `0x100000` | 1/1 | MASTER | patch.squashfs |
| 30 | skype | `0x2e800000` | `0x400000` | 1/1 | MASTER | skype.squashfs |
| 31 | pqldb | `0x2ec00000` | `0x100000` | 1/1 | MASTER | pqldb.squashfs |
| 32 | tplist | `0x2ed00000` | `0x100000` | 1/1 | MASTER | tplist.squashfs |
| 33 | preload | `0x2ee00000` | `0x500000` | 1/1 | MASTER | preload.squashfs |
| 34 | extra | `0x2f300000` | `0x1000000` | 1/1 | MASTER | extra.squashfs |
| 35 | vendor | `0x30300000` | `0x600000` | 1/1 | MASTER | vendor.squashfs |
| 36 | estreamer | `0x30900000` | `0xc00000` | 1/1 | MASTER | estreamer.squashfs |
| 37 | vocdb | `0x31500000` | `0x400000` | 1/1 | MASTER | vocdb.squashfs |
| 38 | rootfs | `0x31900000` | `0xa00000` | 0/1 | — | rootfs.squashfs |
| 39 | lginit | `0x32300000` | `0x80000` | 0/1 | — | lginit.squashfs |
| 40 | kernel | `0x32400000` | `0x800000` | 0/1 | — | uImage |
| 41 | lgapp | `0x32c00000` | `0xd00000` | 0/1 | — | lgapp.lz4 |
| 42 | lgres | `0x33900000` | `0x3400000` | 0/1 | — | lgres.squashfs |
| 43 | lglib | `0x36d00000` | `0x2500000` | 0/1 | — | lglib.squashfs |
| 44 | lgfont | `0x39200000` | `0x3000000` | 0/1 | — | lgfont.img |
| 45 | opensrc | `0x3c200000` | `0x2a00000` | 0/1 | — | opensrc.squashfs |
| 46 | emanual | `0x3ec00000` | `0x6400000` | 0/1 | — | emanual.squashfs |
| 47 | tzfw | `0x45000000` | `0x100000` | 0/1 | — | tzfw.bin |
| 48 | base | `0x45100000` | `0x15a00000` | 0/1 | — | base.squashfs |
| 49 | patch | `0x5ab00000` | `0x100000` | 0/1 | — | patch.squashfs |
| 50 | skype | `0x5ac00000` | `0x400000` | 0/1 | — | skype.squashfs |
| 51 | pqldb | `0x5b000000` | `0x100000` | 0/1 | — | pqldb.squashfs |
| 52 | tplist | `0x5b100000` | `0x100000` | 0/1 | — | tplist.squashfs |
| 53 | preload | `0x5b200000` | `0x500000` | 0/1 | — | preload.squashfs |
| 54 | extra | `0x5b700000` | `0x1000000` | 0/1 | — | extra.squashfs |
| 55 | vendor | `0x5c700000` | `0x600000` | 0/1 | — | vendor.squashfs |
| 56 | estreamer | `0x5cd00000` | `0xc00000` | 0/1 | — | estreamer.squashfs |
| 57 | nback | `0x5db00000` | `0x80000` | 1/1 | DATA | — |
| 58 | hib | `0x5db80000` | `0x4000000` | 1/1 | DATA | — |
| 59 | hist | `0x61b80000` | `0x80000` | 1/0 | FIXED | — |
| 60 | system_app | `0x61c00000` | `0x8200000` | 1/1 | DATA | — |
| 61 | data | `0x69e00000` | `0x12200000` | 1/1 | DATA | — |
| 62 | apps | `0x7c000000` | `0x6b000000` | 1/1 | DATA | — |
| 63 | reserved | `0xe7000000` | `0x19000000` | 0/0 | FIXED | — |

### Capacity and gaps

The device-size field is **3,875,536,896 bytes** (`0xe7000000`, 3.609375 GiB). Entries through `apps` end exactly there. `reserved` then describes `0xe7000000–0x100000000`, 419,430,400 bytes, outside that field. The maximum described endpoint is therefore 4 GiB. This is consistent with a reserved tail in an update-layout template; it is **not a measured physical eMMC capacity**, a flash dump size or an authorization to address that region.

The parser finds no overlapping partition extents. Three gaps occur between entries:

| Start | End exclusive | Bytes |
| --- | --- | ---: |
| `0x5d80000` | `0x6000000` | 2621440 |
| `0x32380000` | `0x32400000` | 524288 |
| `0x5d900000` | `0x5db00000` | 2097152 |

All entry boundaries are at least 256 KiB aligned. Alignment is an observation about this table; it does not prove the physical erase/block geometry.

## Redundancy and recovery interpretation

**CONFIRMED:** repeated names are `swue`, `rootfs`, `lginit`, `kernel`, `lgapp`, `lgres`, `lglib`, `lgfont`, `opensrc`, `emanual`, `tzfw`, `base`, `patch`, `skype`, `pqldb`, `tplist`, `preload`, `extra`, `vendor` and `estreamer`. `partinfo`/`mapbak` also describe equal-sized regions with the same `PART.INFO` filename, but different names.

**LIKELY:** the paired regions support staged software updates or bank selection. The complementary used/master flags support that hypothesis. Current/old version fields and all payload file-size fields being zero make this look like a distribution template, not a snapshot of installed image validity.

**RULED OUT as a justified conclusion:** declaring a verified A/B recovery mechanism merely because duplicate regions exist. The map contains one named boot region, some unpaired system/configuration partitions, and independent identity/data regions. A bad boot image, corrupted selector/map, incompatible shared state or a write to the wrong region could remain unrecoverable even if application copies are duplicated.

**CONFIRMED (bounded negative result):** the boot-package search for partition/recovery/backup/fallback/mapbak/partinfo/swue/bootmode strings yielded only `EMMC boot` at `0x43a8`. It searched complete printable strings no longer than 160 characters and excluded security-material terms. This does not prove such mechanisms are absent: boot stages can be compressed, strings can differ, and control logic need not contain those words. The search found no recovery command or selection algorithm to validate.

Read-only startup scripts have `bootdev` and `bootmode` branches, but changing them has not been tested or authorized. The non-auto path's presence in a vendor script is not proof that the physical unit exposes a safe mode-selection control. Do not invoke it, infer a recovery console or alter boot arguments from this evidence.

Open recovery questions, to resolve before any persistent experiment:

1. Does the running unit's read-only partition map match this update template, including active/used flags and device capacity?
2. Where is the authoritative map/selector stored, and what integrity checks and primary/backup arbitration apply?
3. Does boot selection operate per component or as a coherent bank? Which shared components must match?
4. What triggers rollback: verification failure, boot timeout, watchdog, application health, manual service action, or nothing?
5. Which code remains executable after damage to `boot`, `partinfo`, `mapbak`, `lginit` or the active kernel?
6. Can a documented recovery mode restore this exact model and firmware without relying on the damaged system? Is its entry and restoration procedure independently demonstrated?
7. How are unique identity/configuration partitions protected and preserved during official recovery? No contents from those regions should enter public artifacts.

## Experiment FW-004

- **Objective:** decode partition metadata and distinguish concrete redundancy evidence from an assumed recovery guarantee.
- **Hypothesis:** the signed `part` payload matches a public LG map structure with paired update regions.
- **Environment:** preserved `part.pak` and `boot.pak`, Apple Silicon Mac, Python standard library, pinned public source declarations. No TV contact.
- **Procedure:** compare exact file size/header/first entries with v2 structures → implement fixed-endian parser → validate all slots/strings/extents/flags → group repeated names → identify gaps and out-of-size tail → search boot strings with a narrow technical allowlist → test synthetic malformed maps.
- **Expected result:** bounded parsed map and a list of recovery claims that remain unsupported.
- **Observed result:** exact v2 ARM32 fit;64 declared entries/64 zero slots;20 duplicate names;no overlaps;3 gaps;one reserved extent beyond the declared usable-size field;no direct recovery/selection marker found.
- **Conclusion:** paired storage is supported by static update metadata. Active layout, physical capacity, bank-selection semantics and reliable recovery remain unverified.
- **Risks:** native host structure mismatch, mistaking update defaults for device state, interpreting flag names as protection guarantees, and publishing sensitive contents. Mitigations: fixed wire parser, explicit evidence labels, no device access and map metadata only.
- **Validation:** five synthetic tests passed for exact layout/repeated names, size/magic/count/unused slots, overlaps/overflow, explicit out-of-bound reporting and malformed fields. The real file parsed without changing it.
- **Next step:** correlate the signed update manager and boot/init selection code with this map, keeping runtime state and a verified recovery procedure separate. Provide findings to the independent recovery audit; do not test writes or alter boot controls.

Reproduce:

```sh
python3 -B -m tools.partition_inventory firmware/lab/packages/part.pak
python3 -B -m unittest discover -s tests -p 'test_partition_inventory.py' -v
```

## Follow-up evidence for the independent boot/recovery review

At the integration lead's request, two explicitly selected regular files were copied from the already verified `root.pak` using the existing sandboxed list/cat workflow. No firmware code was executed:

- `firmware/lab/root-review-selected/sbin/init`: 28,323 bytes; SHA-256 `595696e55a908ccbbaa289c4e69165953d7e9a7f0c69bc1354a1350b7fa9b4ef`; mode `0444` on the host.
- `firmware/lab/root-review-selected/etc/checker.sh`: 9,330 bytes; hash and original metadata in `artifacts/firmware-lab/root-review-inventory.json`; mode `0444` on the host.

**CONFIRMED (local):** the selected init binary is ARM32 little-endian EABI5, dynamically linked through `/lib/ld-linux.so.3`. Its bounded string inventory finds `INIT_VERSION=sysvinit-2.86` at byte 24,396, `/etc/inittab` at 23,664 and `/dev/initctl` at 23,220. Evidence is in `artifacts/partition-analysis/init-markers.json`. **PENDING:** whether the kernel actually selects this binary as PID 1, an alternative init, or an earlier RAM-root stage. Identifying the candidate binary does not establish its runtime selection.

`artifacts/firmware-lab/swue-inventory.json` is a metadata-only listing of the verified `swue.pak`: 124 regular files, including `SWUE` (3,911,188 bytes), `SWUE-DBG` (9,502,347), `SWUE.cfg` (11,782) and `SWUE.sym` (732,080). No contents from this filesystem were copied or executed in this follow-up. These names identify candidates for a separate bounded updater audit, not an operational recovery interface.

`etc/register_user.sh` remains **PENDING and unread** in this task: it was not copied, printed or added to a report because it may contain credential material. A future review may produce only a sanitized structural summary from memory if needed.

The review's root-device question remains open: `root.pak` is SquashFS4/LZO, whereas `rcS` attempts to remount `/dev/ram` as ext2 read-write. A vestigial statement, a RAM-root preparation stage or another boot arrangement are hypotheses; neither the image magic nor that single script line proves what is mounted on the running TV. Correlate kernel boot arguments and earlier mount/init logic before describing the script as an active execution path or a recovery mechanism.
