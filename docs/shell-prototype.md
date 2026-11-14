# OpenCast launcher prototype

Updated: 2026-11-14. Location: `prototypes/opencast-shell/`. Current visual revision: **landscape dock**.

**CONFIRMED (local):** a working static launcher with five sections, horizontal remote-focus navigation, pointer operation and local appearance preferences. **CONFIRMED (owner, APP-001):** the portal-packaged landscape dock renders on the physical TV and arrows/OK work; opening and movement are reported very slow. Native integration, quantified latency and successful-launch return remain pending. A lighter host candidate is now in development; it has not run on the TV. This is not an installed OS or verified autostart mechanism.

## Current design

The owner's reference changed the visual direction from a feature-card home screen to a quiet television launcher. The current UI has a full-bleed warm rolling-hills landscape, a selected-item title and one-line action hint at upper left, browser clock/date at upper right, a discreet section bar including **TV / HDMI**, and a compact horizontal dock near the bottom. The central landscape stays open.

The dock uses original semantic icons for Internet, Apps, Media, Live TV and Settings. It contains no commercial service logos or claims of installed streaming applications. In the current lightweight candidate, icon/SVG geometry stays fixed; selection changes color and keyboard focus adds an outline. The first physical baseline enlarged the selected icon and used shadows. Focus outlines are replaced by these visible treatments, not simply removed. Optional high contrast strengthens the treatment. Native-action failures appear as short contextual notices only after activation; long technical warnings and marketing copy are absent from the home view. Project branding and preview badges are absent from the television interface. Development status remains in repository documentation and the on-demand About view.

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

The original physical probe observed pointer-style arrows in the ordinary TV browser. This UI does not claim to change browser-level routing. If arrows remain consumed by that browser, pointer operation may work while physical D-pad control is still unresolved. The pure navigation module can be reused when a supported application/native input route is established.

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

## Verification

**CONFIRMED (local):** 19 Node tests pass, covering pure horizontal navigation, real event handlers, section memory, native activation, preserved system keys, missing codes, pointer focus behavior, hidden-control guards, disconnected capabilities, opt-in preferences, malformed stored records, storage errors and clock lifecycle.

Installed desktop Chrome rendered the actual local artifact through a DevTools pipe without a TCP debugging endpoint or an HTTP server. Device metrics were explicitly set to 1276 × 603 and screenshots captured exactly that region. Home, Inputs and Settings were inspected. All three documents measured 1276 × 603, with the dock at y=415–558 and the footer ending at y=584. There was no page overflow. The current README preview is the unedited Home screenshot from that run.

This validates desktop layout and host behavior only. It does not establish old-WebKit SVG rendering, TV performance, physical input delivery, native access or safe boot integration. Previous card-layout screenshots and measurements are superseded by this revision.

```sh
node --check prototypes/opencast-shell/navigation.js
node --check prototypes/opencast-shell/capabilities.js
node --check prototypes/opencast-shell/shell.js
node --test tests/test_shell_navigation.cjs
```

## Next physical experiment

- **Objective:** validate the landscape dock's layout and interaction on the actual TV through a reviewed reversible route.
- **Hypothesis:** static rendering is usable at the measured viewport; arrow delivery depends on the browser/application context.
- **Environment:** original TV/remote and a reviewed single-peer local asset route; no installation.
- **Procedure:** coordinate one useful owner session, open the launcher, exercise sections and focus, observe SVG/landscape rendering, try one in-memory appearance control, and return through the normal browser exit path. Remember remains off unless explicitly chosen.
- **Expected result:** readable icons/context, actual section changes, truthful unavailable-action notices and ordinary exit behavior.
- **Observed result:** the packaged baseline renders on the TV and arrows/OK work, but the owner reports slow opening and movement. The lightweight candidate has not run on the TV.
- **Conclusion:** desktop success justifies preparing the experiment, not declaring an OS replacement or completed physical milestone.
- **Risks:** transient browser state, image/compositing resource use, browser-consumed remote input and optional browser-only preference writes. No firmware/system setting is modified.
- **Return path:** native Back/Exit/Home remain unhandled; confirm the actual return during the coordinated session.
- **Next step:** review host exposure and combine this check with meaningful input/deployment work. Continue native input/graphics/boot research independently.


## Prepared single-peer deployment route

The host probe server now supports an explicit `--include-shell` option. It keeps the original probe at `/` and snapshots only seven allowlisted launcher routes under `/shell/`, including the current JPEG. Repository files, old images and directory listings are not served. The default server does not expose the shell. A loopback integration test checks every asset and denied paths; no LAN server or TV test was started for this change.

For a coordinated session, use freshly confirmed private bind/peer addresses with `python3 -m tools.probe_server --bind MAC_IP --allow TV_IP --include-shell`. The launcher URL ends in `/shell/` (trailing slash required). This only makes the prepared reversible test available; it is not native installation or proof of input compatibility. Stop the server with Ctrl-C after the session. The shell does not send probe reports or perform native TV actions.
