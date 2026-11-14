# Experiment log

All dates are 2026-11-14 unless noted. Report observed results, not intended outcomes. Raw local network/device evidence stays under ignored artifacts/.

## Latest local workstream index

- FW-003: [controlled firmware extraction](firmware-extraction.md#experiment-fw-003), verified EPK2 header and 77 selected segments; unchanged originals.
- LZ4P-001: [kernel and RELEASE decoding](lz4p-analysis.md#experiment-lz4p-001), exact reconstruction with valid uImage/CramFS CRCs.
- BOOT-001: [startup and ABI map](boot-dependencies.md#experiment-boot-001), firmware ARM32 EABI5 and explicit init chain.
- NATIVE-001: [native interface inventory](native-interfaces.md#experiment-native-001), symbol metadata only; no vendor code execution.
- INPUT-001: [combined input protocol](input-probe-v2.md), client and server ready locally; no new TV session.
- Independent [tool review](tool-review.md): five reproduced defects fixed, six additional regressions passed.

Latest completed integrated validation at this point: 63 Python tests passed in the optional firmware venv, and 16 JavaScript tests passed. Later partition-parser work has its own tests pending inclusion in the next integration run. Reports remain in ignored artifacts/firmware-lab/integration-tests.txt and artifacts/probe/client-tests.txt. No commits, push, pairing, native invocation or firmware changes accompanied this validation.

## ENV-001 — development environment and Git

- **Objective:** establish a usable, reproducible host workspace and preserve owner history.
- **Hypothesis:** installed ARM64 tools are sufficient for initial research without legacy SDK installation.
- **Environment:** macOS 26.6.2 ARM64; Python 3.13.5, Node 22.16.0, Apple Clang 17. Existing OpenCast-UI folder, initially empty.
- **Procedure:** inspect tools and instructions; attempt Git/DNS/network operations; resume after the owner changed permissions; fetch the supplied remote and inspect its tree before establishing the local baseline.
- **Expected result:** editable project, known tools, upstream history preserved.
- **Observed result:** initial sandbox denied .git/socket operations and terminal DNS. Full-access restart enabled Git/public network. Local main now tracks the owner's existing initial commit; its GPLv3 LICENSE is unchanged. No new commit or push. See artifacts/diagnostics/host.json for the later host snapshot.
- **Conclusion:** standard-library development is viable without installing dependencies. Claude Code is installed but not authenticated at the initial check; no Claude task was run.
- **Risks:** overwriting owner files or confusing inherited agent permissions with the resumed root session. File ownership was split and upstream files reviewed.
- **Next step:** review/test changes before any future commit; fetch again and enforce the owner's identity.

## NET-001 — bounded target discovery

- **Objective:** identify the owner's TV without sweeping unrelated devices.
- **Hypothesis:** the LG advertises UDAP and a DLNA renderer over SSDP.
- **Environment:** active Mac interface en0 on the owner's private /24 LAN; target powered on. Current addresses are in ignored diagnostic captures.
- **Procedure:** two M-SEARCH datagrams, TTL 1, one UDAP rootservice and one MediaRenderer query, four-second receive window each. No automatic descriptor fetch and no port/address sweep.
- **Expected result:** a response that can be matched to the supplied model/firmware.
- **Observed result:** initial resumed attempt failed with EHOSTUNREACH despite a multicast route. After the owner reported local-network permissions enabled, a retry returned both service advertisements from one host. UDAP reported exact model 47LA620S-ZA, firmware 04.28.17 and Linux/3.0.13.
- **Conclusion:** CONFIRMED target communication and self-reported identity. Precise cause of the transient OS/network failure is not established. No router changes were made.
- **Risks:** unauthenticated advertisements and possible discovery notification on the TV. No state-changing request was sent.
- **Next step:** read only the advertised descriptors of the model-matched target.

## NET-002 — service descriptions and connectivity

- **Objective:** verify the reachable protocol surface without pairing or control commands.
- **Hypothesis:** advertised descriptions are readable and expose a useful service inventory.
- **Environment:** target identified by NET-001, same private LAN.
- **Procedure:** HTTP GET of the two advertised LOCATION URLs, followed by two ICMP probes. Read the UDAP descriptor once more to retain bounded raw evidence and inspect its service-name attributes; parse the stored response offline thereafter.
- **Expected result:** descriptor XML with model/services and basic connectivity.
- **Observed result:** both descriptors HTTP 200. UDAP: netrcu, mobilehome, smartText, AppToApp. DLNA: ConnectionManager, RenderingControl, AVTransport. Ping: 2/2 replies; 4.050–7.694 ms RTT. Raw XML and reports in artifacts/diagnostics/.
- **Conclusion:** M1 communication is verified. Service availability is not authorization/compatibility proof for every API. Linux/i686 in the DLNA banner is not hardware identification.
- **Risks:** untrusted XML/URLs, accidental capture of unique identifiers. HTTP scope, proxy/redirect policy, body/XML limits and local-only artifacts constrain this.
- **Next step:** physical browser probe; review exact API semantics before paired queries.

## FW-001 — official firmware triage

See the full objective, hypothesis, environment, procedure, expected/observed results, conclusions, risks and next step in [firmware.md](firmware.md#experiment-fw-001).

Outcome: official original retained and hashed; one selected EPK copied with CRC verification; metadata suggests MTK5398/M13. No partitions, ELF ABI, init or recovery chain identified yet. FW-002 explains the detection-path discrepancy; actual container type remains unverified.

## TEST-001 — host validation

- **Objective:** exercise security/resource boundaries and initial navigation before device execution.
- **Hypothesis:** malformed input and denied destinations produce bounded failures while valid input remains usable.
- **Environment:** Python 3.13.5 / Node 22.16.0; synthetic fixtures; loopback HTTP only.
- **Procedure:** run unittest discovery, Node's navigation tests and a JavaScript syntax check. Test private-IP scope, redirects, proxies, XML/SSDP validation, deadline interruption, structured HTTP failures, archive limits/CRC/paths, static asset allowlist, report schema/origin/peer rejection and D-pad boundaries.
- **Expected result:** all tests pass, without contacting the TV.
- **Observed result:** 27 Python tests and 3 JavaScript tests passed; probe.js syntax check passed. A server startup dependency on reverse DNS was removed and the suite rerun successfully.
- **Conclusion:** the tools pass these host checks. No inference about TV rendering speed or input compatibility follows.
- **Risks:** limited synthetic coverage; HTTP peer restriction is based on IP, not authentication. Server serves no private content or control endpoints.
- **Next step:** HW-001 on the physical LG.

## HW-001 — original-browser Hello World

- **Objective:** display and navigate our code on the physical TV, then return normally.
- **Hypothesis:** a lightweight HTTP page can run in the integrated browser without firmware changes.
- **Environment:** approximately 8 KiB static probe, local server bound to the Mac LAN address and accepting only the target TV IP. No external assets or native control calls.
- **Procedure:** [owner-assisted test protocol](hello-world.md). The owner performed the test and subsequently confirmed returning to the Smart menu with Home; the server is now stopped.
- **Expected result:** visible heading, original-remote input, optional capability report, ordinary exit and repeatable reload.
- **Observed result:** two TV reports received at 11:29:23 and 11:29:36 UTC. UA advertises WebKit 537.4 / Chrome 22.0.1229.79. Viewport 1276×603. Canvas2D, JSON and XHR true; unprefixed rAF and NetCastBack/Exit false. Actions increased from 2 to 4; keydown count stayed zero. Owner reported pressing OK and interacting. Both reports measured 25 ms for script initialization, not network load or painted-frame time. The owner then confirmed that arrows move a cursor inside the browser, while outside the browser NetCast cards move directly with the arrows. Remote type was described as possibly Magic Remote, not verified. After initially deferring exit/reopen because URL entry is slow, the owner pressed Home once and confirmed return to the Smart menu. Reload was not requested again. The exact host server process was then stopped and its exit verified.
- **Conclusion:** browser code and local reporting work on the target during the owner-assisted session. Direct D-pad delivery to this page is not demonstrated in the current browser mode; normal Home exit is owner-confirmed, while repeatability and broader essential-function checks remain unverified. Complete M3 acceptance is therefore pending.
- **Risks:** temporary interruption of viewing; browser may consume remote keys or lack features. Preserve normal Back/Home handling and avoid native APIs.
- **Next step:** record the exact owner observations, timing limits and failures; update compatibility without assuming fullscreen, GPU support or autostart.

## FW-002 — detector/layout discrepancy

See [epk-format-notes.md](epk-format-notes.md) for the full reproducible experiment and source/history references. No extractor was run. The current EPK3 heuristic accepts the observed version-field layout, so the four-byte EPK2 structure discrepancy is not a demonstrated detection blocker. Cryptographic/container validation is still pending.

### HW-001 layout follow-up, not yet served

Review found that the baseline card width excluded padding/borders and could wrap the third card. The next on-disk CSS uses border-box sizing and a compact layout for the measured603px viewport. Baseline assets/hashes are retained locally. The completed physical session used the original snapshot. Its server is now stopped; the next layout needs a separately coordinated run and physical verification.
