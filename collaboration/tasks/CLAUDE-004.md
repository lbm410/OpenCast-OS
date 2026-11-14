# CLAUDE-004 — process account application contract

## Objective

Determine how the account label in an admitted application record is consumed by the process manager before process creation. This is a bounded static compatibility study, not a launch mechanism or privilege request. Owner now reports the preferred Fable model has been restored; use the existing session configuration without model overrides.

## Ownership

- docs/process-account-contract.md
- artifacts/process-account-contract/ (ignored)

All other files are read-only. Codex owns integration, shared tools and knowledge. No commits or pushes. All technical writing in English; exclusive owner attribution rules remain in force.

## Context and experiment

Read docs/native-execution-conditions.md, docs/native-execution-policy.md and docs/native-admission.md first. The native account label game is metadata; effective credentials remain unknown. The policy producers were already traced by Codex and must not be duplicated. PM_HNDL_ExecuteProcess at0x16310 and PM_LIST_GetUserAccount are starting references in the already selected procmgr, not permission to send a method.

Pin the selected procmgr hash and consult existing symbol inventories. Trace only demonstrated calls from account lookup to the process creation/credential application path, up to8KiB total selected function ranges. Use reviewed host readers/disassembler, never execute target code or load vendor libraries. Establish whether the label is looked up, what failure branches do, and which explicit credential-related calls occur, if any. Distinguish a string/name, a numeric identity, a checked syscall and a live effective identity. Stop at unavailable implementation, indirect or policy boundary. Do not infer that a default, fallback or missing check grants permission to our program.

Produce a concise evidence table with source hash, addresses, return checks and unresolved contracts. Include reproducible captures under the ignored directory and an experiment record. No bulk extraction, device or LAN contact, IPC invocation, credential/key reads, protected package changes or system configuration changes. Existing static metadata only.

## Updated issuer evidence

Owner supplied a current New App Test screenshot: no App Type selector; the file area is labelled Web App. That form does not expose historical Marmalade/Unity choices. This does not prove every account/issuer route is unavailable. Do not fabricate a native package or modify the working registration.

Acknowledge receipt and active ownership in status before working. Freeze output with hashes for review. Any subagent must have disjoint assigned ownership; do not change configured models.
