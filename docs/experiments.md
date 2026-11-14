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

## UI-002 — minimal landscape and dock redesign (host only)

- **Objective:** revise the shell to match the owner's quieter landscape-led reference.
- **Hypothesis:** a compact dock and discreet TV/HDMI selector improve visual clarity without continuous effects.
- **Environment:** local desktop Chrome, viewport1276×603, static local assets; no TV connection or HTTP listener.
- **Procedure:** replace large cards with a horizontal dock, generate an original warm hills background, render Home/Inputs/Settings and run the shell's actual-handler tests.
- **Expected result:** readable focus, no overflow, truthful unavailable native actions and preserved system keys.
- **Observed result:** inspected Home PNG is1276×603; agent measured no document overflow and rendered Inputs/Settings. Fifteen shell tests pass; the combined Node suite passes31 tests. New background is `prototypes/opencast-shell/assets/landscape-v2.jpg`; prompt/mode are in visual-direction.md.
- **Conclusion:** the desktop redesign is ready for owner review. No physical rendering, navigation latency, memory use or native integration is established.
- **Risks:** old-browser rendering and compositing cost remain unmeasured; background is static and no native control is invoked.
- **Next step:** consolidate this UI check with a valuable future physical input/deployment experiment.


## FW-004 — complete EPK2 signature coverage

- **Objective:** close the41-segment verification gap without extracting more vendor content.
- **Hypothesis:** every exact declared segment verifies against the supplied community public key.
- **Environment:** existing offline macOS lab and preserved official EPK; optional pinned cryptography dependency.
- **Procedure:** add bounded `--verify-all` mode, test signed synthetic fixtures and failure paths, run the full audit under the offline sandbox. See firmware-extraction.md for the command and report hash.
- **Expected result:** all declared signatures verify and a one-bit in-memory mutation is rejected, or fail closed.
- **Observed result:** header and118/118 segments verified; mutation rejected; input hash unchanged. Eleven firmware-lab tests passed. No additional packages extracted.
- **Conclusion:** exact signature coverage is complete relative to the supplied key. Publisher trust chain and runtime enforcement remain unresolved.
- **Risks:** interpreting key consistency as authority or boot compatibility; no device writes or target-code execution occurred.
- **Next step:** continue service/boot analysis using preserved inputs; do not infer recovery from signature success.


## APP-001 — owner reaches NetCast App Test registration

- **Objective:** determine whether the legacy official packaging route remains reachable.
- **Hypothesis:** the owner can register our source-only launcher through the Mac browser.
- **Environment:** owner-operated LG App Test page; source ZIP and icon prepared locally; no TV action.
- **Procedure:** owner opened New App Test, was given the verified launcher-source.zip path and a code-drawn256×256PNG icon (6337bytes), and subsequently supplied a detail-page screenshot.
- **Expected result:** registration detail and a downloadable DRM package, or an explicit service error.
- **Observed result:** screenshot shows LauncherTest, Web > All, the supplied icon and the Download DRM applied file section. Exact submitted entry value, terms acceptance and package download are not yet verified. CP Option Information contains Progress95%; no processing percentage is inferred.
- **Conclusion:** registration UI is reachable; end-to-end packaging and TV execution remain pending.
- **Risks:** confusing a detail page with valid packaged content or working device entitlement. No firmware or TV state was changed by the agent.
- **Next step:** owner reviews terms and downloads if accepted; inspect the resulting local archive with bounded metadata reads before coordinating USB execution.


### APP-001 package download follow-up

- **Procedure:** inspect the owner-downloaded ZIP with bounded metadata/member reads and compare launcher assets to local source; prepare a new fixed-allowlist USB staging tree.
- **Observed result:**222489-byte ZIP,14entries,240501expanded bytes; all six source assets unchanged; four generated icons, developer.test and an opaque NCGFILE_HEADER manifest added. Hash and limits are recorded in app-deployment.md.
- **Conclusion:** portal package download is demonstrated. Manifest semantics, entitlement and physical launch remain pending.
- **Risks:** treating packaging success as device compatibility. No target code executed or removable media modified.
- **Next step:** inspect an owner-supplied USB drive without formatting, then coordinate a reversible TV test.


