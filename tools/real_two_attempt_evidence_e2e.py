#!/usr/bin/env python3
"""Compose two real frozen-node attempts into the canonical run-evidence view.

This is an evidence-producing integration experiment. It reuses the exact-SHA
single-attempt producer/verifier bridge in ``tools/real_node_verifier_e2e.py``
rather than introducing a second worker or verifier protocol.

The normal scenario executes and independently verifies two isolated attempts
from the same WorkUnit/source revision. A second scenario preserves one of
those verified attempts while a peer invocation of the same real node fails
before producing a ResultManifest. Both scenarios are rendered through the
merged non-selecting Run Evidence Report layer.

No path in this tool can select, approve, merge, push, or modify canonical
repository state. Generated artifacts stay under the ignored ``results/`` tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

EVALUATOR_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = EVALUATOR_ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from local_verifier import semantic_signature  # noqa: E402
from run_evidence_report import build_report, render_markdown, validate_report  # noqa: E402

CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"
SOURCE_SHA = "b1397a9be91da6570e8ae370de4fa9f4bc44df5c"
ORCHESTRATOR_VERSION = "real-two-attempt-e2e/0.1"
SINGLE_ATTEMPT_TOOL = "tools/real_node_verifier_e2e.py"
WORK_UNIT_FIXTURE = "node/examples/work-unit.canonical-smoke.json"


class RealRunError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RealRunError(message)


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
        raise RealRunError(f"expected JSON object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


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
        raise RealRunError(
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


def normalize_output_root(raw: str) -> tuple[Path, str]:
    path = (EVALUATOR_ROOT / raw).resolve()
    try:
        relative = path.relative_to(EVALUATOR_ROOT)
    except ValueError as exc:
        raise RealRunError("output root escapes evaluator repository") from exc
    require(bool(relative.parts) and relative.parts[0] == "results", "output root must stay under results/")
    return path, relative.as_posix()


def result_record(worker_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": worker_result["id"],
        "attempt": worker_result["attempt"],
        "worker_id": worker_result["worker"]["id"],
        "worker_status": worker_result["status"],
        "digest": canonical_digest(worker_result),
    }


def verification_record(verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": verification["id"],
        "verifier_id": verification["verifier"]["id"],
        "status": verification["status"],
        "recommendation": verification["decision_support"]["recommendation"],
        "checks": [
            {
                "id": item["id"],
                "status": item["status"],
                "required": item["required"],
            }
            for item in verification["checks"]
        ],
        "semantic_digest": canonical_digest(semantic_signature(verification)),
        "work_unit_digest": verification["provenance"]["work_unit_digest"],
        "result_manifest_digest": verification["provenance"]["result_manifest_digest"],
    }


def execute_verified_attempt(
    *,
    candidate: Path,
    output_root_relative: str,
    attempt_id: str,
    order: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    proc = run(
        [
            sys.executable,
            SINGLE_ATTEMPT_TOOL,
            "--candidate",
            str(candidate),
            "--output-root",
            output_root_relative,
        ],
        cwd=EVALUATOR_ROOT,
    )
    require("IDKMESH_REAL_NODE_VERIFIER_E2E_BEGIN" in proc.stdout, "single-attempt E2E evidence marker missing")

    root = EVALUATOR_ROOT / output_root_relative
    worker_result = load_json(root / "candidate-bundle" / "result-manifest.json")
    verification = load_json(root / "verification-result.json")
    plan = load_json(root / "evaluator-plan.json")
    work_unit = load_json(root / "work-unit.json")

    require(worker_result["status"] == "succeeded", f"{attempt_id} worker did not succeed")
    require(verification["status"] == "passed", f"{attempt_id} verifier did not pass")
    require(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        f"{attempt_id} verifier did not support candidate",
    )
    require(verification["independence"]["independent_from_worker"] is True, f"{attempt_id} lost verifier independence")

    record = {
        "attempt_id": attempt_id,
        "order": order,
        "worker_adapter": "exact-sha-canonical-node",
        "state": "verified",
        "error": None,
        "candidate_root": (root / "candidate-bundle").relative_to(EVALUATOR_ROOT).as_posix(),
        "result_manifest": result_record(worker_result),
        "verification": verification_record(verification),
    }
    return record, work_unit, plan


def run_record(
    *,
    run_id: str,
    work_unit: dict[str, Any],
    plan: dict[str, Any],
    attempts: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    supported = sum(
        item.get("verification", {}).get("recommendation") == "accept_candidate"
        for item in attempts
        if item.get("verification") is not None
    )
    rejected = sum(
        item.get("verification", {}).get("recommendation") == "reject_candidate"
        for item in attempts
        if item.get("verification") is not None
    )
    control_failures = sum(
        item["state"] in {"worker_error", "result_manifest_error", "verification_error"}
        for item in attempts
    )
    control = {
        "schema_version": "0.1",
        "mode": mode,
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "evaluator_plan_digest": canonical_digest(plan),
        "attempt_order": [item["attempt_id"] for item in attempts],
        "worker_adapters": [item["worker_adapter"] for item in attempts],
    }
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-two-attempt-run",
        "run_id": run_id,
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "config_digest": canonical_digest(control),
        "work_unit": {
            "id": work_unit["id"],
            "version": work_unit["version"],
            "digest": canonical_digest(work_unit),
        },
        # Legacy report field name; this digest is the evaluator-owned plan used
        # for every verified attempt in this real run.
        "verifier_policy_digest": canonical_digest(plan),
        "attempt_order": [item["attempt_id"] for item in attempts],
        "attempts": attempts,
        "summary": {
            "attempt_count": len(attempts),
            "control_failures": control_failures,
            "candidates_supported": supported,
            "candidates_rejected": rejected,
        },
        "run_state": "completed_with_failures" if control_failures else "completed",
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }


def semantic_outcome(record: dict[str, Any], attempt_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return replay metadata that excludes timestamps/resource noise."""

    artifacts_by_attempt = {item["attempt_id"]: item for item in attempt_artifacts}
    attempts: list[dict[str, Any]] = []
    for attempt in record["attempts"]:
        verification = attempt.get("verification")
        stable = {
            "attempt_id": attempt["attempt_id"],
            "worker_adapter": attempt["worker_adapter"],
            "state": attempt["state"],
            "recommendation": None if verification is None else verification["recommendation"],
            "required_checks": [] if verification is None else [
                {"id": check["id"], "status": check["status"]}
                for check in verification["checks"]
                if check["required"]
            ],
        }
        artifact = artifacts_by_attempt.get(attempt["attempt_id"])
        if artifact is not None:
            stable["candidate_patch_digest"] = artifact["candidate_patch_digest"]
        attempts.append(stable)
    return {
        "schema_version": "0.1",
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": record["work_unit"]["digest"],
        "evaluator_plan_digest": record["verifier_policy_digest"],
        "attempts": attempts,
        "human_integration_decision_required": True,
    }


