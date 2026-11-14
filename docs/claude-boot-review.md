# Independent boot and recovery review — firmware 04.28.17

Revision 5, 2026-11-14 (task CLAUDE-001). This revision rewrites the body against the evidence
available now. Earlier revisions contained inferences that later traces overturned; they are listed
in "Superseded statements" at the end and must not be quoted from older copies.

Scope: the boot chain, process supervision, launcher separability and recovery assumptions for
OpenCast OS on the owner's LG 47LA620S-ZA, as far as the official 04.28.17 update image shows.

Boundaries. Everything labelled *static* comes from files of the official update read on the host
(Level 0): nothing was executed, loaded or emulated, and this review made no television, LAN or
Git operation. Static evidence describes the shipped image; it does not show which branch, bank,
service list or environment is active on the owner's unit. *Physical* observations are the
owner-assisted Level 2 experiments recorded in `docs/experiments.md`; this review cites them and
adds none. The firmware is built for the MediaTek MT5398 family (static branding strings such as
`mt5398_LGE_linux` and the package label `DVB-BB-MTK5398`); the processor in the physical set is
unobserved.

Labels: **CONFIRMED** (static, or physical where stated), **LIKELY**, **HYPOTHESIS**, **PENDING**.

## Sources

| Source | What it supplies | Who verified |
| --- | --- | --- |
| This review's own reads of `kern.decoded` (`8d9e62e1e5272bdb`), `RELEASE.elf` (`e37751653de2b797`), `lginit` (`0c2cb0c07849d4fe`), `boot.pak` (`458d1fba9fb69631`), `part.pak` (`7289a31801401caa`), root scripts and listings | Strings with offsets, partition table, script text, inventories | Reviewer, by bounded scripts; offsets below were re-read by the reviewer |
| Four read-only research sub-agents of the review session (first pass) | `lginit` disassembly, `RELEASE` symbol grouping, launcher inventories, signature re-check, public sources | Single source unless a row says "re-verified" |
| `docs/bootloader-analysis.md`, `tools/lzhs_inspect.py` | Reviewed decode of both `boot.pak` stages | Integration lead; reproduces the hashes `256e09dbb59a8ecd…` and `11d6616752416c42…` first obtained by a sub-agent's scratch decoder |
| `docs/boot-selection.md` | Boot-stage command-line builder and update-mode selector, by control flow | Integration lead's agents |
| `docs/kernel-init-selection.md` | Kernel init candidate order, by control flow | Integration lead's agents |
| `docs/service-supervision.md`, `docs/app-lifecycle.md` | Service lists, restart policies, `procmgr`/`appctrl`/`fxui` roles | Integration lead's agents |
| `docs/partition-layout.md`, `docs/firmware-extraction.md` | Partition map, EPK2 structure and signatures | Integration lead's agents; partition split re-counted by the reviewer |

Where a row below rests on another report, it says so; this review has not re-derived those traces.

## Boot dependency matrix

Static evidence for the 04.28.17 image. "Runs on the unit" is PENDING for every row.

