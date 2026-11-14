# Collaboration on OpenCast OS

Read AGENTS.md, README.md, docs/handover.md and docs/decisions.md. Apply the same risk, evidence, language and Git rules.

Use `knowledge/index.md` for progressive context loading; follow the bounded retrieval commands in `docs/knowledge-format.md`. Do not repeatedly load every report. Treat compact concepts as pointers to evidence, not replacements for checking a critical source. Check truncation and preserve uncertainty. The channel's assigned file ownership still applies to knowledge edits.

## Mandatory authorship and integration rules

- All new commits and PRs must use only `lbm410 <lbm410@inlumine.ual.es>` as author.
- Never add `Co-Authored-By`, `Generated with`, AI attribution, or another author.
- Do not commit or push for the current review task. Before any later authorized commit or push, fetch and check branch, divergence and owner changes; never commit behind origin/main. Push requires an explicit owner request.
- Write all engineering documentation, code comments and technical instructions in English. Discuss progress with the owner in Spanish.
- Coordinate file ownership with Codex. The current independent Claude task is defined in `docs/claude-review-task.md`; do not edit other agents' files.

Codex integrates tools, prototypes and tests. Claude Code can independently review architecture, firmware and decisions. Assign explicit files without overlapping writes; use worktrees once a valid Git baseline is available. Do not create commits or push automatically.

Suggested first task: audit docs/platform-research.md and build a boot dependency matrix from verified official firmware evidence. Report facts with paths/offsets/hashes, clearly separate hypotheses and challenge unsupported assumptions. Do not connect to the TV or execute extracted code. Never include secrets in prompts or reports.

## Shared coordination channel

Read `collaboration/README.md` and the current assignment `collaboration/tasks/CLAUDE-001.md`. Write an acknowledgement in `collaboration/status/claude.md` before starting. Codex coordinates assignments and integration through these files. The owner explicitly authorizes Claude to use its own agents for scoped parallel research, with disjoint ownership. Re-read the channel between work units and before ending a turn; follow its bounded waiting protocol. Never ask the owner to relay routine agent messages.

Observation, 2026-11-14: Claude Code CLI is installed. The initial authentication check was false; a later check confirmed authentication after the owner opened an interactive session. Authentication does not prove an assignment was received. Wait for the actual recipient acknowledgement before attributing work to Claude; Codex-agent work is not Claude execution.
