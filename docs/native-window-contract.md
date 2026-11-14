# Native window ownership: the fxui consumer boundary

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** fxui passes a framework window identifier directly into its EGL surface-creation call, stores separate surface/display/context handles, and exposes EGL initialization/termination callbacks through the Flash runtime interface. A generic identifier request is implemented by `libafopenapi` and delegates to `processmanagergx`; the actual native-window allocation and EGL implementation remain outside this slice.

The observed startup order includes framework readiness before `playerRun` and its rendering initialization. Consequently vendor “ready” cannot be equated with the `surface-owned -> ready` transition of our [host lifecycle model](native-entry-contract.md). The model defines OpenCast obligations; it does not recover the vendor protocol. No callable private ABI, IPC client, renderer binding or independent native admission is delivered here.

## Sources and bounded reproduction

Only existing selected files were read; there was no extraction, device/network operation or target execution:

| Input | SHA-256 |
| --- | --- |
| `firmware/lab/app-lifecycle/open/bin/fxui` | `98e05ccd63771c2609ec6af348cbbb875a8b4c7b1d176224c3abc80095dc8723` |
| `firmware/lab/app-lifecycle/lgli/libafopenapi.so.0.0.0` | `bbbfaa4c51c0fdb58f258dcb76d399929913c6ac6f11ba0743f227d6d0f50350` |

The reviewed [bounded ARM disassembler](static-disassembly.md) used Apple LLVM 17.0.0, host executable SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Nineteen exact captures total 8,024 bytes, within the 8-KiB budget; all reproduced. PLT instructions and ELF relocations identify imported calls. Selected callback-table words supply data-flow evidence; pointer names alone are not a recovered C/C++ header.

| ELF | Capture | Half-open linked address range |
| --- | --- | --- |
| fxui | Main | `0x37740..0x381e4` |
| fxui | Registration result wrapper | `0x3f3d8..0x3f43c` |
| fxui | Readiness result wrapper | `0x3f4a0..0x3f504` |
| fxui | Window-ID selector | `0x3f568..0x3f6e4` |
| fxui | Window-ID getter/setter | `0x38938..0x38958` |
| fxui | Focus request wrapper | `0x3f780..0x3f814` |
| fxui | Local focus setter | `0x9f350..0x9f35c` |
| fxui | Player driver | `0x3752c..0x37740` |
| fxui | Player constructor | `0x9ea98..0x9ec1c` |
| fxui | Player initialization | `0xa1b60..0xa1e24` |
| fxui | Runtime initialization wrapper | `0xa3cf8..0xa3d34` |
| fxui | EGL callback adapters | `0xa355c..0xa3594` |
| fxui | EGL initialization | `0xa5aec..0xa6008` |
| fxui | EGL termination | `0xa6008..0xa6090` |
| fxui | Player exit flag update | `0x9f1f4..0x9f2c4` |
| fxui | App exit request wrapper | `0x3f6e4..0x3f780` |
| fxui | Player destructor | `0x9f3c8..0x9f5b0` |
| fxui | Runtime finalization wrapper | `0xa3cd4..0xa3cf8` |
| libafopenapi | Generic window-ID provider | `0x2b3e4..0x2b5a8` |

For fxui captures, file offset equals linked address minus `0x8000`; for this libafopenapi capture it equals the linked address. Each JSON capture records the verified mapping, selected-byte hash and normalized-disassembly hash. Literal-pool words are data. LLVM labels the small adapters under a preceding exported symbol; their actual boundaries and uses are established by the table entries and instructions, not that nearest-symbol label.

## Registration, identifier and readiness are separate from rendering

Main constructs the player at `0x37888` before registering. It places three callback pointers in a stack record at `sp+0x154` and passes that record to `registerService` at `0x37944`: `appfrwkMsgHandler` (`0x38d58`), `appfrwkKeyEventHandler` (`0x3b748`), and `appfrwkMouseEventHandler` (`0x3e614`). The record is also referenced from global state. Its downstream copy/retention policy, callback threading and unregister/quiescence guarantees remain untraced; do not retain a temporary table in a future binding without establishing them.

