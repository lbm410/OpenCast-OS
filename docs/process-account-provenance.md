# Process credential field provenance

Revision 2, 2026-11-14. Task CLAUDE-005, continuing CLAUDE-004. Corrects the issues found by an
independent review (change list at the end); the raw captures are unchanged. Level 0 only: local
static disassembly of one already-selected firmware binary. No firmware code was executed, loaded,
emulated or passed to `ldd`; no vendor library loaded; no credential file inspected; no television,
LAN, IPC, protected-package change or system change. No commit or push.

## Result

**CONFIRMED (static, single binary):** the numeric uid/gid fields that `PM_PROC_CreateProcess`
passes to credential setters (process record `+0x8` uid, `+0xc` gid, from CLAUDE-004) are written by **`PM_UTIL_GetID`**,
called from **`PM_LIST_AllocSvc`** with the account **name**. `PM_UTIL_GetID` enumerates the passwd
database with `getpwent()` and compares with
`strncmp(requested_name, entry_name, strlen(requested_name))` — a **prefix match on the requested
name**. The first enumerated entry whose name begins with the requested string supplies `pw_uid` →
record `+0x8` and `pw_gid` → record `+0xc`; on no match `PM_UTIL_GetID` returns `-1` and **does not
write** those fields.

This identifies the writer left PENDING by CLAUDE-004 and fixes CLAUDE-004's open question about
name resolution: resolution is present, via `getpwent`/`strncmp` (not `getpwnam`, which `procmgr`
does not import). The device's actual passwd contents and effective process identity are **PENDING** (no credential file read); the passwd enumeration API does not establish a
particular backing file or its numbers.

## Input and method

Input: `firmware/lab/service-selected/open/bin/procmgr`, 435,528 bytes, SHA-256
`00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5` (same binary as CLAUDE-004 and
`docs/service-supervision.md`; re-hashed before capture). Reviewed wrapper `tools/arm_disassembly.py`
with host `llvm-objdump` (Apple LLVM 17.0.0, `bb7793802ccffe8e…`), one bounded range per call, no
whole-image disassembly, no execution. Import resolution reused the CLAUDE-004 method (PLT index →
`R_ARM_JUMP_SLOT`), cross-checked against known sites.

Captured ranges (file offset = address − `0x8000`):

| Range captured | Bytes | Role |
| --- | --- | ---: |
| `PM_LIST_AllocSvc` `0x3b410..0x3b6cc` | 700 | builds the svc record; calls the resolver |
| `0x1cd48..0x1ce70` (contains `PM_UTIL_GetID` 104 B + adjacent `PM_UTIL_SetOOMADJ`) | 296 | name → uid/gid resolver (subject is the first 104 B) |
| `PM_PROC_InsertProcTable` `0x1a7f0..0x1a9a4` | 436 | checked: not a credential writer |
| `PM_PROC_UpdateCreateProcApp` `0x1b7f4..0x1b878` | 132 | checked: not a credential writer |

**Total captured: 1,564 bytes** (the `PM_UTIL_GetID` subject is 104 of the 296-byte capture, which
incidentally shows the following function), under the 8 KiB budget. Captures under ignored
`artifacts/process-account-provenance/`: `allocsvc.txt`, `getid.txt`, `insertproctable.txt`,
`updatecreateprocapp.txt` (each records the host-tool hash, options and disassembled-byte SHA-256)
and `annotations.json`.

## Evidence

### 1. `PM_LIST_AllocSvc` fills the credential fields through the resolver (`0x3b410`)

- `0x3b42c` `calloc(1, 0x10d8)` → the svc record (returned at `0x3b59c`). Because it is `calloc`,
  unwritten fields, including `+0x8`/`+0xc`, are zero.
- `0x3b440`–`0x3b450`: `add r2,r0,#12`; `add r1,r0,#8`; `mov r0,r6` (arg1); `bl PM_UTIL_GetID`.
  So `PM_UTIL_GetID(arg1, &record[0x8], &record[0xc])`. Arg1 is the account-name buffer that
  `PM_LIST_GetUserAccount` filled in `PM_HNDL_ExecuteProcess` (and which, on a failed lookup, holds
  the fallback string — CLAUDE-004 rev 2). The caller's name buffer is distinct from the passwd
  **table** that `getpwent` walks.
