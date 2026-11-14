# Firmware boot and shell dependency map

Updated 2026-11-14. All findings below are **CONFIRMED (static official-firmware evidence)** unless marked otherwise. They do not assert that every shipped branch or configuration is active on the owner's running unit. Firmware source hashes and extraction provenance are maintained in firmware.md and firmware-extraction.md.

## Executable baseline

The bounded `tools/elf_inventory.py` reader independently inspected the selected files, without running firmware or using `ldd`. Reports: ignored `artifacts/firmware-lab/root-elf.json` and `lgin-elf.json`.

| File in extracted tree | Static result | Dependency implications |
| --- | --- | --- |
| root-selected/bin/busybox | ELF32, little endian, ARM machine 40, EABI5 | Interpreter `/lib/ld-linux.so.3`; needs libm.so.6 and libc.so.6 |
| root-selected/lib/ld-2.12.2.so | ELF32 ARM, SONAME ld-linux.so.3 | Vendor loader available for ABI study; never execute it on the host |
| root-selected/lib/libc-2.12.2.so | ELF32 ARM, SONAME libc.so.6 | Versioned filename indicates 2.12.2; symbol/version inventory remains pending |
| lgin-selected/lginit | ELF32 ARM, no PT_INTERP or DT_NEEDED | Consistent with a statically linked init coordinator; behavior needs static investigation |
| lgin-selected/lginit_app | ELF32 ARM with vendor loader | Needs libdbgfrwk.so, libpthread.so.0, librt.so.1, libgcc_s.so.1 and libc.so.6 |
| base-selected/browser/bin/lb6wk | ELF32 ARM with vendor loader | Links WebKitGTK/GTK3, JavaScriptCoreGTK, DirectFB/Fusion and vendor libtv/libdvb/libncg_agent/liblgesec libraries |

ELF flags are 0x05000002: EABI5, with floating-point calling convention unspecified in the parsed flags. Do not promote a community soft-float toolchain configuration into proof of the vendor's complete ABI. This firmware evidence supersedes the DLNA i686 advertisement as evidence of the shipped userspace architecture; it is not an independent CPU/board inspection.

## Explicit script chain

`root-selected/etc/inittab` selects runlevel 3 and runs `/etc/init.d/rcS`. That script initializes virtual filesystems, derives BOOTDEV from the kernel command line (emmc or fallback nand), invokes checkroot.sh, and invokes executable `/etc/rc.d/rc.local`.

`rc.local` configures temporary files, network branches, conditional UBI and USB setup, and driver scripts `ins_drv.sh` and `ins_basic_mod.sh`. It extends LD_LIBRARY_PATH with vendor paths including `/mnt/addon/lib`, `/mnt/lg/res/lglib`, `/mnt/lg/local/lib`, and `/mnt/vendor`. In the `bootmode=auto` branch it changes into `/mnt/lg/lginit` and invokes `./lginit`.

Independent Claude review correctly notes that this call is foreground and the inspected inittab contains no respawn entry. Do not infer UI supervision from inittab alone: the subsequently inspected vendor service lists distinguish RELEASE and Home; see the service-supervision update below. The actual PID1 binary and its behavior remain under investigation: an sbin/init regular file is listed separately from BusyBox. Also reconcile rcS's ext2 `/dev/ram` remount with the SquashFS root package; a vestigial line or an intervening RAM-root construction is possible, neither proven.

The alternate branch contains development services and login commands. Their presence in a shipped script does not mean those services are exposed on this TV. Do not activate that branch or modify boot arguments as a diagnostic shortcut. The earlier network survey did not establish privileged access.

## Graphics and home application evidence

- `root-selected/etc/directfbrc` names the SaWMan window manager (`wm = sawman`), an ARGB layer, 960×540 layer size and backvideo buffer mode. This is shipped configuration, not a measurement of active resolution or proof of a usable framebuffer/GPU API.
- `root-selected/etc/sawmanrc` contains border configuration. Window ownership, lifecycle and vendor graphics integration are unresolved.
- `base-selected/addon/contents/system/home/manifest.xml` identifies alias home, app ID 70004, app type 11, file Home.swf, and capability resolution 1280,720. This is evidence of a Flash resource-based home application, not proof that replacing this file alone replaces the system shell or is accepted by integrity checks.
- The base image includes systemapps_launcher_su2.xml and systemapps_su2.xml registries with vendor input/settings/browser and media entries. Registry entries are not public callable control APIs.

