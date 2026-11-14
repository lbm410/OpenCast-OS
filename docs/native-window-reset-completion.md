# Native window reset: queue acceptance is not completion

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static):** the type-4 reset request reaches a concrete consumer in `PM_GX_CoreTask`, which invokes the previously examined local reset. Its return value is ignored. That local reset can itself enqueue a separate type-2 update whose failure is also not propagated to the original requester. **PENDING:** acknowledged window release, subsequent graphics completion, callback quiescence, surface destruction and physical restoration.

## Scope and provenance

Only the existing selected `firmware/lab/service-selected/open/bin/procmgr` was inspected: 435,528 bytes, SHA-256 `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5`. Host LLVM SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. ARM linked addresses map to file offsets by subtracting `0x8000`.

The [window-allocation report](native-window-allocation.md) supplies the reviewed producer `[0x31d34,0x31e20)` and direct reset `[0x31a74,0x31d34)`. Their captured words were checked against the unchanged input without recapturing other code. New selections are:

| Range | Bytes | Evidence for selection |
| --- | --- | --- |
| `[0x357e0,0x35be0)` | 1,024 | Exported `PM_GX_CoreTask`, including queue receive and dispatch |
| `[0x35f50,0x35ff4)` | 164 | Type-4 jump-table entry at `0x359dc` |
| `[0x36184,0x361c0)` | 60 | Direct single-item and type-4 alternate branch targets |
| `[0x362f0,0x36328)` | 56 | Queue-initialization failure branch at `0x35810` |
| `[0x31730,0x31a74)` | 836 | Optional call from reviewed direct reset at `0x31d08` |

The five disassembly windows total **2,140 unique bytes**; four explicitly decoded 12-byte PLT stubs add 48 metadata bytes, making **2,188 selected bytes across nine ranges** if those stubs are counted as code ranges. No queue-provider body, other type consumer body, target execution, IPC or device operation was performed. Captured portions of other switch cases are incidental and do not support claims about their complete behavior.

Independent review reproduced the selected bytes, imports and control-flow interpretation without corrections. The reviewed report snapshot was SHA-256 `2f0460b4c2bbdfb4e2683a1bc7eaf504dfb5efb3d8fe023d5003c8a8a805aa1b`; ignored review evidence is under `artifacts/native-window-reset-completion-review/` (`review.md`: `c0b32913265894f5cc3898e2e35263d29d5420f6206624c98d52fabd188b3126`). This integration note changes the report hash, not the frozen evidence.

## Exact queue connection

The dynamic-symbol table establishes `PM_GX_CoreTask` at `0x357e0`, size `0xbe4`. At `0x35800`, it calls the PLT binding for **`osa_queue_init`** with r0 pointing to technical name `qGxMsgQ`, r1=128, r2=64 and r3=0. The return is stored at global word **`0x97720 + 0x4e0 = 0x97c00`**. Zero branches to warning/backtrace and returns zero from this task entry; startup readiness is not established by this static path. The exact meaning and limits of the initializer's parameters beyond their observed values require the provider contract.

The producer loads the handle from the same slot at `0x31d84`. The consumer loads it at `0x35864` and calls **`osa_queue_recvmsg`** at `0x35874`, with a 64-byte destination and fourth register argument `0xffffffff`. A nonzero returned status restarts the receive loop. A zero status proceeds to dispatch. Imports are resolved from the pinned ELF's PLT/GOT relocations, not merely guessed from names or disassembler labels. The fourth argument's timeout semantics are not inferred here.

The consumer also calls **`osa_queue_getcount`** at `0x358d0` and may receive additional messages. It copies the first message and additional non-type-1 messages into a local array of 64-byte records. Only type 1 takes the distinct coalescing/search branch; the selected type-4 route is copied with its type and payload intact. This does not establish the queue provider's ordering, lifetime, delivery or concurrency guarantees.

## Producer acceptance and message identity

In `PM_GX_ResetWindowInfo`, the service-name lookup requests no new allocation. An invalid ID returns -2. Unless its second argument is exactly 1, the routine zeroes a 64-byte message, writes **type 4 at offset 0** and **the resolved numeric window ID at offset 4**, then calls `osa_queue_sendmsg` at `0x31d98`.

- A zero enqueue return is returned directly to the producer's caller. There is no wait or subsequent completion check in this branch.
- A nonzero enqueue return causes warning/backtrace and returns -1.
- The alternate argument=1 branch calls the direct reset at `0x31db0`, then explicitly returns zero, without propagating that reset's result.

The enqueued message contains no service name, generation, sender connection, acknowledgment token or surface handle: those remaining bytes were explicitly zeroed. Its identity is a numeric window ID. Neither enqueue success nor the ID establishes a service-bound lease or proves that the same logical owner still occupies the record when processing occurs. This is an evidence limit, not a demonstrated race on the physical unit.

## Type-4 dispatch and observed completion boundary

The consumer's array starts at SP+132. The dispatch pointer is record+24; the type comes from `[r4-24]`, and type 4 is selected by the ARM table load at `0x359c4`. With PC=`0x359cc`, index 4 reads **`[0x359dc] = 0x35f50`**. The type-4 handler loads **`[r4-20] = record+4`**, exactly the producer's numeric window ID.