- `PM_UTIL_GetID`'s return value is **ignored** by `AllocSvc` (`0x3b450` call, `0x3b454` overwrites
  `r0`). So a no-match (return −1, fields unwritten) leaves the calloc'd zeros, and
  if subsequent allocation/launch prerequisites reach the credential block,
  `PM_PROC_CreateProcess` skips both `setgid` and `setuid` there.
- No other store in `AllocSvc` targets record `+0x8`/`+0xc` (later stores are to `+0x24`, `+0x30`,
  `+0x34`, `+0x38`, `+0x48`, `+0x50`, `+0xed4`, `+0xed8`; `0x3b4d8 add #3792` is decimal, `0xed0`,
  and the argv region begins at record `+0xed4`).

### 2. `PM_UTIL_GetID` resolves by prefix over the passwd enumeration (`0x1cd48`)

- `r4` = requested name, `r7` = `&uid-out`, `r6` = `&gid-out`.
- Loop: `0x1cd78 getpwent()` → `r5` = `struct passwd*`; `0x1cd7c` test; `0x1cd80 mov r0,r4`
  (requested name); `0x1cd84 bne 0x1cd5c` while entries remain. Null → `0x1cd88 endpwent()` and
  return `-1` (`0x1cd8c mvn r0,#0`), leaving the output fields unwritten.
- Per entry: `0x1cd5c strlen(r0 = r4 = requested name)` → length; `0x1cd60 ldr r1,[r5]` (entry name
  `pw_name`); `0x1cd64 mov r2,r0` (length); `0x1cd68 mov r0,r4` (requested name);
  `0x1cd6c strncmp(requested_name, entry_name, strlen(requested_name))`. A non-zero result continues.
- On a match (`r8==0`, `0x1cd74 beq 0x1cd94`): `*uid-out = pw->pw_uid` (`[r5,#0x8]`→`[r7]`),
  `*gid-out = pw->pw_gid` (`[r5,#0xc]`→`[r6]`) — standard glibc `struct passwd` offsets (`pw_name` 0,
  `pw_uid` 8, `pw_gid` 12); then `endpwent` and return `0`.

CONFIRMED: the comparison length is `strlen(requested_name)`, so this is a **requested-name prefix
match**, not exact equality and not bounded by the entry-name length. The **first** enumerated entry
whose name starts with the requested string wins. An empty requested name (prefix of length 0) would
match the first enumerated entry; whether an empty name can reach here is PENDING (it would require
the account buffer, including the CLAUDE-004 fallback, to be empty).

No explicit null-name check or `setpwent` call occurs in this resolver. The first matching entry
means the first returned by the active enumeration state; a fresh reset is not established. Empty
or null names are not demonstrated reachable inputs, and null must not be treated as a safe
missing-name case.

### 3. The two other candidates are not credential writers

- `PM_PROC_UpdateCreateProcApp` (`0x1b7f4`) writes the separate global table field `+0x75c`,
  not the calloc'd service record.
- `PM_PROC_InsertProcTable` (`0x1a7f0`) uses a separate global table at `0x79fe8` with
  stride `0x758`. The caller's `sp+288` is the name buffer passed as its second argument,
  not the entry's storage. It writes table fields (`+0x208`, `+0x220`, `+0x740`, `+0x744`, `+0x748`, `+0x750`, `+0x758`,
  `+0x75c`); none is the svc record `+0x8`/`+0xc`.

## The chain, joined

| Step | Evidence | Label |
| --- | --- | --- |
| List-account **string** | list record `+0x4c`, copied by `PM_LIST_GetUserAccount`; fallback on lookup failure (CLAUDE-004 rev 2) | CONFIRMED static |
| Passed to the allocator | `PM_HNDL_ExecuteProcess` passes the name buffer as `AllocSvc` arg1 (`0x16590`/`0x16594`) | CONFIRMED static |
| **Resolution** string → numbers | `PM_UTIL_GetID`: `getpwent` enumeration + `strncmp(requested, entry, strlen(requested))` prefix match; copies `pw_uid`/`pw_gid`; no match → −1, fields unwritten | CONFIRMED static |
| Process-record **numeric** fields | svc record `+0x8` (uid), `+0xc` (gid), zero when unresolved | CONFIRMED static |
| **Credential calls** | `setgid(rec+0xc)` then `setuid(rec+0x8)` in the vfork child, each skipped when its field is zero (CLAUDE-004 rev 2) | CONFIRMED static |
| **Effective identity** | depends on parent credentials, resolver result, setter outcomes and executable/runtime transitions; unobserved | PENDING |

## Scope and unresolved

