---
{
  "type": "Native Component",
  "title": "RELEASE system application",
  "description": "The main executable is coupled to television services, not proven to be a disposable launcher.",
  "tags": [
    "native",
    "services"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "decoded",
      "resource": "../../docs/lz4p-analysis.md"
    },
    {
      "id": "native",
      "resource": "../../docs/native-interfaces.md"
    },
    {
      "id": "services",
      "resource": "../../docs/service-supervision.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: ELF and dependency/symbol evidence",
    "LIKELY: essential television responsibilities"
  ]
}
---

# RELEASE system application

The lgap package decodes into LG CramFS with a validated RELEASE file extent. That ARM32 executable has 43 direct dynamic dependencies, including MTK, graphics, audio/video, native-player and vendor API libraries. Static symbol evidence includes HDMI functions and a MICOM-watchdog reset import.[^decoded][^native]

These relationships support essential-function coupling; they do not prove exact process ownership, callable prototypes or watchdog policy. Terminating RELEASE to replace the screen has not been shown safe. The normal service list explicitly separates RELEASE (reboot policy) from fxui Home.swf (respawn), strengthening the coexistence hypothesis without proving a safe replacement method.[^services][^native]

A separate [OpenCast shell](/product/shell.md) depends on a verified coexistence boundary through [graphics/input](/platform/graphics-input.md), the shipped [ABI](/platform/abi.md) and [boot lifecycle](/platform/boot.md). Root access would not resolve those dependencies or supply [recovery](/execution/recovery.md).

[^decoded]: Application filesystem and RELEASE dependency inventory.
[^native]: Native symbols, imports and architecture consequence.

[^services]: Selected service lists and bounded procmgr analysis; static declarations only.
