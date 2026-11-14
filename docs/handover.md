# OpenCast OS — operational handover

Updated2026-11-14. Conversation Spanish; repository engineering records English. This is current operational state. Detailed evidence and chronology belong in the linked reports and experiments.md.

## Workspace, publication and boundaries

Root: `/Users/lucasbarrientos/Developer/OpenCast-UI`. Remote: `git@github.com:lbm410/OpenCast-OS.git`, main. Inspect actual Git state before integration; never assume a recorded commit is HEAD. Owner decision D012 authorizes incremental publication of reviewed work. Before every commit/push, fetch and check divergence/concurrent changes. Author and committer exclusively `lbm410 <lbm410@inlumine.ual.es>`; no attribution trailers. Preserve GPLv3, owner history and unfinished agent files. Raw firmware/captures, identifiers and credentials never enter Git.

Local static analysis and host development are authorized. Never execute/load/emulate extracted binaries. Bounded read-only diagnostics target only the confirmed TV. Reversible TV changes require explained effects/return and owner coordination. Privileges, persistence, boot/partitions/service-menu changes require specific authorization and independently verified recovery; no such recovery exists. A Web app or a future native process does not authorize replacing essential services.

## Physical state and owner availability

Target: LG47LA620S-ZA, owner/UDAP firmware04.28.17, displayed SDK03.05. Exact-target SSDP, advertised UDAP/DLNA descriptions and two pings succeeded. Addresses/raw identifiers remain in ignored artifacts/diagnostics/; recheck leases before directed requests. No pairing, real UDAP command, privileged access or firmware write has occurred. No probe server is intended to remain running; inspect before starting one.

- Ordinary browser probe rendered and received clicks. Owner says arrows moved a cursor; Home returned normally. Reported WebKit537.4/Chrome22, viewport1276×603 applies to that browser only.
- Official USB-packaged launcher rendered and accepted arrows/OK after setting relative `index.html` and explicitly re-uploading. Opening/navigation were very slow. Initial black-screen attempt returned through Home; those simultaneous packaging changes do not isolate its cause.
- Pending: Home return from the successful rendered build, repeatable timings, packaged engine/viewport and explicit HDMI/audio continuity. M3 is not fully validated.
- Owner explicitly cannot test now and will try later. No physical session is scheduled. The earlier availability question is superseded; do not ask for isolated low-value tests or act on USB/portal/TV meanwhile.

The owner authorized formatting the identified BIOS pendrive once. Do not reformat during routine updates. Three private portal downloads document initial black-screen layout, rejected nested layout and later physical success. Preserve protected metadata; no fabricated manifest, DRM workaround or payload substitution.

## Implementations and validation

The unbranded landscape shell is `prototypes/opencast-shell/`, conservative JavaScript and local static assets. Native TV actions remain unavailable. PS5 covers commercial streaming; prioritize responsiveness and essential TV functions.

Performance candidate remains **not deployed**: `artifacts/netcast-source/launcher-performance-source.zip`,214134bytes, SHA256`ebfb11cb8a4c8177fac95c9a9a07f5d71b14fcd22816491627f26404316e7ee9`. It reduces synthetic single-Right DOM writes18→3; this is not TV speed. It needs fresh official packaging and inspection before a coordinated comparison. Preserve baseline; use docs/performance.md for the consolidated session, including normal exit and separate AV checks.

`prototypes/native/lifecycle.*` is a disconnected nine-operation ownership model: registration→window lease→surface, dependency-preserving cleanup and independently acknowledged return. Failed surface release retains window/registration; failed window release retains registration. Positive return acknowledgement cannot erase failed cleanup. Ten host groups and the independent6144-scenario/three-mutant review pass. No vendor binding exists.

A separate original648-byte ARM executable probe links and rebuilds reproducibly; the current lifecycle core separately compiles to a3344-byte ARM relocatable object. Neither has run on the TV. See native-probe-build.md and native-lifecycle-arm-build.md; compiler attributes do not identify physical ISA or supply admission/output/exit channels.

