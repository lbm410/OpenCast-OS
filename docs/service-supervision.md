# Service supervision and the Smart Home boundary

Evidence date: 2026-11-14. **CONFIRMED (local static)** unless another label is
shown. This report describes the official update's declarations and binary
contents, not the owner's active process tree or selected service list.

The normal service list declares **RELEASE and Smart Home as different
processes**: RELEASE receives the `reboot` policy, while `fxui Home.swf` receives
`respawn`. A second list declares a separate SWUE executable in place of
RELEASE. These are concrete reasons to preserve RELEASE and the process manager
while investigating a coexisting application surface. They do not establish a
safe way to replace Home, an available launch API, or a recovery procedure.

## Provenance and method

Inputs are the decoded `open.pak` and `swue.pak` from the preserved official
04.28.17 update; provenance and extraction boundaries are recorded in
[firmware-extraction.md](firmware-extraction.md). No firmware program, script,
service declaration or installer was executed. There was no network or TV
access, package modification, firmware reassembly, or persistent configuration.

Selected regular files were copied with the existing bounded
`tools.firmware_lab_squashfs` helper, which invokes the local host unsquashfs
under a sandbox and resource limits. Outputs are read-only files in the ignored
`firmware/lab/service-selected/` directory. The original package hashes remain:

| Package | SHA-256 |
| --- | --- |
| `open.pak` | `d89a800371ea6d2681813c974e4975be92730d10cccd77788945a88a4be33a48` |
| `swue.pak` | `af6a0225dd3b7fc5c5314aaa80b622ee8227540a799258dfa5a569ce53c1825b` |

| Selected path, relative to `service-selected/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `open/bin/procmgr` | 435528 | `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5` |
| `open/bin/svclist.rc` | 7686 | `74c6b2379f94b4122f0eae995cd3a8d02fe851d8150371e15119f4c1374e020d` |
| `open/bin/svclist_nonsmart.rc` | 7671 | `ee9deafb89a129b55f9bd5ced7333cb78d58f854bdd30f5b1470434aea0c0fac` |
| `open/bin/svclist_swue.rc` | 3237 | `58e145a78d23bb7aae9642468e7a8131c57a7e4ce80fff71d7e1e821a122d341` |
| `swue/SWUE` | 3911188 | `10fc93711d78bdab210c70bfd05525094422014f9d8c457914c7104fd3082554` |

Reproduce selected extraction only into **new** output directories; the helper
deliberately refuses to overwrite an existing selection:

```sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/open.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/service-selected/open \
  --select bin/procmgr --select bin/svclist.rc \
  --select bin/svclist_swue.rc --select bin/svclist_nonsmart.rc
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/swue.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/service-selected/swue --select SWUE
python3 -B -m tools.elf_inventory --tree firmware/lab/service-selected
```

Ignored `artifacts/service-analysis/` holds selection manifests, ELF inventory,
service declarations with source lines, targeted strings with file offsets,
dynamic symbol tables, relocations, and bounded disassembly. The declaration
inventory groups non-comment `tv|mgr|core|svc|appsvc` lines and following options;
it is a lexical inventory, not an implementation of the vendor parser.

## Declared startup and restart behavior

Line references below refer to the selected files, not this report.
`svclist.rc:13–78` documents boot-time `daemon` versus on-demand `instant`,
default account `root`, boot/background/foreground priorities, low-memory
adjustment, environment values, pre/post-TV startup ordering, startup waits,
focus, enable/disable, and termination policies.

| Policy | Meaning stated by file comments at `svclist.rc:63–72` |
| --- | --- |
| `oneshot` | No restart after normal or abnormal termination |
| `respawn` | Restart after abnormal termination only; default policy |
| `respawnalways` | Restart after both kinds of termination |
| `reboot` | Reboot after abnormal termination; no reboot after normal termination |

These meanings are **documented declarations**. The binary has additional
conditions, including a low-memory-killer check; they are not a complete runtime
contract for every signal, exit status or shutdown sequence.

| Normal list source lines | Executable / role | Explicit configuration |
| --- | --- | --- |
| 80–84 | `notimgr`, core notification service | pre, wait 0, respawn |
| 86–94 | `/mnt/lg/lgapp/RELEASE`, broadcast service | focus, pre, wait 0, **reboot** |
| 96–100 | `crashmgr` | pre, wait run, respawn |
| 102–106 | `lginput` | pre, wait load, respawn |
| 108–112 | `sdpif` | pre, wait load, respawn |
| 114–118 | `upctrl` | pre, wait load, respawn |
| 120–124 | `appctrl` | pre, wait load, respawn |
| 134–139 | `networkmanager` | **disable**, post, wait load, respawn |
| 141–148 | `fxui .../home/Home.swf`, `lg.service.normal.home2`, AUID `11174` | post, wait load, respawn; lowmem_adj 12; priorities 70/0/20 |
| 186–190 | `fxui .../myapps_mini/myapps_mini.swf` | post, wait load, respawn |
| 197–201 | `fxui .../nlp/voice.swf` | post, wait load, respawn |
| 203–207 | `/mnt/browser/run3556 0` | user browser, post, wait load, respawnalways |
| 209–215 | `/mnt/webbrowser/run_webbrowser 0` | lowmem_adj 13, post, wait load, respawnalways; user override commented |

The declaration inventory contains 33 service lines in the normal file, 14 in
the nonsmart file, and one in the SWUE file. These are not running-process counts:
one declaration is disabled, `runp2p` has `country chn`, and the normal file's last
`intermachine` declaration is surrounded by `#ifdef INCLUDE_NC40_SU1` / `#endif`
text. Whether those markers affect the vendor parser remains unverified. Neither
startup-list selection nor runtime overrides were observed on the physical TV.

