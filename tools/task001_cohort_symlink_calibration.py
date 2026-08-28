#!/usr/bin/env python3
"""Calibrate successor-v2 Task 001 against exact frozen source.

The original proxy did not encode whether ``is_symlink`` ran before or after
``resolve``. This tool strengthens the mutable pre-freeze proxy, evaluates a
correct ordering change and an inert ordering decoy through canonical
EvaluatorPlan v0.4, and separately exercises the path boundary in a disposable
checkout. Calibration candidates are not scored benchmark outcomes.
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
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402
from provenance_integrity import canonical_digest  # noqa: E402

SOURCE_SHA = "a69aa0ae1ae4862e507511cbd9ad854237d0ad32"
TASK_ID = "benchmark/phase-b2-v2/001-cohort-symlink-reference"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/work-units/task-001-cohort-symlink-reference.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-v2/evaluators/task-001-cohort-symlink-reference.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
EXPECTED_WORK_UNIT_DIGEST = "sha256:2e0b49e98e6626131c2b08916753b3b7f6ea7c25519cc9610f7212474d8712b3"
EXPECTED_PLAN_DIGEST = "sha256:b6e3b0bc2627b3600a7a91ec5bd647d800d612228acb7c721795dc2ab0c5ab5e"
TOOL_VERSION = "0.1"

OLD_PATH_LINE = "    path = (ROOT / Path(*posix.parts)).resolve()\n"
OLD_SYMLINK_LINE = '    require(not path.is_symlink(), f"{label}: symlink references are not allowed: {raw}")\n'
STRAIGHT_PATH_BLOCK = '''    unresolved = ROOT / Path(*posix.parts)
    require(not unresolved.is_symlink(), f"{label}: symlink references are not allowed: {raw}")
    path = unresolved.resolve()
'''
DECOY_PATH_BLOCK = '''    path = ROOT / Path(*posix.parts)
    path = path.resolve()
'''
DECOY_SYMLINK_LINE = '    require(not path.is_symlink(), f"{label}: direct symlink references are not allowed: {raw}")\n'


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


def run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
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
    require(bool(relative.parts) and relative.parts[0] == "results", "output root must live under results/")
    return output


def verify_scaffold_control_plane() -> None:
    cohort = load_json(COHORT_PATH)
    require(cohort.get("id") == "benchmark/phase-b2-successor-v2", "cohort id drift")
    require(cohort.get("stage") == "scaffold", "successor scaffold is no longer mutable")
    require("definition_digest" not in cohort, "scaffold unexpectedly has definition_digest")
    extension = cohort.get("extensions", {}).get("org.idkmesh.phase_b2_v2", {})
    pending = set(extension.get("calibration_pending_task_ids", []))
    completed = set(extension.get("calibration_completed", {}))
    require(extension.get("freeze_ready") is (len(pending) == 0), "freeze_ready disagrees with pending state")
    require(TASK_ID in pending | completed, "Task 001 is absent from calibration state")
    task = next((item for item in cohort.get("tasks", []) if item.get("id") == TASK_ID), None)
    require(isinstance(task, dict), "Task 001 missing from scaffold")
    require(task.get("source", {}).get("revision") == SOURCE_SHA, "Task 001 source drift")
    require(task.get("evidence") == {"status": "pending", "attempts": []}, "Task 001 has outcomes")
    require(task.get("negative_case", {}).get("evidence_status") == "pending", "negative evidence is not pending")


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source is dirty")


def apply_transform(source: Path, transform: str) -> None:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require(text.count(OLD_PATH_LINE) == 1, "frozen resolve line drift")
    require(text.count(OLD_SYMLINK_LINE) == 1, "frozen symlink guard drift")
    if transform == "straightforward":
        text = text.replace(OLD_PATH_LINE, STRAIGHT_PATH_BLOCK, 1)
        text = text.replace(OLD_SYMLINK_LINE, "", 1)
    elif transform == "decoy":
        text = text.replace(OLD_PATH_LINE, DECOY_PATH_BLOCK, 1)
        text = text.replace(OLD_SYMLINK_LINE, DECOY_SYMLINK_LINE, 1)
    else:
        raise CalibrationError(f"unsupported transform: {transform}")
    target.write_text(text, encoding="utf-8")


def load_target(source: Path, tag: str) -> ModuleType:
    module_name = f"task001_symlink_calibration_{tag}_{time.monotonic_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, source / TARGET_REL)
    require(spec is not None and spec.loader is not None, "cannot load benchmark cohort source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def observe_path(module: ModuleType, case_id: str, raw: str) -> dict[str, Any]:
    accepted = False
    resolved = None
    error = ""
    try:
        path = module.resolve_repo_file(raw, label="Task 001 calibration")
        accepted = True
        resolved = path.relative_to(module.ROOT).as_posix()
    except module.CohortError as exc:
        error = str(exc)
    return {"id": case_id, "raw": raw, "accepted": accepted, "resolved": resolved, "error": error}


def run_behavioral_matrix(source: Path, transform: str) -> dict[str, Any]:
    reset_source(source)
    apply_transform(source, transform)
    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"behavioral candidate is invalid Python: {compile_proc.stderr}")

    fixture_root = source / "results" / "task001-symlink-calibration"
    fixture_root.mkdir(parents=True)
    target = fixture_root / "cohort.json"
    target.write_text("{}\n", encoding="utf-8")
    link = fixture_root / "cohort-link.json"
    link.symlink_to(target.name)

    module = load_target(source, transform)
    target_rel = target.relative_to(source).as_posix()
    link_rel = link.relative_to(source).as_posix()
    checks = [
        observe_path(module, "ordinary-in-repository-file", target_rel),
        observe_path(module, "direct-in-repository-symlink", link_rel),
        observe_path(module, "parent-traversal", "../outside.json"),
        observe_path(module, "absolute-path", target.resolve().as_posix()),
        observe_path(module, "missing-file", "results/task001-symlink-calibration/missing.json"),
    ]
    by_id = {item["id"]: item for item in checks}
    normal_preserved = (
        by_id["ordinary-in-repository-file"]["accepted"] is True
        and by_id["ordinary-in-repository-file"]["resolved"] == target_rel
        and by_id["parent-traversal"]["accepted"] is False
        and by_id["absolute-path"]["accepted"] is False
        and by_id["missing-file"]["accepted"] is False
    )
    safe = normal_preserved and by_id["direct-in-repository-symlink"]["accepted"] is False
    vulnerable = normal_preserved and by_id["direct-in-repository-symlink"]["accepted"] is True
    reset_source(source)
    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate": transform,
        "checks": checks,
        "normal_boundary_behavior_preserved": normal_preserved,
        "safe_direct_symlink_rejection_passed": safe,
        "vulnerable_direct_symlink_accepted": vulnerable,
    }


def build_result_manifest(
    *, work_unit: dict[str, Any], candidate_id: str, patch_bytes: bytes,
    stdout_bytes: bytes, stderr_bytes: bytes, started_at: str,
    finished_at: str, elapsed: float, objective_satisfied: bool,
) -> dict[str, Any]:
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
            "id": f"idkmesh-task001-symlink-calibration-{candidate_id}",
            "type": "system",
            "adapter": f"task001-symlink-{candidate_id}-calibration",
            "adapter_version": TOOL_VERSION,
        },
        "status": "succeeded",
        "started_at": started_at,
        "finished_at": finished_at,
        "produced_artifacts": [{
            "id": "candidate-patch", "type": "patch", "locator": "candidate.patch",
            "digest": sha256_bytes(patch_bytes), "media_type": "text/x-diff",
            "description": "Task 001 post-definition evaluator-calibration candidate patch.",
        }],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {"objective_satisfied": 1 if objective_satisfied else 0, "changed_path_count": 1},
        "resources": {"wall_seconds": elapsed, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "self_report": {
            "summary": "Task 001 symlink calibration candidate; worker success is not acceptance.",
            "claims": [
                f"objective_satisfied={str(objective_satisfied).lower()}",
                "Metadata verification and separate path-boundary behavior decide calibration evidence.",
            ],
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_SHA,
            "worker_config_digest": canonical_digest(worker_config),
            "environment": {
                "platform": platform.platform(), "python": platform.python_version(),
                "tool_versions": {
                    "task001-cohort-symlink-calibration": TOOL_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": sorted(item["id"] for item in work_unit["validators"] if item.get("required") is True),
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Evaluator calibration only; not a benchmark outcome or integration decision.",
        },
        "extensions": {
            "org.idkmesh.calibration": True,
            "org.idkmesh.objective_satisfied": objective_satisfied,
            "org.idkmesh.authority": {
                "canonical_state_write": False, "git_push": False, "merge": False,
                "automatic_candidate_selection": False,
            },
        },
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, f"{candidate_id} ResultManifest")
    return result


def materialize_candidate(
    *, source: Path, output_root: Path, candidate_id: str,
    transform: str, objective_satisfied: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    reset_source(source)
    started_at = utc_now()
    started = time.monotonic()
    apply_transform(source, transform)
    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"{candidate_id} is invalid Python: {compile_proc.stderr}")
    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"{candidate_id} changed unexpected paths: {changed}")
    patch_text = run(["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL], cwd=source).stdout
    patch_bytes = patch_text.encode("utf-8")
    require(bool(patch_bytes), f"{candidate_id} produced an empty patch")
    behavior = run_behavioral_matrix(source, transform)
    if objective_satisfied:
        require(behavior["safe_direct_symlink_rejection_passed"] is True, "straightforward behavior failed")
    else:
        require(behavior["vulnerable_direct_symlink_accepted"] is True, "decoy unexpectedly rejected symlink")
    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"safe_direct_symlink_rejection_passed={str(behavior['safe_direct_symlink_rejection_passed']).lower()}\n"
        f"vulnerable_direct_symlink_accepted={str(behavior['vulnerable_direct_symlink_accepted']).lower()}\n"
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
        work_unit=work_unit, candidate_id=candidate_id, patch_bytes=patch_bytes,
        stdout_bytes=stdout_bytes, stderr_bytes=stderr_bytes, started_at=started_at,
        finished_at=finished_at, elapsed=elapsed, objective_satisfied=objective_satisfied,
    )
    result_path = candidate_root / "result-manifest.json"
    write_json(result_path, result)
    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH, result_manifest_path=result_path,
        candidate_root=candidate_root, plan_path=PLAN_PATH,
    )
    write_json(candidate_root / "verification-result.json", verification)
    reset_source(source)
    return result, verification, behavior, candidate_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output-root", default="results/verification/phase-b2-v2-task001-symlink-calibration",
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
    require(canonical_digest(work_unit) == EXPECTED_WORK_UNIT_DIGEST, "Task 001 WorkUnit digest drift")
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 001 plan is not EvaluatorPlan v0.4")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "Task 001 verifier version drift")
    require(plan["execution_mode"] == "metadata_only", "Task 001 plan is not metadata-only")
    require(
        plan["backend"]["required_added_substrings"] == [
            "unresolved = ROOT / Path(*posix.parts)",
            "require(not unresolved.is_symlink(),",
            "path = unresolved.resolve()",
        ],
        "Task 001 calibrated added semantics drift",
    )
    require(
        plan["backend"]["required_removed_substrings"]
        == ["path = (ROOT / Path(*posix.parts)).resolve()"],
        "Task 001 removed semantic drift",
    )
    plan_digest = canonical_digest(plan)
    require(plan_digest == EXPECTED_PLAN_DIGEST, "Task 001 EvaluatorPlan digest drift")

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source, output_root=output_root, candidate_id="straightforward",
        transform="straightforward", objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward Task 001")
    require(straight_verification["decision_support"]["recommendation"] == "accept_candidate", "straightforward unsupported")
    require(straight_verification["metrics"].get("matched_substring_count") == 3, "added evidence incomplete")
    require(straight_verification["metrics"].get("matched_removed_substring_count") == 1, "removal evidence incomplete")

    decoy_result, decoy_verification, decoy_behavior, decoy_root = materialize_candidate(
        source=source, output_root=output_root, candidate_id="inert-decoy",
        transform="decoy", objective_satisfied=False,
    )
    require(decoy_verification["status"] == "failed", "calibrated v0.4 accepted Task 001 decoy")
    require(decoy_verification["decision_support"]["recommendation"] == "reject_candidate", "decoy not rejected")
    require(decoy_verification["metrics"].get("matched_substring_count") == 0, "decoy matched calibrated additions")
    require(decoy_verification["metrics"].get("matched_removed_substring_count") == 1, "decoy missed removal")
    decoy_patch = (decoy_root / "candidate.patch").read_text(encoding="utf-8")
    require("+    require(not path.is_symlink()," in decoy_patch, "decoy missed provisional added marker")
    require(f"-    {OLD_PATH_LINE.strip()}" in decoy_patch, "decoy missed provisional removal marker")

    for verification in (straight_verification, decoy_verification):
        require(verification["verifier"]["adapter_version"] == "0.3.0", "verifier version drift")
        require(verification["provenance"]["verifier_config_digest"] == plan_digest, "plan digest lost")
        require(verification.get("extensions", {}).get("org.idkmesh.evaluator_plan.execution_mode") == "metadata_only", "execution mode lost")
        require(
            verification.get("extensions", {}).get("org.idkmesh.local_verifier.semantic_match_mode")
            == "added_and_removed_line_substring_all",
            "v0.4 transition mode lost",
        )

    summary = {
        "schema_version": "0.1", "cohort_id": "benchmark/phase-b2-successor-v2",
        "task_id": TASK_ID, "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit), "evaluator_plan_id": plan["id"],
        "evaluator_plan_digest": plan_digest, "verifier_adapter_version": "0.3.0",
        "provisional_proxy_goodhartable": True,
        "provisional_proxy_decoy_evidence": {
            "added_is_symlink_after_resolution": True,
            "removed_single_line_resolve": True,
            "behavior_remained_vulnerable": True,
        },
        "straightforward": {
            "result_manifest_digest": canonical_digest(straight_result),
            "verification_result_digest": canonical_digest(straight_verification),
            "verification_status": straight_verification["status"],
            "recommendation": straight_verification["decision_support"]["recommendation"],
            "safe_direct_symlink_rejection_passed": straight_behavior["safe_direct_symlink_rejection_passed"],
            "normal_boundary_behavior_preserved": straight_behavior["normal_boundary_behavior_preserved"],
            "matched_added_substrings": straight_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": straight_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "vulnerable_direct_symlink_accepted": decoy_behavior["vulnerable_direct_symlink_accepted"],
            "normal_boundary_behavior_preserved": decoy_behavior["normal_boundary_behavior_preserved"],
            "matched_added_substrings": decoy_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": decoy_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": decoy_root.relative_to(ROOT).as_posix(),
        },
        "calibration_passed": True, "calibration_candidates_are_benchmark_outcomes": False,
        "metadata_only_verifier_executes_candidate_code": False,
        "behavioral_execution_is_separate_evidence_channel": True,
        "automatic_candidate_selection": False, "canonical_state_write_authority": False,
        "merge_authority": False,
    }
    write_json(output_root / "calibration-summary.json", summary)
    reset_source(source)
    print("IDKMESH_PHASE_B2_TASK001_SYMLINK_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_PHASE_B2_TASK001_SYMLINK_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
