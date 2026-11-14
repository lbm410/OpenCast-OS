# USB-test manifest admission: the appctrl boundary

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** appctrl's USB-test list joins the downloaded-app manifest/type/executable-info path. The native-type mapping in [native-execution-gates.md](native-execution-gates.md) is therefore not confined to an unrelated system-app parser. **PENDING:** whether the manifest provider accepts an owner-created native package, what integrity/entitlement policy it enforces, and whether later execution conditions permit that class. No native execution route is established.

The meaningful new boundary is `upctrl`: appctrl delegates manifest retrieval to that service and requires a successful provider result and XML parse before constructing executable information. A success/status check is not by itself evidence of signature verification. No protected owner package was read or decrypted, no metadata was patched, and no IPC, TV, network or target-execution operation occurred.

## Source and bounded method

Input: `firmware/lab/app-lifecycle/open/bin/appctrl`, 277,044 bytes, SHA-256 `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97`. Existing selected stock manifests and symbol inventory supplied context; no additional firmware extraction occurred.

The reviewed [ARM disassembly tool](static-disassembly.md) checked ELF executable-segment coverage and captured explicitly selected ranges with a 10-second deadline per capture. Host Apple LLVM 17.0.0 SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. No whole-image disassembly or target loading was used. Direct ARM branch candidates were scanned in the selected executable region, then checked against containing function symbols and actual instructions; this does not enumerate indirect callers.

Addresses below are linked ELF virtual addresses. For these code/literal ranges, file offset is address minus `0x8000`. In-memory field offsets are local data-flow observations, not a recovered public struct ABI.

## USB-test storage and list identity now connect

| Layer | Static evidence | Result |
| --- | --- | --- |
| List selector | `_AM_CMN_APPLIST_DOWNLOADED_GetAppListData`, `0x36120..0x361b4` | Selector 4 loads `0x56ef4`, the defined symbol `gAppListTestUSB`. Selectors 3/2 select `gAppListUSB`/`gAppListInternal`. |
| Storage selector | `_AM_CMN_APPLIST_DOWNLOADED_GetStorageType`, `0x36b40..0x36ba8` | List 4 maps to storage 3; list 3 to storage 2; list 2 to storage 1. Initialization stores this result at list record `+0x1c` (`0x36bf8..0x36c00`). |
| Storage base | `AM_CMN_GetAppstoreBasePath`, `0x29220..0x29348` | Storage 1 uses `/mnt/appstore/apps`; storage 2 appends `/apps` to the selected USB base; storage 3 appends `/lgapps`. |
| Installed directory | `AM_CMN_GetInstalledAppPath`, `0x29670..0x297a4` | Appends `/installed`, then `/<unsigned decimal app ID>` for a nonzero ID. ID zero selects the installed directory itself. |
| USB-base source | `_CMN_GetAppstoreUSBPath`, `0x2915c..0x29220` | Reads `gszUSBPath` (`0x56c8c`), requires a nonempty string and successful `access(path, 0)`, then copies it. No physical mount, permissions or active value is inferred. |

Thus the static USB-test path is `<selected USB base>/lgapps/installed/<app ID>`, matching the documented package layout. This is a code/path correspondence, not a trace captured from the owner's successful launch.

`APPCTRL_LoadDownloadedAppList` selects list 4 for its storage-3 branch (`0x233d0..0x233e4`) and calls `AM_CMN_APPLIST_LoadApps` at `0x232d4`. The latter forwards list selectors 2–4 to downloaded reload (`0x2bf98`). Reload calls `_CreateAppList` at `0x37448`; creation uses list `+0x1c` to obtain the installed directory, enumerates it through `opendir`/`readdir`, and constructs candidate app-ID records before `_MakeAppsInfo` at `0x37354`. That loop passes the same storage value to `_MakeAppInfo` (`0x37244..0x37248`).

