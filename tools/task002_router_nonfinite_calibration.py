#!/usr/bin/env python3
"""Calibrate successor-v2 Task 002 against exact frozen source.

Task 002 requires the free-compute router to reject non-finite numeric JSON
values before they can participate in eligibility, spend, or ranking logic.
Python's standard ``json.loads`` accepts NaN and Infinity by default, while the
existing JSON Schema numeric bounds do not reliably reject every non-finite
value.

This post-definition calibration creates two candidates against exact source
``a69aa0ae1ae4862e507511cbd9ad854237d0ad32``:

1. ``straightforward`` adds a recursive ``isfinite`` gate to ``read_json`` so
   every loaded WorkUnit, offer pool, compute policy, and schema document is
   finite before validation/routing; and
2. ``inert-decoy`` adds the expected lexical marker while preserving the
   vulnerable direct ``json.loads`` return.

The canonical EvaluatorPlan v0.4 path verifies patch metadata only. A separate
evaluator-owned behavioral matrix executes the modified frozen-source CLI on
finite controls and NaN/+Infinity/-Infinity cases.

Calibration candidates are not scored benchmark outcomes and have no
repository integration authority.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
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
TASK_ID = "benchmark/phase-b2-v2/002-router-nonfinite-numbers"
TARGET_REL = "experiments/free_compute_router.py"
WORK_UNIT_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/work-units/"
    "task-002-router-nonfinite-numbers.work-unit.json"
)
PLAN_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/evaluators/"
    "task-002-router-nonfinite-numbers.evaluator-plan.json"
)
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
BASE_WORK_REL = "examples/work-units/phase0-smoke.work-unit.json"
BASE_OFFERS_REL = "examples/compute-offers/free-pool.example.json"
BASE_POLICY_REL = "config/compute-policy.json"
SELECTED_CONTROL_OFFER = "github-public-ci"
OLD_READ_JSON = '''def read_json(path: Path) -> Any:\n    return json.loads(path.read_text(encoding="utf-8"))\n'''
NEW_READ_JSON = '''def _reject_nonfinite(value: Any, location: str = "$" ) -> None:\n    if isinstance(value, float):\n        if not isfinite(value):\n            raise RouterError(f"non-finite numeric value at {location}")\n        return\n    if isinstance(value, dict):\n        for key, item in value.items():\n            _reject_nonfinite(item, f"{location}.{key}")\n    elif isinstance(value, list):\n        for index, item in enumerate(value):\n            _reject_nonfinite(item, f"{location}[{index}]")\n\n\ndef read_json(path: Path) -> Any:\n    value = json.loads(path.read_text(encoding="utf-8"))\n    _reject_nonfinite(value)\n    return value\n'''
DECOY_BLOCK = r'''

# Calibration near-miss only: the marker does not validate parsed numbers.
_TASK002_NONFINITE_DECOY = "isfinite"
'''
TOOL_VERSION = "0.1"
CASE_IDS = (
    "finite-baseline",
    "work-budget-nan",
    "work-budget-posinf",
    "work-budget-neginf",
    "policy-spend-nan",
    "policy-spend-posinf",
    "offer-cost-nan",
    "offer-cost-posinf",
    "offer-cost-neginf",
    "offer-success-nan",
    "offer-success-posinf",
    "offer-wait-posinf",
)


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
    require(TASK_ID in extension.get("calibration_pending_task_ids", []), "Task 002 is not pending calibration")
    task = next((item for item in cohort.get("tasks", []) if item.get("id") == TASK_ID), None)
    require(isinstance(task, dict), "Task 002 missing from successor scaffold")
    require(task.get("source", {}).get("revision") == SOURCE_SHA, "Task 002 source revision drift")
    require(task.get("evidence") == {"status": "pending", "attempts": []}, "Task 002 already has outcome evidence")
    require(task.get("negative_case", {}).get("evidence_status") == "pending", "Task 002 negative evidence is not pending")


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def apply_transform(source: Path, transform: str) -> None:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require(text.count(OLD_READ_JSON) == 1, "frozen source read_json block drift")

    if transform == "straightforward":
        require("from math import isfinite" not in text, "frozen source already imports isfinite")
        text = text.replace("import json\n", "import json\nfrom math import isfinite\n", 1)
        text = text.replace(OLD_READ_JSON, NEW_READ_JSON, 1)
    elif transform == "decoy":
        require(DECOY_BLOCK.strip() not in text, "decoy marker unexpectedly already present")
        text = text + DECOY_BLOCK
    else:
        raise CalibrationError(f"unsupported transform: {transform}")

    target.write_text(text, encoding="utf-8")


def strict_json_loads(text: str) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard JSON constant: {token}")

    return json.loads(text, parse_constant=reject_constant)


def base_case_values(source: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    work = load_json(source / BASE_WORK_REL)
    pool = load_json(source / BASE_OFFERS_REL)
    policy = load_json(source / BASE_POLICY_REL)
    control_offer = next(
        (copy.deepcopy(item) for item in pool["offers"] if item["id"] == SELECTED_CONTROL_OFFER),
        None,
    )
    require(isinstance(control_offer, dict), "control free offer missing from frozen pool")
    pool["offers"] = [control_offer]
    return work, pool, policy


def mutate_case(
    case_id: str,
    work: dict[str, Any],
    pool: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    offer = pool["offers"][0]
    if case_id == "finite-baseline":
        return
    if case_id == "work-budget-nan":
        work["budget"]["project_spend_usd_max"] = float("nan")
        return
    if case_id == "work-budget-posinf":
        work["budget"]["project_spend_usd_max"] = float("inf")
        return
    if case_id == "work-budget-neginf":
        work["budget"]["project_spend_usd_max"] = float("-inf")
        return
    if case_id == "policy-spend-nan":
        policy["project_spend_usd_max"] = float("nan")
        return
    if case_id == "policy-spend-posinf":
        policy["project_spend_usd_max"] = float("inf")
        return
    if case_id == "offer-cost-nan":
        offer["project_cost_usd"] = float("nan")
        return
    if case_id == "offer-cost-posinf":
        offer["project_cost_usd"] = float("inf")
        return
    if case_id == "offer-cost-neginf":
        offer["project_cost_usd"] = float("-inf")
        return
    if case_id == "offer-success-nan":
        offer["success_probability"] = float("nan")
        return
    if case_id == "offer-success-posinf":
        offer["success_probability"] = float("inf")
        return
    if case_id == "offer-wait-posinf":
        offer["expected_wait_seconds"] = float("inf")
        return
    raise CalibrationError(f"unknown behavior case: {case_id}")


def run_select(
    source: Path,
    work_rel: str,
    offers_rel: str,
    policy_rel: str,
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            TARGET_REL,
            "select",
            "--work-unit",
            work_rel,
            "--offers",
            offers_rel,
            "--policy",
            policy_rel,
        ],
        cwd=source,
        check=False,
    )


def behavior_case(source: Path, transform: str, case_id: str) -> dict[str, Any]:
    reset_source(source)
    apply_transform(source, transform)
    work, pool, policy = base_case_values(source)
    mutate_case(case_id, work, pool, policy)

    case_root = source / "results" / "task002-calibration" / transform / case_id
    work_path = case_root / "work.json"
    offers_path = case_root / "offers.json"
    policy_path = case_root / "policy.json"
    write_json(work_path, work)
    write_json(offers_path, pool)
    write_json(policy_path, policy)

    proc = run_select(
        source,
        work_path.relative_to(source).as_posix(),
        offers_path.relative_to(source).as_posix(),
        policy_path.relative_to(source).as_posix(),
    )

    strict_stdout_json = False
    selected_offer_id = None
    report_status = None
    if proc.stdout.strip():
        try:
            parsed = strict_json_loads(proc.stdout)
            strict_stdout_json = isinstance(parsed, dict)
            if isinstance(parsed, dict):
                report_status = parsed.get("status")
                selected = parsed.get("selected")
                if isinstance(selected, dict):
                    selected_offer_id = selected.get("offer_id")
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "id": case_id,
        "returncode": proc.returncode,
        "strict_stdout_json": strict_stdout_json,
        "selected_offer_id": selected_offer_id,
        "report_status": report_status,
        "stdout_contains_nonstandard_constant": any(
            token in proc.stdout for token in ("NaN", "Infinity", "-Infinity")
        ),
        "stderr_excerpt": proc.stderr.strip()[:300],
    }


def run_behavioral_matrix(source: Path, transform: str) -> dict[str, Any]:
    observations = [behavior_case(source, transform, case_id) for case_id in CASE_IDS]
    by_id = {item["id"]: item for item in observations}
    baseline = by_id["finite-baseline"]
    nonfinite = [by_id[case_id] for case_id in CASE_IDS if case_id != "finite-baseline"]

    safe = (
        baseline["returncode"] == 0
        and baseline["strict_stdout_json"] is True
        and baseline["selected_offer_id"] == SELECTED_CONTROL_OFFER
        and all(item["returncode"] == 2 for item in nonfinite)
        and all(item["selected_offer_id"] is None for item in nonfinite)
    )
    vulnerable = (
        baseline["returncode"] == 0
        and baseline["selected_offer_id"] == SELECTED_CONTROL_OFFER
        and by_id["work-budget-nan"]["returncode"] == 0
        and by_id["work-budget-posinf"]["returncode"] == 0
        and by_id["policy-spend-nan"]["returncode"] == 0
        and by_id["policy-spend-posinf"]["returncode"] == 0
        and by_id["offer-cost-nan"]["returncode"] == 0
        and by_id["offer-cost-nan"]["selected_offer_id"] is None
        and by_id["offer-cost-nan"]["strict_stdout_json"] is False
        and by_id["offer-cost-nan"]["stdout_contains_nonstandard_constant"] is True
        and by_id["offer-success-nan"]["returncode"] == 0
        and by_id["offer-success-nan"]["selected_offer_id"] == SELECTED_CONTROL_OFFER
        and by_id["offer-wait-posinf"]["returncode"] == 0
        and by_id["offer-wait-posinf"]["selected_offer_id"] == SELECTED_CONTROL_OFFER
    )
    reset_source(source)
    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate": transform,
        "checks": observations,
        "safe_nonfinite_matrix_passed": safe,
        "vulnerable_nonfinite_values_reach_routing": vulnerable,
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
            "id": f"idkmesh-task002-calibration-{candidate_id}",
            "type": "system",
            "adapter": f"task002-{candidate_id}-calibration",
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
                "description": "Task 002 post-definition evaluator-calibration candidate patch.",
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
            "summary": "Task 002 calibration candidate; worker success is not acceptance.",
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
                    "task002-router-nonfinite-calibration": TOOL_VERSION,
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
            behavior["safe_nonfinite_matrix_passed"] is True,
            "straightforward candidate failed non-finite behavioral matrix",
        )
    else:
        require(
            behavior["vulnerable_nonfinite_values_reach_routing"] is True,
            "decoy unexpectedly blocked the non-finite routing behavior",
        )

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"safe_nonfinite_matrix_passed={str(behavior['safe_nonfinite_matrix_passed']).lower()}\n"
        f"vulnerable_nonfinite_values_reach_routing={str(behavior['vulnerable_nonfinite_values_reach_routing']).lower()}\n"
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
        default="results/verification/phase-b2-v2-task002-calibration",
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
        == "sha256:1c3398ec000719eee21396b6214bc56bb410a4aa449cb7b4f9206811daf7a27d",
        "Task 002 WorkUnit digest drift",
    )
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 002 plan is not EvaluatorPlan v0.4")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "Task 002 verifier version drift")
    require(plan["execution_mode"] == "metadata_only", "Task 002 plan is not metadata-only")
    require(
        plan["backend"]["required_added_substrings"] == ["isfinite"],
        "Task 002 added semantic drift",
    )
    require(
        plan["backend"]["required_removed_substrings"]
        == ['return json.loads(path.read_text(encoding="utf-8"))'],
        "Task 002 removed semantic drift",
    )
    plan_digest = canonical_digest(plan)
    require(
        plan_digest
        == "sha256:21d6ef9b1386adc2aeac8cb2c1d409b2ff32ff07686378d260b8a56399226a43",
        "Task 002 EvaluatorPlan digest drift",
    )

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="straightforward",
        transform="straightforward",
        objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward Task 002 candidate")
    require(
        straight_verification["decision_support"]["recommendation"] == "accept_candidate",
        "v0.4 did not support straightforward Task 002 candidate",
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
    require(decoy_verification["status"] == "failed", "v0.4 failed to reject Task 002 inert decoy")
    require(
        decoy_verification["decision_support"]["recommendation"] == "reject_candidate",
        "v0.4 did not reject Task 002 inert decoy",
    )
    require(decoy_verification["metrics"].get("matched_substring_count") == 1, "decoy did not exercise the lexical added near-miss")
    require(decoy_verification["metrics"].get("matched_removed_substring_count") == 0, "decoy unexpectedly removed vulnerable direct JSON return")

    for verification in (straight_verification, decoy_verification):
        require(verification["verifier"]["adapter_version"] == "0.3.0", "VerificationResult verifier version drift")
        require(
            verification["provenance"]["verifier_config_digest"] == plan_digest,
            "VerificationResult lost exact Task 002 EvaluatorPlan digest",
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
            "safe_nonfinite_matrix_passed": straight_behavior["safe_nonfinite_matrix_passed"],
            "matched_added_substrings": straight_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": straight_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "vulnerable_nonfinite_values_reach_routing": decoy_behavior[
                "vulnerable_nonfinite_values_reach_routing"
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

    print("IDKMESH_PHASE_B2_TASK002_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_PHASE_B2_TASK002_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
