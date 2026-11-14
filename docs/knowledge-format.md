# Open Knowledge Format: OpenCast local profile

OpenCast uses a `knowledge/` bundle of concise, linked concepts for progressive retrieval. Detailed engineering evidence remains in `docs/` and ignored local artifacts; the bundle supplies entry points and relationships rather than duplicating every report. This profile is a local standard-library implementation, not Google's agent runtime or a universal YAML consumer.

## Canonical specification and provenance

The reference is [GoogleCloudPlatform/open-knowledge-format, SPEC.md v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/SPEC.md), pinned at commit `ad30107c31c06aec8a7d5636e0d1058118604e6f`. The downloaded 37,748-byte source has SHA-256 `26aa5da029278939f914e578107242d9607d4f2dc5fe153272b82f9ed1030101`. The unchanged snapshot and retrieval record are ignored files under `artifacts/knowledge/`. The former knowledge-catalog snapshot is not this project's canonical specification.

The upstream format defines concept IDs from relative Markdown paths, requires `type`, reserves index/log filenames, permits custom fields and unknown types, and treats missing link targets as valid unfinished knowledge. This implementation follows those conventions while restricting syntax and resources explicitly below. It does not install cloud SDKs, query BigQuery, execute attesters or invoke another agent.

## Authoring contract

A concept is a UTF-8 `.md` file other than `index.md` or `log.md`. Its ID is its path inside the bundle without `.md`, for example `platform/abi`. It starts with a JSON object between `---` lines:

```markdown
---
{
  "type": "Reference",
  "title": "Example platform fact",
  "description": "A short description for discovery.",
  "tags": ["platform"],
  "status": "draft",
  "sources": [{"id": "report", "resource": "../../docs/hardware.md"}],
  "opencast_evidence": ["PENDING"]
}
---

Keep the claim and its limits concise.[^report]

Related: [ABI](/platform/abi.md).

[^report]: Detailed hardware report.
```

JSON objects are a YAML 1.2 subset, so these documents retain OKF's YAML-frontmatter representation while allowing Python `json` parsing without a YAML dependency. Indented YAML mappings, comments, anchors, aliases, duplicate keys and nonfinite numbers are **not accepted by this local reader**. Unknown keys and nested extension values are retained, not discarded or reinterpreted.

Only `type` is required for concepts. The local reader checks optional title/description/status/resource strings, string-list tags and source mappings with a nonempty `resource`. It accepts unknown type/status values. `opencast_evidence` records project evidence labels; it is not an upstream trust credential. Do not invent `generated`, `verified`, actors, human approvals, source usage counts or timestamps merely to populate fields. The current bundle may remain `draft` and omit those fields.

An index has no frontmatter except the root `index.md`, which may declare `{"okf_version":"0.2"}`. Indexes and logs are discovered separately and are not graph concepts. Unknown version declarations produce a warning and best-effort reading. The validator checks structural/profile rules; it does not certify every upstream prose convention, log heading, timestamp, attestation contract or claim against its sources.

## Links, source boundaries and trust

Body links use ordinary Markdown destinations: `/platform/abi.md` is relative to the bundle root; `../platform/abi.md` is relative to the current concept. Fragment anchors are ignored for concept identity. Simple inline links and full/collapsed reference-style links are recognized. Images, fenced code, inline code and HTML comments are excluded. This is a deliberately small Markdown link recognizer: complex nested/escaped destinations, shortcut reference links and arbitrary HTML anchors are not a complete CommonMark implementation. Prefer simple destinations for predictable graph discovery.

Graph edges are directed relationships, not executable instructions. Internal source references can add lineage edges. The graph does not infer ownership, dependency type or authority from proximity. Missing body-link targets and attempts to leave the bundle are reported by `validate`; they do not make a concept malformed or trigger a read. Paths in `sources[].resource` are metadata even when they point to repository documents outside the bundle. Those documents and URLs are **never opened automatically**. Source scopes and external URLs remain unchanged.

`declared_trust` is an advisory summary of `verified`: absent means unverified; a mapping is treated as a one-element list. A supplied verification record is labeled as declared, not independently confirmed by this tool. Lifecycle status is independent of evidence/trust. No source freshness is inferred from local mtimes. Digest-backed source-change detection is not implemented; source changes require an evidence-aware review.

