# Nonpersistent native shell: entry contract

Evidence date: 2026-11-14. This investigation separates three achievements:
rendering OpenCast inside an admitted application, running an independently
managed native shell, and replacing startup/system components. The first is a
useful execution and input experiment; it does not establish either later step.
The immediate native target is **a separate foreground surface beside RELEASE**,
with stock Home retained as a return destination. Kernel replacement is outside
this contract and would additionally require drivers, boot and recovery work.

**CONFIRMED local results:** the inner registration dispatcher checks a process
record, but the outer method receiver can create a missing record first. The
follow-up [native-admission.md](native-admission.md) establishes this important
qualification: prior supervisor launch is not proven mandatory. The installed
Apple compiler also produces ARM32 EABI5 objects. Later builds include the
[current window lifecycle object](native-lifecycle-arm-build.md) and a separate
[linked minimal probe](native-probe-build.md). Neither build nor record insertion
establishes native admission or permission to invoke the vendor framework.

## Evidence and the missing admission step

The selected binaries and hashes are recorded in
[app-lifecycle.md](app-lifecycle.md) and
[service-supervision.md](service-supervision.md). The examined `procmgr` SHA-256
is `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5`.
No source file, service declaration or target process was modified.

Previously traced facts remain relevant:

- Appctrl resolves application metadata through `AM_CMN_APPLIST_GetAppInfoEx`
  before its execution route; a pathname is not demonstrated admission.
- Home has a distinct service and AUID. Its fxui argument `11174` is parsed in
  base 16 and matches manifest ID 70004. Reusing that identity would not create
  an independent application.
- Fxui registers, obtains window information and reports readiness. A specialized
  main branch performs application exit, service unregistration and process exit;
  the general post-render cleanup/return path remains unproven. The later
  [window trace](native-window-contract.md) also finds a `playerRun` libc-exit path;
  no universal teardown or restored focus follows.

New bounded disassembly tightens the registration prerequisite:

| Static location | Observed behavior | Consequence |
| --- | --- | --- |
| `PM_HNDL_RegisterService` at `0x14790`; `PM_HNDL_SetReady` at `0x146c8` | Both call the shared routine at `0x1437c`, with different operation selectors | The named handlers do not directly implement independent registration/readiness operations |
| `0x14394–0x143ac` | Handler argument `r2` becomes the first argument of `PM_PROC_SelectProcTable`; a stack buffer receives its output | The inner dispatcher checks a PID-keyed record; the outer receiver may have just created it |
| `0x143b0–0x143b4`, `0x144c4–0x144fc` | Nonzero lookup result enters a failure path, returning `-1`; the registration wrapper's reply flag enables a negative `PM_SEND_Return` | This inner check does not establish mandatory launch through procmgr |
| `PM_PROC_SelectProcTable`, `0x1ba18–0x1baa4` | Locks a mutex, calls lookup helper `0x1a410`, rejects a negative index, otherwise copies a `0x758`-byte record, then unlocks | Follow-up analysis finds both creation-after-vfork and method-receiver insertion; key authenticity remains unresolved |
| `0x143c4`, `0x143f0`, `0x14420–0x14458` | Compares a string field, may update a table signature, then selects a callback through a state/operation table | Readiness and registration depend on state, not only a correctly spelled service name |

These are data/control-flow observations, not recovered C prototypes. In
particular, the string called a signature by `PM_PROC_UpdatePTSignature` is
**not evidence of a cryptographic signature**. The dispatcher has duplicate and
error paths; its operation values do not define a public enum.

The outer `PM_HNDL_MethodHandler` checks the decoded PID at `0x17da4` and calls
`PM_PROC_InsertProcTable` at `0x17e50` on lookup failure, before dispatching to
the specific handler. This supersedes any inference that the inner lookup alone
prevents independently started processes from registering. Whether such a
process can access the connection and complete registration is still unknown.

Ignored evidence lives in `artifacts/native-entry-contract/`:
`procmgr--registration_dispatch.txt` and
`procmgr--PM_PROC_SelectProcTable.txt`. Host `llvm-objdump` inspected only these
address ranges, under a sandbox denying network and writes, with CPU/time/output
bounds. The existing scratch resolver in `artifacts/app-lifecycle/inspect_static.py`
correlated PLT calls with ELF relocations. No vendor code was loaded or executed.

## Dependencies that constrain a replacement client

