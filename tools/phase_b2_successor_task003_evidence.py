#!/usr/bin/env python3
"""Generate source-bound evidence for frozen Phase B2 successor Task 003.

The worker modifies only an isolated checkout of the immutable task source. The
bound metadata verifier does not execute candidate code; a separate behavioral
probe checks that the new command emits exactly the pre-outcome projection and
does not leak mutable evidence fields. Nothing in this harness can write, push,
merge, or select a candidate in the canonical repository.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import platform
import shutil
import sys
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
TASK_ID = "benchmark/phase-b2/003-definition-json-command"
STRUCTURAL_SIGNATURE = "single-worker-baseline-v1"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-003-definition-json-command.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-five/evaluators/task-003-definition-json-command.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-five/cohort.json"
FIXTURE_REL = "results/phase-b2-task003-cohort.json"
WORKER_VERSION = "0.1"

FUNCTION_ANCHOR = "\n\ndef cmd_self_test(_: argparse.Namespace) -> int:\n"
FUNCTION_INSERT = '''

def cmd_definition_json(args: argparse.Namespace) -> int:
    """Print the canonical pre-outcome projection committed by the digest."""

    cohort = load_json((ROOT / args.cohort).resolve())
    validate_schema(cohort, COHORT_SCHEMA, "BenchmarkCohort")
    print(json.dumps(definition_projection(cohort), indent=2, sort_keys=True))
    return 0
'''
PARSER_ANCHOR = '''    digest.set_defaults(func=cmd_definition_digest)

    self_test = subparsers.add_parser("self-test", help="Run deterministic contract and drift tests.")
'''
PARSER_REPLACEMENT = '''    digest.set_defaults(func=cmd_definition_digest)

    definition_json = subparsers.add_parser(
        "definition-json",
        help="Print the canonical pre-outcome benchmark definition as JSON.",
    )
    definition_json.add_argument("--cohort", required=True)
    definition_json.set_defaults(func=cmd_definition_json)

    self_test = subparsers.add_parser("self-test", help="Run deterministic contract and drift tests.")
'''


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def write_fixture(source: Path) -> Path:
    code = (
        "import json,sys; sys.path.insert(0,'tools'); import benchmark_cohort as b; "
        "print(json.dumps(b._fixture_cohort(),indent=2,sort_keys=True))"
    )
    proc = run([sys.executable, "-c", code], cwd=source)
    fixture = source / FIXTURE_REL
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(proc.stdout, encoding="utf-8")
    return fixture


def projection_leaks_outcomes(value: dict[str, Any]) -> bool:
    forbidden_root = {"stage", "definition_digest", "extensions"}
    if forbidden_root.intersection(value):
        return True
    return any("evidence" in task for task in value.get("tasks", []))


def apply_worker_transformation(source: Path) -> tuple[bytes, bytes, bytes, float, str, str, dict[str, Any]]:
    fixture = write_fixture(source)
    baseline = run(
        [sys.executable, TARGET_REL, "definition-json", "--cohort", FIXTURE_REL],
        cwd=source,
        check=False,
    )
    require(baseline.returncode == 2, "frozen source unexpectedly exposes definition-json")
    require("invalid choice" in baseline.stderr, "baseline failed for an unrelated reason")

    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require("def cmd_definition_json(" not in text, "definition-json already exists in frozen source")
    require(text.count(FUNCTION_ANCHOR) == 1, "definition-json function anchor drift")
    require(text.count(PARSER_ANCHOR) == 1, "definition-json parser anchor drift")

    started_at = utc_now()
    started = time.monotonic()
    text = text.replace(FUNCTION_ANCHOR, FUNCTION_INSERT + FUNCTION_ANCHOR)
    text = text.replace(PARSER_ANCHOR, PARSER_REPLACEMENT)
    target.write_text(text, encoding="utf-8")

    compile_result = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_result.returncode == 0, f"candidate does not compile: {compile_result.stderr}")
    self_test = run([sys.executable, TARGET_REL, "self-test"], cwd=source, check=False)
    require(self_test.returncode == 0, f"candidate self-test failed: {self_test.stderr}")

    projection_result = run(
        [sys.executable, TARGET_REL, "definition-json", "--cohort", FIXTURE_REL],
        cwd=source,
        check=False,
    )
    require(projection_result.returncode == 0, f"definition-json failed: {projection_result.stderr}")
    projection = json_loads_object(projection_result.stdout)
    require(not projection_leaks_outcomes(projection), "definition-json leaked mutable outcome fields")

    digest_result = run(
        [sys.executable, TARGET_REL, "definition-digest", "--cohort", FIXTURE_REL],
        cwd=source,
    )
    require(
        canonical_digest(projection) == digest_result.stdout.strip(),
        "definition-json output does not match definition-digest",
    )

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"worker changed unexpected tracked paths: {changed}")
    patch_text = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout
    require("def cmd_definition_json(" in patch_text, "candidate patch lost command function")
    require("definition_projection(cohort)" in patch_text, "candidate patch lost canonical projection")

    bad_projection = copy.deepcopy(projection)
    bad_projection["tasks"][0]["evidence"] = {"status": "pending", "attempts": []}
    observation = {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "baseline_command_absent": True,
        "candidate_command_succeeded": True,
        "candidate_projection_digest_matches": True,
        "candidate_projection_leaks_outcomes": projection_leaks_outcomes(projection),
        "seeded_bad_projection_leaks_outcomes": projection_leaks_outcomes(bad_projection),
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    require(observation["seeded_bad_projection_leaks_outcomes"], "seeded negative was not detected")

    elapsed = max(0.0, time.monotonic() - started)
    stdout = (
        "Phase B2 Task 003 deterministic worker\n"
        f"source_revision={SOURCE_SHA}\n"
        "baseline_command_absent=true\n"
        "candidate_projection_digest_matches=true\n"
        "candidate_projection_leaks_outcomes=false\n"
        "source_self_test=passed\n"
    ).encode("utf-8")
    stderr = (compile_result.stderr + self_test.stderr + projection_result.stderr).encode("utf-8")
    return patch_text.encode("utf-8"), stdout, stderr, elapsed, started_at, utc_now(), observation


def json_loads_object(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    require(isinstance(value, dict), "expected JSON object from definition-json")
    return value


def build_result_manifest(
    *, work_unit: dict[str, Any], patch: bytes, stdout: bytes, stderr: bytes,
    elapsed: float, started_at: str, finished_at: str,
) -> dict[str, Any]:
    worker_config = {
        "tool_version": WORKER_VERSION,
        "source_revision": SOURCE_SHA,
        "structural_signature": STRUCTURAL_SIGNATURE,
        "transform": "add-read-only-definition-json-command",
    }
    required = sorted(v["id"] for v in work_unit["validators"] if v.get("required") is True)
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {"id": "idkmesh-phase-b2-task003-worker", "type": "system", "adapter": "deterministic-text-rewrite", "adapter_version": WORKER_VERSION},
        "status": "succeeded",
        "started_at": started_at,
        "finished_at": finished_at,
        "produced_artifacts": [{"id": "candidate-patch", "type": "patch", "locator": "candidate.patch", "digest": sha256_bytes(patch), "media_type": "text/x-diff", "description": "Unverified frozen-source Task 003 candidate patch."}],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr)},
        ],
        "metrics": {"changed_path_count": 1, "projection_outcome_field_count": 0},
        "resources": {"wall_seconds": elapsed, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "self_report": {"summary": "Deterministic baseline adds a read-only definition-json command; self-report is not acceptance.", "claims": ["Only the allowed tool was changed.", "The emitted projection matches definition-digest and excludes outcome fields.", "Worker success grants no integration authority."]},
        "provenance": {"work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "worker_config_digest": canonical_digest(worker_config), "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"phase-b2-task003-worker": WORKER_VERSION, "git": run(["git", "--version"], cwd=ROOT).stdout.strip()}}},
        "verification_request": {"expected_validator_ids": required, "evidence_artifact_ids": ["candidate-patch"], "notes": "Route through the frozen public EvaluatorPlan; worker self-report is not acceptance."},
        "extensions": {"org.idkmesh.benchmark.structural_signature": STRUCTURAL_SIGNATURE, "org.idkmesh.authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False}},
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, "Task 003 ResultManifest")
    return result


def build_negative_verification(
    *, work_unit: dict[str, Any], result: dict[str, Any], observation: dict[str, Any], plan_digest: str,
) -> dict[str, Any]:
    timestamp = utc_now()
    verification = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001/outcome-leak-negative",
        "result_manifest_id": result["id"],
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "verifier": {"id": "idkmesh-task003-behavior-verifier", "type": "system", "adapter": "definition-projection-boundary", "adapter_version": WORKER_VERSION},
        "independence": {"independent_from_worker": True, "worker_id_observed": result["worker"]["id"], "shared_model_family": False, "shared_runtime": False, "correlation_notes": "Behavioral projection inspection is separate from the text rewrite and metadata-only patch verifier."},
        "status": "failed",
        "started_at": timestamp,
        "finished_at": timestamp,
        "checks": [{"id": "outcome-fields-excluded", "type": "test", "required": True, "status": "failed", "summary": "A deliberately contaminated projection containing task evidence is rejected.", "evidence_ids": ["projection-boundary-observation"]}],
        "evidence": [{"id": "projection-boundary-observation", "type": "test_output", "locator": "behavior-observation.json", "digest": canonical_digest(observation), "media_type": "application/json", "description": "Digest of baseline, candidate, and seeded outcome-leak observations."}],
        "findings": [{"severity": "high", "category": "correctness", "summary": "Seeded mutable outcome fields violate the pre-outcome projection contract.", "path": TARGET_REL}],
        "metrics": {"candidate_outcome_leak": 0, "seeded_negative_outcome_leak": 1},
        "resources": {"wall_seconds": 0.0, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "provenance": {"result_manifest_digest": canonical_digest(result), "work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "verifier_config_digest": plan_digest, "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"definition-projection-boundary": WORKER_VERSION}}},
        "decision_support": {"recommendation": "reject_candidate", "confidence": 1.0, "rationale": "This VerificationResult represents the deliberately invalid outcome-leaking projection, not the accepted candidate."},
        "extensions": {"org.idkmesh.seeded_negative": True, "org.idkmesh.seeded_negative.expected_category": "correctness"},
    }
    local_verifier.validate_schema(verification, local_verifier.VERIFICATION_RESULT_SCHEMA, "Task 003 negative VerificationResult")
    return verification


def attach_prospectively(
    *, result: dict[str, Any], result_path: Path, verification: dict[str, Any],
    verification_path: Path, negative: dict[str, Any], negative_path: Path,
) -> dict[str, Any]:
    cohort = load_json(COHORT_PATH)
    frozen_digest = cohort["definition_digest"]
    task = next((item for item in cohort["tasks"] if item["id"] == TASK_ID), None)
    require(task is not None, "active cohort lost Task 003")
    task["evidence"] = {"status": "verified", "attempts": [{
        "attempt_id": "attempt-001",
        "structural_signature": STRUCTURAL_SIGNATURE,
        "result_manifest": {"path": result_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(result), "id": result["id"]},
        "verification_result": {"path": verification_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(verification), "id": verification["id"]},
        "outcome": "support",
    }]}
    task["negative_case"].update({"evidence_status": "verified", "evidence_type": "verification_result", "evidence_path": negative_path.relative_to(ROOT).as_posix(), "evidence_digest": canonical_digest(negative)})
    summary = benchmark_cohort.validate_cohort(cohort)
    require(summary["definition_digest"] == frozen_digest, "Task 003 attachment changed frozen definition digest")
    require(summary["verified_tasks"] == 2 and summary["pending_tasks"] == 3, "unexpected prospective cohort counts")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", default="results/benchmarks/phase-b2-successor-five/task-003/attempt-001")
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
    require(work_unit["id"] == TASK_ID, "Task 003 WorkUnit id drift")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "Task 003 source binding drift")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "Task 003 WorkUnit digest drift")
    require(plan["execution_mode"] == "metadata_only", "Task 003 evaluator must remain metadata-only")

    patch, stdout, stderr, elapsed, started_at, finished_at, observation = apply_worker_transformation(source)
    (output / "candidate.patch").write_bytes(patch)
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    write_json(output / "behavior-observation.json", observation)

    result = build_result_manifest(work_unit=work_unit, patch=patch, stdout=stdout, stderr=stderr, elapsed=elapsed, started_at=started_at, finished_at=finished_at)
    result_path = output / "result-manifest.json"
    write_json(result_path, result)
    verification = evaluator_plan_runner.run_fixture(work_unit_path=WORK_UNIT_PATH, result_manifest_path=result_path, candidate_root=output, plan_path=PLAN_PATH)
    require(verification["status"] == "passed", "frozen Task 003 evaluator rejected candidate")
    require(verification["decision_support"]["recommendation"] == "accept_candidate", "Task 003 verifier did not support candidate")
    verification_path = output / "verification-result.json"
    write_json(verification_path, verification)

    negative = build_negative_verification(work_unit=work_unit, result=result, observation=observation, plan_digest=canonical_digest(plan))
    negative_path = output / "seeded-negative.verification-result.json"
    write_json(negative_path, negative)
    summary = attach_prospectively(result=result, result_path=result_path, verification=verification, verification_path=verification_path, negative=negative, negative_path=negative_path)
    evidence = {"schema_version": "0.1", "task_id": TASK_ID, "source_revision": SOURCE_SHA, "structural_signature": STRUCTURAL_SIGNATURE, "candidate_patch_digest": sha256_bytes(patch), "result_manifest_digest": canonical_digest(result), "verification_result_digest": canonical_digest(verification), "negative_evidence_digest": canonical_digest(negative), "definition_digest": summary["definition_digest"], "cohort_after_attachment": {"verified_tasks": summary["verified_tasks"], "pending_tasks": summary["pending_tasks"]}, "authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False}}
    write_json(output / "evidence-summary.json", evidence)
    print_json(evidence)
    reset_source(source)
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        EvidenceError,
        evaluator_plan_runner.EvaluatorPlanError,
        local_verifier.VerifierError,
        benchmark_cohort.CohortError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
