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
    },
    {
      "id": "services",
      "resource": "../../docs/service-supervision.md"
    },
    {
      "id": "selection",
      "resource": "../../docs/boot-selection.md"
    },
    {
      "id": "kernel-init",
      "resource": "../../docs/kernel-init-selection.md"
    },
    {
      "id": "static-entry",
      "resource": "../../docs/static-initializer-entry.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: static script chain and init candidate",
    "PENDING: actual PID1 and active branches"
  ]
}
---

# Boot and init chain

The shipped inittab invokes rcS, which reaches rc.local. Its bootmode=auto branch enters the lginit directory and runs lginit in the foreground. This script chain is not demonstrated as the ordinary active boot path. No respawn entry appears in inittab; supervision is declared separately in vendor service lists.[^boot]

Kernel instructions establish this candidate order: retained rdinit (possibly the conditional /init default), explicit init, then /mnt/lg/lginit/lginit and /bin/sh as failure fallbacks. Parameter callbacks write the same slots read by this path. Therefore direct lginit entry is a concrete static path, but early filesystem contents, actual command line and live PID1 remain unobserved. A fallback shell string/call is not a usable recovery procedure.[^kernel-init]

A separate sbin/init binary contains INIT_VERSION=sysvinit-2.86, but its actual PID1 selection remains unverified. rcS's ext2 /dev/ram remount conflicts with the SquashFS root package unless another stage or vestigial code explains it. Development-service branches are static evidence, not enabled interfaces.[^partition]

The normal service list gives RELEASE a reboot policy and runs Home.swf through separate fxui with respawn. A separate list starts SWUE. Actual list selection and full failure semantics remain unobserved.[^services]

[Partition pairs](/platform/partitions.md) do not resolve boot selection. [RELEASE](/platform/release.md) and [graphics/input](/platform/graphics-input.md) require lifecycle analysis before separation. Automatic [shell startup](/product/shell.md) remains blocked by supervision and [recovery](/execution/recovery.md).

[^boot]: Script call chain and foreground invocation.
[^partition]: SysV-init candidate and unresolved RAM-root question.

[^services]: Selected service lists and bounded procmgr analysis; static declarations only.

Static bootloader tracing finds a conditional init=/sbin/init append only in the nfs bootmode branch. Compiled bootmode=auto is not a live environment read; earlier bootargs may already include an init value. SWU-selection reads and a separate write-like path do not establish a safe recovery command.[^selection]

[^selection]: Bounded bootloader control-flow analysis and unresolved runtime state.
[^kernel-init]: Independently traced parameter slots, early /init condition and exec-style fallback order.

The static initializer entry supplies candidate0x82ac to a libc-style startup call. Its bounded prefix has a zero phase-pointer literal, unlike the dynamic initializer; APP_START is passed to an unnamed callee whose zero return branches to0x853c. Candidate extent, callee identity, successor behavior and actual unit startup remain unverified. Do not transfer dynamic initializer API names or recovery behavior by resemblance.[^static-entry]

[^static-entry]: Independently reviewed entry and256-byte prefix, explicit literal values and branch successors; no target execution.
