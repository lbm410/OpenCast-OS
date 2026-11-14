---
{
  "type": "Firmware Evidence",
  "title": "Official firmware evidence",
  "description": "Container identity, integrity coverage and preserved offline analysis inputs.",
  "tags": [
    "firmware",
    "signatures"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "extraction",
      "resource": "../../docs/firmware-extraction.md"
    },
    {
      "id": "provenance",
      "resource": "../../docs/firmware.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static structure and full segment signature audit",
    "PENDING: independent publisher key chain"
  ]
}
---

# Official firmware evidence

The officially applicable 04.28.17 distribution contains historical EPK2 with 24 packages and 118 segments. The encrypted header identifies internal version 04.28.17.01 and the MTK-associated OTA family; historical layout explains the earlier EPK3 heuristic match.[^extraction]

A separate full audit verifies the exact header and all118 segment signatures across24 packages against a community-distributed public key, with an in-memory mutation rejected. The earlier extraction covered77 segments in11 packages. This is not an independently established LG certificate chain or proof of what the TV checks during boot. Original hashes and read-only files are preserved; vendor content stays outside Git.[^extraction][^provenance]

This evidence supports [ABI](/platform/abi.md), [kernel](/platform/kernel.md) and [partition](/platform/partitions.md) analysis. CRC checks on decoded data are separate integrity checks. Follow [validation boundaries](/engineering/validation.md) before extending parsers.

[^extraction]: Controlled extraction, exact verification coverage and immutable artifacts.
[^provenance]: Official applicability and acquisition provenance.
