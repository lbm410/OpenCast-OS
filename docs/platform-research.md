# OpenCast OS: boot, platform, and shell replacement

Research date: 2026-11-14. Level 0 documentary research. No code has been executed on the television. This note separates community precedents from evidence about the owner's unit. The subsequent local firmware triage is recorded in [firmware.md](firmware.md).

## Provisional technical conclusion

The first architecture to investigate is a custom shell that preserves the manufacturer's audiovisual services. A separable launcher process has not yet been demonstrated on the 47LA620S-ZA. Obtaining a root shell, running an ELF, or drawing on the screen would not establish that separation or the preservation of HDMI, tuner, audio, and suspend behavior.

The next useful result is a static inventory of the official firmware: container, partitions, init, main application, libraries, and interprocess contracts. A reversible Hello World deployment provides rendering and remote-input evidence, but does not solve automatic startup.

**CONFIRMED (device, self-reported):** the integration agent has received a UDAP announcement containing the exact model and firmware, `47LA620S-ZA/04.28.17`, together with `Linux/3.0.13`. The DLNA announcement instead contains `Linux/i686`. These observations are recorded in `artifacts/diagnostics/ssdp-retry.json`; descriptors are in `udap-description.json` and `dlna-description.json` in the same ignored directory. The banners are unauthenticated declarations, not physical CPU evidence. The contradictory architecture label must be resolved against firmware ELF headers or direct hardware evidence; do not select an x86 toolchain from the DLNA banner.

## Evidence and limits

