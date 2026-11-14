# Native linkage: declared shared-library dependencies and missing providers

Updated: 2026-11-14. Level 0 only: local static reading of official firmware files already copied
into the ignored lab, plus name-level package listings. No firmware code was executed, loaded,
emulated or passed to `ldd`; nothing was extracted; no television or LAN contact; no credentials.
Task CLAUDE-003.

## Result

**CONFIRMED (static official-firmware evidence):** the fixed 19-file ELF sample in this report
declare 241 `DT_NEEDED` dependencies and 10 `PT_INTERP` interpreters, over 105 distinct names.
Only 9 of those names have a provider that was actually inspected. The other 96 names (208 of the
241 edges) are **listed-only**: a file of that name appears in a package listing, but the file is
not among this sample's inspected inputs. Later workstreams may inspect additional providers. No declared name is absent from every listing, and no name has
more than one inspected candidate.

For a nonpersistent native shell this means the missing evidence is not "the firmware lacks a
provider" but "the provider has not been inspected": the C runtime beyond `libc` and the loader,
the whole graphics stack, and most of the lifecycle and IPC libraries are known by file name only.

**A listing- or name-level candidate is not an inspected provider.** It may not be an ELF file;
its architecture, ABI, `DT_SONAME`, exported symbols and symbol versions are unknown. An inspected
candidate is still only a name-level match. **Nothing in this report shows that a native shell
would link, load or run on the television.**

The 19 files were chosen by several workstreams for other reasons; this is not a census of the
firmware, and later selections will change the counts.

## What the graph is and is not

Declared `DT_NEEDED` edges are one layer of what a process depends on.

- The tool does not reproduce the dynamic loader: no library search path or order, no
  `LD_LIBRARY_PATH`, no `DT_RPATH`/`DT_RUNPATH` or `$ORIGIN` expansion, no loader cache, no
  preloading, no secure-execution rules.
- It resolves no symbol, symbol version, relocation or TLS requirement.
- Libraries and plugins opened at run time (`dlopen`), configuration-selected modules, and
  services reached through inter-process communication are outside the graph. No output here is a
  complete dependency list.
- **A fully matched direct graph does not name every symbol provider.** The selected
  `libscf.so.0.0.0` declares only `libgcc_s.so.1` and `libc.so.6`, yet the file contains the
  import names `dbus_bus_get_private`, `dbus_bus_request_name` and `dbus_message_get_args_valist`
  (checked here as byte strings; the call analysis is in
  [native-bus-policy.md](native-bus-policy.md)). The library that defines those functions is not
  among its own declarations: it has to be supplied by whatever else the process loads. Any file
  can be under-declared in this way, so the `DT_NEEDED` closure of a library is not a link list
  for a client of that library.
- Several inspected candidates for one name are reported as `ambiguous`. The tool never picks one,
  and an ambiguous name adds no edge, cycle or dependent count.
- An in-image identity that the listing contradicts or cannot confirm never establishes a
  provider through a listing. Explicit contradictions are reported under
  `missing_evidence.contradicted_identities`; inconclusive states such as `no_inventory` and
  `listed` remain visible on the input but are not classified as contradictions. `DT_SONAME` and file-name matches do not depend on
  the listing and stay classified on their own, with the candidate's identity check shown.
- "Verified" means exactly one inspected file matched the name. It does not mean the loader would
  select it; where the same name is also listed elsewhere, the edge carries `listed_alternatives`.

Each declared name falls in exactly one category:

| Category | Meaning | Strength |
| --- | --- | --- |
| `local_soname` | one inspected file whose `DT_SONAME` equals the name | name recorded by the producer |
| `local_basename` | one inspected file whose file name equals the name; it has no or another `DT_SONAME` | file name only |
| `local_listed_link` | one inspected file reached because a listing entry of that name resolves, through symbolic links inside the same listing, to the file's declared in-image path; applies only when the listing confirms that identity in entry type and byte size (`listed_size_match`) | depends on the caller-supplied identity and the listing |
| `ambiguous` | more than one inspected candidate | not resolved |
| `listed_only` | no inspected candidate; a listing entry of that name resolves to a regular file | name exists; file not inspected |
| `unresolved` | no inspected or listed candidate | absent from the evidence |