| Boundary | Concrete evidence | Evidence needed before implementation |
| --- | --- | --- |
| Loader and C ABI | Fxui/appctrl/procmgr are ARM32 little-endian EABI5 with `/lib/ld-linux.so.3`; selected libc/loader filenames are 2.12.2 | Verified sysroot, symbol-version requirements, compiler runtime compatibility and per-dependency ABI; filenames alone do not establish compatibility |
| Registration and IPC | Fxui imports `HOA_PROC_RegisterService`; libafopenapi performs SCF initialization, connection and callback setup. SCF wraps D-Bus; shipped policy and the initial registration state callback are identified in [bus/state analysis](native-bus-policy.md) | Actual argument layouts, callback threading, timeout/error ownership, active sender policy and complete ordering/registration outcomes |
| Application identity | Appctrl requires metadata; stock Home has its own service/AUID | A legitimate native admission mechanism, a distinct identity and allowed executable location; successful web packaging does not prove native ELF admission |
| Graphics | Fxui directly needs `libEGL.so`, `libGLESv2.so`, `libIMGegl.so`, `libsrv_um.so` and `libfxcore.so`; it imports EGL display, initialization, window-surface and teardown functions plus `HOA_GX_GetWindowID`. The [consumer](native-window-contract.md) passes a framework identifier to EGL; the [receiver](native-window-allocation.md) separates conditional reservation from surface creation | Service-bound ownership, actual EGL/native-window ABI and provider semantics, callback quiescence, focus restoration and acknowledged teardown; a successful reply or numeric ID is not a lease |
| Input and focus | Appctrl sends focus requests; procmgr implements window/input dispatch and depends on `liblginputopenapi.so` | Key event delivery/callback ABI for an owned window, repeat semantics, focus loss/restore and Home handling; no global input-mode change is part of the first client |
| Essential TV services | RELEASE is a separate service with AV dependencies and a declared reboot policy; Home has respawn policy | Runtime continuity and watchdog ownership; keep RELEASE/procmgr/appctrl and stock Home intact while investigating |

Fxui has 42 direct dependencies in the selected ELF inventory, including its
Flash runtime and unrelated feature APIs. This is **not** a proposed minimal
link list for OpenCast. Similarly, libafopenapi's three `DT_NEEDED` entries do
not describe its entire framework contract: imported symbols and initialization
context can require providers beyond its own direct dependency list.

[ARM ABI research](arm-abi.md) reports base calling-convention attributes in its
selected sample. The reader and its descriptor-ownership correction are reviewed
and integrated; do not generalize the sample to every vendor library. The later
[Chromium check](chromium-abi.md) finds a VFP-declaring loader beside base-PCS clients,
not a demonstrated second coherent runtime. CPU feature permission, actual instructions, procedure
calling convention and physical CPU identification are separate questions.

## Current host lifecycle contract

The implemented [ownership model](native-lifecycle.md) uses synthetic adapters,
not guessed vendor declarations. Its successful acquisition sequence is:

```text
not-admitted -> admitted -> registered -> window-owned -> surface-owned -> ready
                                                               ready <-> focused
close -> dependency-aware cleanup -> return-pending -> returned OR failed
```

A failed return dispatch enters failed directly; a never-admitted close is local
and claims no restoration. This is an OpenCast contract, **not a recovered vendor
state machine**. Admission declares an independently verified execution route
and framework access; registration cannot establish those prerequisites. The
future window adapter must establish a service-bound lease, not merely accept a
numeric ID. Vendor readiness can precede rendering, so its events require an
explicit mapping to this model.

Cleanup makes at most one attempt per eligible owned resource, in reverse order.
Unconfirmed surface release retains window and registration; unconfirmed window
release retains registration. Only an independent restoration request continues;
a positive acknowledgment cannot clear failed cleanup or unresolved ownership.
Process exit alone proves neither Home/focus return nor AV continuity.

Ten host test groups and independent scenario review cover transition failures,
late/stale callbacks, timeouts, reentrancy, retained dependencies and idempotent
close. These are host evidence, not validation of an LG adapter. Keep native
capabilities disconnected until admission, signatures, ownership and policy are
evidenced; further model review must preserve these dependency rules.

## Historical ABI-shape object experiment

The installed **Apple clang 17.0.0 (clang-1700.6.3.2)** compiled our own small C
translation unit twice without additional dependencies. It has no entry point,
syscalls, vendor calls, libc headers or loader. Compile-time assertions check
32-bit pointers/integers/enums and 8-byte double alignment. One pure function
allows inspection of scalar argument lowering.

```sh
/usr/bin/clang --target=armv7a-none-linux-gnueabi -march=armv7-a \
  -marm -mfloat-abi=soft -ffreestanding -fno-builtin \
  -fno-stack-protector -nostdinc -std=c11 -O2 -Wall -Wextra -Werror \
  -c artifacts/native-entry-contract/abi_shape.c \
  -o artifacts/native-entry-contract/abi_shape.o
python3 -B -m tools.elf_inventory artifacts/native-entry-contract/abi_shape.o
```