| Status | Finding | Scope and evidence |
| --- | --- | --- |
| CONFIRMED (documentary) | LG publishes 04.28.17 and explicitly lists `47LA620S-ZA`. | [LG Croatia support](https://www.lg.com/hr/podrska/proizvod/lg-47LA620S.AEE), software section, dated 2019-04-11, displayed size 623.885K. Establishes declared applicability, not downloaded-file integrity, installed version, or a recovery mechanism. |
| CONFIRMED (documentary) | OpenLGTV maintains different tools for different generations. | The [project website](https://openlgtv.github.io/) distinguishes Saturn S6/S7, Broadcom 2010/2011, and webOS. An alternative rootfs for one generation does not establish LA620S compatibility. |
| CONFIRMED (documentary) | `RELEASE` is an actual executable name in older LG implementations. | [About_RELEASE wiki](https://github.com/openlgtv/wiki/wiki/About_RELEASE) describes closed source and NanoX in a historical context referring to the LH50. It does not identify the executable on our target. |
| CONFIRMED (documentary) | OPENRELEASE wraps RELEASE rather than replacing it completely. | [README](https://github.com/rtokarev/OPENRELEASE/blob/master/README) and [Makefile](https://github.com/rtokarev/OPENRELEASE/blob/master/Makefile): MIPS32 options and little-endian linking. Do not use these binaries on a hypothesized ARM platform. |
| CONFIRMED (documentary) | `lgmod_bcm` contains a BusyBox init → rcS → helper scripts → RELEASE chain. | [inittab](https://github.com/openlgtv/lgmod_bcm/blob/master/OpenLGTV_BCM-src/etc/inittab), [rcS](https://github.com/openlgtv/lgmod_bcm/blob/master/OpenLGTV_BCM-src/etc/init.d/rcS). This is modified code for older Broadcom hardware, not the original LA620S init. |
| CONFIRMED (documentary) | DirectFB does not imply a standard Linux framebuffer. | The [Broadcom rc.directfb script](https://github.com/openlgtv/lgmod_bcm/blob/master/OpenLGTV_BCM-src/etc/rc.d/rc.directfb) derives graphics memory from RELEASE process mappings and configures a devmem backend. It also changes state and terminates processes; it was only read. Do not copy it to the target TV. |
| CONFIRMED (documentary) | A community NetCast 4 configuration targets ARM Cortex-A9, little-endian, and soft-float ABI. | [netcast4_defconfig at a pinned commit](https://github.com/openlgtv/buildroot-nc4/blob/a8208332b85993ee65c7711010b0e405ff4861d2/configs/netcast4_defconfig), branch `lg`. It selects GCC 4.9.3, glibc 2.22, and a local `kernel-m13/linux-3.0.13` tree with `mt5398_smp_mod_fix_defconfig`. These are community build parameters, **not** verified installed-system versions. |
| CONFIRMED (documentary) | The buildroot-nc4 name does not guarantee that its current branch or release targets NetCast. | [Branches](https://api.github.com/repos/openlgtv/buildroot-nc4/branches) include `lg`, `master`, and `webos`; [releases](https://github.com/openlgtv/buildroot-nc4/releases) include webOS publications. Pin the commit and configuration before evaluation. |
| CONFIRMED (documentary) | The encrypted.at precedent concerns another device. | [Original article](https://www.encrypted.at/remote-root-shell-on-lg-tv-2013-netcast-models/): 55LB580V-ZM, firmware 04.04.27.01, MTK 5398. Its service-menu mechanism creates an unauthenticated privileged shell and is outside the authorized initial tests. |
| LIKELY | The target family has reusable components from the original system. | An inference from NetCast and the precedents; exact names, ABI, and responsibilities remain unknown. |
| HYPOTHESIS | The visual experience can be separated from essential TV logic. | Must be tested through static dependencies and later authorized observation. The system could instead contain a monolith combining UI and audiovisual control that requires further engineering to separate. |
| PENDING | SoC, RAM, verified kernel configuration, libc, bootloader, MICOM, partitions, GPU, launcher, and recovery mechanism for this unit. | The above sources and self-reported network banners cannot substitute for firmware examination and device evidence. |
| RULED OUT for direct use | Treating Broadcom/MIPS, webOS, or 55LB580V procedures as LA620S procedures. | Retained as historical evidence, not operational instructions. |

## Firmware: candidate tool and preliminary review

The README, headers, format selection, EPK2 code, build script, recent history, and public issues of [epk2extract](https://github.com/openlgtv/epk2extract) were reviewed. The format links below are pinned to `a0ccd8a4b4f48d05675a4cddd233f8780ee36767`. The tool has not been built or executed.

- [README](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/README.md): recognizes EPK1, EPK2, EPK3, and several filesystems. It is an extractor, not a guarantee of installable repacking. EPK2 and EPK3 introduce cryptographic requirements. Do not use its PVR features to circumvent DRM.
- [EPK2 header](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/include/epk2.h): defines version, OTA identifier, image table, signature, and platform/SDK version fields; PAK segments contain a model name and metadata. This is a parser reference, **not proof** that the 04.28.17 file uses exactly this layout.
- [EPK2 implementation](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/src/epk2.c): identifies headers and supports signature checking and decryption. Its signed-size check tolerates different lengths; a success message is not a substitute for auditing the format or trust chain.
- [build.sh](https://github.com/openlgtv/epk2extract/blob/a0ccd8a4b4f48d05675a4cddd233f8780ee36767/build.sh) has a Darwin branch using Homebrew/OpenSSL. Native compilation is worth evaluating, but current ARM64 compatibility is not established.
- Open issues consulted: [#137, false positive and segfault](https://github.com/openlgtv/epk2extract/issues/137), [#135, modern build failure](https://github.com/openlgtv/epk2extract/issues/135), [#52, ARM64 Linux build](https://github.com/openlgtv/epk2extract/issues/52). These are third-party reports, not locally reproduced failures. They justify resource limits, output auditing, and avoiding privileged execution.

The original's SHA-256 supports reproducibility but does not independently prove authenticity. Preserve the official URL, date, length, hash, and model/suffix mapping; separate originals from results and never execute extracted ELF files. Check format and available metadata before decryption; check sizes, paths, symlinks, and device nodes before extraction. Never store keys or credentials in Git or documentation.

## Dependency map to establish

This is an engineering investigation checklist, **not an observed diagram of the television**:

1. Boot: ROM/bootloader → boot configuration → kernel → rootfs → init. Obtain actual versions, signatures, devices, and scripts; do not assume U-Boot, CFE, Device Tree, systemd, or kexec support.
2. Hardware initialization: panel, backlight, GPU, audio, HDMI, tuner, and network. Identify the responsible modules, auxiliary firmware, services, and libraries.
3. Essential control: MICOM or auxiliary controller, power, watchdog, and remote input. Determine the owner of each protocol and whether it depends on the process drawing the UI.
4. Smart TV experience: locate the actual launcher, browser, application registry, resources, and IPC endpoints. Search for `RELEASE`, `lgapp`, init scripts, and graphics libraries as candidates, without assigning responsibilities based only on names.
5. Separation: determine which functions can remain operational while another graphics surface has focus. Do not terminate processes blindly to discover this.

Static inspection must record each ELF's architecture, endianness, ABI, interpreter, required libraries, and versioned symbols. Read scripts as data: never `source` them or run `ldd` on firmware binaries. Map artifact paths and hashes while avoiding configuration dumps containing secrets.

## Architectural alternatives

| Alternative | Current feasibility | Functionality / performance | Compatibility and recovery | Evidence required to advance |
| --- | --- | --- | --- | --- |
| A. Custom shell and launcher on original Linux | Priority HYPOTHESIS | Best initial prospect of preserving TV/HDMI and acceleration; coexistence and IPC costs unknown. | Requires verified ABI and graphics interface; ephemeral execution first. Automatic startup adds a separate risk. | Display UI, exit without side effects, control focus/remote input, and demonstrate that essential services remain operational. |
| B. Custom distribution on existing kernel and hardware components | HYPOTHESIS | Allows service reduction, but could break proprietary-library and power-management contracts. | Preserve sysroot, modules, and protocols. Do not replace libc or init based on assumptions. Independent recovery required. | Complete inventory and demonstrated reversible boot alternative; approved essential-function matrix. |
| C. Alternative Linux with adapted drivers | PENDING, high uncertainty | A modern kernel does not guarantee GPU, HDMI, tuner, or decoding support; acceleration and latency could worsen. | Needs board, memory, display, audio, and power support; GPL sources do not imply possession of every driver. | Recoverable laboratory boot and functional support for each subsystem. |
| D. Fully customized firmware | PENDING, experimental | Theoretical maximum control with maximum cost and risk. | Understand container, signatures, partitions, and recovery before writing anything. An official ZIP is not a full backup. | Verified recovery and specific authorization; root access is insufficient. |

Provisional decision: investigate A while keeping B/C/D open. Separate navigation and service logic from NetCast/native adapters. The UI must not advertise HDMI, power, or settings controls until a verified adapter exists. A future OpenCast supervisor would need a return path to the original system and safe failure behavior; no persistent hook will be designed before the actual init and independent recovery are understood.

## Documentary experiment PR-001

- **Objective:** determine whether the precedents establish that this unit's launcher can be replaced.
- **Hypothesis:** reusable community components exist, but there is no universal NetCast recipe.
- **Environment:** ARM64 Mac; read-only web and GitHub access, 2026-11-14. This documentary experiment did not contact the TV or download executables.
- **Procedure:** review the listed primary sources and compare families, architectures, branches, and each tool's scope.
- **Expected result:** identify useful starting points while avoiding incompatible procedures.
- **Observed result:** an EPK extractor and NetCast 4 configuration exist; OPENRELEASE is a MIPS wrapper, and the detailed scripts reviewed target older Broadcom hardware. The 04.28.17 filesystem tree and boot chain were not obtained in this experiment.
- **Conclusion:** comprehensive replacement remains a hypothesis. UI and essential-function separation must be demonstrated on the target firmware.
- **Risks:** confusing toolchain versions with original libc, inferring SoC from family names, turning historical documentation into flashing instructions, or trusting an unbounded extractor.
- **Next step:** the official original and bounded local triage have now been obtained in FW-001; see [firmware.md](firmware.md). Resolve the container layout before selecting an extractor/toolchain. In parallel, a reversible Hello World can measure browser and remote-input behavior without making boot decisions.
