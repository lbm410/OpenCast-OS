"""Read the OpenCast local OKF profile; never fetch sources or execute content.

Frontmatter uses JSON objects, a deliberately limited YAML 1.2 subset.
This is not a general YAML or complete CommonMark consumer.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib.parse import unquote, urlsplit

MAX_FILES = 256
MAX_ENTRIES = 2048
MAX_DEPTH = 8
MAX_FILE_BYTES = 65536
MAX_TOTAL_BYTES = 8 * 1024**2
MAX_FRONTMATTER = 16384
MAX_LINKS = 256
RESERVED = {"index.md", "log.md"}


@dataclass
class Concept:
    id: str
    metadata: dict
    body: str
    links: list[str]

    def summary(self) -> dict:
        meta = self.metadata
        return {"id": self.id, "type": meta["type"],
                "title": meta.get("title", PurePosixPath(self.id).name),
                "description": meta.get("description", ""), "tags": meta.get("tags", []),
                "status": meta.get("status", "stable"),
                "declared_trust": declared_trust(meta)}


@dataclass
class Bundle:
    concepts: dict[str, Concept] = field(default_factory=dict)
    indexes: dict[str, str] = field(default_factory=dict)
    logs: dict[str, str] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    version: str | None = None

    def issue(self, severity: str, path: str, message: str) -> None:
        self.issues.append({"severity": severity, "path": path, "message": message})

    def edges(self) -> tuple[list[dict], list[dict]]:
        edges, unresolved = [], []
        seen_edges = set()
        for cid, node in sorted(self.concepts.items()):
            targets = [(link, "link") for link in node.links]
            targets += [(s["resource"], "source") for s in node.metadata.get("sources", [])
                        if isinstance(s, dict) and isinstance(s.get("resource"), str)]
            for target, kind in targets:
                resolved, reason = resolve_link(cid, target)
                if resolved in self.concepts:
                    edge = {"from": cid, "to": resolved, "kind": kind}
                    key = (cid, resolved, kind)
                    if key not in seen_edges:
                        edges.append(edge)
                        seen_edges.add(key)
                elif kind == "link" and reason != "external":
                    unresolved.append({"from": cid, "target": target,
                                       "reason": reason or "missing_or_reserved"})
        return edges, unresolved


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON frontmatter key")
        result[key] = value
    return result


def frontmatter(text: str, required: bool) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        if required:
            raise ValueError("Concept requires JSON-object YAML frontmatter")
        return {}, text
    closing = next((i for i, line in enumerate(lines[1:], 1)
                    if line.rstrip("\r\n") == "---"), None)
    if closing is None:
        raise ValueError("Unterminated frontmatter")
    raw = "".join(lines[1:closing])
    if len(raw.encode("utf-8")) > MAX_FRONTMATTER:
        raise ValueError("Frontmatter exceeds local profile limit")
    try:
        meta = json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Frontmatter must use the documented JSON-object subset") from error
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter must be an object")
    # JSON escapes can introduce lone UTF-16 surrogates despite valid UTF-8
    # source bytes. Check every key/value, including unknown nested extensions.
    try:
        json.dumps(meta, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Frontmatter contains invalid Unicode or excessive nesting") from error
    return meta, "".join(lines[closing + 1:])


def declared_trust(meta: dict) -> str:
    events = meta.get("verified", [])
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list) or not events:
        return "unverified"
    actors = [event.get("by") for event in events if isinstance(event, dict)]
    if any(isinstance(actor, str) and actor.startswith("human:") for actor in actors):
        return "human-reviewed (declared)"
    return "machine-confirmed (declared)" if any(actors) else "unverified"


def markdown_links(body: str) -> list[str]:
    """Read simple inline/reference links, ignoring images and code/comment text."""
    lines, fence = [], None
    for line in body.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    text = re.sub(r"<!--[\s\S]*?-->", "", "\n".join(lines))
    text = re.sub(r"`+[^`]*`+", "", text)
    references = {label.casefold(): target.strip("<>") for label, target in
                  re.findall(r"^\s{0,3}\[([^\]^]+)\]:\s*(<[^>]+>|\S+)", text, re.M)}
    text = re.sub(r"^\s{0,3}\[[^\]]+\]:.*$", "", text, flags=re.M)
    targets = [target.strip("<>") for target in re.findall(
        r'(?<!!)\[[^\]\n]+\]\(\s*(<[^>\n]+>|[^\s()]+)(?:\s+"[^"\n]*")?\s*\)', text)]
    for label, ref in re.findall(r"(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]", text):
        target = references.get((ref or label).casefold())
        if target:
            targets.append(target)
    targets = list(dict.fromkeys(targets))
    if len(targets) > MAX_LINKS:
        raise ValueError("Concept link count exceeds local profile limit")
    return targets


def resolve_link(source_id: str, target: str) -> tuple[str | None, str | None]:
    if len(target) > 4096 or "\\" in target or any(ord(c) < 32 for c in target):
        return None, "unsafe_path"
    try:
        parsed = urlsplit(target)
    except ValueError:
        return None, "unsafe_path"
    if parsed.scheme or parsed.netloc:
        return None, "external"
    path = unquote(parsed.path)
    if "\\" in path or any(ord(c) < 32 for c in path):
        return None, "unsafe_path"
    if not path:
        return source_id, None
    parts = [] if path.startswith("/") else list(PurePosixPath(source_id).parent.parts)
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None, "outside_bundle"
            parts.pop()
        elif part.startswith("."):
            return None, "hidden_path"
        else:
            parts.append(part)
    candidate = "/".join(parts)
    if not candidate.endswith(".md"):
        return None, "not_a_concept_path"
    return candidate[:-3], None


def validate_metadata(meta: dict) -> None:
    if not isinstance(meta.get("type"), str) or not meta["type"].strip():
        raise ValueError("Concept type must be a nonempty string")
    for key in ("title", "description", "status", "resource"):
        if key in meta and not isinstance(meta[key], str):
            raise ValueError(f"{key} must be a string in this profile")
    if "tags" in meta and (not isinstance(meta["tags"], list)
                           or not all(isinstance(tag, str) for tag in meta["tags"])):
        raise ValueError("tags must be a list of strings")
    if "sources" in meta:
        if not isinstance(meta["sources"], list) or len(meta["sources"]) > MAX_LINKS or any(
            not isinstance(source, dict) or not isinstance(source.get("resource"), str)
            or not source["resource"] for source in meta["sources"]
        ):
            raise ValueError("sources must be mappings with nonempty resource strings")


def load_bundle(root: Path) -> Bundle:
    bundle = Bundle()
    entries = files = total = 0
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def walk(fd: int, parent: str, depth: int) -> None:
        nonlocal entries, files, total
        if depth > MAX_DEPTH:
            raise ValueError("Bundle directory depth limit exceeded")
        with os.scandir(fd) as iterator:
            names = []
            for entry in iterator:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError("Bundle entry count limit exceeded")
                names.append(entry.name)
        for name in sorted(names):
            path = f"{parent}/{name}" if parent else name
            if name.startswith("."):
                continue
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                bundle.issue("error", path, "Symlink is forbidden; not read")
            elif stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    walk(child, path, depth + 1)
                finally:
                    os.close(child)
            elif name.endswith(".md"):
                files += 1
                if files > MAX_FILES:
                    raise ValueError("Bundle Markdown file limit exceeded")
                try:
                    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                    try:
                        stream = os.fdopen(file_fd, "rb")
                    except BaseException:
                        os.close(file_fd)
                        raise
                    with stream:
                        before = os.fstat(stream.fileno())
                        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                            raise ValueError("Markdown input is not a bounded regular file")
                        total += before.st_size
                        if total > MAX_TOTAL_BYTES:
                            raise ValueError("Bundle byte limit exceeded")
                        raw = stream.read(before.st_size + 1)
                        after = os.fstat(stream.fileno())
                        if len(raw) != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
                            raise ValueError("Markdown changed during read")
                    text = raw.decode("utf-8")
                    meta, body = frontmatter(text, name not in RESERVED)
                    had_frontmatter = bool(text.splitlines()) and text.splitlines()[0] == "---"
                    if name == "index.md":
                        if had_frontmatter and (parent or set(meta) != {"okf_version"}):
                            raise ValueError("Only root index may declare okf_version frontmatter")
                        if meta:
                            bundle.version = str(meta["okf_version"])
                        bundle.indexes[path] = body
                    elif name == "log.md":
                        if had_frontmatter:
                            raise ValueError("Log files must not have frontmatter")
                        bundle.logs[path] = body
                    else:
                        validate_metadata(meta)
                        bundle.concepts[path[:-3]] = Concept(path[:-3], meta, body, markdown_links(body))
                except (OSError, ValueError, UnicodeError) as error:
                    bundle.issue("error", path, str(error))
    try:
        walk(root_fd, "", 0)
    finally:
        os.close(root_fd)
    if bundle.version not in (None, "0.2"):
        bundle.issue("warning", "index.md", "Unknown OKF version; best-effort profile reading")
    return bundle


def overview(bundle: Bundle) -> dict:
    return {"okf_version": bundle.version, "concepts": [n.summary() for _, n in sorted(bundle.concepts.items())],
            "indexes": sorted(bundle.indexes), "logs": sorted(bundle.logs)}


def search(bundle: Bundle, query: str, limit: int = 20) -> list[dict]:
    if not 1 <= limit <= MAX_FILES:
        raise ValueError("Search limit must be between 1 and 256")
    terms = query.casefold().split()
    results = []
    for node in bundle.concepts.values():
        summary = node.summary()
        haystack = " ".join([summary["title"], summary["description"], *summary["tags"]]).casefold()
        if terms and all(term in haystack for term in terms):
            score = sum(summary["title"].casefold().count(term) * 3 + haystack.count(term) for term in terms)
            results.append((score, node.id, summary))
    return [row[2] for row in sorted(results, key=lambda row: (-row[0], row[1]))[:limit]]


def counted_json(value: dict) -> bytes:
    """Return complete UTF-8 JSON+newline with its exact own serialized byte count."""
    value["utf8_bytes"] = 0
    value["approximate_tokens"] = 0
    for _ in range(16):
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        size = len(encoded)
        approximate = math.ceil(size / 4)
        if value["utf8_bytes"] == size and value["approximate_tokens"] == approximate:
            return encoded
        value["utf8_bytes"], value["approximate_tokens"] = size, approximate
    raise ValueError("Output size accounting did not converge")


def context(bundle: Bundle, seeds: list[str], depth: int = 1, max_nodes: int = 8,
            byte_budget: int = 12000) -> bytes:
    if not seeds or not 0 <= depth <= 8 or not 1 <= max_nodes <= MAX_FILES or not 512 <= byte_budget <= 1024**2:
        raise ValueError("Context needs seeds, depth 0..8, nodes 1..256 and bytes 512..1048576")
    for seed in seeds:
        if seed not in bundle.concepts:
            raise ValueError(f"Unknown seed concept: {seed}")
    edges, unresolved = bundle.edges()
    adjacent = {}
    for edge in edges:
        adjacent.setdefault(edge["from"], set()).add(edge["to"])
    queue = deque((seed, 0) for seed in dict.fromkeys(seeds))
    visited, candidates = set(), []
    while queue:
        cid, distance = queue.popleft()
        if cid in visited:
            continue
        visited.add(cid)
        candidates.append(cid)
        if distance < depth:
            queue.extend((target, distance + 1) for target in sorted(adjacent.get(cid, [])))
    result = {"nodes": [], "omitted_nodes": len(candidates), "truncated": False,
              "unresolved_link_count": len(unresolved),
              "token_estimate": "ceil(UTF-8 bytes/4); approximate, not tokenizer measurement"}
    for cid in candidates[:max_nodes]:
        node = bundle.concepts[cid]
        row = {"id": cid, "metadata": node.metadata, "body": node.body, "body_truncated": False}
        result["nodes"].append(row)
        result["omitted_nodes"] = len(candidates) - len(result["nodes"])
        result["truncated"] = result["omitted_nodes"] > 0
        if len(counted_json(result)) <= byte_budget:
            continue
        row["body"] = ""
        row["body_truncated"] = True
        result["truncated"] = True
        if len(counted_json(result)) > byte_budget:
            result["nodes"].pop()
            result["omitted_nodes"] += 1
            continue
        low, high = 0, len(node.body)
        while low < high:
            middle = (low + high + 1) // 2
            row["body"] = node.body[:middle]
            if len(counted_json(result)) <= byte_budget:
                low = middle
            else:
                high = middle - 1
        row["body"] = node.body[:low]
        break
    result["truncated"] = result["omitted_nodes"] > 0 or any(n["body_truncated"] for n in result["nodes"])
    encoded = counted_json(result)
    if len(encoded) > byte_budget:
        raise ValueError("Context envelope exceeds byte budget")
    return encoded


def mermaid(bundle: Bundle) -> str:
    edges, unresolved = bundle.edges()
    ids = {cid: f"n{index}" for index, cid in enumerate(sorted(bundle.concepts))}
    lines = ["flowchart LR"]
    for cid, identifier in ids.items():
        # Labels contain IDs only and allow no Mermaid directives or delimiters.
        safe = re.sub(r"[^A-Za-z0-9 _./-]", "_", cid)
        lines.append(f'  {identifier}["{safe}"]')
    for edge in edges:
        lines.append(f'  {ids[edge["from"]]} --> {ids[edge["to"]]}')
    lines.append(f"  %% Unresolved links: {len(unresolved)}; inspect validate for details.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("knowledge"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("overview")
    finder = commands.add_parser("search")
    finder.add_argument("query")
    finder.add_argument("--limit", type=int, default=20)
    reader = commands.add_parser("context")
    reader.add_argument("seeds", nargs="+")
    reader.add_argument("--depth", type=int, default=1)
    reader.add_argument("--max-nodes", type=int, default=8)
    reader.add_argument("--byte-budget", type=int, default=12000)
    graph = commands.add_parser("graph")
    graph.add_argument("--format", choices=("mermaid", "json"), default="mermaid")
    args = parser.parse_args()
    try:
        bundle = load_bundle(args.bundle)
        edges, unresolved = bundle.edges()
        invalid = any(issue["severity"] == "error" for issue in bundle.issues)
        if args.command == "validate":
            output = {"valid_local_profile": not invalid, "concepts": len(bundle.concepts),
                      "issues": bundle.issues, "unresolved_links": unresolved,
                      "scope": "Local JSON-frontmatter profile, not universal YAML validation"}
        elif invalid:
            raise ValueError("Bundle contains profile errors; run validate for details")
        elif args.command == "overview":
            output = overview(bundle)
        elif args.command == "search":
            output = search(bundle, args.query, args.limit)
        elif args.command == "context":
            sys.stdout.buffer.write(context(bundle, args.seeds, args.depth, args.max_nodes, args.byte_budget))
            return 0
        elif args.format == "mermaid":
            sys.stdout.write(mermaid(bundle))
            return 0
        else:
            output = {"nodes": list(sorted(bundle.concepts)), "edges": edges, "unresolved_links": unresolved}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2 if invalid else 0
    except (OSError, ValueError, RecursionError) as error:
        print(json.dumps({"status": "error", "message": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
