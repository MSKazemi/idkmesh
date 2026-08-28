import tempfile
import unittest
from pathlib import Path

from tools.idkgraph_health_checks import check_residual_health
from tools.idkgraph_link_check import check_links
from tools.idkgraph_repository_mapping import build_repository_graph


class ResidualHealthChecksTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _fixture(self, root: Path) -> None:
        self._write(
            root,
            "docs/README.md",
            "# Docs Index\n\n- [Architecture](architecture/linked.md)\n- [Navigated note](notes/navigated.md)\n",
        )
        self._write(root, "docs/architecture/linked.md", "# Linked Architecture\n")
        self._write(root, "docs/notes/navigated.md", "# Navigated Note\n")
        self._write(root, "docs/notes/orphan.md", "# Orphan Candidate\n")
        self._write(
            root,
            "docs/decisions/ADR-0001-linked.md",
            "# ADR-0001: Linked\n\n- **Status:** Accepted\n\n## Implementation references\n\n- `docs/architecture/linked.md`\n",
        )
        self._write(
            root,
            "docs/decisions/ADR-0002-unlinked.md",
            "# ADR-0002: Unlinked\n\nStatus: Accepted\n",
        )
        self._write(
            root,
            "docs/decisions/ADR-0003-proposed.md",
            "# ADR-0003: Proposed\n\nStatus: Proposed\n",
        )

    def _artifact_fixture(self, root: Path) -> None:
        """Reproduces the motivating case from the #152 cohort triage.

        A calibration document carrying no inbound Markdown link, owned by the CI
        workflow that runs it. Before the refinement this was indistinguishable
        from an abandoned document.
        """
        self._write(root, "docs/README.md", "# Docs Index\n")
        self._write(root, "docs/research/CALIBRATION.md", "# Calibration\n")
        self._write(root, "docs/research/ABANDONED.md", "# Abandoned\n")
        self._write(
            root,
            ".github/workflows/calibration.yml",
            'name: Calibration\non:\n  push:\n    paths:\n'
            '      - "docs/research/CALIBRATION.md"\n',
        )

    def test_workflow_owned_document_is_a_notice_not_an_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._artifact_fixture(root)
            result = check_residual_health(
                root, build_repository_graph(root), check_links(root)
            )
            by_category = {
                item["category"]: item
                for item in result["findings"]
                if item["source_path"] == "docs/research/CALIBRATION.md"
            }

            self.assertIn("document_referenced_only_by_non_markdown_artifact", by_category)
            self.assertNotIn("orphan_document_candidate", by_category)

            finding = by_category["document_referenced_only_by_non_markdown_artifact"]
            self.assertEqual(finding["severity"], "notice")
            self.assertEqual(
                finding["evidence"]["referencing_artifacts"],
                [".github/workflows/calibration.yml"],
            )

    def test_document_referenced_by_nothing_remains_an_orphan_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._artifact_fixture(root)
            result = check_residual_health(
                root, build_repository_graph(root), check_links(root)
            )
            orphans = {
                item["source_path"]
                for item in result["findings"]
                if item["category"] == "orphan_document_candidate"
            }

            self.assertIn("docs/research/ABANDONED.md", orphans)
            self.assertNotIn("docs/research/CALIBRATION.md", orphans)

    def test_document_with_an_inbound_markdown_link_produces_no_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._artifact_fixture(root)
            # Same document, now also reachable by a human reader.
            self._write(
                root,
                "docs/README.md",
                "# Docs Index\n\n- [Calibration](research/CALIBRATION.md)\n",
            )
            result = check_residual_health(
                root, build_repository_graph(root), check_links(root)
            )

            self.assertEqual(
                [
                    item
                    for item in result["findings"]
                    if item["source_path"] == "docs/research/CALIBRATION.md"
                ],
                [],
            )

    def test_only_unreferenced_non_index_document_is_orphan_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            graph = build_repository_graph(root)
            links = check_links(root)

            result = check_residual_health(root, graph, links)
            orphan_paths = {
                item["source_path"]
                for item in result["findings"]
                if item["category"] == "orphan_document_candidate"
            }

            self.assertEqual(orphan_paths, {"docs/notes/orphan.md"})
            self.assertEqual(result["summary"]["orphan_document_candidates"], 1)
            self.assertNotIn("docs/README.md", orphan_paths)

    def test_accepted_decision_requires_explicit_document_implements_relation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            graph = build_repository_graph(root)
            links = check_links(root)

            result = check_residual_health(root, graph, links)
            decision_paths = {
                item["source_path"]
                for item in result["findings"]
                if item["category"] == "accepted_decision_without_document_link"
            }

            self.assertEqual(decision_paths, {"docs/decisions/ADR-0002-unlinked.md"})
            self.assertEqual(result["summary"]["accepted_decisions_without_document_link"], 1)
            self.assertNotIn("docs/decisions/ADR-0001-linked.md", decision_paths)
            self.assertNotIn("docs/decisions/ADR-0003-proposed.md", decision_paths)

    def test_all_residual_findings_are_warning_only_and_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            graph = build_repository_graph(root)
            links = check_links(root)

            result = check_residual_health(root, graph, links)

            self.assertEqual(len(result["findings"]), 2)
            for finding in result["findings"]:
                self.assertEqual(finding["severity"], "warning")
                self.assertTrue(finding["source_id"])
                self.assertEqual(finding["evidence"]["producer"], "P0-health")
                self.assertTrue(finding["evidence"]["rule"])
            self.assertFalse(result["authority"]["repository_write"])
            self.assertFalse(result["authority"]["semantic_inference"])


if __name__ == "__main__":
    unittest.main()
