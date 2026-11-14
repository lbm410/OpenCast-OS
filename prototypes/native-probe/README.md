# ARM Linux build probe

This project-owned assembly program is a **local build experiment**, not an LG application, launcher or deployment mechanism. It has never been executed on the TV or in an emulator.

`probe.S` makes one Linux ARM EABI `write` attempt of the 24-byte marker `OPENCAST_NATIVE_PROBE_1\n` to inherited stdout, then calls `exit` with 0 for a full write or 1 otherwise. It opens no file, creates no network connection and changes no TV setting. There is no retry or loop. A single write may still block or receive a signal; output size is bounded, runtime is not. An eventual authorized starter must supply a known observable/nonblocking output channel or select a separately reviewed exit-only experiment.

`probe.ld` defines a fixed entry, one RX image and an RW/non-executable stack declaration. `build.py` runs only explicitly selected **host** Clang/LLD/LLVM tools. It writes to a new directory under ignored `artifacts/native-probe/`, removes execute permissions from the result, and checks ELF metadata with the repository readers. It never invokes the output. No compiler, linker or dependency is installed automatically.

See [build evidence and instructions](../../docs/native-probe-build.md) for the exact verified toolchain, command, hashes and unresolved execution/admission requirements. Do not copy the ELF into a USB app package or substitute it for a vendor executable.
