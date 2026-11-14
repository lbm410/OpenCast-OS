# Ordinary Internet browser versus the NetCast application runtime

Date: 2026-11-14. Static inspection of the official 04.28.17 update only. No
vendor script, ELF, JavaScript, IPC operation or network request was executed.

**CONFIRMED (local static):** the update supplies two distinct browser launch
paths. The Internet application's manifest points to `run_webbrowser`, whose
script selects Chromium22 and forces the exact Chrome22/WebKit537.4 user-agent
string observed by the physical probe. A separate `run3556` script launches
`lb6wk`, which links WebKitGTK/GTK3 and the LG TV bridge and contains application
mode machinery. This strengthens the runtime distinction; it does not establish
which process was live from the UA alone, nor demonstrate D-pad events inside a
custom packaged application.

## Selection, integrity and method

The existing bounded `tools.firmware_lab_squashfs` helper copied four regular
files from the preserved `base.pak` into ignored
`firmware/lab/browser-runtime/`. Source package SHA-256:
`12182a1b2ea9113b2308f3627832b18b38da490f5bfe7acb3dd9297bea967337`.

| Selected path relative to package | Bytes | SHA-256 |
| --- | ---: | --- |
| `browser/run3556` | 10228 | `319d0df706b5dfafe0c4fbc4c3aaf198aeb3411c0b77f874ddb9ac4bd348db34` |
| `webbrowser/run_webbrowser` | 9216 | `5f860b8ea1612c9258448f7c3bc32cc46fc204e2bad7d7cd0c3faa2b093cb334` |
| `addon/contents/system/internet/manifest.xml` | 859 | `8a2d0acf7c68fb9ee251a86c1cd10017d1efc0842bef2c8b5e534d13440e2894` |
| `addon/browser/browser_application.txt` | 30131 | `256e07533d5f9271497e2869f28ecd323e70956b85c6b8bc396b9a91fc3c522f` |

Reproduction requires new output directories; selections are created read-only:

```sh
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/base.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/browser-runtime/scripts \
  --select browser/run3556 --select webbrowser/run_webbrowser
python3 -B -m tools.firmware_lab_squashfs firmware/lab/packages/base.pak \
  --tool artifacts/firmware-lab/unsquashfs \
  --output-dir firmware/lab/browser-runtime/registry \
  --select addon/contents/system/internet/manifest.xml \
  --select addon/browser/browser_application.txt
```

Existing selections `firmware/lab/base-selected/browser/bin/lb6wk`, the two
system-app registries and `firmware/lab/base-api-selected/browser/lib/libtv.so`
were reused read-only. Ignored `artifacts/browser-runtime/` holds selection
manifests, hashes, ELF metadata, narrowly filtered technical strings and bounded
host disassembly. An attempted symbol-targeted `main` inspection found no
exported `main` in lb6wk; no argument semantics are inferred from that absence.
The 66,835,212-byte `webbrowser/chrome` is present in the inventory but was not
copied or analyzed for this task.

## Concrete launch paths

Line references in this section refer to the vendor files, not this report.

| Evidence | Ordinary Internet path | Separate LG browser path |
| --- | --- | --- |
| Service list | `svclist.rc:209`: `/mnt/webbrowser/run_webbrowser 0`, service `lg.service.normal.pwoff.nomem.webbrowser` | `svclist.rc:203`: `/mnt/browser/run3556 0`, service `lg.service.normal.pwoff.nomem.browser`, user `browser` |
| Wrapper | `run_webbrowser:6–10`: Chromium selection, name `Chromium22`, NetCast 4.0 and deployment directory | `run3556:10–16`: LG Browser 6, NetCast.TV-2013, deployment directory and `LIBTV_PATH` |
| Final command | `run_webbrowser:291`: relative `./chrome`, vendor flags, forced UA, `--chrome-switch-end`, forwarded arguments | `run3556:246`: `lb6wk` resolved through modified PATH, forwarded arguments |
| Mode context | `run_webbrowser:206`: `KROMIUM_LAUNCH_MODE=2`; numeric meaning not traced | `run3556:82–85`: comments/settings distinguish CP/APP mode and tiled backing |
| Overrides | `run_webbrowser:264–269` sources cache `extra_conf` if present | `run3556:123–133` sources addon and cache `extra_conf` if present |

Both scripts forward arguments using unquoted shell expansion. The normal
service declarations supply `0` plus service/AUID fields, but the meaning of
that positional zero and all downstream parser branches remain **PENDING**.
The `--chrome-switch-end` delimiter separates wrapper-selected flags from
forwarded arguments; it is not proof of a supported URL command-line interface.
The Chromium wrapper uses relative executable/library/config paths without
establishing its own working directory. Caller setup is part of its contract.

These are not standalone commands to run as an experiment. `run_webbrowser`
calls a browser-kill helper (`:21`), may remove Preferences (`:68–71`), populates
profile data, changes permissions recursively (`:191–192`), clears lock/cache
files and mounts temporary storage (`:194–200`). `run3556` also creates/configures
runtime files when missing. Its sourced overrides may change behavior. None of
those side effects was performed or proposed for the physical TV.

The Chromium script includes vendor security-disabling flags and selects an
accelerated-compositing-off flag group (`:233–238`). These describe the inspected
default script; they are not settings to copy into OpenCast, measurements of the
live renderer or evidence that changing those flags would improve performance.
Likewise `FRAMEBUFFER=/dev/fb1` (`:11`) is an environment value, not proof that
OpenCast can safely acquire that device or preserve the display pipeline.

## Internet application identity and UA evidence

