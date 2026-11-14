# Native execution: the missing admission boundary

Date: 2026-11-14. **Decision:** prioritize the application-metadata-to-executable trace before building a graphics client. The bounded trace now confirms native type dispatch and executable-path construction, including native type mapping in a downloaded-app helper; no evidenced route admits our own ELF to that path. More registration or rendering code cannot close that earlier gap by itself.

This combines existing evidence with four bounded static disassemblies of the selected official appctrl and read-only literal/relocation checks. No target execution, IPC, TV/network operation, installation, protected-manifest decoding or Git action occurred. No new external source was consulted.

## What has and has not crossed a boundary

| Boundary | Established evidence | Still missing |
| --- | --- | --- |
| C source → ARM object | Our lifecycle core compiles to a 3,140-byte ARM32 EABI5 `ET_REL` object, SHA-256 `9547a71d900776c76a35da8bbbebc642bc3bde5613b28dffd37d25dfda5a483d`; no program headers, interpreter or undefined symbols. [Lifecycle core](native-lifecycle.md) | Executable entry/startup, ARM ELF link, appropriate runtime/ABI and loadable segments. An object with no undefined symbols is still not a process image. |
| Own web content → admitted application | Official corrected USB package renders and accepts arrows/OK on the owner's TV. [Deployment](app-deployment.md) | Independent native binary admission. Package success concerns HTML/CSS/JavaScript, not an arbitrary ELF carried alongside those assets. |
| Admitted application metadata → managed launch | Appctrl calls `AM_CMN_APPLIST_GetAppInfoEx`; failed lookup returns through an error/previous-app path. Procmgr's managed path reaches `vfork` and `execve`. [Lifecycle](app-lifecycle.md), [admission](native-admission.md) | Which externally obtainable app class can select a custom native path, how its metadata is trusted, and which account/permissions apply. |
| Already running process → framework registration | Receiver can insert an absent PID-keyed record; SCF wraps D-Bus; a registration state callback is identified. [Bus/state trace](native-bus-policy.md) | Initial process execution, active socket/policy access, sender/identity rules and complete registration outcome. Record insertion is not process creation or a privilege grant. |
| Registered process → usable shell | Vendor fxui has registration, window, readiness, focus and exit paths; our host model tests ownership. [Entry contract](native-entry-contract.md) | Actual native window/callback ABI, input lifetime, restoration and essential-service continuity. No real platform adapter exists. |
| Usable shell → automatic startup | Kernel fallback and service supervision are statically understood in selected slices. [Kernel selection](kernel-init-selection.md) | A permitted persistent integration point, active boot evidence and independently verified recovery. A one-shot process would not satisfy this gate. |

The build and admission tracks are independent. A linker/sysroot closes part of the first row; it does not create an upload, launch or authorization mechanism. Conversely, an admission route would still need a correctly linked artifact. A minimal libc-free executable could reduce dependency scope, but would still require verified startup/syscall/ISA contracts and the same admission boundary; this report does not select or implement one.

## Candidate routes and next bounded experiment

