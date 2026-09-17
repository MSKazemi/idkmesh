import copy
import json
from pathlib import Path

import pytest

from experiments import harness


ROOT = Path(__file__).resolve().parents[1]
RESULT_FIXTURE = ROOT / "examples/results/phase0-smoke.result-manifest.json"
WORK_UNITS = {"phase0/smoke-work-unit": {"version": 2}}


def _load_result_fixture() -> dict:
    with RESULT_FIXTURE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_result(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "result-manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_worker_result_accepts_unique_produced_artifact_ids() -> None:
    result = harness.validate_worker_result_contract(RESULT_FIXTURE, WORK_UNITS)

    assert result["produced_artifacts"][0]["id"] == "candidate-result"


def test_worker_result_rejects_duplicate_produced_artifact_ids(tmp_path: Path) -> None:
    result = _load_result_fixture()
    duplicate = copy.deepcopy(result["produced_artifacts"][0])
    duplicate["locator"] = "results/phase0-smoke-duplicate.jsonl"
    duplicate["digest"] = "sha256:" + "1" * 64
    result["produced_artifacts"].append(duplicate)

    assert harness.validation_errors(result, harness.WORKER_RESULT_SCHEMA) == []
    path = _write_result(tmp_path, result)

    with pytest.raises(
        harness.HarnessError,
        match=r"duplicate produced artifact id\(s\): candidate-result",
    ):
        harness.validate_worker_result_contract(path, WORK_UNITS)


def test_worker_result_reports_all_duplicate_artifact_ids_in_stable_order(
    tmp_path: Path,
) -> None:
    result = _load_result_fixture()
    first = result["produced_artifacts"][0]
    second = copy.deepcopy(first)
    second.update(
        {
            "id": "alpha-result",
            "locator": "results/alpha.jsonl",
            "digest": "sha256:" + "2" * 64,
        }
    )
    result["produced_artifacts"].extend(
        [
            second,
            {**copy.deepcopy(first), "locator": "results/candidate-copy.jsonl"},
            {**copy.deepcopy(second), "locator": "results/alpha-copy.jsonl"},
        ]
    )

    assert harness.validation_errors(result, harness.WORKER_RESULT_SCHEMA) == []
    path = _write_result(tmp_path, result)

    with pytest.raises(
        harness.HarnessError,
        match=r"duplicate produced artifact id\(s\): alpha-result, candidate-result",
    ):
        harness.validate_worker_result_contract(path, WORK_UNITS)


def test_worker_result_still_rejects_unknown_evidence_artifact_id(tmp_path: Path) -> None:
    result = _load_result_fixture()
    result["verification_request"]["evidence_artifact_ids"] = ["missing-artifact"]
    path = _write_result(tmp_path, result)

    with pytest.raises(
        harness.HarnessError,
        match=r"requests verification of unknown artifact id\(s\): missing-artifact",
    ):
        harness.validate_worker_result_contract(path, WORK_UNITS)