The Internet manifest has `app_id` 70006 (`:5`), `app_type` 8 (`:7`), file name
`/mnt/webbrowser/run_webbrowser` (`:8`), empty `exec_arg` (`:9`) and alias
`internet` (`:13`). `systemapps_su2.xml:51` maps the same alias/id; the launcher
registry repeats it across regional sections, beginning at line 10. This is a
static identity mapping, not a UDAP inventory response or a hard-coded launch
authorization. A live UDAP experiment must still discover and preserve the
returned identifier.

`run_webbrowser:229–230` constructs a forced user-agent:

```text
Mozilla/5.0 (Linux; U) AppleWebKit/537.4 (KHTML, like Gecko) Chrome/22.0.1229.79 Safari/537.4
```

That string matches the version tokens captured by the owner's browser probe.
Combined with the Internet manifest and launch script, the ordinary Chromium
path is **LIKELY** the tested context. A live process/binary identity was not
captured. The explicit UA override is an additional reason not to treat the UA
as independent engine-version proof. Script build/revision banners are also
build metadata, not runtime attestation.

## LG browser application/input evidence

The existing lb6wk ELF is ARM32 little-endian EABI5, SHA-256
`0b9f18180a95c6ad60cfe6c2f8514194c40b51d63511738a7c7caffe279c9b25`.
Its 50 direct dependencies include `libwebkitgtk-3.0.so.0`,
`libjavascriptcoregtk-3.0.so.0`, `libgtk-3.so.0`, `libgdk-3.so.0`,
`libdirectfb-1.2.so.0` and `libtv.so`. This confirms a separate linked software
stack; an exact WebKit revision is not established here.

The script selects `addon/browser/browser_application.txt` (`run3556:49`). Its
column comments describe application IDs/URLs and per-application settings:

- `browser_application.txt:7`: spatial navigation is described as not yet
  implemented. This cannot be advertised as an available navigation switch.
- `:17`: a Magic Remote enable field, with a comment about applications that do
  not handle mouse input.
- `:18`: native options for application versus browser handling of Home/Exit.
- `:20–21`: resolution and system keyboard settings.

These private registry comments do not override the public application API's
reserved-key rules. No registry field was changed. Runtime parsing, defaults,
per-app eligibility and active selection remain unverified; short rows also
exist, so columns cannot be treated as uniformly populated configuration.
No provider URLs or other registry values were fetched.

Targeted lb6wk strings identify `lge_NetCastSetAppMode` (file offset `0x2e8d8`),
`BROWSER_SIG_EXECUTEAPP` (`0x327b0` context), and a missing `BROWSER_APP_URL`
diagnostic (`0x31c70`). These are application-mode leads, not documented JavaScript
methods or an execution recipe.

More concrete native key-path candidates exist in the selected libtv:

| Static evidence | Interpretation and limit |
| --- | --- |
| `BROWSER_GetMappingKey` at `0x1c714`, `BROWSER_GetMappingKeyForFullBrowser` at `0x1c880`, and distinct mapping tables | Separate mapping code/data exists; its active mode and remote-to-DOM mapping have not been fully decoded |
| `TV_BB_KeyEventCallback` at `0x125c4` calls `BROWSER_GetMappingKey` at `0x127c0` | Corroborated native callback-to-mapper edge |
| That callback calls `checkNativeHandleKey` at `0x12b10` and `TV_CMN_SendKeyEventToBrowser` at `0x12b50` on a branch | A conditional forwarding path exists; not every physical key necessarily reaches a page |
| lb6wk `key_press_event_cb` at `0x1cbcc` | Native callback exists; two inspected indirect calls resolve to debug-observer/processor function-pointer relocations, not proof of DOM dispatch |

See [app-lifecycle.md](app-lifecycle.md) for the separately verified
framework-to-procmgr input-manager chain. Native input state can affect cursor
and remote handling beyond the page, so these findings do not justify invoking
private APIs to force keyboard delivery.

## Packaged execution result and remaining comparison

**CONFIRMED (documentary):** LG documents DOM key handling in the application runtime. **CONFIRMED (owner, APP-001):** after entry correction and explicit source re-upload, the official USB-packaged launcher displays and arrows/OK navigate it. Opening and movement are slow. The successful package's engine identity, viewport and detailed key-event trace were not captured; ordinary-browser UA results must not be transferred to it. See [app-deployment.md](app-deployment.md).

The legitimate packaged execution route is therefore demonstrated for this build. Internal entitlement semantics and independent native ELF admission are not established by that success. Future focused comparisons can record runtime identity and key events while preserving Home/Exit; no private input-mode call is required by the current result. The immediate owner-assisted priority is comparing the lightweight launcher candidate against the slow baseline, rather than repeating the already resolved black-screen experiment.

## Experiment record

- **Objective:** distinguish Internet and application browser paths and identify
  concrete input-boundary evidence.
- **Hypothesis:** the observed cursor-oriented Internet context differs from
  the runtime used for integrated NetCast web applications.
- **Environment:** official static package selections and existing physical
  probe reports; macOS host tools only.
- **Procedure:** selectively copy two scripts, Internet manifest and browser
  registry; hash them; correlate existing service/system registries; inspect
  bounded ELF metadata, selected strings and key-path disassembly.
- **Expected:** identify executable selection and distinguish evidence from
  unsupported command-line/native execution assumptions.
- **Observed:** Internet manifest selects the Chromium wrapper; its forced UA
  matches observed tokens; separate lb6wk stack has app-mode and key-path leads.
- **Conclusion:** the runtime distinction is substantially corroborated;
  custom-app key delivery and the exact live renderer remain unproven.
- **Risks:** accidental script execution, disclosure of profile data and
  interpreting private settings as public APIs; avoided by static inspection
  and selected metadata. No live profile or device data was read.
- **Next step:** complete focused browser event testing and legitimate packaged
  app availability; compare contexts only after a viable deployment route exists.
