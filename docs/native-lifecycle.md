# Native lifecycle ownership core

`prototypes/native/lifecycle.h` and `lifecycle.c` implement an **OpenCast host-side model**, not an LG protocol, recovered struct ABI, registration client or native execution mechanism. The model follows the ownership goals in [native-entry-contract.md](native-entry-contract.md) while retaining the admission uncertainty in [native-admission.md](native-admission.md). In particular, it does not assume that a preexisting procmgr record is mandatory, nor that an independent process can access the framework.

The core has no allocation, library/header dependencies beyond its own header, clocks, threads, network, target syscalls, drawing or TV-control operations. It stores one instance's state and calls nine explicitly injected adapter operations. No vendor types, addresses, service names or numeric protocol values are encoded. Its enums are private model values and must never be serialized as a vendor protocol.

## Window ownership update

CONFIRMED (local host model, 2026-11-14): registration, window lease and surface now have separate acquisition stages and ownership flags. The [window consumer report](native-window-contract.md) distinguishes a framework identifier from graphics handles; the [window allocation report](native-window-allocation.md) demonstrates that a successful reply or accepted numeric ID need not establish a reservation or ownership. These findings justify the separation, not a usable platform adapter.

`acquire_window` may report success only after a future adapter establishes an independently verified service-bound lease for this instance. Its context retains the actual handle/identity and evidence; the core receives only the adapter's result. No LG methods, IDs, guessed structs, stock identity reuse or success-reply interpretation are implemented. The lifecycle order below is our ownership contract, not vendor startup ordering: the examined stock readiness can precede rendering initialization.

## Exact contract

1. The caller zero-initializes an `oc_lifecycle` object, then calls `oc_lifecycle_init` with a complete adapter, context and nonzero instance generation. Reinitialization is rejected. The context and callback destination must remain alive until all queued events are drained or cancelled; do not clear/reuse memory early.
2. `oc_lifecycle_admit` is an explicit declaration by the integrator that an independently verified execution route and framework access exist. The core cannot verify that declaration. `start` before admission has no adapter side effects.
3. `start` calls register, acquire window, acquire surface, announce ready, then request focus. Each successful acquisition sets its ownership flag. Failed acquisition must leave no newly acquired resource: the adapter must perform any private rollback before returning failure. Ready/focus are state changes, not separately acquired resources in this model.
4. Successful focus request leaves the model `OC_READY` with a pending request. Only a matching later focus acknowledgment enters `OC_FOCUSED`. Focus loss returns it to idle `OC_READY` and cancels a pending request. A subsequent explicit request can restore focus. Duplicate grants and readiness/start attempts are rejected.
5. Close cancels pending focus, attempts surface release, window release and unregister in reverse acquisition order, subject to retained-child dependencies, then requests an independent return acknowledgment. An admitted instance requests return even if setup failed before acquiring anything. A never-admitted instance closes locally as `OC_CLOSED`, without claiming restoration.
6. Successful request dispatch leaves `OC_RETURN_PENDING`. Only a matching positive return acknowledgment, together with no cleanup failures, enters `OC_RETURNED`. A negative acknowledgment, failed return dispatch or return timeout enters `OC_FAILED`. The future adapter must define what restoration evidence justifies the acknowledgment; the model cannot prove Home, HDMI/audio or input restoration.

All operation functions return zero for success. Any nonzero result indicates failure. The adapter owns actual handles in its context; the core owns only acquisition/attempt flags. It copies the operation table during initialization.

## Failures, cleanup and repeated close

A failure during register/acquire/ready/initial focus automatically initiates cleanup and return. Failure of a subsequent explicit focus request does likewise. Only resources acquired successfully by this instance receive cleanup calls. Each eligible release/unregister is **attempted at most once**, including partial initialization failures. Successful cleanup follows surface → window → registration. If surface release is unconfirmed, both window and registration remain retained and neither parent release is attempted. If window release fails, registration remains retained and unregister is not attempted. A parent skipped for this reason has an unset attempted flag; this is deliberate dependency retention, not an automatic retry opportunity.

The remaining independent return request still runs once. Its adapter must not implicitly revoke retained resources or rely on their destruction. If the platform cannot provide that independence, the binding cannot satisfy this contract and must not be connected. A positive restoration acknowledgment does not erase unresolved resource ownership.

Failed surface release, window release or unregister leaves the corresponding ownership flag set, records `cleanup_failed`, and prevents `OC_RETURNED` even if the return acknowledgment is positive. A retained flag means ownership is unresolved, not proof that the resource certainly still exists. There is no automatic retry that could double-release a resource after an ambiguous failure. The adapter/integrator needs a separately designed recovery decision for such cases.

`failure_stage` preserves the first failing stage. Later cleanup failures remain visible through `cleanup_failed`, `surface_owned`, `window_owned`, `registered` and the attempted flags. A retained parent is not recorded as independently failed if its release was never attempted. A startup failure followed by confirmed cleanup/return can reach `OC_RETURNED` while retaining its initial failure stage; that state describes restoration, not successful startup.

