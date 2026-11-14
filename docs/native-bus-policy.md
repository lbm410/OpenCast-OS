# SCF connection policy and registration state

Date: 2026-11-14. **CONFIRMED (local static)** unless marked otherwise. This
bounded follow-up to [native-admission.md](native-admission.md) identifies the
transport wrapper and the callback selected by registration operation 32. It
does not establish a native execution route, an authenticated client identity,
or permission to contact the TV's internal bus.

## Inputs and extraction

Six explicitly selected regular files were copied read-only through the reviewed
SquashFS list/cat helper. No scripts, libraries or vendor programs were run.
The package hashes match `artifacts/firmware-lab/extraction-verified.json`:

- `open.pak`: `d89a800371ea6d2681813c974e4975be92730d10cccd77788945a88a4be33a48`.
- `lgli.pak`: `bf45626c7b1ead645a8a47d4f78161abc48bbef080ef1d8f29244b6316f37749`.

Both remain mode `0444`. The selected paths, relative to
`firmware/lab/scf-selected/`, are:

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `lgli/libscf.so.0.0.0` | 24704 | `4d5bc2e85b5413f11cf001bfb27e2a1ebfc7366237c3c1ff06e3f61b48f526d7` |
| `open/bin/dbus-1/session.conf` | 2848 | `46eb629c84c17479d968bc2881ee1f96210ba4dea486e25bc601e49c6af6bc40` |
| `open/bin/dbus-1/system.conf` | 2609 | `9b255827ea4c6dee7f44c6f938ff975c2b0b5e863cfc62d23e8e33f382ba8274` |
| `open/bin/dbus-init.sh` | 865 | `2857f8e63d0c168491323745ea07646218d2e671b3bf1581ae6c4b5bbad3314e` |
| `open/bin/dbus-start.sh` | 220 | `367b8c2094eb6c7966519ae39cc077b47d4fd37e65197ea9e0324279ec354a57` |
| `open/bin/dbus-wait.sh` | 270 | `c7b9c3fb5e1ff56ef034b84175fa12a4306ba250b1fcd456d2a08eedc406b965` |

Selection manifests, source hashes, ELF metadata and disassembly are under
ignored `artifacts/native-bus-policy/`. The first extraction attempt stopped
before copying because the parent output directory was absent; after creating
that directory, both selections completed. No firmware input changed.

`python3 -B artifacts/native-bus-policy/reproduce-disassembly.py` reproduces
three bounded function disassemblies and the state-table prefix after checking
input/helper hashes. Each LLVM child has a no-network/no-write sandbox,
15-second CPU limit, 25-second timeout and 1 MiB output limit. The script was
rerun successfully; it executes only the host analysis tools.

Reproduction uses fresh selection destinations; the helper refuses overwrites:

```sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/open.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/scf-selected/open \
  --select bin/dbus-1/session.conf --select bin/dbus-1/system.conf \
  --select bin/dbus-init.sh --select bin/dbus-start.sh --select bin/dbus-wait.sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/lgli.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/scf-selected/lgli --select libscf.so.0.0.0
```

## SCF is a D-Bus wrapper here

`SCF_BUS_Connection_Request` at `0x28f0` forwards its first argument to
`dbus_bus_get_private` at `0x2918`. For a non-null connection it disables
exit-on-disconnect at `0x292c`, calls `dbus_bus_request_name` at `0x2940` with
the supplied name and flag value 2, and compares the result to 1 before returning
the connection. Failure paths check/free an error and return null. These are
actual imported calls resolved through PLT relocations, not D-Bus-like strings.
The flag and return constants are recorded numerically; this slice does not
provide a compatible header set or instructions to request a name.

Procmgr's receiver requests a connection with selector 0 and service name
`lg.service.special.processmanager` at `0x17ea8`; the name is a literal at
`0x3de88`. The registration client also opens selector-0 connections at
`0x16fbc` and `0x17030`, and a selector-1 connection at `0x17068`. This report
does not conflate them: exact selection/address resolution in the shipped
libdbus, including environment overrides, still needs verification.

`SCF_BUS_Message_Get_Any` at `0x3084` calls
`dbus_message_get_args_valist` at `0x30d8`. Therefore the PID/service fields
decoded by the process-manager method handler are message arguments at this
layer, not values obtained by querying peer credentials. The selected SCF
library also exports a separate `SCF_BUS_Message_Get_Sender` wrapper. No sender
credential comparison was found in the **specific connection, argument parser,
method dispatcher and registration callback inspected here**. That bounded
observation does not prove absence of checks in libdbus, daemon policy, filters,
other services or an active configuration.

The SCF ELF is ARM32 little-endian EABI5. Its direct `DT_NEEDED` list contains
only `libgcc_s.so.1` and `libc.so.6`, despite importing D-Bus and diagnostic
symbols. A native client cannot assume that linking SCF alone supplies all
providers. Resolve the process-wide dependency graph separately; procmgr itself
declares D-Bus among its dependencies.

## Shipped configuration: local transport, unresolved active policy

The selected session configuration declares a Unix socket under `/tmp`
(`session.conf:15`). Its default policy allows users, destinations, reception
and name ownership broadly (`:19–27`). It includes `session.d`, an optional
`session-local.conf` and conditional SELinux contexts (`:32–38`). It does not
explicitly select an authentication mechanism; this is **not** evidence that
authentication is disabled.

