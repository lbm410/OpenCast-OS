# Independent Claude review assignment

Read CLAUDE.md and AGENTS.md first. This assignment is for the owner's already-open interactive Claude Code session; creation of this file does not mean that session has read or executed it.

## Scope and ownership

Audit the boot and recovery assumptions for OpenCast OS on LG 47LA620S-ZA, firmware 04.28.17. You own only `docs/claude-boot-review.md`. Read all other files without modifying them. Do not commit, push, contact the TV, change settings, execute extracted firmware, or invoke proprietary payloads. Never include key values, credentials or unique device identifiers in reports.

Codex's firmware agent owns extraction tools and firmware lab outputs. Do not duplicate extraction or mutate its output. Its ongoing results may be read once complete: `artifacts/firmware-lab/manifest.json`, `artifacts/firmware-lab/extraction.json`, `docs/firmware-extraction.md`, and packages under `firmware/lab/packages/`. Public documents and static byte-level inspection are permitted.

## Deliverable

Produce an evidence-based boot/recovery review: confirmed facts with file paths and offsets or source URLs; unsupported assumptions; launcher/display/input/audio/tuner/power/watchdog dependency questions; what a viable recovery procedure must demonstrate; and the highest-value next static tests. Distinguish firmware evidence from observations on the physical unit. A signed vendor update is not proof of recovery after a failed boot. Do not assert launcher replacement is feasible until its dependencies are identified.

Use English. Honor exclusive author identity `lbm410 <lbm410@inlumine.ual.es>`, with no coauthor trailers or AI attribution. End with a short Spanish report in the owner's terminal stating the report path and whether any further owner intervention is essential.
