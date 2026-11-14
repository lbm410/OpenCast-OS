---
{
  "type": "Kernel Evidence",
  "title": "Kernel image",
  "description": "Decoded Linux image evidence and unresolved board-level dependencies.",
  "tags": [
    "kernel",
    "boot"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "decoded",
      "resource": "../../docs/lz4p-analysis.md"
    },
    {
      "id": "hardware",
      "resource": "../../docs/hardware.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: decoded image and CRCs",
    "PENDING: configuration and runtime board mapping"
  ]
}
---

# Kernel image

The selected kernel package decodes from LZ4P into a legacy uImage whose header and payload CRCs pass. Its metadata identifies an ARM Linux kernel; the decoded banner states Linux 3.0.13, GCC 4.5.1, SMP and PREEMPT. The network advertisement reports the same kernel version, without proving installed-byte identity.[^decoded][^hardware]

Kernel configuration, complete boot arguments, board definition, driver contracts and watchdog ownership remain unresolved. Missing configuration/zImage markers are bounded negative searches, not proof that configuration or an initramfs cannot be recovered. Load/entry fields are metadata, not measured physical RAM addresses.[^decoded]

Connect this image to [boot selection](/platform/boot.md), [ABI requirements](/platform/abi.md) and [partition metadata](/platform/partitions.md). An alternative kernel remains blocked by hardware support and [verified recovery](/execution/recovery.md).

[^decoded]: Bounded decoding, CRCs, banner and search limits.
[^hardware]: Device-reported kernel version.
