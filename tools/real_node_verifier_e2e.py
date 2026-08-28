#!/usr/bin/env python3
"""Generate one real frozen-node bundle and verify it with current evaluator control.

The worker is an exact-SHA checkout separate from this evaluator-owned tree.
The EvaluatorPlan is created only after candidate generation and lives outside
the candidate bundle. The verifier executes no candidate code and grants no
merge, approval, or canonical-write authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"
SOURCE_SHA = "b1397a9be91da6570e8ae370de4fa9f4bc44df5c"
EXPECTED_ADDED_TEXT = "<!-- idkmesh-node candidate smoke -->"
PLAN_TEMPLATE = "verification/fixtures/patch-smoke-evaluator-plan-v0.2.json"


class E2EError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
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


def candidate_env(candidate: Path, home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    xdg = home / "xdg"
    xdg.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONPATH": str(candidate / "node" / "src"),
        "PYTHONUNBUFFERED": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


def current_plan(
    evaluator_root: Path,
    work_unit: dict[str, Any],
) -> dict[str, Any]:
    """Derive real-run control from the current canonical v0.2 plan fixture."""

    template = load_json(evaluator_root / PLAN_TEMPLATE)
    require(template.get("schema_version") == "0.2", "plan template is not EvaluatorPlan v0.2")
    require(template.get("execution_mode") == "metadata_only", "plan template is not metadata-only")
    require(template.get("backend", {}).get("type") == "unified_diff", "plan template is not unified_diff")

    required_ids = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    plan = copy.deepcopy(template)
    plan["id"] = f"verification/real-node-{CANDIDATE_SHA[:7]}-plan"
    plan["binding"] = {
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
    }
    plan["candidate_artifact_id"] = "candidate-patch"
    plan["required_validator_ids"] = required_ids
    plan["backend"]["max_candidate_bytes"] = 1_000_000
    plan["backend"]["max_log_bytes"] = 262_144
    plan["backend"]["required_added_text"] = [EXPECTED_ADDED_TEXT]
    required_log_types = set(plan["backend"].get("required_log_types", []))
    require(
        {"stdout", "stderr"}.issubset(required_log_types),
        "current EvaluatorPlan template does not require both stdout and stderr",
    )
    plan.setdefault("extensions", {})["org.idkmesh.real_node_e2e"] = {
        "candidate_sha": CANDIDATE_SHA,
        "purpose": "independent metadata-only verification of a real canonical-node bundle",
    }
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/verification/real-node-520ad2c",
        help="Evaluator-repository-relative output path under results/.",
    )
    args = parser.parse_args()

    evaluator_root = Path(__file__).resolve().parents[1]
    candidate = args.candidate.resolve()
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=candidate).stdout.strip()
    require(actual_sha == CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")

    output_root = (evaluator_root / args.output_root).resolve()
    try:
        relative_output = output_root.relative_to(evaluator_root)
    except ValueError as exc:
        raise E2EError("output root escapes evaluator repository") from exc
    require(
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
    evidence_path = output_root / "e2e-evidence.json"

    source_fixture = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"
    work_unit = load_json(source_fixture)
    require(work_unit["provenance"]["source_revision"] == SOURCE_SHA, "source revision drift")
    write_json(work_unit_path, work_unit)

    # Candidate generation happens before evaluator control exists.
    with tempfile.TemporaryDirectory(prefix="idkmesh-real-node-e2e-") as raw:
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
            env=candidate_env(candidate, Path(raw) / "candidate-home"),
            check=False,
        )
    require(
        worker_proc.returncode == 0,
        "real node producer failed before verification:\n"
        + worker_proc.stdout
        + "\n"
        + worker_proc.stderr,
    )

    worker_result_path = candidate_root / "result-manifest.json"
    worker_result = load_json(worker_result_path)
    require(worker_result["status"] == "succeeded", "worker ResultManifest is not succeeded")
    require(
        worker_result["provenance"]["work_unit_digest"] == canonical_digest(work_unit),
        "worker ResultManifest is not bound to exact WorkUnit",
    )
    require(worker_result["provenance"]["source_revision"] == SOURCE_SHA, "worker source drift")

    # Only now construct verifier-owned control outside candidate_root.
    plan = current_plan(evaluator_root, work_unit)
    write_json(plan_path, plan)
    require(candidate_root not in plan_path.parents, "EvaluatorPlan became candidate-owned")

    # Re-run the merged verifier's negative fixture matrix before real evidence.
    baseline = run(
        [sys.executable, "experiments/evaluator_plan_runner.py", "patch-self-test"],
        cwd=evaluator_root,
    )
    require("OK:" in baseline.stdout, "canonical patch-verifier negative matrix did not pass")

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
    require(
        verify_proc.returncode == 0,
        "independent verifier rejected real node bundle:\n"
        + verify_proc.stdout
        + "\n"
        + verify_proc.stderr,
    )

    verification = load_json(verification_path)
    require(verification["status"] == "passed", "VerificationResult is not passed")
    require(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        "VerificationResult did not recommend accept_candidate",
    )
    require(
        verification["independence"]["independent_from_worker"] is True,
        "independent_from_worker was not preserved",
    )
    require(
        verification["result_manifest_id"] == worker_result["id"],
        "VerificationResult points to a different ResultManifest",
    )
    required_checks = {
        item["id"]: item["status"]
        for item in verification["checks"]
        if item.get("required") is True
    }
    require(
        required_checks == {
            "independent-review": "passed",
            "result-manifest-schema": "passed",
        },
        f"unexpected required check results: {required_checks}",
    )
    plan_digest = canonical_digest(plan)
    require(
        verification["extensions"]["org.idkmesh.evaluator_plan.digest"] == plan_digest,
        "VerificationResult did not preserve exact EvaluatorPlan digest",
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
            "plan_digest": plan_digest,
            "backend": plan["backend"]["type"],
            "verifier_adapter_version": plan["verifier"]["adapter_version"],
            "required_log_types": plan["backend"]["required_log_types"],
            "verification_result_id": verification["id"],
            "verification_result_digest": canonical_digest(verification),
            "status": verification["status"],
            "required_checks": required_checks,
            "recommendation": verification["decision_support"]["recommendation"],
            "independent_from_worker": verification["independence"]["independent_from_worker"],
        },
        "canonical_patch_negative_matrix_passed": True,
        "candidate_code_executed_by_verifier": False,
        "human_integration_decision_required": True,
    }
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
