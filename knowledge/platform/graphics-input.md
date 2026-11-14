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
    },
    {
      "id": "execution",
      "resource": "../../docs/native-execution-gates.md"
    },
    {
      "id": "manifest",
      "resource": "../../docs/native-manifest-admission.md"
    },
    {
      "id": "provider",
      "resource": "../../docs/upctrl-manifest-gate.md"
    },
    {
      "id": "conditions",
      "resource": "../../docs/native-execution-conditions.md"
    },
    {
      "id": "appinfo",
      "resource": "../../docs/appinfo-provenance.md"
    },
    {
      "id": "policy",
      "resource": "../../docs/native-execution-policy.md"
    },
    {
      "id": "window",
      "resource": "../../docs/native-window-contract.md"
    },
    {
      "id": "window-allocation",
      "resource": "../../docs/native-window-allocation.md"
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

Native type conversion and executable-path construction exist in appctrl, including in its downloaded-type helper. This does not establish that the owner's USB package can obtain native admission: USB-test storage 3 now connects through provider retrieval and XML parsing to the converter.[^manifest] The provider tries local AppInfo before a protected fallback with a checked verifier call; AppInfo lookup specifically requires USB-test storage and a positive imported sample-support query; its producer, device policy and native acceptance remain unresolved.[^provider][^appinfo] XML app_type and a game account label are identified, but neither metadata nor loading/state checks establish effective privileges or permission to launch our artifact.[^conditions] A compiled ARM object, a framework record and a running native process are three different achievements.[^execution]

[^execution]: Four bounded type/path function traces and remaining native execution prerequisites.

[^manifest]: Connected USB-test storage/list, manifest provider and native conversion.
[^provider]: AppInfo-first handling, conditional protected fallback and verification boundary.
[^conditions]: Exact XML field provenance, account metadata and later execution conditions.

[^appinfo]: Storage3-only lookup, imported sample-support gate and bounded producer-search limits.

Concrete prohibition-flag producers use update XML/completion records for ordinary downloaded lists2/3. No direct native-type comparison or concrete USB-test list4 producer occurs in that slice; a clear flag still does not admit our ELF.[^policy]

[^policy]: Bounded update-policy producer trace and unresolved upstream authority.

Fxui passes a framework-provided window identifier to EGL. Home has a distinct stock binding that must not be reused. Process readiness can precede rendering; callback-managed EGL cleanup does not prove callback quiescence or restored Home focus. A future adapter must distinguish window assignment, graphics readiness and acknowledged return.[^window]

[^window]: First-window consumer, EGL callback wiring and partial-cleanup boundaries.

The generic window-ID receiver can reserve bookkeeping records. Its supplied-path condition, reply success and numeric validity do not establish authenticated ownership; surface creation and reset follow separate paths. No automatic cleanup or physical Home restoration follows from the selected receiver code.[^window-allocation]

[^window-allocation]: Independently reproduced receiver, pool and reset ranges; no IPC invocation.