This is not a harmless device-side enumeration command: the outer load routine also calls `APPCTRL_DeleteApptoUninstall`, handles invalid-list cleanup and updates state. Nothing in this report proposes invoking it. Physical insertion-to-reload event delivery and the writer of `gszUSBPath` remain outside this slice.

## The manifest is obtained before native type/path construction

The following connected path is **CONFIRMED (static)**:

```text
USB-test list (selector 4, storage 3)
  -> enumerate candidate installed app IDs
  -> _MakeAppInfo(app record, storage)
  -> ParsingAppidManifest(app ID, storage, parsed-manifest buffer)
       -> registered provider callback -> upctrl method/reply
       -> parse returned buffer
  -> _MakeAppInfoFromManifest(app record, storage, parsed buffer)
       -> installed app path
       -> _DOWNLOADED_GetAppType(storage, parsed field +0x28)
       -> write combined type to app record +4
       -> UTIL_GetExecuteInfo(parsed buffer, installed path, app record)
       -> account metadata and service update helpers
```

Key branch/call evidence:

- `_MakeAppInfo` calls `ParsingAppidManifest` at `0x371ac`. A nonzero result returns `-1`; only zero reaches `_MakeAppInfoFromManifest` at `0x371c8`.
- `ParsingAppidManifest` checks that its callback exists, invokes it at `0x31e84`, rejects nonzero status at `0x31e8c`, then passes the returned buffer and length to `_AM_CMN_APPLIST_MANIFEST_Manifest` at `0x31e9c`. A nonzero parser result also returns `-1`.
- `_MakeAppInfoFromManifest` obtains the installed path at `0x36d9c`; failure rejects conversion. It reads the parsed field at `+0x28` and calls the previously traced type helper at `0x36dc4`, storing the result at app record `+4`.
- The same function calls `AM_CMN_APPLIST_UTIL_GetExecuteInfo` at `0x3704c` with the parsed record and installed path. Therefore its native branch can consume the downloaded/USB-test conversion result. The immediately following code does not visibly branch on that helper's return; do not promote this to a guarantee of valid execution information.
- Account and service helpers are called at `0x37058` and `0x37068`. Their existence does not establish UID, ownership or privileges; neither was executed and their policies remain untraced here.

The buffer parser body and field `+0x28`'s precise XML provenance remain unreviewed in this slice. The earlier numeric-type conversion result is retained, but this report does not assume arbitrary owner-controlled XML reaches that buffer unchanged.

## Callback ownership and provider-result gate

`APPCTRL_InitAppList` explicitly installs two callbacks (`0x22264..0x22278`): `0x22178` for file paths and `0x22174` for app-ID/storage requests. Small forwarding functions connect them to `AC_SEND_GetManifestBufferFromFile` (`0x21c58`) and `AC_SEND_GetManifestBuffer` (`0x21ac0`). Registration writes the pointers at `0x55bcc` and `0x55bd0`; the parsing functions read those same locations.

Both wrappers construct a method directed to the defined service string `lg.service.special.upctrl`. The file variant and app-ID variant have distinct method names. Imported calls were correlated with ELF relocation entries: message creation, obtaining the process send connection, synchronous send/reply, reply-field parsing and unreference. No message was generated or sent by this investigation.

For the app-ID path, the wrapper initializes returned status to `-1`. A missing reply remains failure. A parsed reply must have status zero and nonzero byte-array length to reach its copy branch (`0x21c0c..0x21c38`); otherwise output pointers/lengths are cleared. The callback returns the provider status, after which the manifest parser decides whether it can parse the supplied buffer. A zero-length success reply does not by itself prove accepted usable XML. Allocation failure and the provider's complete response semantics were not audited.

The file-path route similarly requires a registered callback, builds a `manifest.xml` path and rejects provider/parse failure. The separate `AM_CMN_APPLIST_DOWNLOADED_ManifestToAppInfoEx` at `0x37670` uses that route with storage 1 and prints a constructed app-info object; it was **not** treated as the USB-test entry. The USB conclusion above follows the app-ID/storage chain instead.

