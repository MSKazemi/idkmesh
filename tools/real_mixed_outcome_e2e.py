#!/usr/bin/env python3
"""Prove one real node failure does not corrupt a successful peer.

The same immutable WorkUnit is invoked twice with the exact accepted node SHA.
Attempt 001 runs normally. Before attempt 002, the local image tag is removed,
so the real node fails during immutable-image resolution before producing a
ResultManifest. Only after observing that real failure is the replay config
constructed; the existing `fixture-failure` adapter represents the already-
observed external failure while attempt 001 is consumed as a real result bundle.

This tests failure isolation and replay semantics without adding a new failure
protocol or granting coordinator execution/merge authority.
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
IMAGE_TAG = "python:3.12-alpine"
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


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def derive_plan(root: Path, work_unit: dict[str, Any]) -> dict[str, Any]:
    template = load_json(root / PLAN_TEMPLATE)
    require(template.get("schema_version") == "0.2", "EvaluatorPlan template is not v0.2")
    require(template.get("backend", {}).get("type") == "unified_diff", "plan is not unified_diff")
    require(template.get("execution_mode") == "metadata_only", "plan is not metadata-only")

    plan = copy.deepcopy(template)
    plan["id"] = f"verification/real-mixed-outcome-{CANDIDATE_SHA[:7]}-plan"
    plan["binding"] = {
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
    }
    plan["candidate_artifact_id"] = "candidate-patch"
    plan["required_validator_ids"] = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    plan["backend"]["max_candidate_bytes"] = 1_000_000
    plan["backend"]["max_log_bytes"] = 262_144
    plan["backend"]["required_added_text"] = [EXPECTED_ADDED_TEXT]
    plan.setdefault("extensions", {})["org.idkmesh.real_mixed_outcome"] = {
        "candidate_sha": CANDIDATE_SHA,
        "purpose": "real successful peer plus real pre-ResultManifest worker failure",
    }
    return plan


def repo_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/orchestration/real-mixed-outcome-520ad2c",
    )
    args = parser.parse_args()

    evaluator_root = Path(__file__).resolve().parents[1]
    candidate = args.candidate.resolve()
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=candidate).stdout.strip()
    require(actual_sha == CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")

    output_root = (evaluator_root / args.output_root).resolve()
    try:
        relative = output_root.relative_to(evaluator_root)
    except ValueError as exc:
        raise E2EError("output root escapes evaluator repository") from exc
    require(relative.parts and relative.parts[0] == "results", "output must stay under results/")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    fixture = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"
    work_unit = load_json(fixture)
    work_unit_digest = canonical_digest(work_unit)
    require(work_unit["provenance"]["source_revision"] == SOURCE_SHA, "source revision drift")

    work_unit_path = output_root / "work-unit.json"
    plan_path = output_root / "evaluator-plan.json"
    config_path = output_root / "config.json"
    run_path = output_root / "run.json"
    report_path = output_root / "evidence-report.json"
    report_md_path = output_root / "evidence-report.md"
    evidence_path = output_root / "e2e-evidence.json"
    failure_record_path = output_root / "attempt-002-observed-failure.json"
    write_json(work_unit_path, work_unit)

    with tempfile.TemporaryDirectory(prefix="idkmesh-real-mixed-") as raw_temp:
        temp_root = Path(raw_temp)

        success_bundle = output_root / "attempt-001"
        success_proc = run(
            [
                sys.executable,
                "-m",
                "idkmesh_node",
                "run",
                str(fixture),
                "--output",
                str(success_bundle),
            ],
            cwd=candidate,
            env=candidate_env(candidate, temp_root / "home-success"),
            check=False,
        )
        require(success_proc.returncode == 0, f"successful peer failed:\n{success_proc.stderr}")
        success_result_path = success_bundle / "result-manifest.json"
        success_result = load_json(success_result_path)
        require(success_result["status"] == "succeeded", "peer ResultManifest is not succeeded")
        require(
            success_result["provenance"]["work_unit_digest"] == work_unit_digest,
            "successful peer WorkUnit binding drift",
        )

        # Produce a genuine second-worker failure from the same WorkUnit by
        # removing only the local tag that the node is required to resolve.
        remove = run(["docker", "image", "rm", "-f", IMAGE_TAG], cwd=evaluator_root, check=False)
        require(remove.returncode == 0, f"could not remove image tag for failure experiment: {remove.stderr}")

        failed_bundle = output_root / "attempt-002"
        try:
            failed_proc = run(
                [
                    sys.executable,
                    "-m",
                    "idkmesh_node",
                    "run",
                    str(fixture),
                    "--output",
                    str(failed_bundle),
                ],
                cwd=candidate,
                env=candidate_env(candidate, temp_root / "home-failure"),
                check=False,
            )
        finally:
            # Restore the controlled host for subsequent checks/jobs.
            run(["docker", "pull", IMAGE_TAG], cwd=evaluator_root, check=True)

    require(failed_proc.returncode == 2, f"expected pre-ResultManifest worker failure, got {failed_proc.returncode}")
    require(
        not (failed_bundle / "result-manifest.json").exists(),
        "failed worker unexpectedly produced a ResultManifest",
    )
    require(failed_proc.stderr.strip(), "real worker failure did not produce stderr evidence")

    failure_record = {
        "schema_version": "0.1",
        "kind": "idkmesh-observed-worker-failure",
        "attempt_id": "attempt-002",
        "worker_adapter": "idkmesh-node",
        "candidate_sha": CANDIDATE_SHA,
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "work_unit_digest": work_unit_digest,
        "source_revision": SOURCE_SHA,
        "exit_code": failed_proc.returncode,
        "stdout_sha256": sha256_text(failed_proc.stdout),
        "stderr_sha256": sha256_text(failed_proc.stderr),
        "stderr": failed_proc.stderr.strip(),
        "result_manifest_created": False,
        "failure_phase": "worker_pre_result_manifest",
    }
    write_json(failure_record_path, failure_record)
    failure_digest = canonical_digest(failure_record)

    # Control is constructed only after the worker outcomes are observed.
    plan = derive_plan(evaluator_root, work_unit)
    write_json(plan_path, plan)

    replay_failure_message = (
        "observed real idkmesh-node pre-ResultManifest failure "
        f"{failure_digest}; exit_code={failed_proc.returncode}; "
        f"stderr_sha256={failure_record['stderr_sha256']}"
    )
    config = {
        "schema_version": "0.1",
        "run_id": f"real-mixed-outcome-{CANDIDATE_SHA[:7]}",
        "work_unit": repo_relative(evaluator_root, work_unit_path),
        "evaluator_plan": repo_relative(evaluator_root, plan_path),
        "attempts": [
            {
                "attempt_id": "attempt-001",
                "worker_adapter": "result-bundle",
                "result_manifest": repo_relative(evaluator_root, success_result_path),
                "candidate_root": repo_relative(evaluator_root, success_bundle),
            },
            {
                "attempt_id": "attempt-002",
                "worker_adapter": "fixture-failure",
                "failure": replay_failure_message,
            },
        ],
    }
    write_json(config_path, config)

    run([sys.executable, "experiments/two_attempt_orchestrator.py", "self-test"], cwd=evaluator_root)
    run([sys.executable, "experiments/run_evidence_report.py", "self-test"], cwd=evaluator_root)

    run(
        [
            sys.executable,
            "experiments/run_evidence_report.py",
            "generate",
            "--config",
            repo_relative(evaluator_root, config_path),
            "--run-output",
            repo_relative(evaluator_root, run_path),
            "--report-json",
            repo_relative(evaluator_root, report_path),
            "--report-markdown",
            repo_relative(evaluator_root, report_md_path),
        ],
        cwd=evaluator_root,
    )
    replay_proc = run(
        [
            sys.executable,
            "experiments/run_evidence_report.py",
            "replay-check",
            "--config",
            repo_relative(evaluator_root, config_path),
            "--run-record",
            repo_relative(evaluator_root, run_path),
        ],
        cwd=evaluator_root,
    )
    replay = json.loads(replay_proc.stdout)
    require(replay.get("match") is True, "mixed-outcome run did not replay exactly")

    run_record = load_json(run_path)
    report = load_json(report_path)
    require(run_record["run_state"] == "completed_with_failures", "mixed run lost failure state")
    require(run_record["summary"]["attempt_count"] == 2, "mixed run lost an attempt")
    require(run_record["summary"]["candidates_supported"] == 1, "successful peer was not supported")
    require(run_record["summary"]["candidates_rejected"] == 0, "mixed run invented a rejection")
    require(run_record["summary"]["control_failures"] == 1, "real failure was not represented")

    attempts = {item["attempt_id"]: item for item in run_record["attempts"]}
    good = attempts["attempt-001"]
    failed = attempts["attempt-002"]
    require(good["state"] == "verified", "successful peer did not reach verification")
    require(good["verification"]["recommendation"] == "accept_candidate", "successful peer unsupported")
    require(failed["state"] == "worker_error", "observed worker failure lost worker_error state")
    require(failed["result_manifest"] is None, "pre-ResultManifest failure invented worker output")
    require(failed["verification"] is None, "pre-ResultManifest failure invented verification")
    require(failure_digest in failed["error"], "source run lost observed failure-record digest")

    report_attempts = {item["attempt_id"]: item for item in report["attempts"]}
    require(report_attempts["attempt-001"]["evidence_state"] == "supported", "report lost supported peer")
    require(report_attempts["attempt-002"]["evidence_state"] == "worker_error", "report lost worker error")
    require(report["summary"]["supported"] == 1, "report lost supported peer count")
    require(report["summary"]["control_errors"] == 1, "report lost failure count")
    require(report["summary"]["control_failure_present"] is True, "report hid failure presence")
    require(
        report["human_decision"] == {
            "status": "pending",
            "selected_attempt_id": None,
            "integration_authority": "external_human_or_governance",
        },
        "report selected a candidate after peer failure",
    )

    evidence = {
        "schema_version": "0.1",
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": work_unit_digest,
        "evaluator_plan_digest": canonical_digest(plan),
        "successful_peer": {
            "result_manifest_id": success_result["id"],
            "result_manifest_digest": canonical_digest(success_result),
            "patch_digest": success_result["produced_artifacts"][0]["digest"],
            "run_state": good["state"],
            "recommendation": good["verification"]["recommendation"],
        },
        "failed_peer": {
            "observed_failure_digest": failure_digest,
            "exit_code": failed_proc.returncode,
            "stderr_sha256": failure_record["stderr_sha256"],
            "result_manifest_created": False,
            "run_state": failed["state"],
            "report_evidence_state": report_attempts["attempt-002"]["evidence_state"],
        },
        "run_digest": canonical_digest(run_record),
        "report_digest": canonical_digest(report),
        "replay": replay,
        "summary": copy.deepcopy(report["summary"]),
        "human_decision": copy.deepcopy(report["human_decision"]),
        "authority": copy.deepcopy(report["authority"]),
        "failure_observed_before_replay_config_construction": True,
        "worker_execution_inside_orchestrator": False,
        "candidate_code_executed_by_verifier": False,
    }
    write_json(evidence_path, evidence)
    print("IDKMESH_REAL_MIXED_OUTCOME_E2E_BEGIN")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("IDKMESH_REAL_MIXED_OUTCOME_E2E_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (E2EError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
