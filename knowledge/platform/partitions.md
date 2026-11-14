---
{
  "type": "Storage Layout",
  "title": "Partition-map evidence",
  "description": "Static paired storage regions do not establish active banks or automatic rollback.",
  "tags": [
    "partitions",
    "recovery"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "map",
      "resource": "../../docs/partition-layout.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: update-map structure",
    "PENDING: active physical layout and rollback"
  ]
}
---

# Partition-map evidence

The signed part payload matches LG partinfo v2 with an 80-byte header and 128 fixed-size slots. It declares 64 non-overlapping entries and leaves 64 slots zero. Twenty names occur twice with equal sizes and filenames, including kernel, rootfs, lginit, lgapp and base.[^map]

First copies carry used/master metadata; second copies have different flags. Both EPK-version fields and every file-size field are zero, supporting an update-template interpretation. There is one boot entry and separate partinfo/mapbak entries. The reserved tail extends beyond declared usable size; its 4-GiB endpoint is not measured physical capacity.[^map]

The map derives from [firmware analysis](/platform/firmware.md). It constrains [boot research](/platform/boot.md), but neither paired regions nor mapbak pass the [recovery gate](/execution/recovery.md).

[^map]: Complete parsed map, bounds, duplicate groups and limits.
