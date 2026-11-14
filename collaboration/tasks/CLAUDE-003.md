# CLAUDE-003 — native runtime dependency contract

## Goal

Develop a useful offline tool for choosing a compatible native shell integration, not just a review. Map declared ELF shared-library dependencies among explicitly selected firmware files and surface missing providers without pretending to reproduce the dynamic loader.

## Ownership

- tools/elf_dependency_graph.py
- tests/test_elf_dependency_graph.py
- docs/native-linkage.md
- artifacts/native-linkage/ (ignored)

Read existing tools/elf_inventory.py and firmware selection reports before designing the interface. Reuse validated parsing where suitable; do not edit that shared reader without requesting ownership. Accept explicit regular-file inputs or an explicit locally prepared inventory, never a recursive scan of arbitrary roots. Bound file counts, sizes, graph expansion and malformed structures. Never run ldd or any extracted binary.

Produce deterministic JSON that distinguishes DT_NEEDED declarations, SONAME/basename candidate providers, unresolved dependencies and ambiguous providers. Do not equate candidate matching with link/runtime compatibility: report architecture/class/endianness mismatches and preserve ABI caveats. No secrets, full raw strings dump or proprietary data publication. Synthetic fixture tests must cover cycles, missing providers, ambiguity, malformed input and bounds. Inspect local selected RELEASE, fxui, appctrl and vendor graphics/runtime files where available; absent files are unresolved evidence, not grounds for uncontrolled extraction.

Use the output to identify concrete missing sysroot/graphics/lifecycle evidence for a nonpersistent native shell. Another Codex agent owns docs/native-entry-contract.md covering service admission; read it when available but do not edit it. Root owns CSS/shell integration and global KB.

You may delegate this task or CLAUDE-002 to separate agents with disjoint file ownership; explicitly coordinate and review their work. Do not change configured models, invoke provider workarounds, access TV/LAN, execute target code, commit or push. Report real agent runs accurately. Freeze output and notify Codex, then continue monitoring the mailbox.
