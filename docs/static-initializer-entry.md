# Static initializer: ELF entry and a main candidate

Date: 2026-11-14. **Entry anchor independently reviewed. CONFIRMED (local static):** the selected `lginit` entry loads linked address `0x82ac` as its first register argument before calling `0xb078`. Its argument setup matches the non-shared ARM libc startup convention. **LIKELY:** `0x82ac` is the program's `main` candidate. This is an evidenced starting address, not a recovered symbol, verified function extent, proven callee identity or observed boot path. A separately assigned 256-byte candidate prefix is recorded below and awaits independent review; neither startup call destination has been traced.

## Input and mapping

Input: `firmware/lab/lgin-selected/lginit`, 512,800 bytes, SHA-256 `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c`. The reviewed ELF reader reports ELF32 little-endian ARM `ET_EXEC`, entry `0x8120`, no `PT_INTERP` and no `DT_NEEDED`. These describe the supplied binary, not the physical unit's PID 1 or complete execution environment.

The executable `PT_LOAD` maps file offset zero to linked `0x8000`, with file-backed length 494,780 bytes and flags 5. Thus the declared entry maps to file `0x120`, the selected interval `[0x8120,0x8220)` to file `[0x120,0x220)`, and candidate `0x82ac` to file `0x2ac`. The candidate falls inside this executable file-backed mapping. The original entry-only stage did not decode candidate bytes; the later prefix does not establish a complete function boundary.

Exactly **256 bytes** were captured, within the approved entry-only scope. ARM decoding is an explicit assumption consistent with the even entry address and coherent instructions; an even address alone does not prove instruction state or code/data separation. Three directly referenced startup literals are inside this interval, so no additional external literal read was required.

## Register and stack evidence

Let `S` be SP on entry. The following is direct instruction/data evidence:

| Address | Observed operation | State before the call at `0x8148` |
| --- | --- | --- |
| `0x8120..0x8124` | Clear frame pointer and LR | Both zero |
| `0x8128` | Load `[S]` into r1 and advance SP by four | r1 = first incoming stack word |
| `0x812c` | Copy SP to r2 | r2 = S+4 |
| `0x8130..0x8134` | Push r2, then incoming r0 | Values retained on stack |
| `0x8138..0x813c` | Load word at `0x8150`, then push it | Top stack word = `0xb798` |
| `0x8140` | Load r0 from word at `0x8154` | r0 = **`0x82ac`** |
| `0x8144` | Load r3 from word at `0x8158` | r3 = `0xb700` |
| `0x8148` | Direct ARM BL | Destination `0xb078` |
| `0x814c` | Next instruction, if the prior call returns | Direct BL to `0xb8f0` |

At the first call, SP is `S-8`; its three stacked argument words are `0xb798`, the incoming r0, and `S+4`. No early conditional branch bypasses the shown setup. The next twelve bytes (`0x8150..0x815c`) are a literal pool. If the second call returned, execution would fall into these data words; no non-returning property of either target has been independently proven here. The remaining captured neighbors are not attributed to the entry function and do not establish a main boundary.

## Contract inference, not library-version attribution

Primary comparison: GNU libc's [ARM startup source at tag glibc-2.17](https://github.com/bminor/glibc/blob/glibc-2.17/ports/sysdeps/arm/start.S), specifically its non-shared entry branch. That source passes a main pointer, argument count, argument-vector pointer and init callback in r0–r3, followed by fini, runtime-linker cleanup and stack-end arguments on the stack. A second call follows if the startup routine returns. The selected binary's argument arrangement is consistent with that contract.

Accordingly, `0xb078` is a **candidate libc startup routine** and `0x82ac` a **candidate main pointer**; `0xb700`/`0xb798` are candidate initialization/finalization callbacks. Those semantic names are inferences. The comparison does not identify the firmware's libc version, implementation, patches, exact ABI completeness or callee behavior. In particular, the reference tag is not evidence that this firmware contains glibc 2.17.

The source was retrieved as plain text from the upstream Git mirror, with no redirects and a 64-KiB response cap. Ignored copy SHA-256: `5bc77b943f954854811377669a9c84bca3c747424f6d70d84596b0d1b5aca258` (4,266 bytes). No upstream code was built or executed.

## Reproduction, review boundary and experiment

