# Execution prohibition: descriptor producers and policy limits

Date: 2026-11-14. **CONFIRMED (local static):** the execution-info descriptor's first word is populated from update XML named `prohibit`, or from update-completion records. Its low bit reaches app-info byte `+0x60b`, bit 4, which the previously traced execution helper rejects when set. **PENDING:** upstream authority for these inputs, other writers, initial USB-test values and native admission. This is an update-policy field, not evidence of a native-class ban.

This continues [execution conditions](native-execution-conditions.md), with the storage identities established by [manifest admission](native-manifest-admission.md). Only the already selected appctrl was examined. No vendor execution, protected-package decoding, IPC, TV/network access, new extraction, device change or Git operation occurred.

## Pinned source and bounded captures

Source: `firmware/lab/app-lifecycle/open/bin/appctrl`, **277,044 bytes**, SHA-256 `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97`. Eight exact symbol extents total **2,964 bytes**, below the 8-KiB capture ceiling:

| Defined symbol | Linked range, end exclusive | Bytes |
| --- | --- | ---: |
| `_APPCTRL_GetExecuteInfoFromXML` | `0x24a04–0x24ba4` | 416 |
| `_APPCTRL_ReadAppUpdateInfoFromXML` | `0x25250–0x25428` | 472 |
| `_APPCTRL_ReadAppsUpdateInfoFromXML` | `0x25428–0x25500` | 216 |
| `APPCTRL_SetUpdateInfoFromFile` | `0x25500–0x25744` | 580 |
| `APPCTRL_MakeMyappsList` | `0x24564–0x24600` | 156 |
| `APPCTRL_CheckUpdateAppComplete` | `0x27550–0x277d4` | 644 |
| `APPCTRL_CheckUpdateAppHandler` | `0x1a308–0x1a430` | 296 |
| `AM_CMN_APPLIST_SetAppExecuteInfo` | `0x2d150–0x2d208` | 184 |

Extents match `artifacts/app-lifecycle/appctrl-symbols.txt`, SHA-256 `b10e5ebd0320779ff13ca1301be16cc5269a22613c98ba4fb5b89da8a5b6f758`. The reviewed reader `tools/arm_disassembly.py` has SHA-256 `a8ee2ac84906148c24a799d96058cd58e9c1b6da22f233b635cdea3fbff9f231`; explicit host Apple LLVM has SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Each host disassembly has a 10-second deadline. Selected file offsets equal linked address minus `0x8000`, checked against ELF executable-segment coverage. Literal pools and jump tables remain data.

A direct ARM B/BL candidate scan located callers to selected targets, then the exact function captures validated the relevant instructions. This does not enumerate indirect calls, external callers or every write to the resulting field. Selected strings and PLT imports were checked through bounded reads and ELF relocations, not guessed from nearby names.

## XML producer: `prohibit`, independently of `app_type`

`_APPCTRL_GetExecuteInfoFromXML` finds child nodes and compares their content with exact single-character strings, including the terminating NUL:

| XML child / value | Descriptor write | Evidence |
| --- | --- | --- |
| `prohibit` = `Y` | word 0 = 1 | Store at `0x24b0c`; name literal through `0x24b90` |
| `need_nsu` = `Y` | word 1 = 1 | Store at `0x24b24`; name literal through `0x24b8c` |
| `update` = `Y` | word 2 = 1 | Store at `0x24a68`; name literal through `0x24b84` |
| `update` = `F` | word 2 = 10 | Store at `0x24b4c` |

Missing/nonmatching content leaves the supplied descriptor field unchanged. The examined caller initializes all three words to zero at `0x2530c–0x25318`, so those cases retain zero in this path. `update=F` does **not itself** set word 0 in this XML helper; the result-10 override described below is in a different producer.

`_APPCTRL_ReadAppUpdateInfoFromXML` obtains `appid`, converts it through `_APPCTRL_AsciiToAppID`, and looks up existing app-info in its supplied list selector at `0x252bc`. Only a successful lookup reaches the zeroed descriptor and parser call at `0x25320`. A nonzero second argument then clears word 1 at `0x25330`; it does not clear word 0.

The caller compares descriptor words against existing app-info: word 0 against byte `+0x60b` bit 4, word 1 against bit 5, and word 2 against byte `+0x60d` bits 1–5. A difference reaches `AM_CMN_APPLIST_SetAppExecuteInfo` at `0x2535c`. The previously captured utility writes the descriptor's low bits into those fields; this completes the provenance of the execution-rejection flag for this path. It does not establish that an arbitrary XML document can enter the path.

## File caller and list selection

`_APPCTRL_ReadAppsUpdateInfoFromXML` finds the `apps` child and loops through children, forwarding its second argument and list selector to the per-app reader at `0x25470`. Its examined caller, `APPCTRL_SetUpdateInfoFromFile`, selects list **2** for input selector **1 or 5**, and list **3** for **2 or 6** (`0x25524–0x25548`, `0x2563c`). Other selectors take the error path. These input selectors must not be conflated with list numbers or XML app types; their complete enum names remain unresolved.

