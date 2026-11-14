# Static initializer: ELF entry and a main candidate

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static):** the selected `lginit` entry loads linked address `0x82ac` as its first register argument before calling `0xb078`. Its argument setup matches the non-shared ARM libc startup convention. **LIKELY:** `0x82ac` is the program's `main` candidate. This is an evidenced starting address, not a recovered symbol, verified function extent, proven callee identity or observed boot path. Neither that candidate nor either called destination has been disassembled in this task.

## Input and mapping

Input: `firmware/lab/lgin-selected/lginit`, 512,800 bytes, SHA-256 `0c2cb0c07849d4fe3473b0ab890a1a5b79aa9c183f2fb134f0b9c38d4f484e4c`. The reviewed ELF reader reports ELF32 little-endian ARM `ET_EXEC`, entry `0x8120`, no `PT_INTERP` and no `DT_NEEDED`. These describe the supplied binary, not the physical unit's PID 1 or complete execution environment.

The executable `PT_LOAD` maps file offset zero to linked `0x8000`, with file-backed length 494,780 bytes and flags 5. Thus the declared entry maps to file `0x120`, the selected interval `[0x8120,0x8220)` to file `[0x120,0x220)`, and candidate `0x82ac` to file `0x2ac`. The candidate falls inside this executable file-backed mapping. No candidate bytes were decoded to establish a prologue or boundary.

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

**Stop boundary:** the candidate's identity, range and callees remain unverified. Root review of this mapping is required before any candidate-body trace. A subsequent assigned slice could start precisely at `0x82ac` with an explicit byte cap; it must not borrow `lginit_app`'s main size or assume equivalent SWU behavior. The [dynamic recovery-entry report](recovery-entry-contract.md) remains separate evidence.

Experiment STATIC-ENTRY-001: **Objective:** obtain a justified static-initializer anchor without symbol/pattern searching. **Hypothesis:** the ELF entry supplies an identifiable libc-style first-function argument. **Environment/procedure:** pinned existing ELF, metadata validation, one 256-byte capture, literal/branch checks and primary startup-contract comparison. **Expected:** a mapped candidate or an explicit unresolved entry boundary. **Observed:** r0 receives `0x82ac` before call `0xb078` in matching startup argument arrangement. **Conclusion:** a narrowly justified main candidate is available, not a verified function. **Risks:** conflating a contract match with symbol/version identity, literal pools with instructions, or static code with active boot; those claims are excluded. **Next:** the entry-only review passed; candidate-body tracing still requires a separately scoped range and argument/branch review.

Independent review verified all64captured words, three PC-relative literal loads, both startup BL destinations, stack argument layout and candidate mapping against the pinned input. The libc source remains a contract comparison; no callee/provider/version identity or candidate-body extent was promoted to confirmed.
