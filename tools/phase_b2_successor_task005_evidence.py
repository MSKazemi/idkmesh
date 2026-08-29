#!/usr/bin/env python3
"""Generate source-bound evidence for frozen Phase B2 successor Task 005."""

from __future__ import annotations

import argparse
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
TASK_ID = "benchmark/phase-b2/005-first-five-freeze-checklist"
STRUCTURAL_SIGNATURE = "single-worker-baseline-v1"
TARGET_REL = "docs/specifications/BENCHMARK_COHORT_V0_1.md"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-005-first-five-freeze-checklist.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-five/evaluators/task-005-first-five-freeze-checklist.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-successor-five/cohort.json"
WORKER_VERSION = "0.1"

ANCHOR = "\n## CLI\n"
CHECKLIST = '''
## First-five freeze checklist

Before freezing the first five-task Phase B2 cohort:

- Pin every task to a full 40-character immutable source SHA.
- Cover five distinct task families and meet `minimum_final_tasks` without duplicating a WorkUnit.
- Bind each canonical WorkUnit and EvaluatorPlan by id, version, digest, source revision, backend, and required validators.
- Inspect `definition-json`. Record the frozen `definition_digest` and reproduce it with `definition-digest`.
- Confirm every attempt and seeded-negative evidence field is still `pending`; do not tune the definition after observing a candidate.
- Keep canonical writes, Git push, merge, and automatic candidate selection set to `false`.
- Run `validate` and obtain review of the frozen definition before generating scored attempts.

If later evidence exposes a definition or evaluator defect, preserve the record and burn or supersede the cohort. Never rewrite a frozen commitment to fit an observed outcome.
'''


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout is not clean")