### APP-001 authorized USB preparation

- **Objective/hypothesis:** prepare the official package in the documented USB directory structure for a reversible application test.
- **Environment/procedure:** owner explicitly authorized formatting the connected BIOS pendrive. Rechecked the sole external physical USB drive's identity/size/volume, formatted FAT32/MBR as OPENCAST, copied the fixed inspected package file set and read every file back.
- **Expected/observed:** twelve files totaling240501bytes match the package; disk ejection succeeded.
- **Conclusion:** removable media is prepared; TV discovery, entitlement, input and return remain untested.
- **Risks:** formatting removed prior USB contents as explicitly requested. No TV state or firmware was changed.
- **Next step:** owner-coordinated TV USB discovery and application launch.


### APP-001 first physical packaged launch: black screen

- **Objective:** determine whether the portal-generated launcher renders on the target TV.
- **Environment/procedure:** owner connected the prepared USB and reports opening the application. No agent-issued TV command.
- **Expected result:** launcher landscape and controls, followed by remote/return checks.
- **Observed result:** owner reports a black screen immediately after opening. Elapsed duration, error messages, Home return and submitted portal URL are not yet known.
- **Conclusion:** application selection is owner-reported, but successful page load/rendering is NOT established. Candidate causes include entry/manifest configuration, entitlement/runtime loading and rendering compatibility; none is confirmed.
- **Risks:** repeated blind retries or treating this as a firmware failure. Requested a short bounded observation, then normal Home return if still black. No update, forced power cut or privileged operation proposed.
- **Next step:** collect Home/error and exact portal URL observations; audit source startup and documented package-entry requirements in parallel.


### APP-001 return and registration-field inspection

CONFIRMED (owner-reported): the screen remained black and Home returned normally to the Smart home screen. No reboot or forced power removal was reported. CONFIRMED (owner screenshots of Modify): URL field appears blank, Web subtype displays --Select--, Developer CP Service is checked, and the uploaded file tree contains index.html. These edit-form values do not prove exactly what the previously generated opaque manifest contained. LG's deployment guide, printed page8, requires a relative HTML entry path for a downloadable ZIP and explicitly excludes http:// for this mode. Next controlled correction: set URL to index.html, Web subtype All, CP unchecked; save and download a new package, then compare and replace only the app directory on USB. Physical launch must be repeated before attributing causality.


### APP-001 revised package layout failure

- **Objective:** verify the regenerated package before USB replacement.
- **Procedure:** inventory the new owner download, compare it with the original package and recheck source ZIP layout.
- **Expected:** index.html directly beneath the single app-ID folder.
- **Observed:** the first package's12files are unchanged inside a second app-ID directory; the new outer level has only a manifest and developer.test.
- **Conclusion:** the revised output does not satisfy the intended index.html entry layout. Portal/input cause unknown.
- **Risks/actions:** no USB replacement or TV retry performed; do not manually flatten or alter protected metadata.
- **Next:** explicitly re-upload original source ZIP through LG, inspect root entry and regenerate.


### APP-001 source re-upload and corrected USB package

CONFIRMED (local): the next owner download is196778bytes, SHA-256 `d348ae50f8e059449fee3d3569b0a9df490c44f5cfe4f708ef2479777b2d42d2`. Its10ZIPentries contain a single app-ID directory, assets directory and8files totaling215044bytes. index.html is directly under the app root; all six launcher source assets match byte-for-byte. The new protected manifest is retained intact. This output contains no separate generated icon files; do not invent or patch protected metadata to add them.

The existing USB app's12files matched the prior verification report. Additional AppleDouble sidecars were bounded and recognized before removal. Only the app folder was replaced, with a temporary rollback directory during copying; all8new files were read-back verified. Cleanup handled macOS automatically removing paired sidecars when deleting their data files. The rollback directory was removed and disk ejection succeeded. No formatting occurred. The verification report is ignored artifacts/netcast-source/usb-copy-v2-verification.json. Next: owner repeats launch and observes rendering, remote navigation and Home return. Successful TV execution remains pending.


