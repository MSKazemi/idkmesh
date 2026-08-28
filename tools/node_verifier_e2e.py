#!/usr/bin/env python3
"""Run the accepted frozen idkmesh-node and independently verify its real patch bundle.

This is an integration/evidence harness, not an acceptance or merge authority.
The worker candidate is loaded from a separate exact-SHA checkout. Evaluator
control is created and executed from this evaluator-owned repository checkout.
Candidate code is not executed by the verifier backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import node_runtime_acceptance as acceptance

CANDIDATE_SHA = "cbd40c43497ae4feb3a4a5e410dc78766b6cb19c"
SOURCE_SHA = "b1397a9be91da6570e8ae370de4fa9f4bc44df5c"
EXPECTED_ADDED_TEXT = "<!-- idkmesh-node candidate smoke -->"


class E2EError(RuntimeError):
    pass


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise E2EError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E2EError(f"expected JSON object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise E2EError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def build_plan(work_unit: dict[str, Any]) -> dict[str, Any]:
    required_validator_ids = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    return {
        "backend": {
            "max_candidate_bytes": 1_000_000,
            "max_log_bytes": 262_144,
            "require_nonempty_patch": True,
            "required_added_text": [EXPECTED_ADDED_TEXT],
            "type": "unified_diff",
            "verify_log_digests": True,
        },
        "binding": {
            "source_revision": SOURCE_SHA,
            "work_unit_digest": canonical_digest(work_unit),
            "work_unit_id": work_unit["id"],
            "work_unit_version": work_unit["version"],
        },
        "candidate_artifact_id": "candidate-patch",
        "execution_mode": "metadata_only",
        "extensions": {
            "org.idkmesh.real_node_e2e": {
                "candidate_sha": CANDIDATE_SHA,
                "purpose": "independent replay of a real canonical-node patch bundle",
            }
        },
        "id": "verification/real-node-cbd40c4-plan",
        "policy": {
            "require_output_outside_candidate_root": True,
            "require_plan_outside_candidate_root": True,
            "require_verifier_distinct_from_worker": True,
        },
        "required_validator_ids": required_validator_ids,
        "schema_version": "0.2",
        "verifier": {
            "adapter": "deterministic-patch-verifier",
            "adapter_version": "0.1",
            "id": "idkmesh-local-verifier",
            "type": "system",
        },
        "visibility": "public",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/verification/real-node-cbd40c4",
        help="Evaluator-repository-relative evidence root under results/.",
    )
    args = parser.parse_args()

    evaluator_root = Path(__file__).resolve().parents[1]
    candidate = args.candidate.resolve()
    actual_sha = run(
        ["git", "rev-parse", "HEAD"],
        cwd=candidate,
    ).stdout.strip()
    assert_true(actual_sha == CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")

    output_root = (evaluator_root / args.output_root).resolve()
    try:
        relative_output = output_root.relative_to(evaluator_root)
    except ValueError as exc:
        raise E2EError("output root escapes evaluator repository") from exc
    assert_true(
        bool(relative_output.parts) and relative_output.parts[0] == "results",
        "output root must remain under evaluator-owned results/",
    )
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    candidate_root = output_root / "candidate-bundle"
    work_unit_path = output_root / "work-unit.json"
    plan_path = output_root / "evaluator-plan.json"
    verification_path = output_root / "verification-result.json"

    source_fixture = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"
    work_unit = load_json(source_fixture)
    assert_true(
        work_unit["provenance"]["source_revision"] == SOURCE_SHA,
        "WorkUnit source revision drift",
    )
    write_json(work_unit_path, work_unit)

    # Generate the candidate using only the frozen worker checkout and a
    # sanitized process environment. The evaluator plan does not yet exist.
    with tempfile.TemporaryDirectory(prefix="idkmesh-real-node-e2e-home-") as raw_home:
        env = acceptance.candidate_env(candidate, Path(raw_home))
        worker_proc = run(
            [
                sys.executable,
                "-m",
                "idkmesh_node",
                "run",
                str(source_fixture),
                "--output",
                str(candidate_root),
            ],
            cwd=candidate,
            env=env,
            check=False,
        )
    assert_true(
        worker_proc.returncode == 0,
        "real node producer failed before independent verification:\n"
        + worker_proc.stdout
        + "\n"
        + worker_proc.stderr,
    )

    worker_result_path = candidate_root / "result-manifest.json"
    worker_result = load_json(worker_result_path)
    assert_true(worker_result["status"] == "succeeded", "worker result is not succeeded")
    assert_true(
        worker_result["provenance"]["work_unit_digest"] == canonical_digest(work_unit),
        "worker result is not bound to the exact WorkUnit",
    )
    assert_true(
        worker_result["provenance"]["source_revision"] == SOURCE_SHA,
        "worker source revision drift",
    )

    # Evaluator control is constructed only after the real worker bundle exists
    # and is stored outside candidate_root.
    plan = build_plan(work_unit)
    write_json(plan_path, plan)
    assert_true(candidate_root not in plan_path.parents, "EvaluatorPlan is candidate-owned")

    # First confirm the merged deterministic patch backend's known positive and
    # negative fixture matrix before using it on the real node bundle.
    baseline = run(
        [sys.executable, "experiments/evaluator_plan_runner.py", "patch-self-test"],
        cwd=evaluator_root,
    )
    assert_true("OK:" in baseline.stdout, "merged patch verifier self-test did not report OK")

    verify_proc = run(
        [
            sys.executable,
            "experiments/evaluator_plan_runner.py",
            "verify",
            "--work-unit",
            work_unit_path.relative_to(evaluator_root).as_posix(),
            "--result-manifest",
            worker_result_path.relative_to(evaluator_root).as_posix(),
            "--candidate-root",
            candidate_root.relative_to(evaluator_root).as_posix(),
            "--evaluator-plan",
            plan_path.relative_to(evaluator_root).as_posix(),
            "--output",
            verification_path.relative_to(evaluator_root).as_posix(),
        ],
        cwd=evaluator_root,
        check=False,
    )
    assert_true(
        verify_proc.returncode == 0,
        "independent verifier rejected the real node bundle:\n"
        + verify_proc.stdout
        + "\n"
        + verify_proc.stderr,
    )

    verification = load_json(verification_path)
    assert_true(verification["status"] == "passed", "VerificationResult status is not passed")
    assert_true(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        "verifier recommendation is not accept_candidate",
    )
    assert_true(
        verification["independence"]["independent_from_worker"] is True,
        "verifier did not preserve independence assertion",
    )
    assert_true(
        verification["independence"]["worker_id_observed"] == worker_result["worker"]["id"],
        "verifier did not bind the observed worker identity",
    )
    assert_true(
        verification["result_manifest_id"] == worker_result["id"],
        "VerificationResult points to a different ResultManifest",
    )
    required_checks = {
        item["id"]: item["status"]
        for item in verification["checks"]
        if item.get("required") is True
    }
    assert_true(
        required_checks == {
            "independent-review": "passed",
            "result-manifest-schema": "passed",
        },
        f"unexpected required check outcomes: {required_checks}",
    )
    assert_true(
        verification["extensions"]["org.idkmesh.evaluator_plan.digest"] == canonical_digest(plan),
        "VerificationResult did not retain exact EvaluatorPlan digest",
    )

    evidence = {
        "schema_version": "0.1",
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit": {
            "id": work_unit["id"],
            "version": work_unit["version"],
            "digest": canonical_digest(work_unit),
        },
        "worker": {
            "id": worker_result["worker"]["id"],
            "result_manifest_id": worker_result["id"],
            "result_manifest_digest": canonical_digest(worker_result),
            "status": worker_result["status"],
            "candidate_patch_digest": worker_result["produced_artifacts"][0]["digest"],
        },
        "evaluator": {
            "plan_id": plan["id"],
            "plan_digest": canonical_digest(plan),
            "backend": "unified_diff",
            "execution_mode": "metadata_only",
            "verification_result_id": verification["id"],
            "verification_result_digest": canonical_digest(verification),
            "status": verification["status"],
            "required_checks": required_checks,
            "recommendation": verification["decision_support"]["recommendation"],
            "independent_from_worker": verification["independence"]["independent_from_worker"],
        },
        "baseline_patch_negative_matrix_passed": True,
        "human_integration_decision_required": True,
    }
    evidence_path = output_root / "e2e-evidence.json"
    write_json(evidence_path, evidence)

    print("IDKMESH_REAL_NODE_VERIFIER_E2E_BEGIN")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("IDKMESH_REAL_NODE_VERIFIER_E2E_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (E2EError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
