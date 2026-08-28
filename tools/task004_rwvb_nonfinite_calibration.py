#!/usr/bin/env python3
"""Calibrate successor-v2 Task 004 against the exact frozen source.

The provisional evaluator accepted a no-op ``math.isfinite`` reference plus a
syntactic guard rewrite. This calibration strengthens that mutable pre-freeze
proxy and checks a real finite-domain repair against that inert near-miss.
Candidate code runs only in a disposable frozen-source checkout; the canonical
EvaluatorPlan remains metadata-only. These candidates are calibration evidence,
not scored benchmark outcomes.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
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
TASK_ID = "benchmark/phase-b2-v2/004-rwvb-nonfinite-domain"
TARGET_REL = "experiments/verification_backpressure.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/work-units/task-004-rwvb-nonfinite-domain.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-v2/evaluators/task-004-rwvb-nonfinite-domain.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
EXPECTED_WORK_UNIT_DIGEST = "sha256:9f4d5dd07e7af04a2d603edc7eb1cd2a424ae389a0edc7496b9ae83bcf11f4e4"
EXPECTED_PLAN_DIGEST = "sha256:e42cbd25ee956fe6d5fe4f0f9ca01d805f28dab3aa9c0601869c16cddd420834"
TOOL_VERSION = "0.1"

HELPER = '''def _require_finite_fields(
    owner: str, fields: tuple[tuple[str, float], ...]
) -> None:
    for name, value in fields:
        if not math.isfinite(value):
            raise ValueError(f"{owner}.{name} must be finite, got {value}")


'''
CANDIDATE_CALL = '''    def validate(self) -> None:
        _require_finite_fields(
            "Candidate",
            (
                ("risk", self.risk),
                ("uncertainty", self.uncertainty),
                ("impact", self.impact),
                ("estimated_verification_cost", self.estimated_verification_cost),
                ("evidence_diversity", self.evidence_diversity),
            ),
        )
        for name in ("risk", "uncertainty", "evidence_diversity"):
'''
CONTROLLER_CALL = '''    def validate(self) -> None:
        _require_finite_fields(
            "ControllerConfig",
            (
                ("diversity_weight", self.diversity_weight),
                ("uncertainty_floor", self.uncertainty_floor),
                ("age_half_life", self.age_half_life),
                ("low_watermark", self.low_watermark),
                ("high_watermark", self.high_watermark),
                ("response_rate", self.response_rate),
            ),
        )
        if self.diversity_weight < 0.0:
'''
DECOY_MARKER = '''
# Calibration near-miss: references the predicate without validating inputs.
_TASK004_NONFINITE_DECOY = math.isfinite
'''
CANDIDATE_FLOATS = ("risk", "uncertainty", "impact", "estimated_verification_cost", "evidence_diversity")
CONFIG_FLOATS = ("diversity_weight", "uncertainty_floor", "age_half_life", "low_watermark", "high_watermark", "response_rate")
NONFINITE_VALUES = (("nan", float("nan")), ("posinf", float("inf")), ("neginf", float("-inf")))


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
    require(
        extension.get("freeze_ready") is (len(pending) == 0),
        "scaffold freeze_ready disagrees with pending calibration state",
    )
    require(TASK_ID in pending | completed, "Task 004 is absent from calibration state")
    task = next((item for item in cohort.get("tasks", []) if item.get("id") == TASK_ID), None)
    require(isinstance(task, dict), "Task 004 missing from scaffold")
    require(task.get("source", {}).get("revision") == SOURCE_SHA, "Task 004 source drift")
    require(task.get("evidence") == {"status": "pending", "attempts": []}, "Task 004 has outcomes")
    require(task.get("negative_case", {}).get("evidence_status") == "pending", "negative evidence is not pending")


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source is dirty")


def apply_transform(source: Path, transform: str) -> None:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    candidate_marker = '''    def validate(self) -> None:
        for name in ("risk", "uncertainty", "evidence_diversity"):
'''
    controller_marker = '''    def validate(self) -> None:
        if self.diversity_weight < 0.0:
'''
    impact_guard = '''        if self.impact < 0.0:
            raise ValueError("impact must be >= 0")
'''
    require(text.count(candidate_marker) == 1, "frozen Candidate.validate drift")
    require(text.count(controller_marker) == 1, "frozen ControllerConfig.validate drift")
    require(text.count(impact_guard) == 1, "frozen impact guard drift")

    if transform == "straightforward":
        class_marker = "@dataclass(frozen=True)\nclass Candidate:"
        require(text.count(class_marker) == 1, "frozen Candidate class marker drift")
        text = text.replace(class_marker, HELPER + class_marker, 1)
        text = text.replace(candidate_marker, CANDIDATE_CALL, 1)
        text = text.replace(controller_marker, CONTROLLER_CALL, 1)
        text = text.replace(
            impact_guard,
            '''        if not 0.0 <= self.impact:
            raise ValueError("impact must be >= 0")
''',
            1,
        )
    elif transform == "decoy":
        text = text.replace("EPSILON = 1e-9\n", "EPSILON = 1e-9\n" + DECOY_MARKER, 1)
        text = text.replace(
            impact_guard,
            '''        if 0.0 > self.impact:
            raise ValueError("impact must be >= 0")
''',
            1,
        )
    else:
        raise CalibrationError(f"unsupported transform: {transform}")
    target.write_text(text, encoding="utf-8")


def load_target(source: Path, tag: str) -> ModuleType:
    module_name = f"task004_calibration_{tag}_{time.monotonic_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, source / TARGET_REL)
    require(spec is not None and spec.loader is not None, "cannot load RWVB source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def finite_signature(module: ModuleType) -> dict[str, Any]:
    candidate = module.Candidate("finite", 0.7, 0.6, 1.2, 2.0, 0.4, 3)
    config = module.ControllerConfig()
    candidate.validate()
    config.validate()
    return {
        "candidate": asdict(candidate),
        "config": asdict(config),
        "debt": module.verification_debt(candidate, config),
        "priority": module.priority_score(candidate, config),
        "selected": [item.id for item in module.schedule_verification([candidate], 2.0, config)],
        "fanout_low": module.next_generation_fanout(4, 0.1, 4.0, config),
        "fanout_high": module.next_generation_fanout(8, 20.0, 4.0, config),
    }


def observe_invalid(module: ModuleType, owner: str, field: str, label: str, value: float) -> dict[str, Any]:
    candidate_values = {
        "id": "probe",
        "risk": 0.7,
        "uncertainty": 0.6,
        "impact": 1.2,
        "estimated_verification_cost": 2.0,
        "evidence_diversity": 0.4,
        "age_steps": 3,
    }
    config_values = asdict(module.ControllerConfig())
    if owner == "Candidate":
        candidate_values[field] = value
    else:
        config_values[field] = value
    candidate = module.Candidate(**candidate_values)
    config = module.ControllerConfig(**config_values)
    rejected = False
    validation_error = ""
    try:
        candidate.validate()
        config.validate()
    except ValueError as exc:
        rejected = True
        validation_error = str(exc)

    outputs_finite = None
    runtime_error = ""
    if not rejected:
        try:
            outputs = (
                module.verification_debt(candidate, config),
                module.priority_score(candidate, config),
            )
            module.next_generation_fanout(8, 20.0, 4.0, config)
            outputs_finite = all(math.isfinite(item) for item in outputs)
        except (OverflowError, ValueError, ZeroDivisionError) as exc:
            outputs_finite = False
            runtime_error = f"{type(exc).__name__}: {exc}"
    return {
        "id": f"{owner}.{field}.{label}",
        "owner": owner,
        "field": field,
        "value": label,
        "validation_rejected": rejected,
        "validation_error": validation_error,
        "outputs_finite": outputs_finite,
        "runtime_error": runtime_error,
    }


def run_behavioral_matrix(source: Path, transform: str) -> dict[str, Any]:
    reset_source(source)
    baseline = finite_signature(load_target(source, "frozen"))
    apply_transform(source, transform)
    changed = load_target(source, transform)
    finite_behavior_preserved = finite_signature(changed) == baseline
    observations = [
        observe_invalid(changed, owner, field, label, value)
        for owner, fields in (("Candidate", CANDIDATE_FLOATS), ("ControllerConfig", CONFIG_FLOATS))
        for field in fields
        for label, value in NONFINITE_VALUES
    ]
    escaped = [item["id"] for item in observations if not item["validation_rejected"]]
    reset_source(source)
    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate": transform,
        "finite_behavior_preserved": finite_behavior_preserved,
        "checks": observations,
        "rejected_nonfinite_count": len(observations) - len(escaped),
        "total_nonfinite_count": len(observations),
        "escaped_validation_case_ids": escaped,
        "safe_nonfinite_domain_matrix_passed": finite_behavior_preserved and not escaped,
        "vulnerable_nonfinite_inputs_pass_validation": finite_behavior_preserved and bool(escaped),
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
            "id": f"idkmesh-task004-calibration-{candidate_id}",
            "type": "system",
            "adapter": f"task004-{candidate_id}-calibration",
            "adapter_version": TOOL_VERSION,
        },
        "status": "succeeded",
        "started_at": started_at,
        "finished_at": finished_at,
        "produced_artifacts": [{
            "id": "candidate-patch", "type": "patch", "locator": "candidate.patch",
            "digest": sha256_bytes(patch_bytes), "media_type": "text/x-diff",
            "description": "Task 004 post-definition evaluator-calibration candidate patch.",
        }],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {"objective_satisfied": 1 if objective_satisfied else 0, "changed_path_count": 1},
        "resources": {"wall_seconds": elapsed, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "self_report": {
            "summary": "Task 004 calibration candidate; worker success is not acceptance.",
            "claims": [
                f"objective_satisfied={str(objective_satisfied).lower()}",
                "Canonical metadata verification and separate behavioral checks decide calibration evidence.",
            ],
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_SHA,
            "worker_config_digest": canonical_digest(worker_config),
            "environment": {
                "platform": platform.platform(), "python": platform.python_version(),
                "tool_versions": {
                    "task004-rwvb-nonfinite-calibration": TOOL_VERSION,
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
        require(behavior["safe_nonfinite_domain_matrix_passed"] is True, "straightforward behavior failed")
    else:
        require(behavior["vulnerable_nonfinite_inputs_pass_validation"] is True, "decoy fixed validation")
    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"safe_nonfinite_domain_matrix_passed={str(behavior['safe_nonfinite_domain_matrix_passed']).lower()}\n"
        f"vulnerable_nonfinite_inputs_pass_validation={str(behavior['vulnerable_nonfinite_inputs_pass_validation']).lower()}\n"
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
        "--output-root", default="results/verification/phase-b2-v2-task004-calibration",
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
    require(canonical_digest(work_unit) == EXPECTED_WORK_UNIT_DIGEST, "Task 004 WorkUnit digest drift")
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 004 plan is not EvaluatorPlan v0.4")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "Task 004 verifier version drift")
    require(plan["execution_mode"] == "metadata_only", "Task 004 plan is not metadata-only")
    require(
        plan["backend"]["required_added_substrings"]
        == ['if not math.isfinite(value):', '"Candidate",', '"ControllerConfig",'],
        "Task 004 calibrated added semantics drift",
    )
    require(plan["backend"]["required_removed_substrings"] == ["if self.impact < 0.0:"], "removed semantic drift")
    plan_digest = canonical_digest(plan)
    require(plan_digest == EXPECTED_PLAN_DIGEST, "Task 004 EvaluatorPlan digest drift")

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source, output_root=output_root, candidate_id="straightforward",
        transform="straightforward", objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward Task 004")
    require(straight_verification["decision_support"]["recommendation"] == "accept_candidate", "straightforward unsupported")
    require(straight_verification["metrics"].get("matched_substring_count") == 3, "added evidence incomplete")
    require(straight_verification["metrics"].get("matched_removed_substring_count") == 1, "removal evidence incomplete")

    decoy_result, decoy_verification, decoy_behavior, decoy_root = materialize_candidate(
        source=source, output_root=output_root, candidate_id="inert-decoy",
        transform="decoy", objective_satisfied=False,
    )
    require(decoy_verification["status"] == "failed", "calibrated v0.4 accepted Task 004 decoy")
    require(decoy_verification["decision_support"]["recommendation"] == "reject_candidate", "decoy not rejected")
    require(decoy_verification["metrics"].get("matched_substring_count") == 0, "decoy matched calibrated additions")
    require(decoy_verification["metrics"].get("matched_removed_substring_count") == 1, "decoy missed removal")
    decoy_patch = (decoy_root / "candidate.patch").read_text(encoding="utf-8")
    require(
        "+_TASK004_NONFINITE_DECOY = math.isfinite" in decoy_patch,
        "decoy did not satisfy the provisional added marker",
    )
    require(
        "-        if self.impact < 0.0:" in decoy_patch,
        "decoy did not satisfy the provisional removal marker",
    )

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
            "added_math_isfinite": True, "removed_original_impact_guard": True,
            "behavior_remained_vulnerable": True,
        },
        "straightforward": {
            "result_manifest_digest": canonical_digest(straight_result),
            "verification_result_digest": canonical_digest(straight_verification),
            "verification_status": straight_verification["status"],
            "recommendation": straight_verification["decision_support"]["recommendation"],
            "safe_nonfinite_domain_matrix_passed": straight_behavior["safe_nonfinite_domain_matrix_passed"],
            "rejected_nonfinite_count": straight_behavior["rejected_nonfinite_count"],
            "total_nonfinite_count": straight_behavior["total_nonfinite_count"],
            "matched_added_substrings": straight_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": straight_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "vulnerable_nonfinite_inputs_pass_validation": decoy_behavior["vulnerable_nonfinite_inputs_pass_validation"],
            "escaped_validation_case_ids": decoy_behavior["escaped_validation_case_ids"],
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
    print("IDKMESH_PHASE_B2_TASK004_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_PHASE_B2_TASK004_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
