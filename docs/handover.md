# OpenCast OS — operational handover

Updated 2026-11-14. Conversation Spanish; code and engineering records English. This file is current operational state; chronology belongs in experiments.md and detailed evidence reports.

## Workspace and permissions

Root: `/Users/lucasbarrientos/Developer/OpenCast-UI`. Remote: `git@github.com:lbm410/OpenCast-OS.git`, branch main. Inspect actual Git state before integration. The owner explicitly authorized incremental publication on 2026-11-14 (D012); fetch and check divergence and concurrent changes before each commit/push. Author and committer exclusively `lbm410 <lbm410@inlumine.ual.es>`, without attribution trailers. Preserve owner history and GPLv3 license. Unfinished agent work stays uncommitted. Reviewed changes are published throughbf34028 (including the original ARM probe and segment reader); GitHub runs43600750961,43601838134 and43603431682 passed both Ubuntu matrix jobs. Check current divergence rather than assuming this remains HEAD.

Local static analysis and bounded diagnostics are authorized. Never execute extracted code. Reversible TV experiments need their mechanism/effects/return explained and physical coordination. Privileged/persistent/boot operations require specific authorization and verified recovery; no such procedure exists yet. A successful packaged app is not permission to modify boot or essential services.

## Physical device and observations

LG 47LA620S-ZA, owner/UDAP firmware04.28.17, displayed SDK03.05. Exact-target SSDP and advertised UDAP/DLNA descriptions were read; two pings succeeded. No subnet sweep, pairing, privileged access or firmware writes. LAN addresses and raw identifiers remain in ignored artifacts; recheck leases before directed access. No current probe server is intended to remain running: inspect processes before starting one.

- **HW-001, ordinary browser:** page displayed; reported WebKit537.4/Chrome22 and viewport1276×603. Clicks arrived, no keydown in the recorded reports. Owner says arrows moved a cursor, while native cards respond outside the browser. Home returned normally.
- **APP-001, official USB-packaged launcher:** first attempt stayed black; Home returned normally. After setting the relative entry `index.html` and explicitly re-uploading the source, the owner confirms the shell displays and arrows/OK work. Opening and movement are very slow. These simultaneous changes do not isolate the original cause.
- **Still pending:** Home return from the successful rendered build, repeatable timings, explicit HDMI/audio continuity, packaged engine identity/viewport. Do not transfer the ordinary browser's UA to the app or declare M3 fully complete.

The owner authorized formatting the identified BIOS pendrive once; subsequent replacement changed only the inspected app directory. It was read-back verified and ejected. Do not reformat as part of routine updates. Three portal downloads remain ignored: first valid layout/black screen, second nested app-ID layout rejected without copying, third correct layout/physical success. The source and portal inspector preserve opaque protected metadata; no DRM workaround or manual manifest editing.

## Implementation available

- Lightweight shell in `prototypes/opencast-shell/`: conservative JavaScript, static warm landscape, compact dock, no visible product branding. Native TV actions explicitly unavailable. PS5 covers commercial streaming; prioritize TV navigation, HDMI/audio and essential controls.
- **Performance candidate (not deployed):** fixed icon geometry, no full-screen overlay/shadows, cached DOM updates. A synthetic single Right event dropped DOM writes18→3 with the same focus count. This is not measured TV speed. Candidate ZIP: `artifacts/netcast-source/launcher-performance-source.zip`,214134bytes, SHA-256 `ebfb11cb8a4c8177fac95c9a9a07f5d71b14fcd22816491627f26404316e7ee9`. Preserve original source baseline. Desktop screenshot: `artifacts/performance-trial/home.png`.
- **Own native build (host only):** `prototypes/native-probe/` links a 648-byte ARM EABI5 executable with installed Clang/Rust-bundled LLD; independent rebuild and byte inspection agree. One RX image, non-executable stack declaration, no dynamic dependencies. No target execution or admitted starter. The stdout descriptor and actual ISA remain unverified; see native-probe-build.md.
- Source builder and bounded portal-package inspector; self-contained startup diagnostic; bounded UDAP pairing/inventory foundation tested only with host fixtures. No real pairing/commands have run.
- `prototypes/native/lifecycle.*`: disconnected C ownership model with admission declaration, reverse cleanup, generation/operation tokens and acknowledged return. Nine host test groups pass. Independent bounded review reported128states/243052transitions; limits and future binding obligations in native-lifecycle.md. No LG IPC implementation, native launch route or physical validation.

## Static platform findings

Read compact concepts via knowledge/index.md, then fetch relevant evidence. A graph link or metadata label is not a substitute for its caveats.

