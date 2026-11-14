# Static initializer: first zero-return successor

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static bytes):** the selected successor contains a return-value gate, calls carrying technical initialization strings, and two stored pointers. **PENDING:** the callees' identities, successful initialization, reexecution and physical recovery. The evidence supports an initialization-preparation hypothesis; it does not establish an enforced prerequisite or an independent recovery path.

## Scope and provenance

The [reviewed entry/prefix](static-initializer-entry.md) justifies this interval through the zero-return branch at `0x82f8` to `0x853c`. The previous unknown call at `0x82f0` receives `APP_START`; its semantics have not been identified. This report therefore calls the new path a **zero-return successor**, not an absent-environment-variable path.

Input: `firmware/lab/lgin-selected/lginit`, 512,800 bytes, SHA-256 `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c`. ELF32 little-endian ARM `ET_EXEC`, entry `0x8120`. The executable segment maps linked `0x8000` to file offset zero. The new range is exactly **`[0x853c,0x85bc)`**, file `[0x53c,0x5bc)`, 128 bytes, SHA-256 `d47978389d029f8233fca0481121bc0917055846f998e41f4c391c19285ffe9c`.

Only this range was decoded, using the existing host LLVM, SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. ARM decoding remains an explicit assumption; no symbol, complete function extent or runtime execution is established. No callee or outside successor body was followed.

## Branches and argument contract

On the reviewed incoming path, r0 and r6 are zero; r4 was loaded with `0x8c1d0`. Continued use of r4/r6 across unknown calls assumes their usual ARM callee-saved preservation, not independently verified implementations. r1–r3 contain unspecified outputs from the preceding unknown call. Below, **U** means not established at that point; a prior call's return is a register value, not a proven success result. All ten call targets remain numeric.

| Call site → target | r0 at call | r1 | r2 | r3 | Following instruction if the call returns |
| --- | --- | --- | --- | --- | --- |
| `0x853c → 0x95bc` | 0 on the reviewed incoming edge | U | U | U | `0x8540` |
| `0x854c → 0x94c0` | `0x68cac`, string `/dev/null` | U | U | U | `0x8550` |
| `0x8554 → 0x8b28` | Return from `0x95bc` or `0x94c0`, depending on branch | U | U | U | `0x8558` |
| `0x8570 → 0xc6d0` | `0x8ce40` | 32 | `0x68cb8`, string `SWU_MODE=ON` | U | `0x8574` |
| `0x8578 → 0x8bf8` | Return from `0xc6d0` | U | U | U | `0x857c` |
| `0x857c → 0x8d48` | Return from `0x8bf8` | U | U | U | `0x8580` |
| `0x8584 → 0x9524` | Return from `0x8d48` | U | U | U | `0x8588` |
| `0x859c → 0xc6d0` | `0x8ce60` | 32 | `0x68cc4`, string `LOCKUP_LEVEL=%d` | 1 if `0x9524` returned zero, otherwise 0 | `0x85a0` |
| `0x85a4 → 0x95bc` | Return from `0xc6d0` | U | U | U | `0x85a8` |
| `0x85b4 → 0x94c0` | Saved return from the first `0x94c0` call, or zero if that call was skipped | U | U | U | `0x85b8` |

This records all four register positions, without asserting how many arguments any unknown callee accepts or whether stack arguments exist. The visible conditional branches are:

- `0x8544`: the first `0x95bc` return is tested at `0x8540`; nonzero goes to `0x8554`, zero falls through to the `/dev/null` call. `0x8550` saves that call's return in r6, with no validity check, then joins at `0x8554`.
- `0x855c`: `0x8b28`'s return is tested at `0x8558`; zero goes outside the slice to **`0x85dc`**, nonzero falls through to `0x8560`. The zero branch cannot be called failure, success, non-SWU selection or a cleanup path until its contract is established.
- `0x85ac`: the second `0x95bc` return is tested at `0x85a8`; nonzero skips directly to `0x85b8`, zero passes r6 to `0x94c0` before the same join. The two `0x95bc` results are not assumed equal.

At `0x858c`, RSBS computes `1 - r0`; MOVLO at `0x8590` changes r3 to zero for unsigned r0 greater than one. Thus r3 is exactly the zero-test Boolean shown in the table, including for high-bit-set return values. It is not an unchecked direct copy of a returned configuration value.

## Referenced data and effects not established

Six external literal words were read. Each is justified by its PC-relative load inside the approved slice.

| Instruction | Literal address | Loaded value | Use |
| --- | --- | --- | --- |
| `0x8548` | `0x8620` | `0x68cac` | `/dev/null` argument |
| `0x8560` | `0x860c` | `0x8ce40` | r5, then call argument and stored pointer |
| `0x8568` | `0x8610` | `0x68cb8` | `SWU_MODE=ON` argument |
| `0x8580` | `0x8628` | `0x8ce60` | r5, then call argument and stored pointer |
| `0x8594` | `0x862c` | `0x68cc4` | `LOCKUP_LEVEL=%d` argument |
| `0x85b8` | `0x8630` | `0x68cd4` | r0 at the final captured instruction; subsequent use unknown |

