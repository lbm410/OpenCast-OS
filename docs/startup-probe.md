# Single-file startup diagnostic S001

## Purpose and evidence boundary

When this diagnostic was prepared, the owner reported a black screen after opening the LG-packaged LauncherTest USB application (APP-001). This does not establish that the HTML entry loaded, DRM entitlement succeeded, or the packaged runtime matches the ordinary TV browser.

Static inspection of the current shell found visible Home/Internet/clock placeholders before JavaScript, a solid CSS background fallback and no root reveal gate. Missing JavaScript, background JPEG or SVG support should normally leave some static text. This is an inference from source, not proof of behavior on this runtime. Renderer defects, unsupported parsing and packaged entry/entitlement failures remain hypotheses. The portal package's source assets matched locally; its protected manifest entry has not been independently decoded or validated.

`prototypes/netcast-startup/index.html` is a diagnostic replacement source, not a signed or USB-installable package. It contains a large **HTML LOADED** heading, teal background and white text before its sole inline script. Both legacy body color attributes and inline CSS provide the basic color treatment. No external CSS, images, SVG, fonts, native APIs, storage, timers or network requests are used. It does not reload, navigate, focus controls or cancel any input. There is no project branding in the TV page.

## Reading the screen

| Visible result | Supported conclusion |
| --- | --- |
| Teal screen and HTML LOADED | This diagnostic's HTML reached a visible rendering path. |
| JS LOADED | Its inline script executed through the first marker update. |
| WINDOW LOAD RECEIVED | The window load callback ran. This does not validate entitlement or native integration separately. |
| Keys/clicks increase | Those DOM events reached this document. Counts describe events, not unique physical presses. |
| Script errors increase | The installed global error handler received an error. Errors before it was installed, including script parse failure, may leave only the HTML marker. |
| Black screen | Inconclusive: entry resolution, entitlement, HTML loading and rendering must still be separated. |

Counters saturate at 999. Only a bounded numeric last key code and error line are displayed; no typed characters, message text, URLs, stack traces or field values are retained. Lifecycle counters use pageshow/pagehide only when supported. A pagehide update may never become visible before the surface closes; its absence is not evidence of a failed exit. All state is in memory and disappears on reload. Home/Back retain their original behavior; this page cannot guarantee the platform's return path.

## Proposed coordinated experiment

- **Objective:** separate application entry/visible HTML from inline-script and launcher-complexity failures.
- **Hypothesis:** a valid entry can render this self-contained document even if the richer shell encounters runtime incompatibility.
- **Environment:** target LG47LA620S-ZA, existing firmware; official App Test packaging, exact entry value to be confirmed first.
- **Procedure:** root integrator confirms the portal's downloadable-source mode and root entry `index.html`, packages this single file through the official workflow, inventories the generated package, and coordinates one bounded USB test with the owner. Do not substitute raw source for the portal package or modify the protected manifest. Observe the three startup markers, optionally press OK and one arrow, then return through Home. No automatic retry.
- **Expected result:** visible teal HTML marker, followed by script and load markers; input delivery remains an independent observation.
- **Observed result:** local Node fixture tests execute the actual inline script and verify marker stages, legacy fallbacks, uncancelled system keys, bounded counters and sanitized error display. No physical startup-probe result is claimed.
- **Conclusion:** locally prepared diagnostic only; not proof that the launcher runs as a NetCast application.
- **Risks:** reversible application launch may fail or remain black. Preserve the already coordinated Home return procedure; do not change system settings or firmware to force execution.
- **Next step:** if S001 renders, add external CSS, one script, then image/SVG separately while retaining a visible boot marker. If it stays black, prioritize entry/packaging/entitlement evidence before altering launcher graphics.

Host test: `node --test tests/test_startup_probe.cjs`. The fixture validates JavaScript behavior, not the legacy browser parser, CSS rendering, LG packaging or the physical television.


APP-001 subsequent result: after correcting the portal entry and explicitly re-uploading the source ZIP, the full launcher displays and arrows/OK work. S001 remains a fallback diagnostic, not the required next TV test and not a physically validated artifact. The current priority is performance comparison and native integration evidence.
