# Process account application contract

Revision 2, 2026-11-14. Task CLAUDE-004. Corrects five control-flow errors found by an independent
review (see the change list at the end); the underlying captures are unchanged. Level 0 only: local
static disassembly of one already-selected firmware binary. No firmware code was executed, loaded,
emulated or passed to `ldd`; no vendor library loaded; no credential file inspected; no television,
LAN, IPC, protected-package change or system change. No commit or push.

## Result

**CONFIRMED (static, single binary):** in the selected `procmgr`, the application account is handled
as a **name string** during admission and as two **numeric identity fields** at process creation.

- `PM_HNDL_ExecuteProcess` fills an account-name buffer with `PM_LIST_GetUserAccount`. On a
  successful lookup the buffer takes one source string; on a failed lookup a **fallback** string is
  formatted into the same buffer and execution **rejoins the same path** — both cases reach
  `PM_LIST_AllocSvc` and `PM_PROC_CreateProcess`. A failed lookup is not an error diversion.
- `PM_PROC_CreateProcess`, in the child after `vfork`, attempts credential changes **GID first, then UID**:
  `setgid(rec+0xc)` then `setuid(rec+0x8)`, each called only when its field is non-zero, then
  `umask(0)` and `execve`. Each field independently gates its own call, so a partial change is
  possible (a zero uid skips only `setuid`).
- Within these three function bodies no inline name→number conversion or directly identified supplementary-group setter appears; called helpers remain separate,
  and `procmgr`'s dynamic import table contains no `getpwnam`, `initgroups` or `setgroups`. This
  does **not** by itself prove the binary performs no name resolution anywhere — it does; the
  resolver is traced separately in `docs/process-account-provenance.md` (CLAUDE-005), which found
  the name resolved to `pw_uid`/`pw_gid` via `getpwent` in `PM_UTIL_GetID`.

So the account label (the `root`/`game`-style token from the service lists) is a string; the
values supplied to the setters are a pair of numbers in the process record; the number for a given label
comes from the passwd database (CLAUDE-005), and the device's effective identity is **PENDING** (no
credential file read). None of this is a route for an OpenCast program to obtain an identity.

## Input and method

Input: `firmware/lab/service-selected/open/bin/procmgr`, 435,528 bytes, SHA-256
`00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5` (the file frozen in
`docs/service-supervision.md`; re-hashed before capture). ELF32 little-endian ARM, EABI 5.

Disassembly used the reviewed wrapper `tools/arm_disassembly.py` with the trusted host
`llvm-objdump` (Apple LLVM 17.0.0, SHA-256 `bb7793802ccffe8e…`), one bounded range per call, no
whole-image disassembly, no execution. Function extents from
`artifacts/service-analysis/procmgr-symbols.txt`. Imports resolved through the PLT and the
`R_ARM_JUMP_SLOT` relocations (GOT plt entries from `0x75188`; stub = `0x10980 + 12·index`),
cross-checked against the `vfork` site.

Selected ranges (file offset = address − `0x8000`):

| Range | Bytes | Purpose |
| --- | --- | ---: |
| `PM_LIST_GetUserAccount` `0x3b970..0x3b9dc` | 108 | account name lookup |
| `PM_HNDL_ExecuteProcess` `0x16310..0x16a90` | 1,920 | admission; where the account is used |
| `PM_PROC_CreateProcess` `0x1ae94..0x1b334` | 1,184 | fork, credential application, exec |
| PLT + adjacent startup `0x1096c..0x11400` | 2,708 | import resolution only, not a study target |

The three study functions total 3,212 bytes, under the 8 KiB budget. The auxiliary range is **not
exclusively `.plt`**: it is the PLT followed by adjacent startup bytes (`_start` at `0x113b0`), used
only to resolve import stubs. Captures under ignored `artifacts/process-account-contract/`:
`getuseraccount.txt`, `executeprocess.txt`, `createprocess.txt`, `plt-import-resolution.json` (each
records the host-tool hash, options and disassembled-byte SHA-256) and `annotations.json`.

## Evidence

### 1. The account is a name string (`PM_LIST_GetUserAccount`, `0x3b970`)

- `0x3b988` calls a list-record helper; a null result takes the error path `0x3b9b4`, which logs via
  `cmd_mask_print` and returns `-1`.
