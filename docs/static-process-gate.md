# Static initializer: clone-backed process gate

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static):** the gate called at `0x93c0` contains a direct ARM EABI syscall 120 with flags `0x01200011`, followed by distinct zero, nonzero and normalized-error paths. Under the primary Linux ARM contract, this is **clone with fork-style flags**, supporting child/parent interpretation of its syscall results. **PENDING:** completion of all wrapper paths, live callback state, successful process creation, execution and recovery. No physical TV behavior was tested.

## Inputs and bounded selection

The [reviewed execution-callee report](static-execution-callee.md) establishes `0x93c0 → 0x1cd70`, with the result determining whether the execution-selection path is entered. Input: `firmware/lab/lgin-selected/lginit`, SHA-256 `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c`, 512,800 bytes. Host LLVM SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. All ranges use the existing executable mapping, file offset = linked address − `0x8000`.

| Capture | Linked range | Bytes | Why selected |
| --- | --- | --- | --- |
| Initial | `[0x1cd70,0x1ce70)` | 256 | Reviewed direct caller target |
| Join | `[0x1ce54,0x1cf54)` | 256 | Explicit BEQ at `0x1cd88 → 0x1ce54` |
| Returns | `[0x1cf70,0x1d08c)` | 284 | Explicit BEQ at `0x1cf44 → 0x1cf70` |

The first two captures overlap by **28 bytes**. Their union plus the third range is exactly **768 unique bytes**, from 796 captured bytes. The gap **`[0x1cf54,0x1cf70)` remains unread**. The final 16 bytes are four referenced literal words, giving 752 selected instruction bytes and 16 in-capture data bytes. These ranges are not asserted function extents. Only the two demonstrated follow-up destinations were followed; outside callees and indirect callback bodies were not inspected.

## Before the syscall: conditional preparation

At entry, a pointer is read through the literal at `0x1d07c`, which contains `0x8e714`. No live value at that location was read. If its loaded value is zero, `0x1cd88` goes directly to `0x1ce54`, leaving r5=0. Otherwise the captured code traverses linked records, manipulates fields at record offset `0x14`, and conditionally invokes a callback from offset `+4` at `0x1ce30`. It builds a temporary list on its own stack. These operations support callback/locking preparation, not identification of specific pthread APIs.

Computed PC transfers at `0x1cd94`, `0x1cdc8`, `0x1ce0c` and `0x1cffc` resolve respectively to `0xffff0fa0` and three instances of `0xffff0fc0`. Their bodies were not read. Condition-dependent retry loops remain dependent on those helpers and memory state. At the join, unknown `0x12ebc` is called before the syscall setup; its return is not used as a success gate. Entry into the routine therefore does not guarantee reaching the trap.

## Exact syscall contract

After the call returns, MRC at `0x1ce58` reads the thread-pointer register into r12. The code saves words at thread-pointer offsets `-0x454` and `-0x458`, writes the negation of the former back to `-0x454`, and constructs these syscall arguments:

| Register at `0x1ce8c` | Value | Linux ARM clone interpretation |
| --- | --- | --- |
| r7 | 120 | Syscall number |
| r0 | `0x01200011` | Flags plus exit signal |
| r1 | 0 | Use current stack |
| r2 | 0 | Parent-TID pointer, unused by these flags |
| r3 | 0 | TLS argument, with no SETTLS flag |
| r4 | thread pointer − `0x458` | Child-TID pointer |

The r4 calculation is explicit: subtract 1216 (`0x4c0`) at `0x1ce64`, then add 104 (`0x68`) at `0x1ce84`. At `0x1ce88`, r7 becomes 120; **`SVC 0` executes at `0x1ce8c`**. The earlier caller's incoming values are overwritten for the syscall.