Repeated close during return-pending or after a terminal state returns `OC_OK` without new calls. Here `OC_OK` means the idempotent close request was accepted, **not** that an earlier cleanup failure disappeared. Inspect state and ownership flags for the actual outcome.

## Callback identity and serialization

Events carry both the externally assigned instance generation and an operation token. Each focus request and return request receives a new nonzero token, so a timer or callback from a previous focus request cannot satisfy a new request or abort a later return wait. Focus-loss notifications carry the latest focus token. Exhaustion fails closed instead of wrapping and reusing tokens. Generations must not be reused while callbacks from an old instance can exist.

The caller serializes all calls on one event loop. This API is **not thread-safe**: `busy` rejects synchronous reentrancy; it is not a mutex or atomic synchronization primitive. All calls made by an adapter back into the same live model during an operation return `OC_BUSY` without changing state. A future binding must queue synchronous vendor callbacks until the public call returns, or prohibit such delivery. Dropping a rejected inline acknowledgment would leave the operation unacknowledged. Wrong generations/tokens return `OC_STALE`; otherwise late callbacks after closing/teardown return `OC_BAD_STATE`.

Adapter operations are synchronous. Their implementation must enforce deadlines externally: this core cannot interrupt a blocking function. `oc_lifecycle_timeout` is a caller-delivered event for the particular pending focus/return token, not a clock, scheduling facility or hard real-time guarantee. A focus timeout initiates cleanup; a return timeout records failed restoration. This requires an event loop that can run timers after operations return.

## Obligations for a future platform binding

The independent review found no violation of the stated model contract, but identified obligations that the model deliberately does not implement:

- **Late focus grants:** rejecting a grant after close does not undo focus that the platform may already have assigned. The binding must define cancellation or restoration for that case, independently of the core's `OC_BAD_STATE` result. There is no focus-release operation or focus ownership flag here.
- **Atomic results and cleanup failure:** acquisition failure must leave no acquired resource. A platform that can partially succeed needs adapter-side reconciliation before reporting a result. Release failure may mean unresolved ownership. The current model retains all dependent parents and refuses `OC_RETURNED`; the binding still needs explicit reconciliation and a separate recovery decision. A returned status alone cannot prove that a service-bound lease exists or has been released.
- **Inline acknowledgments:** queue them until the public operation returns. `OC_BUSY` is rejection, not deferred delivery. Test an inline return acknowledgment explicitly in the eventual binding; otherwise restoration may occur while this model subsequently times out as failed.
- **Serialization and lifetime:** provide one serialized event loop, retain callback destinations until drained, and avoid instance-generation reuse. Neither the model nor the bounded review establishes concurrent or multi-instance safety. `unsigned long` token width differs between the host and ARM32 target; exhaustion fails closed, but token lifetime must remain part of binding design.
- **Internal progress states:** no public call returns in `OC_REGISTERED`, `OC_WINDOW` or `OC_SURFACE`. They are internal synchronous progress markers, not stable milestones that an external event loop can wait for. Reentrant operations during these stages return `OC_BUSY`.

## Historical independent bounded review (before window separation)

**This review covered the earlier seven-operation model, not the current nine-operation contract.** Its explorer has not been adapted or rerun for window ownership; the original positional adapter and cleanup invariants require review before reuse.

CONFIRMED (reported local synthetic review, 2026-11-14): the independent reviewer reran the nine host test groups and reported a breadth-first explorer covering **128 distinct states and 243,052 transitions**, without a counterexample to its stated invariants. The explorer exercised public calls, generation/token mismatches, callback flags, adapter failure combinations and reentrancy. It also rejected seven deliberately defective copies of the core. One missing cleanup invariant was discovered during these negative controls, added, and the exploration rerun; the result is bounded evidence, not a proof that the invariant set is complete.

The review used **one instance**, a **five-token exploration bound**, **single-threaded execution**, and **atomic, truthful adapter outcomes**. It did not model blocking, partial platform effects, generation reuse across instances, the ARM object or any real binding. Therefore its ownership equality invariant describes the synthetic adapter; real failed cleanup remains unresolved as documented above. No TV, IPC, vendor code or network was involved. The local review message is `collaboration/messages/to-codex-006.md` section 2; its ignored explorer is `artifacts/claude-native-review/explore.c` (reported SHA-256 prefix `c7e66a6f75efa846`). These local records are not redistributed as physical-device evidence.

## Host verification

```sh
mkdir -p artifacts/native-window-lifecycle
/usr/bin/clang -std=c11 -O2 -Wall -Wextra -Werror \
  prototypes/native/lifecycle.c prototypes/native/lifecycle_test.c \
  -o artifacts/native-window-lifecycle/lifecycle_test
artifacts/native-window-lifecycle/lifecycle_test
```

CONFIRMED (local, 2026-11-14): Apple clang compiled without warnings; **10 test groups passed**, covering all nine adapter failure stages. The groups exercise admission/arguments, successful focus/return and exact cleanup order, every startup failure, every cleanup/return-dispatch failure, simultaneous failures with unresolved ownership, stale generation/operation tokens, timeout isolation, reentrancy during every operation, and focus-request failure/token exhaustion. The synthetic adapter independently rejects any attempt to release a parent while a child exists. Tests include failed surface/window release followed by focus timeout, stale or late callbacks, return timeout, retained parents and no subsequent cleanup calls. They also verify repeated close, duplicate grants, post-close focus, and missing/negative return acknowledgments. The adapter is entirely synthetic and invokes no TV operations.