### APP-001 corrected packaged launch: visible shell and native remote delivery

- **Objective:** repeat launch after correcting entry path and re-uploading the original source ZIP.
- **Observed (owner):** the interface now displays, arrow navigation works and OK works. Owner reports both slow application opening and slow movement. No quantified latency or load duration was provided. Home successfully exited the previous black-screen attempt; return from this successful launch is still awaiting confirmation.
- **Conclusion:** official packaged execution and D-pad/OK delivery are physically established for this build. Responsiveness is unacceptable by the owner's assessment; this is not an OS/boot replacement or performance success.
- **Next:** reduce redundant DOM updates and variable selected-icon geometry, simplify painting, compare the same navigation workload. Keep the packaged source baseline for reproducibility. Continue static native integration separately.

## NATIVE-STATIC-002 — reviewed native foundations and init selection

- **Objective:** narrow the execution/ABI boundary before proposing a native launcher binding.
- **Hypothesis:** declared ABI, process lifecycle and kernel execution order can be established independently with bounded static tools and synthetic host tests.
- **Environment:** preserved official firmware, Apple Silicon host, reviewed readers; real Claude session plus disjoint Codex research agents.
- **Procedure:** integrate the79-test ARM reader; review the native C ownership model; independently trace kernel parameter slots and fallback calls; inspect three Chromium-tree ELFs after finding an armhf filename.
- **Expected result:** exact static contracts and explicit remaining runtime questions.
- **Observed result:**18selected core files declare base PCS; the separate armhf loader declares VFP while Chrome and adjacent libstdc++ declare base. Kernel code supports retained rdinit/early-init, explicit init, then lginit and shell fallbacks. Nine host C test groups pass; the independent reviewer reports a bounded128-state/243052-transition explorer without an invariant violation. See arm-abi.md, chromium-abi.md, kernel-init-selection.md and native-lifecycle.md for evidence/limits.
- **Conclusion:** native build planning and startup architecture have stronger evidence; no native TV process or startup replacement has been executed.
- **Risks:** interpreting build attributes as measured CPU features, compiled fallback as active PID1, or synthetic cleanup as actual TV restoration. All remain distinguished.
- **Next step:** review the declared-dependency graph and identify missing graphics/IPC providers; establish an actual reversible execution and window-ownership contract.

### Host integration regression: descriptor ownership

- **Objective:** prevent repeated invalid local inputs leaking file descriptors in ELF readers.
- **Hypothesis:** wrapping an opened directory with fdopen can raise before a context manager takes ownership.
- **Environment/procedure:** Claude reported a five-call directory leak; root inspected both open paths in elf_inventory, moved regular-file validation before fdopen, and closed descriptors if validation/wrapping fails. Synthetic regressions cover repeated directory rejection and injected fdopen failures in direct reading and tree sniffing.
- **Expected/observed:** descriptors are closed after rejected inputs; five ELF review tests pass and valid-file inspection still works. Claude owns the equivalent ARM-reader correction separately.
- **Conclusion:** resource cleanup is now explicit in the shared ELF reader; no firmware data or runtime behavior is changed.
- **Risks/next step:** preserve normal ownership transfer and rerun the combined frozen suite after both reader fixes. No TV action.

## NATIVE-STATIC-003 — USB-test provenance and provider gates

