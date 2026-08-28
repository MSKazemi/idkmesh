#!/usr/bin/env python3
"""Run the first bounded evidence attempt for Phase B2 successor Task 001.

The benchmark definition is already frozen on main. This harness does not edit it.
It operates on an isolated checkout of the exact task source revision, proves the
seeded opaque-evidence bug is present before the candidate, materializes one
bounded single-worker baseline candidate, proves the seeded negative fails closed
after the candidate, packages a canonical ResultManifest, invokes the frozen
EvaluatorPlan v0.4 through the canonical metadata-only verifier, and emits a
separate canonical VerificationResult for the behavioral security negative.

The worker self-report and both verifier objects remain evidence only. This tool
has no canonical write, push, merge, approval, or automatic-selection authority.
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
TASK_ID = "benchmark/phase-b2-successor/001-negative-evidence-type-boundary"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-successor-five/work-units/task-001-negative-evidence-type-boundary.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-successor-five/evaluators/task-001-negative-evidence-type-boundary.evaluator-plan.json"
OPAQUE_FIXTURE_REL = "results/phase-b2-successor-task001-opaque-negative.json"
TOOL_VERSION = "0.1"

OLD_BLOCK = '''    if negative["evidence_type"] == "verification_result":
        validate_schema(value, VERIFICATION_RESULT_SCHEMA, f"{task['id']} negative VerificationResult")
        require(
            value["decision_support"]["recommendation"] != "accept_candidate",
            f"{task['id']}: negative VerificationResult unexpectedly recommends acceptance",
        )
        expected = negative["expected_category"]
        if expected in VERIFICATION_FINDING_CATEGORIES:
            categories = {finding["category"] for finding in value["findings"]}
            require(expected in categories, f"{task['id']}: negative evidence lacks expected {expected} finding")
'''

NEW_BLOCK = '''    if negative["expected_category"] in VERIFICATION_FINDING_CATEGORIES:
        require(
            negative["evidence_type"] == "verification_result",
            f"{task['id']}: canonical negative category requires VerificationResult evidence",
        )

    if negative["evidence_type"] != "verification_result":
        return

    validate_schema(value, VERIFICATION_RESULT_SCHEMA, f"{task['id']} negative VerificationResult")
    require(
        value["decision_support"]["recommendation"] != "accept_candidate",
        f"{task['id']}: negative VerificationResult unexpectedly recommends acceptance",
    )
    expected = negative["expected_category"]
    if expected in VERIFICATION_FINDING_CATEGORIES:
        categories = {finding["category"] for finding in value["findings"]}
        require(expected in categories, f"{task['id']}: negative evidence lacks expected {expected} finding")
'''


class AttemptError(RuntimeError):
    """Raised when the frozen attempt or its evidence drifts."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AttemptError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AttemptError(f"expected JSON object: {path}")
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
        raise AttemptError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def ensure_output_root(raw: str) -> Path:
    output = (ROOT / raw).resolve()
    try:
        relative = output.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise AttemptError("output root escapes control repository") from exc
    require(relative.parts and relative.parts[0] == "results", "output root must live under results/")
    return output


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source checkout must be clean")


def write_opaque_negative_fixture(source: Path) -> Path:
    """Create a schema-valid cohort whose canonical security negative uses opaque JSON."""

    code = r'''
import json
from pathlib import Path
import sys
sys.path.insert(0, "tools")
import benchmark_cohort as b
cohort = b._fixture_cohort()
evidence_path = Path("examples/results/phase0-smoke.result-manifest.json")
evidence = b.load_json(evidence_path)
negative = cohort["tasks"][0]["negative_case"]
negative.update({
    "description": "Opaque JSON must not establish a canonical security negative.",
    "expected_category": "security",
    "evidence_status": "verified",
    "evidence_type": "other",
    "evidence_path": evidence_path.as_posix(),
    "evidence_digest": b.canonical_digest(evidence),
})
print(json.dumps(cohort, indent=2, sort_keys=True))
'''
    proc = run([sys.executable, "-c", code], cwd=source)
    fixture = source / OPAQUE_FIXTURE_REL
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(proc.stdout + ("" if proc.stdout.endswith("\n") else "\n"), encoding="utf-8")
    return fixture


def run_opaque_negative_probe(source: Path) -> dict[str, Any]:
    fixture = write_opaque_negative_fixture(source)
    proc = run(
        [sys.executable, TARGET_REL, "validate", "--cohort", OPAQUE_FIXTURE_REL],
        cwd=source,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "accepted": proc.returncode == 0,
        "rejected_for_evidence_type": (
            proc.returncode == 2
            and "canonical negative category requires VerificationResult evidence" in proc.stderr
        ),
        "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
        "stderr_excerpt": proc.stderr.strip()[:400],
        "fixture_digest": canonical_digest(load_json(fixture)),
    }