Independent review additionally passed 6,144 synthetic scenarios using a separate adapter and detected three deliberate defects: releasing a window with a live surface, unregistering with a live window, and accepting a clean return despite cleanup failure. These scenarios are bounded checks, not the historical state-space exploration or a physical validation.

Local ASan/UBSan execution did not complete. A trivial `int main(void){return 0;}` control reproduced the same nontermination under the same Apple clang sanitizer flags, while its normal build exited successfully. Both runs had bounded deadlines and only their own processes were terminated; the environmental cause is unknown. This is not a sanitizer pass or evidence attributing the stall to lifecycle code. The CI workflow now requests a separate bounded Linux sanitizer check; its result must be observed before claiming that validation.

## Historical object-only cross-compilation (before window separation)

```sh
/usr/bin/clang --target=armv7a-none-linux-gnueabi -march=armv7-a \
  -marm -mfloat-abi=soft -ffreestanding -fno-builtin \
  -fno-stack-protector -nostdinc -std=c11 -O2 -Wall -Wextra -Werror \
  -c prototypes/native/lifecycle.c \
  -o artifacts/native-lifecycle/lifecycle-arm.o
python3 -m tools.elf_inventory artifacts/native-lifecycle/lifecycle-arm.o
/usr/bin/nm -u artifacts/native-lifecycle/lifecycle-arm.o
```

**The identity below belongs to the earlier core.** The current window-ownership source was subsequently compiled and independently rebuilt as a separate3,344-byte object; see [current ARM build](native-lifecycle-arm-build.md). Neither object was linked or executed. Preserve the different source/artifact identities.

CONFIRMED (historical local): a 3,140-byte ARM32 little-endian EABI5 relocatable object, SHA-256 `9547a71d900776c76a35da8bbbebc642bc3bde5613b28dffd37d25dfda5a483d`, with no program headers, interpreter, dynamic dependencies or undefined symbols reported by the host tools. No target object was linked, executed or emulated. The compiler flags are inherited from the earlier bounded object experiment; they do not identify the TV CPU, validate a sysroot/libc/vendor ABI, or make this a launchable application. The native host test executable is separate from this ARM object.

## Historical experiment NATIVE-LIFECYCLE-001

- **Objective:** establish deterministic resource ownership and callback rejection before any native binding exists.
- **Hypothesis:** a small independent C model can verify cleanup and restoration semantics without inventing vendor API declarations.
- **Environment:** installed Apple clang on the development Mac; synthetic adapters only.
- **Procedure:** compile/run host tests with strict warnings; inject failure at every operation; compile the core separately to an ARM object and inspect metadata/undefined symbols.
- **Expected result:** no duplicate cleanup, unresolved ownership preserved on failure, and only explicit acknowledged return reaches the returned state.
- **Observed result:** all nine groups passed and an object-only ARM artifact was inspected. No target runtime validation occurred.
- **Conclusion:** the model is usable as a testable ownership boundary for a future adapter; its operations remain disconnected from the TV.
- **Risks:** adapter blocking, dishonest admission/return declarations, premature context destruction or guessed vendor semantics cannot be solved by the core alone.
- **Next step:** establish actual admission, callback threading, window ownership and teardown contracts before implementing an IPC/graphics binding. Keep stock services and Home unchanged.

## Experiment NATIVE-WINDOW-LIFECYCLE-001

- **Objective:** distinguish service-bound window ownership from registration and surface ownership without a platform binding.
- **Hypothesis:** explicit dependencies prevent parent cleanup while a child release remains unconfirmed.
- **Environment/procedure:** installed Apple clang, synthetic host adapters, strict warnings; test acquisition failures, each cleanup failure, ordered success, multiple failures, reentrancy, stale callbacks, timeouts and idempotent close.
- **Expected/observed:** ten groups pass, all nine adapter failure stages covered; failed surface release retains window and registration, failed window release retains registration, and a positive return acknowledgment cannot produce `OC_RETURNED` after cleanup failure.
- **Conclusion:** the disconnected host contract enforces these dependency rules. It does not prove a real lease, target ABI, admission, display or Home restoration.
- **Risks:** atomic acquisition outcomes, external deadlines, callback lifetime and independent return semantics remain adapter obligations. No new finite-state explorer was run for this unit; historical counts/hashes do not cover it. The subsequent [current ARM build](native-lifecycle-arm-build.md) separately records object-only validation.
- **Next:** independent code/scenario review passed; validate the separate Linux sanitizer job and adapt the bounded explorer only if it addresses a remaining question. No TV, IPC or vendor execution occurred. Current local test output and initial freeze hashes are retained under ignored `artifacts/native-window-lifecycle/`; independent review and sanitizer control evidence are under `artifacts/native-window-lifecycle-review/`.
