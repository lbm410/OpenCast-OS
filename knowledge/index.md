---
{"okf_version":"0.2"}
---

# OpenCast knowledge routes

Small task concepts point to their dependencies and detailed evidence. Start with one route; load immediate neighbors only. All concept summaries are draft. Static firmware, device reports and physical tests are separate evidence classes. No installed replacement OS or verified recovery is claimed.

## Choose a task

- [Replacement shell](/product/shell.md) — architecture, native dependencies and startup blockers.
- [Actual TV execution](/execution/browser.md) — physical baseline, remote-input limit and next comparison.
- [Native build](/platform/abi.md) — proven executable metadata and unresolved ABI requirements.
- [Boot or persistent changes](/execution/recovery.md) — recovery gate, boot chain and partition evidence.
- [Firmware analysis](/platform/firmware.md) — integrity coverage, decoded kernel and storage map.
- [Siri control](/product/siri.md) — deferred local bridge; no pairing or control success claimed.

## Browse a group

- [Platform](platform/index.md) — target, firmware, ABI, kernel, boot, RELEASE, partitions, graphics/input.
- [Execution](execution/index.md) — browser, packaged apps, LAN control and recovery.
- [Product](product/index.md) — replacement shell and deferred Siri integration.
- [Engineering](engineering/index.md) — evidence scopes and bounded knowledge loading.

## Retrieval budget

From the repository root, use `python3 -m tools.knowledge --bundle knowledge overview`, then `search QUERY` if the seed is unclear. Load a seed with `context product/shell --depth 1 --max-nodes 8 --byte-budget 12000`. Expand only the next unresolved relationship. Source references outside the bundle do not auto-open; consult their detailed reports deliberately. See [loading rules](/engineering/knowledge-loading.md) and [change history](log.md).