At `0x35f58` it calls `PM_GX_IsValidWindowID`. Invalid status goes directly to the next-item path at `0x35b7c`: no reset and no reply to the producer are shown. On the ordinary valid branch, `0x35fa8` calls the previously reviewed direct reset `0x31a74`. Its returned r0 is not tested; subsequent instructions calculate a display-label address, log, increment the local item index and process another item or return to receiving.

The range-check alternate at `0x35f68 → 0x3618c` also calls `0x31a74`, then rejoins logging at `0x35fbc`, again without inspecting its return. Given the reviewed validator's accepted range, this extra numeric branch is not evidence of another admitted ID range. Both branches are recorded to avoid skipping a visible continuation.

No acknowledgment/reply call is present in the selected type-4 handling path or its producer. A reply call visible in an incidentally captured **different** switch case must not be attributed to type 4. This scoped observation does not establish that no independent notification or acknowledgment exists elsewhere in the system.

## Reset can schedule another operation

The direct reset modifies window bookkeeping under the previously observed lock: fields are cleared or assigned defaults; the service-name field becomes the default marker and may be replaced by a configured name. These mutations do not by themselves destroy a graphics surface or restore focus.

It also saves the old record word at `+4` in r9. If that old value equals 1, it requests a copy with `PM_GX_GetWindowInfo` at `0x31c94`. A nonzero result simply returns zero from the direct reset. A zero result calls **`0x31730`** at `0x31d08` with window ID, the copied record, r2=1, r3=0 and five zero stack arguments. This is the specific call edge justifying the new helper capture.

For these arguments, the helper:

1. Can return zero early when `PM_GXDBG_IsSkipUpdateWindowInfo` returns 1.
2. Otherwise calls `PM_GX_SetWindowInfo`, propagating its nonzero result as a local -1 after warning/backtrace.
3. With the supplied zero optional flags, bypasses rectangle-allocation paths, builds a zero-initialized **64-byte type-2 message**, and fills it with the same window ID plus fields from the record/arguments.
4. Sends that message through **the same global queue handle** at `0x31830`. Enqueue success returns zero; failure warns and returns -1 after any applicable cleanup.

The direct reset then executes **`0x31d0c: mov r0,r5`**, where r5 was explicitly set to zero for this call, and returns. Thus the optional helper's status is discarded. The type-4 consumer in turn discards the direct reset's status. This yields two distinct evidence boundaries: type-4 processing can finish its selected local routine while a type-2 update is merely queued, and failure to queue that follow-up does not become the original producer's result.

The type-2 message carries update data, not a demonstrated completion acknowledgment for the original type-4 request. Its complete consumer and graphics provider effects remain outside this trace. No claim is made that every reset enqueues it: the old-state condition, `GetWindowInfo`, debug-skip branch and `SetWindowInfo` result all matter. Unknown provider internals and runtime scheduling remain additional conditions.

## Consequence for OpenCast's release contract

The host lifecycle's [`release_window` adapter](../prototypes/native/lifecycle.h) must report actual success: [the core](../prototypes/native/lifecycle.c) clears `window_owned` on a zero result and may then unregister its parent resource. Mapping that result to `PM_GX_ResetWindowInfo`'s queue acceptance would prematurely certify cleanup. Mapping it merely to return from the direct reset is also unsupported by this evidence because status can be suppressed and further work can remain queued.

A valid binding therefore still requires an independently verified, service-bound completion condition, with deadline/error handling and proof that dependent resources are no longer held. No such adapter or private-method invocation is implemented here. Surface release, callback quiescence and physical return remain separate obligations; neither the numeric reset nor a later UI log is accepted as their proof.

## Reproduction and experiment

Run `PYTHONPATH=. python3 artifacts/native-window-reset-completion/capture_verify.py`. Verification checks **535 new words**, **108 direct branch/call targets** including incidental captured branches, all **235 reused producer/reset words**, dispatch arithmetic, payload offsets and exact queue-global equality. The four import bindings are checked against pinned relocation metadata. The selected-word budget is **16 words/entries**: four explicit literal/table words plus the twelve words of four PLT stubs. Other literal-pool bytes already inside disassembly windows are retained as data, not followed into their targets. Only one technical string was read: a 96-byte window retaining eight bytes including NUL. Captures and hashes are in the ignored manifest; no live memory or credential data was read.

Experiment WINDOW-RESET-001: **Objective:** distinguish reset enqueue acceptance from actual window cleanup. **Hypothesis:** the consumer and its return handling reveal whether a request has an acknowledgment or further work. **Environment/procedure:** unchanged selected procmgr, reused reviewed producer/reset, five targeted windows and four PLT bindings, bounded metadata and raw-word verification. **Expected:** a concrete consumer/completion edge or an exact unresolved dispatch boundary. **Observed:** type-4 dispatch reaches direct reset, ignores its result, and may indirectly enqueue type 2 with suppressed status. **Conclusion:** queue acceptance cannot satisfy the host release contract; final graphics completion is unproven. **Risks:** confusing a log or numeric-ID reset with owned-resource release, or generalizing the absence of an acknowledgment beyond the examined paths. **Next:** independent review passed; any follow-up must separately define a type-2 completion or independent ownership-verification scope. No automatic tracing expansion, firmware execution, TV/network/IPC, state changes or Git operation occurred.