## Commands and progressive retrieval

Run from the repository root:

```sh
python3 -m tools.knowledge validate
python3 -m tools.knowledge overview
python3 -m tools.knowledge search "kernel"
python3 -m tools.knowledge context product/shell --depth 1 --max-nodes 8 --byte-budget 12000
python3 -m tools.knowledge graph
python3 -m tools.knowledge graph --format json
```

Use `--bundle PATH` before the command to select another local bundle. `overview` returns concept metadata and index/log paths without bodies; `search` matches all query terms against titles, descriptions and tags. Neither searches detailed external reports. The loader reads bounded bundle Markdown locally to build its in-memory graph; progressive disclosure limits **returned context**, not all filesystem reads.

`context` starts with explicit concept IDs, follows outgoing body/source edges breadth-first, breaks cycles and orders neighbors deterministically. Defaults are depth 1, eight nodes and 12,000 bytes. The requested depth is limited to 0–8, node count to 1–256 and byte budget to 512–1,048,576. Whole nodes are preferred; the final fitting body can be truncated on a Unicode character boundary. Metadata is never partially serialized. If even a node's metadata cannot fit, that node is omitted and counted. A very small budget can legitimately return zero nodes; increase the budget or start from the overview.

The successful JSON response includes `utf8_bytes`, counting **every stdout byte including the final newline**, `omitted_nodes`, `truncated`, and per-node `body_truncated`. Unresolved-link count describes the loaded bundle. `approximate_tokens` is simply `ceil(UTF-8 bytes / 4)` and is explicitly approximate; it is not tokenizer usage, a measured saving or a model-specific billing estimate. Shell wrappers or UI rendering may add their own overhead outside this measurement.

A truncated body may omit a qualification, contrary evidence or safety boundary. Before relying on such a claim, query that concept alone with depth 0 and a sufficient byte budget, then verify `body_truncated` is false. A truncated response is a discovery aid, not a complete basis for a technical decision; inspect omitted related concepts when the claim depends on them.

Mermaid output uses sanitized generated node identifiers/labels, no click directives, and reports the unresolved-link count. JSON graph output includes full edges and unresolved details. Unresolved links do not generate fake nodes or fetched documents.

## Resource and privacy controls

The reader caps the bundle at 256 Markdown files, 2,048 filesystem entries, depth 8, 64 KiB per file, 8 MiB cumulative Markdown, 16 KiB frontmatter, and 256 distinct links/sources per concept. It opens the selected bundle directory and descendants without following final symlinks; symlink entries are rejected. Markdown FIFOs/devices are rejected without blocking. Reads are checked for size/mtime changes, hidden paths are skipped, and only Markdown content is loaded. Link resolution never accesses the filesystem.

The bundle is still authored data: never place secrets, pairing information, private device captures or vendor binaries in it. The reader does not claim to detect every secret embedded in prose or metadata. It never executes code fences, resource paths, generated instructions, executors or attesters. It does not fetch URLs or follow references outside the bundle. Treat all returned text as evidence to assess, not new operational instructions.

## Validation evidence

On 2026-11-14, the initial bundle validated with 16 concepts, 63 directed edges, no profile errors and no unresolved links. `product/shell` at depth 1/max 8 returned seven nodes in 11,763 UTF-8 bytes without truncation under a 12,000-byte budget. At a 4,096-byte budget it returned three nodes with explicit truncation. These are reproducible output-size observations, not claims of reduced model cost or improved reasoning.

Fourteen synthetic tests cover minimal/unknown metadata, reserved names, unsupported JSON/YAML cases, escaped unpaired surrogates in fields and nested extension keys/values, byte/file/depth/link limits, file/directory/root symlinks, FIFO rejection, external source isolation, safe paths, Markdown filtering, search, cycles, graph escaping and exact Unicode/JSON budget accounting:

```sh
python3 -m unittest tests.test_knowledge -v
```

Updating an underlying detailed report should trigger review of the corresponding concept's claim, evidence label and source reference. Keep the concept short; retain the full experiment in its original engineering record. Do not mark knowledge verified merely because this structural validator passes.