The registration wrapper converts provider return zero into local success 1. Main checks for 1 at `0x37948`; failure reaches `exit(-1)` at `0x37f08..0x37f0c`. It next calls `getWindowID` at `0x3795c`, checks its local success value, and stores the returned identifier with `setRunArgsWindowID` at `0x37970`.

The selector contains dedicated stock-identity branches. In particular, the branch matching Home's previously identified AUID `0x11174` stores numeric identifier 26 at `0x3f69c..0x3f6ac`. That is a stock binding, not a free identifier or permission to reuse Home. The generic branch calls `HOA_GX_GetWindowID` at `0x3f620`, again translating provider return zero into local success 1.

The supplied libafopenapi defines this provider at `0x2b3e4`. Its body uses process PID/service helpers and the environment-variable name `PM_EXECPATH`, then sends a synchronous method request to the defined destination `lg.service.special.processmanagergx`. No environment value was read. It requires a reply, successful field parsing and a returned success field equal to 1 before writing the returned identifier (`0x2b4a4..0x2b538`); error paths return negative status. This is a provider-mediated lookup, not a local native-window constructor. Receiver allocation policy, ownership enforcement and handle validity remain unknown.

Main calls `setReady` at `0x379dc`, or through its stock-identity branch at `0x37c6c`, before reaching `playerRun` at `0x37b84`. Although the wrapper converts the provider result to 1/0, these main call sites do not check that returned value. If the auto-focus flag is set, main separately calls `requestToFocusedApp` at `0x37c80` and checks success before updating player focus. The wrapper requires a window ID and success from `HOA_APP_RequestToFocusedAppEx`; the local `FXPlayer::setFocus` merely stores a byte. Neither the local flag nor a request result proves visible focus restoration.

## Callback ownership and first EGL surface

The player constructor installs its vtable and initializes object fields `+0xe0`, `+0xe4`, `+0xe8` to zero (`0x9eb0c..0x9eb14`). These later hold EGL surface, display and context respectively. They are private observed offsets, not a public struct ABI.

`playerRun` calls `FXPlayer::init` at `0x3760c` and only enters the player run loop on a nonzero result. Initialization calls the local runtime wrapper at `0xa1bd0`. That wrapper passes the player pointer and a static callback interface at `0x16a948` to imported `fxCore_newIncrementalMemalloc` (`0xa3d20`), storing the returned runtime handle at object `+4`. The caller does not immediately branch on the wrapper's boolean result; later file/font setup has its own checks.

Two selected interface entries are concrete: `0x16aa10 -> 0xa355c`, and `0x16aa14 -> 0xa3580`. The first adapter dispatches through object-vtable offset `+0x74`; the second through `+0x78`. The constructed player's vtable entries at `0x1698dc` and `0x1698e0` resolve to `FXPlayer::egl_initialize` and `FXPlayer::egl_terminate`. This establishes the callback wiring. **PENDING:** when, how often and on which thread the external fxCore implementation invokes them. No direct `main -> egl_initialize` call or guaranteed first-frame ordering is asserted.

Inside the initializer, display acquisition/initialization, configuration enumeration and configuration selection have explicit failure branches. A configuration loop inspects component values; the driver supplies a 32-bit format field. These compiled preferences are not measured output format, acceleration or performance.

The key native-window coupling is at `0xa5f04..0xa5f18`: the saved run-argument window ID becomes the native-window argument of imported `eglCreateWindowSurface`. No fxui-side allocation of an X11/Wayland object or framebuffer mapping is present in this slice. The surface is stored at `+0xe0`; `eglCreateContext` at `0xa5f40` supplies `+0xe8`, and `eglMakeCurrent` follows at `0xa5f64`. Display/context/surface handles are returned through output pointers at `0xa5f68..0xa5f8c`.

The initializer explicitly rejects a zero context, but does not visibly check the surface-creation result before context creation, or the `eglMakeCurrent` return before reporting success 1. Its context-failure branch returns without local destruction of the already created surface. These are bounded observations about this consumer; they do not prove runtime leakage, exploitable behavior or absence of cleanup in the caller. A new adapter must track partial acquisition and check its own verified API results rather than copying these assumptions.

