---
{
  "type": "Engineering Practice",
  "title": "Evidence and validation scopes",
  "description": "Host tests, static firmware results and physical observations answer different questions.",
  "tags": [
    "testing",
    "evidence"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "review",
      "resource": "../../docs/tool-review.md"
    },
    {
      "id": "probe",
      "resource": "../../docs/hello-world.md"
    },
    {
      "id": "extraction",
      "resource": "../../docs/firmware-extraction.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: recorded host and physical results",
    "PENDING: broader device acceptance"
  ]
}
---

# Evidence and validation scopes

Treat evidence as documentary, local/static, device-reported or physically observed; preserve unresolved hypotheses explicitly. A host test validates its tested behavior, not NetCast compatibility or television performance. Report quotas, malformed metadata, parser budgets and incomplete inventories have dedicated review regressions.[^review]

Firmware signature coverage must name the key provenance and verified spans; CRCs validate reconstruction, not publisher identity. Never execute extracted binaries to inspect them. Keep raw captures, vendor images and sensitive material ignored.[^extraction]

Physical acceptance requires owner-correlated display, actual remote behavior, normal exit, repeatability and essential-function checks. Uploads cannot certify themselves.[^probe] Apply these distinctions to [browser results](/execution/browser.md), [native ABI](/platform/abi.md) and the [recovery gate](/execution/recovery.md). Use [bounded knowledge loading](/engineering/knowledge-loading.md) to retrieve only relevant evidence paths.

[^review]: Reproduced host-tool findings and regression scope.
[^probe]: Physical acceptance criteria and incomplete baseline coverage.
[^extraction]: Static-analysis controls and signature limits.