## Evidence

Ignored artifacts: `artifacts/native-linkage/graph-r2.json` (330,370 bytes, SHA-256
`3edb29b552615314adbb65714b57654fdae899c95a3c918841f459c6f65635de`) and the explicit input list
`artifacts/native-linkage/inputs.list` (SHA-256
`40a97466d9108483e06b0debcbfbac800144df741cc468c2dfd2304f60c31aa4`). Regenerating the report from
that list, both as a module and in isolated mode, gives the same SHA-256.

`graph-r2.json` supersedes the first report `graph.json` (`704ba55bbf8dec94…`), produced before an
independent review found three defects in the tool (see Tool). A structural comparison of the two
reports shows additions only — two caveats, three `limits` fields, the
`contradicted_identities` list, an `identity_check` on each of the nine inspected candidates and
two summary counters. Every count, edge, category and annotation is identical, so the figures
below hold for both.

Package listings (name, size and mode only; SHA-256 first 16): `root` `5865504759e016f4`,
`base` `7c1a4c44895e7507`, `lgli` `49e77975d864f8e9`, `open` `e4c8085cb098a889`,
`vend` `8cbd68a5b848888a`, `lgin` `7147be4ed7a55e16`, `swue` `7a5dac79318e5ed0`, all under
`artifacts/firmware-lab/*-inventory.json`. No entry was ignored as malformed.

Inspected files. The identity is the package and in-image path supplied to the tool; 18 of 19
agree with the listing of that package in entry type and byte size. `lgap:RELEASE` has no listing,
so its identity is unchecked. Columns S/B/L/O count `DT_NEEDED` edges resolved by SONAME, by
basename, by listed link, and listed-only.

