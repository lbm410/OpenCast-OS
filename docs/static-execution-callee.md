# Static initializer: execution syscall reached from the pathname call

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static):** the pathname-bearing call at `0x85c4` reaches code containing an ARM `SVC 0` with r7=11 and filename/vector arguments in r0–r2. This matches the Linux ARM EABI `execve` syscall contract. **PENDING:** whether the earlier unknown call creates a process, which branch runs on the unit, argument/environment validity, successful execution and recovery. The result strengthens the execution-attempt hypothesis without establishing a parent/child lifecycle or an operational recovery procedure.

## Provenance and selected ranges

The [reviewed initializer successor](static-initializer-successor.md) establishes the caller's r0=`/lg/lginit/lginit_app`, r1=0 at `0x85c4 → 0x938c`. Input remains `firmware/lab/lgin-selected/lginit`, 512,800 bytes, SHA-256 `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c`. Host LLVM SHA-256 remains `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`.

Two explicitly scoped captures were made; neither is asserted to be a symbol-defined function extent:

| Linked interval | File interval | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `[0x938c,0x948c)` | `[0x138c,0x148c)` | 256 | `1c9d7ac4b7ff0494464397946e8afcc29a7ccc9d1f178bea3d50dac74744de04` |
| `[0x1d100,0x1d17c)` | `[0x15100,0x1517c)` | 124 | `a55d14b79b88f65406561c4084b45e488093cac91e8a90846efb748ae323afaa` |

The extension was approved specifically because the first capture calls both `0x1d100` and `0x1d13c`; no other callee was followed. ARM decoding remains an explicit assumption consistent with this code and the ELF metadata. No target code was executed or loaded.

## Preparation and the unresolved process-creation gate

Let T be SP after the prologue at `0x9394`. The code preserves the incoming pathname in r6, computes r12=T+8+4×incoming-r1, copies two words into `[T,T+8)`, and loads `[r12-8]`. The two copied values, read from the directly referenced template at `0x68db0`, are `0x7b9c4` and `0x7ca30`. For the reviewed incoming r1=0, the selected value is **`0x7b9c4`**, not zero.

The stores at `0x93b8`/`0x93bc` populate `[0x8cec0]` with the pathname pointer and `[0x8cec4]` with that selected template word. This address is subsequently supplied as the argument-vector pointer to the syscall wrapper. Neither the pointed-to argument string nor further vector elements were read. A terminating NULL and the complete argument list remain unverified; the second element must not be described as a NULL terminator.

At `0x93c0`, unknown destination **`0x1cd70`** is called. At that point r0/r1 retain the two template values, r2=`0x68db0`, and r3 is the selected template value. Its signature is unknown. SUBS at `0x93c4` saves the return in r4:

- Nonzero: fall through `0x93cc`, copy r4 into r0, restore stack/registers and return through the saved PC at `0x93d4`. There is no separate positive-versus-negative test; a negative return follows this same path.
- Zero: branch `0x93c8 → 0x93d8` into the execution-selection path below.

This structure resembles a fork wrapper. **It is not proof that `0x1cd70` implements fork, vfork or clone.** Accordingly, “zero branch” and “nonzero branch” are the established names; “child” and “parent/error” remain hypotheses. Subsequent use of r4–r6 across unknown calls assumes their usual callee-saved preservation.

## Zero branch: exact selector and execution arguments

The zero branch calls **unknown `0xbb78`** at `0x93dc` with r0 pointing to the technical string `IS_NFS`; r1–r3 are unspecified outputs of the previous unknown call. A zero return branches to `0x943c`. A nonzero return is dereferenced byte by byte and compared with four directly referenced constant bytes at `0x69424`: **`59 45 53 00` (`YES` plus NUL)**. Mismatch at any of `0x93f8`, `0x9408`, `0x9418` or `0x9428` also selects `0x943c`. This is exact four-byte comparison, not a prefix test. It does not by itself identify `0xbb78` as `getenv` or prove a valid returned object.

| Selection | Call | Values passed before wrapper transformation |
| --- | --- | --- |
| Four-byte match | `0x9434 → 0x1d13c` | r0=pathname; r1=`0x8cec0`; r2=0 and r3=0 from the final matching NUL-byte comparison |
| Lookup return zero or any mismatch | `0x9448 → 0x1d100` | r0=pathname; r1=`0x8cec0`; r2=`0x8c1d0`; r3 is branch-dependent and irrelevant to this three-argument syscall |

If the first call returns, `0x9438 → 0x944c` joins the second call's return path. No success claim follows from entering either branch.

## Direct syscall evidence and wrapper transformations

