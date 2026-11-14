# Boot-mode selection: bounded static cross-reference analysis

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** the reviewed U-Boot-stage code has a justified ARM linked-address mapping, an environment-derived `bootmode` branch and a separate SWU-mode selector. The dedicated `init=/sbin/init` append is conditional on `bootmode` matching `nfs`; it is not an unconditional default. **PENDING:** the owner's actual environment, active branch, boot-console availability and independently usable recovery.

Input: `artifacts/bootloader-analysis/boot-80000.bin`, 545,624 bytes, SHA-256 `11d6616752416c42b40d167de92ae48a190f16d24f9c33dbc2b8ba93ef7a20c7`, reproduced by the [reviewed LZHS decoder](bootloader-analysis.md). No target code was run or emulated. No TV, network or Git operation was performed. Only `docs/boot-selection.md` and ignored `artifacts/boot-selection/` were written.

## Address and instruction evidence

The mapping `linked address = decoded file offset + 0x00800000` is **CONFIRMED (local, static interpretation)** for the reviewed paths, supported by independent structural checks:

1. At file offset `0`, ARM word `ea000012` branches to file offset `0x50`. The next seven vector instructions load PC through words at `0x20`–`0x38`, holding `0x800100`, `0x800160`, …, `0x800340`. These point to instruction sequences at the corresponding file offsets under this base.
2. At linked address `0x800064`, the entry code computes its current start with `sub r0, pc, #108`, loads `0x800000` from file offset `0x40` and compares them. If unequal, a copy loop uses constants at file offsets `0x44`–`0x48` (`0x800000`, `0x885354`). Thus the linked base is supported by startup relocation logic, not chosen solely to make strings line up.
3. PC-relative literal loads in coherent ARM functions resolve to pointers such as `0x87be5a`, which maps exactly to `bootmode=%s ` at file offset `0x7be5a`. Calls, returns and string routines decode consistently as little-endian ARM instructions.

The entry also clears a range ending at `0x8c5eb0`, beyond the decoded file. This is consistent with zero-initialized runtime storage; it is not file-backed evidence about current RAM. No physical load address, memory map, live relocation or exact CPU model is established. `--mattr=+v7` enables decoding instructions such as `movw` and `uxtb`; it is a disassembler setting, not a hardware identification.

Apple LLVM 17.0.0 `/usr/bin/objdump` was used. Because the source is raw data, a **synthetic analysis-only ELF32 relocatable object** was created with one `.text` section mapped at the justified base and no program headers. Its ELF fields are fabricated host-analysis metadata, not vendor ABI evidence. It is mode `0444`, and was never loaded or executed. Literal pools and tables appear as meaningless instructions if indiscriminately disassembled; conclusions below use manually checked code/data boundaries.

## Command-line builder and the `nfs` condition

The function at `0x85ab14` receives a destination buffer. Its sole found aligned direct `BL` reference is at `0x85b1b4`, following initialization of a 4,096-byte stack buffer. This is a bounded direct-call finding, not proof that no indirect caller exists.

Cross-references and helper behavior support this partial interpretation:

```text
builder at 0x85ab14:
    initial = name_value_lookup("bootargs")
    swu_selected = selector_at_0x818ec8()
    append("%s ", initial)
    append root, eMMC, lginit and console fragments
    append lock_time fragment
    mode = name_value_lookup("bootmode")
    append("bootmode=%s ", mode)
    if mode != NULL and string_compare(mode, "nfs") == 0:
        append("init=/sbin/init ")
    else if helper_at_0x81bc78() == 1:
        append("lgsnap ")
    if swu_selected != 0:
        append("swumode ")
    ... further arguments outside this bounded trace ...
```

This is explanatory pseudocode, not an executable or an operational recipe. `name_value_lookup` and `string_compare` are analyst labels, not recovered symbols. The lookup at `0x80cdb0` scans null-terminated entries and uses `0x80cca4` to match a name followed by `=`; it returns a pointer to the value through `0x8103d4`. The routine at `0x854308` compares bytes until mismatch or terminator; `0x8543b4` computes string length. The call at `0x854f20` is a variadic formatting wrapper; its entire formatter was not audited.

| Item | Instruction address | Literal-pool file offset | Referenced string file offset | Evidence |
| --- | --- | --- | --- | --- |
| Lookup `bootmode` | `0x85abf8` | `0x5b09c` | `0x74391` | Lookup return is retained in `r6`. |
| Append `bootmode=%s ` | `0x85ac0c` | `0x5b0a0` | `0x7be5a` | `r6` is the format substitution. |
| Compare against `nfs` | `0x85ac28` | `0x5b0a4` | `0x743b7` | Null check precedes comparison; nonzero comparison skips the init append. |
| Append `init=/sbin/init ` | `0x85ac40` | `0x5b0a8` | `0x7be67` | Reached by the matching branch; format call at `0x85ac68`. |
| Append `swumode ` | `0x85ac7c` | `0x5b0b0` | `0x7be80` | Guarded by `r5 != 0` at `0x85ac6c`–`0x85ac70`; `r5` came from `0x818ec8`. |

