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
        "corpus": {"available": True, "cohorts": [], "audited_cohorts": 4,
                   "total_cohorts": 4, "best_eligible_work_units": 0,
                   "minimum_required": 20},
        "workflows": {"available": True,
                      "state_writing_workflows": ["ace-community-growth.yml"],
                      "hard_coded_issue_numbers": {}, "referenced_issue_numbers": []},
        "node": {"available": True, "node_directory_present": False},
        "activation_gate": {"available": True, "verified_descendant_count": 0,
                            "independently_verified": False,
                            "source": "examples/community/x.json (provenance: issue:109)"},
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
            "worker_fleet": {"collaboration": {"distinct_actors": 10}},
            "external_descendant_evidence": {
                "activation_gate": {"verified_descendant_count": 1}
            },
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
                     "multiple_actors", "evidence_priors", "worker_fleet"):
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
        # 2, 13, 22 and 86 are advanceable by work in this repository and 12 is
        # blocked on owner-held credentials, which no repository evidence can
        # observe; none of the first four may be recorded as externally blocked.
        unclassified = {2, 12, 13, 22}
        self.assertFalse(unclassified & set(gate.REGISTRY))

    def test_an_advanceable_research_issue_is_never_recorded_as_blocked(self) -> None:
        # The failure this guards against is the tempting one: filing a research
        # question as "structurally blocked" because no one has done it yet.
        for number in (2, 13, 22):
            with self.subTest(issue=number):
                self.assertNotIn(number, gate.REGISTRY)


class WorkerFleetTest(unittest.TestCase):
    def test_one_actor_does_not_meet_a_ten_node_fleet(self) -> None:
        check = gate.PRECONDITIONS["worker_fleet"](
            {"collaboration": {"available": True, "distinct_actors": 1}}
        )
        self.assertFalse(check["met"])
        self.assertEqual(check["observed"], 1)
        self.assertEqual(check["required"], ">= 10")

    def test_the_fleet_bar_is_higher_than_the_two_actor_bar(self) -> None:
        # Issue 1 asks for 10-20 nodes; issue 10 only needs a second actor.
        evidence = {"collaboration": {"available": True, "distinct_actors": 3}}
        self.assertTrue(gate.PRECONDITIONS["multiple_actors"](evidence)["met"])
        self.assertFalse(gate.PRECONDITIONS["worker_fleet"](evidence)["met"])

    def test_a_real_fleet_would_meet_it(self) -> None:
        check = gate.PRECONDITIONS["worker_fleet"](
            {"collaboration": {"available": True, "distinct_actors": 12}}
        )
        self.assertTrue(check["met"])

    def test_unavailable_observables_report_no_measurement(self) -> None:
        check = gate.PRECONDITIONS["worker_fleet"](
            {"collaboration": {"available": False}}
        )
        self.assertIsNone(check["observed"], "a missing snapshot is not zero nodes")
        self.assertFalse(check["met"])


class ActivationGateEvidenceTest(unittest.TestCase):
    def test_the_committed_snapshot_reports_no_verified_descendants(self) -> None:
        evidence = gate.activation_gate_evidence(REPO_ROOT)
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["verified_descendant_count"], 0)

    def test_the_source_names_the_snapshot_and_its_provenance(self) -> None:
        # The count is a committed snapshot, not a live GitHub query, so the
        # report must say so rather than imply it was measured just now.
        evidence = gate.activation_gate_evidence(REPO_ROOT)
        self.assertIn("ace-activation-gate-current.example.json", evidence["source"])
        self.assertIn("provenance:", evidence["source"])

    def test_a_missing_snapshot_yields_no_measurement(self) -> None:
        evidence = gate.activation_gate_evidence(REPO_ROOT / "does" / "not" / "exist")
        self.assertFalse(evidence["available"])
        self.assertIsNone(evidence["verified_descendant_count"])
        check = gate.PRECONDITIONS["external_descendant_evidence"](
            {"activation_gate": evidence}
        )
        self.assertIsNone(check["observed"])
        self.assertFalse(check["met"])

    def test_a_verified_descendant_would_meet_it(self) -> None:
        check = gate.PRECONDITIONS["external_descendant_evidence"](
            {"activation_gate": {"available": True, "verified_descendant_count": 2}}
        )
        self.assertTrue(check["met"])


class PartialGateTest(unittest.TestCase):
    def test_issues_with_delivered_work_are_marked_partial(self) -> None:
        # 4, 16, 57 and 86 all have shipped deliverables; recording them as
        # wholly blocked would misreport the repository's own state.
        for number in (4, 16, 57, 86):
            with self.subTest(issue=number):
                self.assertTrue(gate.REGISTRY[number].get("partial"))

    def test_the_partial_flag_reaches_the_report(self) -> None:
        report = gate.audit()
        self.assertTrue(report["issues"]["57"]["partial_gate"])
        self.assertFalse(report["issues"]["9"]["partial_gate"])


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
        self.assertTrue(corpus["cohorts"], "no cohort was found")
        self.assertEqual(corpus["total_cohorts"], len(corpus["cohorts"]))
        for row in corpus["cohorts"]:
            # Either the frozen audit ran and reported coverage, or it could not
            # run and said so. A row that claims neither is a silent zero.
            self.assertTrue(
                "eligible_work_units" in row or row["status"] == "audit_did_not_run",
                row,
            )

    def test_an_unrunnable_corpus_audit_reads_as_cannot_tell_not_as_zero(self) -> None:
        # The audit needs the Phase 0 schema validator. Workflows that run
        # without it must not turn "could not measure" into "measured zero",
        # which would look identical to a genuinely empty corpus.
        ev = _evidence()
        ev["corpus"] = {"available": False, "cohorts": [], "audited_cohorts": 0,
                        "total_cohorts": 4, "best_eligible_work_units": None,
                        "minimum_required": 20}
        check = gate.PRECONDITIONS["real_corpus"](ev)
        self.assertFalse(check["met"])
        self.assertIsNone(check["observed"])

    def test_a_partially_audited_corpus_is_not_treated_as_complete(self) -> None:
        # One unreadable cohort could hide a ready one behind it.
        ev = _evidence()
        ev["corpus"] = {"available": False, "cohorts": [], "audited_cohorts": 3,
                        "total_cohorts": 4, "best_eligible_work_units": 0,
                        "minimum_required": 20}
        self.assertIsNone(gate.PRECONDITIONS["real_corpus"](ev)["observed"])

    def test_a_readiness_audit_that_cannot_run_yields_no_measurement(self) -> None:
        # Reproduces the CI shape: a job that runs without the Phase 0 schema
        # validator cannot execute the readiness audit at all. `/bin/false`
        # stands in -- it exits non-zero with no stdout, exactly like the
        # interpreter that cannot import jsonschema.
        if not Path("/bin/false").exists():  # pragma: no cover
            self.skipTest("/bin/false is unavailable")
        evidence = gate.corpus_evidence(REPO_ROOT, python="/bin/false")
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["audited_cohorts"], 0)
        self.assertGreater(evidence["total_cohorts"], 0)
        self.assertIsNone(evidence["best_eligible_work_units"])
        for row in evidence["cohorts"]:
            self.assertEqual(row["status"], "audit_did_not_run")
        check = gate.PRECONDITIONS["real_corpus"]({"corpus": evidence})
        self.assertFalse(check["met"])
        self.assertIsNone(check["observed"], "an unrunnable audit must not report 0")

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
