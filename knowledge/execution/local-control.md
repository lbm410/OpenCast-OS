---
{
  "type": "Network Capability",
  "title": "Read-only LAN surface",
  "description": "Discovery established UDAP and DLNA descriptions, not tested television control actions.",
  "tags": [
    "udap",
    "lan"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "hardware",
      "resource": "../../docs/hardware.md"
    },
    {
      "id": "voice",
      "resource": "../../docs/backlog.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: discovery and read-only descriptions",
    "PENDING: pairing and control actions"
  ]
}
---

# Read-only LAN surface

Bounded SSDP discovery matched the target model and firmware. Its UDAP and DLNA descriptors returned successfully; advertised services include netrcu, mobilehome, smartText, AppToApp and media-renderer interfaces. No pairing, native action or SOAP control operation was established by those reads.[^hardware]

An advertised action is only an investigation lead. Input switching, installed-app enumeration, application launch, volume and standby/wake need separate verified contracts and owner coordination. Credentials and unique identifiers belong in ignored local operational records, never the knowledge bundle.[^voice]

A future [Siri bridge](/product/siri.md) may consume individually validated actions. This is independent of [shell replacement](/product/shell.md) and must not become an exposed root console or Internet-facing TV service. Current [validation](/engineering/validation.md) covers diagnostic boundaries, not successful control.

[^hardware]: Confirmed service descriptions and their limits.
[^voice]: Deferred action-by-action bridge investigation.