Primary Linux v3.0 [ARM syscall definitions](https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/unistd.h) identify EABI syscall 120 as clone; its [ARM implementation](https://github.com/torvalds/linux/blob/v3.0/arch/arm/kernel/sys_arm.c) accepts flags, stack, parent-TID, TLS and child-TID arguments, substituting the current stack when the supplied stack is zero. This is an ABI comparison, not identification of the vendor kernel build.

The observed flags decompose into `CLONE_CHILD_SETTID` (`0x01000000`), `CLONE_CHILD_CLEARTID` (`0x00200000`) and exit signal 17 (`SIGCHLD`). `CLONE_VM`, `CLONE_VFORK` and `CLONE_THREAD` are absent. These are fork-style process-creation flags, rather than the shared-memory/vfork flag combination. Sources: Linux [clone flag definitions](https://github.com/torvalds/linux/blob/v3.0/include/linux/sched.h) and [ARM signal numbers](https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/signal.h). This does not recover the static routine's original symbol name.

## Return checks and limits of child/parent attribution

At `0x1ce90`, CMN r0,#4096 establishes the error test; MOV r10,r0 at `0x1ce94` preserves the returned value without changing flags. BHI at `0x1ce98` selects the unsigned range `0xfffff001..0xffffffff`, exactly signed -4095..-1. Exactly -4096 does not take that branch. Remaining values are tested against zero at `0x1ce9c`.

Under the referenced Linux implementation, the child receives zero in r0, while the caller receives the child PID or a negative error. These semantics are supported by [ARM child register initialization](https://github.com/torvalds/linux/blob/v3.0/arch/arm/kernel/process.c) and [`do_fork` return handling](https://github.com/torvalds/linux/blob/v3.0/kernel/fork.c). The captured wrapper then applies its own checks and cleanup before returning:

| Syscall result | Captured route | Return value if cleanup reaches the common epilogue |
| --- | --- | --- |
| Zero, child under the standard contract | `0x1cea4` onward | Saved r10 = 0 |
| Nonzero, nonerror; positive PID under the standard contract | `0x1cea0 → 0x1cf9c` | Saved PID |
| Error -4095..-1 | `0x1ce98 → 0x1cf88`, then joins `0x1cf9c` | r10 normalized to -1 |

**Error normalization.** At `0x1cf88`, the referenced literal at `0x1d08c` is `0x6c0f4`; the indexed load at `0x1cf94` resolves to `0x89090`, containing `0x18`. The negated error is stored at `[r12+0x18]`, and r10 becomes `0xffffffff`. This is errno-style normalization; no live thread storage was read.

**Child route.** It compares the current thread-pointer word at `-0x458` with its saved pre-syscall value. Equality branches `0x1ceac → 0x1d068`, which calls unknown `0x2a57c`; its behavior is not assumed. Inequality proceeds through global updates and several unknown calls/iteration at `0x1ced0..0x1cf0c`. If they complete and r5 is zero, `0x1cf44 → 0x1cf70` reaches a visible epilogue. If r5 is nonzero, `0x1cf48..0x1cf50` starts a callback-related path that continues into the deliberately unread gap. Its complete route cannot be certified here.

**Parent/error route.** It checks the same thread word against the saved value. Inequality branches `0x1cfa4 → 0x1d054` to the unknown `0x2a57c` call path. Equality restores the saved word at offset `-0x454`, calls unknown `0x12f34`, then tests r5. Zero branches `0x1cfb4 → 0x1cf7c`. Nonzero processes the temporary list, conditionally calls record callback `+8` at `0x1cfc8`, performs retry operations, and eventually can branch to that same return. A conditional trap at `0x1d04c` uses syscall number 240; it is part of this cleanup, not another process-creation syscall. Its blocking and live-resource behavior were not investigated.

**Common return.** At `0x1cf7c`, r0 receives r10; SP is restored from r11 and registers/PC are popped at `0x1cf84`. Child entry through `0x1cf70` first clears a global word. The parent/error empty-list edge enters directly at `0x1cf7c`. The distinction matters: not every return executes the clear at `0x1cf78`.

Neither call to `0x2a57c` is proven nonreturning. If the first returns, it falls through to the second call setup at `0x1d068`; if the second returns, the next address `0x1d07c` is captured literal data. No safe return, abort or recovery outcome is inferred for these exceptional paths.

Preservation of r5, r8, r10 and the frame register across unknown ordinary calls assumes their ARM callee-saved contract. The selected bytes do not independently verify those callees or callback termination.

## Consequence for the reviewed execution path

The prior gate can now be described as **clone-backed, with fork-style flags and conditional child/PID/error return semantics**. If the standard syscall succeeds and the child cleanup returns normally, the caller at `0x93c4` sees zero and selects the already evidenced execve-attempt path. If the parent cleanup returns a PID, that caller returns it without entering execution selection. A normalized error returns -1 through the nonzero route, if cleanup completes. This removes the earlier need to infer child identity solely from a zero branch.

It still does not prove that the wrapper completes, that a live child executes the image, or that the television can recover when its launcher/root filesystem fails. Unknown callbacks, helper routines, thread checks, the unread child-callback gap and unverified execution vectors remain material boundaries. No physical process, filesystem or environment was queried.

## Reproduction, accounting and stopping point

Run `PYTHONPATH=. python3 artifacts/static-process-gate/capture_verify.py`. The ignored manifest pins all captures and references. Verification checks **192 unique displayed words**, **37 direct branch/call destinations**, the two follow-up predecessor edges, overlap identity, 11 literal-load addresses, four computed helper transfers and synthetic error-range endpoints. Register-indirect callbacks remain unresolved; their destinations are not invented.

Beyond the 768 unique captured bytes, **six additional referenced words (24 bytes)** were inspected: five literal words immediately outside the last interval and the computed `0x89090` word. Four other literal words are already included in the capture accounting. No argument/environment contents, technical strings, runtime globals or further code were read. Validation/hash I/O over the original is excluded from selected-range counts. Capture SHA-256 values are retained in `initial.json`, `join.json`, `returns.json` and the manifest.

Previously downloaded ARM syscall sources were reused. Additional upstream v3.0 flag, signal, child-register and fork references were retrieved as plain text with no redirects/proxies, an eight-second request timeout and a 128-KiB cap per file; `primary-sources.json` records hashes and URLs. These references define the comparison contract, not the exact firmware source lineage.

Experiment STATIC-PROCESS-001: **Objective:** identify the process gate and its return contract. **Hypothesis:** bounded successor tracing exposes a clone/fork syscall rather than an unexplained zero-return test. **Environment/procedure:** unchanged selected ELF, initial 256-byte range, two demonstrated follow-up destinations within the authorized region, 768-byte unique cap, raw instruction/branch verification and primary ABI comparison. **Expected:** a syscall-backed contract or a precise unresolved boundary. **Observed:** clone syscall 120, fork-style flags, error normalization and separate child/parent cleanup leading conditionally to a common return. **Conclusion:** syscall semantics are supported; universal wrapper completion and runtime success are not. **Risks:** treating callback cleanup as guaranteed, reading an error path as a successful child, or assigning runtime values to file-backed pointers. **Next:** independent review passed; stop this scope. Closing the remaining callback path or any outside helper requires a separate plan, not automatic expansion. No firmware execution/emulation, TV/LAN/IPC, credential read or Git operation occurred.

Independent review reproduced the three ranges and verified the768-byte union,28-byte overlap,192words,37targets,11literal loads, six external words, four computed helpers and primary ABI references. The unread gap and unknown callbacks/helpers remain explicit; no additional code or runtime values were read. Evidence: ignored `artifacts/static-process-gate-review/`.