Ignored `artifacts/static-initializer-entry/` contains the metadata, one capture, selected-word/branch verification, primary-reference copy and hash manifest. `capture.py` pins the source, reads the ELF entry and invokes only the reviewed bounded host disassembler. Host LLVM SHA-256: `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Reproduce with `PYTHONPATH=. python3 artifacts/static-initializer-entry/capture.py`. No pattern scan, bulk extraction, target execution/emulation, credential read, TV/IPC/LAN or Git operation occurred.

**Original stop boundary:** the candidate's identity, range and callees remained unverified. Root reviewed the mapping before assigning the bounded prefix below. No stage borrows `lginit_app`'s main size or assumes equivalent SWU behavior. The [dynamic recovery-entry report](recovery-entry-contract.md) remains separate evidence.

Experiment STATIC-ENTRY-001: **Objective:** obtain a justified static-initializer anchor without symbol/pattern searching. **Hypothesis:** the ELF entry supplies an identifiable libc-style first-function argument. **Environment/procedure:** pinned existing ELF, metadata validation, one 256-byte capture, literal/branch checks and primary startup-contract comparison. **Expected:** a mapped candidate or an explicit unresolved entry boundary. **Observed:** r0 receives `0x82ac` before call `0xb078` in matching startup argument arrangement. **Conclusion:** a narrowly justified main candidate is available, not a verified function. **Risks:** conflating a contract match with symbol/version identity, literal pools with instructions, or static code with active boot; those claims are excluded. **Next:** the entry-only review passed; the subsequently assigned prefix is documented separately below.

Independent review verified all64captured words, three PC-relative literal loads, both startup BL destinations, stack argument layout and candidate mapping against the pinned input. The libc source remains a contract comparison; no callee/provider/version identity or candidate-body extent was promoted to confirmed.

## Candidate prefix: separate bounded follow-up

**Independently reviewed. CONFIRMED (local static bytes):** the new interval is `[0x82ac,0x83ac)`, file `[0x2ac,0x3ac)`, exactly 256 bytes, SHA-256 `41fe2f090dd586b7819cf2b20de48ff868d2bc825611430104efbb052e169b20`. The input and host LLVM hashes remain those above. No callee body or outside branch destination was decoded. ARM state remains the explicit decoding assumption inherited from the anchor; a prologue alone does not establish function identity or extent.

The prefix pushes r4–r7 and LR, reserves 28 stack bytes, and makes three initial calls. At `0x82bc`, r0 is zero; `0x82c0` calls another unknown destination. At `0x82d4`, the demonstrated arguments are r0=`0x8ce20`, r1=32, r2 pointing to `LOG_LEVEL=%d`, and r3 holding the previous call's return. This resembles the dynamic initializer's formatting sequence, but the static callee is not identified as `snprintf` here.

Five directly referenced external words establish the following data flow. These are data reads, not additional instruction captures.

| Load instruction | Literal address | Value | Demonstrated use |
| --- | --- | --- | --- |
| `0x82b4` | `0x85e4` | `0x8ce20` | r5; later call argument and stored pointer |
| `0x82cc` | `0x85e8` | `0x68c90` | r2 at call `0x82d4`; NUL-terminated `LOG_LEVEL=%d` |
| `0x82d8` | `0x85ec` | **zero** | r3 tested against zero at `0x82e0` |
| `0x82dc` | `0x85f0` | `0x8c1d0` | r4; `0x82e4` stores r5 to `[r4]` |
| `0x82ec` | `0x85f4` | `0x68ca0` | r0 at call `0x82f0`; NUL-terminated `APP_START` |

For the supplied literal value, BNE at `0x82e8` is not taken: its target is `0x84e8`, and fallthrough is `0x82ec`. No instruction between the compare and branch changes the flags. The fallthrough call passes the technical string `APP_START` to **unknown destination `0xbb78`**. Its returned r0 is copied to r6 and tested by SUBS at `0x82f4`: zero goes to `0x853c`; nonzero continues at `0x82fc`. This establishes a zero/nonzero return gate, not the callee's identity, environment lookup semantics, a live environment value or recovery entry.

On the nonzero path, pairs of calls at `0x8304`/`0x8344` and `0x8350`/`0x8394` use r0=12 and r0=7 respectively, with r1=SP. Between each pair, stack words at offsets 0/4 and 8/12 are transformed as two little-endian 64-bit values shifted left by two, modulo 64 bits. No success-return test precedes those stack reads in this prefix; the first callee's output contract is unverified. The last call uses r0=6/r1=SP, then reads `[SP]` into r6/r7 before the slice ends. There is no claim that these static callees are resource-limit functions, even though the corresponding dynamic sequence uses such imports.

All direct call destinations and their fallthroughs are retained below. Every target is outside the captured prefix; none has been followed.

| Call site | Unknown destination | Following instruction if it returns |
| --- | --- | --- |
| `0x82bc` | `0x1d1e0` | `0x82c0` |
| `0x82c0` | `0x95bc` | `0x82c4` |
| `0x82d4` | `0xc6d0` | `0x82d8` |
| `0x82f0` | `0xbb78` | `0x82f4` |
| `0x8304` | `0x1dcd0` | `0x8308` |
| `0x8344` | `0x1dd3c` | `0x8348` |
| `0x8350` | `0x1dcd0` | `0x8354` |
| `0x8394` | `0x1dd3c` | `0x8398` |
| `0x83a0` | `0x1dcd0` | `0x83a4` |

### Comparison, accounting and next boundary

The previously captured dynamic `lginit_app` sequence at `0x92e4` has the same demonstrated register/stack arrangement and branch structure in its corresponding prefix. Its word at `0x9624` is **nonzero (`0x9128`)**, making its branch at `0x9320` select `0x9520` in the supplied bytes. The static zero literal therefore supports a concrete difference in initial phase selection; it does not establish why the binaries differ or what runs on the television. Dynamic import names are evidence about the dynamic ELF only and are not transferred to static targets by analogy.

New capture accounting: **256 instruction bytes + five external 4-byte words (20 bytes)**. Two explicitly justified technical-string reads were capped at 96 bytes each: **192 bytes of read windows**, retaining only the two NUL-terminated strings (**23 bytes total**), not surrounding contents. Cumulative instruction capture for this entry investigation is **512 bytes**: original entry 256 + new prefix 256. Its three original startup literals were already inside the entry capture. No extra neighboring instructions were captured; prior dynamic captures were reused without expansion.

Ignored `artifacts/static-initializer-prefix/` contains `prefix.json`, `prefix.txt`, `literals.json`, `capture_verify.py` and `verification.json`. Reproduce with `PYTHONPATH=. python3 artifacts/static-initializer-prefix/capture_verify.py`. The verifier pins both inputs, checks all 64 displayed words against mapped bytes, independently calculates all 11 immediate branch/call targets and five PC-relative literal addresses, and records string hashes, exact counts and both conditional successors.

**Stop boundary:** the main identity/extent, static callees, `0x84e8`, `0x853c`, and fallthrough after `0x83a8` remain untraced. A useful next assignment would be **`[0x853c,0x85bc)` (128 bytes)**, anchored only by the observed zero-return branch target. That proposed window is a byte budget, not a function extent; it has not been inspected. It can test whether that successor contains an initialization/reexecution prerequisite without first assuming that `0xbb78` is an environment API. No recovery or runtime execution permission follows from this proposal.

Experiment STATIC-ENTRY-002: **Objective:** determine the first evidenced phase gate at the justified candidate. **Hypothesis:** a bounded prefix distinguishes the static and dynamic initializer's early paths. **Environment/procedure:** unchanged selected ELF and pinned host LLVM; one 256-byte slice, five referenced words, two bounded technical strings, arithmetic verification and comparison with existing dynamic captures. **Expected:** explicit arguments and successors, or a clear unresolved boundary. **Observed:** zero static phase word, `APP_START` passed to an unnamed callee, and a zero-return branch to `0x853c`. **Conclusion:** the files differ at the initial pointer gate; static recovery behavior remains unknown. **Risks:** importing dynamic names or interpreting a technical string as proof of API identity, active boot or recoverability. **Next:** independent review passed; follow only the separately scoped successor slice if useful.

Independent prefix review passed without substantive corrections: six manifest files,64words,11branch/call targets, five literals and both technical strings were verified. The existing256-byte interval was reproduced using the pinned host LLVM; no new successor/callee bytes were read. Review evidence: ignored `artifacts/static-initializer-prefix-review/`.

The subsequently scoped zero-return successor is documented separately in [static-initializer-successor.md](static-initializer-successor.md). Its preparation-shaped calls do not establish initialization success or recovery.
