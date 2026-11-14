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
    "CONFIRMED: packaged TV rendering and arrows/OK; slow startup/navigation",
    "HYPOTHESIS: native coexistence",
    "PENDING: acceptable performance and autostart"
  ]
}
---

# OpenCast replacement shell

OpenCast OS aims to replace the Smart TV experience, including direct startup when feasible. The leading architecture keeps original drivers and essential vendor services while hosting an independent shell. Native capabilities stay behind explicit adapters; unsupported operations must report unavailable rather than simulate success.[^architecture]

The owner uses a PS5 for commercial streaming. Current Netflix/YouTube apps on the TV are not required; prioritize measured responsiveness, remote navigation, HDMI, audio, essential settings and reliability. Console/CEC control remains untested.[^architecture]

A conservative local prototype has Home, Apps, Inputs, Media and Settings, directional/pointer navigation and optional appearance storage. The official USB-packaged baseline now renders on the TV with owner-confirmed arrows and OK, but both launch and navigation are slow. A lighter candidate reduces redundant DOM writes and painting complexity; its TV performance is unmeasured. Its HDMI/app cards do not control the TV. The baseline [browser test](/execution/browser.md) is a separate artifact.[^prototype]

Integration depends on [graphics/input](/platform/graphics-input.md), [RELEASE coexistence](/platform/release.md) and a viable [app entry point](/execution/app-deployment.md). Automatic startup additionally depends on [boot supervision](/platform/boot.md) and [verified recovery](/execution/recovery.md).

[^architecture]: Intended product boundary and integration gates.
[^prototype]: Actual prototype behavior and validation scope.