The 960×540 graphics configuration, 1280×720 application manifest and physical browser viewport 1276×603 describe different layers/contexts. Do not choose the replacement's rendering resolution from any one of them without measuring the actual runtime.

The separately inventoried browser (`artifacts/firmware-lab/browser-elf.json`) declares 50 DT_NEEDED libraries, including `libdirectfb-1.2.so.0`, `libwebkitgtk-3.0.so.0`, `libgtk-3.so.0`, `libtv.so` and `libdvb-1.0.so.0`. These are actual dynamic dependencies, stronger than loose string matches. SONAME versions are ABI identifiers, not complete source release versions. Vendor browser/native integration exists, but its private APIs and safe standalone startup contract remain unknown.

The selected lginit contains `lgapp_xip` at file offset 0x60ef8 and `/mnt/lg/lgapp` at 0x60f04; lginit_app contains corresponding strings at 0x2b98 and 0x2ba4 and execv/execve symbol strings. These are **HYPOTHESIS leads**, not a verified control-flow edge. Bounded string reports are in ignored `artifacts/firmware-lab/lginit-startup-strings.json` and `lginit_app-startup-strings.json`. Native disassembly/cross-references are needed before asserting exactly how the executable is selected or supervised.

## Architecture consequences and open dependencies

Keep the shell-over-vendor-services strategy as the leading hypothesis. Separate at least the resource/application registry layer, lginit coordinator, native application executable, and graphics/window management before proposing a replacement boundary. A valid next step is static examination of the decoded lgap executable's dependencies and lginit references, followed by documented IPC ownership. It is not safe to infer that killing a process preserves tuner, sound, power or watchdog operation.

PENDING: active boot mode/storage, true partition map and redundancy, kernel configuration, runtime memory, graphics initialization and exclusive ownership, input arbitration, service IPC, watchdog policy, firmware trust enforcement, and independently demonstrated recovery. No native launch or persistent modification is authorized by these static findings.

## Experiment BOOT-001

- Objective: establish actual shipped userspace ABI and the explicit startup chain.
- Hypothesis: selected files from verified firmware packages expose the init and graphics boundaries without TV access.
- Environment: Apple Silicon host; selected regular files copied by the firmware lab; no target execution.
- Procedure: run `python3 -m tools.elf_inventory --tree firmware/lab/root-selected` and the same command for lgin-selected; inspect the named init/config/manifest files as text.
- Expected: bounded metadata and a traceable script call chain, with unresolved proprietary transitions marked.
- Observed: five ARM32 EABI5 ELF records, no parser errors; inittab → rcS → rc.local → conditional lginit invocation; SaWMan/DirectFB configuration and Home.swf manifest found.
- Conclusion: native userspace research can now target the shipped ARM ABI, while launcher separability and recovery remain unproven.
- Risks: treating inactive vendor branches or filenames as runtime truth; avoided by evidence labels and no execution.
- Next: inspect decoded lgap and lginit dependency/IPC clues and reconcile independent Claude review.


## Service-supervision update

[Selected service lists and procmgr analysis](service-supervision.md) now supply a concrete boundary: the normal list declares `/mnt/lg/lgapp/RELEASE` under `reboot`, and a separate `fxui .../home/Home.swf --service lg.service.normal.home2 --auid 11174` under `respawn`. The SWUE list declares a separate `/mnt/swue/SWUE` executable. The supplied comments define these policies for normal/abnormal termination, while bounded procmgr disassembly identifies additional conditions; do not equate closing Home with exiting procmgr or rebooting the TV. Actual active list selection remains unobserved.

The Home service AUID string `11174`, interpreted as hexadecimal, equals decimal70004 in the selected Home manifest. This numerical match supports a common identifier mapping; argument parsing and universal identifier semantics still require tracing.

Next static work targets appctrl/fxui registration, focus and lifecycle rather than replacing RELEASE. Original startup declarations and Home assets remain untouched on the TV.