- On success it `snprintf`s the record's `+0x4c` field into the caller's buffer with a buffer capacity of
  63 bytes including the NUL (`0x3b998 mov r1,#63`; `0x3b9a4`) and returns 0. The `+0x4c` field is the account **name**; the
  function produces a bounded C string, not a number.

### 2. Admission fills the account buffer on both the found and not-found paths (`PM_HNDL_ExecuteProcess`, `0x16310`)

- `0x16578` calls `PM_LIST_GetUserAccount` into buffer `r7`. `0x1657c cmp r0,#0` / `0x16580 bne 0x167c8`.
  - **Found** (`r0==0`): fall through to `0x16584`; `r7` retains the name copied by
    GetUserAccount from its lookup record's `+0x4c` pointer. At `0x1658c`, the separate value
    `[sp+0x1000+0xeb8]` is loaded into `r1` as AllocSvc argument 2, on both paths;
    `0x16590` passes `r7` in `r0` as argument 1. This slice does not assign argument 2 a purpose.
  - **Not found** (`r0!=0`, branch to `0x167c8`): `0x167cc-0x167d8` select the same `r7` buffer,
    buffer capacity 63, a `%s` format and a pointer from `[sp+0x1000+0xeb0]`; `0x167dc snprintf`; then
    `0x167e0 b 0x16584` — unconditionally back to the mainline.
- Both paths reach `PM_LIST_AllocSvc` (`0x16594`) and `PM_PROC_CreateProcess` (`0x165ac`). So the
  account lookup is **not** a precondition of creation; a failed lookup substitutes an alternate
  textual source and proceeds. The origin and authorization of that fallback source (`+0xeb0`) are
  not traced here and must not be assumed benign or privileged.

### 3. Credentials: GID then UID, numeric, in the child (`PM_PROC_CreateProcess`, `0x1ae94`)

- `0x1af18 vfork`. The child does `chdir` (`0x1b170`) then the credential block. The record pointer
  is `[sp,#0x10]` (`rec`), which is the first argument = the `PM_LIST_AllocSvc` result.
- Order (control flow): `0x1b188 ldr r0,[rec,#0xc]` (gid); if non-zero `0x1b190 bne 0x1b2c4`
  → **`setgid(rec+0xc)`** (`0x1b2c4`); then `0x1b2dc b 0x1b194`. Next `0x1b198 ldr r0,[rec,#8]` (uid);
  if non-zero `0x1b1a0 bne 0x1b2a4` → **`setuid(rec+0x8)`** (`0x1b2a4`); then `0x1b2c0 b 0x1b1a4`.
  The **GID setter is attempted before the UID setter**; neither success is assumed.
- Each call is skipped when its field is zero (`0x1b18c`, `0x1b19c`). The skips are independent: a
  zero uid skips only `setuid`, a zero gid skips only `setgid`. A zero-uid case also takes a helper
  detour (`0x1b180→0x1b2e0→0x1b184`) that calls the untraced helper at `0x1a478` and rejoins; its purpose is not inferred here.
- Return handling: `setuid`'s result is tested `cmp 0x1b2a8` / `bge 0x1b2ac`, and on a negative
  result `perror` (`0x1b2b4`) is called; `setgid` likewise (`cmp 0x1b2c8` / `bge 0x1b2cc` / `perror`
  `0x1b2d4`). Neither failure aborts the block. After each, `getuid`/`geteuid` (`0x1b2b8`,`0x1b2bc`)
  and `getgid` (`0x1b2d8`) are **called but their results are discarded** in this captured code
  (each is immediately overwritten or branched past; no consumer).
- `0x1b1a8 umask(0)`; `0x1b1c0 execve(path = pointer loaded from rec+0x50, argv = address rec+0xed4, envp)`. The argv pointer is
  `rec+3792+4 = rec+3796` decimal = **`rec+0xed4`** (`0x1b1b4 add #3792`; `0x1b1bc add #4`). On
  failure: `__errno_location`, `strerror`, a warning, `exit`.

### 4. The four distinct notions the task asked to separate