The last pointer's target was **not read**: the slice does not contain a call proving its use as a string argument. The other three technical strings were read in bounded 96-byte windows, retaining only NUL-terminated contents. No pointed-to writable buffer, environment contents or credential data was inspected.

Instructions `0x8574` and `0x85a0` store r5 to `[r4+8]` and `[r4+12]` respectively. With the inherited r4 value and callee-save assumption, these are locations `0x8c1d8` and `0x8c1dc`. No successful string formatting, environment installation, mount operation or later consumer is proven by these stores. There is no return-value check between the formatting-shaped calls and their stores, nor between `0x8bf8`, `0x8d48` and `0x9524`. Their implementations may enforce conditions internally, but that is outside this evidence.

The [dynamic initializer report](recovery-entry-contract.md) offers a hypothesis for the similar preparation sequence. Its import/symbol names and mount/reexecution findings apply to that other ELF. They are not identities for these static targets. In particular, `/dev/null` is not proof that `0x94c0` redirects descriptors, and a format-shaped call is not proof that `0xc6d0` implements `snprintf`.

## Reproduction and stop boundary

Run `PYTHONPATH=. python3 artifacts/static-initializer-successor/capture_verify.py`. The ignored directory includes the script, capture, literal metadata, verification and manifest. The verifier checks all **32 words**, all **13 immediate branch/call destinations**, six literal-load addresses, pinned input and host hashes, and three string values/hashes. Call fallthroughs and both conditional successors are retained; no nonreturning property is assumed.

New accounting: **128 code bytes**, **24 external literal bytes**, and **288 bytes of string read windows**, retaining **38 NUL-terminated string bytes**. Across the entry, prefix and this successor, the cumulative instruction capture is **640 bytes**, external literal words **44 bytes**, and string windows **480 bytes**, retaining **61 string bytes**. Original startup literals were already inside the entry capture. These totals exclude metadata/hash reads of the source file; they describe selected analysis ranges, not total filesystem I/O. No neighboring instructions were captured.

At the end of the original128-byte experiment, the next instruction at `0x85bc` and alternate successor at `0x85dc` remained uninspected; the separately assigned follow-up below resolves that boundary. A precise proposed next slice is **`[0x85bc,0x85e4)` (40 bytes)**, anchored by those two known successors and stopping before the already identified word at `0x85e4`. This is a proposed capture budget, not a function boundary or authorization to follow further callees. It could reveal whether the loaded r0 pointer reaches a call and whether both paths rejoin. No such continuation was decoded here.

Experiment STATIC-ENTRY-003: **Objective:** inspect the reviewed zero-return successor for initialization/reexecution prerequisites. **Hypothesis:** a bounded successor exposes relevant preparation and conditional control flow. **Environment/procedure:** pinned existing ELF, one 128-byte host disassembly, six referenced words, three proven argument strings, raw-word and branch checks. **Expected:** explicit gates and calls or a precise unresolved boundary. **Observed:** one external zero-return branch, preparation-shaped calls with SWU/lockup literals, pointer stores and two local joins. **Conclusion:** preparation is supported as a hypothesis; enforcement and reexecution remain unproven. **Risks:** mistaking unknown return values for success, guessing static API identities from dynamic analogues, or extrapolating active recovery. **Next:** independent review passed; separately scoped successor tracing if assigned. No target execution, emulation, device/IPC/LAN, credential read, system change or Git operation occurred.

Independent review reproduced the exact128-byte interval and verified all32words,13targets, six literals,38string bytes, argument provenance and the Boolean calculation. Callee-save assumptions remain explicit; no new target or successor was read. Evidence: ignored `artifacts/static-initializer-successor-review/`.

## Separate follow-up: the 40-byte tail

**Independently reviewed.** This separately assigned continuation resolves the two successor addresses left open by the preceding, reviewed experiment. Its scope is exactly **`[0x85bc,0x85e4)`**, file `[0x5bc,0x5e4)`, 40 bytes, SHA-256 `ee0f3573877bb8517523d8ab10c50bb7ecc7085ff5d90b73da5d4ac2c5b0f3d7`. The selected ELF and host LLVM hashes are unchanged. No callee body or additional branch target was decoded.

The previously retained pointer from `0x85b8` now has demonstrated call provenance: r0 remains `0x68cd4` until the call at `0x85c4`. Reading its bounded technical string yields **`/lg/lginit/lginit_app`**. The continuation sets r1 to zero and r4 to SP+20 before that call. This is a call carrying an executable-looking pathname; it supports a launch/reexecution hypothesis but does not identify the unknown callee `0x938c` as an execution API or prove a launch attempt actually occurs inside it.