| Identity | Local path (under `firmware/lab/` unless noted) | Bytes | SHA-256 (first 16) | Type | DT_SONAME | NEEDED | S/B/L/O |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lgap:RELEASE` | `artifacts/boot-triage/decoded/RELEASE.elf` | 23,591,000 | `e37751653de2b797` | ET_EXEC | – | 43 | 1/2/1/39 |
| `open:bin/fxui` | `app-lifecycle/open/bin/fxui` | 1,878,212 | `98e05ccd63771c26` | ET_EXEC | – | 42 | 1/0/2/39 |
| `open:bin/appctrl` | `app-lifecycle/open/bin/appctrl` | 277,044 | `630bfe0e7ab3c93e` | ET_EXEC | – | 22 | 1/0/2/19 |
| `open:bin/procmgr` | `service-selected/open/bin/procmgr` | 435,528 | `00cc453a3dd9cdf2` | ET_EXEC | – | 18 | 1/0/2/15 |
| `swue:SWUE` | `service-selected/swue/SWUE` | 3,911,188 | `10fc93711d78bdab` | ET_EXEC | – | 32 | 1/0/2/29 |
| `base:browser/bin/lb6wk` | `base-selected/browser/bin/lb6wk` | 275,004 | `0b9f18180a95c6ad` | ET_EXEC | – | 50 | 2/1/0/47 |
| `base:browser/lib/libtv.so` | `base-api-selected/browser/lib/libtv.so` | 247,256 | `09138fc3920e4d3e` | ET_DYN | none | 10 | 1/0/1/8 |
| `base:addon/lib/libncg_agent.so` | `base-api-selected/addon/lib/libncg_agent.so` | 150,072 | `554e1189be94c89f` | ET_DYN | `libncg_agent.so.1` | 2 | 1/0/0/1 |
| `lgli:libafopenapi.so.0.0.0` | `app-lifecycle/lgli/libafopenapi.so.0.0.0` | 221,880 | `bbbfaa4c51c0fdb5` | ET_DYN | none | 3 | 2/0/0/1 |
| `lgli:libscf.so.0.0.0` | `scf-selected/lgli/libscf.so.0.0.0` | 24,704 | `4d5bc2e85b5413f1` | ET_DYN | none | 2 | 1/0/0/1 |
| `lgli:liblgopenapi.so.0.0.0` | `lgli-api-selected/liblgopenapi.so.0.0.0` | 1,323,828 | `538ec51bd5bee6c3` | ET_DYN | none | 3 | 2/0/0/1 |
| `lgli:libapiwrapper.so` | `lgli-api-selected/libapiwrapper.so` | 568,188 | `28ed343a42443bae` | ET_DYN | none | 2 | 1/0/0/1 |
| `lgli:libauitv.so` | `lgli-api-selected/libauitv.so` | 565,512 | `5edd456d20e02959` | ET_DYN | none | 3 | 1/0/0/2 |
| `lgin:lginit_app` | `lgin-selected/lginit_app` | 29,816 | `a5bd53970c284498` | ET_EXEC | – | 5 | 1/0/0/4 |
| `lgin:lginit` | `lgin-selected/lginit` | 512,800 | `0c2cb0c07849d4fe` | ET_EXEC | – | 0 | no interpreter, no dynamic dependencies |
| `root:bin/busybox` | `root-selected/bin/busybox` | 594,104 | `264a4085fbc8926d` | ET_EXEC | – | 2 | 1/0/0/1 |
| `root:sbin/init` | `root-review-selected/sbin/init` | 28,323 | `595696e55a908ccb` | ET_EXEC | – | 1 | 1/0/0/0 |
| `root:lib/libc-2.12.2.so` | `root-selected/lib/libc-2.12.2.so` | 1,197,620 | `bdcaa27d7c62aed5` | ET_DYN | `libc.so.6` | 1 | 1/0/0/0 |
| `root:lib/ld-2.12.2.so` | `root-selected/lib/ld-2.12.2.so` | 122,196 | `6077709a05643d69` | ET_DYN | `ld-linux.so.3` | 0 | – |

All 19 are ELF32 little-endian ARM, EABI version 5. The optional annotation from
`tools.arm_attributes` reports the base calling convention for all 19 (see
[arm-abi.md](arm-abi.md)), so no float-calling-convention difference could be flagged between any
inspected consumer and provider; no class, byte-order, machine or EABI mismatch was flagged
either. That covers the 43 verified edges only and says nothing about the 96 uninspected names.

Graph facts:

- 43 verified local edges (20 SONAME, 3 basename, 10 listed-link among `DT_NEEDED`; 10 interpreter
  edges, all to `root:lib/ld-2.12.2.so`). No cycle and no self-dependency.
- Dependents: `libc-2.12.2.so` 16, `ld-2.12.2.so` 12, `libafopenapi.so.0.0.0` 4,
  `libscf.so.0.0.0` 4, `liblgopenapi.so.0.0.0` 2, `libapiwrapper.so` 1, `libauitv.so` 1,
  `libtv.so` 1, `libncg_agent.so` 1.
- Six of the nine inspected shared objects carry no `DT_SONAME` (`libtv.so`,
  `libafopenapi.so.0.0.0`, `libscf.so.0.0.0`, `liblgopenapi.so.0.0.0`, `libapiwrapper.so`,
  `libauitv.so`). Their consumers declare unversioned names such as `libscf.so`, which exist in
  the listings only as symbolic links. This is why the listed-link rule exists, and why those
  matches rest on the listing rather than on metadata inside the library.
- `lb6wk` and `libtv.so` carry a `DT_RPATH` naming two build-host directories. It is reported
  verbatim and not expanded.
- Nine verified edges have an uninspected listed alternative: `libafopenapi.so` and `libscf.so`
  (four consumers each; `swue` lists its own copies, the first at 209,544 bytes against the
  inspected 221,880) and `libncg_agent.so.1` (`open:lib/libncg_agent.so.1`, 150,072 bytes, the
  same size as the inspected `base` copy). For `SWUE` in particular the inspected `lgli` copies
  are **LIKELY** not the ones it uses; the tool cannot decide.

Cross-check: a separate scratch reader that takes `DT_NEEDED` and `DT_SONAME` through the section
header table (`SHT_DYNAMIC` and its linked string table), not through the program headers,
returned identical lists for all 19 files. It was written for this task and is a second code path,
not an independent implementation.

## Missing evidence for a nonpersistent native shell

Admission and lifecycle are covered by [native-entry-contract.md](native-entry-contract.md) and
[native-admission.md](native-admission.md), which this report does not extend: the process manager
can create a process-table record after its own `vfork` or when its method receiver sees an
unknown process key, so prior launch by the supervisor is not proven mandatory, while bus access
policy, identity validation and registration state transitions remain PENDING. A dependency graph
says where a library name is declared and which file might provide it. It does not say whether a
client may register, in what state a function may be called, or what the services behind those
libraries require.

### C runtime and sysroot

| Name | Declared by | Evidence | Label |
| --- | --- | --- | --- |
| `ld-linux.so.3` | 9 programs and `libc-2.12.2.so` itself as `PT_INTERP` (10 edges); `libafopenapi`, `liblgopenapi`, `libc` as `DT_NEEDED` | inspected `root:lib/ld-2.12.2.so`, SONAME match | CONFIRMED name match |
| `libc.so.6` | 16 files | inspected `root:lib/libc-2.12.2.so`, SONAME match | CONFIRMED name match |
| `libgcc_s.so.1` | 14 files, including every inspected vendor library | `root:lib/libgcc_s.so.1` (41,592 B), listed only | PENDING inspection |
| `libpthread.so.0` | 8 files | `root:lib/libpthread-2.12.2.so` (123,481 B), listed only | PENDING |
| `libdl.so.2`, `librt.so.1`, `libm.so.6` | 7 files each | `root:lib/libdl-2.12.2.so` (18,156 B), `librt-2.12.2.so` (26,636 B), `libm-2.12.2.so` (444,172 B), listed only | PENDING |
| `libstdc++.so.6` | RELEASE, appctrl, fxui, procmgr, SWUE | `root:lib/libstdc++.so.6.0.14` (771,884 B) and `base:webbrowser/lib/libstdc++.so.6` (636,940 B), both listed only | PENDING; two candidates in different trees |

Symbol versions required by the consumers and provided by these libraries are not known: the
shared ELF reader does not report `DT_VERNEED`/`DT_VERDEF`. A sysroot cannot be chosen from file
names.

### Graphics

Nothing in the graphics stack has been inspected.

| Name | Declared by | Listed in | Label |
| --- | --- | --- | --- |
| `libEGL.so`, `libGLESv2.so` | fxui | `lgli:libEGL.so.1.4` (6,480 B), `lgli:libGLESv2.so.2.0` (439,560 B) | PENDING |
| `libIMGegl.so`, `libsrv_um.so` | fxui | `lgli` (72,604 B; 189,712 B) | PENDING |
| `libfxcore.so` | fxui | `lgli` (4,224,648 B) | PENDING |
| `libgal.so` | RELEASE | `lgli` and `vend`, both 34,704 B | PENDING |
| `libmtal.so` | RELEASE, procmgr, SWUE | `vend` (476,700 B), `swue` (474,636 B); not in `lgli` | PENDING; two sizes |
| `libmtk5398.so` | RELEASE, SWUE | `vend` (1,467,148 B), `swue` (1,424,668 B) | PENDING; two sizes |
| `libadec_api.so`, `libvdec_api.so` | RELEASE | `vend` | PENDING |
| `libdirectfb-1.2.so.0`, `libdirect-1.2.so.0`, `libfusion-1.2.so.0` | lb6wk only | `open:lib` (495,044 B; 96,828 B; 34,820 B) | PENDING |

Among the inspected programs only the LG browser `lb6wk` declares DirectFB; fxui and RELEASE do
not. The `lgli` listing also contains PowerVR-style names that no inspected file declares
(`libpvr2d.so`, `libpvrPVR2D_CobraNetCast40WSEGL.so`, `libpvrPVR2D_NullWSEGL.so`,
`libsrv_init.so`, `libglslcompiler.so`, `libGLESv1_CM.so.1.1`), and `open` lists DirectFB modules
under `lib/directfb-1.2-0/`. **HYPOTHESIS:** these are loaded at run time or are dependencies of
the uninspected libraries above. That is exactly the layer this graph cannot see. The native
window type, its provider, surface ownership and teardown remain as stated in
[native-entry-contract.md](native-entry-contract.md).

### Lifecycle and IPC

| Name | Declared by | Evidence | Label |
| --- | --- | --- | --- |
| `libafopenapi.so` | appctrl, fxui, procmgr, SWUE | inspected `lgli:libafopenapi.so.0.0.0` through the listed link; `swue` lists a different-size copy | CONFIRMED name match via listing |
| `libscf.so` | appctrl, fxui, procmgr, SWUE | inspected `lgli:libscf.so.0.0.0` through the listed link; `swue` lists a same-size copy | CONFIRMED name match via listing |
| `liblgopenapi.so` | RELEASE, `libtv.so` | inspected `lgli:liblgopenapi.so.0.0.0` through the listed link | CONFIRMED name match via listing |
| `libapiwrapper.so`, `libauitv.so` | RELEASE | inspected, basename match only | CONFIRMED file-name match |
| `libafcommon.so` | appctrl, fxui, procmgr, SWUE | `lgli:libafcommon.so.0.0.0` (55,980 B), `swue` (55,588 B) | PENDING |
| `libdbus-1.so.3` | RELEASE, appctrl, fxui, procmgr, SWUE, `libtv.so` | `lgli` (236,936 B), `open:lib` (236,872 B), `swue` (236,936 B) | PENDING; three candidates |
| `libdbgfrwk.so` | 7 files | `lgli:libdbgfrwk.so.0.0.0` (304,120 B), `swue` (304,144 B) | PENDING |
| `liblginputopenapi.so` | appctrl, fxui, procmgr, SWUE, `libtv.so` | `lgli` (56,564 B), `swue` (53,080 B) | PENDING |

`libafopenapi.so.0.0.0` declares only `libgcc_s.so.1`, `libc.so.6` and `ld-linux.so.3`;
`libscf.so.0.0.0` declares only `libgcc_s.so.1` and `libc.so.6`. Neither declares a message-bus or
framework library, although `libscf` imports D-Bus functions (see above). Their real requirements
are in their undefined symbols, which this tool does not inventory. **PENDING.**

`lgli:libdbgfrwk.so.0.0.0` and `lgli:liblgexc.so.0.0.0` are listed with the same size
(304,120 B), as are the two `swue` copies (304,144 B). **HYPOTHESIS:** one library under two
names. Equal sizes are not evidence of equal content.

### Files wanted for inspection

Selection belongs to the extraction workstream. Listed paths are name-level; sizes are in
`graph.json`.

1. C runtime (`root`): `lib/libgcc_s.so.1`, `lib/libpthread-2.12.2.so`, `lib/libdl-2.12.2.so`,
   `lib/librt-2.12.2.so`, `lib/libm-2.12.2.so`, `lib/libstdc++.so.6.0.14`.
2. Lifecycle and IPC (`lgli`): `libafcommon.so.0.0.0`, `libdbus-1.so.3.5.8`,
   `libdbgfrwk.so.0.0.0`, `liblginputopenapi.so.0.0.0`.
3. Graphics: `lgli` `libEGL.so.1.4`, `libGLESv2.so.2.0`, `libIMGegl.so`, `libsrv_um.so`,
   `libpvr2d.so`, `libpvrPVR2D_CobraNetCast40WSEGL.so`, `libsrv_init.so`, `libglslcompiler.so`;
   `vend` `libgal.so.0.0.0`, `libmtal.so.0.0.0`, `libmtk5398.so.0.0.0`; `open`
   `lib/libdirectfb-1.2.so.0.7.0`, `lib/libdirect-1.2.so.0.7.0`, `lib/libfusion-1.2.so.0.7.0` and
   the modules `lib/directfb-1.2-0/systems/libdirectfb_devmem.so`,
   `gfxdrivers/libdirectfb_gpuddi.so`, `wm/libdirectfbwm_default.so`.
4. Disambiguation: `swue:lib/libafopenapi.so.0.0.0`, `swue:lib/libscf.so.0.0.0`,
   `open:lib/libncg_agent.so.1`, `open:lib/libdbus-1.so.3.5.8`,
   `base:webbrowser/lib/libstdc++.so.6`, `base:webbrowser/lib/ld-linux-armhf.so.3`.

## Tool

`tools/elf_dependency_graph.py` uses only the Python standard library and imports the existing
`tools/elf_inventory.py` unchanged, through its stream interface. ABI annotation is optional and
parses the same open stream (`arm_attributes.inspect_stream`); the path is not looked up again,
and any failure there is recorded as `unavailable` and never fails the report.

```sh
python3 -B -m unittest tests.test_elf_dependency_graph
python3 -m tools.elf_dependency_graph --help
python3 -m tools.elf_dependency_graph --file-list artifacts/native-linkage/inputs.list \
  --inventory root=artifacts/firmware-lab/root-inventory.json \
  --inventory base=artifacts/firmware-lab/base-inventory.json \
  --inventory lgli=artifacts/firmware-lab/lgli-inventory.json \
  --inventory open=artifacts/firmware-lab/open-inventory.json \
  --inventory vend=artifacts/firmware-lab/vend-inventory.json \
  --inventory lgin=artifacts/firmware-lab/lgin-inventory.json \
  --inventory swue=artifacts/firmware-lab/swue-inventory.json \
  --output artifacts/native-linkage/NEW-NAME.json