The nonsmart list retains RELEASE (`:87–94`), appctrl (`:124–129`), input and
other core services while commenting the Home block (`:141–148`) and browsers.
RELEASE's wait is `run` instead of `0`. This is **evidence of a supplied variant**
with a reduced Smart service set, not permission or proof that switching to it
would preserve all functions on this unit. No variant was activated.

## Process-manager binary corroboration

`procmgr` is ARM32 little-endian EABI5, dynamically linked through
`/lib/ld-linux.so.3`, with 18 `DT_NEEDED` entries. They include `libafcommon.so`,
`libscf.so`, `libafopenapi.so`, `liblginputopenapi.so`, `libmtal.so`, and D-Bus.
ELF flags do not settle float ABI.

The dynamic symbol table contains defined functions for service-list startup,
restart, enable/disable, process execution, focus, graphics surfaces, and input
dispatch. Relevant symbol virtual addresses include:

| Symbol | Virtual address | What is established |
| --- | --- | --- |
| `PM_LIST_RestartService` | `0x3ae90` | Defined function; bounded branch analysis below |
| `PM_HNDL_RespawnTermProcesses` | `0x15b90` | Calls `PM_LIST_StartServiceList` at `0x15bc8` |
| `PM_HNDL_ExecuteProcess` | `0x16310` | Defined symbol; request contract not traced |
| `PM_HNDL_RequestFocus` | `0x145d4` | Defined symbol; authorization and semantics unverified |
| `PM_HNDL_SetWindowInputDispatchType` | `0x26394` | Defined symbol; no API invocation |
| `PM_HNDL_CreateWindow` | `0x26cc0` | Defined symbol; no rendering experiment |
| `PM_HNDL_CreateSurface` | `0x28cf4` | Defined symbol; no rendering experiment |

`PM_LIST_RestartService` disassembly covers `[0x3ae90, 0x3b028)`. At
`0x3af8c` a branch tests service-state bits against `0x10`; the reached path calls
`_PM_LIST_FinalizeWIFIDriver` at `0x3af94`, loads the string at virtual address
`0x6a028` (file offset `0x62028`, `/sbin/reboot`), and calls PLT `0x10b78` at
`0x3afa0`. The PLT resolves via GOT `0x75230`, whose relocation is
`R_ARM_JUMP_SLOT system`. Thus an actual reboot-command branch is present, not
merely a reboot string. No branch was executed.

Other paths test flags `0x0c` / `0x08` and reach an internal startup routine at
`0x3acd8`. A call to `PM_UTIL_IsThisProcessKilledByLmk` at `0x3af50` and a
separate killed-process path at `0x3afe8` prevent reducing the whole function to
the comments' two termination cases. The full caller argument enumeration,
policy-bit parsing, retry timing/limits, shutdown mode and signal decoding are
**PENDING**. Symbol names alone do not establish a usable external API.

Host disassembly used Xcode's `llvm-objdump`, with `-d --start-address=...`
and `--stop-address=...`, `--dynamic-syms`, or `-R`, under `sandbox-exec` denying
network and path writes; CPU 15 seconds, wall timeout 25 seconds, bounded output,
and no core dumps. Only the host tool ran. The ELF metadata parser did not invoke
`ldd` or load target libraries.

