#!/usr/bin/env python3
"""Calibrate successor-v2 Task 003 against exact frozen source.

Task 003 requires the branch convergence auditor to fail closed when a branch's
current head SHA was not observed. Historical merged-PR metadata must not by
itself make such a branch cleanup-eligible.

This calibration creates two candidates against source
``a69aa0ae1ae4862e507511cbd9ad854237d0ad32``:

1. ``straightforward`` requires a non-null observed ``head_sha`` before an
   exact merged-PR head can match; and
2. ``inert-decoy`` adds the expected lexical marker without changing the
   vulnerable matching condition.

The canonical EvaluatorPlan v0.4 path verifies patch metadata only. A separate
behavioral matrix imports the modified frozen-source auditor and exercises
missing, exact, and moved current-head states.

Calibration candidates are not scored benchmark outcomes and have no
repository integration authority.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402

SOURCE_SHA = "a69aa0ae1ae4862e507511cbd9ad854237d0ad32"
TASK_ID = "benchmark/phase-b2-v2/003-branch-unobserved-head"
TARGET_REL = "tools/branch_convergence_audit.py"
WORK_UNIT_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/work-units/"
    "task-003-branch-unobserved-head.work-unit.json"
)
PLAN_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/evaluators/"
    "task-003-branch-unobserved-head.evaluator-plan.json"
)
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
OLD_LINE = (
    "            pr for pr in merged_prs if head_sha is None or pr.head_sha == head_sha"
)
NEW_LINE = (
    "            pr for pr in merged_prs if head_sha is not None and pr.head_sha == head_sha"
)
DECOY_BLOCK = r'''

# Calibration near-miss only: this lexical marker does not enforce the guard.
_TASK003_UNOBSERVED_HEAD_DECOY = "head_sha is not None"
'''
TOOL_VERSION = "0.1"


class CalibrationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CalibrationError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalibrationError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env={
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONUNBUFFERED": "1",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise CalibrationError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def ensure_output_root(raw: str) -> Path:
    output = (ROOT / raw).resolve()
    try:
        relative = output.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise CalibrationError("output root escapes evaluator repository") from exc
    require(
        bool(relative.parts) and relative.parts[0] == "results",
        "output root must live under results/",
    )
    return output


def verify_scaffold_control_plane() -> None:
    cohort = load_json(COHORT_PATH)
    require(cohort.get("id") == "benchmark/phase-b2-successor-v2", "successor cohort id drift")
    require(cohort.get("stage") == "scaffold", "successor cohort was frozen during calibration")
    require("definition_digest" not in cohort, "successor scaffold unexpectedly has definition_digest")
    extension = cohort.get("extensions", {}).get("org.idkmesh.phase_b2_v2", {})
    require(extension.get("freeze_ready") is False, "successor scaffold unexpectedly reports freeze_ready")
    require(TASK_ID in extension.get("calibration_pending_task_ids", []), "Task 003 is not pending calibration")
    task = next((item for item in cohort.get("tasks", []) if item.get("id") == TASK_ID), None)
    require(isinstance(task, dict), "Task 003 missing from successor scaffold")
    require(task.get("source", {}).get("revision") == SOURCE_SHA, "Task 003 source revision drift")
    require(task.get("evidence") == {"status": "pending", "attempts": []}, "Task 003 already has outcome evidence")
    require(task.get("negative_case", {}).get("evidence_status") == "pending", "Task 003 negative evidence is not pending")


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def apply_transform(source: Path, transform: str) -> None:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require(text.count(OLD_LINE) == 1, "frozen source merged-PR matching condition drift")

    if transform == "straightforward":
        text = text.replace(OLD_LINE, NEW_LINE, 1)
    elif transform == "decoy":
        require(DECOY_BLOCK.strip() not in text, "decoy marker unexpectedly already present")
        text = text + DECOY_BLOCK
    else:
        raise CalibrationError(f"unsupported transform: {transform}")

    target.write_text(text, encoding="utf-8")


def load_candidate_module(source: Path, tag: str) -> Any:
    module_path = source / TARGET_REL
    module_name = f"idkmesh_task003_calibration_{tag.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    require(spec is not None and spec.loader is not None, "could not create module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def decision_snapshot(decision: Any) -> dict[str, Any]:
    return {
        "state": decision.state,
        "cleanup_eligible": decision.cleanup_eligible,
        "direct_merge_allowed": decision.direct_merge_allowed,
        "head_sha": decision.head_sha,
        "pull_requests": list(decision.pull_requests),
    }


def run_behavioral_matrix(source: Path, transform: str) -> dict[str, Any]:
    module = load_candidate_module(source, transform)
    comparison = module.Comparison(status="diverged", ahead_by=1, behind_by=1)
    merged_pr = module.PullRequestRef(
        number=4242,
        state="closed",
        merged=True,
        draft=False,
        head_sha="reviewed-head-sha",
        base_ref="main",
        updated_at=None,
    )

    missing = module.classify_branch(
        branch="feature/reused-after-merge",
        default_branch="main",
        comparison=comparison,
        prs=[merged_pr],
        head_sha=None,
    )
    exact = module.classify_branch(
        branch="feature/reused-after-merge",
        default_branch="main",
        comparison=comparison,
        prs=[merged_pr],
        head_sha="reviewed-head-sha",
    )
    moved = module.classify_branch(
        branch="feature/reused-after-merge",
        default_branch="main",
        comparison=comparison,
        prs=[merged_pr],
        head_sha="new-unreviewed-head-sha",
    )

    missing_snapshot = decision_snapshot(missing)
    exact_snapshot = decision_snapshot(exact)
    moved_snapshot = decision_snapshot(moved)

    safe = (
        missing_snapshot["state"] == "post-merge-branch-moved"
        and missing_snapshot["cleanup_eligible"] is False
        and exact_snapshot["state"] == "integrated-via-pr"
        and exact_snapshot["cleanup_eligible"] is True
        and moved_snapshot["state"] == "post-merge-branch-moved"
        and moved_snapshot["cleanup_eligible"] is False
        and all(
            item["direct_merge_allowed"] is False
            for item in (missing_snapshot, exact_snapshot, moved_snapshot)
        )
    )
    vulnerable = (
        missing_snapshot["state"] == "integrated-via-pr"
        and missing_snapshot["cleanup_eligible"] is True
        and exact_snapshot["state"] == "integrated-via-pr"
        and moved_snapshot["state"] == "post-merge-branch-moved"
    )

    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate": transform,
        "missing_current_head": missing_snapshot,
        "exact_current_head": exact_snapshot,
        "moved_current_head": moved_snapshot,
        "safe_unobserved_head_matrix_passed": safe,
        "vulnerable_missing_head_inherits_merge_history": vulnerable,
    }


def build_result_manifest(
    *,
    work_unit: dict[str, Any],
    candidate_id: str,
    patch_bytes: bytes,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    started_at: str,
    finished_at: str,
    elapsed: float,
    objective_satisfied: bool,
) -> dict[str, Any]:
    required_validator_ids = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    worker_config = {
        "tool_version": TOOL_VERSION,
        "candidate_id": candidate_id,
        "source_revision": SOURCE_SHA,
        "objective_satisfied": objective_satisfied,
    }
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/calibration/{candidate_id}",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": f"idkmesh-task003-calibration-{candidate_id}",
            "type": "system",
            "adapter": f"task003-{candidate_id}-calibration",
            "adapter_version": TOOL_VERSION,
        },
        "status": "succeeded",
        "started_at": started_at,
        "finished_at": finished_at,
        "produced_artifacts": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "locator": "candidate.patch",
                "digest": sha256_bytes(patch_bytes),
                "media_type": "text/x-diff",
                "description": "Task 003 post-definition evaluator-calibration candidate patch.",
            }
        ],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {
            "objective_satisfied": 1 if objective_satisfied else 0,
            "changed_path_count": 1,
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": "Task 003 calibration candidate; worker success is not acceptance.",
            "claims": [
                f"objective_satisfied={str(objective_satisfied).lower()}",
                "Canonical v0.4 verification and separate behavioral checks decide calibration evidence.",
            ],
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_SHA,
            "worker_config_digest": canonical_digest(worker_config),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {
                    "task003-branch-unobserved-head-calibration": TOOL_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids,
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Evaluator calibration only; not a scored benchmark outcome or integration decision.",
        },
        "extensions": {
            "org.idkmesh.calibration": True,
            "org.idkmesh.objective_satisfied": objective_satisfied,
            "org.idkmesh.authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        },
    }
    local_verifier.validate_schema(
        result,
        local_verifier.RESULT_MANIFEST_SCHEMA,
        f"{candidate_id} ResultManifest",
    )
    return result


def materialize_candidate(
    *,
    source: Path,
    output_root: Path,
    candidate_id: str,
    transform: str,
    objective_satisfied: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    reset_source(source)
    started_at = utc_now()
    started = time.monotonic()
    apply_transform(source, transform)

    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"{candidate_id} is not valid Python: {compile_proc.stderr}")

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"{candidate_id} changed unexpected paths: {changed}")
    patch_text = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout
    patch_bytes = patch_text.encode("utf-8")
    require(bool(patch_bytes), f"{candidate_id} produced an empty patch")

    behavior = run_behavioral_matrix(source, transform)
    if objective_satisfied:
        require(
            behavior["safe_unobserved_head_matrix_passed"] is True,
            "straightforward candidate failed branch-head behavioral matrix",
        )
    else:
        require(
            behavior["vulnerable_missing_head_inherits_merge_history"] is True,
            "decoy unexpectedly fixed the missing-head behavior",
        )

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"safe_unobserved_head_matrix_passed={str(behavior['safe_unobserved_head_matrix_passed']).lower()}\n"
        f"vulnerable_missing_head_inherits_merge_history={str(behavior['vulnerable_missing_head_inherits_merge_history']).lower()}\n"
    ).encode("utf-8")
    stderr_bytes = compile_proc.stderr.encode("utf-8")

    candidate_root = output_root / candidate_id
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True)
    (candidate_root / "candidate.patch").write_bytes(patch_bytes)
    (candidate_root / "stdout.txt").write_bytes(stdout_bytes)
    (candidate_root / "stderr.txt").write_bytes(stderr_bytes)
    write_json(candidate_root / "behavioral-evidence.json", behavior)

    work_unit = load_json(WORK_UNIT_PATH)
    result = build_result_manifest(
        work_unit=work_unit,
        candidate_id=candidate_id,
        patch_bytes=patch_bytes,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        started_at=started_at,
        finished_at=finished_at,
        elapsed=elapsed,
        objective_satisfied=objective_satisfied,
    )
    result_path = candidate_root / "result-manifest.json"
    write_json(result_path, result)

    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH,
        result_manifest_path=result_path,
        candidate_root=candidate_root,
        plan_path=PLAN_PATH,
    )
    write_json(candidate_root / "verification-result.json", verification)
    reset_source(source)
    return result, verification, behavior, candidate_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/verification/phase-b2-v2-task003-calibration",
        help="Evaluator-repository-relative output root under results/.",
    )
    args = parser.parse_args()

    verify_scaffold_control_plane()
    source = args.source.resolve()
    require(source.is_dir(), f"source checkout does not exist: {source}")
    reset_source(source)
    output_root = ensure_output_root(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    work_unit = load_json(WORK_UNIT_PATH)
    require(
        canonical_digest(work_unit)
        == "sha256:a48ec044dea90201c2bd43505e54c94d9bb9830dad29b6397a943e19f4f3cc75",
        "Task 003 WorkUnit digest drift",
    )
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 003 plan is not EvaluatorPlan v0.4")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "Task 003 verifier version drift")
    require(plan["execution_mode"] == "metadata_only", "Task 003 plan is not metadata-only")
    require(
        plan["backend"]["required_added_substrings"] == ["head_sha is not None"],
        "Task 003 added semantic drift",
    )
    require(
        plan["backend"]["required_removed_substrings"]
        == ["head_sha is None or pr.head_sha == head_sha"],
        "Task 003 removed semantic drift",
    )
    plan_digest = canonical_digest(plan)
    require(
        plan_digest
        == "sha256:8e4dc161a2f1a4cb3009274c0e786047c77b15f5f9c59a2eb8a936a9b9cf8993",
        "Task 003 EvaluatorPlan digest drift",
    )

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="straightforward",
        transform="straightforward",
        objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward Task 003 candidate")
    require(
        straight_verification["decision_support"]["recommendation"] == "accept_candidate",
        "v0.4 did not support straightforward Task 003 candidate",
    )
    require(straight_verification["metrics"].get("matched_substring_count") == 1, "straightforward did not satisfy required added evidence")
    require(straight_verification["metrics"].get("matched_removed_substring_count") == 1, "straightforward did not satisfy required removal evidence")

    decoy_result, decoy_verification, decoy_behavior, decoy_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="inert-decoy",
        transform="decoy",
        objective_satisfied=False,
    )
    require(decoy_verification["status"] == "failed", "v0.4 failed to reject Task 003 inert decoy")
    require(
        decoy_verification["decision_support"]["recommendation"] == "reject_candidate",
        "v0.4 did not reject Task 003 inert decoy",
    )
    require(decoy_verification["metrics"].get("matched_substring_count") == 1, "decoy did not exercise the lexical added near-miss")
    require(decoy_verification["metrics"].get("matched_removed_substring_count") == 0, "decoy unexpectedly removed vulnerable merged-PR condition")

    for verification in (straight_verification, decoy_verification):
        require(verification["verifier"]["adapter_version"] == "0.3.0", "VerificationResult verifier version drift")
        require(
            verification["provenance"]["verifier_config_digest"] == plan_digest,
            "VerificationResult lost exact Task 003 EvaluatorPlan digest",
        )
        require(
            verification.get("extensions", {}).get("org.idkmesh.evaluator_plan.execution_mode") == "metadata_only",
            "VerificationResult lost metadata-only EvaluatorPlan provenance",
        )
        require(
            verification.get("extensions", {}).get("org.idkmesh.local_verifier.semantic_match_mode")
            == "added_and_removed_line_substring_all",
            "VerificationResult lost canonical v0.4 transition mode",
        )

    summary = {
        "schema_version": "0.1",
        "cohort_id": "benchmark/phase-b2-successor-v2",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "evaluator_plan_id": plan["id"],
        "evaluator_plan_digest": plan_digest,
        "verifier_adapter_version": "0.3.0",
        "straightforward": {
            "result_manifest_digest": canonical_digest(straight_result),
            "verification_result_digest": canonical_digest(straight_verification),
            "verification_status": straight_verification["status"],
            "recommendation": straight_verification["decision_support"]["recommendation"],
            "safe_unobserved_head_matrix_passed": straight_behavior["safe_unobserved_head_matrix_passed"],
            "matched_added_substrings": straight_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": straight_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "vulnerable_missing_head_inherits_merge_history": decoy_behavior[
                "vulnerable_missing_head_inherits_merge_history"
            ],
            "matched_added_substrings": decoy_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": decoy_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": decoy_root.relative_to(ROOT).as_posix(),
        },
        "calibration_passed": True,
        "calibration_candidates_are_benchmark_outcomes": False,
        "metadata_only_verifier_executes_candidate_code": False,
        "behavioral_execution_is_separate_evidence_channel": True,
        "automatic_candidate_selection": False,
        "canonical_state_write_authority": False,
        "merge_authority": False,
    }
    write_json(output_root / "calibration-summary.json", summary)
    reset_source(source)

    print("IDKMESH_PHASE_B2_TASK003_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_PHASE_B2_TASK003_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