def invoke_expected_worker_failure(candidate: Path, blocker: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the real node with a deliberately invalid output target.

    The output path is a regular file, so the worker must fail before it can
    produce a ResultManifest. The WorkUnit/source are unchanged.
    """

    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("intentional output-path blocker\n", encoding="utf-8")
    source_fixture = candidate / WORK_UNIT_FIXTURE
    with tempfile.TemporaryDirectory(prefix="idkmesh-real-two-attempt-failure-") as raw:
        return run(
            [
                sys.executable,
                "-m",
                "idkmesh_node",
                "run",
                str(source_fixture),
                "--output",
                str(blocker),
            ],
            cwd=candidate,
            env=candidate_env(candidate, Path(raw) / "candidate-home"),
            check=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/orchestration/real-two-attempt-evidence",
        help="Evaluator-repository-relative path under results/.",
    )
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=candidate).stdout.strip()
    require(actual_sha == CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")

    output_root, output_relative = normalize_output_root(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    attempts: list[dict[str, Any]] = []
    artifact_summaries: list[dict[str, Any]] = []
    reference_work_unit: dict[str, Any] | None = None
    reference_plan: dict[str, Any] | None = None

    for order, attempt_id in enumerate(("attempt-001", "attempt-002"), start=1):
        attempt_relative = f"{output_relative}/{attempt_id}"
        record, work_unit, plan = execute_verified_attempt(
            candidate=candidate,
            output_root_relative=attempt_relative,
            attempt_id=attempt_id,
            order=order,
        )
        if reference_work_unit is None:
            reference_work_unit = work_unit
            reference_plan = plan
        else:
            require(canonical_digest(work_unit) == canonical_digest(reference_work_unit), "attempt WorkUnit drift")
            require(canonical_digest(plan) == canonical_digest(reference_plan), "attempt EvaluatorPlan drift")
        attempts.append(record)
        worker_result = load_json(EVALUATOR_ROOT / attempt_relative / "candidate-bundle" / "result-manifest.json")
        patch_artifacts = [item for item in worker_result["produced_artifacts"] if item["type"] == "patch"]
        require(len(patch_artifacts) == 1, f"{attempt_id} did not produce exactly one patch")
        artifact_summaries.append(
            {
                "attempt_id": attempt_id,
                "candidate_patch_digest": patch_artifacts[0]["digest"],
            }
        )

    require(reference_work_unit is not None and reference_plan is not None, "no real attempts executed")
    require(
        artifact_summaries[0]["candidate_patch_digest"] == artifact_summaries[1]["candidate_patch_digest"],
        "deterministic smoke attempts produced different candidate patches",
    )

    normal_run = run_record(
        run_id="real-node-two-attempt-520ad2c",
        work_unit=reference_work_unit,
        plan=reference_plan,
        attempts=attempts,
        mode="two-real-verified-attempts",
    )
    normal_report = build_report(normal_run)
    validate_report(normal_report, normal_run)
    require(normal_report["summary"]["supported"] == 2, "normal run did not preserve two supported attempts")
    require(normal_report["summary"]["control_errors"] == 0, "normal run has unexpected control errors")
    require(normal_report["human_decision"]["status"] == "pending", "report made a human decision")
    require(normal_report["human_decision"]["selected_attempt_id"] is None, "report selected a candidate")

    normal_run_path = output_root / "run.json"
    normal_report_path = output_root / "evidence-report.json"
    normal_markdown_path = output_root / "evidence-report.md"
    write_json(normal_run_path, normal_run)
    write_json(normal_report_path, normal_report)
    write_text(normal_markdown_path, render_markdown(normal_report))

    # Saved-run replay: rendering the exact saved evidence must be deterministic.
    saved_run = load_json(normal_run_path)
    replayed_report = build_report(saved_run)
    require(
        canonical_digest(replayed_report) == canonical_digest(normal_report),
        "saved real run did not replay to the same evidence report",
    )
    semantic = semantic_outcome(normal_run, artifact_summaries)

    # Separate two-attempt failure-isolation scenario: preserve one real verified
    # peer while a second invocation of the same worker fails before ResultManifest.
    blocker = output_root / "fault-isolation" / "blocked-output"
    failed_proc = invoke_expected_worker_failure(candidate, blocker)
    require(failed_proc.returncode != 0, "intentionally blocked worker unexpectedly succeeded")
    failure_text = (failed_proc.stderr.strip() or failed_proc.stdout.strip() or "worker failed as expected")[-4000:]
    failure_attempt = {
        "attempt_id": "attempt-002",
        "order": 2,
        "worker_adapter": "exact-sha-canonical-node",
        "state": "worker_error",
        "error": failure_text,
        "result_manifest": None,
        "verification": None,
    }
    surviving_attempt = dict(attempts[0])
    fault_run = run_record(
        run_id="real-node-two-attempt-fault-isolation-520ad2c",
        work_unit=reference_work_unit,
        plan=reference_plan,
        attempts=[surviving_attempt, failure_attempt],
        mode="verified-peer-plus-real-worker-error",
    )
    fault_report = build_report(fault_run)
    validate_report(fault_report, fault_run)
    require(fault_report["summary"]["supported"] == 1, "peer failure erased surviving verified evidence")
    require(fault_report["summary"]["control_errors"] == 1, "worker error was not preserved")
    require(fault_report["summary"]["control_failure_present"] is True, "control failure flag missing")
    require(fault_report["human_decision"]["selected_attempt_id"] is None, "fault report selected a candidate")
    blocker.unlink(missing_ok=True)

    write_json(output_root / "fault-isolation-run.json", fault_run)
    write_json(output_root / "fault-isolation-report.json", fault_report)
    write_text(output_root / "fault-isolation-report.md", render_markdown(fault_report))

    evidence = {
        "schema_version": "0.1",
        "kind": "idkmesh-real-two-attempt-e2e-evidence",
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": normal_run["work_unit"]["digest"],
        "evaluator_plan_digest": normal_run["verifier_policy_digest"],
        "normal_run": {
            "run_digest": canonical_digest(normal_run),
            "report_digest": canonical_digest(normal_report),
            "semantic_outcome_digest": canonical_digest(semantic),
            "attempt_count": 2,
            "supported": normal_report["summary"]["supported"],
            "control_errors": normal_report["summary"]["control_errors"],
            "candidate_patch_digest": artifact_summaries[0]["candidate_patch_digest"],
            "saved_run_report_replay_match": True,
        },
        "fault_isolation": {
            "run_digest": canonical_digest(fault_run),
            "report_digest": canonical_digest(fault_report),
            "supported": fault_report["summary"]["supported"],
            "control_errors": fault_report["summary"]["control_errors"],
            "failed_worker_exit_code": failed_proc.returncode,
            "surviving_peer_preserved": True,
        },
        "human_integration_decision_required": True,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    write_json(output_root / "e2e-evidence.json", evidence)
    print("IDKMESH_REAL_TWO_ATTEMPT_E2E_BEGIN")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("IDKMESH_REAL_TWO_ATTEMPT_E2E_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RealRunError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
