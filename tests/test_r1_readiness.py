import unittest

from randomness_lab.r1_readiness import ReadinessConfig, assess_cohort_readiness
from randomness_lab.r1_replay import ReplayCandidate


BASELINE = "fixed-worker-v1"
DIVERSE = "role-specialized-v1"


def candidate(task_id: str, signature: str, attempt: int, *, good: bool) -> ReplayCandidate:
    return ReplayCandidate(
        result_manifest_id=f"{task_id}/{signature}/{attempt}",
        work_unit_id=task_id,
        attempt=attempt,
        worker_id=f"worker-{signature}-{attempt}",
        structural_signature=signature,
        structural_signature_source="result.extensions.r1_structural_signature",
        verified_good=good,
        independent_test_pass=good,
        regression_finding=not good,
        security_finding=False,
        compute_units=1.0,
        human_minutes=0.1,
        observed_wall_seconds=2.0,
        verifier_signatures=("independent-verifier-v1",),
    )


def verified_task(index: int) -> tuple[dict, list[ReplayCandidate]]:
    task_id = f"held-out-{index:03d}"
    candidates = [
        candidate(task_id, BASELINE, 1, good=index % 3 != 0),
        candidate(task_id, BASELINE, 2, good=index % 4 != 0),
        candidate(task_id, DIVERSE, 3, good=index % 5 != 0),
    ]
    attempts = [
        {
            "attempt_id": f"attempt-{item.attempt}",
            "structural_signature": item.structural_signature,
            "result_manifest": {"id": item.result_manifest_id},
            "outcome": "support" if item.verified_good else "reject",
        }
        for item in candidates
    ]
    task = {
        "id": task_id,
        "split": "held_out",
        "_validated_work_unit_kind": "coding",
        "work_unit": {"id": task_id},
        "declared_structural_signatures": [BASELINE, DIVERSE],
        "negative_case": {"evidence_status": "verified"},
        "accounting": {
            "required_metrics": ["wall_seconds", "compute_units", "human_minutes"]
        },
        "evidence": {"status": "verified", "attempts": attempts},
    }
    return task, candidates


def cohort(task_count: int = 20) -> tuple[dict, list[ReplayCandidate]]:
    tasks = []
    candidates = []
    for index in range(task_count):
        task, task_candidates = verified_task(index)
        tasks.append(task)
        candidates.extend(task_candidates)
    return (
        {
            "id": "benchmark/r1-contract-fixture",
            "stage": "burned",
            "minimum_final_tasks": 20,
            "definition_digest": "sha256:" + "a" * 64,
            "taxonomy_frozen_before_outcomes": True,
            "authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
            "tasks": tasks,
        },
        candidates,
    )


def diagnostics(candidate_count: int) -> dict:
    return {
        "input_result_manifests": candidate_count,
        "input_verification_results": candidate_count,
        "conclusive_candidates": candidate_count,
        "excluded": {
            "no_independent_verification": 0,
            "inconclusive_or_conflicting_verification": 0,
        },
        "unknown_verification_result_references": 0,
    }


class R1ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = ReadinessConfig(
            baseline_signature=BASELINE,
            diversity_signatures=(BASELINE, DIVERSE),
        )

    def test_complete_synthetic_contract_fixture_is_mechanically_ready(self):
        fixture, candidates = cohort()
        first = assess_cohort_readiness(
            fixture, candidates, diagnostics(len(candidates)), self.config
        )
        second = assess_cohort_readiness(
            fixture, candidates, diagnostics(len(candidates)), self.config
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ready_for_frozen_replay")
        self.assertFalse(first["supports_empirical_r1_claim"])
        self.assertEqual(first["coverage"]["eligible_work_units"], 20)
        self.assertEqual(
            first["coverage"]["pairwise_signature_overlap"][
                f"{BASELINE}::{DIVERSE}"
            ],
            20,
        )

    def test_scaffold_with_pending_pilot_tasks_fails_closed(self):
        fixture, _ = cohort(task_count=5)
        fixture["stage"] = "scaffold"
        fixture.pop("definition_digest")
        fixture["minimum_final_tasks"] = 5
        for task in fixture["tasks"]:
            task["split"] = "pilot"
            task["evidence"] = {"status": "pending", "attempts": []}
            task["negative_case"]["evidence_status"] = "pending"

        report = assess_cohort_readiness(fixture, [], diagnostics(0), self.config)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["coverage"]["eligible_work_units"], 0)
        failed = {
            condition["code"]
            for condition in report["global_conditions"]
            if not condition["passed"]
        }
        self.assertEqual(
            failed,
            {
                "frozen_or_burned_cohort",
                "definition_digest_committed",
                "prospective_minimum_target",
                "minimum_eligible_work_units",
            },
        )

    def test_replay_signature_drift_and_missing_cost_fail_task(self):
        fixture, candidates = cohort()
        first = candidates[0]
        candidates[0] = ReplayCandidate(
            **{
                **first.__dict__,
                "structural_signature": "post-outcome-renamed-signature",
                "compute_units": None,
            }
        )

        report = assess_cohort_readiness(
            fixture, candidates, diagnostics(len(candidates)), self.config
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["coverage"]["eligible_work_units"], 19)
        self.assertEqual(
            report["tasks"][0]["blockers"],
            ["candidate_cost_measurement_missing", "replay_signature_mismatch"],
        )

    def test_one_ineligible_analyzed_task_blocks_otherwise_ready_corpus(self):
        fixture, candidates = cohort()
        pilot, pilot_candidates = verified_task(20)
        pilot["split"] = "pilot"
        fixture["tasks"].append(pilot)
        candidates.extend(pilot_candidates)

        report = assess_cohort_readiness(
            fixture, candidates, diagnostics(len(candidates)), self.config
        )

        self.assertEqual(report["coverage"]["eligible_work_units"], 20)
        self.assertEqual(report["status"], "blocked")
        condition = next(
            item
            for item in report["global_conditions"]
            if item["code"] == "all_analyzed_tasks_eligible"
        )
        self.assertFalse(condition["passed"])
        self.assertEqual(condition["observed"], ["held-out-020"])

    def test_pending_ineligible_task_without_attempts_does_not_block(self):
        fixture, candidates = cohort()
        pending, _ = verified_task(20)
        pending["split"] = "pilot"
        pending["evidence"] = {"status": "pending", "attempts": []}
        pending["negative_case"]["evidence_status"] = "pending"
        fixture["tasks"].append(pending)

        report = assess_cohort_readiness(
            fixture, candidates, diagnostics(len(candidates)), self.config
        )

        self.assertEqual(report["status"], "ready_for_frozen_replay")
        self.assertEqual(report["coverage"]["eligible_work_units"], 20)

    def test_configuration_rejects_an_unequal_diversity_arm(self):
        with self.assertRaisesRegex(ValueError, "exactly swarm_size"):
            ReadinessConfig(
                baseline_signature=BASELINE,
                diversity_signatures=(BASELINE,),
            )


if __name__ == "__main__":
    unittest.main()
