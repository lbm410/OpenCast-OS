# Appctrl type provenance and execution conditions

Date: 2026-11-14. **CONFIRMED (local static):** the downloaded parsed field `+0x28` comes from XML `app_type`; downloaded native classes select the account label `game`; the examined execution-condition helper rejects particular loading/state/flag combinations. **PENDING:** provider acceptance of our native artifact, the policy producing the rejection flag, actual account enforcement and a permitted launch mechanism. These findings do not establish native admission or privileges.

This follows [manifest admission](native-manifest-admission.md) and [execution gates](native-execution-gates.md). Scope is the already selected appctrl only. No protected package was opened/decrypted, no metadata changed, and no IPC, TV, network, target execution or Git operation occurred. Upctrl remains a separate investigation.

## Input, range budget and method

Input: `firmware/lab/app-lifecycle/open/bin/appctrl`, **277,044 bytes**, SHA-256 `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97`. The source hash was checked before capture and in every resulting report. Exact function extents were matched to the existing `artifacts/app-lifecycle/appctrl-symbols.txt` inventory. Addresses below are linked ELF addresses; these selected file offsets equal address minus `0x8000`, independently checked by the disassembly reader's executable-segment mapping.

Fourteen exact function ranges total **5,644 bytes**, below the initial 8-KiB budget:

| Capture / defined symbol | Range, end exclusive | Bytes |
| --- | --- | ---: |
| `_AM_CMN_APPLIST_MANIFEST_ParsingXML` | `0x31990–0x31b30` | 416 |
| `_AM_CMN_APPLIST_MANIFEST_ParsingBase` | `0x2fb60–0x2fd44` | 484 |
| `_AM_CMN_APPLIST_MANIFEST_ParsingAppCondition` | `0x31738–0x31990` | 600 |
| `_AM_CMN_APPLIST_DOWNLOADED_GetAccount` | `0x35fd0–0x36120` | 336 |
| `_AM_CMN_APPLIST_DOWNLOADED_MakeAppInfoFromManifest` | `0x36d58–0x37170` | 1,048 |
| `_APPCTRL_CheckExecuteCondition` | `0x14594–0x146a8` | 276 |
| `APPCTRL_IsAppLoading` | `0x143e0–0x14420` | 64 |
| `APPCTRL_GetLiveAppState` | `0x187c8–0x187dc` | 20 |
| `APPCTRL_IsLiveAppPreLoading` | `0x18810–0x18824` | 20 |
| `_APPCTRL_ExecuteAppByAppinfoEx` | `0x15f28–0x161fc` | 724 |
| `_APPCTRL_ExecuteProcess` | `0x17068–0x173dc` | 884 |
| `AM_CMN_APPLIST_UTIL_SetAppExecuteInfo` | `0x2dba8–0x2dcbc` | 276 |
| `AM_CMN_APPLIST_DOWNLOADED_SetAppExecuteInfo` | `0x36794–0x3682c` | 152 |
| `_AM_CMN_APPLIST_SetAppExecuteInfo` | `0x2cff8–0x2d150` | 344 |

The reviewed `tools/arm_disassembly.py` SHA-256 is `a8ee2ac84906148c24a799d96058cd58e9c1b6da22f233b635cdea3fbff9f231`. Explicit host Apple LLVM 17 SHA-256 is `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`; its path is shown below. Each capture has a 10-second deadline and the reader's input/range/output limits. Literal pools and jump tables inside these ranges are data, not executed instructions despite objdump's mnemonic display.

## Exact XML-to-type provenance

`ParsingXML` obtains each child node's name and content at `0x319d8`/`0x319e4`, then calls `ParsingBase(name, content, parsed_record)` at `0x319f8`. The base parser compares the name with the literal **`app_type`** through `strcmp` at `0x2fba0`; the equality branch reaches `0x2fc80`. There it calls `strtol(content, NULL, 10)` at `0x2fc8c` and stores the result at **parsed record `+0x28`** at `0x2fc90`.

This is the raw decimal value, not the combined type/storage bitmask. The previously traced downloaded conversion reads it at `0x36dc0`, calls `_DOWNLOADED_GetAppType` at `0x36dc4`, and writes combined type bits to app-info `+4` at `0x36dcc`. Thus the exact field in the provider→XML→downloaded-type chain is now identified. It is not necessary to infer this from the similarly named standalone `GetAppTypeFromString` helper.

There is no end-pointer or range validation in this particular `strtol` call. That observation does not prove malformed or arbitrary owner-supplied XML can reach it: provider transformation/validation, parser initialization and required-field policy remain separate boundaries. XML helper names/content are tracked through calls; their internal parser semantics were not recovered here.

`ParsingAppCondition` also recognizes `loading_effect`, `enable_on_dvr`, `enable_on_widi`, `disable_on_nsu`, `enable_app_lock`, `in_backlist` and `video_type`. Selected Y/N branches write fields around parsed record `+0x2f78..+0x2f90`. These are metadata writes, not demonstrated runtime checks for DVR/WiDi/update/lock permission. Do not treat this parser as enforcement of those conditions.

## What the execution-condition helper actually rejects

The inspected helper returns `-1` for any of the following, in order:

| Branch evidence | Condition |
| --- | --- |
| `0x145c4–0x145dc`, failure at `0x14644` | `APPCTRL_IsAppLoading()` returns exactly 1 **and** bit 0 of the word at linked address `0x53500` is set. The loading accessor reads the adjacent word at `0x53504`. |
| `0x145e0–0x145f0` | Its third argument is nonzero. |
| `0x145fc–0x14620`, failure at `0x14668` | The queried app is not preloading, and its live state is 1 or 2. A nonzero preloading result bypasses this last state rejection, not the earlier checks. |

