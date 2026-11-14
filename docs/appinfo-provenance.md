# AppInfo lookup: USB-test storage and sample-support gate

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** upctrl's AppInfo path builder accepts only a nonzero app ID with storage 3, and requires a successful sample-support query whose output flag is nonzero. Only then does it construct `<selected USB base>/lgapps/installed/<app ID>/app_info.txt`. The previous [upctrl report](upctrl-manifest-gate.md) identified this branch before protected-manifest fallback; it is now a specifically gated branch, not a general unprotected alternative.

**PENDING:** the imported query's underlying policy, the physical unit's result, the producer and integrity provenance of `app_info.txt`, and native admission. Vendor log text calls the condition “CP Box”; that label does not identify the owner's device class or establish a supported developer mode. Nothing here proposes changing the flag or creating that file.

## Sources and method

No new extraction occurred. The two previously selected official ELF inputs were read as data:

| Input | SHA-256 |
| --- | --- |
| `firmware/lab/upctrl-selected/bin/upctrl` | `5cc04d10a43926a843c27c15f8928a6e2400a968f7e1a3e5bde93175ff787e4f` |
| `firmware/lab/app-lifecycle/open/bin/appctrl` | `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97` |

The reviewed [static disassembler](static-disassembly.md) used Apple LLVM 17.0.0, host executable SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Six captures total 1,532 bytes, below the 8-KiB budget. Every capture reproduced with matching input, selected-byte and normalized-display hashes. No target code, protected package, licensing call, IPC or TV/network operation was executed.

Addresses below are linked virtual addresses; these code/literal file offsets equal address minus `0x8000`. Ranges are half-open and include local literal pools. A bounded direct ARM B/BL candidate scan covered executable file-backed segments of only these two small ELFs; it is not whole-image disassembly or a complete call graph.

| ELF | Selected function | Range | Bytes |
| --- | --- | --- | ---: |
| upctrl | `UC_PATH_GetAppInfoFilePath` | `0x27670..0x27674` | 4 |
| upctrl | `AM_CMN_GetAppInfoFilePath` | `0x36c98..0x36e04` | 364 |
| upctrl | `AM_CMN_GetInstalledAppPath` | `0x36a70..0x36ba4` | 308 |
| upctrl | `AM_CMN_GetAppstoreBasePath` | `0x36620..0x36748` | 296 |
| upctrl | `_CMN_GetAppstoreUSBPath` | `0x3655c..0x36620` | 196 |
| appctrl | `AM_CMN_GetAppInfoFilePath` | `0x29898..0x29a04` | 364 |

## The flag is a mandatory precondition for this lookup

`UC_PATH_GetAppInfoFilePath` is a direct branch to `AM_CMN_GetAppInfoFilePath`. In upctrl the latter makes the following decisions:

| Step | Exact evidence | Consequence |
| --- | --- | --- |
| Argument restriction | `0x36cd8..0x36cf0` computes a rejection condition for app ID zero or storage other than 3 | Rejection returns `-1` at `0x36dd4`. Storage 1/2 cannot use this path builder. |
| Cached-query check | `0x36cf4..0x36d00` loads state through literal `0x36de4`, pointing to `0x65ce4`, and tests its first word | Zero branches to the query; nonzero uses the adjacent cached support flag. |
| Imported query | `0x36d6c` passes `0x65ce8` as an output pointer; call `0x36d70` resolves to `HOA_IO_CheckSampleSetIsSupported` | Only return zero reaches the flag test (`0x36d74..0x36d78`); failure returns `-1`. |
| Remember and test | `0x36d04..0x36d14` reads the output flag at state `+4`, writes 1 to the checked word, then tests the flag | A zero support flag returns `-1` at `0x36da4`. A successful false result is cached as checked. |
| Construct path | `0x36d18..0x36d50` calls the installed-path helper with storage fixed to 3 and appends the AppInfo basename | Successful path construction returns zero. This does not create or authenticate the file. |

The two cached words lie in an ELF `SHT_NOBITS` region beginning `0x65328`, size 3,920 bytes. They have no serialized initialized file values; normal ELF loading supplies zero-filled storage. This supports the first-query interpretation but does not establish current process memory or exclude earlier runtime writes. The inspected path queries lazily when its checked word is zero. Query failure does not take the instruction that sets it to 1.

The import was identified through PLT `0x167f0`, GOT `0x6324c`, type-22 relocation at file offset `0xe158`. That symbol is the actual call target name. Nearby diagnostic strings instead say `Check CP Box Flag`, `HOA_IO_CheckCpBoxIsSupported fail`, and `This device is not CP Box. bIsCpBoxSample: %d`. The name discrepancy is preserved: logs suggest a vendor sample/CP-box concept, but do not define its implementation, authority or current device value. The imported function body was not inspected.

## Exact location if the gate passes

