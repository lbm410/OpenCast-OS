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
    },
    {
      "id": "attributes",
      "resource": "../../docs/arm-abi.md"
    },
    {
      "id": "chromium",
      "resource": "../../docs/chromium-abi.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static ARM32 little-endian EABI5",
    "CONFIRMED: 18 selected files declare the base floating-point calling convention",
    "PENDING: symbol versions, complete library contracts and physical CPU"
  ]
}
---

# Firmware ABI

Selected official binaries, including BusyBox, lginit, browser lb6wk and RELEASE, are ELF32 little-endian ARM EABI5. Dynamic examples request /lib/ld-linux.so.3; the shipped loader and libc filenames indicate 2.12.2. lginit lacks interpreter and dynamic dependencies, consistent with static linkage.[^boot]

The ELF flags alone did not settle floating-point calling convention. The reviewed attribute reader now establishes the base procedure-call convention for 18 selected files: 17 permit Arm v7 application-profile instructions and floating-point hardware use; sysvinit permits Arm v6KZ without FP hardware. Instruction permission is not a CPU measurement or proof that a particular instruction occurs. This is a selected sample, not a firmware-wide census.[^attributes]

The later Chromium-tree check finds a VFP-declaring loader, but Chrome and its adjacent libstdc++ declare base PCS; Chrome requests /lib/ld-linux.so.3. No matching libc member occurs under that subtree in the inspected image. This confirms mixed declarations, not a complete separate hard-float Chromium runtime.[^chromium]

Compiler selection still requires symbol versions and library contracts; an ARM cross-compile alone cannot prove the result runs safely. The DLNA i686 banner does not override firmware ELF metadata. Calls carrying floating-point values must agree at their ABI boundary; an ABI match alone does not establish loader or application compatibility.[^boot][^decoded][^attributes]

The [kernel](/platform/kernel.md) constrains native execution, while [RELEASE dependencies](/platform/release.md) and [graphics/input](/platform/graphics-input.md) constrain integration. A native build remains separate from an authorized, reversible [deployment route](/execution/app-deployment.md).

[^boot]: Executable metadata and interpreter inventory.
[^decoded]: Validated RELEASE ELF extent; historical flags-only ABI uncertainty.
[^attributes]: Reviewed attribute parser, 79 synthetic tests and 18-file calling-convention evidence.
[^chromium]: Three exact selected files, explicit VFP-loader attribute and Chrome's different interpreter path.
