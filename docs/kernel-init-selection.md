# Kernel init selection: ordered code references

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** the decoded kernel contains an ordered execution path that tries a retained `rdinit` candidate, then an explicit `init` candidate, then `/mnt/lg/lginit/lginit`, then `/bin/sh`. This independently strengthens the earlier string-only finding reported during the parallel boot review. It also adds a necessary qualification: `/init` is an earlier default candidate in the `rdinit` path. **PENDING:** which candidates the physical unit actually attempts, its live command line, and the identity of its running PID 1.

No firmware was executed or emulated. No TV, network, account or Git operation was performed. Only this report and ignored `artifacts/kernel-init-selection/` were written.

## Input, address mapping and method

Input: `artifacts/boot-triage/decoded/kern.decoded`, 5,191,748 bytes, SHA-256 `8d9e62e1e5272bdbbadd8cd0925a5f3ac55a04693cd90429621f3af67c19226e`. This is the reviewed [LZ4P decode](lz4p-analysis.md), including its 64-byte legacy uImage header. The prior decoder validated both uImage CRCs; this analysis independently rechecked the complete decoded file hash, not the compressed-container extraction. The payload is uncompressed ARM code, not an ELF file.

All **file offsets below include the 64-byte uImage header**. The justified mapping for the reviewed code is:

```text
linked virtual address = file offset - 0x40 + 0xc0008000
file offset            = linked virtual address - 0xc0007fc0
```

This is supported by startup self-references, not merely by choosing a base that makes string pointers work. At linked `0xc0008014`, `add r3, pc, #44` obtains the current location corresponding to file offset `0x88`; the following load reads the word `0xc0008048` stored at that offset, and subtraction computes the relocation difference. A second sequence at `0xc000807c` uses the self-reference `0xc0008104` at file offset `0x144`. A third uses `0xc0008198` at file offset `0x1d8`. Literal pointers and ARM branches in the selected functions agree with this mapping. These are linked virtual addresses; they do not establish the physical RAM layout or current MMU state. The uImage load/entry fields are a separate address context.

For host disassembly only, the payload was wrapped in a synthetic ELF32 little-endian ARM `ET_REL` file, with no program headers and one executable `.text` section at `0xc0008000`. This metadata is fabricated analysis scaffolding, not recovered ABI evidence. The wrapper is mode `0444` and was never loaded as a program. The explicit installed host tool was Apple LLVM 17.0.0:

```text
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump
SHA-256 bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4
```

Each of seven captures covers at most 512 source bytes, with a 10-second deadline and 256-KiB combined output cap enforced by the reviewed subprocess helper in [arm_disassembly.py](../tools/arm_disassembly.py). `--mattr=+v7` is a decoding setting, not a physical CPU identification. Literal pools and parameter tables must be read as data even when LLVM prints instruction mnemonics for them.

## Parameters connect to the execution slots

Two adjacent three-word setup records connect distinct parameter strings to callbacks:

| Record file offset | String pointer and contents | Callback linked address | Third word |
| --- | --- | --- | --- |
| `0x1aa10` | `0xc00269e8`, `rdinit=` at file `0x1ea28` | `0xc00082c4` | `0` |
| `0x1aa1c` | `0xc00269f0`, `init=` at file `0x1ea30` | `0xc0008294` | `0` |

The `init` callback stores its incoming pointer at `0xc04fb820 + 0x0c`; the `rdinit` callback stores it at `0xc04fb820 + 0x10`. Both clear argument-vector slots after the first and return 1. The later selection function loads these exact two locations. This is stronger evidence than the presence of `init=` text alone. The surrounding generic setup-table dispatcher was not fully audited, so argument tokenization and duplicate-parameter policy are outside this result.

The earlier string-only note's `init=` offset `0x1ea2a` points into the suffix of `rdinit=`. The independently registered `init=` string is at `0x1ea30`. This corrects the reference, not the conclusion that an explicit-init handler exists.

## The earlier `/init` candidate

At `0xc0008b5c`–`0xc0008b6c`, code reads the `+0x10` slot and, only when it is zero, fills it with the pointer to `/init` (file `0x44c9c6`, linked `0xc0454986`). At `0xc0008b70`–`0xc0008b88` it passes that path and `r1 = 0` to a check at `0xc00b790c`:

- result zero: retain the candidate and proceed;
- result nonzero: clear the slot and call the preparation function at `0xc000907c` before proceeding.

The caller then branches to the final selection function at `0xc002984c`. **CONFIRMED (static):** the default path, conditional slot clearing and shared continuation. **LIKELY:** the check is the usual initial-root path-access check and the intervening function prepares the real root namespace. Those semantic labels are not needed to establish the branch order, and the whole filesystem preparation path was not audited here. No presence or absence of `/init` in the initial runtime filesystem has been established by this analysis.

## Final candidate order is present in instructions

The function at `0xc002984c` uses the execution wrapper at `0xc0029838`. These calls and their fall-through paths are directly visible:

| Order | Call site | Candidate | Condition / fall-through evidence |
| --- | --- | --- | --- |
| 1 | `0xc0029894` | Pointer in `0xc04fb830` (`+0x10`) | Skip if zero. If execution returns, print `Failed to execute %s` and continue. This can be `rdinit=` or the retained `/init` default. |
| 2 | `0xc00298b4` | Pointer in `0xc04fb82c` (`+0x0c`) | Skip if zero. If execution returns, print `Failed to execute %s. Attempting defaults...` and continue. |
| 3 | `0xc00298c8` | `/mnt/lg/lginit/lginit` | Unconditional once this fallback block is reached. |
| 4 | `0xc00298d0` | `/bin/sh` | Reached if the preceding execution call returns. |
| Error path | `0xc00298d8` | `No init found. Try passing init= option to kernel...` | Reached if the shell execution call also returns. |

