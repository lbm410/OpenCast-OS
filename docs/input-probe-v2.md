# INPUT-001 — focused-control input probe

Prepared: 2026-11-14. Probe version: `input-001-v2`.

**Status: CONFIRMED (local implementation and host tests); PENDING (physical execution).** This is an instrument for researching input delivery in the ordinary NetCast browser. It is not a replacement launcher, packaged NetCast application or installed OS.

## Objective and hypothesis

Determine whether the TV browser delivers keyboard events when an ordinary HTML control has verified focus. H1: focus or listener coverage explains the missing arrows. H2: browser-level input routing consumes arrows even with a focused control. The earlier owner-assisted session received clicks and no `keydown` events, while the owner observed cursor movement. That baseline does not resolve H1 versus H2. See [the evidence and official input contract](input-routing.md).

## Environment and boundaries

Target: LG 47LA620S-ZA, firmware 04.28.17, ordinary browser. Previous device-reported viewport: 1276 × 603; user agent advertises WebKit 537.4 / Chrome 22. Reuse the original remote and the existing host server with its explicit LAN bind and one confirmed peer. Preserve baseline captures.

The page makes no native TV API calls, writes no browser preferences/storage, loads no external assets and sends only an explicit report to same-origin `/report`. It does not change inputs, TV settings, services or firmware. Only arrows targeted at the three large cards are consumed. Enter, Back, Exit, Home, unknown keys and all keys targeted at the focus controls retain their browser defaults.

The separate `Focus test button` is the primary experiment. The optional read-only input tests a different native control without requesting typed text. An old browser might still show its input UI; that behavior must be observed rather than assumed. Do not type credentials or personal text. The logger never captures text, input values, HTML or arbitrary element IDs.

## Procedure for the coordinated physical run

1. The integrator reviews server/schema compatibility, confirms current LAN addresses and starts the restricted probe server only when the owner is ready. Starting a replacement server is necessary because assets are snapshotted at startup.
2. Explain the temporary browser-page execution and normal return path. Reopen the existing browser page or use its ordinary refresh/history if available; do not require URL retyping when it can be avoided. Seeing `INPUT-001 / V2` confirms the new page loaded. A new UI in desktop Chrome is not physical evidence.
3. Click **Clear session** once. This resets only in-memory counters/timing and cancels an outstanding upload; previously saved Mac files are untouched.
4. Click **Focus test button**. Confirm that the yellow diagnostic line reports `Active element: focusButton`. The button's focus outline is separate from the selected card's background. If focus cannot be established, record that result and stop this comparison.
5. Press Left, Up, Right and Down once each, then OK once. Observe whether a pointer moves, focus changes, event counters increment or the focused button activates. No automatic success claim follows from a click.
6. Click **Save report** once and wait for the explicit saved message. The report includes the save click and its current active element; the bounded event tail preserves prior focus transitions. Do not treat the active element at upload as proof that it remained focused throughout the test.
7. Only if useful and coordinated, run a separate cleared session on the optional read-only field and repeat the arrow sequence. Save a separate report. Do not infer that text-field input routing also applies to cards.
8. Use **Reload probe** for the separate repeat-load check. It performs ordinary `location.reload()` on the current URL, cancels an upload, clears page state through reload and does not call native APIs. A reload is not a report save. Confirm that V2 reappears and the session counters restart.
9. Finish using the browser's normal exit control when ready. Home returned to Smart successfully in the earlier baseline; confirm this run independently if exercised. The `Return instructions` card only displays text and does not itself exit. HDMI/audio verification is a separate physical check.

## Expected and observed result

**Expected:** either physical arrow key events appear with the intended focus target, or pointer movement continues without keyboard events. `keyup` and `keypress` cover delivery paths omitted by the first probe. A missing `keypress` for arrows can be normal browser behavior and is not itself a fault.

**Observed locally:** 16 Node tests passed: three existing navigation tests plus 13 client tests covering capture/fallback delivery, native-click activation, preserved system keys, focus-control behavior, bounded records, privacy labels, clear/retry/timeout, failure paths and lifecycle cancellation. These use a deterministic fake DOM/XHR transport; they do not emulate NetCast, a remote control, layout or browser default activation.

An installed desktop Chrome headless render loaded an inline temporary copy through `file://`, without starting a probe server or contacting the TV. At an actual inner viewport of 1276 × 603, document dimensions were 1276 × 603, all three card top edges were y=115 and their bottom edges y=227, and the shell bottom was about y=483. A screenshot was inspected. This confirms the desktop layout fits without card wrapping or page scroll at that size; actual old-WebKit layout remains PENDING. Temporary render output is outside the repository, not physical-test evidence.