The called `AM_CMN_GetInstalledAppPath` invokes `AM_CMN_GetAppstoreBasePath` at `0x36adc`. For storage 3 the latter obtains the selected USB base at `0x3669c`, then appends `/lgapps` using the literal loaded at `0x366b0`. The installed-path helper adds `/installed` and the unsigned decimal app ID (`0x36af0..0x36b0c`). Finally the AppInfo builder appends `app_info.txt` with `%s/%s` at `0x36d34..0x36d4c`.

The USB-base helper reads the buffer at `0x65f58`, requires a nonempty first byte and successful `access(base, 0)` (`0x36588..0x365a8`), then copies it. PLT relocations resolve the calls to `access` and `strncpy`. This is existence/path handling, not an ownership, execute-permission, signature or entitlement check. The current mount path and writer of the base buffer remain untraced.

Selected technical literals have explicit mappings: `app_info.txt` is at file offset `0x4ba48` / VA `0x53a48`, `/installed` at VA `0x539c4`, `/lgapps` at VA `0x4d044`. No complete manifest template, metadata recipe, key or protected application content was read or produced.

## Producer search: a bounded negative result

The immediate reference search found these upctrl calls, already consistent with the previous provider trace:

- Handler call `0x1999c` to `UC_APPUTIL_GetManifestBufferFromAppInfo`.
- Its path request at `0x2bcec` to `UC_PATH_GetAppInfoFilePath`, whose wrapper branches at `0x27670` to the shared path builder.
- Its reader call `0x2bd4c` to `_UC_APPUTIL_GetAppInfoFromFile`. The prior inspected reader opens/parses an existing file; it does not create it.

Within upctrl there is one exact `app_info.txt` string and one aligned pointer to it, in the path builder's literal pool at `0x36de8`. No further direct B/BL callers of that path builder or wrapper were found. Appctrl also contains one exact basename string and one pointer in its equivalent path builder (`0x299e8`); the selected function has the same argument and cached-support branch structure. No direct B/BL caller of appctrl's path builder was found in the scanned executable segments.

**PENDING, not a global absence claim:** no producer was identified through these immediate direct references. Indirect calls, dynamic symbol lookup, computed filenames, another executable, an external authoring tool or installation/extraction of a pre-existing file remain possible. The search did not inspect every filesystem write or other firmware component. A symbol containing “AppInfo” can describe an in-memory record rather than this on-disk file; names alone were not treated as producer evidence.

## What this changes and where to stop

**CONFIRMED (static):** a failed support query, false support flag, wrong storage or app ID zero prevents this AppInfo lookup. Combined with the prior handler trace, failure falls back to the protected downloaded-manifest path. A successful physical USB launch therefore does not prove that the sample-support flag was true or that AppInfo was consumed.

**PENDING:** whether the imported policy permits the owner's TV, whether the official portal emits this file for any supported device class, who supplies/validates its contents, and whether any legitimate native package issuer exists. Metadata lookup is distinct from protection, issuance and later execution authorization. The inspected gate is not permission to change device configuration or bypass the protected fallback.

This slice stops at the imported support-policy boundary and unresolved producer. A useful next independent static step is the downstream appctrl execution-condition check, which can reveal class restrictions without manipulating AppInfo or investigating license/key contents. Further provenance research should begin with a documented producer or a narrow reference in an already available artifact, not an indiscriminate firmware search. No owner action is needed for the present result.

## Reproduction and experiment record

Ignored `artifacts/appinfo-provenance/` contains pinned capture/reproduction scripts, six JSON captures, `manifest.json`, exact literal/relocation evidence and the two-input candidate-reference report. From the repository root, `PYTHONPATH=. python3 -B artifacts/appinfo-provenance/capture.py` reproduces captures. The public tool independently reproduces the central gate:

```sh
python3 -m tools.arm_disassembly firmware/lab/upctrl-selected/bin/upctrl \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --start 0x36c98 --end 0x36e04
```

**Objective:** establish AppInfo storage provenance and immediate production/acceptance conditions. **Hypothesis:** the AppInfo-first path has a narrower prerequisite than the outer handler reveals. **Environment:** two previously selected official ARM ELFs and reviewed host tooling. **Procedure:** trace the path wrapper, argument/support gate and path builders; resolve the imported query; inspect immediate direct references and an equivalent appctrl function; reproduce six captures. **Expected:** a concrete USB path and gate, plus producer evidence or a bounded unresolved boundary. **Observed:** storage-3-only path, cached imported sample-support requirement, exact AppInfo location and no identified immediate producer. **Conclusion:** the earlier general-looking branch is conditional on a device-policy result; its applicability and native authorization remain unknown. **Risks:** treating a diagnostic label as device identity, static zero-filled state as live memory, or a negative direct-reference search as proof of no writer. **Next step:** downstream execution-condition analysis; retain the policy and producer uncertainties explicitly.