def authority_language_violation(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    forbidden = (
        "verifier support grants integration authority",
        "benchmark inclusion grants integration authority",
        "benchmark inclusion authorizes merge",
        "automatically merge",
        "automatic merge approval",
    )
    return any(phrase in normalized for phrase in forbidden)


def checklist_complete(text: str) -> bool:
    required = (
        "## First-five freeze checklist",
        "full 40-character immutable source SHA",
        "five distinct task families",
        "WorkUnit and EvaluatorPlan",
        "Record the frozen `definition_digest`",
        "evidence field is still `pending`",
        "automatic candidate selection set to `false`",
        "Run `validate`",
    )
    return all(fragment in text for fragment in required)


def apply_worker_transformation(source: Path) -> tuple[bytes, bytes, bytes, float, str, str, dict[str, Any]]:
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require("## First-five freeze checklist" not in text, "Task 005 already exists in frozen source")
    require(text.count(ANCHOR) == 1, "Task 005 insertion anchor drift")
    started_at = utc_now()
    started = time.monotonic()
    candidate_text = text.replace(ANCHOR, "\n" + CHECKLIST + ANCHOR)
    target.write_text(candidate_text, encoding="utf-8")
    require(checklist_complete(candidate_text), "candidate checklist omits a required freeze gate")
    require(not authority_language_violation(candidate_text), "candidate checklist grants integration authority")

    seeded_text = candidate_text + "\nVerifier support grants integration authority and can automatically merge the candidate.\n"
    seeded_violation = authority_language_violation(seeded_text)
    require(seeded_violation, "seeded authority-language violation was not detected")

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"worker changed unexpected tracked paths: {changed}")
    patch_text = run(["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL], cwd=source).stdout
    require("## First-five freeze checklist" in patch_text, "candidate patch lost checklist heading")
    require("Record the frozen `definition_digest`" in patch_text, "candidate patch lost digest gate")

    observation = {
        "schema_version": "0.1", "task_id": TASK_ID, "source_revision": SOURCE_SHA,
        "candidate_checklist_complete": True, "candidate_authority_violation": False,
        "seeded_authority_violation": seeded_violation,
        "required_gate_count": 8,
        "authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False},
    }
    elapsed = max(0.0, time.monotonic() - started)
    stdout = (
        "Phase B2 Task 005 deterministic worker\n"
        f"source_revision={SOURCE_SHA}\n"
        "checklist_complete=true\n"
        "candidate_authority_violation=false\n"
        "seeded_authority_violation=true\n"
    ).encode("utf-8")
    return patch_text.encode("utf-8"), stdout, b"", elapsed, started_at, utc_now(), observation


def build_result_manifest(*, work_unit: dict[str, Any], patch: bytes, stdout: bytes, stderr: bytes, elapsed: float, started_at: str, finished_at: str) -> dict[str, Any]:
    worker_config = {"tool_version": WORKER_VERSION, "source_revision": SOURCE_SHA, "structural_signature": STRUCTURAL_SIGNATURE, "transform": "add-first-five-freeze-checklist"}
    required = sorted(v["id"] for v in work_unit["validators"] if v.get("required") is True)
    result = {
        "schema_version": "0.1", "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001",
        "work_unit_id": work_unit["id"], "work_unit_version": work_unit["version"], "attempt": 1,
        "worker": {"id": "idkmesh-phase-b2-task005-worker", "type": "system", "adapter": "deterministic-document-rewrite", "adapter_version": WORKER_VERSION},
        "status": "succeeded", "started_at": started_at, "finished_at": finished_at,
        "produced_artifacts": [{"id": "candidate-patch", "type": "patch", "locator": "candidate.patch", "digest": sha256_bytes(patch), "media_type": "text/x-diff", "description": "Unverified frozen-source Task 005 candidate patch."}],
        "logs": [{"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout)}, {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr)}],
        "metrics": {"changed_path_count": 1, "documented_freeze_gates": 8, "candidate_authority_violations": 0},
        "resources": {"wall_seconds": elapsed, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "self_report": {"summary": "Deterministic baseline adds the first-five freeze checklist; self-report is not acceptance.", "claims": ["Only the allowed specification was changed.", "All required pre-outcome gates are explicit.", "The checklist denies automatic integration authority."]},
        "provenance": {"work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "worker_config_digest": canonical_digest(worker_config), "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"phase-b2-task005-worker": WORKER_VERSION, "git": run(["git", "--version"], cwd=ROOT).stdout.strip()}}},
        "verification_request": {"expected_validator_ids": required, "evidence_artifact_ids": ["candidate-patch"], "notes": "Route through the frozen public EvaluatorPlan; worker self-report is not acceptance."},
        "extensions": {"org.idkmesh.benchmark.structural_signature": STRUCTURAL_SIGNATURE, "org.idkmesh.authority": {"canonical_state_write": False, "git_push": False, "merge": False, "automatic_candidate_selection": False}},
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, "Task 005 ResultManifest")
    return result


def build_negative_verification(*, work_unit: dict[str, Any], result: dict[str, Any], observation: dict[str, Any], plan_digest: str) -> dict[str, Any]:
    timestamp = utc_now()
    verification = {
        "schema_version": "0.1", "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001/authority-language",
        "result_manifest_id": result["id"], "work_unit_id": work_unit["id"], "work_unit_version": work_unit["version"], "attempt": 1,
        "verifier": {"id": "idkmesh-task005-behavior-verifier", "type": "system", "adapter": "integration-authority-language", "adapter_version": WORKER_VERSION},
        "independence": {"independent_from_worker": True, "worker_id_observed": result["worker"]["id"], "shared_model_family": False, "shared_runtime": True, "correlation_notes": "The deterministic language probe is separate from document generation but runs in the same controlled harness."},
        "status": "failed", "started_at": timestamp, "finished_at": timestamp,
        "checks": [{"id": "no-automatic-integration-authority", "type": "test", "required": True, "status": "failed", "summary": "The deliberately contaminated checklist claims verifier-granted automatic merge authority.", "evidence_ids": ["behavior-observation"]}],
        "evidence": [{"id": "behavior-observation", "type": "test_output", "locator": "behavior-observation.json", "digest": canonical_digest(observation), "media_type": "application/json", "description": "Digest of checklist completeness and seeded authority-language observations."}],
        "findings": [{"severity": "high", "category": "correctness", "summary": "Verifier support must not grant automatic integration authority.", "path": TARGET_REL}],
        "metrics": {"candidate_authority_violations": 0, "seeded_authority_violations": 1},
        "resources": {"wall_seconds": 0.0, "compute_units": 0.0, "human_minutes": 0.0, "tokens": 0},
        "provenance": {"result_manifest_digest": canonical_digest(result), "work_unit_digest": canonical_digest(work_unit), "source_revision": SOURCE_SHA, "verifier_config_digest": plan_digest, "environment": {"platform": platform.platform(), "python": platform.python_version(), "tool_versions": {"integration-authority-language": WORKER_VERSION}}},
        "decision_support": {"recommendation": "reject_candidate", "confidence": 1.0, "rationale": "This VerificationResult records the deliberately contaminated seeded text, not the accepted candidate."},
        "extensions": {"org.idkmesh.seeded_negative": True, "org.idkmesh.seeded_negative.expected_category": "correctness"},
    }
    local_verifier.validate_schema(verification, local_verifier.VERIFICATION_RESULT_SCHEMA, "Task 005 negative VerificationResult")
    return verification


def attach_prospectively(*, result: dict[str, Any], result_path: Path, verification: dict[str, Any], verification_path: Path, negative: dict[str, Any], negative_path: Path) -> dict[str, Any]:
    cohort = load_json(COHORT_PATH)
    frozen_digest = cohort["definition_digest"]
    task = next((item for item in cohort["tasks"] if item["id"] == TASK_ID), None)
    require(task is not None, "active cohort lost Task 005")
    task["evidence"] = {"status": "verified", "attempts": [{"attempt_id": "attempt-001", "structural_signature": STRUCTURAL_SIGNATURE, "result_manifest": {"path": result_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(result), "id": result["id"]}, "verification_result": {"path": verification_path.relative_to(ROOT).as_posix(), "digest": canonical_digest(verification), "id": verification["id"]}, "outcome": "support"}]}
    task["negative_case"].update({"evidence_status": "verified", "evidence_type": "verification_result", "evidence_path": negative_path.relative_to(ROOT).as_posix(), "evidence_digest": canonical_digest(negative)})
    summary = benchmark_cohort.validate_cohort(cohort, require_evidence=True)
    require(summary["definition_digest"] == frozen_digest, "Task 005 attachment changed frozen definition digest")
    require(summary["verified_tasks"] == 5 and summary["pending_tasks"] == 0, "first-five cohort is not complete")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", default="results/benchmarks/phase-b2-successor-five/task-005/attempt-001")
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
    require(work_unit["id"] == TASK_ID, "Task 005 WorkUnit id drift")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "Task 005 source binding drift")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "Task 005 WorkUnit digest drift")
    require(plan["execution_mode"] == "metadata_only", "Task 005 evaluator must remain metadata-only")
    patch, stdout, stderr, elapsed, started_at, finished_at, observation = apply_worker_transformation(source)
    (output / "candidate.patch").write_bytes(patch); (output / "stdout.txt").write_bytes(stdout); (output / "stderr.txt").write_bytes(stderr)
    write_json(output / "behavior-observation.json", observation)
    result = build_result_manifest(work_unit=work_unit, patch=patch, stdout=stdout, stderr=stderr, elapsed=elapsed, started_at=started_at, finished_at=finished_at)
    result_path = output / "result-manifest.json"; write_json(result_path, result)
    verification = evaluator_plan_runner.run_fixture(work_unit_path=WORK_UNIT_PATH, result_manifest_path=result_path, candidate_root=output, plan_path=PLAN_PATH)
    require(verification["status"] == "passed", "frozen Task 005 evaluator rejected candidate")
    require(verification["decision_support"]["recommendation"] == "accept_candidate", "Task 005 verifier did not support candidate")
    verification_path = output / "verification-result.json"; write_json(verification_path, verification)
    negative = build_negative_verification(work_unit=work_unit, result=result, observation=observation, plan_digest=canonical_digest(plan))
    negative_path = output / "seeded-negative.verification-result.json"; write_json(negative_path, negative)
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
