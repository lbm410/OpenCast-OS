---
{
  "type": "Experiment Result",
  "title": "Physical browser probe",
  "description": "Own code ran on the TV, while direct D-pad input and repeat-load acceptance remain incomplete.",
  "tags": [
    "browser",
    "physical-test"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "probe",
      "resource": "../../docs/hello-world.md"
    },
    {
      "id": "v2",
      "resource": "../../docs/input-probe-v2.md"
    },
    {
      "id": "app",
      "resource": "../../docs/app-deployment.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: physical baseline and Home return",
    "PENDING: direct D-pad and V2 physical results"
  ]
}
---

# Physical browser probe

The owner observed the baseline page on the television, activated buttons and returned to the Smart menu with Home. Two device reports arrived. In that browser context, remote arrows moved a cursor and no keydown events reached the page; native NetCast cards respond differently.[^probe]

That establishes physical browser execution, not direct D-pad navigation, repeated deployment, native integration or completed M3 acceptance. The baseline session ended and its server stopped. V2 adds bounded key/focus observations and explicit focus verification; its physical result is still pending in the experiment record.[^v2]

The later [packaged application](/execution/app-deployment.md) renders with working arrows/OK according to the owner; that separate context does not retroactively change the browser probe result.[^app] [Graphics/input analysis](/platform/graphics-input.md) addresses the native boundary. The [shell prototype](/product/shell.md) must receive its own physical evaluation, with [validation scopes](/engineering/validation.md) kept explicit.

[^probe]: Owner-correlated baseline result and remaining acceptance criteria.
[^v2]: Focus/event instrumentation and pending physical experiment.

[^app]: Official packaged-launch result and performance limits.