## Separate software-update service and watchdog evidence

`svclist_swue.rc:78–82` declares exactly:

```text
tv /mnt/swue/SWUE --service lg.service.special.broadcast
focus
runodr pre
waitfor 0
reboot
```

This provides a concrete alternative broadcast executable. The `procmgr`
binary contains `PM_SVC_LIST` at file offset `0x622c0` and the SWUE-list path at
`0x622cc`; the `lginit` selection analysis is separately discussed in
[claude-boot-review.md](claude-boot-review.md). This report does not independently
retrace all `lginit` branches or establish that the mode is reachable on the TV.

`SWUE` is a separate ARM32 little-endian EABI5 executable, with the same loader
path and 32 direct library dependencies. Those include `libmtk5398.so`,
`libmtal.so`, `librpc4dtv.so.1`, `libsecurestorage.so`, graphics/input framework
libraries, and GStreamer. Its dynamic symbol table defines
`API_DDM_INIT_WATCHDOG` at `0xbebb0` and `API_SWU_ResetMicomWatchdog` at `0x87118`,
and imports `DDI_SYS_SetWatchDogTimer`. These are **static symbol facts**, not
proof of an enabled watchdog, call sequence, timeout, or current feeder.

No explicit hardware-watchdog directive is present in the three selected
service lists. Software reboot-on-exit policy and a hardware/MICOM watchdog are
different mechanisms. Their runtime interaction remains unknown.

The separate SWUE path weakens a blanket claim that all update capability must
reside in a functioning RELEASE process. It does **not** establish recovery:
kernel/root/loader/library dependencies, mode selection, package verification,
partition writes, power-loss behavior and physical entry/reversal are unresolved.
Do not run SWUE, force update mode or use this report as a recovery plan.

## Candidate reversible integration boundary

**HYPOTHESIS:** an ordinary application or independently managed surface could
coexist with RELEASE, procmgr and essential services, obtain focus/input through
the established framework, and relinquish both on exit. The separate Home
declaration and process manager's graphics/lifecycle symbols make this a more
concrete research direction than replacing RELEASE wholesale.

The first candidate experiment is still a foreground application launched by an
already supported, reversible route. It would leave startup lists and original
Home assets intact; a normal application close should return to Smart Home, to
be verified physically. It would measure input focus, close/return, AV continuity
and relaunch, then consider a native surface only after the execution route,
client ABI and graphics/input lifetime are understood. No such route or native
experiment has been established here, and no IPC command is proposed for blind
execution. Automatic startup and Home-key redirection remain separate later
questions.

Stopping RELEASE is a poor initial experiment because its declared abnormal-exit
policy requests reboot. Stopping procmgr affects supervision beyond Home.
Killing `fxui` may invoke respawn and is not a demonstrated reversible method
for substituting Home. Activating the nonsmart list would alter startup behavior
and cannot be justified by the static variant alone.

Next local investigation: trace `appctrl` / `fxui` launch and focus registration,
their service-name/AUID mapping and exit behavior, then match that contract to
the existing native API analysis. Keep the stock Home as the return target.

## Experiment record

- **Objective:** identify declared supervisor boundaries and compare normal,
  nonsmart and software-update service paths.
- **Hypothesis:** Home and update execution may have narrower boundaries than
  the RELEASE hardware-control executable.
- **Environment:** macOS ARM64 host, preserved official-update packages, bounded
  host extraction/ELF tools; no connected-device operation.
- **Procedure:** select five regular files, hash/inventory them, inspect three
  service lists, inventory ELF metadata and symbols, and disassemble selected
  procmgr functions with relocation checks.
- **Expected result:** reproducible paths, policies and dependency evidence
  without running vendor code.
- **Observed result:** separate RELEASE/Home/SWUE declarations, reboot and
  respawn policies, a real reboot-command branch, independent SWUE executable,
  and framework lifecycle/graphics symbols.
- **Conclusion:** coexistence is a supported research hypothesis; a complete
  launcher-replacement or recovery mechanism remains unproven.
- **Risks:** host parsing of untrusted data was bounded; interpreting inactive
  templates or symbol names as runtime behavior remains the principal evidence
  risk. No TV state was changed.
- **Next step:** static app-control/focus contract analysis, then one consolidated
  owner-coordinated reversible physical experiment when a viable launch route
  is available.
