# HW-001 — physical browser execution probe

## Purpose and boundaries

Demonstrate our own HTML/JavaScript executing on the LG screen, receiving original-remote input and returning to normal TV operation. This is a capability experiment, not a replacement launcher or a completed OpenCast OS milestone.

The page contains three cards: an interaction counter, a capability report and exit instructions. It uses no external resources, control APIs or persistent browser storage. Visiting it may create normal browser history/cache entries. The TV remains on its current firmware. Opening the browser temporarily replaces the current viewing screen.

## Host preparation

Run the tests from README.md. Check current Mac/TV addresses and ensure port 8765 is unused. Start from the project root:

```sh
python3 -m tools.probe_server --bind MAC_IP --allow TV_IP --port 8765
```

Only that TV IP may connect. Reports go to ignored artifacts/probe/. No router changes are needed. Keep the Mac awake and the process running. An address change requires updating the command. For desktop development use the default loopback server; desktop results do not count as TV evidence.

## Owner-assisted procedure

1. Confirm readiness to interrupt the current viewing screen. Open the TV's ordinary Internet/browser application with the original remote.
2. Enter `http://MAC_IP:8765/` directly. Use HTTP, not HTTPS or a search query. If ordinary browser navigation is unavailable, record the failure; do not change service-menu settings.
3. Confirm the OpenCast heading is physically visible on the LG. Record load errors, viewport, text clipping and approximate navigation-to-visible time separately from the page's script timing.
4. Press Left, Right and OK. Record which keys reach JavaScript, whether the selection is clear and whether one OK produces one action. Do not infer key support from desktop keyboard tests.
5. Select Device report and press OK. Record whether the local save succeeds. The report deliberately retains `physical_tv_confirmed: false`; only owner observation can satisfy that criterion.
6. Use the browser's normal Back/Exit/Home controls to return to the previous TV interface. Confirm picture/audio and the previously selected input still work. Testing another HDMI source would require announcing that input change separately.
7. Reopen the URL once to verify repeatability, then exit normally. Stop the Mac server after collecting results.

## Measurement limits

`loadMs` measures early inline script to probe initialization, not full network load or first painted frame. `maxHandlerMs` is a coarse Date-based JavaScript handler duration, not remote-to-photon latency. `keyEvents` counts delivered keydown events, including repeats. Feature presence does not prove acceleration. No CPU/RAM/GPU figures are currently available.

## Success criteria

Owner confirms physical TV display, original-remote navigation, ordinary exit, unaffected essential functions and repeatable reload. A served HTTP response or uploaded report alone is insufficient. Current result: physical browser execution, button interactions, two device reports and return to the ordinary Smart menu with Home are confirmed. Direct D-pad navigation, repeat load and broader essential-function checks remain incomplete. The server has been stopped; no further owner action is required for this session.
