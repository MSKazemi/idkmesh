import json
import tempfile
import unittest
from pathlib import Path

from tools.idkgraph_observatory import (
    build_graph,
    executable_cycle_witness,
    extract_documents,
    observe,
    parse_markdown,
    resolve_internal_links,
    validate_graph_shape,
)


class IDKGraphObservatoryTests(unittest.TestCase):
    def write(self, root: Path, rel: str, content: str) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_heading_identity_is_deterministic_and_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.write(
                root,
                "docs/a.md",
                "# Café & Graphs\n\n## Repeat!\n\n## Repeat!\n\n### Unicode Ω\n",
            )
            first = parse_markdown(path, root)
            second = parse_markdown(path, root)
            self.assertEqual(first, second)
            self.assertEqual([h.anchor for h in first.headings], ["café--graphs", "repeat", "repeat-1", "unicode-ω"])
            self.assertEqual(len({h.id for h in first.headings}), len(first.headings))

    def test_internal_link_diagnostics_distinguish_file_and_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(
                root,
                "README.md",
                "# Home\n\n[Doc](docs/doc.md#target)\n[Missing file](docs/nope.md)\n[Missing anchor](docs/doc.md#nope)\n",
            )
            self.write(root, "docs/doc.md", "# Doc\n\n## Target\n")
            docs = extract_documents(root)
            resolved, findings = resolve_internal_links(root, docs)
            self.assertTrue(any(link.anchor == "target" for link in resolved))
            categories = [finding.category for finding in findings]
            self.assertIn("missing_target_file", categories)
            self.assertIn("missing_target_anchor", categories)

    def test_valid_fixture_has_no_deterministic_link_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "README.md", "# Home\n\n[Guide](docs/guide.md#start)\n")
            self.write(root, "docs/guide.md", "# Guide\n\n## Start\n\n[Home](../README.md)\n")
            _, findings = resolve_internal_links(root, extract_documents(root))
            self.assertEqual([f for f in findings if f.severity == "error"], [])

    def test_deterministic_repository_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "README.md", "# Home\n\n[Decision](docs/decisions/ADR-0001-test.md)\n[Schema](schemas/example.json)\n")
            self.write(root, "docs/decisions/ADR-0001-test.md", "# ADR 0001: Test\n")
            self.write(root, "schemas/example.json", "{}\n")
            documents = extract_documents(root)
            links, findings = resolve_internal_links(root, documents)
            self.assertEqual([f for f in findings if f.severity == "error"], [])
            graph, mapping_findings = build_graph(root, documents, links)
            self.assertEqual(mapping_findings, [])
            self.assertEqual(validate_graph_shape(graph), [])
            types = [node["type"] for node in graph["nodes"]]
            self.assertIn("document", types)
            self.assertIn("decision", types)
            self.assertIn("artifact", types)
            relations = [edge["relation"] for edge in graph["hyperedges"]]
            self.assertIn("documents", relations)
            self.assertIn("mentions", relations)

    def test_executable_cycle_returns_stable_witness(self):
        graph = {
            "nodes": [
                {"id": "work_unit:C", "type": "work_unit", "title": "C"},
                {"id": "work_unit:A", "type": "work_unit", "title": "A"},
                {"id": "work_unit:B", "type": "work_unit", "title": "B"},
                {"id": "hypothesis:H1", "type": "hypothesis", "title": "H1"},
                {"id": "hypothesis:H2", "type": "hypothesis", "title": "H2"},
            ],
            "hyperedges": [
                {"id": "e3", "relation": "depends_on", "sources": ["work_unit:C"], "targets": ["work_unit:A"]},
                {"id": "e1", "relation": "depends_on", "sources": ["work_unit:A"], "targets": ["work_unit:B"]},
                {"id": "e2", "relation": "depends_on", "sources": ["work_unit:B"], "targets": ["work_unit:C"]},
                {"id": "knowledge-cycle", "relation": "contradicts", "sources": ["hypothesis:H1"], "targets": ["hypothesis:H2"]},
                {"id": "knowledge-cycle-2", "relation": "contradicts", "sources": ["hypothesis:H2"], "targets": ["hypothesis:H1"]},
            ],
        }
        first = executable_cycle_witness(graph)
        second = executable_cycle_witness(
            {"nodes": list(reversed(graph["nodes"])), "hyperedges": list(reversed(graph["hyperedges"]))}
        )
        self.assertEqual(first, ["work_unit:A", "work_unit:B", "work_unit:C", "work_unit:A"])
        self.assertEqual(first, second)

    def test_knowledge_cycle_does_not_fail_executable_projection(self):
        graph = {
            "nodes": [
                {"id": "hypothesis:A", "type": "hypothesis", "title": "A"},
                {"id": "hypothesis:B", "type": "hypothesis", "title": "B"},
            ],
            "hyperedges": [
                {"id": "x", "relation": "contradicts", "sources": ["hypothesis:A"], "targets": ["hypothesis:B"]},
                {"id": "y", "relation": "contradicts", "sources": ["hypothesis:B"], "targets": ["hypothesis:A"]},
            ],
        }
        self.assertIsNone(executable_cycle_witness(graph))

    def test_observe_is_replay_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "README.md", "# Home\n\n[Guide](docs/guide.md)\n")
            self.write(root, "docs/guide.md", "# Guide\n\n[Home](../README.md)\n")
            first_graph, first_findings, _ = observe(root)
            second_graph, second_findings, _ = observe(root)
            self.assertEqual(
                json.dumps(first_graph, sort_keys=True),
                json.dumps(second_graph, sort_keys=True),
            )
            self.assertEqual(first_findings, second_findings)

    def test_explicit_workunit_file_drives_cycle_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "README.md", "# Home\n")
            self.write(
                root,
                "work/a.workunit.json",
                json.dumps({"id": "A", "type": "work_unit", "title": "A", "depends_on": ["B"]}),
            )
            self.write(
                root,
                "work/b.workunit.json",
                json.dumps({"id": "B", "type": "work_unit", "title": "B", "depends_on": ["A"]}),
            )
            graph, findings, _ = observe(root)
            self.assertEqual(executable_cycle_witness(graph), ["work_unit:A", "work_unit:B", "work_unit:A"])
            self.assertTrue(any(f.category == "executable_dependency_cycle" for f in findings))


if __name__ == "__main__":
    unittest.main()
