---
{
  "type": "Integration Boundary",
  "title": "Graphics and input boundary",
  "description": "Static graphics/runtime evidence and the unresolved path to native remote navigation.",
  "tags": [
    "graphics",
    "input"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "boot",
      "resource": "../../docs/boot-dependencies.md"
    },
    {
      "id": "native",
      "resource": "../../docs/native-interfaces.md"
    },
    {
      "id": "lifecycle",
      "resource": "../../docs/app-lifecycle.md"
    },
    {
      "id": "admission",
      "resource": "../../docs/native-admission.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static configuration and message wrapper",
    "PENDING: runtime access and argument semantics"
  ]
}
---

# Graphics and input boundary

Shipped DirectFB configuration names SaWMan and a 960×540 layer; the Home.swf manifest declares 1280×720. Neither is a measurement of active rendering resolution. The browser links DirectFB/Fusion, WebKitGTK and vendor television libraries.[^boot]

Static disassembly shows an input-dispatch wrapper constructing a named vendor-service message and waiting for a reply. A later static trace identifies the process-manager receiver and input-manager dispatch path; runtime argument semantics, transport access and authorization remain unresolved.[^lifecycle] D-Bus-like strings do not establish an unrestricted standard endpoint; no message was sent.[^native]

This boundary connects [RELEASE](/platform/release.md) to a possible separate [shell](/product/shell.md). Physical [browser input](/execution/browser.md) currently differs from native card navigation, motivating the [packaged-application comparison](/execution/app-deployment.md). Configuration, symbols and screenshots cannot substitute for measured focus routing or display ownership.

[^boot]: Graphics configuration, Home manifest and browser dependencies.
[^native]: Input-dispatch wrapper reconstruction and its limits.

The native entry study separates app metadata, process registration, graphics surface ownership, focus and teardown. Procmgr can create records after managed launch or through an outer message-dispatch fallback, so an inner lookup is not proof that pre-launch is mandatory. Sender authentication and runtime admission remain unverified.[^admission]

[^lifecycle]: Matched native receiver and lifecycle call paths.
[^admission]: Corrected dual process-table creation paths and unresolved bus policy.