The compiled data contains exactly `bootmode=auto` at file offset `0x7d0e5`. The environment accessors can use active storage or a compiled fallback rooted at `0x87cfe8`. Therefore **CONFIRMED (static)** is the compiled default's presence; **PENDING** is the selected environment and value on the owner’s set. The initial `bootargs` string can itself contain arguments, so this conditional append does not rule out an `init=` argument arriving by another route. The normal running PID 1 still cannot be inferred from this fragment alone.

## SWU-mode input and command effect

The selector at `0x818ec8` calls the helper at `0x818454` with two reads into stack buffers:

- selector index/offset `0x198`, length 4; the loaded word is compared with `0x20121205`;
- only after that match, selector index/offset `0x18b`, length 1; the return is 1 if the resulting byte is `0x53`, otherwise 0.

The failed first comparison reaches the diagnostic `Get SWUM Magic ( %08x : %08x ) failed...` at file offset `0x74b9b`. These constants are static format/select-state evidence, not values read from the TV. `0x818454` packages a two-byte offset and forwards the buffer to `0x823f58`; the physical backend, persistence guarantees and error behavior remain **PENDING**. In particular, the selector does not visibly check that helper's returned status before examining the stack buffers. Do not assume reliable results after a failed underlying read.

A six-word record at file offset `0x85264` contains pointers to `swumode`, a function at `0x817b10`, and help text `swumode [on/off]`. Its layout and neighboring records are **LIKELY** a U-Boot-style command registry. The code at `0x817b10` corroborates that interpretation: it reads an argument count/list, queries `0x818ec8`, compares a supplied string with `on`, and on a changed selection calls `0x818f28`.

The setter at `0x818f28` calls a distinct write-like helper at `0x81838c`, first with the marker word and then with a selected-state byte. The helper splits writes into bounded chunks and calls a lower transport at `0x824020`; it is structurally different from the read path. **CONFIRMED (static):** a state-changing path exists behind this command. **LIKELY:** it changes nonvolatile selection state. **PENDING:** the physical medium and persistence/failure semantics. It must not be proposed as a harmless toggle, routine diagnosis or demonstrated recovery method. No command was issued, and command registration alone does not establish a reachable console.

## `env_nvm` is a separate dependency

The string at file offset `0x7291a` has aligned pointer words at `0x1068c`, `0x14118` and `0x17a38`; corresponding literal loads are at `0x8105f0`, `0x814084` and `0x817990`. The bounded first path calls `0x815538` with `env_nvm`, tests the returned pointer and accesses fields at offsets `0x20` and `0x28`. A null result reaches `env_nvm partition not found.` and a fallback path.

This supports a **LIKELY** partition-backed environment path, consistent with the [partition template](partition-layout.md). It does not identify the currently selected partition or prove the semantics of every field and integrity check. No environment contents were extracted. The SWU selector above uses a different helper chain; equating it with a `swumode` environment variable would be unsupported.

## Reproduction, limitations and next step

Ignored evidence: `artifacts/boot-selection/initial-xrefs.json`, `selected-data.json`, `capture-manifest.json`, the synthetic wrapper and 14 bounded `.asm.txt` captures. `capture.py` pins the input SHA-256, reconstructs the wrapper, invokes only the installed host disassembler with fixed ranges and refuses differing existing outputs. Run it from the repository root:

```sh
PYTHONPATH=. python3 artifacts/boot-selection/capture.py
```

An individual capture is reproducible without the script:

```sh
/usr/bin/objdump -d --arch-name=arm --mattr=+v7 \
  --start-address=0x85ab14 --stop-address=0x85ac88 \
  artifacts/boot-selection/boot-80000.analysis-only.o
```

The initial aligned-word/PC-relative-load scan yields candidates across code and data; only the manually reviewed paths above are promoted to findings. There is no full control-flow graph, exhaustive indirect-call analysis, transport audit or runtime validation. Input hashes and selected literal targets were checked locally; this static research adds no firmware execution or device-side test result.

Experiment objective/hypothesis: determine whether the decoded strings have real selector-controlled references under a defensible address map. Expected outcome: justified local paths or explicit unresolved mapping. Observed outcome: startup relocation supports the base, the `nfs` guard is concrete, and SWU state comes through a separate read/write helper pair. Conclusion: the evidence narrows boot-selection questions and corrects an unconditional-init inference. Risks: false positives from disassembling data were controlled with bounded manual review; target bytes remain untrusted and untouched. Next step: identify the SWU read/write transport and the environment initialization/fallback decisions statically, then connect only proven selectors to the already inspected userspace service lists. Runtime recovery and any persistent operation remain behind the existing authorization and verified-recovery gate.
