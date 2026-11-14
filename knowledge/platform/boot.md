---
{
  "type": "Boot Dependency",
  "title": "Boot and init chain",
  "description": "Shipped startup paths and the gaps before asserting live process supervision.",
  "tags": [
    "boot",
    "init"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "boot",
      "resource": "../../docs/boot-dependencies.md"
    },
    {
      "id": "partition",
      "resource": "../../docs/partition-layout.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static script chain and init candidate",
    "PENDING: actual PID1 and active branches"
  ]
}
---

# Boot and init chain

The shipped inittab invokes rcS, which reaches rc.local. Its bootmode=auto branch enters the lginit directory and runs lginit in the foreground. No respawn entry appears in the inspected inittab, so automatic restart after termination cannot be assumed.[^boot]

A separate sbin/init binary contains INIT_VERSION=sysvinit-2.86, but its actual PID1 selection remains unverified. rcS's ext2 /dev/ram remount conflicts with the SquashFS root package unless another stage or vestigial code explains it. Development-service branches are static evidence, not enabled interfaces.[^partition]

[Partition pairs](/platform/partitions.md) do not resolve boot selection. [RELEASE](/platform/release.md) and [graphics/input](/platform/graphics-input.md) require lifecycle analysis before separation. Automatic [shell startup](/product/shell.md) remains blocked by supervision and [recovery](/execution/recovery.md).

[^boot]: Script call chain and foreground invocation.
[^partition]: SysV-init candidate and unresolved RAM-root question.
