#!/usr/bin/env python3
"""Calibrate successor-v2 Task 005 against real frozen source.

Task 005 asks the discovery-only local compute-offer CLI to preserve its
no-canonical-write authority by allowing file output only under generated
``results/`` paths (or stdout).

This post-definition calibration creates two candidates against exact source
``a69aa0ae...``:

1. ``straightforward`` removes the vulnerable direct ``Path(args.output)``
   assignment, adds a repository/results-bounded resolver, and is expected to
   pass both canonical EvaluatorPlan v0.4 metadata verification and a separate
   evaluator-owned CLI behavioral matrix; and
2. ``inert-decoy`` merely adds a lexical ``results/`` marker while leaving the
   vulnerable output assignment untouched. It must be rejected by v0.4 while
   the behavioral matrix proves arbitrary/canonical writes remain possible.

Calibration candidates are not scored benchmark outcomes. Metadata verification
does not execute candidate code; behavioral execution is a separate explicit
calibration channel over a disposable checkout of public frozen source.
"""

from __future__ import annotations

import argparse
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
TASK_ID = "benchmark/phase-b2-v2/005-local-offer-output-boundary"
TARGET_REL = "experiments/local_compute_offer.py"
WORK_UNIT_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/work-units/"
    "task-005-local-offer-output-boundary.work-unit.json"
)
PLAN_PATH = (
    ROOT
    / "benchmarks/phase-b2-successor-v2/evaluators/"
    "task-005-local-offer-output-boundary.evaluator-plan.json"
)
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-v2/cohort.json"
VULNERABLE_LINE = "        output = Path(args.output)"
HELPER_ANCHOR = "\ndef command_discover(args: argparse.Namespace) -> int:\n"
SAFE_HELPER = r'''

def resolve_generated_output(raw: str) -> Path:
    """Return one repository-generated output path under results/ only."""
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise DiscoveryError("generated output must be a safe repository-relative path under results/")
    if len(path.parts) < 2 or path.parts[0] != "results":
        raise DiscoveryError("generated output must be a file under results/")

    repository_root = ROOT.resolve()
    results_root = (ROOT / "results").resolve()
    try:
        results_root.relative_to(repository_root)
    except ValueError as exc:
        raise DiscoveryError("results/ resolves outside the repository") from exc

    output = (ROOT / path).resolve()
    try:
        output.relative_to(results_root)
    except ValueError as exc:
        raise DiscoveryError("generated output escapes results/") from exc
    return output
'''
SAFE_LINE = "        output = resolve_generated_output(args.output)"
DECOY_BLOCK = r'''

# Calibration near-miss only: mentioning results/ does not bound --output.
_TASK005_OUTPUT_BOUNDARY_DECOY = "results/"
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
    require(
        cohort.get("extensions", {})
        .get("org.idkmesh.phase_b2_v2", {})
        .get("freeze_ready")
        is False,
        "successor scaffold unexpectedly reports freeze_ready",
    )
    task = next((item for item in cohort.get("tasks", []) if item.get("id") == TASK_ID), None)
    require(isinstance(task, dict), "Task 005 missing from successor scaffold")
    require(task.get("source", {}).get("revision") == SOURCE_SHA, "Task 005 source revision drift")
    require(task.get("evidence") == {"status": "pending", "attempts": []}, "Task 005 already has outcome evidence")
    require(task.get("negative_case", {}).get("evidence_status") == "pending", "Task 005 negative evidence is not pending")


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def apply_transform(source: Path, transform: str) -> None:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require(text.count(VULNERABLE_LINE) == 1, "frozen source vulnerable output assignment drift")

    if transform == "straightforward":
        require(HELPER_ANCHOR in text, "command_discover anchor drift")
        text = text.replace(HELPER_ANCHOR, SAFE_HELPER + HELPER_ANCHOR, 1)
        text = text.replace(VULNERABLE_LINE, SAFE_LINE, 1)
    elif transform == "decoy":
        require(DECOY_BLOCK.strip() not in text, "decoy marker unexpectedly already present")
        text = text + DECOY_BLOCK
    else:
        raise CalibrationError(f"unsupported transform: {transform}")

    target.write_text(text, encoding="utf-8")


def run_discover(source: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, TARGET_REL, "discover", *arguments],
        cwd=source,
        check=False,
    )


def behavior_case(source: Path, transform: str, case_id: str) -> dict[str, Any]:
    reset_source(source)
    apply_transform(source, transform)

    sibling_absolute = source.parent / f"idkmesh-task005-{transform}-absolute.json"
    sibling_traversal = source.parent / f"idkmesh-task005-{transform}-traversal.json"
    for path in (sibling_absolute, sibling_traversal):
        path.unlink(missing_ok=True)

    readme = source / "README.md"
    readme_before = readme.read_bytes()
    results_file = source / "results" / "task005-calibration" / f"{transform}.json"

    if case_id == "stdout":
        proc = run_discover(source)
        json_valid = False
        if proc.returncode == 0:
            try:
                json.loads(proc.stdout)
                json_valid = True
            except json.JSONDecodeError:
                pass
        return {
            "id": case_id,
            "returncode": proc.returncode,
            "stdout_json_valid": json_valid,
            "write_observed": False,
            "stderr_excerpt": proc.stderr.strip()[:300],
        }

    if case_id == "results":
        proc = run_discover(source, "--output", "results/task005-calibration/" + f"{transform}.json")
        file_valid = False
        if results_file.is_file():
            try:
                value = json.loads(results_file.read_text(encoding="utf-8"))
                file_valid = isinstance(value, dict) and value.get("schema_version") == "0.1"
            except json.JSONDecodeError:
                pass
        return {
            "id": case_id,
            "returncode": proc.returncode,
            "results_file_created": results_file.is_file(),
            "results_file_json_valid": file_valid,
            "stderr_excerpt": proc.stderr.strip()[:300],
        }

    if case_id == "canonical-readme":
        proc = run_discover(source, "--output", "README.md")
        return {
            "id": case_id,
            "returncode": proc.returncode,
            "canonical_file_modified": readme.read_bytes() != readme_before,
            "stderr_excerpt": proc.stderr.strip()[:300],
        }

    if case_id == "absolute":
        proc = run_discover(source, "--output", str(sibling_absolute.resolve()))
        observed = sibling_absolute.is_file()
        sibling_absolute.unlink(missing_ok=True)
        return {
            "id": case_id,
            "returncode": proc.returncode,
            "outside_file_created": observed,
            "stderr_excerpt": proc.stderr.strip()[:300],
        }

    if case_id == "traversal":
        proc = run_discover(source, "--output", f"../{sibling_traversal.name}")
        observed = sibling_traversal.is_file()
        sibling_traversal.unlink(missing_ok=True)
        return {
            "id": case_id,
            "returncode": proc.returncode,
            "outside_file_created": observed,
            "stderr_excerpt": proc.stderr.strip()[:300],
        }

    raise CalibrationError(f"unknown behavior case: {case_id}")


def run_behavioral_matrix(source: Path, transform: str) -> dict[str, Any]:
    observations = [
        behavior_case(source, transform, case_id)
        for case_id in ("stdout", "results", "canonical-readme", "absolute", "traversal")
    ]
    by_id = {item["id"]: item for item in observations}
    safe = (
        by_id["stdout"]["returncode"] == 0
        and by_id["stdout"]["stdout_json_valid"] is True
        and by_id["results"]["returncode"] == 0
        and by_id["results"]["results_file_created"] is True
        and by_id["results"]["results_file_json_valid"] is True
        and by_id["canonical-readme"]["returncode"] == 2
        and by_id["canonical-readme"]["canonical_file_modified"] is False
        and by_id["absolute"]["returncode"] == 2
        and by_id["absolute"]["outside_file_created"] is False
        and by_id["traversal"]["returncode"] == 2
        and by_id["traversal"]["outside_file_created"] is False
    )
    vulnerable = (
        by_id["stdout"]["returncode"] == 0
        and by_id["results"]["returncode"] == 0
        and by_id["canonical-readme"]["returncode"] == 0
        and by_id["canonical-readme"]["canonical_file_modified"] is True
        and by_id["absolute"]["returncode"] == 0
        and by_id["absolute"]["outside_file_created"] is True
        and by_id["traversal"]["returncode"] == 0
        and by_id["traversal"]["outside_file_created"] is True
    )
    reset_source(source)
    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate": transform,
        "checks": observations,
        "safe_boundary_matrix_passed": safe,
        "vulnerable_boundary_preserved": vulnerable,
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
            "id": f"idkmesh-task005-calibration-{candidate_id}",
            "type": "system",
            "adapter": f"task005-{candidate_id}-calibration",
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
                "description": "Task 005 post-definition evaluator-calibration candidate patch.",
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
            "summary": "Task 005 calibration candidate; worker success is not acceptance.",
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
                    "task005-local-offer-output-calibration": TOOL_VERSION,
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
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, f"{candidate_id} ResultManifest")
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
        require(behavior["safe_boundary_matrix_passed"] is True, "straightforward candidate failed output-boundary behavior")
    else:
        require(behavior["vulnerable_boundary_preserved"] is True, "decoy unexpectedly fixed output-boundary behavior")

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"safe_boundary_matrix_passed={str(behavior['safe_boundary_matrix_passed']).lower()}\n"
        f"vulnerable_boundary_preserved={str(behavior['vulnerable_boundary_preserved']).lower()}\n"
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
        default="results/verification/phase-b2-v2-task005-calibration",
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
    require(canonical_digest(work_unit) == "sha256:063dd0504fac4b9eb474f4d16e68ffc3680edd5ab6570f3473b1634cc8edd7f8", "Task 005 WorkUnit digest drift")
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 005 plan is not EvaluatorPlan v0.4")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "Task 005 verifier version drift")
    require(plan["execution_mode"] == "metadata_only", "Task 005 plan is not metadata-only")
    require(plan["backend"]["required_added_substrings"] == ["results/"], "Task 005 added semantic drift")
    require(plan["backend"]["required_removed_substrings"] == ["output = Path(args.output)"], "Task 005 removed semantic drift")
    plan_digest = canonical_digest(plan)
    require(plan_digest == "sha256:1965941c5c2844dc302049bcf461815df885571107e73d430ca3f68cac0adc16", "Task 005 EvaluatorPlan digest drift")

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="straightforward",
        transform="straightforward",
        objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward Task 005 candidate")
    require(straight_verification["decision_support"]["recommendation"] == "accept_candidate", "v0.4 did not support straightforward Task 005 candidate")
    require(straight_verification["metrics"].get("required_substring_count") == 1, "straightforward added requirement count drift")
    require(straight_verification["metrics"].get("matched_substring_count") == 1, "straightforward did not satisfy required added evidence")
    require(straight_verification["metrics"].get("required_removed_substring_count") == 1, "straightforward removal requirement count drift")
    require(straight_verification["metrics"].get("matched_removed_substring_count") == 1, "straightforward did not satisfy required removal evidence")

    decoy_result, decoy_verification, decoy_behavior, decoy_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="inert-decoy",
        transform="decoy",
        objective_satisfied=False,
    )
    require(decoy_verification["status"] == "failed", "v0.4 failed to reject Task 005 inert decoy")
    require(decoy_verification["decision_support"]["recommendation"] == "reject_candidate", "v0.4 did not reject Task 005 inert decoy")
    require(decoy_verification["metrics"].get("required_substring_count") == 1, "decoy added requirement count drift")
    require(decoy_verification["metrics"].get("matched_substring_count") == 1, "decoy did not exercise the lexical added near-miss")
    require(decoy_verification["metrics"].get("required_removed_substring_count") == 1, "decoy removal requirement count drift")
    require(decoy_verification["metrics"].get("matched_removed_substring_count") == 0, "decoy unexpectedly removed vulnerable output assignment")

    for verification in (straight_verification, decoy_verification):
        require(verification["verifier"]["adapter_version"] == "0.3.0", "VerificationResult verifier version drift")
        require(verification["provenance"]["verifier_config_digest"] == plan_digest, "VerificationResult lost exact Task 005 EvaluatorPlan digest")
        require(
            verification.get("extensions", {}).get("org.idkmesh.evaluator_plan.execution_mode") == "metadata_only",
            "VerificationResult lost metadata-only EvaluatorPlan provenance",
        )
        require(
            verification.get("extensions", {}).get("org.idkmesh.local_verifier.semantic_match_mode") == "added_and_removed_line_substring_all",
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
            "safe_boundary_matrix_passed": straight_behavior["safe_boundary_matrix_passed"],
            "matched_added_substrings": straight_verification["metrics"]["matched_substring_count"],
            "matched_removed_substrings": straight_verification["metrics"]["matched_removed_substring_count"],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "vulnerable_boundary_preserved": decoy_behavior["vulnerable_boundary_preserved"],
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

    print("IDKMESH_PHASE_B2_TASK005_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_PHASE_B2_TASK005_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
