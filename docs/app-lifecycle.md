# Application lifecycle and coexistence contract

Date: 2026-11-14. **CONFIRMED (local static)** describes the inspected official
04.28.17 firmware, not a live service or accessible execution interface.

There is a concrete managed-application boundary: appctrl resolves application
metadata and sends execution, focus and exit requests to procmgr; fxui registers
with this framework and reports readiness. Home is one such separately declared
service. This supports investigating coexistence with the original TV services.
It does not provide initial code-execution access or a verified native launch
mechanism for OpenCast.

## Inputs and reproducibility

The bounded SquashFS helper copied three selected regular files into the ignored
`firmware/lab/app-lifecycle/` directory. No target code, library, script or IPC
was executed. Existing procmgr and Home manifest selections were read without
modification. Original package hashes and read-only modes were rechecked.

| Selected file | Bytes | SHA-256 |
| --- | ---: | --- |
| `open/bin/appctrl` | 277044 | `630bfe0e7ab3c93ee7650405166b7ad24124807eb9b4243389b021068c704c97` |
| `open/bin/fxui` | 1878212 | `98e05ccd63771c2609ec6af348cbbb875a8b4c7b1d176224c3abc80095dc8723` |
| `lgli/libafopenapi.so.0.0.0` | 221880 | `bbbfaa4c51c0fdb58f258dcb76d399929913c6ac6f11ba0743f227d6d0f50350` |

The Home manifest at
`firmware/lab/base-selected/addon/contents/system/home/manifest.xml` is 1422 bytes,
SHA-256 `399cc98603ec84aec701f5dd14a5a24c8478dd4e8ca05468e324c0270204451d`.
Procmgr and service-list hashes are in
[service-supervision.md](service-supervision.md).

Extraction commands, requiring fresh output directories:

```sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/open.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/app-lifecycle/open \
  --select bin/appctrl --select bin/fxui
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/lgli.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/app-lifecycle/lgli \
  --select libafopenapi.so.0.0.0
python3 -B -m tools.elf_inventory --tree firmware/lab/app-lifecycle
```

Ignored `artifacts/app-lifecycle/` contains selection manifests, ELF metadata,
dynamic-symbol lists, annotated bounded disassembly, method-table references
and `inspect_static.py`, the host-only scratch reader used to correlate ELF32
dynamic relocations with ARM PLT stubs. Its disassembly invokes Xcode's
`llvm-objdump` with explicit function address bounds under a sandbox denying
network and path writes, a 15-second CPU bound and a 25-second timeout. Its PLT
resolver reproduced the independently verified procmgr `system` GOT mapping.
These local notes are research artifacts, not a supported firmware execution
toolchain. No device or network operation occurred.

## Home identity and observed startup code

The normal list's Home command supplies `--service lg.service.normal.home2`
and `--auid 11174` to fxui. The manifest identifies `app_id` 70004, alias `home`,
file `Home.swf`, app type 11 and capability resolution `1280,720`. These are
metadata values; the memory-size field is not a measured allocation.

This identifier match is now supported by code, not only arithmetic:

- `fxui` main detects `--auid` using the literal at virtual address `0x10c838`,
  loaded through literal-pool slot `0x3813c`.
- The corresponding branch at `0x37798` sets argument `r2` to 16 and calls
  `strtoull` at `0x377a4`; its result goes to `setRunArgsAUID` at `0x377a8`.
- Consequently this fxui argument `11174` is parsed in base 16 and equals the
  manifest's decimal 70004. This does not establish the representation of every
  AUID field in other APIs or files.

Fxui main calls its `registerService` wrapper at `0x37944`, obtains a window ID,
and reaches a `setReady` call at `0x379dc`. The wrappers call
`HOA_PROC_RegisterService` (`0x3f3e0`) and `HOA_PROC_SetReady` (`0x3f4a8`). Other
branches perform player/focus setup and readiness notifications. A later exit
branch contains `HOA_APP_ExitAppEx` (`0x37dc8`),
`HOA_PROC_UnregisterService` (`0x37dcc`), and libc `exit` (`0x37dd4`). These are
reachable-code relationships; the exact triggering events and return destination
have not been simulated or observed.

