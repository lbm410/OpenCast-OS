# OpenCast OS — operational handover

Updated 2026-11-14. Full-access host session; work active. Conversation Spanish; engineering material English. Historical details stay in experiments.md and linked reports.

## Workspace and coordination

Root: `/Users/lucasbarrientos/Developer/OpenCast-UI`. Remote: `git@github.com:lbm410/OpenCast-OS.git`. Main was fetched and matched origin/main at `276d54d3a84e3d258a87f8ab5369ed1cc04ad896` before the newly authorized granular local commits. Owner history and GPLv3 LICENSE preserved. Check actual Git state; no push authorized. Exclusive author/committer: `lbm410 <lbm410@inlumine.ual.es>`, no coauthor/AI trailers. Fetch/check divergence and owner changes before each commit/push.

Read collaboration/status/ and new addressed messages. Claude acknowledged CLAUDE-001 and reported four actual read-only agents; final review pending. Codex integrates. Knowledge bundle/tools are being implemented under knowledge/ and tools/knowledge.py; consult its compact index when ready, then relevant concepts. Do not load all reports by default.

## Device and physical test

LG47LA620S-ZA; firmware04.28.17 matches owner/UDAP; displayed SDK03.05. Exact-target SSDP, advertised UDAP/DLNA descriptors and two pings succeeded. No sweep, pairing, privileged access or firmware write. Current LAN addresses are in ignored diagnostics; recheck leases.

HW-001 displayed code in the TV browser. Two reports: WebKit537.4/Chrome22, viewport1276×603, clicks and zero keydown. Owner confirms arrows move a browser cursor but navigate native cards outside it. Home returned to Smart menu. Direct D-pad, repeat launch and explicit HDMI/audio checks remain pending: M3 incomplete. All probe servers are stopped.

Owner requests consolidated high-value physical sessions, not small repeated interruptions. INPUT-001 v2 and the glass/landscape launcher are prepared locally, not tested on TV. Shell native actions are explicitly unavailable. See input-probe-v2.md and shell-prototype.md.

## Firmware evidence

- Historical EPK2:24 packages/118 segments. Header and77 selected segments verify against the community public key;41 unverified. No independent LG trust-root/runtime-enforcement claim. Originals0444 unchanged; hashes/provenance in firmware.md and firmware-extraction.md.
- Kernel uImage and LG CramFS CRCs pass. RELEASE identified: ARM32 little-endian EABI5,43 direct dependencies. Vendor loader `/lib/ld-linux.so.3`; libc/loader filenames2.12.2. Float ABI unresolved. No target code executed. See lz4p-analysis.md.
- inittab→rcS→rc.local→foreground lginit in bootmode=auto. No script respawn. Shipped sbin/init identifies sysvinit2.86, but actual PID1 selection unresolved. SquashFS/ext2-RAM remount mismatch unresolved.
- RELEASE couples to essential vendor/AV libraries. Home.swf manifest and DirectFB/SaWMan config found. Native input wrapper constructs service messages: native-interfaces.md. Registration/transport/authorization and safe coexistence unverified.
- Partition template:64 entries,20 pairs,one boot. No active-bank or fallback proof. Recovery unverified; persistent device changes still require specific approval and demonstrated recovery.

## Host validation and local evidence

Latest integrated run:68 Python tests pass in optional firmware venv;16 probe JS tests and12 shell tests passed separately. Review fixed report persistence, FIFO blocking, incomplete inventory reporting, resource amplification and contradictory ABI flags. See tool-review.md. Recheck after knowledge tools land.

Python3.13.5/Node22.16.0/Apple LLVM, arm64 macOS26.6.2. Crypto dependencies pinned in requirements-firmware.txt, isolated in artifacts/firmware-lab/venv. Lab unsquashfs is a verified host ARM64 tool, bounded offline list/cat only. No global installation.

Ignored evidence: artifacts/diagnostics/, artifacts/probe/, artifacts/firmware-lab/, artifacts/boot-triage/decoded/, artifacts/partition-analysis/. Vendor inputs: firmware/. Never publish firmware, keys, raw captures or private identifiers.

## Next

Integrate Claude review and OKF retrieval; finish granular commits without push. Continue static service/boot-supervision analysis while preserving RELEASE. Prepare one useful physical session when the execution/input route warrants it. Siri is deferred in backlog.md. Actual-TV responsiveness takes priority over effects; see performance.md.