The file loader reads XML system information and compares the two strings logged as `SWVersion` using `strcmp` at `0x25608`. A mismatch becomes the nonzero second argument passed at `0x2561c`, causing the per-app reader to clear `need_nsu` only. Group and country values are logged in this function, but these logging calls do not establish rejection checks for those values.

`APPCTRL_MakeMyappsList` obtains a filename from `_APPCTRL_GetMyAppsFilePath` at `0x24570`, then immediately passes that filename and its own selector to the file loader at `0x24578`. **Stopping boundary:** the file-path helper, file producer, provenance, permissions and integrity policy are untraced. This function also proceeds into list maintenance; it is not proposed as a harmless diagnostic invocation.

## Completion producer: storage and update result matter

`APPCTRL_CheckUpdateAppComplete` iterates records of 348 bytes. Its debug string labels record `+0x44` as storage type and `+0x48` as update result. This bounded trace establishes the following field flow without defining a reusable vendor ABI:

| Record field / condition | Observed use |
| --- | --- |
| `+0` | App ID passed to the setter |
| `+0x44` = 1 or 2 | Only these storage values proceed; storage 1 selects list 2, storage 2 selects list 3 |
| `+0x48` = 0, 1 or 8 | Normal update path copies record `+0x50` into descriptor word 0 |
| `+0x48` = 10 | Normal update path forces descriptor word 0 to 1 at `0x27634–0x27638` |
| `+0x4c` | Copied to descriptor word 1 |
| `+0x48` | Copied to descriptor word 2 |

The filtering and setters are at `0x275d8–0x27620`, `0x27640–0x27650` and `0x276b8–0x276f0`. Other result values are logged and skipped. A separate branch for results 1/10 consults `HOA_CTRL_GetIsGIPMode`; particular matching state invokes `HOA_CTRL_SetIsGIPNeedUpdate` and skips the normal setter. Its mode semantics are untraced. Consequently the table describes normal paths, not an unconditional promise to update every record. Numeric results are not manifest classes, and the shared value 10 does not establish complete equivalence with the XML `F` semantics.

The direct caller `APPCTRL_CheckUpdateAppHandler` obtains input through imported `SCF_BUS_Message_Get_Any` at `0x1a358`, checks that the byte count represents a nonempty exact multiple of the record stride, then calls completion at `0x1a404`. **Stopping boundary:** message sender, authorization, decoding ownership/lifetime and the service that determines the supplied fields are untraced. No request construction or private-method invocation is provided. Completion can write app-list files and send notifications; it is not read-only on a device.

## Meaning for native admission

The generic setter dispatches selectors 2, 3 and 4 to the downloaded implementation (`0x2d188`), so structural support for the USB-test list exists. However, both concrete producers traced here select **2/3**, corresponding to ordinary internal/USB downloaded lists. Neither selects USB-test list **4**, and neither directly compares manifest `app_type` or the combined native-type bits.

**CONFIRMED:** two concrete sources of the prohibition bit and storage-based routing. **RULED OUT within these captured producers:** a direct native-class comparison. **PENDING:** other/indirect callers, initial field values and writers for USB-test apps, upstream update-policy authority, provider acceptance and effective execution account. The absence of a comparison here cannot rule out a native restriction elsewhere, nor does a clear bit admit an ELF.

## Reproduction and experiment record

Ignored `artifacts/native-execution-policy/` contains eight captures, `manifest.json`, `capture-summary.json`, `capture.py`, `callers.py`/`callers.json`, and `selected_data.py`/`selected-data.json`. The capture pins source, reader, symbol extents and host-tool hashes; repeat runs check range and display hashes. No extracted vendor content is redistributed in this report.

```sh
PYTHONPATH=. python3 artifacts/native-execution-policy/capture.py
PYTHONPATH=. python3 artifacts/native-execution-policy/callers.py
PYTHONPATH=. python3 artifacts/native-execution-policy/selected_data.py
```

- **Objective:** identify immediate producers of descriptor word 0 and distinguish type/storage policy.
- **Hypothesis:** the rejection bit represents policy supplied by another subsystem rather than a direct native-type test.
- **Environment:** pinned selected appctrl and explicit reviewed host LLVM; local static data only.
- **Procedure:** validate direct caller candidates, capture eight exact functions, track descriptor writes and list selectors, resolve selected literals/imports, repeat hash checks.
- **Expected result:** a concrete policy producer or a named unresolved boundary.
- **Observed result:** XML `prohibit`, completion-record fields and result-10 override produce the flag; examined paths route to lists 2/3.
- **Conclusion:** the immediate producer is identified; ultimate policy authority and USB-test applicability remain unresolved.
- **Risks:** treating list routing as universal policy, update codes as app classes, or absent type comparisons as native permission.
- **Next step:** reconcile provider acceptance first; any further policy slice should target the USB-test field initializer or one evidenced upstream producer, without invoking setters or altering metadata.
