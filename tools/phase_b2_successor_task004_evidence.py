#!/usr/bin/env python3
"""Generate source-bound evidence for frozen Phase B2 successor Task 004."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402

import benchmark_cohort  # noqa: E402
from phase_b2_task001_evidence import (  # noqa: E402
    EvidenceError,
    canonical_digest,
    ensure_results_output,
    load_json,
    require,
    run,
    sha256_bytes,
    utc_now,
    write_json,
)

SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/004-safe-cohort-loader-refactor"
STRUCTURAL_SIGNATURE = "single-worker-baseline-v1"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-004-safe-cohort-loader-refactor.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-five/evaluators/task-004-safe-cohort-loader-refactor.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-five/cohort.json"
WORKER_VERSION = "0.1"

FUNCTION_ANCHOR = "\n\ndef cmd_validate(args: argparse.Namespace) -> int:\n"
FUNCTION_INSERT = '''

def load_cohort_argument(raw: str) -> dict[str, Any]:
    """Load one CLI cohort argument through the repository path boundary."""

    return load_json(resolve_repo_file(raw, label="BenchmarkCohort"))
'''
OLD_LOAD = "    cohort = load_json((ROOT / args.cohort).resolve())"
NEW_LOAD = "    cohort = load_cohort_argument(args.cohort)"
DEFINITION_BLOCK = '''def cmd_definition_digest(args: argparse.Namespace) -> int:
    cohort = load_cohort_argument(args.cohort)
'''
SEEDED_DEFINITION_BLOCK = '''def cmd_definition_digest(args: argparse.Namespace) -> int:
    cohort = load_json((ROOT / args.cohort).resolve())
'''


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def rejects_unsafe_path(proc: Any) -> bool:
    return proc.returncode == 2 and "unsafe path" in proc.stderr


def apply_worker_transformation(source: Path) -> tuple[bytes, bytes, bytes, float, str, str, dict[str, Any]]:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require("def load_cohort_argument(" not in text, "Task 004 already exists in frozen source")
    require(text.count(FUNCTION_ANCHOR) == 1, "Task 004 function anchor drift")
    require(text.count(OLD_LOAD) == 2, "expected exactly two duplicated cohort loaders")

    started_at = utc_now()
    started = time.monotonic()
    candidate_text = text.replace(FUNCTION_ANCHOR, FUNCTION_INSERT + FUNCTION_ANCHOR)
    candidate_text = candidate_text.replace(OLD_LOAD, NEW_LOAD)
    target.write_text(candidate_text, encoding="utf-8")

    compile_result = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_result.returncode == 0, f"candidate does not compile: {compile_result.stderr}")
    self_test = run([sys.executable, TARGET_REL, "self-test"], cwd=source, check=False)
    require(self_test.returncode == 0, f"candidate self-test failed: {self_test.stderr}")

    with tempfile.TemporaryDirectory(prefix="idkmesh-task004-") as temp_dir:
        fixture = Path(temp_dir) / "cohort.json"
        fixture_proc = run(
            [sys.executable, "-c", "import json,sys;sys.path.insert(0,'tools');import benchmark_cohort as b;print(json.dumps(b._fixture_cohort()))"],
            cwd=source,
        )
        fixture.write_text(fixture_proc.stdout, encoding="utf-8")
        validate = run([sys.executable, TARGET_REL, "validate", "--cohort", str(fixture)], cwd=source, check=False)
        digest = run([sys.executable, TARGET_REL, "definition-digest", "--cohort", str(fixture)], cwd=source, check=False)
        require(rejects_unsafe_path(validate), "validate did not reject the external cohort path")
        require(rejects_unsafe_path(digest), "definition-digest did not reject the external cohort path")

        require(candidate_text.count(DEFINITION_BLOCK) == 1, "definition-digest seed anchor drift")
        target.write_text(candidate_text.replace(DEFINITION_BLOCK, SEEDED_DEFINITION_BLOCK), encoding="utf-8")
        seeded_validate = run([sys.executable, TARGET_REL, "validate", "--cohort", str(fixture)], cwd=source, check=False)
        seeded_digest = run([sys.executable, TARGET_REL, "definition-digest", "--cohort", str(fixture)], cwd=source, check=False)
        target.write_text(candidate_text, encoding="utf-8")
        seeded_divergence = rejects_unsafe_path(seeded_validate) and seeded_digest.returncode == 0
        require(seeded_divergence, "seeded loader divergence was not observed")

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"worker changed unexpected tracked paths: {changed}")
    patch_text = run(["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL], cwd=source).stdout
    require("def load_cohort_argument(" in patch_text, "candidate patch lost shared loader")
    require("resolve_repo_file(raw, label=" in patch_text, "candidate patch lost safe resolver")
    require(OLD_LOAD not in candidate_text, "candidate retained direct cohort loading")

    observation = {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "candidate_validate_rejected_external_path": True,
        "candidate_definition_digest_rejected_external_path": True,
        "candidate_commands_consistent": True,
        "seeded_validate_rejected_external_path": True,
        "seeded_definition_digest_accepted_external_path": True,
        "seeded_divergence_detected": True,
        "authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False},
    }
    elapsed = max(0.0, time.monotonic() - started)
    stdout = (
        "Phase B2 Task 004 deterministic worker\n"
        f"source_revision={SOURCE_SHA}\n"
        "candidate_boundary_consistency=passed\n"
        "seeded_loader_divergence=detected\n"
        "source_self_test=passed\n\n" + self_test.stdout
    ).encode("utf-8")
    stderr = (compile_result.stderr + self_test.stderr).encode("utf-8")
    return patch_text.encode("utf-8"), stdout, stderr, elapsed, started_at, utc_now(), observation


def build_result_manifest(
    *, work_unit: dict[str, Any], patch: bytes, stdout: bytes, stderr: bytes,
    elapsed: float, started_at: str, finished_at: str,
) -> dict[str, Any]:
    worker_config = {"tool_version": WORKER_VERSION, "source_revision": SOURCE_SHA, "structural_signature": STRUCTURAL_SIGNATURE, "transform": "centralize-safe-cohort-loader"}
    required = sorted(v["id"] for v in work_unit["validators"] if v.get("required") is True)
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001",
        "work_unit_id": work_unit["id"], "work_unit_version": work_unit["version"], "attempt": 1,
        "worker": {"id": "idkmesh-phase-b2-task004-worker", "type": "system", "adapter": "deterministic-text-rewrite", "adapter_version": WORKER_VERSION},
        "status": "succeeded", "started_at": started_at, "finished_at": finished_at,
        "produced_artifacts": [{"id": "candidate-patch", "type": "patch", "locator": "candidate.patch", "digest": sha256_bytes(patch), "media_type": "text/x-diff", "description": "Unverified frozen-source Task 004 candidate patch."}],
        "logs": [{"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout)}, {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr)}],
        "metrics": {"changed_path_count": 1, "centralized_call_sites": 2, "seeded_divergences_detected": 1},
        "resources": {"wall_seconds": elapsed, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "self_report": {"summary": "Deterministic baseline centralizes two CLI loaders; self-report is not acceptance.", "claims": ["Only the allowed tool was changed.", "Both commands reject external paths through one helper.", "Worker success grants no integration authority."]},
        "provenance": {"work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "worker_config_digest": canonical_digest(worker_config), "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"phase-b2-task004-worker": WORKER_VERSION, "git": run(["git", "--version"], cwd=ROOT).stdout.strip()}}},
        "verification_request": {"expected_validator_ids": required, "evidence_artifact_ids": ["candidate-patch"], "notes": "Route through the frozen public EvaluatorPlan; worker self-report is not acceptance."},
        "extensions": {"org.idkmesh.benchmark.structural_signature": STRUCTURAL_SIGNATURE, "org.idkmesh.authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False}},
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, "Task 004 ResultManifest")
    return result


def build_negative_verification(
    *, work_unit: dict[str, Any], result: dict[str, Any], observation: dict[str, Any], plan_digest: str,
) -> dict[str, Any]:
    timestamp = utc_now()
    verification = {
        "schema_version": "0.1", "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001/loader-divergence",
        "result_manifest_id": result["id"], "work_unit_id": work_unit["id"], "work_unit_version": work_unit["version"], "attempt": 1,
        "verifier": {"id": "idkmesh-task004-behavior-verifier", "type": "system", "adapter": "cohort-loader-boundary-parity", "adapter_version": WORKER_VERSION},
        "independence": {"independent_from_worker": True, "worker_id_observed": result["worker"]["id"], "shared_model_family": False, "shared_runtime": True, "correlation_notes": "The behavioral probe is logically separate from candidate generation but reuses the isolated source runtime and executes an explicit one-command divergence."},
        "status": "failed", "started_at": timestamp, "finished_at": timestamp,
        "checks": [{"id": "cohort-loader-boundary-parity", "type": "test", "required": True, "status": "failed", "summary": "The deliberately divergent definition-digest loader accepts an external path rejected by validate.", "evidence_ids": ["behavior-observation"]}],
        "evidence": [{"id": "behavior-observation", "type": "test_output", "locator": "behavior-observation.json", "digest": canonical_digest(observation), "media_type": "application/json", "description": "Digest of candidate parity and seeded divergence observations."}],
        "findings": [{"severity": "high", "category": "regression", "summary": "CLI cohort loaders diverge at the repository boundary.", "path": TARGET_REL}],
        "metrics": {"candidate_boundary_divergences": 0, "seeded_boundary_divergences": 1},
        "resources": {"wall_seconds": 0.0, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "provenance": {"result_manifest_digest": canonical_digest(result), "work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "verifier_config_digest": plan_digest, "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"cohort-loader-boundary-parity": WORKER_VERSION}}},
        "decision_support": {"recommendation": "reject_candidate", "confidence": 1.0, "rationale": "This VerificationResult records the deliberately divergent seeded case, not the accepted candidate."},
        "extensions": {"org.idkmesh.seeded_negative": True, "org.idkmesh.seeded_negative.expected_category": "regression"},
    }
    local_verifier.validate_schema(verification, local_verifier.VERIFICATION_RESULT_SCHEMA, "Task 004 negative VerificationResult")
    return verification


def attach_prospectively(*, result: dict[str, Any], result_path: Path, verification: dict[str, Any], verification_path: Path, negative: dict[str, Any], negative_path: Path) -> dict[str, Any]:
    cohort = load_json(COHORT_PATH)
    frozen_digest = cohort["definition_digest"]
    task = next((item for item in cohort["tasks"] if item["id"] == TASK_ID), None)
    require(task is not None, "active cohort lost Task 004")
    task["evidence"] = {"status": "verified", "attempts": [{"attempt_id": "attempt-001", "structural_signature": STRUCTURAL_SIGNATURE, "result_manifest": {"path": result_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(result), "id": result["id"]}, "verification_result": {"path": verification_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(verification), "id": verification["id"]}, "outcome": "support"}]}
    task["negative_case"].update({"evidence_status": "verified", "evidence_type": "verification_result", "evidence_path": negative_path.relative_to(ROOT).as_posix(), "evidence_digest": canonical_digest(negative)})
    summary = benchmark_cohort.validate_cohort(cohort)
    require(summary["definition_digest"] == frozen_digest, "Task 004 attachment changed frozen definition digest")
    require(task["evidence"]["status"] == "verified", "Task 004 evidence was not attached")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", default="results/benchmarks/phase-b2-successor-five/task-004/attempt-001")
    args = parser.parse_args()
    source = args.source.resolve()
    require(source.is_dir(), f"source checkout missing: {source}")
    reset_source(source)
    output = ensure_results_output(args.output_root)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    work_unit = load_json(WORK_UNIT_PATH)
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(work_unit["id"] == TASK_ID, "Task 004 WorkUnit id drift")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "Task 004 source binding drift")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "Task 004 WorkUnit digest drift")
    require(plan["execution_mode"] == "metadata_only", "Task 004 evaluator must remain metadata-only")

    patch, stdout, stderr, elapsed, started_at, finished_at, observation = apply_worker_transformation(source)
    (output / "candidate.patch").write_bytes(patch)
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    write_json(output / "behavior-observation.json", observation)
    result = build_result_manifest(work_unit=work_unit, patch=patch, stdout=stdout, stderr=stderr, elapsed=elapsed, started_at=started_at, finished_at=finished_at)
    result_path = output / "result-manifest.json"
    write_json(result_path, result)
    verification = evaluator_plan_runner.run_fixture(work_unit_path=WORK_UNIT_PATH, result_manifest_path=result_path, candidate_root=output, plan_path=PLAN_PATH)
    require(verification["status"] == "passed", "frozen Task 004 evaluator rejected candidate")
    require(verification["decision_support"]["recommendation"] == "accept_candidate", "Task 004 verifier did not support candidate")
    verification_path = output / "verification-result.json"
    write_json(verification_path, verification)
    negative = build_negative_verification(work_unit=work_unit, result=result, observation=observation, plan_digest=canonical_digest(plan))
    negative_path = output / "seeded-negative.verification-result.json"
    write_json(negative_path, negative)
    summary = attach_prospectively(result=result, result_path=result_path, verification=verification, verification_path=verification_path, negative=negative, negative_path=negative_path)
    evidence = {"schema_version": "0.1", "task_id": TASK_ID, "source_revision": SOURCE_SHA, "structural_signature": STRUCTURAL_SIGNATURE, "candidate_patch_digest": sha256_bytes(patch), "result_manifest_digest": canonical_digest(result), "verification_result_digest": canonical_digest(verification), "negative_evidence_digest": canonical_digest(negative), "definition_digest": summary["definition_digest"], "cohort_after_attachment": {"verified_tasks": summary["verified_tasks"], "pending_tasks": summary["pending_tasks"]}, "authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False}}
    write_json(output / "evidence-summary.json", evidence)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    reset_source(source)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, evaluator_plan_runner.EvaluatorPlanError, local_verifier.VerifierError, benchmark_cohort.CohortError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
