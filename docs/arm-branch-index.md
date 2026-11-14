# Bounded ARM immediate-branch index

`tools.arm_branch_index` lists **candidate encodings**, making distant targets and backward rejoins visible during manual review. It is not a control-flow graph, reachability proof, function detector or runtime trace. Executable segments can contain literal words that match branch encodings. All output carries these limits; no disassembler, target instruction, vendor library or external executable is run.

## Explicit input contract

```sh
python3 -m tools.arm_branch_index /absolute/path/to/selected.elf \
  --start 0x16310 --end 0x16a90 --arm-state --timeout 10
```

The mandatory `--arm-state` flag is a **caller assertion**, not a detected property. Only aligned four-byte ARM-state interpretation is offered. Thumb, mixed-state recovery, mapping-symbol interpretation and inference from the ELF entry bit are out of scope. Do not pass a Thumb slice merely because its addresses happen to be divisible by four.

Input and range checks reuse the reviewed `tools.arm_disassembly._read_input` and `validate_range` mechanisms and their ELF reader:

- Regular nonempty file, at most **64 MiB**; no symlinks in the input or parent components, no-follow/nonblocking open, descriptor size/identity checks before and after the bounded read.
- ELF32 little-endian ARM `ET_EXEC` or `ET_DYN`; linked virtual addresses, not file offsets or observed runtime addresses.
- Nonempty, four-byte-aligned half-open interval, at most **64 KiB**, fully backed by one unambiguous executable `PT_LOAD`. Overlap, zero-fill-only coverage, gaps, wraparound load mappings and non-executable ranges are rejected.
- At most **16,384 words/candidates**; compact JSON is capped at **4 MiB**. All candidates in the accepted slice are returned or an error occurs: there is no silent truncation.
- Cooperative processing deadline defaults to 10 seconds, maximum 30. Checks surround input validation and run every 256 words during scanning, with a final check after hashing. The regular-file read and filesystem stalls are not interruptible hard real-time guarantees; JSON serialization/stdout delivery are also outside this processing deadline.

The library offers `index_file` and `index_bytes`, both requiring `arm_state=True`. The latter accepts an immutable ELF snapshot for synthetic testing; it still applies the same file-size/ELF/range checks. No raw-byte-address guessing or file writes are offered. The tool does not automatically inspect branch targets outside the selected slice.

## Encoding basis

Primary reference: [Arm DDI 0597, ID121324, A32/T32 Instruction Set, 2024-12](https://documentation-service.arm.com/static/6762baf227eda361ad4e0735), B A1 on PDF page 60 (printed page 57), and BL/BLX immediate A1/A2 on PDF page 77 (printed page 74). In A32, immediate B/BL use bits 27–25 equal to `101`, a condition other than `1111`, and bit 24 to distinguish jump from link/call. The signed displacement is the 24-bit immediate shifted left two positions. The index adds it to the source address plus eight and wraps the result to 32 bits. Arm's [PC-relative addressing explanation](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/how-to-load-constants-in-assembly-for-arm-architecture) explicitly documents the ARM PC's eight-byte offset.

Condition `1111` in this encoding family is **BLX immediate**, with bit 24 serving as an extra displacement bit and an instruction-state change. Both bit-24 variants are counted in `excluded_blx_immediate_count` and excluded from B/BL candidates; they must not be decoded as ordinary conditional jumps/calls. Register-indirect BX/BLX forms, PC loads/writes, jump tables, return behavior and instruction-state transitions are unresolved.

## Output and review use

Successful stdout is one compact JSON object with schema `arm-branch-index-v1`: source size/hash, validated range and selected-byte hash/file offset, word/candidate counts, excluded BLX-immediate count, explicit assumptions/limits, and a source-ordered `candidates` array. Each row gives:

| Field | Meaning |
| --- | --- |
| `source`, `word`, `target` | Eight-digit hexadecimal linked addresses and raw encoding word |
| `offset_bytes` | Signed PC-relative displacement before adding source + 8 |
| `condition`, `condition_bits` | Condition name/value; CS/CC are the HS/LO aliases; AL is always |
| `kind` | `jump` for B, `call` for BL, based only on the link bit |
| `target_relation` | `in-range` iff target lies in the selected half-open interval; otherwise `outside` |

`in-range` does not mean reachable, executable or inside the same function. `outside` does not mean an error: a legitimate distant call/jump may leave the slice. Conditions are recorded but never evaluated. `call` does not prove a function boundary or eventual return. Literal data may produce identical rows to real instructions.

Use the index to locate targets, then inspect each successor and its later rejoin/termination with independently bounded disassembly and data-flow evidence. An apparent error branch may format a fallback and rejoin creation; a branch destination alone does not justify rejection semantics. See [static interpretation guidance](static-disassembly.md).

Runtime validation failures produce JSON on stderr and exit code 2; malformed CLI arguments use argparse's normal usage errors. Successful reports omit the original path and a full file dump, but candidate addresses/raw words are selected input content and may be vendor-derived evidence. Keep real-input reports in ignored artifacts, not public fixtures.

## Validation

```sh
python3 -m unittest tests.test_arm_branch_index
```

**CONFIRMED (local, 2026-11-14): 12 synthetic test methods pass.** Coverage includes the exact conditional `0x16580 → 0x167c8` and backward `0x167e0 → 0x16584` regression, signed displacement extremes, 32-bit wrap, all 15 ordinary conditions, both BLX H variants, indirect exclusions, half-open membership, literal-data ambiguity, no-candidate and `ET_DYN` cases, range/mapping/architecture limits, maximum-density output, cooperative deadline failure, no-follow/regular-file/changed-descriptor checks and CLI success/errors. No firmware fixture or host disassembler is needed.

One additional read-only check used the already selected 435,528-byte procmgr, SHA-256 `00cc453a3dd9cdf2723c79df07d8385ae9186a06d891ced7dac9363d3e2d79f5`, interval `[0x16310,0x16a90)`. The ignored report `artifacts/arm-branch-index/procmgr-004.json` preserves both regression targets from the actual bytes. This verifies index operation; it does not validate the branch's meaning or execute the target.