- **Objective:** connect the discovered native dispatcher to the actual USB-test metadata route and identify its acceptance boundaries.
- **Hypothesis:** native classes survive conversion but require earlier provider acceptance and later execution conditions.
- **Environment:** pinned official appctrl and individually selected upctrl; bounded host-only disassembly and independent review.
- **Procedure:** trace list/storage/path mapping, provider callbacks, XML type write, account metadata, execution checks and manifest-provider handlers. Review source ELF words, branch targets, literals and import relocations independently.
- **Expected result:** a connected path with explicit gates, or a demonstrated disconnection.
- **Observed result:** USB-test list4/storage3 joins provider-mediated parsing and native conversion. XML app_type writes parsed+0x28; examined native classes select game metadata. Upctrl first attempts AppInfo, then a protected downloaded fallback that checks the named verifier and read results. AppInfo availability/provenance, real account and native issuer remain unresolved. Independent review of the two later reports matched24captures/10088bytes,2522ARM words,483branch targets,20relocations,24literals and two method records. See native-manifest-admission.md, upctrl-manifest-gate.md and native-execution-conditions.md.
- **Conclusion:** the native path is connected statically, but our ELF has not been admitted or executed.
- **Risks:** treating metadata, a zero return, an account label or a verifier name as full authorization, effective privilege or live-device behavior.
- **Next step:** trace AppInfo provenance and the supplied execution-policy flag; verify current official native-runtime submission availability. No device operation occurred.

### CI-001 — published checks on GitHub

- **Objective:** reproduce host validation outside the development workspace.
- **Hypothesis:** reviewed source and synthetic fixtures suffice without private firmware or device access.
- **Environment/procedure:** clean Git snapshot10c556d locally, then GitHub run43600750961 with Python3.11 baseline/Python3.13 optional crypto, Node22 and host C.
- **Expected/observed:** local285Python tests pass without skips,40Node tests and9C groups pass; both hosted matrix jobs and knowledge/view checks pass.
- **Conclusion:** published host checks are reproducible in these environments; no TV compatibility or speed conclusion follows.
- **Risks/next step:** keep private artifacts and target execution out of CI; validate the next reviewed graph implementation before publication.

### NATIVE-STATIC-003 follow-up: AppInfo policy boundary

The next six captures (1532bytes), independently reproduced by root, restrict AppInfo lookup to storage3/nonzero app ID and a successful sample-support query with a nonzero output. No producer was identified in immediate references. Vendor CP Box wording does not establish the owner's device class or correspond to the portal checkbox. See appinfo-provenance.md. This narrows the branch; no device behavior or new execution permission follows.

### LINKAGE-001 — reviewed dependency graph

- **Objective:** distinguish inspected dependency-name candidates from listing-only evidence.
- **Hypothesis:** a bounded declared-dependency graph reveals missing inspections without claiming loader/symbol compatibility.
- **Environment/procedure:** real Claude/subagent implementation, synthetic fixtures, fixed19-file firmware sample and seven listings; independent root/reviewer execution.
- **Observed:**64graph tests pass; review caught and corrected rejected-file byte accounting, unencodable text and contradicted listing-link matches. Independent pathname-race/same-descriptor tests pass. Root full suite passes349tests with optional crypto/no skips. Fixed sample has241NEEDED edges,10interpreters,105names,9inspected candidates and96listing-only names. See native-linkage.md for category limits.
- **Conclusion:** dependency evidence is reproducible; it does not establish dynamic linking, native admission or physical execution.
- **Risks:** name matches or listing sizes can mislead; contradictions remain explicit and imported/dynamically loaded providers may be undeclared.
- **Next:** use only the needed provider contracts after selecting a permitted entry route.

The independent reproduction initially stopped at its frozen documentation hash after root's two wording corrections; substituting only the reviewed report hash in memory made all synthetic checks pass. Tool/test hashes were unchanged. The original ignored reproduction is preserved.

### NATIVE-STATIC-003 follow-up: execution-policy producers

Eight exact captures (2964bytes) establish XML prohibit and update-completion record fields as producers of the execution rejection bit. Concrete callers select lists2/3, not USB-test list4; they do not directly compare native app_type. Independent review matched741ARM words,159branches,14literals and8relocations. See native-execution-policy.md. No device setters were called; native permission, initial USB-test state and ultimate policy authority remain unproven.

### ISSUER-001 current account-form observation

- **Objective/hypothesis:** check whether the current New App Test form exposes the historically documented native-runtime choices.
- **Environment/procedure:** owner opened New App Test on the Mac and supplied a screenshot; no form submission requested.
- **Expected:** an application-type selector or evidence it is absent in this form.
- **Observed:** no App Type selector; the upload area explicitly says Web App.
- **Conclusion:** historical Marmalade/Unity choices are not exposed by the observed UI. This is not proof of every backend/account capability or a firmware-wide native ban.
- **Risks/next step:** avoid treating Developer CP Service as a firmware flag or altering protected metadata. Preserve the Web baseline; research a concrete native entry contract independently.

