# Native interface evidence

Date: 2026-11-14. Static analysis only. No native library was loaded or called.

## Method and reproducible artifacts

Selected regular files were copied through the reviewed SquashFS list/cat helper into `firmware/lab/lgli-api-selected/` and `base-api-selected/`. Source images remain read-only. The existing Xcode `llvm-nm` inspected dynamic symbols with `--dynamic --format=posix`, in a macOS sandbox denying network, path writes and other program execution. Each process had a 10-second CPU bound, 15-second wall bound and 4 MiB output-file limit. Outputs are under ignored `artifacts/firmware-lab/symbols/`; every invocation completed successfully.

`U` means an undefined/imported symbol; `T` means a defined text symbol. Addresses below are ELF symbol values, not observed live process addresses. Names suggest responsibilities but do not establish callable signatures or safety.

## Findings

| Evidence | Status and implication |
| --- | --- |
| `libtv.so`: `HOA_GX_SetWindowInputDispatchType U`; `liblgopenapi.so.0.0.0`: same name `T 0x9c458`, size 0x1b8 | CONFIRMED import/provider relationship in selected binaries; a concrete input-routing function to investigate statically |
| `libtv.so`: `BROWSER_DFB_Inputdriver_Initialize T 0x1caec`, size 0x10 | CONFIRMED symbol; likely browser/DirectFB input initialization boundary, behavior PENDING |
| `libtv.so`: `TV_CMN_TerminateLauncher T 0xb044`, size 0x94 | CONFIRMED symbol, not authorization to invoke termination or proof it affects only visual UI |
| `RELEASE`: `API_VCS_ChangeInputDispatchType T 0x61a94c`, size 0x68 | CONFIRMED native implementation symbol; cross-reference to exported wrapper and dispatch protocol PENDING |
| `RELEASE`: `API_CECP_ChangeHDMIPort T 0xc44e28`, size 0x3c, plus multiple defined HDMI/audio/video functions | CONFIRMED native definitions, supporting the hypothesis that RELEASE participates in essential functions |
| `RELEASE`: `API_SWU_ResetMicomWatchdog U` | CONFIRMED imported symbol; actual watchdog initialization, cadence and supervision behavior PENDING |

The RELEASE symbol inventory contains 42,397 dynamic entries; liblgopenapi has 3,051. Symbol presence makes targeted disassembly possible. It does not turn these private interfaces into stable/documented APIs. No function prototypes, enum values, IPC packets or service calls have been guessed or executed.

## Targeted wrapper reconstruction

Static ARM disassembly of `HOA_GX_SetWindowInputDispatchType` at 0x9c458 is stored in `artifacts/firmware-lab/symbols/HOA_GX_SetWindowInputDispatchType.asm.txt`. Its PLT calls, correlated with `.rel.plt` and `.dynsym`, identify `HOA_UTIL_GetProcPID`, `HOA_UTIL_GetProcServiceName`, `HOA_UTIL_GetProcSendConnection1`, `SCF_BUS_Message_Create_Method`, `SCF_BUS_Message_Send_And_Wait_Reply`, `SCF_BUS_Message_Get_Any`, and `SCF_BUS_Message_Unreference`.

The Create_Method PLT stub at 0x38724 computes GOT address 0x140488: PC 0x3872c + 0x100000 + 0x7000 + 0xd5c. The relocation at that address names SCF_BUS_Message_Create_Method, independently checking the PLT-index mapping. Resolving the wrapper's PIC base gives 0x1403ac and the following four argument string addresses:

| Register at message creation | String address | Value |
| --- | --- | --- |
| r0 | 0x119aa8 | lg.service.special.processmanagergx |
| r1 | 0x1145cc | /hoa/proc |
| r2 | 0x1080b4 | lg.if.service |
| r3 | 0x11986c | HOA_GX_SetWindowInputDispatchType |

**CONFIRMED (static data/control flow):** this wrapper uses a message-construction and reply path with those names. **HYPOTHESIS:** a service-mediated integration boundary may permit an independent shell to retain vendor services. Transport details, process registration, authorization, argument semantics, timeout behavior and the receiving implementation remain PENDING. Strings resembling D-Bus names are not enough to assume a standard unrestricted D-Bus endpoint. No IPC message was constructed for transmission or sent to the television.

## Architecture consequence

Treat RELEASE as a candidate host for essential TV services, not as a process that can simply be killed to replace the screen. Investigate a separately hosted shell using an established application/runtime boundary first. Keep input and native TV actions behind capability adapters; the UI must report unavailable operations until each adapter is verified. A future Siri bridge can use independently validated network actions and need not depend on replacing native processes.

## Experiment NATIVE-001

- Objective: identify concrete native import/provider relationships and control boundaries.
- Hypothesis: dynamic symbols expose more precise integration leads than arbitrary binary strings.
- Environment: selected official ELF files, installed Apple LLVM tools, offline sandbox and bounded local output.
- Procedure: inspect dynamic symbols for RELEASE, lginit_app and five selected libraries; retain bounded full metadata locally; select input/graphics/app/power/HDMI names for review.
- Expected: symbol records or explicit tool failure without executing target code.
- Observed: seven successful inventories, including matched input-dispatch import/provider names and native TV-related definitions in RELEASE.
- Conclusion: there are concrete static-analysis targets; safe runtime access and separation remain unproven.
- Risks: treating names as semantics or accidentally executing native control; avoided by static metadata-only inspection.
- Next: disassemble the identified wrappers, identify IPC/argument contracts, and reconcile with Claude's independent boot/recovery review.


## Receiver and lifecycle follow-up

[App lifecycle tracing](app-lifecycle.md) now matches the input wrapper to procmgr's method table, handler and input-manager dispatch path. [Native admission tracing](native-admission.md) identifies both managed-launch and message-receiver process-table insertion. These narrow earlier receiver/registration unknowns; they do not establish IPC authorization, callable enum/layout contracts or successful standalone access. No service call has been sent.
