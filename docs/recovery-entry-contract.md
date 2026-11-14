# Recovery entry: shared initializer and updater dependencies

Date: 2026-11-14. **Bounded firmware-static findings, independently reviewed.** Question: does the selected update-mode initializer demonstrate an updater entry that survives failure of the ordinary launcher or root filesystem?

**Result:** this slice establishes neither independent recovery nor a complete successful updater launch. The dynamic `lginit_app` contains an SWU-specific setup table and attempts to configure the ordinary `procmgr` path for update mode. It also contains shared mount/relaunch code, but its linked `main` selects a different phase through a nonzero imported-function pointer. The static `lginit` entry was not traced here. A further concrete limitation appears in the dynamic SWU branch: its service-list environment assignment uses a 32-byte formatting capacity for a 42-byte literal and does not check truncation. Do not promote intended service-list selection to a demonstrated successful launch.

This refines the dependency question in [recovery](recovery.md) and the [independent boot review](claude-boot-review.md), without repeating the already-established [boot selector](boot-selection.md) or [kernel init order](kernel-init-selection.md). Physical entry controls, active state and verified recovery remain **PENDING**.

## Input and bounded evidence

Only existing selected official inputs and inventories were read. No extraction, credential database, TV/network/IPC, target execution/emulation, system change or Git operation occurred.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `firmware/lab/lgin-selected/lginit_app` | 29816 | `a5bd53970c284498faa3a6c4eeccf479c1a411a10650658b02b86f44f346172f` |
| `firmware/lab/lgin-selected/lginit` (hash/symbol metadata only) | 512800 | `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c` |

Six exact captures total **3,440 bytes**, including their literal pools, all from `lginit_app`:

| Function | Half-open linked range | Bytes |
| --- | --- | ---: |
| `main` | `0x92e4..0x966c` | 904 |
| `sys_get_swumode` | `0x9b60..0x9c30` | 208 |
| `sys_swue_init` | `0x9c30..0x9d80` | 336 |
| `sys_mount_init` | `0x9d80..0xa3c4` | 1604 |
| `sys_create_root` | `0xa690..0xa728` | 152 |
| `system_fork` | `0xa3c4..0xa4b0` | 236 |

Additional bounded metadata: the 240-byte SWU table, 168-byte ordinary table, three dispatch pointers and their selected technical literals. No full mount/environment dump was produced. The static file did not expose the requested `main`/`sys_swue_init` symbols in its inspected symbol tables; the approved symbol-bounded extension stopped there. Similar strings or function names do not prove equivalent control flow between the two executables.