## ELF-SEGMENTS-001 — reusable program-segment evidence

- **Objective:** make already-parsed program headers available to a separate native-probe artifact checker without copying the ELF parser.
- **Hypothesis:** an additive segments field preserves reader behavior and lets the caller distinguish loadable regions, zero-fill and declared permissions.
- **Environment/procedure:** synthetic ELF32/64 fixtures in both byte orders; existing bounded reader; independent review.
- **Expected/observed:** four new tests and77existing reader/review/graph tests pass. The first explicit module invocation omitted the legacy tests fixture directory and failed one import; PYTHONPATH=.:tests resolved that runner issue without source changes. Standard discovery already handles it.
- **Conclusion:** metadata is now reusable. Reporting flags does not establish W^X, entry reachability, loader validity or effective device permissions. No vendor/target program was executed.
- **Risks/next step:** preserve the caller's independent artifact checks and resource limits; use this for the separately built native probe.

## NATIVE-PROBE-BUILD-001 — first locally linked native probe

- **Objective/hypothesis:** close the object-to-executable build gap with installed host tools and original minimal source, independently of native admission.
- **Environment/procedure:** Apple Clang plus installed Rust-bundled LLD; reviewed ELF/ARM readers; assemble/link twice, inspect entry segments/instructions, compare further root and independent reviewer builds. No installation or target execution.
- **Observed:** identical 648-byte ARM EABI5 executable, SHA-256 d351176fb1a1942fef5d5156b2bc0605c7b2e2be93c8751fd26a4067a9251d63. One RX image, non-executable stack declaration, no dynamic dependencies. Seven contract tests pass; independent byte/header review matches the two-syscall design.
- **Conclusion:** local linking is demonstrated, not device compatibility, admission or native UI execution.
- **Risks:** inherited stdout can block, signal or point to an unintended sink; bounded output does not imply bounded runtime. Host-tool output limit is checked after capture. See native-probe-build.md.
- **Next:** establish a legitimate starter with known output/exit observation before any device experiment.

## NATIVE-WINDOW-001 — framework identifier and EGL consumer

- **Objective/hypothesis:** determine whether framework window ownership and graphics readiness are separate contracts.
- **Environment/procedure:** existing selected fxui/libafopenapi; 19 bounded captures totaling 8,024 bytes; independent review against original ELF bytes.
- **Observed:** framework window ID passes to EGL; stock Home has a separate binding; ready precedes rendering in inspected paths. Callback tables connect EGL initialization/termination, but external scheduling/quiescence and Home restoration remain unproven. Independent review matched 2,006 ARM words, 480 branches and 188 PLT annotations.
- **Conclusion:** a future adapter needs distinct process-ready, graphics-ready, window ownership and return handling.
- **Risks/next:** do not reuse Home identity or copy unchecked cleanup; trace the window allocator and receiver next. No device operation occurred.

## NATIVE-WINDOW-002 — receiver reservation and reset

- **Objective/hypothesis:** distinguish ID lookup from allocation and graphics-surface ownership.
- **Environment/procedure:** selected procmgr;15 bounded captures/4,484bytes and bounded method-table reads; independent reproduction from original ELF.
- **Observed:** generic GetWindowID can reserve service-name bookkeeping; reply boolean and numeric-range validation are separate from ownership. CreateWindow's examined handler does not create a GAL surface. Reset has direct/queued branches but complete exit-to-reset and restoration are unproven.
- **Conclusion:** a future adapter must track reservation separately and cannot infer ownership from a successful response. See native-window-allocation.md.
- **Risks:** misclassifying a private method as read-only, borrowing a stock identity, or equating record reset with restored video/input. No TV/IPC or target execution occurred.
- **Next:** resolve admitted entry first; if pursuing the graphics contract, follow the demonstrated reset queue consumer and EGL provider boundary without invoking them.

