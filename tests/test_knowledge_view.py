"""Offline graph export tests; no browser execution or external requests."""

import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from tools.knowledge import Bundle, Concept, load_bundle
from tools.knowledge_view import graph_data, html_view, markdown_view, overview_edges, source_href, svg_view


def example(title="First", resource="../../docs/research.md"):
    bundle = Bundle(version="0.2")
    bundle.concepts["platform/one"] = Concept("platform/one", {
        "type": "Test", "title": title, "description": title, "status": "draft",
        "sources": [{"id": "report", "resource": resource}],
        "opencast_evidence": ["PENDING: synthetic"]},
        "# First\n\nUntrusted <img src=x onerror=alert(1)> remains text. [Second](/platform/two.md).",
        ["/platform/two.md"])
    bundle.concepts["platform/two"] = Concept("platform/two", {"type": "Test", "title": "Second"}, "# Second", [])
    return bundle


class KnowledgeViewTests(unittest.TestCase):
    def test_script_termination_and_html_injection_are_data(self):
        title = '</script><script>alert("x")</script><img src="https://example.invalid">'
        data = graph_data(example(title))
        exported = html_view(data)
        self.assertNotIn(title, exported)
        self.assertNotIn("<img src=x", exported)
        raw = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', exported, re.S).group(1)
        self.assertNotIn("<", raw)
        self.assertEqual(json.loads(raw)["nodes"][0]["title"], title)
        self.assertNotIn("innerHTML", exported)
        markdown = markdown_view(data)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn('<img src="', markdown)
        svg = ET.fromstring(svg_view(data))
        self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}script'))
        self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}image'))

    def test_dangerous_sources_never_become_links(self):
        for resource in ["javascript:alert(1)", "data:text/html,test", "//evil.example/file.md", "https://evil.example/file.md",
                         "../../../secret.md", "../../.env.md", "../../firmware/secret.md", "../../docs/../.git/a.md",
                         "../../docs/x.md?redirect=evil", "../../docs/x.md#payload", "..\\..\\docs\\x.md",
                         "%6aavascript:alert(1)", "https://[bad"]:
            with self.subTest(resource=resource):
                self.assertIsNone(source_href("platform/one", resource))
                self.assertIsNone(graph_data(example(resource=resource))["nodes"][0]["sources"][0]["href"])

    def test_manual_repository_links_resolve_from_html_location(self):
        self.assertEqual(source_href("platform/one", "../../docs/research.md"), "../docs/research.md")
        self.assertEqual(source_href("platform/one", "../../AGENTS.md"), "../AGENTS.md")
        self.assertEqual(source_href("platform/one", "/platform/two.md"), "platform/two.md")

    def test_deterministic_exports_and_real_relationships(self):
        first = graph_data(example())
        second = graph_data(example())
        self.assertEqual(html_view(first), html_view(second))
        self.assertEqual(markdown_view(first), markdown_view(second))
        self.assertEqual(svg_view(first), svg_view(second))
        self.assertEqual(len(first["nodes"]), 2)
        self.assertEqual(len(first["edges"]), 1)
        self.assertEqual(overview_edges(first), first["edges"])
        self.assertIn('click n0 "../knowledge/platform/one.md"', markdown_view(first))

    def test_current_bundle_counts_are_not_invented_by_the_view(self):
        bundle = load_bundle(Path(__file__).resolve().parents[1] / "knowledge")
        data = graph_data(bundle)
        edges, unresolved = bundle.edges()
        self.assertFalse(unresolved)
        self.assertEqual(len(data["nodes"]), len(bundle.concepts))
        self.assertEqual(data["edges"], sorted(edges, key=lambda edge: (edge["from"], edge["to"], edge["kind"])))
        self.assertTrue(all(edge in edges for edge in overview_edges(data)))
        self.assertEqual(len(overview_edges(data)), len(bundle.concepts) - 1)

    def test_invalid_ids_and_unresolved_concepts_fail_export(self):
        bundle = example()
        bundle.concepts["platform/one"].links.append("/missing.md")
        with self.assertRaises(ValueError):
            graph_data(bundle)
        bundle = example()
        bundle.concepts["bad\" onclick=alert(1)"] = Concept("bad", {"type": "Test"}, "", [])
        with self.assertRaises(ValueError):
            graph_data(bundle)


if __name__ == "__main__":
    unittest.main()
