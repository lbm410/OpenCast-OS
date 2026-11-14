# Compatibility matrix

| Capability | Current evidence | Next validation |
| --- | --- | --- |
| UDAP discovery | CONFIRMED on target; exact model/FW response | Repeat after ordinary TV restart only when owner initiates it |
| UDAP/DLNA descriptor reads | CONFIRMED HTTP 200 | Review advertised APIs before any paired query |
| Browser HTML/JS execution | CONFIRMED device reports during owner-assisted test; original remote OK/click actions observed | Normal Home exit is confirmed; repeat load remains pending |
| Browser engine | Device UA advertises AppleWebKit/537.4 and Chrome/22.0.1229.79 | Engine build internals not independently verified |
| Browser viewport | CONFIRMED 1276×603 CSS pixels in both reports; panel is Full HD | Fullscreen behavior and readability remain separate checks |
| Modern JavaScript/frameworks | Unverified; not used | Capability evidence first, no framework assumption |
| Canvas / requestAnimationFrame | 2D context obtained; unprefixed requestAnimationFrame absent | Check prefixed variants later; no acceleration claim |
| Original remote input | Four click-handler actions, zero keydown events across two reports | Owner confirms browser cursor movement, but direct card movement outside the browser; Home exit confirmed; reload pending |
| USB app packaging | CONFIRMED: owner portal registration/download, inspected output and FAT32 USB preparation; corrected package renders | Repeat launch, exit/AV checks and quantified load time |
| Packaged remote navigation | CONFIRMED by owner: arrows and OK work in launcher; movement is slow | Compare fixed-geometry/reduced-write candidate; measure actual input latency |
| Browser NetCast symbols | NetCastBack and NetCastExit absent from window | Packaged-app APIs must be assessed separately |
| Native app / replacement shell | No compatible ELF executed | Identify ABI, graphics/input contracts, exit path |
| Auto-start / boot replacement | No documented target-specific safe mechanism yet | Map init and recovery first |
| HDMI/tuner/native media integration | Not implemented; existing TV untouched | Verified adapter per function, explicit state-changing test |
| Netflix/YouTube/other commercial apps | No compatibility claim | Current API/DRM/TLS/provider support; no DRM bypass |

Host tools use Python's standard library. Total descriptor deadlines currently use POSIX signals in the main thread (macOS/Linux); Windows support is not claimed. The probe has no dependencies or external asset requests. JavaScript syntax checks on Node do not establish compatibility with the old TV engine.

## Input-routing observation

The owner confirmed that native NetCast cards respond directly to the remote arrows; only the current Internet/browser mode moves a cursor. This establishes a difference in input routing between execution contexts, not a physical remote limitation or proof that all browser modes are incapable of keyboard input. The probe observed no keydown events; other event modes and packaged-app APIs remain untested. Do not redesign the final OS around pointer-only interaction.

Home returned to the ordinary Smart menu, explicitly confirmed by the owner after HW-001. This verifies that exit path for the tested page; it does not independently test HDMI, tuner, audio, power management or recovery from a modified boot chain. The local experiment server has been stopped.


APP-001 update: the owner confirms rendering plus arrow/OK navigation in the corrected official USB-packaged launcher. Both startup and movement are reported slow. This is a different execution context from the ordinary Internet browser; its engine/version/viewport must not be inherited from the earlier UA report. Home exited the first black-screen package normally; successful-launch exit and explicit HDMI/audio continuity remain pending. The host performance candidate has not yet run on the TV.
