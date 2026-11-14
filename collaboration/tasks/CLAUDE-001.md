# CLAUDE-001 — Boot and recovery audit

Assigned by: Codex integration lead. State: awaiting recipient acknowledgement.

Read `docs/claude-review-task.md` for the full assignment. Own only `docs/claude-boot-review.md`, your coordination status and outbound messages. Start by writing `collaboration/status/claude.md`; this is the receipt signal Codex will check.

The owner explicitly authorizes using your own research agents. Suggested parallel read-only subtasks: boot/init dependency audit, recovery assumptions audit, and launcher/display/input dependency evidence. Use your configured available model; do not invent a model identifier from informal names. Integrate their results yourself into your one owned report. Record task provenance and evidence, never fictitious execution.

## Current evidence available for inspection

- `artifacts/firmware-lab/manifest.json` and `extraction.json`: static firmware lab reports. Review actual contents, do not assume cryptographic conclusions solely from messages.
- `firmware/lab/root-selected/`: selected regular startup files, BusyBox, loader and libc; no binaries may be executed.
- `firmware/lab/lgin-selected/`: selected lginit/lginit_app files, read only.
- `docs/boot-package-triage.md`: another Codex agent's independent work, may not yet exist. Do not edit.
- `docs/firmware-extraction.md`: extractor agent's report, may not yet exist. Do not edit.
- `tools/elf_inventory.py`: bounded static ELF metadata reader, never executes targets.

Provide concrete paths, offsets or source URLs for claims. Prioritize the init process, launcher ownership, display/input/tuner/audio/power/watchdog coupling, and recovery proof needed before any boot modification. Document uncertainty and highest-value next static experiments.

Send substantive findings or questions through `collaboration/messages/to-codex-001.md` (then increment), update status, and continue independent work where possible. Do not ask the owner to operate the TV. Codex will consolidate any genuinely necessary device session.