def build_result_manifest(
    *,
    work_unit: dict[str, Any],
    patch_bytes: bytes,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    started_at: str,
    finished_at: str,
    elapsed: float,
) -> dict[str, Any]:
    required_validators = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    worker_config = {
        "tool_version": TOOL_VERSION,
        "structural_signature": "single-worker-baseline-v1",
        "source_revision": SOURCE_SHA,
        "transform": "category-aware-negative-evidence-boundary",
    }
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/single-worker-baseline-v1/attempt-001",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": "idkmesh-phase-b2-deterministic-baseline",
            "type": "system",
            "adapter": "bounded-source-transform",
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
                "description": "Unverified successor Task 001 candidate patch.",
            }
        ],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {
            "changed_path_count": 1,
            "baseline_negative_accepted": 1,
            "candidate_negative_rejected": 1,
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": "One bounded deterministic baseline candidate; self-report is not acceptance.",
            "claims": [
                "The frozen source accepted opaque security evidence before the candidate.",
                "The patched source rejects the same negative fixture before semantic evidence is trusted.",
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
                    "phase-b2-successor-task001-attempt": TOOL_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validators,
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Frozen EvaluatorPlan plus separate behavioral seeded-negative evidence required.",
        },
        "extensions": {
            "org.idkmesh.benchmark.structural_signature": "single-worker-baseline-v1",
            "org.idkmesh.authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        },
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, "Task 001 ResultManifest")
    return result


def build_negative_verification(
    *,
    work_unit: dict[str, Any],
    result: dict[str, Any],
    observation: dict[str, Any],
    plan_digest: str,
) -> dict[str, Any]:
    timestamp = utc_now()
    evidence_digest = canonical_digest(observation)
    verification = {
        "schema_version": "0.1",
        "id": "phase-b2-successor/task001/attempt-001/opaque-security-negative",
        "result_manifest_id": result["id"],
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": result["attempt"],
        "verifier": {
            "id": "idkmesh-seeded-negative-verifier",
            "type": "system",
            "adapter": "opaque-evidence-security-regression",
            "adapter_version": TOOL_VERSION,
        },
        "independence": {
            "independent_from_worker": True,
            "worker_id_observed": result["worker"]["id"],
            "shared_model_family": False,
            "shared_runtime": False,
            "correlation_notes": "Behavioral negative is evaluated separately from the worker transform and metadata-only patch verifier.",
        },
        "status": "failed",
        "started_at": timestamp,
        "finished_at": timestamp,
        "checks": [
            {
                "id": "opaque-security-evidence-rejected",
                "type": "policy",
                "required": True,
                "status": "failed",
                "summary": "Opaque non-VerificationResult evidence is rejected for a canonical security negative.",
                "evidence_ids": ["opaque-negative-observation"],
                "diagnostics": observation.get("stderr_excerpt", ""),
            }
        ],
        "evidence": [
            {
                "id": "opaque-negative-observation",
                "type": "test_output",
                "locator": "inline://phase-b2-successor-task001/opaque-negative",
                "digest": evidence_digest,
                "media_type": "application/json",
                "description": "Canonical digest of before/after opaque security-evidence regression observations.",
            }
        ],
        "findings": [
            {
                "severity": "high",
                "category": "security",
                "summary": "Seeded opaque security evidence is rejected unless it is a canonical VerificationResult.",
                "path": TARGET_REL,
            }
        ],
        "metrics": {
            "baseline_accepted": int(observation["baseline"]["accepted"]),
            "candidate_rejected": int(observation["candidate"]["rejected_for_evidence_type"]),
        },
        "resources": {
            "wall_seconds": 0.0,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "provenance": {
            "result_manifest_digest": canonical_digest(result),
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_SHA,
            "verifier_config_digest": plan_digest,
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {"opaque-evidence-security-regression": TOOL_VERSION},
            },
        },
        "decision_support": {
            "recommendation": "reject_candidate",
            "confidence": 1.0,
            "rationale": "This object represents the deliberately invalid opaque-evidence negative case, which must be rejected. It is not the acceptance verdict for the corrected candidate patch.",
        },
        "extensions": {
            "org.idkmesh.seeded_negative": True,
            "org.idkmesh.seeded_negative.expected_category": "security",
            "org.idkmesh.seeded_negative.candidate_fix_observed": True,
        },
    }
    local_verifier.validate_schema(
        verification,
        local_verifier.VERIFICATION_RESULT_SCHEMA,
        "Task 001 seeded-negative VerificationResult",
    )
    return verification


def materialize_attempt(source: Path, output_root: Path) -> dict[str, Any]:
    reset_source(source)
    work_unit = load_json(WORK_UNIT_PATH)
    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "Task 001 frozen plan must remain EvaluatorPlan v0.4")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "Task 001 plan source revision drift")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "Task 001 WorkUnit digest drift")
    plan_digest = canonical_digest(plan)

    baseline = run_opaque_negative_probe(source)
    require(baseline["accepted"] is True, "frozen source no longer demonstrates the seeded opaque-evidence bug")

    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    require(text.count(OLD_BLOCK) == 1, "expected exactly one legacy negative-evidence validation block")

    started_at = utc_now()
    started = time.monotonic()
    target.write_text(text.replace(OLD_BLOCK, NEW_BLOCK), encoding="utf-8")

    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"candidate does not compile: {compile_proc.stderr}")
    self_test = run([sys.executable, TARGET_REL, "self-test"], cwd=source, check=False)
    require(self_test.returncode == 0, f"candidate breaks benchmark cohort self-test: {self_test.stderr}")

    candidate_probe = run_opaque_negative_probe(source)
    require(
        candidate_probe["rejected_for_evidence_type"] is True,
        "candidate did not reject opaque evidence for canonical security category",
    )

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"candidate changed unexpected tracked paths: {changed}")
    patch_bytes = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout.encode("utf-8")
    require(bool(patch_bytes), "candidate patch is empty")

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    observation = {"baseline": baseline, "candidate": candidate_probe}
    stdout_bytes = (
        "structural_signature=single-worker-baseline-v1\n"
        "baseline_opaque_security_evidence_accepted=true\n"
        "candidate_opaque_security_evidence_rejected=true\n"
        f"self_test_returncode={self_test.returncode}\n"
    ).encode("utf-8")
    stderr_bytes = compile_proc.stderr.encode("utf-8") + self_test.stderr.encode("utf-8")

    candidate_root = output_root / "attempt-001"
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    candidate_root.mkdir(parents=True)
    (candidate_root / "candidate.patch").write_bytes(patch_bytes)
    (candidate_root / "stdout.txt").write_bytes(stdout_bytes)
    (candidate_root / "stderr.txt").write_bytes(stderr_bytes)
    write_json(candidate_root / "opaque-negative-observation.json", observation)

    result = build_result_manifest(
        work_unit=work_unit,
        patch_bytes=patch_bytes,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        started_at=started_at,
        finished_at=finished_at,
        elapsed=elapsed,
    )
    result_path = candidate_root / "result-manifest.json"
    write_json(result_path, result)

    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH,
        result_manifest_path=result_path,
        candidate_root=candidate_root,
        plan_path=PLAN_PATH,
    )
    require(verification["status"] == "passed", "frozen v0.4 evaluator rejected candidate")
    require(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        "frozen v0.4 evaluator did not support candidate",
    )
    require(
        verification["provenance"]["verifier_config_digest"] == plan_digest,
        "candidate VerificationResult lost exact frozen plan digest",
    )
    write_json(candidate_root / "verification-result.json", verification)

    negative_verification = build_negative_verification(
        work_unit=work_unit,
        result=result,
        observation=observation,
        plan_digest=plan_digest,
    )
    write_json(candidate_root / "seeded-negative.verification-result.json", negative_verification)

    summary = {
        "schema_version": "0.1",
        "cohort_id": "benchmark/phase-b2-successor-five",
        "cohort_definition_digest": "sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "structural_signature": "single-worker-baseline-v1",
        "result_manifest_digest": canonical_digest(result),
        "verification_result_digest": canonical_digest(verification),
        "seeded_negative_verification_result_digest": canonical_digest(negative_verification),
        "candidate_patch_digest": sha256_bytes(patch_bytes),
        "frozen_evaluator_plan_digest": plan_digest,
        "candidate_verification_status": verification["status"],
        "candidate_recommendation": verification["decision_support"]["recommendation"],
        "baseline_seeded_negative_accepted": baseline["accepted"],
        "candidate_seeded_negative_rejected": candidate_probe["rejected_for_evidence_type"],
        "seeded_negative_category": "security",
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    write_json(candidate_root / "attempt-summary.json", summary)

    print("IDKMESH_PHASE_B2_TASK001_PATCH_BEGIN")
    print(patch_bytes.decode("utf-8"), end="" if patch_bytes.endswith(b"\n") else "\n")
    print("IDKMESH_PHASE_B2_TASK001_PATCH_END")
    for label, value in (
        ("RESULT_MANIFEST", result),
        ("VERIFICATION_RESULT", verification),
        ("SEEDED_NEGATIVE_VERIFICATION_RESULT", negative_verification),
        ("ATTEMPT_SUMMARY", summary),
    ):
        print(f"IDKMESH_PHASE_B2_TASK001_{label}_BEGIN")
        print(json.dumps(value, indent=2, sort_keys=True))
        print(f"IDKMESH_PHASE_B2_TASK001_{label}_END")

    reset_source(source)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/benchmarks/phase-b2-successor-five/task-001",
        help="Control-repository-relative output root under results/.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    require(source.is_dir(), f"source checkout missing: {source}")
    reset_source(source)
    output_root = ensure_output_root(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    materialize_attempt(source, output_root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AttemptError,
        OSError,
        json.JSONDecodeError,
        evaluator_plan_runner.EvaluatorPlanError,
        local_verifier.VerifierError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
