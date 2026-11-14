# Native host toolchain: object-only feasibility probe

Date: 2026-11-14. **CONFIRMED (local):** the installed Apple Clang can generate a small ARM Linux-targeted ELF relocatable object on this Apple Silicon Mac without extra dependencies. **PENDING:** a compatible ELF link environment, target sysroot, reviewed firmware ABI profile and an authorized native execution route. No target program was linked, run or emulated; no TV/network/Git operation or installation occurred.

## Installed tools and scope of inventory

Host observation: macOS 26.6.2, `arm64`; Python 3.13.5. The inventory checked `PATH`, Xcode's selected tools through `xcrun`, and the immediate binary directories under Xcode, Command Line Tools, `/opt/homebrew/bin` and `/usr/local/bin`. It is not an exhaustive search of every disk location.

| Tool | Observed result | Consequence |
| --- | --- | --- |
| `/usr/bin/clang` | Apple clang 17.0.0, build `clang-1700.6.3.2`; default target `arm64-apple-darwin25.6.0` | Host-native compiler with registered `arm`, `armeb`, `thumb`, `thumbeb` and AArch64 targets. |
| `/usr/bin/gcc` | Reports the same Apple Clang build | The name does not provide a GNU ARM cross-compiler. |
| `/usr/bin/objdump` / `xcrun --find llvm-objdump` | Apple LLVM 17.0.0; Xcode tool resolves successfully | ARM object sections, symbols, raw attributes and instructions can be inspected statically. |
| `/usr/bin/ld` | Apple linker `ld-1230.1`, Apple platform architecture list | No demonstrated ARM Linux ELF linker. The compiler's `-print-prog-name=ld` selects Xcode's Apple linker. |
| `ld.lld`, `lld`, `readelf`, `llvm-readelf` | Not in `PATH`; `xcrun` also cannot resolve `ld.lld` or `llvm-readelf` | ELF linking and a dedicated external attribute reader are not yet supplied by the discovered setup. |
| `arm-linux-gnueabi-gcc`, `arm-linux-gnueabihf-gcc`, `arm-none-eabi-gcc`, `aarch64-linux-gnu-gcc` | Not in `PATH` or the scoped tool directories | No discovered GNU cross-toolchain. AArch64 would not match the inspected 32-bit firmware in any case. |
| `ar`, project `tools.elf_inventory` | Available | Archive tooling and a bounded static ELF metadata reader exist; archive/link compatibility was not tested. |

The presence of ARM in Apple's linker architecture list does not demonstrate Linux ELF output. No speculative link attempt was made. Tool paths, versions, exit codes and discovery failures are preserved in ignored `artifacts/native-toolchain/host-inventory.json`.

## Minimal object experiment

The only target-code artifact is `artifacts/native-toolchain/integer_probe.arm.o`. Its source is also ignored and is deliberately independent of the future production native prototype:

```c
/* Host cross-compilation probe only; no runtime entry point or dependencies. */
_Static_assert(sizeof(unsigned) == 4, "The probe requires 32-bit unsigned integers");
unsigned opencast_probe_mix(unsigned value)
{
    return ((value << 5) | (value >> 27)) ^ 0x4f50434fu;
}
```

No headers, floating-point operations, system calls, startup code or library calls are needed. The command used was:

```sh
/usr/bin/clang --target=arm-linux-gnueabi -march=armv5te -marm \
  -mfloat-abi=soft -ffreestanding -fno-builtin -fno-stack-protector \
  -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdinc \
  -O2 -std=c11 -Wall -Wextra -Werror -c \
  artifacts/native-toolchain/integer_probe.c \
  -o artifacts/native-toolchain/integer_probe.arm.o
```

The source/output paths were checked for absence before creation. Source and successful output are now `0444`; do not reuse the existing output name for a new experiment. Compilation exited 0 with empty stdout/stderr. A later `-###` driver-only trace records Clang's selected internal options without recompilation or linking.

**This profile is an experimental compiler input, not the selected TV ABI.** `armv5te`, ARM instruction mode and soft floating-point were chosen solely for this integer-only baseline. The raw generated attributes contain the compiler's `arm1022e` CPU-name string; it is unrelated to physical identification of the LG unit. A compiler may choose a default CPU label for an architecture switch.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `integer_probe.c` | 272 | `f26521dadeb5cc7add48d07be246bdce46d900c88cf130a48807e97cee9c5ffa` |
| `integer_probe.arm.o` | 832 | `90de028d6a1897da2f8c7d26d0c6101620ffac06b8750d44fe9b7af4ba1a0dfb` |

## Static validation

