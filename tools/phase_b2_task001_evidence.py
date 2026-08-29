#!/usr/bin/env python3
"""Generate worker-neutral Phase B2 evidence for frozen benchmark Task 001.

The benchmark definition is already frozen. This harness does not rewrite that
pre-outcome definition. It checks out the exact frozen source separately,
performs one deterministic single-worker baseline transformation, packages the
candidate as canonical ResultManifest v0.1, routes it through the already-bound
EvaluatorPlan v0.2 metadata-only verifier, exercises the seeded unsafe-path
negative case, and proves that the resulting evidence can be attached without
changing the benchmark definition digest.

The harness has no repository write/push/merge/selection authority.
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

# tools/ is already sys.path[0] when this file is executed directly.
import benchmark_cohort  # noqa: E402

SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/001-cohort-path-boundary"
STRUCTURAL_SIGNATURE = "single-worker-baseline-v1"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-001-cohort-path-boundary.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-first-five/evaluators/task-001-cohort-path-boundary.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-first-five/cohort.json"
TARGET_REL = "tools/benchmark_cohort.py"
OLD_LINE = "    cohort = load_json((ROOT / args.cohort).resolve())"
NEW_LINE = "    cohort = load_json(resolve_repo_file(args.cohort, label=\"BenchmarkCohort\"))"
WORKER_ID = "idkmesh-phase-b2-task001-deterministic-worker"
WORKER_VERSION = "0.1"


class EvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceError(f"expected JSON object: {path}")
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
        raise EvidenceError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def ensure_results_output(raw: str) -> Path:
    output = (ROOT / raw).resolve()
    try:
        relative = output.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise EvidenceError("output root escapes evaluator repository") from exc
    require(relative.parts and relative.parts[0] == "results", "output root must live under results/")
    return output


def apply_worker_transformation(source: Path) -> tuple[bytes, str, str, float, str, str]:
    target = source / TARGET_REL
    require(target.is_file(), f"frozen source is missing {TARGET_REL}")
    text = target.read_text(encoding="utf-8")
    count = text.count(OLD_LINE)
    require(count == 2, f"expected exactly two vulnerable cohort loaders, found {count}")

    started_at = utc_now()
    started = time.monotonic()
    target.write_text(text.replace(OLD_LINE, NEW_LINE), encoding="utf-8")

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"worker changed unexpected paths: {changed}")

    patch_text = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout
    patch_bytes = patch_text.encode("utf-8")
    require(bool(patch_bytes), "worker produced an empty candidate patch")
    require(NEW_LINE.strip() in patch_text, "candidate patch lost the intended repository-bound resolver")

    self_test = run([sys.executable, TARGET_REL, "self-test"], cwd=source, check=False)
    require(
        self_test.returncode == 0,
        f"patched frozen source self-test failed:\n{self_test.stdout}\n{self_test.stderr}",
    )

    elapsed = max(0.0, time.monotonic() - started)
    finished_at = utc_now()
    stdout = (
        "Phase B2 Task 001 deterministic worker\n"
        f"source_revision={SOURCE_SHA}\n"
        f"target={TARGET_REL}\n"
        f"replacement_count={count}\n"
        "source_self_test=passed\n\n"
        + self_test.stdout
    )
    stderr = self_test.stderr
    return patch_bytes, stdout, stderr, elapsed, started_at, finished_at


def run_seeded_negative_checks(source: Path) -> dict[str, Any]:
    cases = [
        ("validate-absolute", ["validate", "--cohort", "/tmp/idkmesh-phase-b2-outside.json"]),
        (
            "definition-digest-absolute",
            ["definition-digest", "--cohort", "/tmp/idkmesh-phase-b2-outside.json"],
        ),
        ("validate-traversal", ["validate", "--cohort", "../outside.json"]),
        (
            "definition-digest-traversal",
            ["definition-digest", "--cohort", "../outside.json"],
        ),
    ]
    observations: list[dict[str, Any]] = []
    for case_id, args in cases:
        proc = run([sys.executable, TARGET_REL, *args], cwd=source, check=False)
        rejected = proc.returncode == 2 and "unsafe path" in proc.stderr
        observations.append(
            {
                "id": case_id,
                "arguments": args,
                "returncode": proc.returncode,
                "rejected_as_unsafe_path": rejected,
                "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
                "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
                "stderr_excerpt": proc.stderr.strip()[:500],
            }
        )
    passed = all(item["rejected_as_unsafe_path"] for item in observations)
    require(passed, "one or more absolute/traversal cohort paths did not fail closed as unsafe")
    return {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/seeded-negative-path-boundary",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "expected_category": "security",
        "description": "Absolute and traversal --cohort inputs are rejected by both public CLI entry points before file loading.",
        "passed": True,
        "checks": observations,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }


def build_result_manifest(
    *,
    work_unit: dict[str, Any],
    patch_bytes: bytes,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    elapsed: float,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    worker_config = {
        "schema_version": "0.1",
        "source_revision": SOURCE_SHA,
        "target": TARGET_REL,
        "replacement": {"from": OLD_LINE, "to": NEW_LINE, "expected_count": 2},
        "structural_signature": STRUCTURAL_SIGNATURE,
    }
    required_validator_ids = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/{STRUCTURAL_SIGNATURE}/attempt-001",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": WORKER_ID,
            "type": "system",
            "adapter": "deterministic-text-rewrite",
            "adapter_version": WORKER_VERSION,
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
                "description": "Unverified frozen-source Task 001 candidate patch.",
            }
        ],
        "logs": [
            {
                "type": "stdout",
                "locator": "stdout.txt",
                "digest": sha256_bytes(stdout_bytes),
            },
            {
                "type": "stderr",
                "locator": "stderr.txt",
                "digest": sha256_bytes(stderr_bytes),
            },
        ],
        "metrics": {
            "replacement_count": 2,
            "changed_path_count": 1,
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": "Deterministic baseline replaced only the two direct --cohort path loaders with the existing repository-bounded resolver; candidate remains unverified until the independent evaluator runs.",
            "claims": [
                "Exactly one repository path was changed in the frozen source checkout.",
                "No benchmark definition, evaluator plan, schema, workflow, or verification control file was changed by the worker.",
                "Worker success is not acceptance or merge authority.",
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
                    "phase-b2-task001-worker": WORKER_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids,
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Route through the frozen public EvaluatorPlan v0.2; no worker self-acceptance.",
        },
        "extensions": {
            "org.idkmesh.benchmark.task_id": TASK_ID,
            "org.idkmesh.benchmark.structural_signature": STRUCTURAL_SIGNATURE,
            "org.idkmesh.benchmark.worker_mode": "deterministic_single_worker_baseline",
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
        "Task 001 ResultManifest",
    )
    return result


def prospective_cohort(
    *,
    result: dict[str, Any],
    result_path: Path,
    verification: dict[str, Any],
    verification_path: Path,
    negative: dict[str, Any],
    negative_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cohort = load_json(COHORT_PATH)
    frozen_digest = cohort["definition_digest"]
    derived = copy.deepcopy(cohort)
    matches = [task for task in derived["tasks"] if task["id"] == TASK_ID]
    require(len(matches) == 1, "frozen cohort does not contain exactly one Task 001")
    task = matches[0]
    task["evidence"] = {
        "status": "verified",
        "attempts": [
            {
                "attempt_id": "attempt-001",
                "structural_signature": STRUCTURAL_SIGNATURE,
                "result_manifest": {
                    "path": repo_relative(result_path),
                    "digest": canonical_digest(result),
                    "id": result["id"],
                },
                "verification_result": {
                    "path": repo_relative(verification_path),
                    "digest": canonical_digest(verification),
                    "id": verification["id"],
                },
                "outcome": "support",
            }
        ],
    }
    task["negative_case"].update(
        {
            "evidence_status": "verified",
            "evidence_type": "other",
            "evidence_path": repo_relative(negative_path),
            "evidence_digest": canonical_digest(negative),
        }
    )

    summary = benchmark_cohort.validate_cohort(derived, require_evidence=False)
    require(summary["verified_tasks"] == 1, "prospective cohort did not validate Task 001 evidence")
    require(summary["pending_tasks"] == 4, "prospective cohort changed another task's evidence state")
    require(
        summary["definition_digest"] == frozen_digest,
        "attaching Task 001 evidence changed the frozen pre-outcome definition digest",
    )
    return derived, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Checkout of exact frozen source revision.")
    parser.add_argument(
        "--output-root",
        default="results/benchmarks/phase-b2-first-five/task-001/single-worker-baseline-v1",
        help="Evaluator-repository-relative output root under results/.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    require(source.is_dir(), f"source checkout does not exist: {source}")
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    require(actual_sha == SOURCE_SHA, f"frozen source SHA drift: {actual_sha}")
    require(
        run(["git", "status", "--porcelain"], cwd=source).stdout == "",
        "frozen source checkout is not clean before worker execution",
    )

    output_root = ensure_results_output(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    candidate_root = output_root / "attempt-001"
    candidate_root.mkdir(parents=True)

    work_unit = load_json(WORK_UNIT_PATH)
    plan = load_json(PLAN_PATH)
    require(work_unit["id"] == TASK_ID, "Task 001 WorkUnit id drift")
    require(work_unit["provenance"]["source_revision"] == SOURCE_SHA, "WorkUnit source revision drift")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "EvaluatorPlan source revision drift")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "EvaluatorPlan WorkUnit digest drift")
    require(plan["execution_mode"] == "metadata_only", "Task 001 evaluator must remain metadata-only")

    patch_bytes, stdout, stderr, elapsed, started_at, finished_at = apply_worker_transformation(source)
    stdout_bytes = stdout.encode("utf-8")
    stderr_bytes = stderr.encode("utf-8")
    (candidate_root / "candidate.patch").write_bytes(patch_bytes)
    (candidate_root / "stdout.txt").write_bytes(stdout_bytes)
    (candidate_root / "stderr.txt").write_bytes(stderr_bytes)

    result = build_result_manifest(
        work_unit=work_unit,
        patch_bytes=patch_bytes,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        elapsed=elapsed,
        started_at=started_at,
        finished_at=finished_at,
    )
    result_path = candidate_root / "result-manifest.json"
    write_json(result_path, result)

    negative = run_seeded_negative_checks(source)
    negative_path = output_root / "negative-evidence.json"
    write_json(negative_path, negative)

    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH,
        result_manifest_path=result_path,
        candidate_root=candidate_root,
        plan_path=PLAN_PATH,
    )
    require(verification["status"] == "passed", "independent Task 001 verification did not pass")
    require(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        "independent Task 001 verifier did not support the candidate",
    )
    require(
        verification["provenance"]["verifier_config_digest"] == canonical_digest(plan),
        "VerificationResult lost exact frozen EvaluatorPlan digest",
    )
    verification_path = output_root / "verification-result.json"
    write_json(verification_path, verification)

    derived_cohort, cohort_summary = prospective_cohort(
        result=result,
        result_path=result_path,
        verification=verification,
        verification_path=verification_path,
        negative=negative,
        negative_path=negative_path,
    )
    prospective_path = output_root / "prospective-cohort.json"
    write_json(prospective_path, derived_cohort)

    evidence = {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "structural_signature": STRUCTURAL_SIGNATURE,
        "work_unit_digest": canonical_digest(work_unit),
        "evaluator_plan_digest": canonical_digest(plan),
        "candidate_patch_digest": sha256_bytes(patch_bytes),
        "result_manifest_digest": canonical_digest(result),
        "verification_result_digest": canonical_digest(verification),
        "negative_evidence_digest": canonical_digest(negative),
        "definition_digest_before": load_json(COHORT_PATH)["definition_digest"],
        "definition_digest_after_attachment": cohort_summary["definition_digest"],
        "definition_digest_unchanged": True,
        "outcome": "support",
        "negative_case_passed": True,
        "cohort_after_attachment": {
            "verified_tasks": cohort_summary["verified_tasks"],
            "pending_tasks": cohort_summary["pending_tasks"],
        },
        "human_decision": {
            "status": "pending",
            "integration_authority": "external_human_or_governance",
        },
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    evidence_path = output_root / "evidence-summary.json"
    write_json(evidence_path, evidence)

    markdown = f"""# Phase B2 Task 001 evidence\n\n- source revision: `{SOURCE_SHA}`\n- structural signature: `{STRUCTURAL_SIGNATURE}`\n- candidate patch: `{evidence['candidate_patch_digest']}`\n- ResultManifest: `{evidence['result_manifest_digest']}`\n- independent VerificationResult: `{evidence['verification_result_digest']}`\n- verifier recommendation: **accept_candidate**\n- seeded unsafe-path negative checks: **passed**\n- frozen definition digest unchanged: **yes** (`{evidence['definition_digest_before']}`)\n- cohort state if attached: **1 verified / 4 pending**\n- human integration decision: **pending**\n\nThe metadata-only evaluator did not execute candidate code. The separate seeded-negative regression check executed only the controlled frozen repository tool after the deterministic patch was applied. This evidence grants no write, push, merge, or automatic candidate-selection authority.\n"""
    (output_root / "evidence-summary.md").write_text(markdown, encoding="utf-8")

    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, evaluator_plan_runner.EvaluatorPlanError, local_verifier.VerifierError, benchmark_cohort.CohortError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
