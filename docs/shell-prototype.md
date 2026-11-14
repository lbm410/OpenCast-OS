# OpenCast launcher prototype

Updated: 2026-11-14. Location: `prototypes/opencast-shell/`. Physical baseline: **landscape dock**. Current source: **undeployed lightweight candidate**.

**CONFIRMED (local):** a working static launcher with five sections, horizontal remote-focus navigation, pointer operation and local appearance preferences. **CONFIRMED (owner, APP-001):** the portal-packaged landscape dock renders on the physical TV and arrows/OK work; opening and movement are reported very slow. Native integration, quantified latency and successful-launch return remain pending. A lighter host candidate and source ZIP are prepared; neither has been deployed or run on the TV. This is not an installed OS or verified autostart mechanism.

## Current candidate design and physical baseline

The owner's reference changed the visual direction from a feature-card home screen to a quiet television launcher. The current UI has a full-bleed warm rolling-hills landscape, a selected-item title and one-line action hint at upper left, browser clock/date at upper right, a discreet section bar including **TV / HDMI**, and a compact horizontal dock near the bottom. The central landscape stays open.

The dock uses original semantic icons for Internet, Apps, Media, Live TV and Settings. It contains no commercial service logos or claims of installed streaming applications. In the current lightweight candidate, icon/SVG geometry stays fixed; selection changes color and keyboard focus adds an outline. The physical baseline enlarged the selected icon and used brighter fill/shadows as its focus treatment. Candidate High Contrast removes the background image and strengthens contrast; its TV effect remains unmeasured. Native-action failures appear as short contextual notices only after activation; long technical warnings and marketing copy are absent from the home view. Project branding and preview badges are absent from the television interface. Development status remains in repository documentation and the on-demand About view.

The local background is `assets/landscape-v2.jpg`; the original `landscape.jpg` is retained but is no longer loaded by the active stylesheet. The integrator maintains image provenance in [visual direction](visual-direction.md). The new JPEG is 1280 × 720 and approximately 188 kB compressed; one decoded RGBA image occupies approximately 3.5 MiB before compositor/browser copies. Neither compressed size nor static CSS establishes real-TV memory or performance.

There is no animation, moving landscape, live blur, `backdrop-filter`, framework runtime, external resource or per-frame work. The lightweight candidate removes shadows and the full-screen overlay; small dock/tab backgrounds retain static transparency. The browser clock updates at most once per minute and suspends on page hide/unload. Real-device measurements must precede adding motion.

## Files and boundaries

| File | Responsibility |
| --- | --- |
| `index.html` | Semantic buttons, original inline SVG icons, compact section/dock layout. |
| `style.css` | Static landscape, translucent dock, selected/focused treatments and contrast. |
| `navigation.js` | Pure horizontal movement and section-bar transitions, exported for host tests. |
| `capabilities.js` | Disconnected native capability boundary; every TV action remains unavailable. |
| `shell.js` | Actual focus/click handlers, selection context, page-local preferences and clock. |
| `assets/landscape-v2.jpg` | Current local landscape. |

Assets are relative so the directory can be served intact beneath a separately reviewed route. This artifact remains independent of the input probe. It makes no network request or native TV API call. The current probe server must not be assumed to expose the shell automatically.

### Input behavior

- Left/Right move across the dock without wrapping at its ends. The upper-left title follows selection.
- Up moves from the dock to its section tab. Left/Right on the tab bar select sections; Down returns to that section's remembered dock item.
- Native Tab traversal remains available. Down from a natively focused tab opens that actual section before entering its dock.
- Enter and Space use native button click activation. No keydown handler synthesizes a duplicate click.
- Back, Home, Exit, unknown/missing key codes and unrelated targets remain untouched. Only explicit arrow codes on current controls are canceled.
- Pointer hover updates the selected context without stealing keyboard focus or activating anything. Hidden section controls cannot trigger actions.

The original physical probe observed pointer-style arrows in the ordinary TV browser. APP-001 subsequently established owner-observed arrow/OK delivery in the official packaged application. These are distinct execution contexts: the shell does not change browser-level routing, and the ordinary browser's engine/viewport evidence does not identify the packaged engine. Host tests cover detailed navigation behavior; the owner's confirmation does not yet cover every focus, repeat or exit edge case. The pure navigation module remains reusable for a future verified native input route.

### Native actions and truthful status

`OpenCastShellCapabilities.query(name)` returns `available=false`. `invoke(name, target)` returns an unsuccessful result with a short explanation; it performs no native operation. Unknown and inherited-property names remain unavailable.

Internet/NetCast app launch, TV/HDMI selection, USB browsing and network media are represented as destinations but are disconnected. Clicking them displays that limitation. There is no simulated app launch, HDMI transition, playback, device scan or native file access. HDMI 1/2/3 are proposed layout slots and are explicitly described as unverified when selected, not a detected physical port inventory.

The clock/date come from the browser. No connection, playback, input or power state is inferred. The About view provides installation/integration status when requested.