**Observed:** 804-byte ELF32 little-endian ARM, `ET_REL`, EABI5, zero program
headers, no interpreter/dependencies. Both compilations produced SHA-256
`44fe94b72a3cfdd99ebb09026863c76e6e8ba30ba8df31ee8b2ef63a269db103`.
The six-instruction disassembly moves the double argument from core registers
`r2/r3` into return registers `r0/r1`; it contains no FP instructions or calls.
The source SHA-256 is
`33b2305f99092a8bc59b3454d905d7364e6df32a7b5d62e4a54591ade82a7c4a`.
`compile-report.json`, `object-metadata.json`, disassembly and artifact hashes
record the local result. No generated target object was executed or emulated.

This proves **cross-compilation to an object on the existing Mac**, not a usable
Linux linker/sysroot, a launchable program, vendor binary compatibility or
physical CPU support. `-mfloat-abi=soft` is a conservative option for this pure
object experiment, not the final renderer configuration. No performance claim
follows from it. No Linux cross-linker or target C runtime was installed here.

## Current bounded engineering priorities

1. **Legitimate entry:** follow [execution gates](native-execution-gates.md) and
   the [runtime artifact/issuer boundary](native-runtime-artifacts.md). No
   admitted owner-authored ELF or permitted starter has been demonstrated.
2. **Remaining registration/graphics contracts:** connection and callback
   identification, window consumer flow and conditional reservation are already
   traced. Any further slice must target active-policy provenance, ordering-state
   branches, service-bound ownership, actual EGL semantics or acknowledged
   teardown, rather than repeat those completed discoveries. Do not construct IPC.
3. **Binding readiness:** the host lifecycle and its current ARM object exist,
   but no real adapter or linked graphics client does. Audit argument/callback
   contracts and the chosen dependency closure before selecting compatible headers
   or linking vendor providers. The separate libc-free probe needs no sysroot;
   that result does not supply a renderer ABI or execution permission.

These tracks can progress locally, but downstream framework work cannot substitute
for legitimate initial execution. Keep RELEASE, procmgr, appctrl and stock Home
intact; real service continuity and return must eventually be observed separately.

Autostart remains a separate integration boundary. A coexisting shell becoming
usable does not justify replacing Home's declaration, intercepting Home globally,
selecting a different startup list or modifying boot files. Those actions require
their own compatibility, recovery and owner-authorized execution procedure.

## Historical experiment NATIVE-ENTRY-001

- **Objective:** identify a precise native admission prerequisite and test the
  Mac's ability to produce a conservative ARM object.
- **Hypothesis:** managed registration requires existing supervisor state, while
  object compilation can advance independently of runtime access.
- **Environment:** selected official update binaries, macOS ARM64, existing host
  compiler/LLVM and bounded static readers; no TV/LAN.
- **Procedure:** inspect registration/readiness handlers, shared dispatch and
  process lookup; correlate direct libraries/imports; compile our pure C source
  twice and inspect metadata/disassembly without executing it.
- **Expected result:** concrete admission checks and either a reproducible object
  or an explicit host toolchain limitation.
- **Observed result:** prerequisite table lookup and state dispatch; two identical
  ARM32 EABI5 objects; no linker/sysroot or native execution route established.
- **Conclusion:** proceed with admission/graphics contract recovery and a host
  ownership model while the reversible app measures physical UI behavior. The
  subsequent outer-receiver trace rules out treating this inner lookup as proof
  of mandatory prior supervisor launch.
- **Risks:** treating static names as public ABI, object generation as deployability,
  or app execution as startup replacement. None is claimed here.
- **Next step:** process-record creation is now traced; inspect SCF identity
  validation and registration state transitions offline.

## Later build and graphics evidence

The separate [minimal native probe](native-probe-build.md) now demonstrates a local linked ARM ELF using existing host tools, beyond the earlier object-only experiment. Its self-contained syscall experiment has no LG framework binding and has not run on a device. The [native window consumer trace](native-window-contract.md) establishes a framework identifier passed into EGL, while the later receiver trace identifies conditional reservation. Service-bound ownership, callback quiescence and actual return remain unresolved. Vendor process readiness occurs before rendering setup in the inspected paths, so the host model's surface/readiness order must be mapped explicitly rather than treated as a recovered protocol.

Receiver follow-up: [window allocation](native-window-allocation.md) distinguishes conditional bookkeeping reservation, reply success, numeric validity and surface creation. A GetWindowID-shaped call is not automatically read-only. No native adapter should borrow a stock ID/path or consider success a service-ownership proof.
