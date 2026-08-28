import json
from pathlib import Path
import tempfile
import unittest

from randomness_lab.r1_replay import (
    ReplayConfig,
    normalize_replay_candidates,
    run_replay_analysis,
    run_replay_from_paths,
)


def result_manifest(
    *,
    result_id,
    task_id,
    attempt,
    worker_id,
    adapter="same-agent",
    model="model-a",
    signature=None,
    compute_units=1.0,
    human_minutes=0.0,
):
    result = {
        "schema_version": "0.1",
        "id": result_id,
        "work_unit_id": task_id,
        "attempt": attempt,
        "worker": {
            "id": worker_id,
            "type": "agent",
            "adapter": adapter,
            "model": {
                "provider": "test-provider",
                "name": model,
                "version": "1",
            },
        },
        "status": "succeeded",
        "resources": {
            "wall_seconds": 1.0,
            "compute_units": compute_units,
            "human_minutes": human_minutes,
        },
    }
    if signature is not None:
        result["extensions"] = {"r1_structural_signature": signature}
    return result


def verification_result(
    *,
    verification_id,
    result_id,
    task_id,
    worker_id,
    accepted,
    independent=True,
    regression=False,
    security=False,
    human_minutes=0.1,
):
    passed = bool(accepted)
    findings = []
    if regression:
        findings.append(
            {
                "severity": "high",
                "category": "regression",
                "summary": "synthetic regression fixture",
            }
        )
    if security:
        findings.append(
            {
                "severity": "high",
                "category": "security",
                "summary": "synthetic security fixture",
            }
        )
    return {
        "schema_version": "0.1",
        "id": verification_id,
        "result_manifest_id": result_id,
        "work_unit_id": task_id,
        "verifier": {
            "id": f"verifier-{verification_id}",
            "type": "system",
            "adapter": "independent-test-harness",
            "model": {
                "provider": "test-provider",
                "name": "verifier-model",
                "version": "1",
            },
        },
        "independence": {
            "independent_from_worker": independent,
            "worker_id_observed": worker_id,
            "shared_model_family": False,
            "shared_runtime": False,
        },
        "status": "passed" if passed else "failed",
        "checks": [
            {
                "id": "hidden-test",
                "type": "test",
                "required": True,
                "status": "passed" if passed else "failed",
                "summary": "fixture hidden test",
                "evidence_ids": [],
            }
        ],
        "findings": findings,
        "resources": {
            "wall_seconds": 0.2,
            "compute_units": 0.1,
            "human_minutes": human_minutes,
        },
        "decision_support": {
            "recommendation": "accept_candidate" if passed else "reject_candidate",
            "confidence": 1.0,
            "rationale": "fixture verdict",
        },
    }


