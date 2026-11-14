# Minimal ARM Linux probe: build evidence only

Date: 2026-11-14. **CONFIRMED (local build/static inspection):** the existing Apple Silicon host tools produced a linked **648-byte ELF32 ARM EABI5 executable**, with an explicit entry and no libc, dynamic interpreter or `DT_NEEDED` dependency. Two initial builds produced identical executable hashes. **PENDING:** physical instruction-set compatibility, Linux entry/loader behavior, a permitted native admission mechanism, process account, observable output and actual execution. Nothing was deployed or run on a target or emulator.

This closes a small part of the source-to-linked-image gap in [native execution gates](native-execution-gates.md); it does not close the independent admission gate. The source is original project code, not a vendor binary or runtime. It does not bind the [lifecycle model](native-lifecycle.md) to LG interfaces.

## Program and primary-source basis

[probe.S](../prototypes/native-probe/probe.S) uses ARM state and no floating-point/SIMD instructions. It loads the syscall number into `r7`, passes arguments in `r0–r2` and uses `svc 0`. These conventions are documented in the [Linux syscall ABI table](https://man7.org/linux/man-pages/man2/syscall.2.html) and confirmed for the historical kernel generation by [Linux v3.0 ARM entry code](https://github.com/torvalds/linux/blob/v3.0/arch/arm/kernel/entry-common.S). The [v3.0 ARM syscall definitions](https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/unistd.h) define EABI base zero, `write=4` and `exit=1`. These upstream sources establish the intended ABI, not the owner's active kernel configuration.

The program makes **one** `write(1, marker, 24)` attempt, where the marker is `OPENCAST_NATIVE_PROBE_1` followed by a newline. A full 24-byte return selects exit status 0; a short or error return selects 1. It then calls `exit` directly; it creates no threads. A trailing undefined instruction traps only if the exit syscall unexpectedly returns. There is no retry, loop, stack access, libc call, file open, network operation, native TV API or settings operation. The entry code is 44 bytes; marker data follows it in the same RX section.

**Bounded bytes do not mean bounded runtime.** Inherited stdout might block, be closed, discard output, point to an unintended file/device, or cause a signal such as SIGPIPE. The single-write design cannot guarantee marker delivery or a normal exit under those conditions. Any future authorized starter must provide a known observable/nonblocking output channel, or use a separately reviewed exit-only experiment. Even observing an exit status requires a demonstrated starter. No timeout or signal machinery is implied.

The linker emits `e_flags=0x05000200`; the explicit soft-float flag identifies the **base procedure-call standard**, not software floating-point work. `Tag_ABI_VFP_args=0` agrees. This distinction follows [Arm AAELF32, ELF header flags](https://github.com/ARM-software/abi-aa/blob/main/aaelf32/aaelf32.rst). No FP operation or floating-point argument appears in the code.

## Existing host tools; no installation

Host inspection reported `Darwin arm64`. Apple Clang and LLVM objdump were already installed with Xcode. No PATH/Homebrew `ld.lld` existed, but the installed Rust toolchain contained a native-host LLD. Homebrew's current `lld` formula depended on full LLVM; it was inspected and **not installed**. No toolchain download, Rosetta, VM, container or emulation was needed.

| Tool | Observed version | Executable SHA-256 |
| --- | --- | --- |
| Apple Clang | 17.0.0, `clang-1700.6.3.2` | `be5518e9c6736cda8dfc3486ce11e8112a2e08045084260691cf41f57a653f59` |
| Rust-bundled LLD | 22.1.2, LLVM revision `1cb4e3833c1919c2e6fb579a23ac0e2b22587b7e` | `613eb4a0b9a297e3efb58e5ddf311091c7ab606bc846584f2ea27125f4e97063` |
| Apple LLVM objdump | 17.0.0 | `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4` |

These are explicit host tools, not programs extracted from firmware. The build report records resolved paths, versions, hashes, full argument vectors and source/reader hashes. Compiler flags request `arm-linux-gnueabi`, `armv6kz`, ARM state and base PCS. The resulting attributes report Arm v6, ARM instructions permitted, no FP/SIMD requirement and the compiler-selected CPU-name string `arm1176jzf-s`. **That string is tool output, not identification of the television's CPU.** No physical minimum ISA is assumed from a successful cross-build.

## Reproduce the local build

From the repository root, with the same installed tools:

```sh
python3 prototypes/native-probe/build.py \
  --clang /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang \
  --linker "$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/lib/rustlib/aarch64-apple-darwin/bin/rust-lld" \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --output artifacts/native-probe/build-next
python3 -m unittest tests.test_native_probe
```

Use a **new** output directory; an existing directory is rejected without overwriting it. Other hosts must supply their own trusted tool paths and inspect the resulting report. The script does not discover/install tools or execute the output. It uses static linking, `--no-undefined`, fatal linker warnings, no build ID, a 4-KiB maximum page alignment and [the explicit linker script](../prototypes/native-probe/probe.ld). The chosen `0x10000` image base is a local experiment parameter, not a verified target mapping.

The build result is deliberately mode `0600`. Failed builds may leave their new directory for diagnosis; the script does not remove or reuse it. Tool steps have finite host deadlines. Their 64 KiB output check is an acceptance limit after capture, not a streaming memory bound; this runner is for the explicit trusted tools and fixed project sources, not arbitrary untrusted compiler jobs. These host-build deadlines impose no runtime limit on the ARM program. The script accepts trusted project sources and tools, not arbitrary untrusted compiler inputs.

## Result and static checks

| Property | Observed artifact |
| --- | --- |
| Relocatable object | 644 bytes, `ET_REL`, SHA-256 `b6817b9df1ccf7c2b191ed4472302173ea89f3563f22dde7d52941da7f4ed135` |
| Linked image | 648 bytes, `ET_EXEC`, SHA-256 `d351176fb1a1942fef5d5156b2bc0605c7b2e2be93c8751fd26a4067a9251d63` |
| Machine / data | ELF32, ARM, little-endian, EABI5, explicit base PCS |
| Entry | ARM address `0x10074`, inside file-backed RX image |
| `PT_LOAD` | File offset 0, virtual address `0x10000`, file/memory size 184, alignment 4096, flags `R-X` |
| `PT_GNU_STACK` | Zero file/memory size, flags `RW-`; no executable-stack request |
| Dynamic linkage | No `PT_INTERP`, no `PT_DYNAMIC`, no `DT_NEEDED` |
| Writable image segments | None; stack permission is a declaration, not a mapped stack measurement |

The reviewed ELF reader supplies segment metadata. The probe-specific validator additionally checks linked type, base PCS, exact segment kinds/permissions, alignment, file-backed entry/code range, no zero-fill image storage and coherent non-FP ARM attributes. This is a narrow expected-build contract, **not** a general ELF verifier or proof that the TV loader accepts it. The reviewed disassembler reads exactly the 44 entry-code bytes; it shows two `svc 0` instructions and the intended straight-line register setup/conditional status selection. No target instruction was executed.

Seven host-only test methods exercise the contract with declared metadata and negative cases: relocatable/dynamic/foreign/hard-float inputs, writable executable segments, executable stack, extra segments, unmapped/Thumb/truncated entry ranges, layout/attribute mismatches, out-of-scope output and preservation of an existing directory. These tests do not replace the actual build reports. Ignored `artifacts/native-probe/build-001/` and `build-002/` preserve initial independent build reports; later checked builds preserve the final script identity. Their metadata is local evidence, not physical validation.

## Experiment NATIVE-PROBE-BUILD-001

- **Objective:** demonstrate that existing native-host tools can link our minimal ARM EABI program into an inspectable executable.
- **Hypothesis:** Apple Clang's assembler plus an already installed ELF-capable LLD suffice without a full cross-toolchain or libc/sysroot.
- **Environment:** Apple Silicon macOS, exact tool versions/hashes above, original assembly/linker script and reviewed repository ELF readers.
- **Procedure:** inspect tools, verify syscall ABI from primary sources, assemble, link, inspect segments/attributes and bounded entry code, compare repeat-build hashes, run negative contract tests.
- **Expected result:** a linked self-contained image or a concrete linker blocker; never confuse an object with an executable.
- **Observed result:** linked image obtained without installation; repeat executable hashes match; seven host test methods pass. Target code was not run.
- **Conclusion:** this local build route works. Native admission, physical ISA/loader compatibility, output observation and runtime behavior remain unresolved.
- **Risks:** treating build metadata as execution permission; blocking or misdirected inherited stdout; assuming standalone process exit restores framework focus/state.
- **Next step:** independently review the artifact and reconcile a legitimate admission/starter contract. Do not package, copy, launch or integrate it with device services on the strength of this build result.

### Independent review

Root and an independent reviewer rebuilt the image with identical 648-byte output/hash. The reviewer checked the three tools as native-host Mach-O files, parsed ELF headers independently, and verified all 11 ARM words plus the marker address rather than relying only on the contract validator. Seven host tests pass. The validator establishes structural expectations, not instruction semantics or entry-symbol identity; those are reviewed separately for this exact source/artifact. The ignored review lives under artifacts/native-probe-review/. No target execution occurred.