| Candidate | Evidence and exact unknown | Next bounded experiment / acceptance | Return and recovery requirement |
| --- | --- | --- | --- |
| Official downloadable Web app | **CONFIRMED (physically observed)** HTML shell execution. Protected portal manifest remains opaque; no evidence it admits ELF execution. | Run the already prepared lightweight Web candidate in one coordinated owner session. Accept only observed rendering, D-pad/OK, normal return and repeatability; classify this as Web progress. | Explain launch/effects/return before execution; preserve baseline package; verify successful-build Home return and HDMI/audio continuity. |
| Official hosted Web app | **CONFIRMED (documentary)** server URL instead of downloadable source; the USB launcher still supplies the application context. LAN URL acceptance and current hosted packaging are **PENDING**. | If iteration cost justifies it, prepare a package pointing to the bounded local HTTP server and inspect it before owner launch. Accept only actual hosted-app rendering/reload/input/return. | Stop/close through the app's normal exit route; test failure when its server is unavailable. This does not authorize native APIs or OS execution. |
| Ordinary browser URL | **CONFIRMED (physically observed)** page/clicks and Home return; cursor-style arrows in that session. | Use only for browser capability questions that cannot be answered by the packaged test. No native capability is inferred from JavaScript or HTTP. | Preserve ordinary browser Home/Exit; no private input-mode changes. |
| Custom native application admitted by appctrl | **HYPOTHESIS.** Stock Internet manifest has `app_type=8`, a wrapper pathname and `is_system_app=Y`; Home has `app_type=11`, `Home.swf` and the same system flag. The new slice confirms a Native dispatch and downloaded-type mapping, described below. The later USB-test trace connects storage 3 to this converter; provider trust and current native issuer availability remain unresolved. | Continue from the connected USB-test path through AppInfo provenance and provider acceptance; compare the historical official native-runtime issuer route. Accept the static slice only when each type decision is connected to its provenance and launch condition. A native-looking filename or helper name is insufficient. | Before any future launch: distinct identity, permitted temporary location, known effective account, normal stop path and no edits to vendor manifests/services. Preserve stock Home and RELEASE. |
| Independently started process then SCF registration | **HYPOTHESIS.** An existing process can supply registration fields and receiver insertion exists; active access and full registration remain unproven. No independent starter is available. | Investigate only after identifying a legitimate initial execution mechanism; then finish transport identity, ordering-state and teardown analysis. Accept independently evidenced entry and bus permission, not a permissive shipped policy alone. | Registration can affect focus/state; stop cannot be assumed equivalent to restoration. Require owned-resource cleanup, bounded failure handling and verified return. |
| Developer/debug or privileged route | **PENDING.** The reviewed official IDE Run on TV path requires prior USB launch and is not an independent native loader. No verified SSH/Telnet/native developer channel exists. | Static official-document or firmware investigation only, scoped to a concrete candidate if found. Do not convert private method names into a launch command or infer access from historical sibling-model research. | Any privileged/persistent candidate needs specific authorization and verified recovery before use; no opaque payload, unauthenticated shell or service-menu shortcut. |
| Service-list, Home identity or kernel-init replacement | **PENDING integration**, not an initial execution shortcut. Kernel fallback to `lginit`/shell is compiled behavior; active bank/command line are unknown. | Keep static analysis separate. First prove independent reversible native execution and coexistence, then evaluate startup changes against recovery. | Level 3: explicit authorization plus recovery independent of the changed components. No reuse of Home's AUID, editing its declaration or changing boot parameters now. |

The first three routes are content execution contexts, not evidence of arbitrary native execution. The next two are separate OS/application-framework boundaries. Elevated privileges are a further property: neither a registered service nor a process launched by procmgr proves UID 0, privilege escalation or permission to modify the system. Conversely, do not assume root is necessary until the chosen resource and policy requirements have been established.

## Completed bounded slice: type provenance to executable path

Use the already selected appctrl, 277,044 bytes, SHA-256 `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97`, at `firmware/lab/app-lifecycle/open/bin/appctrl`. Addresses below are ELF linked addresses. Symbols and sizes were cross-checked against `artifacts/app-lifecycle/appctrl-symbols.txt`; the four ranges below were then independently disassembled with the reviewed [bounded host tool](static-disassembly.md).

| Order | Bounded range | Question to settle |
| --- | --- | --- |
| 1 | `_AM_CMN_APPLIST_MANIFEST_GetAppTypeFromString`, `[0x311c0,0x312e8)` | Which exact textual/numeric type representations map to internal types? Are unknown types rejected or defaulted? |
| 2 | `_AM_CMN_APPLIST_DOWNLOADED_GetAppType`, `[0x36c40,0x36d58)` | Does the downloaded path preserve, translate or restrict those types? Do not assume this path includes USB tests until its caller is traced. |
| 3 | `AM_CMN_APPLIST_UTIL_GetExecuteInfo`, `[0x2f370,0x2f4b8)` | Which type selects each runtime/native helper, and what data reaches that dispatch? |
| 4 | `_AM_CMN_APPLIST_UTIL_GetExecuteInfoNative`, `[0x2f1c4,0x2f294)` | Is the executable fixed, derived from trusted metadata or resolved relative to a storage class? What is copied as arguments? |