Appctrl main similarly initializes handlers/lists, calls
`HOA_PROC_RegisterService` at `0x13f10`, checks/loads application lists and calls
`HOA_PROC_SetReady` at `0x13f44`. Framework registration is therefore part of
the supplied process lifecycle, not an optional detail inferred from a name.

In `libafopenapi`, `HOA_PROC_RegisterService` at `0x16b94` calls command-line
parsing, SCF bus initialization/connection requests, process-info storage,
callback setup and a register-service message/reply path. Its full struct layout,
environment prerequisites, bus policy and caller authentication remain
**PENDING**. `HOA_PROC_SetReady` at `0x186ec` constructs and sends a message;
its wrapper uses `SCF_BUS_Message_Send`, rather than the synchronous reply
operation used by the launch wrapper.

## Launch, focus and exit routing

`HOA_APP_ExecuteApp` in `libafopenapi` at `0x109ac` builds a method message with
these string arguments, resolved from its PIC base and literal pool:

| Argument | String virtual address | Value |
| --- | --- | --- |
| Destination | `0x2dd6c` | `lg.service.special.appctrl` |
| Path | `0x2caec` | `/hoa/app` |
| Interface | `0x2c758` | `lg.if.service` |
| Method | `0x2d6ec` | `HOA_APP_ExecuteApp` |

This is a private service protocol. No transmitted packet, callable C prototype,
authorization bypass, or unrestricted D-Bus endpoint follows from these strings.

Appctrl's table at file offset `0x41440` pairs the `HOA_APP_ExecuteApp` string
pointer with `APPCTRL_ExecuteAppHandler` (`0x1f6a0`). The handler calls
`APPCTRL_ExecuteApp` at `0x1f800`; that small wrapper branches to
`APPCTRL_ExecuteAppEx` (`0x161fc`). The latter queries
`AM_CMN_APPLIST_GetAppInfoEx` at `0x16228`, retries after loading the app list,
and only reaches `_APPCTRL_ExecuteAppByAppinfoEx` after a successful lookup.
The failed lookup path calls `APPCTRL_BackToPrevAppByAM` and returns an error.

Further calls include `_APPCTRL_CheckExecuteCondition` and
`_APPCTRL_ExecuteProcess`; the latter has calls to `AC_SEND_ExecuteProcess`.
Thus the observed managed launch route depends on application metadata and state.
It is not evidence that supplying a pathname launches arbitrary software.

Appctrl sends execution/focus/exit methods to
`lg.service.special.processmanager`, path `/hoa/proc`, interface `lg.if.service`.
The procmgr method table contains these exact pairs:

| Method | Table file offset | Handler virtual address |
| --- | --- | --- |
| `AC_SEND_ExecuteProcess` | `0x65838` | `PM_HNDL_ExecuteProcess`, `0x16310` |
| `AC_SEND_RequestFocus` | `0x65828` | `PM_HNDL_RequestFocus`, `0x145d4` |
| `AC_SEND_ExitApp` | `0x65858` | `PM_HNDL_ExitApp`, `0x14518` |
| `HOA_PROC_RegisterService` | `0x65588` | `PM_HNDL_RegisterService`, `0x14790` |
| `HOA_PROC_SetReady` | `0x656b8` | `PM_HNDL_SetReady`, `0x146c8` |

The appctrl table also maps `HOA_APP_ExitApp` at file offset `0x414a4` to
`APPCTRL_ExitAppHandler` (`0x1e1ac`), which calls `APPCTRL_ExitApp`. That function
contains multiple state-dependent paths through live-app tracking,
`AC_SEND_ExitApp`, focus restoration, and abnormal-exit DTV notification.
`APPCTRL_RequestFocus` calls `AC_SEND_RequestFocus` and maintains focused-app
state. These paths argue for normal lifecycle handling instead of process kills;
they do not prove every exit returns to Home or preserves every AV state.

