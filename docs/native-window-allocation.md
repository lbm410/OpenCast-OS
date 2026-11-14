# Native window identifiers: lookup, reservation and surface boundaries

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** the generic `GetWindowID` receiver can reserve a service-name record; it is not necessarily a side-effect-free lookup. Its new-reservation branch requires a supplied path equal to the stock fxui path. Separate functions create and destroy graphics surfaces. None establishes a callable ABI, admission for another executable, authenticated ownership, successful display or physical return to the stock UI.

This follows the [fxui consumer trace](native-window-contract.md). That report's provider-mediated lookup describes the consumer boundary; this receiver slice adds the conditional reservation effect. Preserve the [bus-policy](native-bus-policy.md) and [entry-contract](native-entry-contract.md) limitations.

## Provenance and reproduction

Only the existing selected `firmware/lab/service-selected/open/bin/procmgr` was inspected: 435,528 bytes, SHA-256 `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5`. No extraction, target execution, IPC, TV/network action or Git operation occurred. Apple LLVM host executable SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`.

Ignored evidence is under `artifacts/native-window-allocation/`: 15 JSON/annotated-text captures totaling 4,484 selected bytes; `selected-data.json` contains three technical literals, three method-table entries and resolved import names. The bounded table walk terminates after 58 records. It reads names only for the three selected handlers. `manifest.json` records capture, helper and source hashes. Reproduce from the repository root with the existing reviewed host disassembler:

```sh
PYTHONPATH=. python3 artifacts/native-window-allocation/capture.py
PYTHONPATH=. python3 artifacts/native-window-allocation/metadata.py
```

Linked addresses below map to file offsets by subtracting `0x8000`. Captures include literal pools, which are data. Two exploratory captures include neighbors: `service-lookup` extends beyond its `0x29a40` boundary to `0x29ac4`; `pool-locks` includes the next function's first 12 bytes. Only explicitly identified instructions support claims here. The nearest exported-symbol label is not a function boundary.

## Receiver route and reply limits

`PM_HNDL_GxMsgRecvHandler` (`0x291a8..0x292c0`) requests `lg.service.special.processmanagergx`, recognizes method messages, compares their interface/member through `SCF_BUS_Message_Is_Method` (`0x29250`) and calls the matching handler at `0x29284`. Its 16-byte table records provide these exact routes:

| Record address | Interface | Member | Handler |
| --- | --- | --- | --- |
| `0x75fa0` | `lg.if.service` | `HOA_GX_GetWindowID` | `0x2698c` |
| `0x75fb0` | `lg.if.service` | `HOA_GX_GetWindowIDWithServiceName` | `0x26898` (body outside this slice) |
| `0x75f10` | `lg.if.service` | `HOA_GX_CreateWindow` | `0x26cc0` |

The generic handler parses PID, service and execution-path fields, then invokes `PM_GX_GetWindowIDWithServcieName` with allocation flag 1 (`0x26a0c..0x26a18`). The examined body does not compare the parsed PID to a transport peer identity. This does not establish the absence of authentication elsewhere.

`PM_SEND_WindowID` (`0x19fd4..0x1a078`) constructs a reply containing the numeric ID and a separate boolean. The generic handler sets that boolean to 1 after successful payload parsing, without checking the returned ID's validity. A successful reply therefore does not prove a reserved record, valid rendering handle or ownership.

## Lookup can become a reservation

`PM_GX_GetWindowIDWithServcieName` (`0x2c2e8..0x2c3d0`) first checks global word `0x97720+0x58`; zero returns 79. A null service returns -2. Its local lookup (`0x298c4..0x29a40`) checks 19 configured substring mappings, then scans 79 records using a 256-byte service-name comparison. Existing mappings return their ID. These are name associations, not demonstrated security principals.

On no match, allocation flag 1 invokes `_PM_GX_GetWindowIDAtWindowIDPool` (`0x2c1c0..0x2c2e8`). All three arguments must be non-null and the supplied execution-path string must equal `/usr/local/bin/fxui` (literal `0x46c68`, comparison `0x2c1f8`). This is a string condition, not a demonstrated verification of the sender's loaded executable. It must not be repurposed as an identity-spoofing workaround.

Under the mutex reached through `0x29318`/`0x29330`, the pool checks IDs **27–66**. Records have an observed stride of 4,032 bytes; the service-name field is at record `+0x898`. A record containing `lg.service.normal.default` is treated as available. The code writes the chosen ID, clears 256 name bytes and copies the supplied service name (`0x2c268..0x2c284`). Thus this branch mutates bookkeeping. The helper also returns an existing matching ID and reports failure if the pool is exhausted. These offsets describe this binary, not a recovered public structure.

The wrapper returns numeric 25 on pool-helper failure; no-allocation lookup failure retains 79. Neither value is evidence of fresh ownership. Separately, `PM_GX_IsValidWindowID` (`0x2a564..0x2a618`) requires the global flag and accepts unsigned IDs 0–77; it rejects 78, 79 and negative values. It checks a numeric range, not service ownership, and would accept 25 under that flag. Do not treat this validator as a reservation certificate.

## Creation and release are separate operations

`PM_HNDL_CreateWindow` (`0x26cc0..0x26e78`) decodes a 24-byte payload, then calls the service-ID helper with a **null execution-path argument** and allocation flag 1 (`0x26d8c..0x26d98`). Consequently its fallback cannot satisfy the pool's non-null-path requirement. It can return an existing mapping; a failed fallback returns 25. An optional branch calls the key-table function at `0x2c944`; its internals remain outside this slice. No graphics-surface constructor is called in this handler.

The distinct `PM_GX_CreateSurface` (`0x2ad48..0x2aed0`) calls imported `GAL_GX_CreateSurface` at `0x2ad90`, checks its result, and inserts a separate surface record into the hash object at `0x97744`. `PM_GX_DestroySurface` (`0x2bedc..0x2bf30`) deletes from that hash; it does not directly call GAL in its own body. The local callback at `0x29a40..0x29a50` passes a non-null node plus eight bytes to `GAL_GX_DestroySurface`. `PM_GX_DestroySurfaceDirectly` temporarily removes the hash destroy callback around deletion and restores that callback (`0x2be70..0x2bedc`). Hash-callback invocation semantics, external GAL internals and the EGL-to-GAL connection are not established here.

`PM_GX_ResetWindowInfo` resolves without allocation and validates the ID. Its ordinary branch queues a 64-byte type-4 operation (`0x31d80..0x31d98`); its alternate branch invokes the local reset at `0x31a74`. That reset clears fields and replaces the service name with the default marker (`0x31b40..0x31b74`), then can restore a configured name by numeric-ID lookup. This demonstrates a bookkeeping-reset path, not that every process exit reaches it. `PM_GX_ExitApp` (`0x31e20..0x32064`) changes window state and delegates to another helper; its name alone does not establish destruction or pool release. Queue completion, callback quiescence, focus restoration and HDMI/audio continuity remain **PENDING**.

## Consequence for the next experiment

The least-risk next step remains host-only: model ID reservation separately from surface acquisition and reject a merely successful reply or numeric-range check as proof of ownership. Native binding still requires a verified admission route, service-bound identity, renderer/provider contract and acknowledged teardown. A narrowly scoped follow-up can trace the reset queue consumer and EGL provider's use of the framework ID; it must not call these private methods on the television. No stock ID should be borrowed, no path impersonated, and no launcher stopped on the strength of this evidence.