| Notion | In this binary | Label |
| --- | --- | --- |
| A name / string | account token at list-record `+0x4c`, copied by `PM_LIST_GetUserAccount`; a fallback string substitutes on lookup failure | CONFIRMED static |
| A numeric identity | process-record `+0x8` (uid), `+0xc` (gid), arguments to `setuid`/`setgid` | CONFIRMED static |
| A checked syscall | `setgid` then `setuid`; each return tested `bge`, `perror` on negative, no abort | CONFIRMED static |
| A live effective identity | `getuid`/`geteuid`/`getgid` are called but their results are discarded; device identity unobserved | PENDING (static only) |

## Unresolved contracts (narrowed)

- **Name → number** is not done inside these three functions, and the import table lists no
  `getpwnam`/`initgroups`/`setgroups`. That is all this slice establishes. It does **not** show the
  binary performs no name resolution: `docs/process-account-provenance.md` (CLAUDE-005) traces the
  resolution to `PM_UTIL_GetID` via `getpwent`/`strncmp` on the `PM_LIST_AllocSvc` path.
- **The fallback account source** (`+0xeb0`) used on lookup failure is untraced; what it contains and
  whether it changes the resulting identity are PENDING.
- **The device's effective identity** remains unobserved. A passwd-database mapping is not
  live process state: parent credentials, each setter's outcome and executable/runtime transitions
  also matter. No credential database was read.
- A zero field skips only its own credential call; this is a property of the vendor records, not a
  permission for any OpenCast program, and no admission or privilege is established here.

## Review corrections (including root integration)

1. **Admission branch corrected.** Revision 1 said a failed lookup "diverts away from the normal
   path" and that the account name is "a precondition of creation." Verified wrong at `0x16580→
   0x167c8→(snprintf fallback)→0x167e0 b 0x16584`: the failure path fills a fallback name and rejoins
   `AllocSvc`/`CreateProcess`.
2. **argv offset corrected** from `rec+0x3796` to `rec+0xed4` (decimal 3796; `add #3792` then `add #4`).
3. **Identity reads corrected** from "read for logging" to "called but results discarded"
   (`getuid`/`geteuid`/`getgid`). The `perror` after a negative `setuid`/`setgid` is a genuine use.
4. **Credential order corrected** to **GID then UID** (revision 1 and delivery message 012 implied
   UID first). The `setuid` signed branch is at `0x1b2ac` (`0x1b2a8` is the `cmp`).
5. **Negative claims narrowed** to what the demonstrated slice and the import table establish; the
   "no name resolution" implication is withdrawn and pointed at CLAUDE-005.
6. The auxiliary disassembly range is described as PLT plus adjacent startup bytes, not `.plt` alone.

Root integration additionally separates the lookup-name buffer from AllocSvc argument 2, describes
setter attempts rather than observed identity changes, distinguishes loaded pathname pointers from
argv addresses, and narrows direct-call/lookup claims.

Captures (`*.txt`, `plt-import-resolution.json`) are unchanged; only this report and the derived
`annotations.json` were corrected.

## Experiment ACCOUNT-001 (revised)

- **Objective:** determine how the account label in an admitted application record is consumed before
  process creation.
- **Hypothesis:** account metadata reaches numeric credential setters through a separate record.
- **Environment/procedure:** selected hashed procmgr on the Mac; bounded disassembly, independent branch/argument and PLT verification; no target execution.
- **Expected:** an explicit account buffer, checked branches and credential calls, with unresolved dependencies named.
- **Observed result (corrected):** the account name is looked up and, on failure, a fallback name is
  substituted; both paths reach creation. In the `vfork` child, `setgid(rec+0xc)` then `setuid(rec+0x8)`
  are attempted when non-zero (returns checked, `perror` on failure, no abort); `getuid`/`geteuid`/
  `getgid` results are discarded; `umask(0)` then `execve(pathname pointer loaded from rec+0x50, argv address rec+0xed4, envp)`. No inline name→number
  conversion in these bodies; `procmgr` imports no `getpwnam`/`initgroups`/`setgroups`.
- **Conclusion:** the account is a name at admission and a pair of numbers at creation; the join is
  outside this slice (CLAUDE-005). No privilege, admission or launch route follows.
- **Risks:** mistaking a branch for rejection, a field pointer for its value, a setter attempt for successful identity change, or import absence for global behavior.
- **Next step:** the credential-field writer trace, delivered as CLAUDE-005.
