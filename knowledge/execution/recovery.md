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
    },
    {
      "id": "updater-entry",
      "resource": "../../docs/recovery-entry-contract.md"
    },
    {
      "id": "static-entry",
      "resource": "../../docs/static-initializer-entry.md"
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

The selected dynamic initializer's update-mode branch still attempts the ordinary process manager and has an apparently truncated service-list assignment. Shared mount code exists, but the static initial phase is not established by that dynamic binary. Neither the full-path literal, separate SWUE image nor continuing mount/error path proves independent recovery.[^updater-entry]

[^updater-entry]: Independently reviewed phase, formatting and shared-dependency evidence; physical recovery remains untested.

The stripped static initializer now has a reviewed ELF-entry anchor: its argument setup supports a main candidate at0x82ac. The candidate body, startup callee identity, function extent and physical boot selection remain unverified; this is an address for further bounded study, not a recovery entry procedure.[^static-entry]

[^static-entry]: Entry-only instruction/literal verification and explicitly inferential libc contract comparison.