- Official EPK2:24packages/118segments; header and all segments verified against a community-distributed key with a failing negative control. Not an independent LG trust root, runtime verification policy or recovery proof. Original firmware hashes in firmware.md; originals read-only; no redistribution.
- Linux3.0.13 kernel; selected ELF32 little-endian ARM EABI5. Reviewed ARM attributes establish the base FP calling convention in18selected files (17permitv7-A/FP instructions, sysvinitv6KZ). Instruction permission is not a physical CPU measurement. Full symbol-version/library compatibility remains open. A later three-file Chromium check finds a VFP loader but base-PCS Chrome/libstdc++; Chrome requests /lib/ld-linux.so.3, not the adjacent armhf loader. No coherent second runtime is proven. See arm-abi.md and chromium-abi.md.
- Normal service list runs essential `RELEASE` with reboot policy and separate `fxui` Home.swf with respawn. SWUE has a separate list. Preserve RELEASE while mapping visible interfaces and AV/watchdog ownership. See service-supervision.md and app-lifecycle.md.
- Static bootloader trace appends `init=/sbin/init` only in the nfs branch; compiled defaults are not the unit's stored environment. Kernel code now establishes retained rdinit (including a conditional /init default), explicit init, then lginit and /bin/sh failure fallbacks. Active selection/PID1 remain unknown. See kernel-init-selection.md; do not present rcS/rc.local as the demonstrated ordinary boot path.
- Procmgr creates table entries after managed launch **and** through an outer message-dispatch fallback; inner lookup alone does not prove managed launch is mandatory. SCF uses D-Bus, and selected configs use local sockets. Active bus policy, peer authentication, window/focus contract and execution admission are unverified. See native-admission.md and native-bus-policy.md.
- The fxui consumer passes its framework window ID to EGL through callbacks. Process-ready is distinct from graphics-ready; stock Home identity must not be reused. Consumer teardown does not establish callback quiescence or physical restoration. The receiver/allocation report passed independent reproduction of15captures/4,484bytes: lookup may reserve bookkeeping; reply success and numeric validity do not establish ownership, and reset does not prove restoration. See native-window-contract.md and native-window-allocation.md.
- libscf imports D-Bus functions while declaring only libgcc/libc DT_NEEDED: a dependency-name graph cannot establish all symbol providers or real loader behavior.
- Partition template64entries/20pairs/oneboot; active banks, automatic fallback, recovery and physical memory/SoC inventory unresolved. Root access would not close these gaps.

## Active collaboration and ownership

Use collaboration/README.md and current status/messages; do not infer receipt from a written file. Claude actually acknowledged task002/003 at13:06UTC, reports its configured Fable5.2 unchanged, and launched one real dependency-graph subagent. It delivered the reviewed ABI reader and independent native-core review. Root integrated those as359bfa2 and141027b. Messages024–026 acknowledge results and request current graph/boot-review delivery. No model override, idle wake-up daemon or automatic background execution is claimed.

Current integration and ownership (2026-11-14, active session):

- Claude actually acknowledged038/039 after the owner restored the preferred Fable model and delivered012, CLAUDE-004. Independent review found an incorrect account-lookup failure branch, a decimal/hex offset error and overbroad negative claims; message041 returns the report for correction before integration. No device identity or account policy is inferred from that unreviewed report. Claude acknowledged and startedCLAUDE-005 at14:09UTC; messages041/042 request correcting004 first at its next work boundary.
- input_probe completed the original native probe (6d3e6fd) and is independently reviewing CLAUDE-004; platform_research independently passed the probe and window-allocation report; firmware_extract froze the latter and its captures. Only root integrates reviewed output.
- Earlier graph, ABI, boot, provider and execution-policy reports remain integrated with their recorded review limitations. Root owns shared docs/knowledge, tests and Git. No model override or idle wake-up mechanism is used. Runtime status/message files contain current acknowledgements and disjoint ownership.

Check new messages between work units. Finite mailbox helper: `python3 -m tools.collaboration_wait --recipient codex --after LAST_READ --timeout 30`. A file cannot awaken a session that ended.

## Validation and next work

Host: Apple Silicon macOS, Python3.13, Node22, Apple clang. Optional pinned cryptography environment: `artifacts/firmware-lab/venv`. Use only reviewed host tools for bounded firmware reads; never ldd or execute extracted binaries.

Earlier exact committed snapshot10c556d:285Python tests pass with optional cryptography/no skips,40Node tests,9host C groups,16knowledge concepts/63relationships and generated-view checks. GitHub-hosted run43600750961 passed both Ubuntu24.04 jobs (Python3.11 baseline and3.13crypto), including host C. No private firmware or TV access was needed. That earlier run excluded the then-uncommitted graph; see the later validation below and ci.md.


The exact clean10048b4 archive including the reviewed graph passes349Python tests with optional cryptography/no skips,40Node tests,9host C groups and knowledge/view checks. Published GitHub run43601838134 passed both Ubuntu matrix jobs and every required test step. That published snapshot predates the current native-probe and window/account work. A clean archive ofbf34028 passes360Python tests with optional cryptography/no skips,40Node tests,9host C groups and both knowledge checks; its new linked probe is independently rebuilt and inspected. Current pending assignments are listed above. The owner supplied the missing form evidence: no App Type selector in the New App Test form; broader issuer availability remains unresolved. Further static work should target a demonstrated contract rather than expand indiscriminately. Kernel init and Chromium ABI reports are already integrated. Consolidate the next physical comparison around baseline versus lightweight app, startup probe, D-pad/OK, normal exit and AV continuity. Do not interrupt the owner for isolated low-value tests. Native admission/graphics integration and recovery remain the critical path to the replacement OS.

Private evidence lives under ignored artifacts/ and firmware/. Do not publish firmware, keys, pairing data, raw captures or unique device identifiers.

## Native issuer and next owner session

LG historically documents Marmalade/Unity App Test uploads; current account/artifact availability is unproven (native-packaging-route.md). The 2013 emulator does not support C Native, so it cannot validate this route. Browser automation inventory returned no browser surfaces/host unavailable; no portal registration was changed. Root asked the owner asynchronously for the available New App Test application types without saving. Owner screenshot now confirms this New App Test form has no App Type selector and labels the upload Web App. Historical native-runtime choices are not exposed here; no form was saved. Consolidate subsequent portal packaging/USB and baseline-versus-candidate measurements; the performance source ZIP remains uninstalled.

Owner restored the preferred Claude model; actual acknowledgement and delivery012 are now present. Correction004 and follow-up005 are coordinated through the mailbox, with independent review before integration. No owner intervention is needed for these local tasks.
