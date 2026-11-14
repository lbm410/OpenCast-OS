---
{
  "type": "Platform Contract",
  "title": "Firmware ABI",
  "description": "ARM executable evidence without claiming an established native deployment environment.",
  "tags": [
    "arm",
    "abi"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "boot",
      "resource": "../../docs/boot-dependencies.md"
    },
    {
      "id": "decoded",
      "resource": "../../docs/lz4p-analysis.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static ARM32 little-endian EABI5",
    "PENDING: floating-point convention and full ABI"
  ]
}
---

# Firmware ABI

Selected official binaries, including BusyBox, lginit, browser lb6wk and RELEASE, are ELF32 little-endian ARM EABI5. Dynamic examples request /lib/ld-linux.so.3; the shipped loader and libc filenames indicate 2.12.2. lginit lacks interpreter and dynamic dependencies, consistent with static linkage.[^boot]

The parsed flags do not settle floating-point calling convention. Compiler selection also requires symbol versions, architecture attributes and library contracts; an ARM cross-compile alone cannot prove the result runs safely. The DLNA i686 banner does not override actual firmware ELF metadata.[^boot][^decoded]

The [kernel](/platform/kernel.md) constrains native execution, while [RELEASE dependencies](/platform/release.md) and [graphics/input](/platform/graphics-input.md) constrain integration. A native build remains separate from an authorized, reversible [deployment route](/execution/app-deployment.md).

[^boot]: Executable metadata and interpreter inventory.
[^decoded]: Validated RELEASE ELF extent and unresolved float ABI.
