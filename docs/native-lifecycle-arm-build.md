# Window lifecycle: current ARM object-only build

Date: 2026-11-14. **CONFIRMED (local compilation and static metadata):** the current original [lifecycle model](native-lifecycle.md), including separate window ownership, compiles to a **3,344-byte ARM relocatable object**. This is not an executable, admitted application, platform adapter or TV test. No linking, target execution/emulation, vendor libraries, SDK installation, IPC or device access occurred.

## Pinned inputs and tools

| Input/tool | SHA-256 |
| --- | --- |
| `prototypes/native/lifecycle.c` | `0099e2006f4af4199ec83b2f6adc73b418a6e4aeab3b54060577e4da983f850b` |
| `prototypes/native/lifecycle.h` | `04740dae02ae341b7f211ab8cd798f25e7b6bdb721e44f28f424c4d038f9e17a` |
| Xcode `clang` | `be5518e9c6736cda8dfc3486ce11e8112a2e08045084260691cf41f57a653f59` |
| Xcode `llvm-nm` | `51f8e9c766ccaf16986eca9f842cf5a5096af0c608c64bdf8bc16e4bb1d056ff` |
| `tools/elf_inventory.py` | `344eb190681a234e0ec56e5791ea31a32f9d209cb0603601ead21d51589b8a60` |
| `tools/arm_attributes.py` | `852a7c525e02852e500eecbe5dd6590e8bb9fbaf7cacf56663306fa4473ed813` |

Installed Apple clang **17.0.0 (clang-1700.6.3.2)** and Apple LLVM nm **17.0.0** were invoked by explicit paths under `/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/`. The Python metadata readers ran under installed Python **3.13.5**. Input/tool hashes were checked before and after the bounded commands; complete commands, versions, streams and Python executable hash are in ignored `artifacts/native-window-lifecycle-arm/build-001/provenance.json` and adjacent files.

## Exact build and inspection

From repository root, using a **new evidence directory** (do not overwrite the existing capture):

```sh
mkdir artifacts/native-window-lifecycle-arm/build-001
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang \
  --target=armv7a-none-linux-gnueabi -march=armv7-a -marm -mfloat-abi=soft \
  -ffreestanding -fno-builtin -fno-stack-protector -nostdinc \
  -std=c11 -O2 -Wall -Wextra -Werror \
  -c prototypes/native/lifecycle.c \
  -o artifacts/native-window-lifecycle-arm/build-001/lifecycle-arm.o
chmod 600 artifacts/native-window-lifecycle-arm/build-001/lifecycle-arm.o
python3 -m tools.elf_inventory artifacts/native-window-lifecycle-arm/build-001/lifecycle-arm.o
python3 -m tools.arm_attributes artifacts/native-window-lifecycle-arm/build-001/lifecycle-arm.o
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-nm \
  --undefined-only artifacts/native-window-lifecycle-arm/build-001/lifecycle-arm.o
```

The actual capture driver is `artifacts/native-window-lifecycle-arm/build.py`; it invokes those compiler/nm arguments with 30-second per-process timeouts, calls the same readers through their Python API, and refuses an existing `build-001` directory. Reproduction in this workspace needs a new explicitly chosen directory and corresponding output paths. The compiler completed with exit status zero and empty stdout/stderr. No linker was invoked.

## Observed result and limits

Object SHA-256: **`d8e890eb9d4ad01e3080f18780882d2d4774a63007877d09c5320e89eb884972`**. This replaces no historical artifact; the earlier 3,140-byte object/hash belongs to the older model.

- ELF32, little-endian, `EM_ARM`, `ET_REL`, EABI5 (`e_flags = 0x05000000`), entry zero. No program headers, load segments, interpreter or dynamic dependencies. Segment RX/RW permissions do not apply to this unlinked object.
- ARM attributes explicitly specify architecture v7/application profile and permit ARM instructions. They also permit Thumb-2; that attribute is not evidence that this `-marm` build contains Thumb code or that the physical TV supports either instruction set.
- The bounded attributes reader reports base AAPCS floating-point argument convention from the file-scope default `Tag_ABI_VFP_args = 0`. Its FP/Neon defaults prohibit hardware FP/Advanced SIMD instructions. These are emitted build declarations, not runtime measurements. Float ABI header bits are not used to infer the calling convention for `ET_REL`.
- `llvm-nm --undefined-only` succeeds with empty output. Defined-symbol output contains all eight public lifecycle functions and the local cleanup helper. This does not establish a complete application: injected operations, admission, callback lifetime, output, graphics and return-to-stock integration remain external obligations.

The attributes interpretation uses the existing reviewed reader's pinned Arm ABI specification, recorded in `tools/arm_attributes.py`; no new ELF parser was introduced. Compiler target/ISA/PCS choices describe this experiment only. The physical CPU, compatible sysroot, actual runtime ABI, service-bound lease and execution route remain unverified by this build. Host lifecycle tests are separate evidence; this task did not rerun them or execute the ARM object.

**Experiment NATIVE-WINDOW-ARM-001:** objective: check current core cross-compilation without runtime dependencies. Hypothesis: the allocation-free, injected-adapter core compiles freestanding with no unresolved symbols. Procedure: pin current source/tools, compile with historical experimental flags, inspect through trusted host readers and nm. Expected/observed: relocatable ARM object, no unresolved symbols, clean compiler exit; achieved. Conclusion: object compilation works, not native admission or target behavior. Risk: conflating build attributes with device compatibility. Next: establish native admission and the platform adapter contract; no deployment is implied.

Independent review passed: all16manifest entries and seven source/tool pins were verified, and a separate explicit compiler invocation reproduced the exact3,344bytes/hash. ELF headers, attributes and symbol output matched. Review evidence remains in ignored `artifacts/native-window-lifecycle-arm-review/`; no target execution occurred.
