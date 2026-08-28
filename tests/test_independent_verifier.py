from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from experiments import harness
from experiments.independent_verifier import sha256_file, verify_candidate
from experiments.provenance_integrity import validate_integrity

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "examples/experiments/phase0-smoke.manifest.json"
WORK_UNIT_PATH = ROOT / "examples/work-units/phase0-smoke.work-unit.json"
BASE_WORKER_RESULT_PATH = ROOT / "examples/results/phase0-smoke.result-manifest.json"


def candidate_rows() -> list[dict[str, object]]:
    manifest = harness.load_json(MANIFEST_PATH)
    manifest_digest = harness.canonical_digest(manifest)
    rows: list[dict[str, object]] = []
    for configuration in manifest["configurations"]:
        for seed in manifest["seeds"]:
            for repetition in range(1, manifest["repetitions"] + 1):
                score = harness.deterministic_score(
                    manifest["id"], configuration["id"], seed
                )
                rows.append(
                    {
                        "schema_version": "0.1",
                        "experiment_id": manifest["id"],
                        "run_id": f"{configuration['id']}-seed{seed}-r{repetition}",
                        "configuration_id": configuration["id"],
                        "seed": seed,
                        "status": "passed",
                        "started_at": "2026-08-28T13:30:00Z",
                        "finished_at": "2026-08-28T13:30:01Z",
                        "metrics": {
                            "smoke_score": score,
                            "work_unit_count": len(manifest["work_units"]),
                            "agent_count": configuration["agent_count"],
                        },
                        "costs": {
                            "wall_seconds": 0.001,
                            "compute_units": 0.0,
                            "human_minutes": 0.0,
                            "tokens": 0,
                        },
                        "verification": {
                            "policy": configuration["verification_policy"],
                            "passed": True,
                            "checks": [
                                {
                                    "id": "candidate-self-check",
                                    "passed": True,
                                    "detail": "Candidate-side fixture metadata; not independent acceptance evidence.",
                                }
                            ],
                        },
                        "artifacts": [],
                        "provenance": {
                            "harness_version": harness.HARNESS_VERSION,
                            "manifest_digest": manifest_digest,
                        },
                        "notes": "Test fixture for the independent verifier.",
                        "extensions": {
                            "org.idkmesh.phase0.repetition": repetition
                        },
                    }
                )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_worker_result(path: Path, candidate_path: Path, digest: str | None = None) -> dict:
    worker_result = harness.load_json(BASE_WORKER_RESULT_PATH)
    work_unit = harness.load_json(WORK_UNIT_PATH)
    worker_result["produced_artifacts"][0]["locator"] = str(candidate_path)
    worker_result["produced_artifacts"][0]["digest"] = digest or sha256_file(candidate_path)
    worker_result["provenance"]["work_unit_digest"] = harness.canonical_digest(work_unit)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(worker_result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return worker_result


class IndependentVerifierTests(unittest.TestCase):
    def test_good_candidate_passes_and_binds_exact_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            candidate_path = tmp / "candidate.jsonl"
            worker_result_path = tmp / "worker-result.json"
            verification_path = tmp / "verification-result.json"

            write_jsonl(candidate_path, candidate_rows())
            worker_result = write_worker_result(worker_result_path, candidate_path)

            result = verify_candidate(
                manifest_path=MANIFEST_PATH,
                worker_result_path=worker_result_path,
                candidate_path=candidate_path,
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(
                result["decision_support"]["recommendation"], "accept_candidate"
            )
            self.assertTrue(
                all(
                    check["status"] == "passed"
                    for check in result["checks"]
                    if check["required"]
                )
            )

            with verification_path.open("w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, sort_keys=True)
                handle.write("\n")

            _, work_units = harness.validate_manifest_and_work_units(MANIFEST_PATH)
            harness.validate_verification_result_contract(
                verification_path, worker_result, work_units
            )
            work_unit = harness.load_json(WORK_UNIT_PATH)
            bindings = validate_integrity(work_unit, worker_result, result)
            self.assertEqual(
                bindings["result_manifest_digest"],
                harness.canonical_digest(worker_result),
            )

    def test_tampered_smoke_score_is_rejected_by_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            candidate_path = tmp / "candidate.jsonl"
            worker_result_path = tmp / "worker-result.json"

            rows = candidate_rows()
            rows[0] = copy.deepcopy(rows[0])
            rows[0]["metrics"]["smoke_score"] = float(  # type: ignore[index]
                rows[0]["metrics"]["smoke_score"]  # type: ignore[index]
            ) + 0.25
            write_jsonl(candidate_path, rows)
            write_worker_result(worker_result_path, candidate_path)

            result = verify_candidate(
                manifest_path=MANIFEST_PATH,
                worker_result_path=worker_result_path,
                candidate_path=candidate_path,
            )
            checks = {check["id"]: check for check in result["checks"]}
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                result["decision_support"]["recommendation"], "reject_candidate"
            )
            self.assertEqual(checks["artifact-integrity"]["status"], "passed")
            self.assertEqual(checks["schema"]["status"], "passed")
            self.assertEqual(checks["reproduction"]["status"], "failed")

    def test_stale_worker_digest_is_rejected_even_when_content_reproduces(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            candidate_path = tmp / "candidate.jsonl"
            worker_result_path = tmp / "worker-result.json"

            write_jsonl(candidate_path, candidate_rows())
            stale_digest = "sha256:" + "0" * 64
            write_worker_result(worker_result_path, candidate_path, digest=stale_digest)

            result = verify_candidate(
                manifest_path=MANIFEST_PATH,
                worker_result_path=worker_result_path,
                candidate_path=candidate_path,
            )
            checks = {check["id"]: check for check in result["checks"]}
            self.assertEqual(result["status"], "failed")
            self.assertEqual(checks["artifact-integrity"]["status"], "failed")
            self.assertEqual(checks["schema"]["status"], "passed")
            self.assertEqual(checks["reproduction"]["status"], "passed")
            self.assertTrue(
                any(finding["category"] == "provenance" for finding in result["findings"])
            )


if __name__ == "__main__":
    unittest.main()
