# Native process admission: two record-creation paths

Date: 2026-11-14. **CONFIRMED (local static)** applies to the selected official
04.28.17 binaries. No TV, IPC, privileged execution or target code execution.

The missing edge is now concrete: procmgr can create a process-table record
either after its own `vfork` or while receiving a method whose supplied process
key is not already present. Consequently the inner registration handler's
lookup does **not** prove that only supervisor-launched programs may register.
Whether an independently started application can reach and satisfy that path
remains **PENDING**: bus access policy, identity validation and registration
state transitions have not been established.

This refines [native-entry-contract.md](native-entry-contract.md); it does not
provide an execution mechanism or a packet recipe.

## Provenance and repeatability

Input: `firmware/lab/service-selected/open/bin/procmgr`, 435528 bytes,
SHA-256 `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5`.
The existing libafopenapi registration disassembly and its hash provenance are
in [app-lifecycle.md](app-lifecycle.md). No additional firmware extraction occurred.

Ignored `artifacts/native-admission/reproduce.py` pins the input and existing
host scratch reader hashes, and writes nine bounded function disassemblies plus
`evidence-hashes.json`. From the repository root:

```sh
python3 -B artifacts/native-admission/reproduce.py
```

Each host LLVM invocation uses the existing no-network/no-write sandbox, a
15-second CPU limit, 25-second timeout and 1 MiB output bound. Only explicitly
selected function ranges are inspected. PLT names are correlated with ELF
relocations, not inferred from nearby labels. The unnamed lookup helper is
exactly `[0x1a410, 0x1a478)`; objdump's enclosing symbol label is not its identity.

## Path A: launch creates a record indexed by child PID

The previously matched `AC_SEND_ExecuteProcess` method reaches
`PM_HNDL_ExecuteProcess` at `0x16310`. Within one new-process branch:

| Caller/call site | Callee or action | Static result |
| --- | --- | --- |
| `0x164d8`, `0x164fc` | `AF_UTIL_GetServiceName`, `PM_PROC_SearchServiceNamePT` | Extracts a service string and searches existing service records |
| `0x16514`, `0x16578` | `PM_LIST_GetCreateStatus`, `PM_LIST_GetUserAccount` | Consults startup state/account metadata; numeric states and complete policy remain unresolved |
| `0x16594`, `0x165ac` | `PM_LIST_AllocSvc`, `PM_PROC_CreateProcess` | Constructs a service description and invokes the creator |
| `CreateProcess 0x1aeec`, `0x1af0c` | `access`, `AF_UTIL_GetServiceName` | Checks the executable path with mode 1 and extracts service identity before creation |
| `0x1af18–0x1af2c` | `vfork`, result checks | Positive return goes to the parent branch; zero goes to the child; `-1` goes to failure |
| `0x1af54–0x1af5c` | `PM_PROC_InsertProcTable` | Passes the positive `vfork` return as first argument and extracted service string as second |
| `0x1af70`, `0x1af7c` | `PM_PROC_UpdatePTPathArgs`, output write | Stores path/arguments and returns the child PID to the caller |
| `0x165e0`, `0x165f0`, `0x16604` | `PM_PROC_UpdatePTAUID`, `PM_PROC_UpdateCreateProcApp`, `PM_PROC_UpdatePTOrderRelated` | Attaches AUID and additional lifecycle metadata after creation |

The child branch includes scheduling/environment setup, working-directory
selection and `execve` at `0x1b1c0`. Account-related branches also exist. This
does not establish a default privilege or an acceptable custom executable path.
No branch was run. The parent does not visibly branch on the insert return at
`0x1af60`; successful creation alone therefore must not be treated as proof of
successful record insertion or subsequent registration.

## Path B: the method receiver inserts a missing record

`PM_HNDL_MsgRecvHandler` obtains a connection through
`SCF_BUS_Connection_Request` (`0x17ea8`), receives messages through
`SCF_BUS_Message_Receive` (`0x17ee4`) and calls `PM_HNDL_MethodHandler`
(`0x17ecc`). Inside that handler:

1. `SCF_BUS_Message_Get_Any` at `0x17d48` decodes one integer and two strings
   using selectors `0x69`, `0x73`, `0x73`. The local integer slot is `sp+0x774`;
   string slots are `sp+0x770` and `sp+0x76c`.
2. `0x17d9c–0x17da4` uses the integer as the lookup key for
   `PM_PROC_SelectProcTable`.