class R1ReplayTests(unittest.TestCase):
    def test_self_report_without_independent_verification_is_excluded(self):
        result = result_manifest(
            result_id="result-1",
            task_id="task-1",
            attempt=1,
            worker_id="worker-1",
        )
        candidate_list, diagnostics = normalize_replay_candidates([result], [])
        self.assertEqual(candidate_list, [])
        self.assertEqual(diagnostics["excluded"]["no_independent_verification"], 1)

    def test_non_independent_verification_does_not_establish_truth(self):
        result = result_manifest(
            result_id="result-1",
            task_id="task-1",
            attempt=1,
            worker_id="worker-1",
        )
        verification = verification_result(
            verification_id="verify-1",
            result_id="result-1",
            task_id="task-1",
            worker_id="worker-1",
            accepted=True,
            independent=False,
        )
        candidates, diagnostics = normalize_replay_candidates([result], [verification])
        self.assertEqual(candidates, [])
        self.assertEqual(diagnostics["excluded"]["no_independent_verification"], 1)

    def test_independent_acceptance_and_rejection_become_conclusive(self):
        good_result = result_manifest(
            result_id="good-result",
            task_id="task-1",
            attempt=1,
            worker_id="worker-good",
        )
        bad_result = result_manifest(
            result_id="bad-result",
            task_id="task-1",
            attempt=2,
            worker_id="worker-bad",
        )
        verifications = [
            verification_result(
                verification_id="verify-good",
                result_id="good-result",
                task_id="task-1",
                worker_id="worker-good",
                accepted=True,
            ),
            verification_result(
                verification_id="verify-bad",
                result_id="bad-result",
                task_id="task-1",
                worker_id="worker-bad",
                accepted=False,
                regression=True,
                security=True,
            ),
        ]
        candidates, diagnostics = normalize_replay_candidates(
            [good_result, bad_result], verifications
        )
        self.assertEqual(diagnostics["conclusive_candidates"], 2)
        by_id = {candidate.result_manifest_id: candidate for candidate in candidates}
        self.assertTrue(by_id["good-result"].verified_good)
        self.assertTrue(by_id["good-result"].independent_test_pass)
        self.assertFalse(by_id["bad-result"].verified_good)
        self.assertFalse(by_id["bad-result"].independent_test_pass)
        self.assertTrue(by_id["bad-result"].regression_finding)
        self.assertTrue(by_id["bad-result"].security_finding)

    def test_structural_signature_extension_overrides_worker_metadata(self):
        result = result_manifest(
            result_id="result-1",
            task_id="task-1",
            attempt=1,
            worker_id="worker-1",
            signature="planner-plus-coder",
        )
        verification = verification_result(
            verification_id="verify-1",
            result_id="result-1",
            task_id="task-1",
            worker_id="worker-1",
            accepted=True,
        )
        candidates, _ = normalize_replay_candidates([result], [verification])
        self.assertEqual(candidates[0].structural_signature, "planner-plus-coder")
        self.assertEqual(
            candidates[0].structural_signature_source,
            "result.extensions.r1_structural_signature",
        )

    def _comparison_fixture(self):
        results = []
        verifications = []
        # Signature A has two replicas on every work unit. Signature B is a
        # distinct structure and always independently verifies as good. A is
        # bad on three of four work units and good on the fourth. With swarm
        # size 2, diversity A+B therefore has a clear synthetic advantage.
        for task_index in range(1, 5):
            task_id = f"task-{task_index}"
            a_good = task_index == 4
            for attempt in (1, 2):
                result_id = f"{task_id}-a-{attempt}"
                worker_id = f"worker-a-{attempt}"
                results.append(
                    result_manifest(
                        result_id=result_id,
                        task_id=task_id,
                        attempt=attempt,
                        worker_id=worker_id,
                        signature="signature-a",
                    )
                )
                verifications.append(
                    verification_result(
                        verification_id=f"verify-{result_id}",
                        result_id=result_id,
                        task_id=task_id,
                        worker_id=worker_id,
                        accepted=a_good,
                    )
                )

            result_id = f"{task_id}-b-1"
            worker_id = "worker-b"
            results.append(
                result_manifest(
                    result_id=result_id,
                    task_id=task_id,
                    attempt=3,
                    worker_id=worker_id,
                    adapter="different-agent",
                    model="model-b",
                    signature="signature-b",
                )
            )
            verifications.append(
                verification_result(
                    verification_id=f"verify-{result_id}",
                    result_id=result_id,
                    task_id=task_id,
                    worker_id=worker_id,
                    accepted=True,
                )
            )
        return results, verifications

    def test_fixed_budget_real_replay_can_identify_helpful_diversity_fixture(self):
        results, verifications = self._comparison_fixture()
        candidates, diagnostics = normalize_replay_candidates(results, verifications)
        config = ReplayConfig(
            swarm_size=2,
            bootstrap_trials=300,
            seed=23,
            baseline_signature="signature-a",
        )
        first = run_replay_analysis(
            candidates, config, normalization_diagnostics=diagnostics
        )
        second = run_replay_analysis(
            candidates, config, normalization_diagnostics=diagnostics
        )
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["coverage"]["eligible_work_units"], 4)
        self.assertGreater(first["success_delta"]["mean_delta"], 0.0)
        self.assertEqual(first["success_delta"]["classification"], "helps")
        self.assertEqual(len(first["raw_bootstrap_trials"]), 300)

    def test_replay_reports_insufficient_data_without_multiple_structures(self):
        results = []
        verifications = []
        for attempt in (1, 2):
            result_id = f"result-{attempt}"
            worker_id = f"worker-{attempt}"
            results.append(
                result_manifest(
                    result_id=result_id,
                    task_id="task-1",
                    attempt=attempt,
                    worker_id=worker_id,
                    signature="signature-a",
                )
            )
            verifications.append(
                verification_result(
                    verification_id=f"verify-{attempt}",
                    result_id=result_id,
                    task_id="task-1",
                    worker_id=worker_id,
                    accepted=True,
                )
            )
        candidates, diagnostics = normalize_replay_candidates(results, verifications)
        report = run_replay_analysis(
            candidates,
            ReplayConfig(
                swarm_size=2,
                bootstrap_trials=20,
                seed=1,
                baseline_signature="signature-a",
            ),
            normalization_diagnostics=diagnostics,
        )
        self.assertEqual(report["status"], "insufficient_data")

    def test_path_loader_accepts_json_arrays(self):
        results, verifications = self._comparison_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results_path = root / "results.json"
            verifications_path = root / "verifications.json"
            results_path.write_text(json.dumps(results), encoding="utf-8")
            verifications_path.write_text(json.dumps(verifications), encoding="utf-8")
            report = run_replay_from_paths(
                results_path,
                verifications_path,
                ReplayConfig(
                    swarm_size=2,
                    bootstrap_trials=30,
                    seed=8,
                    baseline_signature="signature-a",
                ),
            )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["normalization"]["conclusive_candidates"], 12)


if __name__ == "__main__":
    unittest.main()
