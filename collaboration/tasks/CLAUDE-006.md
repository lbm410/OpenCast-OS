# CLAUDE-006 — bounded explorer for explicit window ownership

## Activation and role

Deferred assignment: do not start before2026-11-14T15:00:07Z and only after the owner's quota pause has elapsed, the scheduled Codex message arrives and your actual runtime quota permits work. Keep the owner-selected model. No alternate sessions, quota workarounds or model overrides. Acknowledge the task before starting. Codex remains integration lead for this collaborative assignment; standalone handoff is a separate owner choice.

## Objective

Adapt the earlier bounded host exploration to the reviewed nine-operation native lifecycle contract, which now separates registration, window lease and graphics surface. This is a disconnected model: no recovered LG binding, TV action, target execution or physical-safety claim.

Read docs/native-lifecycle.md, prototypes/native/lifecycle.h/.c/lifecycle_test.c and artifacts/native-window-lifecycle-review/review.md if available. Prior128-state/243052-transition results covered the old seven-operation model and do not validate current code. The newer independent6144-scenario review and three mutation controls provide a useful baseline, not a full state-space claim.

## Exclusive writable scope

- tests/native_lifecycle_explore.c (new host-only explorer)
- docs/native-lifecycle-exploration.md (new concise method/results)
- artifacts/native-window-exploration/ (ignored)

All other files read-only, including production model/tests/workflow/knowledge. No commits/pushes. Report any production defect with minimal reproducer before proposing a fix; Codex will assign ownership. English technical writing, exclusive owner attribution. Scoped independent subagents are allowed with disjoint review artifacts, but do not duplicate the whole task.

## Required model and bounds

Use the real public C API with an independent synthetic adapter. State exactly the admitted assumptions: single instance, serialized calls, atomic truthful outcomes, bounded operation tokens and no target ABI/runtime. Keep separate external-resource bookkeeping so the model is not its own oracle. Failed surface release must retain window+registration; failed window release must retain registration; positive return acknowledgement cannot erase unresolved cleanup. Check parent-child safety, no double release, stale/late callbacks, timeout isolation, reentrancy rejection and first-failure preservation.

Clone contexts safely: copied lifecycle.context and adapter back-pointers must point to the cloned node, not another node. Canonicalize explicit initialized fields; never hash/compare C struct padding, pointer addresses or uninitialized bytes as semantic state. Include generation/token semantics without assuming host unsigned-long width is the ARM target width. Separate token-exhaustion tests from a small bounded exploration when necessary.

Set explicit finite state, transition, memory and execution limits; no unbounded search. Stop with a non-success/partial label if any cap is reached. Run host builds with strict warnings and deterministic output. Check a few deliberately defective copies in ignored artifacts to demonstrate that the stated invariants detect violations; do not mutate tracked production files or claim that mutation coverage proves completeness.

No firmware extraction, vendor binary/library execution or emulation, IPC, LAN/TV, credential reads, SDK installation or protected metadata changes. No automatic device recovery, root operation or takeover of vendor services is implied.

## Deliverable

Freeze source/report hashes and exact compiler commands, source identity, limits, explored-state/transition counts, stop conditions and negative controls. Distinguish passed scenarios, bounded exploration, untested assumptions and any environmental sanitizer limitation. Review current files rather than copying stale report numbers. Send a new numbered to-codex delivery and update your own status; do not keep an indefinite model-driven polling loop after delivery.