Otherwise this helper returns zero. The two live-state wrappers call `_APPCTRL_GetLiveAppItem`; for a nonnull record they read offsets `+0x58` and `+0x60`. Record lookup/creation, state writers and the meaning of every enum value remain untraced. The diagnostic string calls the rejected states “already loading or running”; their individual numeric names are not established by that text.

At caller `0x1600c–0x1601c`, the third argument is extracted from **bit 4 of app-info byte `+0x60b`**. A nonzero helper result branches away at `0x16024` and reaches the failure return. The success path can reach `_APPCTRL_ExecuteProcess` at `0x160a8`, but intervening and alternative execution branches exist; zero is not a universal launch guarantee.

A concrete writer of that bit is `AM_CMN_APPLIST_UTIL_SetAppExecuteInfo`: it reads the first word of its supplied execution-info descriptor at `0x2dc34`, inserts its low bit at `0x2dc48` and writes byte `+0x60b` at `0x2dc50`. The downloaded wrapper delegates to this utility, and `_AM_CMN_APPLIST_SetAppExecuteInfo` has a list-selector-4 call at `0x2d0ec–0x2d0fc`, connecting the writer to the previously identified USB-test list. This traces the field writer, **not** who constructs/authorizes that descriptor or whether its value rejects native types under some policy.

No direct native-type comparison occurs inside `_APPCTRL_CheckExecuteCondition`. Its diagnostic word “type” must not be mistaken for the XML app type: that diagnostic prints the global prohibition word. Absence of a native comparison in this small helper does not establish absence of a native restriction elsewhere, especially in the flag's producer or manifest provider.

## Account labels are selected metadata, not observed credentials

`_DOWNLOADED_GetAccount` switches on parsed `+0x28` at `0x35fe8–0x36024` and copies a fixed literal with `strncpy(..., 63)` to app-info **`+0x1594`**:

| Parsed type | Label | Copy call |
| --- | --- | --- |
| 1, 3, 5 | `flash` | `0x36058` |
| 2 | `browser` | `0x360cc` |
| 4, 7, 8, 9 — mapped to native by the earlier dispatcher trace | `game` | `0x36038` |
| 6, and out-of-range fallback | `others` | `0x360b0` |
| 10, 11 | `root` | `0x36074` |

The downloaded conversion passes its parsed record and app-info output to this helper at `0x37050–0x37058`. In `_APPCTRL_ExecuteProcess`, several paths pass app-info `+0x1594` as a stack argument to `AC_SEND_ExecuteProcess` (for example `0x17114–0x17138`). This connects the selected label to the send wrapper; it does not establish how the receiving supervisor resolves or applies it.

**PENDING:** passwd/group mapping, effective UID/GID, fallback on account failure, filesystem/mount execution permissions, supervisor validation and runtime privileges. In particular, neither the `game` label nor presence of a `root` case proves privilege level for our artifact. Nothing here proposes selecting another type or altering protected metadata to influence that label.

## Reproduction and stopping point

Ignored `artifacts/native-execution-conditions/` contains `capture.py`, fourteen disassembly JSON reports, `manifest.json`, `capture-summary.json`, `selected_data.py` and `selected-data.json`. The capture checks source/reader/tool hashes and exact symbol extents, rejects a summed range over 8 KiB, and checks repeat capture hashes. The selected-data reader resolves five imports through ARM PLT words and type-22 ELF relocations (`strcmp`, `strtol`, `strncpy` and two logging functions); it reads only explicitly selected technical literals. These are local vendor-derived evidence, not redistributed payloads.

```sh
PYTHONPATH=. python3 artifacts/native-execution-conditions/capture.py
python3 -m tools.arm_disassembly firmware/lab/app-lifecycle/open/bin/appctrl \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --start 0x14594 --end 0x146a8
```

Stop at the untraced execution-info descriptor producer, `_APPCTRL_GetLiveAppItem`/state writers, other execution branches, and supervisor account enforcement. The independent upctrl slice must resolve provider acceptance. A useful next narrowly scoped trace is the caller that constructs the descriptor consumed by `SetAppExecuteInfo`; a default bit value or a permissive account label alone cannot admit an ELF. No device-side experiment is justified by this slice.

## Experiment NATIVE-CONDITIONS-001

- **Objective:** recover XML type provenance and bounded downstream conditions/account selection.
- **Hypothesis:** native-looking conversion support still passes additional metadata/state gates.
- **Environment:** pinned selected official appctrl, existing symbol inventory, reviewed host LLVM wrapper; local static data only.
- **Procedure:** capture exact functions within 8 KiB, track field writes/call arguments, resolve selected imports and literals, and repeat capture consistency checks.
- **Expected result:** an exact field writer and explicit conditions, or a named unresolved dependency.
- **Observed result:** `app_type` decimal value writes `+0x28`; native classes select `game`; loading/prohibition/live-state checks and their supplied-bit writer are identified.
- **Conclusion:** type provenance is closed for this parser; native admission and effective account remain unproven.
- **Risks:** treating parser conversion as permission, account text as UID, or one helper's lack of a type check as absence of restrictions.
- **Next step:** reconcile provider evidence and trace the execution-info policy producer without creating a caller or changing device state.

## Follow-up producer trace

[Execution policy](native-execution-policy.md) now identifies XML `prohibit` and update-completion fields as concrete descriptor producers for lists2/3. Neither captured producer selects USB-test list4 or directly tests app_type. Upstream authority, other writers and the USB-test initial field remain unresolved. This narrows the prior producer gap without establishing native permission.