These four captured ranges total 1,112 bytes. Expand only along demonstrated calls/data flows. Likely next targets, still **PENDING behavior**, are `_AM_CMN_APPLIST_MANIFEST_ParsingExecFile` `[0x30424,0x30530)`, `AM_CMN_APPLIST_UTIL_SetAppExecuteInfo` `[0x2dba8,0x2dcbc)`, and `AM_CMN_APPLIST_DOWNLOADED_SetAppExecuteInfo` `[0x36794,0x3682c)`. Correlate them with the already traced `_APPCTRL_ExecuteProcess` at `0x17068`, then the existing procmgr creation/account checks. Avoid broad disassembly or guessed C struct declarations.

### Results: native mapping is present, admission remains upstream

**CONFIRMED (local static):** the manifest type parser calls `strtol(value, NULL, 10)` at `0x311fc`, subtracts one and indexes an eleven-case table. A null pointer returns `-1`; an out-of-range conversion returns zero. This helper does not check an end pointer, so its numeric conversion must not be described as strict validation of the entire string.

| Parsed number | Internal type bits | Dispatcher target |
| --- | --- | --- |
| 1 | `0x030000` | Flash helper |
| 2 | `0x040000` | Browser helper |
| 3 | `0x050000` | Plex helper |
| 4 | `0x080000` | Native helper |
| 5 | `0x090000` | AdobeAir helper |
| 6 | `0x060000` | TrickPlay helper |
| 7, 8, 9 | `0x070000` | Native helper |
| 10 | `0x010000` | TV helper |
| 11 | `0x020000` | FXUI helper |

The target names above are defined firmware symbols matched to actual branches, not proposed public SDK enum names. The dispatcher masks the app-info word at `+4` with `0x00ff0000`; both `0x070000` and `0x080000` reach the Native helper through the branch at `0x2f46c`. Its inputs are already parsed records; it is not itself a package admission check.

The downloaded-type helper maps its second argument through the **same numeric table**, including both native classes. It then augments the result according to its first argument: `1` adds `0x03000000`, `2` adds `0x04000000`, and `3` adds `0x05000000`; other first-argument values log an invalid-storage diagnostic and return zero. The later [manifest-admission trace](native-manifest-admission.md) maps storage 1 to internal app storage, 2 to USB `/apps`, and 3 to USB-test `/lgapps`; the four-function slice alone did not establish those meanings. An unknown second argument is logged and initially mapped to zero, but valid storage still adds its high bits: the caller must determine whether that result is rejected. Thus this helper alone neither whitelists Web-only apps nor proves native admission.

The Native helper has two concrete filename cases. It compares the first five bytes of the string at input record `+0x30` against `/mnt/` using `strncmp` at `0x2f1fc`. A match copies that string to output record `+0x614` with a 255-byte `strncpy` bound. Otherwise it formats `%s/%s` into that output field with `snprintf(..., 256, ...)`, using the helper's second argument as prefix and the input filename as suffix. It copies the input `+0xeb0` argument string into output `+0x714` with bound `0xe7f`, then returns zero. The null-input path returns `-1`. Callers, field initialization, source-string termination, formatting truncation handling and path authorization are outside this slice; no safe writable/executable directory follows from these operations.

Four imported calls were independently resolved through ARM PLT words and type-22 ELF relocations: `0x13ac8→strtol` (GOT `0x51308`), `0x13d20→strncmp` (`0x513d0`), `0x13cfc→snprintf` (`0x513c4`) and `0x1381c→strncpy` (`0x51224`). Literal slots `0x2f280` and `0x2f284` point to `/mnt/` and `%s/%s`. This supplies code/data evidence beyond suggestive helper names.

