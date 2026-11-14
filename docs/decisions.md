# Architecture decisions

## D001 — OpenCast OS is the destination (2026-11-14)

The intended result replaces startup UX, launcher and menus where technically feasible. A NetCast application is an intermediate experiment. Investigate, in order of increasing depth: shell over existing system, distribution using the existing kernel, alternative Linux, complete custom firmware. None of these integrations is proven yet.

## D002 — Evidence before persistence

Root access is not proof of system replaceability. Map display, input, tuner, audio, power and watchdog dependencies before replacing processes. An independently verified recovery path is required before persistent changes. A normal vendor update is not a recovery guarantee.

## D003 — Small, bounded host tools

Use standard-library Python for explicit SSDP discovery and descriptor reads from a confirmed target. No address sweeps, environment proxies, cross-host redirects, pairing or command dispatch. Firmware inspection is separate from networking and never runs extracted code. One deliberately selected archive member may be copied after metadata validation; never extractall.

## D004 — Preserve upstream and the owner's license

The owner created `git@github.com:lbm410/OpenCast-OS.git` with README and GPLv3 LICENSE. Local main is based on upstream commit `276d54d3a84e3d258a87f8ab5369ed1cc04ad896`; original history and LICENSE are preserved. New commits use only the required owner identity. No push without explicit instruction.

## D005 — First execution probe is a web capability experiment

The browser path offers a low-risk first execution without depending on legacy LG DRM packaging. It is not the replacement architecture. Use conservative JavaScript, system fonts, explicit focus and no external assets. Capture actual UA, viewport, received remote keys and coarse JavaScript timings; never equate them with GPU acceleration or hardware latency.

## D006 — English engineering record

All repository knowledge and technical material is written in English, including agent instructions, comments and CLI messages. Conversation with the owner remains Spanish. Original third-party material and recorded evidence are preserved verbatim, not rewritten to change the historical observation.

## D007 — Preserve essential vendor services while researching shell replacement

The decoded RELEASE executable has vendor AV dependencies and native TV-related definitions. A graphics/input wrapper uses a service-message path. Investigate coexistence and explicit capability adapters before proposing process replacement. Symbol names or paired partitions do not prove safe separation or recovery. See native-interfaces.md and architecture.md.

## D008 — OKF concepts are a bounded retrieval layer

At the owner's request, adopt Open Knowledge Format0.2 in knowledge/ with concise linked concepts and source references. Keep detailed experiment reports as evidence. Use JSON-object YAML frontmatter for a dependency-free local profile; do not claim a universal YAML reader. Return only task-relevant context with exact byte limits and explicit truncation. Token counts are estimates until measured with a specific tokenizer. Do not fabricate verification metadata or duplicate raw artifacts into the graph.

## D009 — Responsiveness governs visual effects

The owner's landscape/glass direction starts with a static local image and inexpensive translucent panels. Actual-TV input latency, startup and stability decide whether any movement or additional compositing is acceptable. Desktop smoothness and compressed asset size are insufficient evidence. See performance.md.

## D010 — Granular local history, publication separately authorized

The owner explicitly requested local commits by coherent functionality/investigation. Keep tests and relevant documentation with each block, fetch/check before every commit, preserve exclusive owner attribution, and leave unfinished work out. This instruction does not authorize push or deployment.
