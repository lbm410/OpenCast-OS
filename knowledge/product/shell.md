---
{
  "type": "Product Architecture",
  "title": "OpenCast replacement shell",
  "description": "A modern shell over retained vendor services is the leading unproven integration architecture.",
  "tags": [
    "shell",
    "product"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "architecture",
      "resource": "../../docs/architecture.md"
    },
    {
      "id": "prototype",
      "resource": "../../docs/shell-prototype.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: local prototype",
    "HYPOTHESIS: native coexistence",
    "PENDING: physical prototype and autostart"
  ]
}
---

# OpenCast replacement shell

OpenCast OS aims to replace the Smart TV experience, including direct startup when feasible. The leading architecture keeps original drivers and essential vendor services while hosting an independent shell. Native capabilities stay behind explicit adapters; unsupported operations must report unavailable rather than simulate success.[^architecture]

A conservative local prototype has Home, Apps, Inputs, Media and Settings, directional/pointer navigation and optional appearance storage. Desktop checks passed, but this artifact has not been physically validated. Its HDMI/app cards do not control the TV. The baseline [browser test](/execution/browser.md) is a separate artifact.[^prototype]

Integration depends on [graphics/input](/platform/graphics-input.md), [RELEASE coexistence](/platform/release.md) and a viable [app entry point](/execution/app-deployment.md). Automatic startup additionally depends on [boot supervision](/platform/boot.md) and [verified recovery](/execution/recovery.md).

[^architecture]: Intended product boundary and integration gates.
[^prototype]: Actual prototype behavior and validation scope.