## ARM-BRANCH-001 — reproducible direct-target review

- **Objective/hypothesis:** make distant branch targets and backward rejoins explicit without attempting automatic control-flow recovery.
- **Environment/procedure:** reviewed ELF/range reader, fixed A32 encoding decoder and primary Arm references; synthetic fixtures plus a read-only existing procmgr slice.
- **Expected:** exact signed target arithmetic and declared limitations on instruction state, literal data, conditions and indirect branches.
- **Observed:**12 new tests pass; independent oracle agrees for10,023 synthetic words across three bases, including address wrap. Maximum64KiB slice yields16,384candidates and2,786,241JSONbytes below4MiB. The actual selected480-word slice includes both the conditional target and previously missed backward rejoin.
- **Conclusion:** repeatable target indexing is available; it does not establish runtime reachability or validate an account-policy interpretation. Full working-tree suite372Python tests passes with optional cryptography/no skips.
- **Risks:** literal data can resemble instructions, alignment does not establish ARM state and filesystem/stdout are not hard real-time bounded. Output repeats these limits.
- **Next:** use the index alongside independent argument/branch review for future bounded static reports. No vendor program, disassembler subprocess or TV operation was executed by this index.

## ACCOUNT-001/002 — corrected account-to-credential flow

- **Objective/hypothesis:** join account text to numeric fields and the child credential-call block without inferring runtime privileges.
- **Environment/procedure:** selected procmgr; original bounded captures, two independent reviews, corrected reports/annotations and root integration. No credential database was read.
- **Expected:** exact data provenance and branch/failure behavior, with unresolved identity/admission clearly separated.
- **Observed:** failed account lookup can format a fallback and rejoin allocation; GetID uses passwd enumeration and requested-name prefix comparison. The writer supplies numeric fields; the child attempts GID then UID setters independently when nonzero and does not abort this block on their negative return. Initial report errors in branch rejoins, comparison operands, pointer/table provenance and decimal offsets were caught before publication. Raw captures remained unchanged.
- **Conclusion:** the selected static writer chain is established. Mapping, attempted calls and live effective identity remain distinct; there is no native launch or privilege proof. Full details: process-account-contract.md and process-account-provenance.md.
- **Risks:** unobserved database/state, prefix/input reachability, ignored resolver/setter failures and remaining allocation/launch prerequisites.
- **Next:** native artifact issuer/admission and independently recoverable startup remain the integration questions; do not broaden credential searches or call private methods.

## ISSUER-002 — historical runtime artifact prerequisites

- **Objective/hypothesis:** identify whether historical runtime upload labels imply a public native build/deployment contract.
- **Environment/procedure:** original LG/Unity documentation and timestamped original-site Marmalade archives; independent source verification. No SDK or application binary acquisition/execution.
- **Expected/observed:** historical LG-target entitlement and a generic architecture-binary/platform-loader package model exist; exact NetCast2013 loader, archive and current issuer remain absent from this bounded search. Unity's source describes Union licensing/distribution. Independent archive retrieval succeeded with bounded HTTPS after the web tool failed.
- **Conclusion/risks:** historical availability is not current entitlement or model compatibility. See native-runtime-artifacts.md; do not install a generic legacy SDK to substitute for the missing target specification.
- **Next:** acquire a provenance-verifiable exact target specification/bundle only through an authorized available source; continue recovery and performance work independently.

## RECOVERY-ENTRY-001 — update mode versus independent recovery

- **Objective/hypothesis:** distinguish a separate update service set from an independently usable recovery environment.
- **Environment/procedure:** existing selected initializers; six bounded dynamic-lginit_app captures totaling3,440bytes, two mount tables and technical literals; independent byte/branch/PLT review. Static lginit metadata lacked the requested symbols; no pattern search followed.
- **Expected/observed:** update-mode configuration attempts the same procmgr path; dynamic phase selection bypasses its initial-preparation block. A32-byte formatting capacity is smaller than its42-byte service-list literal. Mount/exec failure handling does not demonstrate success or safe restoration. Review verified860words/205branches/35imports.
- **Conclusion/risks:** no independently verified recovery follows. Do not extrapolate this artifact's intended/truncated configuration to physical updater failure or assume static/dynamic initializers behave identically.
- **Next:** recover a separately justified static entry anchor and then trace only its evidenced phase boundaries. No TV operation or target execution occurred.

