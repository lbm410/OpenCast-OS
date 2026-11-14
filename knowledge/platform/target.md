---
{
  "type": "Hardware Target",
  "title": "Target television",
  "description": "Exact target identity and the boundary between owner, network and physical hardware evidence.",
  "tags": [
    "netcast",
    "hardware"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "hardware",
      "resource": "../../docs/hardware.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: owner/device reports",
    "PENDING: physical silicon and memory"
  ]
}
---

# Target television

The target is LG 47LA620S-ZA, a 2013 NetCast television. The owner reports a 47-inch Full HD panel and firmware 04.28.17; bounded network discovery independently received the matching model and firmware strings. These announcements are self-reported, not cryptographic device attestation.[^hardware]

MTK5398/M13 is a strong firmware-supported lead, while exact physical silicon, RAM, GPU and active storage remain unmeasured. The displayed SDK 03.05 must not be equated with a public SDK release. NetCast is not webOS.[^hardware]

Use [firmware provenance](/platform/firmware.md) and [ABI evidence](/platform/abi.md) for static implementation decisions. Use [local control](/execution/local-control.md) for the verified network surface. None establishes a safe [recovery mechanism](/execution/recovery.md).

[^hardware]: Target hardware evidence and read-only discovery record.