3. A failed lookup branches to `0x17e48`. At `0x17e50`,
   `PM_PROC_InsertProcTable` receives that integer and the first string. The
   handler updates its stored return-message reference and rejoins dispatch.
4. `SCF_BUS_Message_Is_Method` at `0x17df8` selects a method-table entry. The
   indirect call at `0x17e3c` passes the decoded integer in `r2` and the first
   string in `r3` to the chosen handler. The third decoded value is passed on
   the stack.
5. For registration/readiness, the specific handler then reaches the inner
   lookup described in [native-entry-contract.md](native-entry-contract.md).

The registration client corroborates the identity meanings: libafopenapi calls
`HOA_UTIL_GetProcPID` at `0x1715c` and `HOA_UTIL_GetProcServiceName` at `0x17168`,
stores those outputs, and supplies their addresses to
`SCF_BUS_Message_Create_Method` at `0x17220`. Its third string is separately
prepared method data. These are library-supplied message fields in the inspected
client; they are not demonstrated kernel-authenticated sender credentials.

The receiver fallback means **a preexisting record is not a universal admission
requirement**. Conversely, it is not evidence of anonymous access: the selected
functions do not establish what SCF connection setup, the underlying bus or
later state callbacks allow. No claim of missing authentication or exploitable
access follows from this trace.

## What the table key actually represents

The insertion and lookup agree on the following partial layout. Offsets are
relative to a record beginning at `0x79ff0 + index * 0x758`, not C declarations:

| Offset | Observation | Confidence |
| --- | --- | --- |
| `+0x000` | Up to 256-byte service-name string; its first byte is used as the occupied/empty test | CONFIRMED static |
| `+0x100` | A second string initialized during insertion and later handled by signature-update logic | CONFIRMED string field; meaning beyond state/signature tracking unresolved |
| `+0x200` | Integer lookup key stored from insert argument 1; compared at `0x1a458–0x1a460` | CONFIRMED PID in managed-creation path; claimed PID in incoming client messages |
| `+0x230` | Eight-byte AUID written by `PM_PROC_UpdatePTAUID` at `0x1b724` | CONFIRMED separate identifier; not the lookup key |

The table has a count at `0x79fe8`; insertion and lookup scan at most 50 slots.
Insertion holds a mutex, rejects an already present key, checks capacity, fills
an empty slot and increments the count. `PM_PROC_SearchServiceNamePT` separately
compares service strings; that is different from PID lookup and includes
state-sensitive selection. This is only a partial layout for static reasoning,
not a usable struct ABI or a runtime memory address map.

## Next evidence, narrowly scoped

The highest-value remaining trace is now **transport admission and callback
state**, rather than finding another generic launcher:

- Identify the selected connection requested at `0x17ea8`, its policy/configuration
  and whether SCF checks sender credentials or transforms the supplied PID/name.
  Evaluate library code and shipped policy statically; do not connect to it.
- Resolve the registration state-table callback reached from operation selector
  32 and its initial record state. Determine whether the fallback record alone
  can complete registration, and how callback setup and service-name ownership
  are validated.
- Trace the first owned native window and readiness transition after registration.
  Preserve RELEASE and the original Home throughout the design.

These scopes complement a dependency/ABI graph: a symbol provider proves where
a function is defined; this report addresses why and in what state it is called.
Native execution access, safe exit/focus restoration and nonpersistent deployment
are still unproven. No executable, IPC request or device procedure is proposed.

## Experiment NATIVE-ADMISSION-001

- **Objective:** locate the creator and identity key of the record required by
  the inner registration dispatcher.
- **Hypothesis:** managed creation inserts the child process before registration;
  other insertion paths must be checked before declaring it mandatory.
- **Environment:** existing selected official firmware, bounded host disassembly,
  no TV/network or target execution.
- **Procedure:** inspect insert/create/execute functions, lookup, method receiver,
  method dispatcher and identity/AUID writers; cross-check the existing client.
- **Expected result:** creator-to-record edges and either identified key semantics
  or an explicit uncertainty.
- **Observed result:** both post-vfork and receiver-fallback insertions; PID-keyed
  lookup separate from service name and AUID; caller-supplied fields visible at
  the method layer, with lower-layer authentication unresolved.
- **Conclusion:** the earlier inner-handler finding is valid but insufficient
  to claim mandatory supervisor launch. The outer fallback changes the next
  research target to connection admission and registration state transitions.
- **Risks:** mistaking decoded identity fields for authenticated credentials, or
  static fallback logic for an accessible execution route. Neither is asserted.
- **Next step:** bound the SCF/policy and registration callback investigation.