After successful parsing, both parser functions perform `__xstat` on the installed path and may record a filesystem field. On the inspected `__xstat` failure branch, the previous successful parser status is returned; this is not a demonstrated mandatory integrity or admission check. It must not be cited as signature verification.

## What this establishes about native acceptance

**CONFIRMED (local static):** USB-test storage joins the same metadata construction path whose type helper preserves native classes and whose dispatcher can build native executable paths. No Web-only restriction was found in these specific conversion steps. The manifest provider succeeds before they run on the normal app-ID path.

**PENDING:** provider-side protected-manifest handling, signature/entitlement/account rules, model/developer restrictions, any filtering or rewriting of type fields, later execute-condition checks, executable permission/mount policy, effective account and the initial UI/event trigger. Appctrl's provider-result check does not establish which of those checks upctrl performs, or that they are absent. A path builder's acceptance of metadata is downstream of these unresolved questions.

Accordingly, neither “USB native apps are forbidden” nor “any native ELF can be launched from USB” follows from this result. The two routes now have a concrete common path; permission to put our native artifact on it is still missing. Do not edit/decrypt the protected package, reuse a system identity, call the private methods or replace service files to test the hypothesis.

## Next static slice and stopping condition

Identify the corresponding method-table entries and handlers in the official `open:bin/upctrl`, a name present in the existing package inventory and service list. That executable was **not selected or read by this task**. An explicitly bounded future selection should establish its hash/ABI before tracing only the two manifest handlers and their immediate result-producing callees. Determine where a provider response becomes success, which app-ID/storage/path inputs it uses, whether type filtering occurs, and which library owns protection/entitlement checks. Stop at an unavailable provider or cryptographic boundary and report it; do not attempt decryption or build a caller.

In parallel, the small appctrl XML-to-`+0x28` field writer can confirm how type reaches the parsed structure, and `_APPCTRL_CheckExecuteCondition` can identify later restrictions. These are complementary; neither should replace tracing the provider gate. A legitimate current issuer/developer route for a native package would still be required even if the static loader supports one.

## Reproduction and experiment record

Ignored `artifacts/native-manifest-admission/capture.py` pins the appctrl hash, uses the reviewed host tool and enforces a 16-KiB summed-range budget. Its JSON captures record exact selected-byte and normalized-disassembly hashes. `selected_data.py` verifies the same input, resolves the listed PLT imports through ARM stub instructions plus type-22 ELF relocations, and reads only selected technical literals. Neither helper executes target code. `manifest.json` inventories the capture budget. One exploratory storage-base capture extends into the beginning of its neighbor; `appstore-base-exact.json` narrows the final cited function, and no conclusion uses that neighbor.

Public-tool reproduction for the key conversion branch; substitute the explicit ranges above for the other captures:

```sh
python3 -m tools.arm_disassembly firmware/lab/app-lifecycle/open/bin/appctrl \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --start 0x37170 --end 0x37208
```

**Objective:** connect USB-test provenance to downloaded-type conversion and locate the admission gate. **Hypothesis:** an earlier manifest provider mediates the native-looking metadata path. **Environment:** selected official appctrl, existing inventories, reviewed bounded host tooling. **Procedure:** check direct callers; trace list/storage mappings, path builder, callback registration, provider reply and parse branches; correlate selected literals/imports. **Expected:** either connected routes with an identifiable gate or an explicit disconnection. **Observed:** USB-test selector 4/storage 3 joins the downloaded conversion; a successful upctrl-provided manifest and parse precede type/path construction. **Conclusion:** the route joins, but native entitlement/permission remains upstream and unverified. **Risks:** conflating directory enumeration, XML parsing or a zero status with cryptographic authorization; interpreting compiled paths as active-device behavior. **Next step:** bounded upctrl manifest-handler analysis, preserving all device state.