| Call site → unknown target | r0 | r1 | r2 | r3 | Following instruction if it returns |
| --- | --- | --- | --- | --- | --- |
| `0x85c4 → 0x938c` | `0x68cd4`, string `/lg/lginit/lginit_app` | 0 | U from prior call | U from prior call | `0x85c8` |
| `0x85d4 → 0x1c9d0` | `0xffffffff` | SP+20, through r4 | 0 | U from the preceding call | `0x85d8` |
| `0x85dc → 0x8d48` | 0 from the reviewed `0x8b28` zero-return edge | U from `0x8b28` | U from `0x8b28` | U from `0x8b28` | `0x85e0` |

U denotes unspecified register contents, not absent arguments. At `0x85c0`, r4 is replaced with a stack pointer; it no longer holds the earlier pointer-table base. Continued use of this stack pointer across calls assumes callee-saved r4 and balanced SP. No stack slot contents were read as data, and no complete callee argument count is inferred.

Two unconditional branches close the visible flow:

- **`0x85d8 → 0x85c8`:** if the unknown call at `0x85d4` returns, r1, r2 and r0 are set again and the call repeats. The result of `0x938c` is neither tested nor retained as an argument: `0x85d0` overwrites r0 before the subsequent call. The repeated call's return is also untested. This demonstrates a caller-side loop with no visible exit, not its timing, blocking behavior, wait/reap semantics or runtime liveness.
- **`0x85e0 → 0x8580`:** the zero-return edge from `0x855c` first calls `0x8d48` at `0x85dc`, then rejoins the already reviewed preparation continuation at `0x8580`. The nonzero edge calls `0x8bf8` and then the same `0x8d48` before reaching `0x8580`. Thus both alternatives converge after a call to `0x8d48`, **provided their respective calls return**. The zero alternative skips the visible `SWU_MODE=ON` preparation/store and `0x8bf8` call; it does not establish the previous contents of the skipped storage slot.

The two calls to `0x8d48` receive different demonstrated r0 provenance: zero on the alternate edge, versus `0x8bf8`'s return on the nonzero edge. The callee might ignore that register, but no signature has been recovered here. No return check at either site establishes successful initialization before the shared continuation. Likewise, absence of a caller-side check does not rule out enforcement inside the unknown callees.

**Evidence conclusion:** a pathname-bearing call and a subsequent unconditional call loop are now present in the static initializer's selected bytes. Both earlier branch alternatives can reach that call through the demonstrated join. These are useful prerequisites for a focused callee-identity investigation, not proof that static `lginit` launches `lginit_app`, that its dependencies mount successfully, or that it can recover a failed root filesystem or launcher. Dynamic initializer names remain comparison evidence only.

Reproduce with `PYTHONPATH=. python3 artifacts/static-initializer-tail/capture_verify.py`. Ignored captures and verification pin the source/host, compare all **10 words** with mapped bytes, independently calculate all **five branch/call destinations**, and reuse the previously hashed pointer evidence. New accounting is **40 code bytes**, **zero new external literal words**, and **one 96-byte technical-string window**, retaining **22 NUL-terminated bytes**. The cumulative selected code is **680 bytes**, external literal words remain **44 bytes**, and technical-string windows total **576 bytes**, retaining **83 bytes**. These are analysis-selection counts, excluding whole-file validation/hash I/O. No new neighboring instructions were captured.

Experiment STATIC-ENTRY-004: **Objective:** resolve the two known continuations and test whether a pathname-bearing call is visible. **Hypothesis:** the narrow tail contains a shared continuation or a relevant call without requiring further target tracing. **Environment/procedure:** unchanged selected ELF and pinned host LLVM, one 40-byte capture, reuse of an existing pointer literal, one justified argument-string read, and raw branch verification. **Expected:** explicit joins/call arguments or an unresolved boundary. **Observed:** `0x85dc` rejoins `0x8580`; `0x85c4` receives `/lg/lginit/lginit_app` and zero; a separate unknown call repeats without a caller-side return check. **Conclusion:** a launch/reexecution hypothesis is better anchored, while implementation, enforcement and physical recovery remain unknown. **Risks:** naming an execution/wait API by analogy or interpreting a loop as successful execution. **Next:** independent review passed; stop this bounded trace. Further callee-identity work requires a new evidence-based plan; no additional slice is implicitly assigned or proposed here. No target execution, emulation, device/IPC/LAN, credential read or Git operation occurred.

Independent tail review passed: exact40-byte reproduction,10words, five targets, inherited pointer/pathname, changed r4 provenance, both joins and the unchecked caller-side loop. No callee or additional slice was read. Evidence: ignored `artifacts/static-initializer-tail-review/`.
