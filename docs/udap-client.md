# Bounded UDAP client foundation

Prepared: 2026-11-14. Implementation: `tools/udap.py`. **CONFIRMED (host/synthetic):** request construction, bounded transport, XML parsing, pairing state, limited inventory and gated SmartText planning. **PENDING:** actual TV pairing, inventory, callback delivery and text control. No TV or LAN request was made to build or test this module.

The first CLI is deliberately offline-only. The library contains transport primitives but is not yet a complete interactive device runner. A real, restricted callback listener and reviewed lifecycle integration are required before device use. The integration work is separate from this foundation. `tools/udap_session.py` now provides the inventory-only runner described below; its validation remains synthetic/loopback-only.

## Offline use

```sh
python3 -m tools.udap --dry-run pairing
python3 -m tools.udap --dry-run inventory
python3 -m tools.udap --dry-run smarttext
python3 -m unittest discover -s tests -p 'test_udap.py' -v
```

Dry runs print a fixed, non-sensitive plan and `network_requests: 0`. The CLI accepts no address, PIN, URL or live-operation argument. Argument errors do not echo unrecognized input. Do not pass pairing codes on a command line or paste them into project records.

## Protocol scope

The request and dataset shapes follow [the grouped UDAP plan](udap-control-plan.md) and the [official LG UDAP specification](https://webostv.developer.lge.com/assets/netcast/NetCast-UDAP.pdf), especially printed pages 18–22, 56–59 and 65–67. The locally retained source text was checked for the actual `envelope/api` and `envelope/dataList/data` schemas. Documentary support does not establish behavior on this unit.

Implemented requests are `showKey`, `hello`, `byebye`, `appnum_get`, and the first bounded `applist_get` page. SmartText event requests can be prepared, but the transport explicitly rejects them. There are no arbitrary URLs, app launches, remote keys, Home commands, channel controls, HDMI selectors, persistence operations or callback server in this module.

`contentId` is not treated as a browser URL. App identifiers are preserved as returned hexadecimal strings, including leading zeros. Inventory discards provider content IDs, icon names and adult flags after validating their schema; it retains only app ID, name and category in memory. No icon or returned URL is fetched.

## Network and resource contract

`PeerConfig` requires the exact confirmed target IPv4, explicit service port, source/controller IPv4 and a private local `/24` or narrower subnet. Both addresses must be real host addresses within that subnet and differ. Hostnames, public destinations, wildcard/source addresses, network/broadcast addresses and unconfirmed targets fail before connection. The separate `loopback_fixture` constructor permits only the exact test address `127.0.0.1`; it is not a LAN-discovery mechanism.

`Transport.exchange` makes direct source-bound `HTTPConnection` requests. Environment proxies are irrelevant; redirects and all non-200 responses are rejected without following them or retrying. The library never accepts a generic fetch URL. Request method, path, query fields and XML are checked against the small supported profile before connecting.

Each exchange has a finite socket timeout and a POSIX wall-clock deadline, default three seconds and at most ten. The deadline is reused from discovery and requires the macOS/Linux main thread without an existing active alarm. Calling transport from a callback worker fails closed. HTTP parsing has the standard library's finite header bounds, followed by an 8 KiB aggregate-header check; response bodies are limited to 64 KiB. Duplicate Content-Length, transfer encoding, compressed content, truncated lengths, oversized bodies, unexpected query MIME types and nonempty pairing acknowledgements are rejected. No raw response or header enters an error message.

A transport permits at most 32 attempts, with its final slot reserved for one explicit `byebye` attempt. There are no automatic retries. Inventory counts first and requests at most 16 apps with `index=1`; ambiguous later-page semantics are not implemented. Results explicitly indicate partial inventory. A filtered category response containing another category is rejected.

XML accepts UTF-8 only and rejects null bytes, DTDs and entity declarations. Parsed trees are bounded to 256 elements and depth five; exact known fields, attributes and leaf structure are checked. Callback payloads are limited to 8 KiB, field text to 2 KiB, and each session to 64 accepted-peer callback attempts. Unsupported shapes fail rather than being guessed into a compatible form.

## Pairing and cleanup

`Session` requires a callable reporting actual callback-receiver readiness. It is an integration contract, not a listener implementation or proof that a port is bound. Do not replace it with a constant in device code; constant readiness exists only in synthetic tests.

The library sequence is:

1. Confirm the target and explain the temporary pairing-code overlay to the owner.
2. Start and verify the restricted callback receiver outside this module.
3. Call `request_pairing_code(owner_approved=True)` once, after that specific agreement.
4. `pair_interactive()` reads the code with hidden `getpass` input and submits `hello` once.
5. On success, perform the bounded inventory if intended.
6. In the integration's `finally` path, call `close()` and stop the callback receiver.

The explicit booleans represent agreement already obtained; setting a variable does not obtain owner authorization. Hidden input rejects the terminal echo-fallback warning instead of exposing the credential. Only six ASCII digits are accepted. A failure moves the session to failed state and does not prompt or retry again.

The PIN is never a session field, argv option, report or log value. Temporary request/body representations omit it, and method-local references are released after the attempt. Python immutable strings and socket buffers do not provide guaranteed cryptographic memory erasure. Do not debug-log raw requests.

Explicit close sends at most one `byebye` after a `hello` attempt, even when its outcome was uncertain, and closes local state regardless of disconnect success. A received `byebye` closes state without sending another. Disconnect is not described as rotating or revoking a reusable pairing credential. A failed `showKey`/PIN stage also does not imply the visible code overlay was dismissed.

## SmartText gate: planning only

The callback parser returns a sanitized event containing enums, booleans and optional text-presence information. It never returns the current field string. Password-mode text is not retained by the session. The original complete value is discarded; error messages and object representations omit it.

A local-URL plan requires all of the following:

- A paired session and a still-ready receiver.
- `KeyboardVisible=true, mode=default` from the confirmed peer, within 30 seconds.
- The subsequent `TextEdited` / `Editing` handshake.
- An explicit owner confirmation that the intended browser address field is focused, within 15 seconds.
- An HTTP URL naming exactly the confirmed controller IPv4 with an explicit port, no credentials, query, fragment or whitespace.

Password mode, hidden keyboard, field changes, unexpected edit states, malformed callbacks, timeouts or disconnection invalidate the gate. A confirmation is consumed on one planning attempt, including URL-validation failures. An empty original field produces EditStart → Editing → EditEnd; a nonempty field already in Editing produces Editing → EditEnd. No original field string is copied into the plan.

`SmartTextPlan.transmission_enabled` is always false, and passing its requests to `Transport.exchange` raises `smarttext_transport_not_integrated` before network access. This is intentional: planning is not proof of safe asynchronous field tracking or accepted editing sequences on the TV. `EditEnd` is not assumed to submit or navigate. No key command is generated.

Before enabling a dedicated session-bound sending route, integrate bounded callback ingestion, ingress timestamps, immediate password/field/disconnect invalidation and validity checks before every send. Do not wire an unbounded callback worker into the library or hold a network request open while waiting for interactive input. The current serialized library state is a foundation; it does not itself promise prompt callback HTTP acknowledgements or atomic TV focus tracking.

## Experiment UDAP-F001

- **Objective:** establish a reviewable client contract before the grouped physical session.
- **Hypothesis:** explicit targets, strict shapes, finite budgets and state gates reject unsafe requests while allowing documented fixture exchanges.
- **Environment:** Python standard library, synthetic XML and ephemeral HTTP servers bound only to `127.0.0.1`; no vendor executable or TV connection.
- **Procedure:** test destination validation, escaped builders, hostile datasets, PIN handling, pairing/inventory state, callback privacy and SmartText gates; exercise direct HTTP against synthetic acknowledgements, redirects, errors, truncation, excessive bodies and slow responses.
- **Expected result:** valid fixtures succeed; malformed/out-of-scope data fails without retries, raw-data disclosure or unintended requests.
- **Observed result:** 24 tests passed. An independent review found that category-filtered inventory could accept another category; this was corrected and covered by a regression. Slow-drip headers are now also tested against the total deadline, separately from an idle socket timeout. Dry-run modes made zero requests.
- **Conclusion:** the local foundation is ready for integration review. Device compatibility, successful pairing, a working callback server and URL entry remain unproven.
- **Risks:** real protocol variation may fail strict parsing; partial inventory does not identify every app; library readiness is supplied by the integrator; physical focus remains externally observable state.
- **Next step:** add and test a bounded callback receiver and complete session lifecycle without activating any TV operation. Inventory-only execution is the fallback if SmartText integration is not demonstrably safe.


## Inventory-only interactive integration

`tools/udap_session.py` supplies the missing callback receiver and an explicit session lifecycle for **inventory only**. It does not enable the foundation's blocked SmartText transport, and it exposes no URL-entry, app-launch, input-switching or key-command option. The receiver can observe keyboard events for diagnostics, but those observations do not authorize or perform text changes.

Offline inspection remains available without opening sockets:

```sh
python3 -m tools.udap_session preview
python3 -m tools.udap_session inventory --help
```

After integration review and coordination with the owner, the intended interactive invocation is:

```sh
python3 -m tools.udap_session inventory \
  --confirmed-target TV_IP --port ADVERTISED_UDAP_PORT \
  --bind MAC_IP --network LOCAL_SUBNET/24 \
  --save-inventory
```

Replace placeholders only with freshly confirmed addresses and the advertised service port. There are no embedded target addresses or assumed default UDAP ports. The CLI requires a real interactive terminal and a typed `PAIR` confirmation explaining the code overlay, pairing, read-only inventory and temporary listener before any socket is opened. The code itself is then requested through hidden input; no PIN flag exists. Declining creates no listener and makes no request.

The listener binds the explicit controller interface and normally uses an OS-assigned port, which is passed to `hello`. It starts before pairing. Incoming connections must originate from the exact confirmed TV peer. Only POSTs to the pairing/event paths are accepted. Requests have a 512-byte request-line bound, 4 KiB aggregate header budget, exact Host and singleton length/type checks, no transfer/content encoding, and an 8 KiB body bound. A hard per-connection timer closes slow-drip requests independently of the idle socket timeout. The listener permits at most 64 accepted-peer connections and has a finite lifetime, default 90 seconds.

The lifetime bounds the listener and further non-cleanup network actions. Waiting at the hidden terminal prompt can continue after listener expiry; if input subsequently arrives, readiness checks prevent a late `hello`. This is stated in CLI help. The process does not forcibly terminate the owner's terminal.

Callback parsing and acknowledgement happen independently of the library's session lock. Stored state contains only event counts, visibility/mode enums, edit-observation booleans, receipt time and an invalidation generation. It never queues raw XML or field strings. Password mode, hidden keyboard, edit-end/malformed events and listener expiry clear the editing observation. `byebye` immediately sets a disconnect flag. A guarded transport checks receiver/disconnect state before every outgoing request, including the transition from app count to app list; the loopback test proves that a `byebye` during the count response suppresses the list request.

The `finally` path makes at most one explicit disconnect attempt, then always stops the listener. A keyboard interruption during disconnect still reaches listener cleanup. Concurrent stop calls wait for socket teardown; failure to start a worker closes an already-bound socket. A received remote disconnect prevents unnecessary further requests. HTTP success is recorded separately from a physical outcome, and no synthetic run marks `physical_tv_confirmed` true.

### Optional private inventory evidence

Without `--save-inventory`, app records remain only in the returned library result and are discarded when the CLI exits. Standard output contains bounded counts and lifecycle status, not app identities or callback text.

With the explicit flag, a complete private JSON report is published under the repository's ignored `artifacts/diagnostics/` directory. It contains exactly a capture timestamp, reported total, partial-inventory flag and records with `auid`, `name` and `category`. This makes later browser identification possible without repeating discovery or exposing raw XML. No PIN, field value, channel history, icon, provider content identifier or device identifier is included.

The file is created with mode `0600`. Directory-relative descriptors and `O_NOFOLLOW` prevent following output-directory symlinks; publication is exclusive and cannot overwrite an existing file or symlink. Encoding happens before creation, temporary output is private, and failed publication removes the temporary file. The CLI prints only the saved relative path alongside counts. The report remains local evidence, not material for Git or project documentation.

### Experiment UDAP-S001

- **Objective:** validate listener/session lifecycle and retain useful bounded inventory without contacting the TV.
- **Hypothesis:** a real bounded callback receiver and per-request state guard can support one controlled pairing/inventory/disconnect cycle.
- **Environment:** Python standard library; synthetic TV and callback servers exclusively on `127.0.0.1`; temporary private report directories.
- **Procedure:** run the full session against the fixture; inject PIN rejection, asynchronous disconnect, slow bodies, malformed/duplicate headers, wrong methods/peers, listener expiry, worker startup failure and interruption during cleanup; test exclusive private report publication and symlink rejection.
- **Expected result:** successful fixture inventory, no retry, early stop on invalid session state, no secret/raw-text output and closed listener on every tested exit path.
- **Observed result:** 19 integration tests passed, in addition to the 24 foundation tests. A review-found cleanup gap for interruption during `byebye` was fixed and covered. No actual TV or LAN listener was used.
- **Conclusion:** a concrete inventory-only runner is ready for review. Real pairing, exact callback compatibility and inventory response compatibility remain PENDING.
- **Risks:** strict headers or datasets may reject an older implementation; callback IP filtering is not cryptographic authentication; the app list is limited to its first page; terminal input can outlive listener expiry.
- **Next step:** review the integrated code and coordinate a single owner-assisted inventory session when useful. SmartText remains planning-only until asynchronous focus validity and the real editing sequence are verified through a dedicated session-bound design.

```sh
python3 -m unittest discover -s tests -p 'test_udap*.py' -v
```
