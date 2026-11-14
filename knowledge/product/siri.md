---
{
  "type": "Product Backlog",
  "title": "Deferred Siri bridge",
  "description": "Voice control is a separate local-adapter investigation, not a completed feature.",
  "tags": [
    "siri",
    "bridge",
    "deferred"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "voice",
      "resource": "../../docs/backlog.md"
    }
  ],
  "opencast_evidence": [
    "HYPOTHESIS: local authenticated bridge",
    "PENDING: pairing and action support"
  ]
}
---

# Deferred Siri bridge

The owner requested Siri control for television inputs, installed apps and possibly volume/power. This remains deferred so it does not interrupt boot and firmware research. The candidate chain is Siri → Shortcut → authenticated local bridge → individually verified UDAP action.[^voice]

Existing Home Assistant Netcast support is an evaluation option, not proof of exact-model HDMI or application behavior. A bridge needs an available host; a sleeping Mac cannot be assumed reachable. Launching a commercial app cannot restore unsupported streaming, certificates or DRM compatibility.[^voice]

The bridge depends on [local-control verification](/execution/local-control.md), not on replacing [RELEASE](/platform/release.md) or enabling [shell autostart](/product/shell.md). Keep traffic local, secrets outside Git and unsupported actions truthful. No bridge installation, pairing or control test is claimed.

[^voice]: Owner-requested deferred scope, candidates and acceptance criteria.