`tools.elf_inventory.inspect_file` reports ELF32 little-endian ARM, `ET_REL` (type 1), EABI5, flags `0x05000000`, entry 0, no program headers, no interpreter and no dynamic dependency entries. This is a relocatable object, not a runnable executable. The ELF floating-point flags are **unspecified**, despite the explicitly requested `-mfloat-abi=soft`; compile options and attribute semantics must not be inferred from those flags alone.

The installed host disassembler reports:

```text
0:  e59f1004   ldr r1, [pc, #4]
4:  e0210de0   eor r0, r1, r0, ror #27
8:  e12fff1e   bx lr
c:  4f50434f   literal data
```

`.text` is 16 bytes, of which 12 are instructions and four are a literal. The symbol table has the defined function and local section/mapping symbols; no undefined external symbol was listed. `.ARM.attributes` is 66 bytes. Clang also emitted an eight-byte `.ARM.exidx` section and its relocation despite the disabled unwind-generation options; this metadata has not been used to assert runtime unwind compatibility.

Reproduction of inspection, without target execution:

```sh
python3 -m tools.elf_inventory artifacts/native-toolchain/integer_probe.arm.o
/usr/bin/objdump -h -t artifacts/native-toolchain/integer_probe.arm.o
/usr/bin/objdump -d --arch-name=arm --mattr=+v5te \
  artifacts/native-toolchain/integer_probe.arm.o
/usr/bin/objdump -s --section=.ARM.attributes \
  artifacts/native-toolchain/integer_probe.arm.o
```

Raw attribute bytes are saved in `attributes-raw.txt`. At this report's creation, Claude's `tools/arm_attributes.py` was still being developed. It was not imported or executed for this experiment, by integration instruction. Detailed attribute interpretation and comparison with firmware are **PENDING** that reader's review/freeze. The integer-only object cannot by itself validate floating-point argument conventions, structure layout at vendor interfaces or libc interoperability.

Additional ignored evidence: `compile.json`, `compile-driver-trace.txt`, `elf-report.json`, `sections-symbols.txt`, `instructions.txt` and `driver-only.txt`. No vendor binary or library was copied into the native-toolchain artifact directory.

## Gaps before a native build is meaningful

| Gap | Evidence needed before selecting a production configuration |
| --- | --- |
| ISA and calling convention | Reviewed ARM attributes across the executable, loader and relevant libraries; distinguish base AAPCS from VFP argument conventions and actual instruction requirements. ELF class/EABI alone is insufficient. |
| ELF linker | A host-native, pinned linker capable of the required ARM ELF output, with a local link-only validation. No installation has yet been justified or performed by this experiment. |
| Linux/libc sysroot | Matching headers, startup objects, linker inputs, symbol versions, loader path and license/provenance records. Shipped `/lib/ld-linux.so.3` and libc filenames suggesting 2.12.2 are starting evidence, not a complete SDK. |
| Compiler runtime | A justified source of any required arithmetic, atomic or other compiler helper routines. This tiny object happens to require none. |
| Graphics and vendor services | Compatible DirectFB/Fusion/SaWMan interfaces and headers, application registration and remote-input lifecycle. Library names or symbols do not supply safe call contracts. |
| Execution and return path | A reversible, authorized way to start and stop the native test while preserving the TV's services. Compilation provides no deployment mechanism. |

The next useful local step is to compare this object with the reviewed firmware attribute matrix, then define the smallest explicit target profile and sysroot manifest. Only after those inputs are understood should a linker/sysroot acquisition or native program be proposed. A successful host compile is neither evidence of TV compatibility nor progress toward a verified recovery path.

## Experiment record

- **Objective:** determine whether the installed host compiler can emit inspectable ARM Linux-targeted object code without adding tools.
- **Hypothesis:** Apple's Clang ARM backend can compile a freestanding integer function even though the host platform and default linker target macOS.
- **Environment:** existing Apple Silicon host, Apple Clang/LLVM 17, existing project ELF reader; no target libraries.
- **Procedure:** inventory tools; create an ignored, dependency-free source; compile with `-c`; inspect ELF headers, symbols, instructions and raw attributes; hash and preserve outputs read-only.
- **Expected result:** either a precise unsupported-target failure or an ARM relocatable object requiring no target execution.
- **Observed result:** an 832-byte object with the metadata above; no diagnostics, no external symbols and no link step.
- **Conclusion:** object generation is available; a compatible native application toolchain is not yet established.
- **Risks:** no device-side risk introduced; object metadata and host compile success must not be promoted to runtime or full-ABI validation.
- **Next step:** integrate the reviewed ABI report and close linker/sysroot requirements before any native executable or deployment experiment.