## STATIC-ENTRY-001 — symbol-independent initializer anchor

- **Objective/hypothesis:** use the declared ELF entry and demonstrated arguments to identify a narrowly justified startup candidate without a pattern scan.
- **Environment/procedure:** selected static lginit; one256-byte entry slice, mapped literals and comparison with primary glibc ARM start.S contract; independent review.
- **Expected/observed:** r0 receives0x82ac before a libc-style startup call;64words, three literals, two BL destinations and stack layout were independently checked.
- **Conclusion:** candidate main address is LIKELY; neither its body/extent nor startup-callee identity/library version or actual device boot was established.
- **Risks/next:** avoid importing dynamic-lginit_app boundaries or behavior. Further tracing must use a separate explicit candidate-range budget. No target execution occurred.

## NATIVE-WINDOW-LIFECYCLE-001 — explicit dependency-preserving ownership

- **Objective/hypothesis:** keep a window lease distinct from registration/surface, retaining dependent parents when child release is unresolved.
- **Environment/procedure:** original disconnected C core, strict-warning host builds,10test groups, independent6,144-scenario adapter and three mutation controls.
- **Expected/observed:** failed surface release retains window+registration; failed window release retains registration; positive return acknowledgement cannot erase cleanup failure. Normal and adversarial tests pass. A trivial ASan/UBSan control also stalled locally, so local sanitizer validation is unavailable; Linux CI check is requested, not yet claimed.
- **Conclusion/risks:** host contract is verified within stated assumptions, with no LG binding or physical restoration evidence. Atomic outcomes, callback lifetime, serialization and operation deadlines remain adapter obligations. Old128-state explorer is incompatible/historical.
- **Next:** observe hosted sanitizer result; deferred CLAUDE-006 may adapt bounded exploration after the owner's quota deadline.

## NATIVE-WINDOW-ARM-001 — current lifecycle object

- **Objective/hypothesis:** verify the changed original core still compiles independently of vendor headers/runtime.
- **Environment/procedure:** installed trusted Apple Clang with documented historical ARM flags; source/tool hashes before/after; reviewed ELF/attribute readers and llvm-nm; independent exact rebuild.
- **Expected/observed:**3,344-byte ARM EABI5 ET_REL, SHA-256 d8e890eb9d4ad01e3080f18780882d2d4774a63007877d09c5320e89eb884972, identical independent output and no reported undefined symbols.
- **Conclusion/risks:** compiler-target object build only; no linker, target execution, physical ISA or native admission proof. Keep this separate from the old3,140-byte object and minimal linked probe.
- **Next:** complete the legitimate entry and platform adapter contracts before any device experiment.

## STATIC-ENTRY-002 — initial static phase gate

- **Objective/hypothesis:** test whether the demonstrated static candidate shares the dynamic initializer's first phase selection.
- **Environment/procedure:** pinned static lginit;256-byte candidate prefix, five referenced words and two bounded technical strings; independent reproduction and branch/argument review.
- **Expected/observed:** zero static pointer literal causes fallthrough, unlike the dynamic nonzero pointer. APP_START reaches unknown callee0xbb78; its zero return branches to0x853c. Review verified64words,11targets and five literals without expanding scope.
- **Conclusion/risks:** an artifact-level phase distinction is confirmed; API identity, active boot and recovery are not. Do not infer environment semantics from a string or borrow dynamic function names.
- **Next:** separately bounded128-byte successor study; no TV action or target execution.

## STATIC-ENTRY-003 — preparation-shaped zero-return path