Ignored `artifacts/recovery-entry-contract/` contains `capture.py`, six JSON/text pairs, `metadata.py`, `selected-data.json`, `static-symbols.json`, verification and a hash manifest. Reproduce with `PYTHONPATH=. python3 artifacts/recovery-entry-contract/capture.py` and then `metadata.py`. The reviewed host LLVM tool hash is `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Code addresses map to file offsets by subtracting `0x8000`; data addresses use their actual ELF LOAD mapping. Literal pools are data, not executable evidence.

## Phase selection prevents a naive initial-boot inference

At `0x9310..0x9320`, main tests a word from literal `0x9624`. In this linked file it is nonzero `0x9128`, the PLT entry for `dbgfrwk_init`, with no relocation at that literal. The nonzero branch goes to `0x9520`, through debug initialization and back to `0x9334`. Therefore the direct file-backed path bypasses the nearby `APP_START` test and initial-mount branch. Runtime import resolution and actual startup are unobserved; no claim that weak-symbol naming alone selects the initial phase is made.

The alternative code, reached by a zero pointer and absent `APP_START`, calls `sys_get_swumode`. That helper reads up to 1,024 bytes from `/proc/cmdline` and looks for the seven bytes `swumode` without proving token boundaries; it returns a nonzero pointer after a match. Its caller only tests nonzero. Failure to open returns zero. This is shipped parsing code, not a reading of the owner's command line.

In that alternative block, a match writes `SWU_MODE=ON`, calls `sys_swue_init` at `0x95b0`, then **also calls** `sys_mount_init` at `0x95b4`. No match calls `sys_mount_init` at `0x9614`; both paths join at `0x95b8`. Later `0x95f0..0x95fc` attempts `/lg/lginit/lginit_app` via `system_fork` and enters a wait loop. The calls' presence is confirmed; reachability of this initial phase from the static `lginit` is unresolved here. Consequently this is not an independently established kernel-to-updater chain.

## SWU-specific setup is not a completed recovery environment

`sys_swue_init` walks two 24-byte-record tables. Operations return zero to advance immediately; nonzero prints a diagnostic and then advances anyway (`0x9c88..0x9cc0`, `0x9d14..0x9d4c`). It attempts a directory-creation command and returns zero without checking that command's status. No failure-abort/recovery-success contract is established.

Dispatch pointers at `0xaa20` are: type 0 → imported `mount`, type 1 → `0x9868`, type 2 → `0x9748`. The latter two helper bodies were not inspected; do not equate their table names to proven partition selection or successful mounting.

Selected SWU table declarations include:

| Type | Source | Destination | Other declared fields |
| --- | --- | --- | --- |
| 1 | `model` | `/mnt/lg/model` | `squashfs` |
| 1 | `swue` | `/mnt/swue` | `squashfs` |
| 0 | `/mnt/swue` | `/mnt/vendor` | flags `0x1000`, null filesystem |
| 0 | `/mnt/swue/lib` | `/mnt/lg/res/lglib` | flags `0x1000`, null filesystem |
| 0 | `/mnt/swue/pqldb` | `/mnt/pqldb` | flags `0x1000`, null filesystem |
| 0 | `tmpfs` | `/usr/local` | `tmpfs`, `size=1M` |
| 2 | `data` | `/mnt/lg/cmn_data` | `ext4`, flags `0x400` |

The type-0 source/target aliases are consistent with bind-mount requests; no mount was actually performed. The shared `sys_mount_init` then contains another table walk with the same dispatch/error-and-continue structure. Its `lg_mounttbl` entry at `0x16bf0` declares **`opensrc` → `/usr/local`, `squashfs`, type 1**. Thus SWU setup is not documented here as a substitute for every shared image: in the initial-phase code, common initialization follows it and includes this shared source declaration. Whether helpers skip, remap or successfully overlay any mount remains unproven.

## Dynamic process launch and a truncated service-list assignment

After the nonzero phase branch, `IS_NFS=YES` follows a separate procmgr launch/sleep path. In the ordinary non-NFS path, main tests `SWU_MODE` against `ON`, including the terminator (`0x9488..0x94b8`). Both the matching and nonmatching branches attempt **`/usr/local/bin/procmgr`**, at `0x94f4` and `0x9508` respectively. This is a shared executable path, not a direct early invocation of `SWUE`.

The matching branch stores two formatted environment pointers. At `0x94d4..0x94e4`, `snprintf` receives capacity **32** and the literal `PM_SVC_LIST=/usr/local/bin/svclist_swue.rc` at `0xa9bc`, which is **42 bytes** excluding NUL. Under the standard imported `snprintf` contract, the buffer contains at most 31 non-NUL bytes: `PM_SVC_LIST=/usr/local/bin/svcl`. The return value is ignored before the pointer is installed at `0x94e8`. This is an apparent truncation in this selected branch; the actual libc result, procmgr interpretation/fallback and physical updater behavior were not observed. Earlier string-only evidence of the full path must not be treated as successful selection by this call.

`system_fork` confirms `fork` followed in the child by `execv` for the NFS condition, otherwise `execve` with the compiled environment vector. Negative fork returns go back to the caller; failed exec prints `perror` and returns from the helper. The main call sites do not establish a successful exec handshake. A PID/result, wait loop or diagnostic is not proof that the target started or that a usable update environment exists.

The prior ELF inventory independently establishes `/lib/ld-linux.so.3` and dynamic dependencies for `lginit_app`; procmgr also uses vendor userspace dependencies. Those are requirements of loading these particular binaries, not proof of which physical root partition supplies them. No independent initial root, alternate loader or fallback mount is established by this slice.

Independent review reproduced all six ranges and verified 860 ARM words, 205 direct branch destinations, 35 imported-call resolutions, both input hashes and the selected tables/literals. The truncation and phase claims remain scoped to this artifact and branch; no physical update failure was observed.

## Failure-domain conclusion and next evidence

**LIKELY, conditional architecture implication:** a stock Home/RELEASE failure could differ from failure of the shared initializer, loader or procmgr, because a separate SWUE executable/service declaration exists. **PENDING:** a usable entry into that service set, a complete service-list assignment, and all required images/mounts when the ordinary system is damaged. This analysis cannot establish recovery after rootfs, kernel, lginit or partition-map failure.

The next useful evidence is the exact static `lginit` phase entry and its corresponding service-list formatting call, obtained through a separately justified address map/function boundary—not a broader scan or running this code. Then trace the named-partition mount helper only if that comparison supports the shared-image question. Physical active banks, boot-console availability, owner-accessible entry controls, independent media, restoration verification and power-loss behavior remain unresolved. No persistent experiment or updater invocation follows from these findings.

Experiment RECOVERY-ENTRY-001: **Objective/hypothesis:** distinguish a separate update service set from an independently bootable recovery environment. **Environment/procedure:** pinned selected official initializer, six bounded host disassemblies, two technical tables and import/argument/branch review. **Expected:** a proven independence edge or concrete shared prerequisites/unresolved transitions. **Observed:** phase-sensitive shared procmgr launch; conditional SWU preparation rejoins common setup; continuing error paths; apparent service-list truncation. **Conclusion:** no independent recovery proof, with specific phase/formatting/mount questions for the next slice. **Risks:** conflating dynamic/static twins, literal intent with actual buffers, mount attempts with success and update availability with recovery; all remain explicitly separated. **Next step:** the targeted static-entry anchor and phase comparison, separately scoped; independent review of this slice passed.
