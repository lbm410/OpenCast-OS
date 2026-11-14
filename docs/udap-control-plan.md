# UDAP control plan for a grouped owner session

Prepared: 2026-11-14. Scope: documentation and existing local descriptor inspection only. No new TV request, pairing, key command, input change or owner prompt occurred. This original planning task did not implement a client. A later inventory-only client is now available and host-tested (udap-client.md); launch, SmartText and real pairing remain untested.

## Evidence and limits

Primary reference: [LG UDAP specification](https://webostv.developer.lge.com/assets/netcast/NetCast-UDAP.pdf), 76 printed pages. Page references below use the printed numbering, which equals PDF page index plus one. The official download is 3,926,438 bytes, SHA-256 `0ec50de6de018e451d3810dfcb10833f7be8da383ed5bb05a742e63948258c57`; the PDF, extracted text and acquisition record are ignored under `artifacts/udap-research/`.

CONFIRMED (device-reported, previously captured): `artifacts/diagnostics/udap-rootservice.xml` advertises these relevant APIs. A reduced inventory without unique device identifiers is `artifacts/udap-research/advertised-actions.json`.

| Service | Advertised commands | Advertised events | Relevant advertised queries |
| --- | --- | --- | --- |
| `netrcu` | `HandleKeyInput`, `HandleTouchMove`, `HandleTouchClick`, `HandleTouchWheel`, `HandleChannelChange` | `CursorVisible`, `ChannelChanged`, `CallStateChanged`, `DragMode`, `3DMode` | `context_ui`, `cur_channel`, `volume_info`; additional queries retained in inventory |
| `mobilehome` | `AppExecute`, `AppTerminate` | `Mobilehome_App_Change`, `Mobilehome_App_Errstate` | `appnum_get`, `applist_get`, `appicon_get` |
| `smartText` | None listed | `KeyboardVisible`, `TextEdited` | None listed |
| `AppToApp` | `LaunchApplication`, `TerminateApplication`, `SendMessage` | `ReceiveMessage` | `GetApplicationID`, `GetApplicationStatus` |

The descriptor proves advertisement, not successful invocation. Pairing, inventory, browser launch, text delivery and callback handling remain PENDING. The specification's capability-check requirement is on p.17; the service name alone is insufficient.

## Common wire contract

These are future request shapes, not executed commands. The current target address must come from fresh, confirmed discovery; do not embed a stale address in code. Ordinary API XML uses `envelope/api`, `api@type` and a `name` element. Requests use UTF-8, byte-accurate Content-Length and a User-Agent of the form `OS/version UDAP/2.0 product/version`. Build XML with proper escaping rather than string concatenation. See pp.18, 25–31.

| Operation | HTTP path | Payload/response |
| --- | --- | --- |
| Pairing | POST `/udap/api/pairing` | XML, `api type="pairing"` |
| Commands | POST `/udap/api/command` | XML, `api type="command"` |
| Ordinary events | POST `/udap/api/event` | XML, `api type="event"` |
| Ordinary queries | GET `/udap/api/data?target=...` | Query parameters URL-encoded; XML datasets |
| AppToApp | Paths below | Separate path-based profile; do not force the ordinary XML contract onto it |

The generic event example on p.30 prints `/udap/api/command` despite its event body. The smartText-specific section explicitly specifies `/udap/api/event` on p.56. Record this discrepancy rather than propagating the generic example blindly. Query errors include 401 (unpaired), 404 (path) and 500 (operation failure), p.31. These distinguish failure classes; none should trigger repeated commands automatically.

## Pairing, confirmation and clean disconnection

| Name | Fields inside `api type="pairing"` | Effect and checks | Pages |
| --- | --- | --- | --- |
| `showKey` | `name` only | Shows a six-digit pairing code on TV. This is a visible interruption, not a read-only query. HTTP 200 acknowledges the request. | 18–20 |
| `hello` | `name`, `value` = six digits without spaces, `port` = controller callback port | Establishes the controller session. HTTP 200 indicates pairing success; 401 rejects the code, 503 indicates controller capacity. Successful pairing dismisses the code overlay. | 20–21 |
| `byebye` | `name`, `port` = callback port | Ends pairing/session communication. Either side can send it; TV shutdown may notify controllers this way. | 21–22 |

The document describes a reusable UUID/code association on p.24. Treat that code as a credential, not a disposable screenshot label. The future first client should accept it through hidden local input, keep it only in memory, exclude it from argv/logs/reports and forget it after the session. No persistence mechanism is required for the first experiment. `byebye` ends the session; it is not documented as rotating the pairing credential or revoking every saved association.

A callback HTTP listener is required before `hello` if events are to be observed. Bind only to the confirmed Mac LAN interface and accept only the confirmed TV peer. Support bounded event/pairing paths, return promptly and tear it down at session end. Do not expose it through router forwarding. Incoming requests are untrusted data; do not execute them or log arbitrary text fields.

## Application inventory and launch semantics

| API | Parameters / fields | Meaning and bounds | Pages |
| --- | --- | --- | --- |
| `appnum_get` | Query `type`; response `type`, `number` | Categories: 1 all, 2 Premium, 3 My Apps. Count before fetching a list. | 66–67 |
| `applist_get` | Query `type`, `index`, `number`; response `auid`, `name`, `type`, `cpid`, `adult`, `icon_name` | Installed application inventory. Start with `type=1,index=1,number=16` or a smaller positive count. Do not use the unbounded all-items shortcut `index=0,number=0` for the first probe. | 65–66 |
| `AppExecute` | Command `auid`, `appname`, `contentId` | Starts an identified app. `contentId` is provider-defined content identity, not a documented arbitrary browser URL argument. | 62 |
| `AppTerminate` | Command `auid`, `appname` | Ends an identified app; do not terminate unknown/background TV components. | 62–63 |
| `Mobilehome_App_Errstate` | Event `action` = `Execute` or `Terminate`; `detail` = `OK`, `ERROR` or `BUSY` | The asynchronous operation result. AppExecute/AppTerminate HTTP 200 alone does not prove execution/termination success. | 63–64 |

The `number` description on p.66 calls it an item count but also says it must be greater than or equal to `index`; pagination semantics are therefore not cleanly specified. A first page with index 1 avoids that ambiguity. Do not implement subsequent pages until observed behavior or additional evidence resolves it. If the browser is not found in that bounded page, record a partial inventory; do not guess an AUID.

The AUID is documented as a hexadecimal identifier with an eight-byte description, while the p.72 example returns a shorter textual value. Preserve returned strings and leading zeros; do not derive IDs from visible names, assume a fixed hard-coded browser ID, or silently normalize numerically.

AppToApp adds these contracts:

| Method/path suffix | Contract | Pages |
| --- | --- | --- |
| GET `/udap/api/apptoapp/data/{URL-encoded Application Name}` | Returns plain-text AUID; searches Premium, My Apps, USB, Downloaded in that order. Duplicate names select the first match. Descriptor name is `GetApplicationID`; section title is “Get Application AUID”. | 72 |
| POST `/udap/api/apptoapp/command/{AUID}/run` | Launch existing app; 503 indicates no matching app. No URL launch argument is documented here. | 69–70 |
| POST `/udap/api/apptoapp/command/{AUID}/term` | Terminate identified app. | 70 |
| GET `/udap/api/apptoapp/data/{AUID}/status` | `NONE`, `LOAD`, `RUN`, `RUN_NF`, `TERM`. Example response is plain text despite nearby prose calling it XML. | 73 |
| POST `/udap/api/apptoapp/command/{AUID}/send` | Message to a cooperating web application, not a general browser navigation command. | 70–71 |

RULED OUT (as documented capabilities): treating AppExecute, AppToApp/run or messaging as arbitrary app installation, an unsigned USB loader, startup replacement or unrestricted URL execution. PENDING: whether the native browser appears in the target's app inventory and supports these launch paths.

## SmartText as the proposed URL-entry route

| Event | Direction | Fields | Pages |
| --- | --- | --- | --- |
| `KeyboardVisible` | TV → controller | `value` = `true`/`false`; `mode` = `default`/`password` | 56–57 |
| `TextEdited` | Both directions | `state` = `EditStart`/`Editing`/`EditEnd`; `value` = entire field string | 58–59 |

CONFIRMED (documentary): SmartText replaces/transmits the complete UTF-8 field content, not individual keypresses. The documented limit is 2 KB. Our proposed URL is short ASCII and must remain well below that bound. A field click can trigger KeyboardVisible, followed by one TV TextEdited event containing the existing text with state `Editing`.

HYPOTHESIS: focusing the ordinary browser's address bar exposes SmartText on this model. Advertisement does not prove that browser chrome uses it. If it does, a controller can supply the exact local probe URL without repeated remote typing. Preserve the documented edit-state sequence; do not assume `EditEnd` also submits/navigates. One explicitly coordinated OK action may still be needed after the URL appears.

For password mode, stop text handling and discard values without logging. Also avoid logging the current field text in normal mode: it may contain private history or unrelated information. Do not send a URL until the owner confirms the intended address field is focused and `KeyboardVisible=true, mode=default` has been observed. If that event never arrives, do not send blind TextEdited requests; use a later manual/bookmark fallback or investigate independently.

## Input control boundaries

`HandleKeyInput` sends a virtual key value in the `value` XML element (p.42). These UDAP values differ from DOM keycodes: Up/Down/Left/Right are 12/13/14/15, OK is 20, Home is 21 and Back is 23. External input is 47 (p.75); Exit is 412 (p.76). Do not reuse browser arrow codes 37–40 as UDAP arrows.

PENDING: direct HDMI selection. This specification documents an External input key, not a verified per-port HDMI selector or input enumeration contract. Opening an input menu and navigating it changes viewing state; exclude that from the first URL-entry session. Channel-changing commands are not HDMI selection APIs.

`context_ui` reports `VolCh` or `TouchPad` (p.53); it is a query, not a mode setter. `CursorVisible` has `value=true/false` and `mode=auto` (p.46); it controls cursor visibility, not a documented conversion of browser arrow movement into DOM key events. Keep it out of the first session to avoid confounding the existing input observations.

## Proposed experiment UDAP-001: one pairing, inventory, one URL

- **Objective:** test whether authorized UDAP can remove repeated on-TV URL typing while preserving a clear return path.
- **Hypothesis:** the advertised services support pairing, app inventory and SmartText for the browser address field.
- **Environment:** confirmed target and Mac on the owner's LAN; bounded controller prepared and tested locally beforehand; fresh peer addresses; callback listener limited to that TV. No client or listener exists yet for this experiment.
- **Before execution:** explain the pairing-code overlay, temporary browser launch/text change, listener lifetime and Home return. Obtain the owner's agreement for this specific reversible session. Begin from the Smart menu if convenient so an active HDMI session is not interrupted unnecessarily.
- **Stage A, one owner action:** request the code once; owner enters it privately on the Mac; send `hello` and require success. No PIN retry loop.
- **Stage B, no owner action:** issue one `appnum_get`, one bounded `applist_get`, and optionally one `context_ui` query. Record only necessary app identity/status fields in ignored local evidence. No icons, screen capture, channel list or unrelated data are needed. Do not launch anything until its identity is unambiguous.
- **Stage C, one focus action:** if the browser can be identified and launch has been authorized, launch once and check operation result/status. Otherwise the owner opens the existing browser once. The owner selects its address bar. Wait a bounded interval for normal-mode KeyboardVisible, then send the prepared local URL through SmartText. Submit once only after the displayed URL is confirmed; never use an unattended key sequence through unknown UI state.
- **Stage D, one confirmation and return:** owner confirms the local probe is visible. Collect its normal report. Return using the previously demonstrated physical Home path, or one separately agreed UDAP Home command with physical confirmation. End pairing with `byebye`, close the callback listener and discard the code. If the initial viewing state was an external input, coordinate restoration explicitly rather than assuming Home restored HDMI.
- **Expected result:** paired session, bounded inventory, observable keyboard handshake, exact URL entry, probe displayed and normal return. Each stage has an independent acceptance result.
- **Observed result:** PENDING; only discovery/description and the earlier manual browser probe have run.
- **Failure handling:** stop the failing branch on 401/503, callback timeout, absent keyboard event, ambiguous app identity, password mode or UI mismatch. Continue independent host research. A successful HTTP request alone never establishes the visual outcome.
- **Risks:** temporary viewing interruption, unintended text replacement, old-service instability and disclosure through callback logs. Mitigate with explicit field confirmation, one target, bounded requests/timeouts, no raw text/PIN logs and no automatic retry/navigation loops. No persistent/privileged operation is part of this plan.
- **Next step:** implement and test a narrowly scoped controller with synthetic HTTP/XML/event fixtures before scheduling the grouped owner session. Keep API research and control authorization separate from firmware/native-launcher integration.

## Direct input selection: implementation cross-check

**CONFIRMED (primary source, 2026-11-14):** Connect SDK's generated NetcastTVService API lists external-input methods, but the [pinned Android implementation](https://github.com/ConnectSDK/Connect-SDK-Android-Core/blob/2f7ebbc7eb909321ff41b2c6bcdf6b0881427579/src/com/connectsdk/service/NetcastTVService.java#L1405) returns not-supported for input enumeration and direct selection (lines1446–1455). Its picker method instead looks up and launches Input List. Source blob90471146d805689b5ddb5da43376ea5146424d53 was inspected through the GitHub connector, without executing it. Interface documentation alone must not be presented as implemented HDMI switching. This is a limitation of that inspected adapter, not proof that every device-side control route is absent.

**Experiment INPUT-CONTRACT-001:** compare the published interface with actual source for the desired HDMI capability. Expected an implemented command or an explicit unsupported result; observed the latter for direct selection. No TV request, pairing or input change occurred. Continue native TV-control contract research separately; never replace an unavailable per-port operation with blind arrow sequences.