String pointers are loaded from literal words at linked `0xc00298ec`, `0xc00298f0` and `0xc00298f4`, corresponding to source offsets `0x2192c`, `0x21930` and `0x21934`. The strings themselves are at file offsets `0x44c63f`, `0x44c655` and `0x44c65d` respectively. Their order is therefore a control-flow result, not an inference from neighboring strings.

The wrapper at `0xc0029838` writes the candidate into the first argument-vector slot at `0xc04d51c8`, sets `r1` to that vector and `r2` to the adjacent environment vector, then tail-branches to `0xc00322e4`. That function passes the filename, argument vector, environment vector and a register-frame buffer to `0xc00be55c`. A negative return takes the ordinary return path; a nonnegative return copies the frame, changes the stack and branches to `0xc002ee60` without returning to the candidate caller. This corroborates an exec-style operation: later candidates are failure fallbacks, not a list of programs all started sequentially. The complete executable loader and final exception-return path were not audited; helper names here are interpretations, not recovered symbols.

Full-image byte checks found no NUL-terminated `/sbin/init`, `/etc/init` or `/bin/init` string. The bounded final selection block directly references only the two fixed candidates above. This supports the absence of the stock three-name fallback list in this block; it does not rule out dynamically constructed filenames elsewhere.

## Implications and limits

- **CONFIRMED (local, static):** `lginit` precedes `/bin/sh` in the fixed fallback block. A failed explicit `init=` falls through to this block. A retained `rdinit` candidate is attempted before explicit `init=`.
- **LIKELY:** without a usable early `/init` or `rdinit` candidate and without a successful explicit `init=`, the vendor `lginit` executable is the normal userspace entry. This does not independently prove its physical PID or that this precise kernel image/bank is running on the unit.
- **PENDING:** actual command line, early filesystem contents, environment-selected boot mode, active kernel bank and observed PID 1. The [boot-stage trace](boot-selection.md) only establishes that its dedicated `init=/sbin/init` append is conditional on `bootmode=nfs`; stored `bootargs` can supply another override.
- The presence of a fallback `/bin/sh` is **not a recovery procedure**. Console reachability, shell dependencies and usable I/O are unverified. No proposal to force candidate failure or change boot arguments follows from this finding.
- This result does not prove that root scripts or module-loading operations are never invoked by another component. It narrows the kernel's initial execution selection; it does not audit the entire subsequent boot graph.

## Reproduction and experiment record

The ignored capture script `artifacts/kernel-init-selection/capture.py` pins the complete source hash, constructs the synthetic wrapper, checks host-tool provenance, captures bounded ranges and refuses conflicting existing artifacts. Run from the repository root with `PYTHONPATH=. python3 artifacts/kernel-init-selection/capture.py`. `complete-manifest.json` records all seven range commands and hashes; `selected-evidence.json` records the string offsets and setup words. These local artifacts are not distributed with the firmware-free repository.

To independently reproduce the wrapper without the ignored helper, use the following exact layout after checking the source hash above. This is a static-data transformation only:

```text
raw = kern.decoded[64:]
ELF32 header: ET_REL=1, EM_ARM=40, version=1, entry=0, phoff=0,
              flags=0, ehsize=52, phentsize=0, phnum=0,
              shentsize=40, shnum=3, shstrndx=2
ELF ident: 7f454c46 01 01 01 followed by nine zero bytes
Payload begins at wrapper offset 52.
Section names immediately follow payload: NUL .text NUL .shstrtab NUL
Section-header table starts at the next four-byte boundary:
  section 0: forty zero bytes
  .text: name=1,type=1,flags=6,addr=0xc0008000,offset=52,
         size=len(raw),link=0,info=0,align=4,entsize=0
  .shstrtab: name=7,type=3,flags=0,addr=0,offset=52+len(raw),
            size=17,link=0,info=0,align=1,entsize=0
All integer fields are little-endian; retain the wrapper as non-executable data.
```

Selected linked ranges sufficient to verify the conclusions: entry `0xc0008000..0xc00081c0`, parameter callbacks `0xc0008260..0xc00082f8`, early candidate `0xc0008ac0..0xc0008c20`, final wrapper/selection `0xc0029838..0xc00298f8`, execution transition `0xc00322e4..0xc0032364`. Invoke the explicit trusted LLVM path with `-d --arch-name=arm --mattr=+v7 --start-address=START --stop-address=END WRAPPER`, using a finite timeout and bounded output as in the capture script. Read setup records and literal pools as words, not instructions.

**Objective:** independently verify the earlier string-only init inference. **Hypothesis:** actual calls establish the fallback order and connect command-line override slots. **Environment:** preserved decoded kernel and installed host LLVM on Apple Silicon macOS. **Procedure:** verify hash; justify address mapping; find exact pointer words; disassemble seven small ranges; trace slot writes, reads and branches. **Expected result:** corroborated ordering or an explicit mapping/flow blocker. **Observed result:** both override slots and ordered fallback calls are present; `/init` adds an earlier conditional path. **Conclusion:** the kernel-level fallback inference is now supported by code, with runtime selection unresolved. **Risks:** mistaking literal pools for code, virtual for physical addresses, or compiled paths for active behavior; these distinctions are retained above. **Next step:** integrate this qualification into the boot graph, then trace vendor `lginit` responsibilities without changing the device or assuming that root scripts are its only source of initialization.
