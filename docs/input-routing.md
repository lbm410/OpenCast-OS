# NetCast input routing: application versus ordinary browser

Research date: 2026-11-14. Target: LG 47LA620S-ZA, firmware 04.28.17. This note records documentary findings and the current owner-assisted browser test; it does not establish a working packaged application or a replacement shell.

## Current evidence

| Status | Observation | Interpretation limit |
| --- | --- | --- |
| CONFIRMED (physically observed, owner report) | Arrow buttons move a cursor in the ordinary browser; native NetCast cards respond directly to arrows. | The behavior differs by execution context. The remote type and browser's internal routing mechanism are unverified. |
| CONFIRMED (device-reported) | Two probe reports contain zero received `keydown` events and four click-handler actions in the later report. | This does not prove that all keyboard event types are suppressed or that every element-focus configuration has been tested. |
| CONFIRMED (device-reported) | UA advertises WebKit 537.4 / Chrome 22; viewport is 1276 × 603; Canvas 2D, JSON and XHR are detected. Unprefixed `requestAnimationFrame`, `NetCastBack` and `NetCastExit` are absent. | Engine strings and feature presence do not establish access to native application APIs. Absence of two symbols does not establish absence of every NetCast symbol. |
| CONFIRMED (physically observed, owner report) | Home returned to the ordinary Smart menu after the test. | Reopening/reload and broader essential functions are still unverified. The server is stopped; no further owner action is required for this session. |

The ignored evidence files are `artifacts/probe/probe-20261114T112923-905140Z.json` and `artifacts/probe/probe-20261114T112936-136764Z.json`. Owner observations are recorded in the handover.

## What the official application documentation establishes

CONFIRMED (documentary): LG's application guide describes DOM key handling in LG Smart TV applications. Its traditional IR remote table maps Left/Up/Right/Down to 37/38/39/40, OK to 13 and Back to 461. The sample handles `keydown` on the document body. EXIT is reserved by the platform; several system keys, including Home and power, are unavailable to applications. The guide separately describes Magic Remote pointer activation, `mouseon`/`mouseoff` events and arrow-key behavior. These are application-runtime contracts, not proof that an arbitrary URL in the ordinary browser receives the same events. See [Developing Web App, printed pages 25–28](https://webostv.developer.lge.com/assets/netcast/NetCast-Developing%20Web%20App.pdf).

The documented pointer methods have narrower purposes than a browser input-mode switch:

| API | Documented purpose and limitation |
| --- | --- |
| `window.NetCastGetMouseOnOff()` | Reads Magic Remote pointer status as `on` or `off`; does not select an input route. |
| `window.NetCastMouseOff(time)` | Deactivates the pointer on NetCast 2.0 / 2011. LG explicitly states it does nothing on NetCast 3.0 and later. |
| `window.NetCastSetAutoMouseOff(control)` | Controls automatic pointer timeout using `enable` or `disable`; introduced in SDK 3.0. It does not document a switch from browser cursor emulation to DOM arrows. |
| `mouseon` / `mouseoff` | Proprietary events describing Magic Remote activation/deactivation. They are not commands. |

CONFIRMED (documentary): these descriptions appear in the [NetCast API guide, printed pages 28–33](https://webostv.developer.lge.com/assets/netcast/NetCast-API.pdf). Applicability and symbol presence in this TV's ordinary browser remain PENDING. No listed method was invoked for this research. The [official FAQ](https://webostv.developer.lge.com/more/netcast/netcast-faq) independently warns that `NetCastMouseOff` is ineffective from NetCast 3.0 onward and states that no SDK API activates the Magic Remote pointer.

RULED OUT (documentary, as a proposed fix): using `NetCastMouseOff` as a supported NetCast 4-era browser D-pad switch. PENDING: whether this particular ordinary browser exposes any documented user setting or JavaScript API that changes cursor routing. No such mechanism has been established in the reviewed official developer material. This is an evidence gap, not proof that no browser setting exists. Do not substitute webOS key-registration APIs or guessed NetCast names.

## Packaged context and availability are separate questions

CONFIRMED (documentary): LG documents an App Test workflow that DRM-packages a web application for USB deployment, with both downloadable and URL-based web application variants. A URL-based application launched through that workflow must not be equated with typing the same URL into the normal browser. LG also warns that including LG Inspector when remote debugging is not used can break Back/Home behavior and cause a freeze. See [Deploying and Testing App on Real TV, printed pages 3–5 and 14–17](https://webostv.developer.lge.com/assets/netcast/NetCast-Deploying_and_Testing_App_on_Real_TV.pdf).

PENDING: present-day App Test login, DRM packaging, entitlement retrieval and actual launch on this unit. Accessible historical documentation is not service availability evidence. A packaged comparison is conditional on verifying that legitimate workflow; do not bypass packaging or install an unofficial privileged loader to answer an input question.

## Proposed bounded experiment INPUT-001

- **Objective:** distinguish missing element focus or listener coverage from browser-level arrow consumption.
- **Hypothesis:** H1: a focused, ordinary HTML control receives arrows; H2: the browser consumes them even after focus. Neither is established.
- **Environment:** the existing LAN-only probe, original remote and ordinary browser; no package, credentials or native API calls.
- **Procedure:** prepare an updated probe locally with a visible focusable button and bounded logging of `keydown`, `keyup`, `keypress`, click and focus events, including event target and `document.activeElement`. After coordinating one refresh with the owner, click that button, verify the reported focus, then press each arrow once and OK once. Compare with the unfocused baseline. Preserve normal browser exit controls; do not cancel unknown/system keys.
- **Expected result:** either raw arrow codes reach the focused control, or cursor movement continues without keyboard events. A listener self-check can validate instrumentation locally but cannot simulate physical remote routing.
- **Observed result:** PENDING; this experiment has not run.
- **Conclusion rule:** received physical key events justify adapting DOM navigation. Their absence after verified focus supports H2 only for the tested browser configuration; it does not invalidate documented NetCast application input.
- **Risks and return path:** temporary replacement of the research page and possible loss of its in-page state. No TV settings, inputs, services or storage are changed. Use the browser's existing normal exit path when the owner is ready; Home exit was confirmed in HW-001; repeat-load acceptance remains separate.
- **Next step:** if H2 persists, inspect the ordinary browser's visible options without changing them, and investigate legitimate packaged-app availability in parallel. If available, compare the same event probe in application context. Continue native input/graphics dependency research toward the replacement shell regardless of the browser result.

Pointer operation is useful diagnostic access, not the intended OpenCast OS navigation model. No input result here proves autostart, launcher replacement, process isolation or recovery.