**Observed on TV:** PENDING. No V2 deployment, refresh, report, D-pad success, native input access or repeat-load result is claimed.

## Instrument behavior and report schema

The page attaches exactly one observer for each of `keydown`, `keyup`, `keypress`, `click` and `focus`. If `document.addEventListener` exists, all five use capture and no duplicate bubble observer is installed. Otherwise one `attachEvent` or property-based bubble path is used, with `focusin` normalized to `focus`. `captureEvents=false` records the fallback; a platform lacking `focusin` may not report focus transitions, although every other record and the visible line still sample `document.activeElement`.

Enter does not call an activation handler from keydown. Native button click is the sole activation path, avoiding a keydown-plus-synthesized-click double action. No synthetic instrumentation self-check runs in the physical page. The first large card counts activation; the focus button explicitly calls its normal DOM `focus()` after click so the experiment can verify the result.

The exact V2 schema extends the baseline fields:

| Field | Meaning / bound |
| --- | --- |
| `probeVersion` | Exact string `input-001-v2`. |
| `userAgent` | Browser-reported UA; server limit 1024 characters. |
| `viewportWidth`, `viewportHeight` | Current document viewport; not panel dimensions. |
| `loadMs` | Coarse elapsed time from the early inline timestamp to probe initialization; not full page load. |
| `keyEvents` | Alias of `eventCounts.keydown` for baseline comparison. |
| `lastKey` | Most recently observed keyboard-event code, zero if none. |
| `interactions` | Large-card actions and focus-button activations, including Save report and Return instructions; Clear resets it. Not a physical OK count. |
| `maxHandlerMs` | Coarse maximum observer work time before final diagnostic text rendering. Not input-to-photon latency or frame timing. |
| `features` | Baseline booleans `canvas2d`, `requestAnimationFrame`, `json`, `xhr`, `netCastBack`, `netCastExit`, plus `webkitRequestAnimationFrame`, `mozRequestAnimationFrame`, `captureEvents`. Detection only; no rAF or NetCast call is made. |
| `eventCounts` | Exact keys `keydown`, `keyup`, `keypress`, `click`, `focus`; saturated nonnegative integer counters. |
| `events` | Latest 16 records, in listener-entry order. Each has exact keys `type`, `key`, `target`, `active`, `phase`, `elapsedMs`. |
| `droppedEvents` | Number of oldest records discarded from the bounded tail. Counts still retain all observations up to saturation. |
| `activeElement` | Safe label sampled when the report is assembled. |

Event `type` is one of the five observed types. `key` is 0–65535 and zero for non-keyboard records. `target` and `active` are allowlisted control IDs or sanitized tag names, never field values or arbitrary IDs; labels match `[A-Za-z][A-Za-z0-9_-]{0,23}`. `phase` is `capture` or `bubble`. `elapsedMs` measures time since initialization or the latest Clear session. Counts and numeric timing fields saturate at 1,000,000,000. The server enforces an 8192-byte request bound and strict schemas for baseline and V2 separately.

A single report upload may be outstanding, with a five-second timeout. Clear, reload, `pagehide` and unload detach its callback, clear the timer and abort it. `pageshow` resumes observation for a browser history-cache restore. A successful upload cancels its timer. HTTP errors, unsupported JSON/XHR and exceptions are displayed without retry loops. Reports have no automatic physical-confirmation flag from the client; owner correlation remains necessary.

## Conclusions, risks and next step

If physical keyboard events arrive with verified focus, adapt navigation using that evidence. If arrows still move a cursor with zero keyboard events, H2 gains support only for this control and browser configuration. The documented packaged NetCast input contract remains a separate execution context.

Temporary page state can be lost on reload or exit, report saving changes focus, native controls may invoke browser behavior, and the 16-event tail can discard early samples. Save short experiments separately and interpret total counts alongside retained records. Normal exit remains available because system keys are not canceled. No recovery or persistent integration claim follows from this experiment.

Next: integrate the strict server schema, then coordinate one short physical run. Continue packaged-application availability and firmware input/graphics research independently. The destination remains a replacement shell with native D-pad interaction; this browser probe is evidence gathering.

## Reproduce local tests

```sh
node --check prototypes/netcast-web/probe.js
node --test tests/test_navigation.cjs tests/test_probe_client.cjs
```