- Resolution is a **prefix** match over the passwd enumeration API. The numeric value for any label
  (`root`, `game`, …) is in whatever passwd database the system provides; it was **not** read, and
  the API does not establish `/etc/passwd` as the exclusive backing store or its contents. The
  effective uid/gid on the device is PENDING.
- Per-component skipping: a zero uid skips only `setuid`, a zero gid skips only `setgid`. There is no
  basis here for "a `root` account keeps the parent identity" by assuming uid 0 — the gid may differ,
  and the actual numbers are unverified. A failed resolution (no prefix match) does leave both fields
  zero (both setters skipped if execution reaches that block), because `AllocSvc` ignores the −1 and the record was calloc'd.
- This is one demonstrated path (`ExecuteProcess` → `AllocSvc` → `GetID`). Other callers of
  `PM_UTIL_GetID` or other writers of these fields were not enumerated (not requested); the claim is
  scoped to this path. Inline or indirect resolution elsewhere is not excluded, only shown
  unnecessary here.
- Nothing here is an admission, privilege or launch mechanism.

## Review corrections (including root integration)

1. **`strlen` operand corrected.** Revision 1 said `strlen(pw->pw_name)` and
   `strncmp(name, pw_name, strlen(pw_name))`. Verified: `strlen` measures `r4` = the **requested
   name**; the comparison is `strncmp(requested_name, entry_name, strlen(requested_name))` — a
   **prefix match**, first enumerated hit wins; empty name matches the first entry.
2. **No-match behaviour stated.** `PM_UTIL_GetID` returns −1 without writing `+0x8`/`+0xc`;
   `AllocSvc` ignores the return; the calloc'd zeros then cause both setters to be skipped.
3. **Per-component skipping / no root assumption.** Removed "a `root`-account service keeps the
   parent identity"; each field independently gates its own call and the numbers are unverified.
4. **Backing store narrowed.** Removed the implication that `/etc/passwd` is the exclusive source or
   that its numbers are known; `getpwent` is the enumeration API and the contents were not read.
5. **Radix.** `add #3792` is decimal `0xed0`; argv region at record `+0xed4`.
6. **Budget.** Stated the actual captured total, 1,564 bytes (the `getid.txt` capture is 296 bytes,
   of which `PM_UTIL_GetID` is 104).
7. **Removed the "CLAUDE-004 consistency defense."** Revision 1 claimed CLAUDE-004's prior wording
   was consistent; CLAUDE-004 in fact had control-flow errors, corrected in its revision 2. This
   report states the factual relationship without defending the earlier wording.

Root integration additionally distinguishes global-table storage from the caller's name buffer,
qualifies continuation through remaining launch prerequisites and live identity, and records the
unproven enumeration reset/null-input boundary.

Raw captures (`*.txt`) are unchanged; only this report and the derived `annotations.json` were
corrected.

## Experiment ACCOUNT-002 (revised)

- **Objective:** identify the demonstrated writer of the process-record uid/gid fields `+0x8`/`+0xc`.
- **Hypothesis:** a demonstrated resolver populates the record consumed by the credential setters.
- **Environment/procedure:** the same pinned procmgr on the Mac; four bounded captures and independent bytes, imports, arguments and branch checks. No credential database read or target execution.
- **Expected:** an evidenced writer or an explicit unresolved data-flow boundary.
- **Observed result (corrected):** `AllocSvc` `calloc`s the record and calls
  `PM_UTIL_GetID(name, &uid, &gid)`, ignoring its return; the resolver enumerates `getpwent`, matches
  by `strncmp(requested_name, entry_name, strlen(requested_name))` (prefix), and on a hit copies
  `pw_uid`/`pw_gid`; on no match returns −1 leaving the fields zero. The other two functions write
  different fields.
- **Conclusion:** the account name is resolved to a uid/gid pair by a prefix match over the passwd
  enumeration and stored in the record `setuid`/`setgid` later read; a failed resolution yields a
  zero pair (both setters skipped if later prerequisites reach that block). The numeric result for any label and the device's effective identity remain
  unverified.
- **Risks:** reading the prefix match as exact equality; assuming a uid-0 result for `root`; treating
  the passwd API as a known file with known numbers; over-generalising from one call path. Avoided by
  the labels above and by reading no credential file.
- **Next step:** this selected writer chain is established. Prioritize the unresolved native admission
  route; enumerate other callers only if a specific integration question requires it. An enumeration
  of direct callers alone would not prove there are no indirect writers.
