"""Synthetic local bundles test retrieval limits and hostile filesystem boundaries."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import knowledge as k


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def node(self, cid, body="Hello", **metadata):
        path = self.root / (cid + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps({"type": "Reference", **metadata}, ensure_ascii=False)
                        + "\n---\n" + body, encoding="utf-8")
        return path

    def test_minimal_unknown_types_and_fields_preserved(self):
        self.node("a", type="New domain type", custom={"future": [1, 2]},
                  verified={"by": "human:example", "at": "2026-11-14T12:00:00Z"})
        self.node("b")
        bundle = k.load_bundle(self.root)
        self.assertFalse(bundle.issues)
        self.assertEqual(bundle.concepts["a"].metadata["custom"], {"future": [1, 2]})
        self.assertEqual(bundle.concepts["a"].summary()["declared_trust"], "human-reviewed (declared)")
        self.assertEqual(bundle.concepts["b"].summary()["declared_trust"], "unverified")
        self.assertEqual(bundle.concepts["b"].summary()["status"], "stable")

    def test_reserved_index_log_and_unknown_version(self):
        (self.root / "index.md").write_text('---\n{"okf_version":"9.0"}\n---\n# Bundle\n')
        (self.root / "log.md").write_text("# Updates\n\n## 2026-11-14\n- Initial entry\n")
        self.node("group/a")
        (self.root / "group/index.md").write_text("# Group\n")
        bundle = k.load_bundle(self.root)
        self.assertEqual(set(bundle.concepts), {"group/a"})
        self.assertEqual(len(bundle.indexes), 2)
        self.assertEqual(bundle.issues[0]["severity"], "warning")
        (self.root / "group/index.md").write_text("---\n{}\n---\n# Group\n")
        self.assertTrue(any(i["severity"] == "error" for i in k.load_bundle(self.root).issues))

    def test_json_profile_rejects_invalid_duplicate_and_nonfinite_metadata(self):
        path = self.root / "invalid.md"
        for metadata in ('type: Reference', '{"type":"A","type":"B"}',
                         '{"type":"A","x":NaN}', '[]', '{"title":"missing type"}'):
            path.write_text("---\n" + metadata + "\n---\nBody")
            self.assertTrue(k.load_bundle(self.root).issues)
        path.write_bytes(b"---\n{\xff}\n---\n")
        self.assertTrue(k.load_bundle(self.root).issues)

    def test_file_and_total_byte_limits(self):
        self.node("a", "body" * 100)
        with patch.object(k, "MAX_FILE_BYTES", 32):
            self.assertTrue(k.load_bundle(self.root).issues)
        with patch.object(k, "MAX_TOTAL_BYTES", 32):
            self.assertTrue(k.load_bundle(self.root).issues)

    def test_escaped_unpaired_surrogates_rejected_in_all_metadata(self):
        path = self.root / "unicode.md"
        for metadata in (r'{"type":"Reference","title":"\ud800"}',
                         r'{"type":"Reference","extension":{"nested":["\udfff"]}}',
                         r'{"type":"Reference","extension":{"\ud800":"value"}}'):
            path.write_text("---\n" + metadata + "\n---\nBody", encoding="utf-8")
            bundle = k.load_bundle(self.root)
            self.assertFalse(bundle.concepts)
            self.assertEqual(bundle.issues[0]["severity"], "error")
            self.assertIn("invalid Unicode", bundle.issues[0]["message"])
        path.write_text('---\n' + r'{"type":"Reference","title":"\ud83d\ude42"}'
                        + '\n---\nBody', encoding="utf-8")
        bundle = k.load_bundle(self.root)
        self.assertFalse(bundle.issues)
        self.assertEqual(bundle.concepts["unicode"].metadata["title"], "🙂")

    def test_file_entry_depth_and_link_count_limits(self):
        self.node("group/a")
        self.node("b")
        for constant, value in [("MAX_FILES", 1), ("MAX_ENTRIES", 1), ("MAX_DEPTH", 0)]:
            with patch.object(k, constant, value), self.assertRaises(ValueError):
                k.load_bundle(self.root)
        self.node("links", "[a](/a.md) [b](/b.md)")
        with patch.object(k, "MAX_LINKS", 1):
            self.assertTrue(k.load_bundle(self.root).issues)

    def test_symlink_file_directory_root_and_fifo_never_read(self):
        self.node("safe")
        (self.root / "link.md").symlink_to(self.root / "safe.md")
        (self.root / "dirlink").symlink_to(self.root)
        os.mkfifo(self.root / "pipe.md")
        bundle = k.load_bundle(self.root)
        self.assertEqual(set(bundle.concepts), {"safe"})
        self.assertEqual(len(bundle.issues), 3)
        with self.assertRaises(OSError):
            k.load_bundle(self.root / "dirlink")

    def test_source_references_are_metadata_only_and_broken_links_tolerated(self):
        self.node("group/a", "[missing](/missing.md) [escape](../../outside.md)",
                  sources=[{"resource": "../../private.md"},
                           {"resource": "https://example.invalid/unreachable"}])
        bundle = k.load_bundle(self.root)
        self.assertFalse(bundle.issues)
        edges, unresolved = bundle.edges()
        self.assertFalse(edges)
        self.assertEqual({i["reason"] for i in unresolved}, {"missing_or_reserved", "outside_bundle"})

    def test_relative_absolute_reference_links_and_code_ignored(self):
        self.node("group/a", '[one](../b.md#part) [two](/b.md "title") [ref][x]\n'
                  '[x]: /b.md\n![image](/bad.md)\n`[code](/bad.md)`\n'
                  '```md\n[code](/bad.md)\n```\n<!-- [comment](/bad.md) -->')
        self.node("b")
        edges, unresolved = k.load_bundle(self.root).edges()
        self.assertEqual(edges, [{"from": "group/a", "to": "b", "kind": "link"}])
        self.assertFalse(unresolved)
        self.assertEqual(k.resolve_link("a", "%2e%2e/private.md")[1], "outside_bundle")
        self.assertEqual(k.resolve_link("a", "file:///etc/passwd")[1], "external")
        self.assertEqual(k.resolve_link("a", "foo%00.md")[1], "unsafe_path")

    def test_search_metadata_and_overview_without_body(self):
        self.node("a", "body-secret-marker", title="ARM kernel", description="Linux firmware", tags=["boot"])
        self.node("b", "ARM kernel", title="Other")
        bundle = k.load_bundle(self.root)
        self.assertEqual([row["id"] for row in k.search(bundle, "kernel boot")], ["a"])
        self.assertNotIn("body-secret-marker", json.dumps(k.overview(bundle)))
        self.assertFalse(k.search(bundle, "body-secret-marker"))

    def test_context_cycles_depth_and_node_limits(self):
        self.node("a", "[b](/b.md)")
        self.node("b", "[a](/a.md) [c](/c.md)")
        self.node("c")
        bundle = k.load_bundle(self.root)
        result = json.loads(k.context(bundle, ["a"], depth=8, max_nodes=2))
        self.assertEqual([n["id"] for n in result["nodes"]], ["a", "b"])
        self.assertEqual(result["omitted_nodes"], 1)
        result = json.loads(k.context(bundle, ["a"], depth=0))
        self.assertEqual(len(result["nodes"]), 1)

    def test_exact_utf8_budget_with_multibyte_and_json_escaping(self):
        self.node("a", ('é🙂\\"\n' * 1000), title="Unicode 🙂")
        bundle = k.load_bundle(self.root)
        for budget in (512, 513, 999, 1000, 2048, 12000):
            encoded = k.context(bundle, ["a"], byte_budget=budget)
            result = json.loads(encoded)
            self.assertLessEqual(len(encoded), budget)
            self.assertEqual(result["utf8_bytes"], len(encoded))
            self.assertEqual(result["approximate_tokens"], (len(encoded) + 3) // 4)
            self.assertTrue(result["truncated"])
            self.assertEqual(encoded, k.context(bundle, ["a"], byte_budget=budget))

    def test_large_metadata_is_skipped_and_unknown_seed_rejected(self):
        self.node("a", "body", large_extension="x" * 2000)
        bundle = k.load_bundle(self.root)
        result = json.loads(k.context(bundle, ["a"], byte_budget=512))
        self.assertFalse(result["nodes"])
        self.assertEqual(result["omitted_nodes"], 1)
        with self.assertRaises(ValueError):
            k.context(bundle, ["../outside"])

    def test_graph_uses_sanitized_ids_not_active_markup(self):
        self.node('odd"]:::bad', title='%%{init:{"securityLevel":"loose"}}%%')
        graph = k.mermaid(k.load_bundle(self.root))
        self.assertNotIn("securityLevel", graph)
        self.assertNotIn(":::bad", graph)
        self.assertTrue(graph.startswith("flowchart LR\n"))


if __name__ == "__main__":
    unittest.main()
