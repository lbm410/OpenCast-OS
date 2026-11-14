# CLAUDE-005 — process credential field provenance

## Objective and boundaries

Continue the bounded static compatibility study by identifying the demonstrated writer of process-record uid/gid fields +0x8/+0xc. CLAUDE-004 stays frozen for independent review. This is evidence about existing vendor records, not permission or a mechanism to introduce new records or execute software on the TV.

## Ownership

- docs/process-account-provenance.md
- artifacts/process-account-provenance/ (ignored)

All other files read-only. No commits or pushes. English technical writing; owner-only attribution. Keep the existing owner-selected model; no model overrides. Scoped read-only subagent review is permitted if useful, with its artifacts under the owned directory.

## Procedure

Pin the same already-selected procmgr. Start at PM_PROC_InsertProcTable (0x1a7f0), PM_PROC_UpdateCreateProcApp (0x1b7f4), and PM_LIST_AllocSvc (0x3b410), using existing symbol extents. Follow demonstrated data flow only, up to 8 KiB total new function ranges. Reuse reviewed import resolution. Determine whether numbers are constants, parsed fields, direct copies or results from a demonstrated resolver. Missing named imports alone cannot exclude inline resolution, direct syscalls, indirect calls or another binary. Stop at an unavailable/indirect boundary and say exactly what remains unresolved.

Distinguish list-account string, process-record fields, credential call ordering and real device identity. Do not inspect credential files or collect secrets; no device/LAN/IPC, extracted-code execution, emulation, vendor-library loading, protected metadata changes or system configuration. Do not duplicate the graphics allocator task owned by firmware_extract.

Include input hashes, selected ranges and total, checked branches, evidence labels and a reproducible experiment. Freeze report/capture hashes in a new to-codex message. Check the mailbox between work units; bounded waits only while the actual session remains active.
