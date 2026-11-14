---
{
  "type": "Knowledge Navigation",
  "title": "Bounded knowledge loading",
  "description": "Load one task concept and its immediate neighbors before opening detailed reports.",
  "tags": [
    "knowledge",
    "okf",
    "context-budget"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "okf",
      "resource": "https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/SPEC.md"
    },
    {
      "id": "instructions",
      "resource": "../../AGENTS.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: project navigation convention",
    "PENDING: independent concept review"
  ]
}
---

# Bounded knowledge loading

This OKF 0.2 bundle is a compact graph over detailed project reports. File paths without .md are concept IDs; normal Markdown links express relationships, and source IDs join claim footnotes to evidence locations. Index and log files are navigation/history rather than concepts.[^okf]

Start at the task route in the root index. Load one seed and depth-one neighbors, initially capped at eight nodes and 12,000 bytes. Expand only an unresolved dependency; open a detailed source deliberately when a claim needs checking. Source paths outside the bundle are references, not automatically loaded instructions.

All concepts currently remain draft and omit verified events; evidence labels do not imply independent review. Preserve [validation distinctions](/engineering/validation.md), sensitive-artifact exclusions and the detailed reports as experiment records.[^instructions] For integration work, begin with [shell dependencies](/product/shell.md); for safety, begin with [recovery](/execution/recovery.md).

[^okf]: Pinned Open Knowledge Format specification, version 0.2.
[^instructions]: Project working and evidence instructions.
