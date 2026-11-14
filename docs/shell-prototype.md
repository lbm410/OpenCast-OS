# OpenCast launcher prototype

Prepared: 2026-11-14. Location: `prototypes/opencast-shell/`.

**CONFIRMED (local):** a working static launcher with Home, Apps, Inputs, Media and Settings sections, bounded directional navigation, pointer operation and local appearance preferences. **PENDING:** execution of this artifact on the physical TV, native integration and actual input delivery in that execution context. This prototype is not an installed OS, an autostart mechanism or a replacement for the current NetCast launcher.

## Design and implementation

The interface uses an original OpenCast identity, a quiet landscape, translucent tinted panels, thin light borders, large text and a clearly outlined focused button. It follows the owner's requested restrained glass-like direction without relying on modern live blur. The generated static background is `assets/landscape.jpg`; its provenance is maintained separately by the integrator.

The main layout targets the previously observed 1276 × 603 browser viewport. A five-item navigation bar sits above a home introduction and two-column cards. Other sections keep the same navigation and use two-column cards. Appearance controls provide Mint or Amber accents and an optional high-contrast mode. All visible labels and source comments are English.

The code deliberately uses conservative JavaScript, ordinary buttons, CSS floats, fixed-size cards, static opacity and basic gradients. There are no dependencies, remote assets, network requests, native TV API calls, `backdrop-filter`, canvas effects, CSS animation or animation loops. The only periodic update is the browser clock, at most once per minute; it stops on page hide/unload and resumes on page show.

The 1280 × 720 landscape JPEG is about 97 kB compressed. One decoded 32-bit image is about 3.5 MiB before compositor surfaces or browser caches. The complete current artifact is approximately 121 kB on disk. Neither figure measures actual TV memory consumption. Static glass-like compositing may still have a cost on the old browser. Landscape motion remains absent until device measurements justify a separately reviewed implementation.

## Architecture

| File | Responsibility |
| --- | --- |
| `index.html` | Semantic buttons, static section content and truthful capability status. |
| `style.css` | Landscape layering, compact two-column layout and focus/accessibility styling. |
| `navigation.js` | Pure row/column and tab/content movement rules; exportable for host tests. |
| `capabilities.js` | Explicit native-operation boundary; all TV capabilities default to unavailable. |
| `shell.js` | Section changes, actual event handlers, local preferences and clock lifecycle. |
| `assets/landscape.jpg` | Static local background supplied by the integrator. |

All links are relative so the directory can be served intact beneath a reviewed route. It is intentionally separate from the existing input probe. The probe server's current routes must not be assumed to expose it automatically.

### Navigation and activation

Left/Right move across the section bar and select its section. Down enters the section's first card. Card arrows move within a two-column grid without wrapping across row edges. Up from the first row returns to that section's tab. Native Tab traversal is also supported: Down on a tab that received focus through Tab first opens that actual section.

Enter and Space use native button click activation. No keydown handler synthesizes a second action. Back, Home, Exit, missing key codes, unknown key codes and events targeted at unrelated elements are not consumed. The controller cancels only recognized arrow codes on its own controls. Native browser behavior therefore remains the return path.

The earlier physical probe demonstrated cursor-style arrows in the normal TV browser. This launcher does not solve or hide that limitation: if that browser still consumes arrow events, pointer buttons remain usable but physical D-pad control has not been established. The same navigation module can be reused after a supported application/native input route is verified.

### Native capability boundary

`OpenCastShellCapabilities.query(name)` always returns `available=false` in this version. `invoke(name, target)` returns a truthful unsuccessful result and explanation; it executes no TV action. Unknown capability names are also unavailable, including inherited object-property names.

The following operations are represented but disconnected: launching NetCast applications, selecting an input, browsing USB and browsing network media. Selecting these cards displays the missing capability. It never reports successful HDMI switching, opens a guessed native API, launches a commercial app, scans the network or accesses files.

HDMI 1/2/3 are proposed layout destinations, explicitly labeled undetected. They are not a verified inventory of this unit's ports, connection state or attached equipment. A future verified adapter must enumerate actual destinations and supported operations. The browser clock is local display data; no connection, tuner, playback or power status is inferred.

### Preferences and storage

Accent and contrast affect this page only. They initially remain in memory. The page performs no automatic storage write. Explicitly enabling **Remember my choices** stores only this small object under `opencast.shell.preferences.v1`:

```json
{"version":1,"accent":"mint","contrast":false}
```

On a subsequent load, stored content is limited to 256 characters, parsed only when JSON/storage are available, and checked for the expected version, allowed accent and boolean contrast. No stored value becomes HTML or a class name unless it matches the allowed choices. Corrupt or unsupported content is ignored. A blocked/quota-failing write keeps the page usable and tells the owner that appearance is for the current visit only. Turning remembering off removes only the namespaced key; it never clears other browser data. If removal fails, the UI keeps its saved-preference indicator on rather than claiming deletion.

Origin changes or `file://` browser policies may change preference availability. Host tests and desktop behavior do not prove localStorage support on this TV. No credentials, media history or device identifiers are stored.

## Local verification

Twelve Node tests in `tests/test_shell_navigation.cjs` passed. They cover pure grid/tab navigation, actual shell key handlers, native Enter activation without duplication, preserved system/unknown keys, inactive TV adapters, pointer actions, preference opt-in, validation, storage failures, removal scope and lifecycle timer cleanup. The fixtures exercise the real scripts with a deterministic DOM/storage model; they do not emulate the TV or certify browser compatibility.

Installed desktop Chrome rendered local temporary copies with the project's relative assets resolved to local files. No HTTP server or TV connection was needed. Home, Inputs and Settings were rendered at an actual inner viewport of 1276 × 603. Each document measured 1276 × 603; the shell ended at y=547, and the two-row Inputs/Settings content ended at y=471. Screenshots were visually inspected. The final full-height landscape treatment was also rendered and inspected after correcting the body height. These measurements establish only the tested desktop layout, not old-WebKit rendering or performance.

```sh
node --check prototypes/opencast-shell/navigation.js
node --check prototypes/opencast-shell/capabilities.js
node --check prototypes/opencast-shell/shell.js
node --test tests/test_shell_navigation.cjs
```

## Proposed next experiment

- **Objective:** evaluate this launcher layout and navigation through the least-risk verified execution route.
- **Hypothesis:** the static UI renders acceptably at the TV's measured viewport; physical arrow delivery remains dependent on execution context.
- **Environment:** a reviewed single-peer LAN asset route, original TV and remote; no system installation.
- **Procedure:** integrate a fixed asset allowlist for the complete directory, coordinate one combined owner session, open the prototype, exercise all five sections, observe focus/input behavior, test one in-memory appearance control and return through the normal browser control. Persistent browser preferences should remain off unless explicitly chosen during that session.
- **Expected result:** visible, readable cards and actual section changes, with unsupported native actions accurately explained.
- **Observed result:** PENDING; this artifact has not been deployed to the TV.
- **Conclusion:** desktop success supports preparing the experiment only. It does not establish M3 completion, native navigation, launcher replacement or boot integration.
- **Risks:** temporary browser/page state, image/compositing memory, remote events being consumed by the browser, and optional origin-specific browser preference writes. No TV firmware or system settings are changed.
- **Return path:** ordinary browser Back/Exit/Home; the prototype does not cancel these keys or replace their behavior. The owner confirmed Home return in the earlier probe, but this artifact requires its own observation.
- **Next step:** review host exposure and bundle this check with the next useful physical input/deployment session rather than requesting repeated small interruptions. Native graphics/input/boot dependency analysis continues independently.