The concrete HOA wrapper provider is available and inspected. The actual implementations of EGL creation/destruction and fxCore invocation are external and uninspected here. Fxui's declared graphics libraries constrain provider research, but `DT_NEEDED` alone is not proof of runtime symbol resolution, a usable native-window type, or permission for a new process to allocate one.

## Teardown does not demonstrate return to Home

`FXPlayer::egl_terminate` attempts `eglMakeCurrent` with zero arguments, destroys the saved surface (`0xa6068`), destroys the saved context (`0xa6074`), and terminates the saved display (`0xa607c`). It returns 1 without testing these results or clearing the handle fields in this body. The zero-display unbind attempt is recorded as emitted code, not endorsed as a portable EGL recipe. Repeated invocation, render-thread quiescence and partial-initialization safety remain unproven.

The player destructor calls `fxCore::finalize` at `0x9f3f0`. The latter checks runtime handle `+4`, invokes imported `fxCore_delete` when nonzero and clears it. The interface has the EGL termination callback described above, but this slice does not establish that every runtime deletion calls it or waits for callbacks to finish.

`FXPlayer::exit` writes an exit-code field, a stop flag and an additional value (`0x9f26c..0x9f274`); it is not itself EGL teardown or a return acknowledgement. The separate app-exit wrapper requests `HOA_APP_ExitAppEx` and checks its return. Main also contains a specialized branch with app-exit, service unregistration and process exit (`0x37dc8..0x37dd4`). It is not the universal post-render cleanup path: `playerRun` can end with libc `exit` at `0x37690`, including after initialization failure. The run-loop's cleanup and surrounding callback transitions are outside the remaining budget.

Accordingly, surface destruction, runtime deletion, app-exit acknowledgement and regained stock focus are four distinct outcomes. No captured device observation or selected branch establishes a completed return to Home, restored HDMI/audio, or release of the framework-owned window identifier.

## Small binding obligations and stopping point

1. Obtain an independently admitted identity and its own valid window assignment; never reuse Home or identifier 26. Determine the actual native-window/provider contract before choosing an EGL type or header.
2. Keep process-registration readiness, graphics readiness and focus acknowledgement separate. An eventual adapter must map these to the host model explicitly, not forward identically named events blindly.
3. Establish callback-table retention, invocation thread and cancellation/quiescence. Retain instance state until callbacks and rendering are acknowledged stopped.
4. Track display, surface, context and runtime ownership separately; check partial-failure results and make cleanup idempotent. The vendor consumer's unchecked calls are not our safety contract.
5. Require an observed/acknowledged return destination in addition to cleanup. Process exit or a local focus byte is insufficient.

This slice stops at the fxCore callback scheduler, processmanagergx window owner and actual EGL implementation. The highest-value next static step is the corresponding window-ID receiver/allocator and destruction policy, followed by the demonstrated run-loop exit path if budgeted separately. Neither requires constructing private IPC or changing the TV. Account/admission research remains separate.

Ignored `artifacts/native-window-contract/` contains the pinned capture script, 19 JSON captures, relocation-annotated text, selected callback/provider data and `manifest.json`. From repository root, `PYTHONPATH=. python3 -B artifacts/native-window-contract/capture.py` rechecks the captures. Public-tool reproduction for the surface constructor uses `python3 -m tools.arm_disassembly firmware/lab/app-lifecycle/open/bin/fxui --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump --start 0xa5aec --end 0xa6008`; substitute exact table bounds for the other ranges.

**Objective:** identify the first native-window consumer and lifetime obligations. **Hypothesis:** framework window assignment and EGL ownership are separate from registration/readiness. **Environment:** two selected official ELFs and bounded host tools. **Procedure:** trace startup and window-ID lookup; resolve callback tables; inspect EGL acquisition/failure/teardown and selected exit paths; reproduce captures. **Expected:** concrete handle/provider flow and explicit unresolved boundaries. **Observed:** framework identifier passed to EGL, callback-managed initialization/termination, readiness before player setup, and incomplete proof of close restoration. **Conclusion:** a minimal binding needs separate window, graphics, readiness and callback contracts; no drop-in private API is established. **Risks:** reusing stock IDs, equating ready with first frame, assuming callback cleanup or treating process exit as restored focus. **Next step:** bounded receiver/allocator and run-loop teardown research, without device operations.