### Appearance preferences

Accent and contrast initially live in memory. Explicitly enabling Remember stores only the following small, versioned record under `opencast.shell.preferences.v1`:

```json
{"version":1,"accent":"mint","contrast":false}
```

There is no automatic write. Stored input is capped at 256 characters and validated against the version, Mint/Amber allowlist and boolean contrast. Corrupt or unsupported values are ignored. No arbitrary stored value becomes HTML or a CSS class. Storage failures keep the interface usable and display a short notice. Disabling Remember removes only this project's key; failed removal keeps the saved-state indicator truthful.

No credentials, personal text or device identifiers are retained. Origin changes and `file://` policies can alter storage availability. Host tests do not prove localStorage support on the TV.

## Host verification and physical evidence

**CONFIRMED (local):** 19 Node tests pass, covering pure horizontal navigation, real event handlers, section memory, native activation, preserved system keys, missing codes, pointer focus behavior, hidden-control guards, disconnected capabilities, opt-in preferences, malformed stored records, storage errors and clock lifecycle.

Before APP-001, installed desktop Chrome rendered the landscape-dock baseline through a DevTools pipe without a TCP debugging endpoint or an HTTP server. Device metrics were explicitly set to 1276 × 603 and screenshots captured exactly that region. Home, Inputs and Settings were inspected. All three documents measured 1276 × 603, with the dock at y=415–558 and the footer ending at y=584. There was no page overflow. That baseline run supplied the unedited Home screenshot used for the README preview. These dimensions describe the desktop capture, not the packaged TV viewport.

Those desktop tests and captures alone establish host behavior/layout. Separately, APP-001 confirms owner-observed shell rendering and arrows/OK on the physical TV, with very slow opening and movement. It does not yet provide measured performance, complete SVG fidelity, packaged engine identity/viewport, native access or safe boot integration. Home return from the rendered build, repeatability and HDMI/audio continuity remain pending. Previous card-layout screenshots are historical.

The lightweight candidate has 19 passing shell tests. A host synthetic Right movement now performs three DOM writes instead of the baseline's eighteen; unchanged elements and duplicate focus callbacks are not rewritten. This is program-behavior evidence, not a TV latency percentage. Candidate desktop Home rendering was inspected at 1276 × 603; its private screenshot and source ZIP are recorded in [performance.md](performance.md). No physical improvement is claimed.

```sh
node --check prototypes/opencast-shell/navigation.js
node --check prototypes/opencast-shell/capabilities.js
node --check prototypes/opencast-shell/shell.js
node --test tests/test_shell_navigation.cjs
```

## Next physical experiment: PERF-001 candidate comparison

- **Objective:** compare the lightweight candidate with the slow, physically rendered APP-001 baseline and complete return/essential-function checks.
- **Hypothesis:** fewer redundant DOM writes and simpler painting reduce perceived delay; the contribution of either change is unmeasured.
- **Environment:** original TV/remote, official portal-generated USB package from the explicitly selected candidate source, reviewed through the same bounded package process. No firmware or startup integration.
- **Procedure:** coordinate one owner session; preserve the baseline, verify candidate root index.html/package contents, time opening until controls respond, perform ten isolated left/right presses and a short sequence, check OK/sections, then normal Home return and HDMI/audio continuity. Remember stays off unless explicitly selected. Do not infer speedup from entry-point corrections.
- **Expected result:** the interface remains readable and usable, with no duplicate navigation/activation and a confirmed ordinary return; performance may or may not improve.
- **Observed result:** the earlier packaged baseline renders and receives arrows/OK but is reported very slow. The candidate remains undeployed and has no physical result.
- **Conclusion:** application rendering/input are established for the baseline; candidate improvement, full M3 acceptance and replacement-OS integration are not established.
- **Risks:** temporary viewing interruption and app-rendering/resource costs. No privileged operation or firmware/system-setting change is part of the candidate.
- **Return path:** Home/Back/Exit remain unhandled by the shell. The earlier black-screen Home exit is confirmed; return from a successfully rendered build still needs confirmation.
- **Next step:** follow [PERF-001](performance.md) in a consolidated physical session, recording owner observations separately from host counters. Continue native admission/graphics/boot research independently.


## Alternative prepared single-peer browser route

The host probe server now supports an explicit `--include-shell` option. It keeps the original probe at `/` and snapshots only seven allowlisted launcher routes under `/shell/`, including the current JPEG. Repository files, old images and directory listings are not served. The default server does not expose the shell. A loopback integration test checks every asset and denied paths; no LAN server or TV test was started for this change.

For a coordinated session, use freshly confirmed private bind/peer addresses with `python3 -m tools.probe_server --bind MAC_IP --allow TV_IP --include-shell`. The launcher URL ends in `/shell/` (trailing slash required). This is an alternative browser experiment, not the packaged route demonstrated by APP-001. Its existence does not prove ordinary-browser arrow delivery or native integration. Stop the server with Ctrl-C after the session. The shell does not send probe reports or perform native TV actions.