The selected system configuration explicitly declares `EXTERNAL` authentication
(`system.conf:35–36`) and a local Unix socket (`:42`). Its default policy has
broad allow rules (`:44–52`) plus a specific activation-environment denial
(`:57–59`), followed by system/local/SELinux includes (`:64–70`). These are
on-disk policy declarations, not a live authorization result.

The `open.pak` inventory contains only zero-length `dummy` files in the shipped
`session.d` and `system.d` directories. No corresponding local override file
appears in that image. Other mounts, generated configuration, patches and the
actual daemon arguments remain unobserved; do not infer a complete active
policy from one update image.

`dbus-init.sh` contains startup commands for both a system daemon and a session
launcher, then writes session address/PID files under `/var/run`.
`dbus-start.sh` reads those files into `DBUS_SESSION_BUS_ADDRESS` and
`DBUS_SESSION_BUS_PID`. This supports investigating an inherited session-bus
environment, but the active script chain and socket permissions are not proven
by these files. `dbus-wait.sh` additionally launches example programs; it is not
a harmless wait utility. None of these scripts was executed or sourced.

## Registration operation 32 has an identified state callback

The shared dispatcher table at virtual address `0x754fc` begins with these
three 12-byte entries, independently read from the selected procmgr:

| Record state | Operation | Callback |
| ---: | ---: | --- |
| `0x10` | `0x20` (32) | `PM_HNDL_ChangeFromInitToLoad`, `0x172c8` |
| `0x20` | `0x41` (65) | `PM_HNDL_ChangeFromLoadToBG`, `0x14d6c` |
| `0x41` | `0x42` (66) | `PM_HNDL_ChangeFromBGToFG`, `0x147c8` |

Insertion initializes state `0x10`; the registration handler supplies operation
`0x20`. These match the first table row. Readiness supplies operation `0x41`,
so registration and readiness are distinct transitions. State names follow
defined symbol names; they are not a complete public state enum.

Bounded inspection of `PM_HNDL_ChangeFromInitToLoad` establishes:

- It requires method data and decodes additional fields via
  `SCF_UTIL_Get_DataArgs` at `0x17354`.
- It queries service creation status at `0x173ac`; one branch updates that
  status and calls `AF_WaitSem` with numeric argument 1000 at `0x173e0`.
  The unit/timeout contract of that private helper is not established here.
- It consults an ordering-process relation through `PM_PROC_GetOrderer`
  (`0x1740c`), with different branches for success, `-3`, and other errors.
- A traced branch updates path/argument metadata (`0x17588`) and writes process
  state `0x20` (`0x1758c–0x17594`). Other branches handle process relationships,
  priorities, notifications and focus. Calls include `PM_GX_RequestFocus`
  (`0x175f4`, `0x178ac`) and `PM_SEND_SetFocusNoti`.

Thus registration is not merely adding a passive record. Its successful path
can affect scheduling/focus-related state; complete coexistence and exit
behavior still need analysis. This report does not claim every new record
passes the callback or every branch requests focus.

The client references environment labels `PM_EXECPATH`, `PM_EXECARGS` and
`PM_EXECPID`, resolved from its PIC literal pool. Later checks require non-null
path/argument values before message construction, but earlier branches parse
arguments and call `setenv` themselves. These labels are **context metadata**,
not demonstrated credentials or proof of exclusive supervisor launch. No
environment values or complete message recipe are published here.

## Narrow next step

Two missing contracts now have specific targets:

1. Resolve the selected libdbus implementation's selector/address handling and
   daemon configuration provenance, then distinguish transport-authenticated
   sender identity from the PID claimed in application payloads. Do not change
   the policy, start a daemon or connect a client.
2. Trace `PM_PROC_GetOrderer` and the `-3` registration branch, then the first
   owned window/readiness transition. Determine whether a legitimately started
   independent client can complete setup without a launch-order record and how
   it relinquishes focus. Keep this separate from automatic startup replacement.

The result is sufficient to scope the next static experiment. It is insufficient
to authorize or construct a runtime call, stop vendor services, or claim a
nonpersistent native deployment route.

## Experiment NATIVE-BUS-001

- **Objective:** identify the transport and registration callback behind the
  process-table admission paths.
- **Hypothesis:** SCF wraps a local message bus and registration advances a
  stateful lifecycle rather than granting execution itself.
- **Environment:** official selected files, existing bounded host extraction and
  disassembly tools, macOS; no TV/network or target execution.
- **Procedure:** select six regular files; inspect SCF connection/argument
  functions, shipped policy/scripts, state-table entries and one registration
  callback; correlate existing client environment references.
- **Expected result:** concrete transport/configuration/state evidence with
  explicit authorization and runtime gaps.
- **Observed result:** D-Bus calls, local-socket policy templates, decoded payload
  identity fields, registration state `0x10→0x20` on one branch, and additional
  ordering/focus/priority behavior. Six files copied read-only after correcting
  the missing parent directory; hashes retained.
- **Conclusion:** connection policy and application lifecycle are now grounded in
  selected code. Live policy, identity enforcement and independent native entry
  remain unproven.
- **Risks:** extrapolating permissive templates to active policy or successful
  registration to safe coexistence. No such extrapolation or invocation occurred.
- **Next step:** static selector/policy provenance and ordering-process analysis.
