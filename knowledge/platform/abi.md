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
    },
    {
      "id": "linkage",
      "resource": "../../docs/native-linkage.md"
    },
    {
      "id": "probe-build",
      "resource": "../../docs/native-probe-build.md"
    },
    {
      "id": "lifecycle-arm",
      "resource": "../../docs/native-lifecycle-arm-build.md"
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
[^attributes]: Reviewed attribute parser, 85 synthetic tests and 18-file calling-convention evidence.
[^chromium]: Three exact selected files, explicit VFP-loader attribute and Chrome's different interpreter path.

The fixed19-file dependency sample declares241DT_NEEDED edges and10interpreters over105names; nine names have inspected candidates and96remain listing-only in that sample. These are name matches, not symbol resolution or loader selection. libscf imports D-Bus calls without declaring their provider directly, so even complete declared dependencies would not establish a working link contract.[^linkage]

[^linkage]: Bounded dependency graph, reviewed identity/budget handling and unresolved providers.

An original minimal probe links locally to a 648-byte ARM EABI5 ET_EXEC with explicit entry, RX image and no dynamic dependencies, reproduced and independently inspected. This closes a build step only: it does not identify physical ISA support, supply an admitted starter or link the graphics/lifecycle client.[^probe-build]

[^probe-build]: Existing-host-tool link, independent byte inspection and unresolved target execution.

The current window-ownership lifecycle core separately compiles to a reproducible3,344-byte ARM EABI5 relocatable object with no reported undefined symbols. It is not the648-byte executable probe, a linked graphics client or target execution. Compiler architecture/attribute permissions remain distinct from physical hardware and vendor ABI verification.[^lifecycle-arm]

[^lifecycle-arm]: Current-source cross-compilation and independent object rebuild; no link, emulation or execution.
