"""Tests for the benchmark cohort publication (issue #10).

The publication's whole value is that it cannot quietly disagree with the
cohorts it describes, so most of these tests are about *derivation*: the
committed files must be exactly what the generator produces, the counts must
come from the cohort definitions rather than from the prose, and the honest
statements must appear when — and only when — the evidence warrants them.
"""

from __future__ import annotations

import json
import pathlib
import unittest

import tools.benchmark_publication as bp

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _cohort(**overrides):
    base = {
        "schema_version": "0.1",
        "id": "benchmark/fixture",
        "title": "Fixture cohort",
        "stage": "frozen",
        "minimum_final_tasks": 2,
        "required_families": ["bug_fix", "refactor"],
        "taxonomy_frozen_before_outcomes": True,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
        "tasks": [
            {
                "id": "benchmark/fixture/001",
                "family": "bug_fix",
                "split": "pilot",
                "evidence": {"status": "pending", "attempts": []},
                "negative_case": {"expected_category": "regression"},
            },
            {
                "id": "benchmark/fixture/002",
                "family": "refactor",
                "split": "pilot",
                "evidence": {"status": "pending", "attempts": []},
                "negative_case": {"expected_category": "correctness"},
            },
        ],
    }
    base.update(overrides)
    return base


def _measured(outcome="support", signature="single-worker-baseline-v1", n=2):
    cohort = _cohort()
    for i, task in enumerate(cohort["tasks"][:n]):
        task["evidence"] = {
            "status": "verified",
            "attempts": [
                {
                    "attempt_id": f"a{i}",
                    "outcome": outcome,
                    "structural_signature": signature,
                }
            ],
        }
    return cohort


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class DiscoveryTest(unittest.TestCase):
    def test_every_committed_cohort_is_discovered(self):
        found = {p.parent.name for p in bp.discover()}
        on_disk = {
            p.parent.name for p in (ROOT / "benchmarks").glob("*/cohort.json")
        }
        self.assertEqual(found, on_disk)
        self.assertTrue(found, "no cohorts discovered at all")

    def test_discovery_is_ordered(self):
        paths = bp.discover()
        self.assertEqual(paths, sorted(paths))


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class OutcomeCountingTest(unittest.TestCase):
    def test_attempts_are_read_from_evidence_not_the_task_root(self):
        # The attempts live under evidence.attempts. Reading task["attempts"]
        # returns nothing and would report a measured cohort as unmeasured.
        out = bp._outcomes(_measured())
        self.assertEqual(out["attempts"], 2)
        self.assertEqual(out["by_outcome"], {"support": 2})

    def test_signatures_are_counted_distinctly(self):
        cohort = _measured(n=1)
        cohort["tasks"][1]["evidence"] = {
            "status": "verified",
            "attempts": [
                {"attempt_id": "b", "outcome": "reject", "structural_signature": "other-v1"}
            ],
        }
        out = bp._outcomes(cohort)
        self.assertEqual(out["distinct_structural_signatures"], 2)
        self.assertEqual(out["by_outcome"], {"reject": 1, "support": 1})

    def test_a_cohort_with_no_attempts_counts_zero(self):
        out = bp._outcomes(_cohort())
        self.assertEqual(out["attempts"], 0)
        self.assertEqual(out["by_outcome"], {})


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class StatementTest(unittest.TestCase):
    """The statements are the part a reader will quote. They must be earned."""

    def _statements(self, cohorts):
        totals = {
            "cohorts": len(cohorts),
            "tasks": sum(c["tasks"] for c in cohorts),
            "measured_tasks": sum(c["measured_tasks"] for c in cohorts),
        }
        return bp._statements(cohorts, totals)

    def _summary(self, cohort):
        summary = {
            "tasks": len(cohort["tasks"]),
            "measured_tasks": sum(
                1 for t in cohort["tasks"] if t["evidence"]["status"] == "verified"
            ),
            "outcomes": bp._outcomes(cohort),
        }
        return summary

    def test_no_measured_outcome_says_so_plainly(self):
        statements = self._statements([self._summary(_cohort())])
        self.assertEqual(len(statements), 1)
        self.assertIn("No cohort carries a measured outcome", statements[0])

    def test_a_single_signature_is_called_a_baseline_not_a_comparison(self):
        statements = " ".join(self._statements([self._summary(_measured())]))
        self.assertIn("single structural signature", statements)
        self.assertIn("not a comparison", statements)

    def test_two_signatures_do_not_trigger_the_baseline_caveat(self):
        cohort = _measured(n=1)
        cohort["tasks"][1]["evidence"] = {
            "status": "verified",
            "attempts": [
                {"attempt_id": "b", "outcome": "support", "structural_signature": "other-v1"}
            ],
        }
        statements = " ".join(self._statements([self._summary(cohort)]))
        self.assertNotIn("not a comparison", statements)

    def test_a_uniform_outcome_is_flagged_as_undiscriminating(self):
        statements = " ".join(self._statements([self._summary(_measured())]))
        self.assertIn("has not been shown to discriminate", statements)

    def test_mixed_outcomes_are_not_flagged(self):
        cohort = _measured(n=1)
        cohort["tasks"][1]["evidence"] = {
            "status": "verified",
            "attempts": [
                {
                    "attempt_id": "b",
                    "outcome": "reject",
                    "structural_signature": "single-worker-baseline-v1",
                }
            ],
        }
        statements = " ".join(self._statements([self._summary(cohort)]))
        self.assertNotIn("has not been shown to discriminate", statements)


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class DeterminismTest(unittest.TestCase):
    def test_two_runs_agree_byte_for_byte(self):
        a = bp._serialize(bp.publication())
        b = bp._serialize(bp.publication())
        self.assertEqual(a, b)

    def test_the_report_carries_no_timestamp(self):
        text = bp._serialize(bp.publication()).lower()
        for word in ("timestamp", "generated_at", "date", "utc"):
            self.assertNotIn(f'"{word}"', text)


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class CommittedPublicationTest(unittest.TestCase):
    """The committed files must be exactly what the generator produces."""

    def setUp(self):
        self.report = bp.publication()

    def test_the_committed_json_is_current(self):
        committed = bp.REPORT_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            committed,
            bp._serialize(self.report),
            "benchmarks/publication.json is stale; regenerate it",
        )

    def test_the_committed_markdown_is_current(self):
        committed = bp.MARKDOWN_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            committed,
            bp.render_markdown(self.report),
            "benchmarks/PUBLICATION.md is stale; regenerate it",
        )

    def test_check_mode_passes_on_the_committed_tree(self):
        self.assertEqual(bp.main(["--check"]), 0)

    def test_every_cohort_passes_its_own_contract(self):
        for cohort in self.report["cohorts"]:
            with self.subTest(cohort=cohort["id"]):
                self.assertTrue(
                    cohort["contract"]["valid"], cohort["contract"]["error"]
                )

    def test_totals_add_up_from_the_cohorts(self):
        totals = self.report["totals"]
        self.assertEqual(
            totals["tasks"], sum(c["tasks"] for c in self.report["cohorts"])
        )
        self.assertEqual(
            totals["measured_tasks"],
            sum(c["measured_tasks"] for c in self.report["cohorts"]),
        )
        self.assertEqual(
            totals["attempts"],
            sum(c["outcomes"]["attempts"] for c in self.report["cohorts"]),
        )

    def test_the_markdown_headline_matches_the_totals(self):
        totals = self.report["totals"]
        text = bp.MARKDOWN_PATH.read_text(encoding="utf-8")
        self.assertIn(
            f"**{totals['cohorts']} cohorts · {totals['tasks']} tasks · "
            f"{totals['measured_tasks']} with a verified outcome · "
            f"{totals['attempts']} attempts**",
            text,
        )

    def test_no_aggregate_score_is_published(self):
        # Averaging one signature's outcomes into a rate would invent a result.
        text = bp.MARKDOWN_PATH.read_text(encoding="utf-8").lower()
        for banned in ("pass rate", "success rate", "score:", "ranking"):
            self.assertNotIn(banned, text)


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class CheckModeTest(unittest.TestCase):
    def test_a_drifted_file_is_reported_rather_than_silently_rewritten(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            stale_json = pathlib.Path(tmp) / "publication.json"
            stale_md = pathlib.Path(tmp) / "PUBLICATION.md"
            stale_json.write_text("{}\n", encoding="utf-8")
            stale_md.write_text("# stale\n", encoding="utf-8")
            rc = bp.main(
                ["--check", "--output", str(stale_json), "--markdown", str(stale_md)]
            )
            self.assertEqual(rc, 1)
            # --check must not repair what it found.
            self.assertEqual(stale_json.read_text(encoding="utf-8"), "{}\n")

    def test_a_missing_file_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            rc = bp.main(
                [
                    "--check",
                    "--output",
                    str(pathlib.Path(tmp) / "nope.json"),
                    "--markdown",
                    str(pathlib.Path(tmp) / "nope.md"),
                ]
            )
            self.assertEqual(rc, 1)


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class WorkflowCoverageTest(unittest.TestCase):
    """Every cohort must be covered by the contract workflow's path filters."""

    def test_the_workflow_watches_every_cohort_directory(self):
        workflow = (
            ROOT / ".github" / "workflows" / "benchmark-cohort-contract.yml"
        ).read_text(encoding="utf-8")
        for path in bp.discover():
            directory = path.parent.name
            with self.subTest(cohort=directory):
                self.assertTrue(
                    f"benchmarks/{directory}/**" in workflow
                    or "benchmarks/**" in workflow,
                    f"benchmarks/{directory} is not watched by the contract workflow",
                )

    def test_the_workflow_runs_the_publication_check(self):
        workflow = (
            ROOT / ".github" / "workflows" / "benchmark-cohort-contract.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("tools/benchmark_publication.py --check", workflow)


@unittest.skipUnless(
    bp.JSONSCHEMA_AVAILABLE,
    "benchmark publication tests require requirements-phase0.txt",
)
class AuditAgreementTest(unittest.TestCase):
    """The open-issue audit quotes cohort counts; they must match the generator.

    The audit originally stated that all four cohorts carried six recorded
    attempts. The generated publication counts five, all inside a single
    cohort. Prose that restates a derived number is a place where drift hides,
    so the number is pinned to the generator here.
    """

    AUDIT = ROOT / "docs" / "audits" / "2026-08-30-open-issue-evidence-gates.md"

    def setUp(self):
        self.text = self.AUDIT.read_text(encoding="utf-8")
        self.report = bp.publication()

    def test_the_audit_does_not_repeat_the_withdrawn_six_attempt_count(self):
        self.assertNotIn(
            "five tasks with six recorded attempts",
            self.text,
            "the audit still carries the withdrawn hand-counted attempt total",
        )

    def test_the_generated_attempt_total_is_five(self):
        self.assertEqual(
            sum(c["outcomes"]["attempts"] for c in self.report["cohorts"]),
            5,
            "the audit prose is written against a total of five attempts",
        )

    def test_exactly_one_cohort_holds_every_attempt(self):
        carrying = [c for c in self.report["cohorts"] if c["outcomes"]["attempts"]]
        self.assertEqual(
            [c["id"] for c in carrying],
            ["benchmark/phase-b2-successor-five"],
            "the audit names phase-b2-successor-five as the sole carrier",
        )

    def test_the_audit_points_at_the_generator(self):
        self.assertIn("tools/benchmark_publication.py", self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