At `0x1d100`, r7 is pushed, set to **11**, and `SVC 0` executes at `0x1d108`. r0–r2 are not changed before this trap. The primary Linux ARM [syscall definitions](https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/unistd.h) define EABI base zero and syscall 11 as `execve`; the corresponding [ARM syscall implementation](https://github.com/torvalds/linux/blob/v3.0/arch/arm/kernel/sys_arm.c) takes filename, argv and envp. This identifies the attempted syscall contract under that ABI, not the physical kernel version, active configuration or successful result.

The entry at `0x1d13c` constructs address **`0x8dd78`**, loads its word into r2 and unconditionally branches at `0x1d148` to `0x1d100`. It preserves r0/r1. Thus both call routes reach the same syscall, with different environment-pointer provenance: explicit address `0x8c1d0` versus a pointer read from slot `0x8dd78`. That slot lies inside the ELF segment's zero-fill-only extent, outside its file-backed bytes. Its live value depends on runtime initialization and was not invented from file contents. Neither environment vector was read.

The returned-syscall path performs CMN r0,#4096 at `0x1d10c`; BHI at `0x1d110` selects the error normalization for unsigned values `0xfffff001..0xffffffff` (signed -4095..-1), excluding exactly -4096. Otherwise it restores r7 and returns at `0x1d118`. On the error path:

1. r1 receives the negated returned value.
2. MRC at `0x1d124` reads the thread-pointer register into r2.
3. The in-capture literal at `0x1d138` is `0x6bf5c`. The indexed PC-relative load at `0x1d12c` therefore reads `0x89090`, whose explicitly inspected word is `0x18`.
4. The code stores r1 at `[r2+0x18]`, sets r0 to `0xffffffff`, then branches `0x1d134 → 0x1d114` to restore r7 and return. This is consistent with errno-style normalization; no live thread storage was read.

The nearby blocks starting `0x1d150` and `0x1d170` were incidentally captured by the approved fixed window. They are not reached by these wrappers' visible branches and are not attributed to the observed execution call. Their decoded syscall immediates do not prove that the caller invokes those operations. The neighbor branch to `0x20100` was checked arithmetically but not followed.

## Caller-visible failure behavior

At the common return point `0x944c`, CMN r0,#1 checks specifically for `0xffffffff`. Any other returned value branches `0x9450 → 0x93cc`, returning the saved r4, which is **zero on this branch**. A returned -1 instead loads the technical label `lginit`, calls **unknown `0xc7ac`** at `0x9458`, then branches `0x945c → 0x93cc`. If that diagnostic-shaped call returns and preserves r4, the wrapper also returns zero after the syscall error. It does not propagate the returned -1 to its caller on this path. No exit/abort operation occurs in the captured error path.

For the inspected error normalization, r1 at `0xc7ac` contains the positive error magnitude, r2 the thread pointer and r3=`0x18`; only r0 is explicitly prepared by the outer routine. This does not establish the diagnostic callee's signature or identify it as `perror`.

The original caller ignores the outer return and enters the already reviewed repeated-call loop. This provides neither a successful-execution handshake nor proof that an error path terminates a newly created process. Establishing a child/parent relationship still requires evidence for `0x1cd70`; no such body was inspected.

## Accounting, reproduction and unresolved boundary

Run `PYTHONPATH=. python3 artifacts/static-execution-callee/capture_verify.py`. The script pins the source and host, validates all **95 displayed words**, checks **18 direct branch/call destinations** (one in an unattributed neighbor), verifies seven PC-relative literal loads in the first window, and records external words and argument strings. The in-capture data words are not interpreted as instructions when following control flow. Synthetic arithmetic checks cover the error-range endpoints.

The **380 captured bytes** comprise 284 bytes attributed to the examined instruction paths, 28 bytes of literal pools, four unassigned zero bytes and 64 bytes of unattributed neighboring instructions. These are capture/accounting categories, not recovered function sizes. Additional data reads were **four external words (16 bytes)**: three in the first stage, one in the approved extension. Two technical-string windows total **192 bytes**, retaining **14 NUL-terminated bytes**. The pathname was reused from reviewed evidence; no argument-string targets or environment contents were read. Whole-file validation/hash I/O is excluded from these selected-read counts.

Primary reference copies under the same ignored directory were fetched as text from the upstream Linux mirror, with redirects/proxies disabled, an eight-second request timeout and a 64-KiB cap per file. `primary-sources.json` records URLs, lengths and hashes for `unistd.h`, `entry-common.S` and `sys_arm.c` at tag v3.0. They establish an ABI comparison, not exact source provenance of this vendor firmware.

**Stop boundary:** `0x1cd70`, `0xbb78` and `0xc7ac` remain unknown; the complete argument/environment vectors and live selector value remain unverified. The selected code now supports a concrete execve-attempt contract, but no runtime execution or recovery success. Further work must separately choose whether process-creation identity or argument-vector validity is the next highest-value missing edge; this report does not authorize recursive tracing or a device experiment.

Experiment STATIC-EXEC-001: **Objective:** determine whether the observed pathname call reaches a demonstrable execution operation. **Hypothesis:** its bounded body exposes an execution wrapper rather than merely a pathname consumer. **Environment/procedure:** pinned existing ELF, approved 256-byte window and explicitly approved 124-byte extension, bounded data reads, raw instruction/branch checks and primary ABI comparison. **Expected:** an execution syscall or an exact unresolved call boundary. **Observed:** syscall number 11 with unchanged filename/argv and either explicit or loaded envp; zero/nonzero outer gate and returned-error handling. **Conclusion:** an execve attempt is statically supported under Linux ARM EABI; fork identity, successful launch and recovery are not. **Risks:** equating zero with a child, confusing pointer slots with live contents, or transferring dynamic names. **Next:** independent review passed; a separately scoped process-gate study may resolve the initial zero/nonzero split. No target execution/emulation, TV/LAN/IPC, credential read or Git operation occurred.

Independent review reproduced both380-byte windows and verified all95words,18direct targets, seven literal loads, four external words,14retained string bytes and three primary-reference copies. The review preserves the unknown process gate, incomplete vectors, unobserved runtime environment and absence of recovery proof. Evidence: ignored `artifacts/static-execution-callee-review/`.