```

That last command, written to a new name, reproduces `graph-r2.json` byte for byte.

Each input, on the command line or on a line of `--file-list`, is `LOCAL_PATH` or
`PACKAGE:IN_IMAGE_PATH=LOCAL_PATH`. The second form records where the file lives inside a firmware
package so that it can be matched against that package's listing. An input starting with `/`,
`./` or `../` is always a plain path. The tool never walks a directory. `--output` creates a new
file and refuses an existing one. The script also runs under isolated mode
(`python3 -I tools/elf_dependency_graph.py ...`) with byte-identical output. Exit status is 2 for
an invalid request, an exceeded bound or any per-file error.

Bounds and refusals:

- At most 512 inputs. Each input is opened once, read-only, without following a final symbolic
  link; symbolic links, directories and other non-regular files are refused and the descriptor is
  closed on every refusal. The size reported by `fstat` **on that descriptor** is checked against
  the 1 GiB per-file limit and the remaining 4 GiB cumulative budget, and charged once, before any
  content is read. A rejected input keeps its charge, so malformed files cannot be used to read
  more than the budget. The file is read from that descriptor in at most two passes (ELF metadata,
  SHA-256), or three with annotation; the budget counts the size once, not per pass. A file whose
  size or modification time changes while open is rejected.
- Text that is not valid Unicode is refused without a traceback (exit status 2, no output file):
  an input specification or an inventory path as a usage error, a listing that contains an
  isolated surrogate anywhere as a whole, and such a name coming from an ELF file as a per-file
  error.
- At most 256 `DT_NEEDED` entries per file and 16,384 edges in total, interpreters included. A
  file over a limit becomes an error entry; nothing is truncated into the graph.
- Declared names at most 255 bytes (1,024 for path-form names), non-empty, without control
  characters; at most one `DT_SONAME`. A violation rejects the file.
- At most 16 listings, each at most 16 MiB and 65,536 entries; paths and link targets at most
  1,024 bytes. Malformed entries are skipped and counted. Links are followed textually inside one
  listing for at most 8 hops, with loop detection; absolute targets, targets outside the image and
  links through a directory that is itself a link are not resolved.
- At most 4 file lists of 1 MiB each; input specifications at most 4,096 bytes.
- Candidate and listing lists are truncated at 16 and 32 entries per name, with true counts.
- A malformed or non-ELF input becomes a per-file error with no edges; the other files are still
  analysed, and the failed file is never a provider.
- Duplicates: a repeated input is collapsed and reported; one identity given for two local paths
  is rejected; identical content under several inputs is reported and stays ambiguous.
- Output has sorted keys and lists, no timestamps and no host paths beyond those supplied.

Validation: 64 synthetic tests in `tests/test_elf_dependency_graph.py` (no firmware) cover chains,
cycles, self-dependency, missing providers, ambiguity, rule labelling, interpreter resolution,
listing chains and loops, every bound above, malformed input, refusals, duplicates, deterministic
output and the command line. Eighteen of them are regressions for three defects found by an
independent review of the first version, each reproduced before it was fixed:

1. *Byte budget.* The first version read and hashed a file before validating it and charged the
   budget only on success, using a size taken before the reader's own open. Rejected inputs were
   free, and the size checked was not that of the opened file. Fixed as described in the first
   bound above; tests cover a rejected-then-valid sequence, every kind of rejection, a path
   replaced by a larger file between the pre-check and the open, and a file that grows while open.
2. *Un-encodable text.* A listing key containing an isolated surrogate raised an uncaught
   exception. Fixed on every request path, with a last-resort check before any output is written.
3. *Contradicted identity.* A listing alias was accepted as a provider even when the listing's
   size contradicted the supplied identity. The listed-link rule now has an explicit allow-list of
   one state, `listed_size_match`.

## Limits

- Name matching only. No loader behaviour, search path, symbol or symbol-version resolution.
- `DT_NEEDED` is one layer: run-time loading, plugins, inter-process services and under-declared
  libraries are invisible to it.
- 19 selected files. The transitive dependencies of the 96 uninspected names are unknown and are
  not in the graph.
- Listings are unauthenticated name, mode and size records produced by another workstream.
  In-image identities are supplied by the caller and checked against entry type and size only.
- Local paths must be valid UTF-8. A listing generated with escaped undecodable file names is
  refused as a whole, not entry by entry.
- A file-name (`local_basename`) match for an input given with an identity takes the name from
  the caller's claimed in-image path. It is labelled as such, with the identity check beside it,
  and is not suppressed when the listing contradicts the identity.
- Where a name is listed in several packages, which copy a process would load depends on mount
  points and search order, neither of which is established here.
- Nothing here identifies an admission mechanism, a safe execution route or a return path.

Requested from the owner of the shared reader `tools/elf_inventory.py` (not changed by this
task): required and provided symbol versions (`DT_VERNEED`/`DT_VERDEF`); a summary of undefined
and defined dynamic symbols; `DT_FLAGS`/`DT_FLAGS_1`, `DT_AUXILIARY` and `DT_FILTER`; a marker
when a name needed replacement characters. One defect was observed in it: `inspect_file` on a
directory raises `IsADirectoryError` and leaves the opened descriptor unclosed (five calls raised
the process's open descriptors from 4 to 9). This tool avoids the path by refusing directories
before calling the reader.

## Experiment LINKAGE-001

- **Objective:** map the declared shared-library dependencies of the selected firmware files and
  identify which providers are inspected, only listed or absent, as input for a nonpersistent
  native shell.
- **Hypothesis:** most providers the vendor programs declare are not yet in the lab, and some
  vendor libraries cannot be matched by `DT_SONAME`.
- **Environment:** Apple Silicon macOS host, Python 3.13 standard library; official 04.28.17
  firmware files already in the ignored lab; seven package listings.
- **Procedure:** implement a bounded mapper over explicit files; test it on synthetic ELF files;
  enumerate the ELF files already present in the named lab directories; run the mapper read-only
  with the seven listings; cross-check the declared names through the section header route;
  regenerate the report independently and compare hashes.
- **Expected result:** deterministic JSON separating inspected, ambiguous, listed-only and
  unresolved providers, or explicit per-file refusals.
- **Observed result:** 19 files, no errors; 241 `DT_NEEDED` edges and 10 interpreter edges over
  105 names; 9 names with an inspected provider, 96 listed-only, none unresolved, none ambiguous;
  43 verified edges, no cycles, no header-level mismatch; six of nine shared objects without
  `DT_SONAME`; one library whose declarations omit a provider it imports from.
- **Conclusion:** the loader and `libc` are the only C-runtime files inspected; the graphics stack
  is entirely uninspected; of the lifecycle libraries only `libafopenapi`, `libscf`,
  `liblgopenapi`, `libapiwrapper` and `libauitv` are in the lab, and their own declarations
  understate what they require. No link or run claim can be made.
- **Risks:** reading a name match as compatibility; reading the graph as complete; choosing
  between same-named copies without mount and search-path evidence; hostile parser input (bounded
  and tested).
- **Next step:** select the files listed above; add symbol-version and undefined-symbol inventory
  to the shared reader; rerun the mapper; only then define a sysroot manifest.
