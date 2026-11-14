# Inspecting a NetCast portal package

`tools/netcast_package.py` inspects an explicitly selected local ZIP. It never extracts files, writes a staging tree, touches USB, contacts the TV, uploads anything, decrypts a manifest or executes packaged code. It uses the Python standard library.

```sh
python3 -m tools.netcast_package /path/to/portal-output.zip
python3 -m tools.netcast_package /path/to/portal-output.zip \
  --source-zip artifacts/netcast-source/launcher-source.zip
python3 -m unittest tests.test_netcast_package -v
```

Use the exact source ZIP submitted for that portal output, not a newer locally rebuilt launcher. Source comparison requires the six current launcher assets: `index.html`, `style.css`, `navigation.js`, `capabilities.js`, `shell.js`, and `assets/landscape-v2.jpg`. Input/source paths are explicit; the inspector does not search Downloads or infer the newest package.

## What a successful inspection establishes

- One numeric application directory contains root `index.html`, `manifest.xml` and `developer.test` files.
- The HTML entry is nonempty. The manifest begins with `NCGFILE_HEADER`; its remaining bytes stay opaque.
- ZIP members have acceptable paths, types, sizes, compression and CRCs within the configured bounds.
- Optional source comparison identifies matching, changed and missing assets using the exact bytes from both bounded archives. Per-file and whole-ZIP SHA-256 hashes are reported.

The JSON labels the app root `<app-id>` instead of exposing its numeric identifier. It includes relative filenames, sizes and hashes, never file contents, manifest data or absolute input paths. Reports still describe a local package and should remain under ignored `artifacts/` unless reviewed for publication. The inspector itself writes only JSON to stdout.

A successful result is **structural validation**, not proof of LG authenticity, correct manifest entry, entitlement, safe vendor behavior, native execution or TV compatibility. `entry_in_manifest_verified` and `entitlement_verified` remain false. No signature verification or manifest decryption is attempted. Compare the portal entry field separately with `index.html`.

## The observed Modify failure

After Modify, the downloaded output contained the previous package nested inside a new application directory (identifiers redacted):

```text
<app-id>/manifest.xml
<app-id>/developer.test
<app-id>/<same-app-id>/index.html
<app-id>/<same-app-id>/manifest.xml
<app-id>/<same-app-id>/developer.test
<app-id>/<same-app-id>/...source assets and icons...
```

The expected root entry was absent. This establishes the downloaded layout, not which input or portal behavior caused it; no attribution to the owner is established. The inspector reports `nested_app_root` and recommends re-uploading the original source ZIP and verifying the entry tree. Successful physical launch followed both correction of the portal entry value and source re-upload. Their individual causal contributions have not been isolated, and this observation does not explain every black screen.

Synthetic regressions cover the original 14-entry/12-file layout, the malformed nested layout, and the corrected 10-entry/8-file layout without icons. Icons are optional; neither their absence nor their count determines validity. Other regular assets are inventoried, not executed or declared safe.

## Limits and rejection behavior

| Boundary | Limit or policy |
| --- | --- |
| Compressed input | At most 10 MiB; regular file, final symlink rejected, nonblocking open |
| Entries | At most 100, checked before constructing ZIP member objects |
| Central directory | At most 128 KiB; consistent end record and boundaries |
| Expanded data | At most 20 MiB total and 2 MiB per member |
| Compression ratio | At most 200:1 per member |
| Compression | Stored or deflated only; ZIP encryption rejected |
| Paths | Bounded names; no absolute, traversal, empty segments, backslashes, controls, trailing dots/spaces or drive prefixes |
| Collisions | Duplicate, NFC/case-fold collision and file-as-parent paths rejected |
| Types | Regular files and empty directory entries only; no links/devices/FIFOs |
| ZIP variants | Split archives, ZIP64 end records, executable prefixes and trailing bytes unsupported |

Reads use a bounded in-memory snapshot, with source size/modification checks around the read. CRC validation detects corruption, not malicious modification by an actor able to rewrite the archive. Failures use fixed diagnostics without embedding private filenames or parser exception contents. Limits intentionally reject unusual packages for manual investigation instead of loosening them automatically.

Exit codes: **0** for structural success and any requested source comparison matching; **1** for invalid/unreadable input or unsupported structure; **2** for a structurally valid package whose source comparison has changed/missing assets. Source-comparison failure does not erase the inventory: its JSON still reports the mismatches.

## Validation status

CONFIRMED (local): automated synthetic tests exercise the actual inspector, including nested Modify input, optional icons, missing entry/metadata, manifest prefix, unsafe names/NUL, collisions, links, CRC corruption, encrypted flags, compression/resource limits, source differences, input symlinks/FIFOs and redacted CLI errors. These synthetic tests do not constitute physical TV validation. Integrators should run the inspector against each exact portal output before the separately authorized USB-copy procedure.

CONFIRMED (local, integration verification): the integrator ran this inspector against all three actual downloaded packages. The original 12-file package passed with all six source assets matching; the malformed nested package was rejected; the corrected 8-file package passed with all six source assets matching. Package provenance and hashes remain in [app-deployment.md](app-deployment.md) and ignored local inventories. This verification read local ZIP files only; the inspector did not contact the TV or establish entitlement or the protected manifest entry.