- **Objective/hypothesis:** inspect the reviewed zero-return successor for initialization/reexecution prerequisites.
- **Environment/procedure:** same pinned static initializer,128-byte successor, six referenced words, three bounded argument strings; independent exact reproduction and argument/branch review.
- **Expected/observed:** calls carry SWU_MODE=ON and LOCKUP_LEVEL=%d; two pointers are stored and a zero-return branch exits the slice. Verified32words,13targets and all six literals. Callees remain unnamed; reexecution is not shown.
- **Conclusion/risks:** initialization preparation is a hypothesis, not enforced success. Unknown returns cannot be labeled success/failure; preserved registers assume normal callee-save behavior.
- **Next:** separately justified successor continuation; no target execution or TV action.

## PROBE-PERSISTENCE-002 — cleanup before error acknowledgement

- **Objective/hypothesis:** explain the hosted baseline failure that observed a pending report file after an HTTP500response.
- **Environment/procedure:** synthetic loopback server, injected ENOSPC publication error, a handler reply-boundary observer and cleanup Event; no sleeps or model-driven retry. Compare original and minimally corrected code.
- **Expected/observed:** the old implementation deterministically sends500before unlink; the new regression detects the pending file at that exact boundary. Recording the error and replying after finally fixes the ordering. All16focused tests and the373-test local suite with optional crypto pass.
- **Conclusion/risks:** confirmed response-ordering race, not an assumed Python3.11 incompatibility. Cleanup failure itself, crash durability and external directory mutation remain outside this fix. No device/LAN action.
- **Next:** run the corrected snapshot in both hosted matrix jobs; retain the earlier Linux lifecycle sanitizer pass separately.

## STATIC-ENTRY-004 — pathname call and branch convergence

- **Objective/hypothesis:** close the two demonstrated successors and test whether the inherited pathname pointer reaches a call.
- **Environment/procedure:** same pinned ELF, a separately assigned40-byte tail, reused pointer and one bounded technical string; independent reproduction and branch/argument review.
- **Expected/observed:** both earlier alternatives converge at0x8580 if their calls return. A later unknown call receives /lg/lginit/lginit_app and zero; its result is overwritten before an unchecked repeating call. All10words/five targets verified.
- **Conclusion/risks:** launch/reexecution hypothesis now has an exact argument/call anchor; API identity, success and physical recovery are still unknown. A visible loop does not imply successful launch or known wait semantics.
- **Next:** stop slice expansion; propose a distinct callee-identity investigation with explicit evidence budget. No device or target execution.

## STATIC-EXEC-001 — explicit execution syscall behind the pathname call

- **Objective/hypothesis:** determine whether the initializer pathname call reaches an execution operation rather than an arbitrary pathname consumer.
- **Environment/procedure:** selected static lginit,256-byte callee window and approved124-byte wrapper extension; bounded literal/technical-string reads, Linux v3.0 primary ABI comparison and independent reproduction.
- **Expected/observed:** both selected routes reach SVC0 with r7=11 and filename/argv/envp arguments, matching ARM EABI execve. Verified95words/18targets; error normalization and the caller's saved-zero return are explicit.
- **Conclusion/risks:** an execution attempt is established statically. Initial process-creation gate, complete vectors, live environment and success remain unproven; an ignored returned error is not recovery.
- **Next:** separately scoped process-gate analysis, without executing firmware or modifying the TV.

## SAMPLE-POLICY-001 — implementation behind the AppInfo support query

- **Objective/hypothesis:** trace the exact imported sample-support query to an internal policy, rather than equating it with a portal checkbox.
- **Environment/procedure:** two previously selected ELFs, four symbol-bounded ranges totaling532bytes, ten PLT/relocation imports, technical-string arguments, an exact method/handler pair and independent argument/branch/storage review.
- **Expected/observed:** wrapper status1 gates output copying independently of support value; matching handler normalizes a three-global-word predicate. All133words/20targets verified. Sender outcomes are unchecked. A/C storage is file-backed and B zero-fill-only; no field values were read.
- **Conclusion/risks:** static policy shape is now explicit; active dispatch, live values/writers, metadata integrity and native admission remain unknown. ELF initialization and table adjacency are not physical-state proof.
- **Next:** separately scope policy producers or dispatch only if needed; no owner action, IPC or TV test now.