| # | Stage | Depends on | Starts or provides | On failure | Label and source |
| --- | --- | --- | --- | --- | --- |
| 1 | First boot stage, `boot.pak` 0x0–0x44ef (`MTK/DTV/ROMCODE/MSDCBOOT/V01.00` at 0x100) | `boot` partition, single copy at eMMC offset 0 | Unpacks the next stage (`LZHS ok` / `LZHS failed`, `not secure loader`) | Not traced | Strings CONFIRMED static (reviewer) |
| 2 | Loader stage, LZHS segment at `boot.pak` 0xA040 (337,704 B decoded; `MT5398 Boot Loader` at 0x3e041) | Stage 1 | Hands over to stage 3 | Not traced | Decode CONFIRMED (`bootloader-analysis.md`); behaviour PENDING |
| 3 | U-Boot 1.3.4 stage, LZHS segment at 0x80000 (545,624 B decoded) | Stage 2; environment (`env_nvm` path LIKELY, compiled fallback exists) | Builds the kernel command line; appends `init=/sbin/init` **only if** `bootmode` equals `nfs`; appends `swumode` when a stored selector is set; `bootm` | Not traced | Control flow CONFIRMED static (`boot-selection.md`); stored environment and selector state PENDING |
| 4 | Kernel, Linux 3.0.13 (`kern.decoded`) | Command line from stage 3 | Mounts the root and the `lginit` file system (`VFS: Mounted lginit.` 0x44cb5b); selects the first user program in this order: retained `rdinit=`/`/init` candidate, `init=` candidate, `/mnt/lg/lginit/lginit`, `/bin/sh` | Each failed candidate falls through to the next; after `/bin/sh`, `No init found` | Order CONFIRMED static by control flow (`kernel-init-selection.md`); strings re-read by the reviewer |
| 5 | `lginit` (`lgin` image; static twin of `lginit_app`) | Kernel-mounted `/mnt/lg/lginit` | Mounts the other vendor partitions by name; re-executes itself once; forks `/usr/local/bin/procmgr`, with the update-mode service list when `swumode` was passed | When the waited `procmgr` exits: reads `/proc/sys/kernel/panic`; value `1` → reboot, otherwise sleeps | Control flow CONFIRMED static (one sub-agent's disassembly; strings re-verified). **LIKELY the normal first user program** (see §1) |
| 6 | `procmgr` (`open:bin/procmgr`) with a service list | `lginit`; `svclist.rc`, `svclist_nonsmart.rc` or `svclist_swue.rc` | Starts and supervises the declared services with per-service restart policies | Per policy: `respawn`, `respawnalways`, `oneshot` or `reboot` | Declarations CONFIRMED static (`service-supervision.md`); which list is selected PENDING |
| 7 | `RELEASE` (`/mnt/lg/lgapp/RELEASE`, 23.6 MB) | `procmgr`; vendor libraries; contains GPU/DTV module-loading command strings (execution untraced) | Broadcast/TV service: tuner, audio, HDMI/CEC, panel, MICOM, native menus | Declared policy `reboot`: abnormal exit reboots the set | Declaration CONFIRMED static (`service-supervision.md`); contents by symbols and strings (reviewer and sub-agent) |
| 8 | `fxui …/home/Home.swf` (service `lg.service.normal.home2`) and other `fxui` services | `procmgr`, `appctrl`, framework libraries | Smart Home surface as a **separate process** | Declared policy `respawn` | Declaration CONFIRMED static (`service-supervision.md`, `app-lifecycle.md`) |
| A | Alternative entry: `/sbin/init` (sysvinit-2.86) → `inittab` → `rcS` → `rc.local` | An `init=/sbin/init` argument (the `nfs` mode, or a stored `bootargs` containing it) | With `bootmode=auto` `rc.local` runs `./lginit`; otherwise a development branch | `inittab` has no respawn entry | Script text and binary CONFIRMED static; **not shown to run on the default path** |

## 1. Boot chain

- **First user program.** With the boot stage's compiled defaults — `bootmode=auto` (0x7d0e5) and
  an empty `bootargs=` (0x7cfe8) in the decoded second stage — no `init=` argument is produced,
  because the dedicated append is conditional on `nfs` (`boot-selection.md`). The kernel then
  tries, in order, a retained `rdinit`/`/init` candidate, an explicit `init=` candidate,
  `/mnt/lg/lginit/lginit` (0x44c63f) and `/bin/sh` (0x44c655) (`kernel-init-selection.md`). The
  stock names `/sbin/init`, `/etc/init` and `/bin/init` occur nowhere in the kernel image as
  NUL-terminated strings (reviewer's search; the same report confirms it). `lginit` itself carries
  the mount vocabulary of a bare system (`proc` 0x60fb8, `tmpfs` 0x614fc, `devpts` 0x61518,
  `sysfs` 0x6152c) and never returns from its exit handler. **LIKELY:** on the default path
  `lginit` is the first user program and PID 1. **Not established:** whether an early `/init`
  exists in the initial file system (it would be tried first), what the stored environment of the
  unit contains, which kernel bank runs, and the PID 1 actually running. `lginit` must not be
  described as the kernel's first candidate: it is the third.
- **The sysvinit script chain is an alternative entry, not the demonstrated default.**
  `/sbin/init` is sysvinit-2.86 (`artifacts/partition-analysis/init-markers.json`); `inittab`
  (`6727ed7b…`) has only `id:3:initdefault:` and `si::sysinit:/etc/init.d/rcS`; `rcS`
  (`c729c096…`) calls `rc.local` (`669a1ae1…`), which runs `./lginit` in the foreground when
  `bootmode=auto` (L125–126) and a development branch otherwise (L128–134). All of that is shipped
  script text. Unless `init=/sbin/init` is supplied, the evidence above gives no reason to think
  these scripts run, and this review does not claim the opposite either: another component could
  still invoke them (`kernel-init-selection.md` makes the same reservation).
- **Consequences if the scripts do not run on the default path** (LIKELY, following from the
  above): the `rcS` remount of `/dev/ram`, `echo 1 > /proc/usercalls`, `checkroot.sh` and the
  `ins_*` module scripts are inactive, and `lginit` performs the mounts. Independently of that,
  the module scripts reference `/basic/modules/*.ko`; none of the 15 referenced file names occurs
  in the seven inventoried images, `/basic` is mounted only by a UBI script gated on a non-eMMC
  boot device, and `part.pak` has no `basic` entry (reviewer's trace). Whether the corresponding
  drivers are built into the kernel is a HYPOTHESIS from string presence only.
- **`lginit` and `procmgr`.** The reviewed `lginit` trace identifies exec targets for itself as
  `/lg/lginit/lginit_app` (0x60cd4) and `/usr/local/bin/procmgr` (0x60cf4). The reported mount path uses compiled-in tables; the inspected slice identified no
  dm-verity, hash or signature step and no `RELEASE` reference. This is not an audit of all
  integrity enforcement or indirect calls. With `swumode` on the command line it sets `SWU_MODE=ON` (0x60cb8) and
  `PM_SVC_LIST=/usr/local/bin/svclist_swue.rc` (0x60d1c). It does not restart `procmgr`: its exit
  handler reads `/proc/sys/kernel/panic` (0x60c78) and either reboots or sleeps. Source: one
  sub-agent's ARM disassembly; the reviewer re-verified the strings, not the control flow.
- **Supervision lives in `procmgr`.** The normal list declares `RELEASE` in the pre-TV group with
  policy `reboot`; `lginput`, `appctrl` and others with `respawn`;
  `fxui …/home/Home.swf` with `respawn`; the two browsers with `respawnalways`
  (`service-supervision.md`, `svclist.rc` lines 80–215). These are declarations in a shipped file.
  The policy text says `reboot` means a reboot after abnormal termination. So, by declaration, a
  `RELEASE` that crashes at start would reboot the set repeatedly, while a crashing Home would be
  restarted without a reboot. Runtime behaviour, the selected list and the low-memory conditions
  noted in that report are PENDING.
- **Watchdog.** No root script and none of the three service lists mentions a hardware watchdog.
  The second boot stage contains `Enable Watchdog` (0x6ea15); `RELEASE` and `SWUE` define
  `API_DDM_INIT_WATCHDOG` and reference MICOM watchdog functions; the kernel has `RT Watchdog`
  (0x453b7c). Who arms and who feeds it is PENDING. A software reboot policy and a hardware
  watchdog are different mechanisms.

## 2. Launcher separability

**Current reading: a process boundary for the Smart Home surface exists in the shipped
configuration; an equivalent boundary for native TV menus and overlays has not been established.
Neither observation demonstrates that a replacement is feasible.**

- **Home is a separate, restartable process.** `svclist.rc` declares
  `fxui /mnt/addon/contents/system/home/Home.swf` as its own service with `respawn`, after
  `RELEASE` and `appctrl` (`service-supervision.md`); `appctrl` sends execution, focus and exit
  requests to `procmgr`, and `fxui` registers and reports readiness (`app-lifecycle.md`).
  `Home.swf` (1,619,496 B, with 14 card movies) is content for that `fxui` host; its manifest gives
  `app_id=70004`, `app_type=11`, `resolution=1280,720`. Earlier revisions of this review said the
  UI was not an isolable process. That was wrong for Home: the declarations show the opposite.
  What remains unproven is everything a replacement would need: an admitted way to start another
  client, its window and input contract, and a return path (`docs/native-entry-contract.md`,
  `docs/native-admission.md`).
- **The reduced list is evidence that the TV service set is designed to run without Home.**
  `svclist_nonsmart.rc` keeps `RELEASE`, `appctrl` and input services and comments out the Home
  block and the browsers (`service-supervision.md`). It is a shipped variant, not a tested
  configuration of this unit, and nothing here proposes selecting it.
- **`RELEASE` still combines native UI code with hardware control.** In its dynamic symbol table
  the same image defines menu and widget families (`UI_SVC_WIDGET_*`, `MENU_*`) and tuner, audio,
  HDMI/CEC, panel and MICOM families (for example `DDI_MICOM_CancelPowerOff` at 0x35b0b8,
  `API_DDM_INIT_WATCHDOG` at 0xd4e374). Counts by name prefix come from one sub-agent; they show
  what is linked into one image, not what each function does. `RELEASE` also contains the commands
  `insmod /mnt/vendor/dtv_driver_adpt.ko panel_early_init=-1` (0x118d328),
  `pvrsrvkm.ko img_major=260` (0x118cd94) and `dc_cobra.ko img_major=261` (0x118cdb0); no other
  inspected component is shown to load the GPU and DTV modules. These are strings, not a traced
  call.
- **Surfaces differ in how they are shipped.**

| Surface | Shipped as | Coupling a replacement would meet | Label |
| --- | --- | --- | --- |
| Home, My Apps mini, voice | SWF movies run by separate `fxui` services | Host card and app APIs; `appctrl`/`procmgr` lifecycle; focus and key tables granted by the framework | Process boundary CONFIRMED static; contract PENDING |
| Other SWF system apps (34 of the 102 declared aliases ship SWF payload, e.g. the input list) | SWF content; host process per app not individually traced | As above; the input list only picks — the switch itself is a host function | Payload CONFIRMED static; hosting LIKELY `fxui` |
| Settings, quick menu, guide, programme list, banner, info, aspect ratio, SimpLink and similar (57 aliases) | Manifest and icons only, no payload | LIKELY drawn natively by `RELEASE`: no file or separate process to substitute | Payload absence CONFIRMED static; native drawing LIKELY |
| Volume, mute, no-signal and system pop-ups | Not in the app registry | LIKELY `RELEASE` on its own graphics plane (`API_DDM_GFX_EnableVirtualOSD…` 0xfda2f4) | HYPOTHESIS |
| Browsers | `/mnt/browser/run3556` (the tree that contains the WebKitGTK `lb6wk`) and `/mnt/webbrowser/run_webbrowser` (Chromium), both `respawnalways` services | Window and input granted through `libtv.so` → `liblgopenapi` for `lb6wk` | Declarations and imports CONFIRMED static |

- **Input.** Statically: `RELEASE` contains `/dev/uinput` (0xe84d30) and
  `…/micom/micom_uinput.c` (0xe84e00); `liblgopenapi` exports window key-table and
  key-dispatch functions; `lginput` is a separate `respawn` service. Physically: in HW-001 an
  ordinary page in the Internet browser received pointer clicks and no key events; in APP-001 the
  official packaged NetCast application received arrows and OK (owner-observed, slow). **The
  cause of that difference is not established.** Earlier revisions attributed it to the page not
  being a registered window; no evidence supports that specific explanation, and the packaged-app
  result shows only that a supported route delivers keys. `docs/browser-runtime.md` reports that
  the Chromium launch script forces a user agent matching the one the probe recorded, which
  identifies the browser involved, not the reason for the key behaviour.
- **Graphics configuration.** `directfbrc` sets `wm = sawman` and no `system =` line. The `open`
  DirectFB tree ships the `devmem` system module, a `gpuddi` graphics driver and the default
  window manager, with no input drivers; a browser-private tree in `base` ships `fbdev`, `devmem`
  and eleven input drivers. No `sawman` module appears in the seven inventoried images. Which
  modules any process loads is unobserved. Among the inspected programs only `lb6wk` declares
  DirectFB libraries; `fxui` declares EGL/GLES and PowerVR libraries (`docs/native-linkage.md`).

## 3. Recovery

**No recovery path for a non-booting unit is evidenced. A signed vendor update, a shell, or a
second copy of a partition does not amount to one.**

- **Update mode is a separate service set.** `svclist_swue.rc` declares
  `/mnt/swue/SWUE --service lg.service.special.broadcast` with policy `reboot`, in the place
  `RELEASE` has in the normal list (`service-supervision.md`). `SWUE` is its own 3.9 MB
  executable in the `swue` image, which also ships its own libraries, a copy of the DTV driver
  module and panel data. The boot stage reads a stored selector and appends `swumode`
  (`boot-selection.md`); `lginit` then starts `procmgr` with that list. So update mode, once
  selected, LIKELY does not need `RELEASE`. Earlier revisions said the updater lived in
  `RELEASE` and could not help if `RELEASE` failed; that is withdrawn.
- **What update mode still needs, and what is unknown.** It runs through the same boot stages,
  kernel, `lginit` and `procmgr`, and needs the `swue` image and the image that holds `procmgr`
  and the service lists (`open`). How the selector gets
  set — by `RELEASE`'s own update code (it contains `%s/LG_DTV` 0x122bd24,
  `/mnt/appstore/usbfile.epk` 0x122baf8, `Write partition to download area` 0x122d304 and the
  token `swumode` 0x118caa0), by the boot-stage `swumode [on/off]` command, or automatically after
  a failure — is PENDING. Whether it can be entered when `RELEASE` cannot start is therefore
  PENDING. Package verification, partition writes and power-loss behaviour are untraced.
- **Signatures.** All 118 segment signatures verify against the community-distributed
  `mtk5398.pem` (first by a sub-agent's standard-library check, then by the integration lead's
  `--verify-all` mode with a rejected mutation). That shows consistency with a key extracted by
  the community, using RSA-1024 and SHA-1. It says nothing about what the television verifies at
  update or at boot. The boot stages contain `not secure loader`, a `…should be verify before
  bootm` message and `fullverify`; 5,376-byte trailers occur in the inspected relevant package
  images, with the partition-table package treated separately. Their purpose and boot-time
  verification policy are PENDING; do not generalize the trailer to every package.
- **Partition redundancy is partial.** In `part.pak` (64 entries, eMMC), 20 names appear twice,
  the second copy marked unused: `rootfs`, `kernel`, `lginit`, `lgapp`, `base`, `swue`, `tzfw`
  and others. **`boot` is single-copy.** So are `partinfo` (with `mapbak`), `crc32info`, `model`,
  `cfginfo` and `logo`. Paired entries are not proof of automatic fallback; no bank-selection
  logic has been traced. Nine per-device partitions (`macadr`, `env_nvm`, `nvram`, `hdcp`,
  `widevine`, `cert`, `idfile`, `marlin`, `authcxt`) have no corresponding image in the inspected update packages. These packages do not
  supply a backup of this unit's original per-device contents; no restoration procedure is established.
- **A vendor update can itself rewrite the riskiest regions.** The package set includes `boot`,
  `tzfw` and `mico`. Whether a given update writes them depends on skip logic known only from
  strings.
- **`/bin/sh` as the kernel's last candidate is not a recovery procedure**: console reachability
  and usable input/output are unverified (`kernel-init-selection.md` states the same).

### What a recovery procedure would have to demonstrate

Evidence today is none for every line.

1. Demonstrated on this physical unit, not a sibling model.
2. Independent of every component being modified, including the boot stage it relies on.
3. Works with `RELEASE` not starting.
4. Works with `lginit`, the root image or the kernel not starting, if those are in scope.
5. Restores, or provably never touches, the per-device partitions, backed by a verified full
   backup of this unit.
6. Restores the single-copy regions.
7. Known behaviour for a same-version reinstall and for a version or OTA-ID mismatch.
8. Known boot-time verification policy for modified images.
9. Exercised end to end at least once from a deliberately induced, harmless failure state.
10. Entry condition reachable without the modified partition and without settings changed after
    the failure.
11. Covers MICOM and TrustZone firmware state, or proves them untouched.
12. Written down, with a success check and specific owner authorization.

### Failure modes by modification level

| Level of change | What must still work for the vendor update to be usable afterwards | Label |
| --- | --- | --- |
| Reversible page or packaged application (Level 2, owner-assisted) | Everything, unchanged | LIKELY unaffected; Home return observed from HW-001 and the black-screen APP-001 attempt; successful-build return/repeat still pending |
| File in a writable data partition | Boot chain through `procmgr` and the normal services; the inspected update has no matching data image; deletion/preservation by updater logic remains untraced | Absence from packages CONFIRMED static |
| Autostart hook | As above on every boot; a hook that makes `RELEASE` exit abnormally meets the declared `reboot` policy | LIKELY; hook location undefined |
| Replacing Home content or the `fxui` Home service | `RELEASE`, `procmgr`, `appctrl`; a failing Home is restarted by declaration, without a reboot | Declarations CONFIRMED static; integrity checks on content PENDING |
| Replacing `lgapp` (`RELEASE`) | Update mode, if it can be selected without `RELEASE` | PENDING |
| Replacing the root image, `lginit` or `opensrc` | Update mode shares these dependencies; only a boot-stage facility or the second bank could help, neither evidenced | Shared dependency CONFIRMED static |
| Replacing the kernel or `boot` | `boot` is single-copy; nothing shows a boot-stage load from external media | PENDING; highest risk class |

## 4. Open questions and static tests

1. What sets the update-mode selector, and can it be set when `RELEASE` cannot start? Trace the
   writer in `RELEASE`'s update code and in `libswu`; read the `swue` image's own service files.
2. Does the boot stage select between the two banks, and on what condition? Find the consumer of
   the `used` bits of the partition table.
3. What do the 5,376-byte trailers contain, and what reads them?
4. Who arms and feeds the hardware watchdog, and what happens to it under update mode?
5. Is there an early `/init` in the kernel's initial file system (it would precede `lginit`)?
6. Which service list does `procmgr` select by default, and from what input?
7. What are `tzfw`, `mico`, `crc3` and `mode`, and does a normal update write them?
8. For a native client: `docs/native-linkage.md` lists the 96 library names that are declared but
   not yet inspected, including the whole graphics stack.

## 5. Architecture implications

- The only route with physical evidence is the supported one: a reversible page or packaged
  application run with the owner (Level 2). It does not touch boot.
- The shipped configuration separates Smart Home from the TV service: Home is a `respawn`
  service hosted by `fxui`, and a reduced list without Home ships. That makes "a surface beside
  `RELEASE`" a reasonable thing to investigate. It does not make it available: admission, window,
  input and return contracts are open, and the native menus and overlays are LIKELY inside
  `RELEASE`.
- `RELEASE` should be treated as essential and kept running: hardware-control and native-UI
  symbol families coexist in it, its strings suggest display/DTV driver-loading responsibilities,
  and its declared policy is `reboot`. The string evidence alone does not establish those calls
  executing on the unit.
- No persistent or boot-affecting change is justified. `boot` is single-copy, per-device data is
  in no update package, and no recovery procedure meets any of the twelve criteria above.

## Superseded statements from earlier revisions

Kept so that older copies are not quoted. Each was this review's own error or over-reading.

| Earlier statement | Revisions | Why it is withdrawn |
| --- | --- | --- |
| PID 1 is sysvinit `/sbin/init`; the boot stage passes `init=/sbin/init` by default | 1–3 | The append is conditional on `bootmode=nfs`; the kernel's fixed fallback is `lginit` then `/bin/sh` |
| `lginit` is the kernel's first candidate | 4 (by implication) | A retained `rdinit`/`/init` candidate and an explicit `init=` candidate are tried first |
| The kernel's `init=` string is at 0x1ea2a | 4 | That offset is inside `rdinit=`; the registered `init=` string is at 0x1ea30 |
| The UI is not an isolable process; `RELEASE` includes the launcher | 1–4 | Home is a separate `fxui` service with its own restart policy |
| `procmgr` and the service lists are unexamined | 1–4 | Read and reported in `docs/service-supervision.md` |
| A UI that fails to start means a hang or a reboot | 1 | That was `lginit`'s reaction to `procmgr` exiting; per-service policy is in the service list |
| The USB updater is inside `RELEASE`, so a vendor update cannot recover a set whose `RELEASE` fails | 1 | `SWUE` is a separate executable with its own service list |
| The boot-stage decode is an unreviewed scratch result | 2–4 | Reproduced by the reviewed `tools/lzhs_inspect.py` with identical hashes |
| The ordinary browser page got no keys because it is not a registered window | 1–4 | No evidence for that cause; the packaged application does receive keys |
| DirectFB on this firmware is `devmem`-only | 1 | True of one tree; another ships `fbdev` and input drivers |
| The module scripts are no-ops and the drivers are built in | 1 | Path trace supports "no shipped file at the referenced path"; built-in drivers remain a hypothesis |
| `docs/platform-research.md` wrongly applies a Broadcom init chain to this unit | 2 | That document labels the example as older Broadcom code |
| "A/B redundancy exists for boot" (one sub-agent) | 1, corrected in 1 | `boot` has a single entry |
| The app experiment is a Level 0/1 activity | 1–4 | Owner-assisted execution on the television is Level 2 |
