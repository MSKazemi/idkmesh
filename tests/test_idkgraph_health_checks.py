import subprocess
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



class UnexercisedExecutableTests(unittest.TestCase):
    """The check only speaks when the repository can answer the question.

    Every fixture here is a real git work tree, because the tracked-file set is
    what makes the answer reproducible across clones.
    """

    def _repository(self, root: Path, files: dict[str, str]) -> None:
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)

    def _executable_findings(self, root: Path) -> list[str]:
        graph = build_repository_graph(root)
        links = check_links(root)
        result = check_residual_health(root, graph, links)
        return sorted(
            finding["source_path"]
            for finding in result["findings"]
            if finding["category"] == "executable_without_exercise_or_recorded_output"
        )

    def test_only_the_executable_with_neither_exercise_nor_output_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(
                root,
                {
                    "tools/wired.py": "print('wired')\n",
                    "tools/recorded.py": "print('recorded')\n",
                    "tools/dormant.py": "print('dormant')\n",
                    "scripts/tested.py": "print('tested')\n",
                    ".github/workflows/run.yml": "run: python tools/wired.py\n",
                    "tests/test_thing.py": "from scripts.tested import main\n",
                    "docs/report.md": "# Report\n\nProduced by `tools/recorded.py`.\n",
                },
            )
            self.assertEqual(["tools/dormant.py"], self._executable_findings(root))

    def test_stem_matching_respects_identifier_boundaries(self) -> None:
        """A longer name must not silently clear the shorter one it contains."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(
                root,
                {
                    "tools/verify_e2e.py": "print('short')\n",
                    "tools/real_verify_e2e.py": "print('long')\n",
                    ".github/workflows/run.yml": "run: python tools/real_verify_e2e.py\n",
                },
            )
            # Only the long name is referenced. Substring matching would clear both.
            self.assertEqual(["tools/verify_e2e.py"], self._executable_findings(root))

    def test_module_plumbing_is_not_an_entry_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(
                root,
                {
                    "tools/__init__.py": "",
                    "tools/__main__.py": "print('entry')\n",
                },
            )
            self.assertEqual([], self._executable_findings(root))

    def test_unanswerable_outside_a_work_tree_reports_nothing(self) -> None:
        """No tracked-file set means no finding, never a finding by default."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "dormant.py").write_text("print('x')\n", encoding="utf-8")
            self.assertEqual([], self._executable_findings(root))

    def test_a_findings_report_does_not_clear_what_it_reports(self) -> None:
        """The check must not silence itself when someone writes down what it found.

        The first report this check produced listed all five of its findings in a
        table. Because docs/ counts as recorded output, that table cleared all five
        on the next run.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(
                root,
                {
                    "tools/dormant.py": "print('dormant')\n",
                    "docs/findings/2026-01-01-health.md": (
                        "# Health\n\nNothing runs `tools/dormant.py`.\n"
                    ),
                },
            )
            self.assertEqual(["tools/dormant.py"], self._executable_findings(root))

    def test_a_non_findings_document_still_counts_as_recorded_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(
                root,
                {
                    "tools/documented.py": "print('documented')\n",
                    "docs/guides/how-to.md": (
                        "# How to\n\nRun `tools/documented.py` to produce the bundle.\n"
                    ),
                },
            )
            self.assertEqual([], self._executable_findings(root))

    def test_the_finding_is_a_review_candidate_not_a_defect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(root, {"tools/dormant.py": "print('dormant')\n"})
            graph = build_repository_graph(root)
            links = check_links(root)
            findings = [
                finding
                for finding in check_residual_health(root, graph, links)["findings"]
                if finding["category"] == "executable_without_exercise_or_recorded_output"
            ]
            self.assertEqual(1, len(findings))
            finding = findings[0]
            # Notice, not warning: an executable can be legitimately dormant while it
            # waits on an absent dependency, and this module cannot tell that apart
            # from abandonment.
            self.assertEqual("notice", finding["severity"])
            self.assertEqual("executable:tools/dormant.py", finding["source_id"])
            self.assertEqual("P0-health", finding["evidence"]["producer"])
            self.assertTrue(finding["evidence"]["rule"])


if __name__ == "__main__":
    unittest.main()