## Input-dispatch wrapper matched to implementation

The earlier wrapper in [native-interfaces.md](native-interfaces.md) now has a
concrete receiving match. Procmgr's table at **file offset `0x66008`** pairs the
method-string pointer `0x45098` (`HOA_GX_SetWindowInputDispatchType`) with
`PM_HNDL_SetWindowInputDispatchType` (`0x26394`).

The handler reads typed message arguments, calls
`PM_GX_SetWindowInputDispathType` at `0x26430`, and sends a success/failure reply.
The callee at `0x2cf14` checks its first argument against 78, reads and updates a
field in a per-window indexed structure, and calls
`PM_INPUTMGR_SetInputDispatchType` at `0x2cf9c`. That function at `0x1fe2c`
updates an input-manager state field and has a five-case jump table reaching
cursor-status, cursor-support and Magic Remote standby operations.

The directly linked `libafopenapi` also provides this wrapper at `0x2a3dc`;
its early checks compare the two arguments against 78 and 4. Those are static
unsigned range checks, **not verified enum meanings or safe settings**.
The input-manager path means this API cannot be treated as a harmless DOM
keyboard switch. Lifetime, focus ownership, concurrency, error recovery and
restoration of the prior input state remain unresolved. Nothing was called.

## Permissible runtime entry and coexistence requirements

**CONFIRMED:** these private APIs describe how already running, integrated
vendor applications cooperate. They do not expose an entry point from the Mac
or establish that an unsigned native OpenCast binary can run.

The concrete low-risk entry remains an official NetCast application deployment
if the package/account/device prerequisites in
[app-deployment.md](app-deployment.md) can be satisfied. The existing browser
probe remains useful for web capability measurement but does not grant native
framework access. A native surface is **PENDING** an independently established,
authorized, reversible execution route; no privileged route is implied here.

A candidate coexistence contract now has specific requirements to verify:

1. The supported loader admits the application and gives it a distinct identity;
   no reuse of the Home AUID or alteration of vendor manifests/startup lists.
2. Registration and readiness complete with verified ABI, callbacks and service
   policy; RELEASE, procmgr, appctrl and essential services remain running.
3. The application receives its own window/surface and focus through the managed
   lifecycle. Input dispatch remains unchanged until its contract and rollback
   are independently understood.
4. A normal exit releases that application's resources and restores the previous
   application/input state. The owner confirms Smart Home return, AV continuity,
   repeat launch and absence of service restarts in one consolidated test.

These are validation criteria, not implemented behavior. Automatic startup,
Home-key interception, replacement of menu services and recovery still require
separate evidence. The next local work should determine the available official
loader route and inspect process-manager admission/registration policy, rather
than writing an unverified caller for the discovered IPC methods.

## Experiment record

- **Objective:** locate a managed launch/focus/exit boundary and connect the
  input-dispatch wrapper to its receiver.
- **Hypothesis:** appctrl/procmgr can host separate UI applications while RELEASE
  continues essential TV work.
- **Environment:** static official-update files on macOS ARM64; no TV/network.
- **Procedure:** selectively copy appctrl, fxui and libafopenapi; hash/inventory
  them; inspect dynamic symbols, bounded function disassembly, method-table
  pointers, relocations and the existing Home manifest.
- **Expected result:** corroborated lifecycle edges and unresolved entry/access
  conditions, without target execution.
- **Observed result:** base-16 Home AUID parsing; registration/readiness calls;
  metadata-dependent managed launch; focus/exit method routing; input wrapper
  to handler to input-manager chain.
- **Conclusion:** a concrete coexistence boundary exists in the vendor design;
  admission of custom code and a reversible native runtime remain PENDING.
- **Risks:** confusing static tables with active bus endpoints, documentation
  with a usable ABI, or input-manager operations with local key handling.
- **Next step:** establish legitimate loader availability and admission contract;
  retain the original services and Home as the return path.
