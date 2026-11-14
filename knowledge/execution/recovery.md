---
{
  "type": "Safety Gate",
  "title": "Recovery gate",
  "description": "Persistent integration requires a demonstrated recovery procedure for this exact hardware.",
  "tags": [
    "recovery",
    "persistence"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "recovery",
      "resource": "../../docs/recovery.md"
    },
    {
      "id": "map",
      "resource": "../../docs/partition-layout.md"
    },
    {
      "id": "architecture",
      "resource": "../../docs/architecture.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: project boundary",
    "PENDING: independently demonstrated recovery"
  ]
}
---

# Recovery gate

No independently demonstrated recovery procedure exists for this television in the project evidence. Ordinary vendor updating, privileged access and duplicate partition names are insufficient substitutes. A failure in boot, selectors, shared state or unique device data may defeat otherwise duplicated application regions.[^recovery][^map]

Before persistent or privileged device changes, establish exact compatibility, affected components, failure modes, a tested recovery path, reversal and specific owner authorization. Read-only local analysis can continue independently. An executable built for ARM or a successful browser test does not satisfy this gate.[^architecture]

The unresolved [boot chain](/platform/boot.md) and [partition selection](/platform/partitions.md) are direct blockers to automatic [OpenCast startup](/product/shell.md). [Validation discipline](/engineering/validation.md) must separate host-tool robustness from actual recovery evidence.

[^recovery]: Recovery status and required protections.
[^map]: Paired-map limits and open recovery questions.
[^architecture]: Integration decision gates.