**Follow-up evidence:** [manifest admission](native-manifest-admission.md) connects USB-test list selector 4/storage 3 through the upctrl provider and XML parse to this conversion. [Execution conditions](native-execution-conditions.md) identifies XML `app_type` as the source of parsed `+0x28`, account label `game` for the examined native classes, and loading/state/supplied-flag checks. [Provider gates](upctrl-manifest-gate.md) identifies AppInfo-first construction followed by a protected-manifest fallback with a checked verifier call. These resolve several static provenance edges; current native package admission, effective account and executable permissions remain **PENDING**. The decision table remains **source/storage class → manifest trust step → accepted type → executable path → execution condition → account**. Stock Internet/Home manifests are system examples, not reusable templates. No alteration of protected metadata is proposed.

A useful rejection result would identify the caller's gate that excludes native types for owner-created apps. A useful positive result would trace an admitted native class to a legitimate package issuer/developer mechanism; it would still require proving that the current portal can issue that class. Neither result justifies fabricating metadata or invoking the private bus.

### Reproducibility

Ignored `artifacts/native-execution-gates/` contains four disassembly JSON reports with full input/tool/range/output hashes, plus `selected_data.py` and `selected-data.json` for the four selected literals and PLT relocations. Apple LLVM 17.0.0 host executable SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. No target libraries were loaded. Each disassembly used a 10-second overall deadline and the reviewed tool's input/range/output caps.

All four disassemblies can be reproduced after obtaining the same official file using the published tool; substitute each start/end pair from the range table:

```sh
python3 -m tools.arm_disassembly firmware/lab/app-lifecycle/open/bin/appctrl \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --start 0x2f1c4 --end 0x2f294
```

The ELF maps these function addresses to file offsets by subtracting `0x8000`; the reports validate executable-segment coverage. A fresh rerun must match input and selected-byte hashes; normalized display hashes avoid dependence on temporary snapshot filenames. No target execution test or TV result is claimed.

## Acceptance before the first native device experiment

1. Identify a legitimate entry route with explicit supported/verified artifact type, delivery location and launch trigger. Document its privileges and temporary/persistent effects; do not assume account or USB entitlement implies native admission.
2. Produce and inspect our own linked artifact with the chosen ISA/calling convention, entry, segments, interpreter and required providers resolved. Scope the first program to a bounded, non-graphical observable action and normal exit if the admitted route supports it; do not use successful graphics registration as the only execution proof.
3. Define how the exact artifact's execution will be distinguished from a browser/runtime success, how completion/failure is observed, and how to stop it without terminating vendor services. A UI screenshot alone cannot prove a separate native process.
4. Present the concrete mechanism, effects and return path before any owner-coordinated reversible execution. Require specific authorization and independently verified recovery if it introduces privileges or persistence; readiness of host code is not authorization.
5. Only after execution/exit is demonstrated, add the reviewed registration/window/input adapter. Validate normal and failed exit, repeat launch, Home/focus restoration and essential AV continuity. Autostart remains a separate gate.

## Assessment record

**Objective:** identify the missing edge from a compiled object to physical native execution. **Hypothesis:** existing service/lifecycle evidence describes downstream cooperation, while admission of a custom native executable remains unresolved. **Environment/procedure:** read the current deployment, lifecycle, bus, kernel and architecture reports; inspect selected Home/Internet manifests as data, then independently disassemble four exact appctrl ranges and resolve four PLT calls/literals. **Expected:** either an evidenced native starter or a concrete missing contract. **Observed:** official Web execution is real; managed native creation exists internally; no demonstrated bridge admits our ELF. The four-function trace confirms native mappings and path construction, including downloaded-type conversion, but not the trust/admission edge. **Conclusion:** trace the upstream USB/downloaded admission caller alongside Web performance testing; do not equate more ABI/framework code with execution access. **Risks:** conflating system and downloadable types, shipped and active policy, or registration and privilege. **Next step:** recover the type/provenance decision table and then choose a permitted execution experiment only if the admission edge is actually established.