Exact code snapshot06afc97 passes373local Python tests with optional crypto/no skips. GitHub run43607643070 passes both full Ubuntu jobs, including Node, host C, knowledge checks and Linux ASan/UBSan in the crypto job. It fixes the observed cleanup-before-500response race; the earlier failed run is preserved in docs/ci.md. Mac sanitizers stalled even on a trivial control; do not claim a Mac sanitizer pass. Later documentation-only snapshots require their own knowledge checks, not invented target validation.

## Latest evidence and critical gaps

Use knowledge/index.md for bounded retrieval, then inspect the relevant report. Metadata/hashes are not factual review.

- Selected firmware: Linux3.0.13, ARM32 little-endian EABI5 and base FP argument PCS in18selected files. Per-library/physical CPU/runtime compatibility remains unresolved. Chromium's adjacent VFP loader is not a coherent second runtime. See arm-abi.md, chromium-abi.md and hardware.md.
- Essential RELEASE has reboot policy; separate fxui Home has respawn. Kernel/direct initializer candidates are statically traced; live PID1/boot bank/command line and recovery remain unknown. See kernel-init-selection.md, service-supervision.md and recovery.md.
- Initializer research now connects an exact pathname call to execve and its process gate to clone with fork-style flags. Conditional child/PID/error paths are identified; callbacks/helpers, an unread callback gap, argument/environment validity and runtime success remain open. See static-execution-callee.md and static-process-gate.md. No boot modification follows.
- Native type/path conversion and account-name→numeric setter attempts are traced. Lookup fallback rejoins creation; prefix passwd enumeration and GID-then-UID attempts do not prove effective credentials. See native-execution-gates.md and process-account-contract/provenance.md.
- AppInfo sample-support implementation has a checked client status, static method/handler pair and a three-global-word predicate. No live values/writers or active dispatch were established. Protected fallback and current native issuance remain separate. See sample-support-policy.md and appinfo-provenance.md.
- Current owner screenshot exposes Web App upload and no App Type selector. Historical Marmalade/Unity entitlement is documented; exact LG-target artifacts/current issuer are unavailable in evidence. Do not ask the owner to search for the same missing control. See native-runtime-artifacts.md and native-packaging-route.md.
- SCF/policy/state and window allocation traces distinguish record insertion, numeric IDs, conditional reservation, actual surface creation and restoration. The independently reviewed type-4 reset consumer ignores direct-reset status and can schedule a further type-2 update with suppressed failure. Queue acceptance is not a release completion condition. Active authentication, service-bound ownership, provider ABI, callback quiescence and successful Home/AV return remain unresolved. See native-bus-policy.md, native-window-allocation.md and native-window-reset-completion.md. No stock ID/path impersonation or private IPC is authorized.

The critical path is an evidenced native admission mechanism plus compatible graphics/input ownership and independent recovery. More host code does not establish any of these by itself.

## Concurrent collaboration and next work

Codex remains integration lead; standalone docs/claude-kickoff.md is a backup only. Read collaboration/status/codex.md, status/claude.md and newest addressed messages. Mailbox creation is not receipt. The quota timer delivered049 at15:00:06.976294UTC and exited; it is not an active relay. Claude actually acknowledged resumption and delivered006 through017/018, then acknowledged050. Retain the owner-selected model; no quota workaround or automatic restart is implied.

Claude owns only `tests/native_lifecycle_explore.c`, `docs/native-lifecycle-exploration.md` and ignored `artifacts/native-window-exploration/`. Its first delivery is **not integrated**: independent review found vacuous exhaustion testing and lossy canonicalization that accepted defective cores. Message052 requests revision with those exact negative controls, bounded reentry and resource/report fixes. The reported135states/983784transitions must not be promoted as validating those missing checks. Review evidence: artifacts/native-window-exploration-review/. Keep author changes out of commits until re-reviewed.

Codex agents completed independent static reviews and five-document coherence corrections. The separately scoped reset-queue study in docs/native-window-reset-completion.md passed independent review: 535 new words / 108 targets, 235 reused words and four relocation bindings. No additional consumer or provider trace is currently assigned. Root owns shared docs/knowledge/Git; no remaining firmware slice is automatically authorized by an old task. After Claude's revision, independently validate source/limits/negative controls, then integrate appropriate bounded CI coverage. Continue useful host-only evidence work while physical testing is deferred.
