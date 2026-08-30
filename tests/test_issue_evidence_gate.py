"""The gate must report what the repository measures, and must not launder a guess."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools import issue_evidence_gate as gate  # noqa: E402


def _evidence(**overrides):
    base = {
        "collaboration": {
            "available": True, "source": "results/collaboration/observables-x.json",
            "independent_review_samples": 0, "closed_without_review": 50,
            "contributor_recurrence_trials": 0, "distinct_actors": 1,
            "evidence_derived_strategy_priors": 0,
        },
        "corpus": {"available": True, "cohorts": [],
                   "best_eligible_work_units": 0, "minimum_required": 20},
        "workflows": {"available": True,
                      "state_writing_workflows": ["ace-community-growth.yml"],
                      "hard_coded_issue_numbers": {}, "referenced_issue_numbers": []},
        "node": {"available": True, "node_directory_present": False},
    }
    for key, value in overrides.items():
        base[key] = {**base[key], **value}
    return base


class PreconditionTest(unittest.TestCase):
    def test_every_precondition_is_unmet_on_the_current_repository_state(self) -> None:
        ev = _evidence()
        for name, predicate in gate.PRECONDITIONS.items():
            with self.subTest(precondition=name):
                self.assertFalse(predicate(ev)["met"])

    def test_each_precondition_flips_when_its_own_evidence_arrives(self) -> None:
        # A gate that can never open is not a gate. Each of these is the exact
        # observation that would make the corresponding issue workable.
        flips = {
            "real_corpus": {"corpus": {"best_eligible_work_units": 20}},
            "independent_review": {"collaboration": {"independent_review_samples": 1}},
            "recurring_contributors": {"collaboration": {"contributor_recurrence_trials": 1}},
            "multiple_actors": {"collaboration": {"distinct_actors": 2}},
            "evidence_priors": {"collaboration": {"evidence_derived_strategy_priors": 1}},
            "node_directory": {"node": {"node_directory_present": True}},
            "not_a_state_store": {"workflows": {"state_writing_workflows": []}},
        }
        self.assertEqual(set(flips), set(gate.PRECONDITIONS))
        for name, override in flips.items():
            with self.subTest(precondition=name):
                self.assertTrue(gate.PRECONDITIONS[name](_evidence(**override))["met"])

    def test_a_precondition_reports_what_it_observed_and_what_it_needed(self) -> None:
        for name, predicate in gate.PRECONDITIONS.items():
            with self.subTest(precondition=name):
                check = predicate(_evidence())
                self.assertIn("observed", check)
                self.assertIn("required", check)
                self.assertTrue(check["code"])

    def test_missing_collaboration_evidence_does_not_read_as_unblocked(self) -> None:
        # A fresh clone with no snapshot must report "cannot tell", never
        # "no blocker measured, therefore actionable".
        ev = _evidence()
        ev["collaboration"] = {"available": False, "source": None}
        for name in ("independent_review", "recurring_contributors",
                     "multiple_actors", "evidence_priors"):
            with self.subTest(precondition=name):
                check = gate.PRECONDITIONS[name](ev)
                self.assertFalse(check["met"])
                self.assertIsNone(check["observed"])


class RegistryTest(unittest.TestCase):
    def test_every_registry_entry_names_known_preconditions_and_a_note(self) -> None:
        for number, entry in gate.REGISTRY.items():
            with self.subTest(issue=number):
                self.assertTrue(entry["preconditions"])
                for name in entry["preconditions"]:
                    self.assertIn(name, gate.PRECONDITIONS)
                self.assertGreater(len(entry["note"]), 40, "note must say where it came from")

    def test_the_registry_does_not_claim_issues_it_cannot_measure(self) -> None:
        # Issues whose blocking reason was never verified mechanically must stay
        # out of the registry rather than be recorded as blocked on a guess.
        unclassified = {1, 2, 4, 12, 13, 16, 22, 57}
        self.assertFalse(unclassified & set(gate.REGISTRY))


class AuditTest(unittest.TestCase):
    def test_the_audit_disclaims_deciding_blockedness(self) -> None:
        report = gate.audit()
        self.assertFalse(report["authority"]["decides_whether_an_issue_is_blocked"])
        self.assertTrue(report["authority"]["reports_measured_preconditions"])
        self.assertEqual(report["contract"], gate.CONTRACT)

    def test_the_audit_covers_every_registered_issue(self) -> None:
        report = gate.audit()
        self.assertEqual(
            sorted(int(n) for n in report["issues"]), sorted(gate.REGISTRY)
        )

    def test_the_real_corpus_gate_is_the_frozen_r1_audit_not_a_reimplementation(self) -> None:
        # If this ever stops shelling out to randomness_lab.r1_readiness, the
        # preregistered thresholds could drift without anyone noticing.
        report = gate.audit()
        corpus = report["evidence"]["corpus"]
        self.assertTrue(corpus["available"], "no cohort was audited")
        self.assertTrue(corpus["cohorts"])
        for row in corpus["cohorts"]:
            self.assertIn("eligible_work_units", row, row)

    def test_workflows_that_store_state_in_issues_are_found(self) -> None:
        found = gate.workflow_evidence(REPO_ROOT)["state_writing_workflows"]
        self.assertIn("ace-community-growth.yml", found)


class CommandLineTest(unittest.TestCase):
    def test_an_unmet_precondition_is_not_an_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/issue_evidence_gate.py", "--require-no-stale-entries"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["newly_actionable"], [])

    def test_output_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gate.json"
            completed = subprocess.run(
                [sys.executable, "tools/issue_evidence_gate.py", "--output", str(out)],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("issues", json.loads(out.read_text()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
