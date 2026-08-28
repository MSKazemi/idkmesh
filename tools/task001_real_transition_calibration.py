#!/usr/bin/env python3
"""Calibrate the merged EvaluatorPlan v0.4 transition verifier on real Task 001.

This experiment is deliberately post-burn. It does not rewrite the frozen Phase
B2 WorkUnit, old EvaluatorPlan, or definition digest. Instead it checks out the
exact original task source and constructs two fresh calibration candidates:

1. a straightforward repair that removes both vulnerable direct cohort loaders
   and routes both CLI commands through the repository-bounded resolver; and
2. a valid-Python inert decoy that merely mentions the safe resolver fragment
   while leaving both vulnerable loaders untouched.

The canonical metadata-only v0.4 verifier must support the straightforward
transition and reject the decoy. A separate evaluator-owned behavioral matrix
then proves that the straightforward candidate rejects absolute/traversal
cohort paths while the decoy still accepts them.
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

SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/001-cohort-path-boundary"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = (
    ROOT
    / "benchmarks/phase-b2-first-five/work-units/task-001-cohort-path-boundary.work-unit.json"
)
PLAN_PATH = (
    ROOT
    / "verification/fixtures/task001-real-transition-calibration-evaluator-plan-v0.4.json"
)
CONTROL_COHORT_PATH = ROOT / "benchmarks/phase-b2-first-five/cohort.json"
BURNED_DEFINITION_DIGEST = (
    "sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c"
)
OLD_LINE = "    cohort = load_json((ROOT / args.cohort).resolve())"
NEW_LINE = "    cohort = load_json(resolve_repo_file(args.cohort, label=\"BenchmarkCohort\"))"
DECOY_BLOCK = '\n\n_TASK001_EVALUATOR_DECOY = """\nresolve_repo_file(args.cohort\n"""\n'
TOOL_VERSION = "0.1"


class CalibrationError(RuntimeError):
    """Raised when calibration cannot preserve or distinguish its invariants."""


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


def verify_burned_control_plane() -> None:
    """Ensure this calibration cannot silently resurrect or rewrite the pilot."""

    require(CONTROL_COHORT_PATH.is_file(), "burned first-five cohort is missing")
    cohort = load_json(CONTROL_COHORT_PATH)
    require(cohort.get("id") == "benchmark/phase-b2-first-five", "burned cohort id drift")
    require(cohort.get("stage") == "burned", "first-five cohort is no longer burned")
    require(
        cohort.get("definition_digest") == BURNED_DEFINITION_DIGEST,
        "burned first-five definition digest drift",
    )
    require(
        len(cohort.get("tasks", [])) == 5
        and all(task.get("evidence", {}).get("status") == "excluded" for task in cohort["tasks"]),
        "burned first-five outcomes are no longer fully excluded",
    )


def reset_source(source: Path) -> None:
    run(["git", "reset", "--hard", SOURCE_SHA], cwd=source)
    run(["git", "clean", "-fdx"], cwd=source)
    require(
        run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA,
        "source SHA drift",
    )
    require(
        run(["git", "status", "--porcelain"], cwd=source).stdout == "",
        "source checkout is not clean",
    )


def frozen_source_scaffold_cohort(source: Path) -> dict[str, Any]:
    """Build a valid outside-path probe solely from frozen-source fixtures."""

    work_rel = "examples/work-units/patch-verifier-smoke.work-unit.json"
    plan_rel = "verification/fixtures/patch-smoke-evaluator-plan-v0.2.json"
    work_path = source / work_rel
    plan_path = source / plan_rel
    require(work_path.is_file(), f"frozen source lacks {work_rel}")
    require(plan_path.is_file(), f"frozen source lacks {plan_rel}")
    work = load_json(work_path)
    plan = load_json(plan_path)
    require(
        work.get("provenance", {}).get("source_revision")
        == plan.get("binding", {}).get("source_revision"),
        "frozen probe WorkUnit/EvaluatorPlan revision mismatch",
    )
    return {
        "schema_version": "0.1",
        "id": "benchmark/task001-outside-boundary-probe",
        "title": "Task 001 outside-path boundary probe",
        "description": (
            "Self-contained scaffold using only fixtures that existed at the exact "
            "frozen source revision. It is not benchmark evidence."
        ),
        "stage": "scaffold",
        "minimum_final_tasks": 5,
        "required_families": ["documentation_contract"],
        "taxonomy_frozen_before_outcomes": True,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
        "tasks": [
            {
                "id": "benchmark/task001-outside-boundary-probe/task-001",
                "family": "documentation_contract",
                "difficulty": "trivial",
                "split": "pilot",
                "source": {
                    "repository": "https://github.com/MSKazemi/idkmesh",
                    "revision": work["provenance"]["source_revision"],
                },
                "work_unit": {
                    "path": work_rel,
                    "digest": canonical_digest(work),
                    "id": work["id"],
                    "version": work["version"],
                },
                "evaluator": {
                    "visibility": "public",
                    "plan_id": plan["id"],
                    "plan_digest": canonical_digest(plan),
                    "backend": plan["backend"]["type"],
                    "plan_path": plan_rel,
                },
                "declared_structural_signatures": ["boundary-probe-v1"],
                "negative_case": {
                    "description": "Probe fixture only.",
                    "expected_category": "correctness",
                    "evidence_status": "pending",
                },
                "accounting": {"required_metrics": ["wall_seconds"]},
                "evidence": {"status": "pending", "attempts": []},
            }
        ],
    }


def outside_cohort_path(source: Path) -> Path:
    outside = source.parent / "idkmesh-task001-outside-cohort.json"
    write_json(outside, frozen_source_scaffold_cohort(source))
    return outside


def run_behavioral_boundary_matrix(source: Path) -> dict[str, Any]:
    outside = outside_cohort_path(source)
    traversal = f"../{outside.name}"
    cases = [
        ("validate-absolute", ["validate", "--cohort", str(outside.resolve())]),
        (
            "definition-digest-absolute",
            ["definition-digest", "--cohort", str(outside.resolve())],
        ),
        ("validate-traversal", ["validate", "--cohort", traversal]),
        ("definition-digest-traversal", ["definition-digest", "--cohort", traversal]),
    ]
    observations: list[dict[str, Any]] = []
    for case_id, arguments in cases:
        proc = run([sys.executable, TARGET_REL, *arguments], cwd=source, check=False)
        observations.append(
            {
                "id": case_id,
                "returncode": proc.returncode,
                "rejected_as_unsafe_path": proc.returncode == 2 and "unsafe path" in proc.stderr,
                "accepted": proc.returncode == 0,
                "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
                "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
                "stderr_excerpt": proc.stderr.strip()[:300],
            }
        )
    outside.unlink(missing_ok=True)
    return {
        "schema_version": "0.1",
        "task_id": TASK_ID,
        "source_revision": SOURCE_SHA,
        "checks": observations,
        "all_rejected_as_unsafe_path": all(
            item["rejected_as_unsafe_path"] for item in observations
        ),
        "all_accepted": all(item["accepted"] for item in observations),
    }


def build_result_manifest(
    *,
    work_unit: dict[str, Any],
    candidate_id: str,
    worker_id: str,
    worker_adapter: str,
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
        "id": f"{TASK_ID}/real-v04-calibration/{candidate_id}",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": worker_id,
            "type": "system",
            "adapter": worker_adapter,
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
                "description": "Post-burn Task 001 real-source calibration candidate patch.",
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
            "summary": (
                "Calibration candidate generated from exact frozen Task 001 source; "
                "worker success is not acceptance."
            ),
            "claims": [
                f"objective_satisfied={str(objective_satisfied).lower()}",
                "Canonical v0.4 verification and the separate behavioral matrix decide calibration outcomes.",
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
                    "task001-real-transition-calibration": TOOL_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids,
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Post-burn evaluator calibration only; no integration authority.",
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
    target = source / TARGET_REL
    text = target.read_text(encoding="utf-8")
    started_at = utc_now()
    started = time.monotonic()

    if transform == "straightforward":
        count = text.count(OLD_LINE)
        require(count == 2, f"expected two vulnerable loaders, found {count}")
        target.write_text(text.replace(OLD_LINE, NEW_LINE), encoding="utf-8")
    elif transform == "decoy":
        require(text.count(OLD_LINE) == 2, "decoy source no longer has two vulnerable loaders")
        with target.open("a", encoding="utf-8") as handle:
            handle.write(DECOY_BLOCK)
    else:
        raise CalibrationError(f"unsupported transform: {transform}")

    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"{candidate_id} is not valid Python: {compile_proc.stderr}")

    behavior = run_behavioral_boundary_matrix(source)
    if objective_satisfied:
        require(
            behavior["all_rejected_as_unsafe_path"] is True,
            "straightforward candidate failed seeded boundary behavior",
        )
    else:
        require(
            behavior["all_accepted"] is True,
            "decoy unexpectedly changed vulnerable boundary behavior",
        )

    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"{candidate_id} changed unexpected paths: {changed}")
    patch_text = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout
    patch_bytes = patch_text.encode("utf-8")
    require(bool(patch_bytes), f"{candidate_id} produced an empty patch")

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout_bytes = (
        f"candidate={candidate_id}\n"
        f"objective_satisfied={str(objective_satisfied).lower()}\n"
        f"behavior_all_rejected={str(behavior['all_rejected_as_unsafe_path']).lower()}\n"
        f"behavior_all_accepted={str(behavior['all_accepted']).lower()}\n"
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
        worker_id=f"idkmesh-task001-real-calibration-{candidate_id}",
        worker_adapter=f"task001-{transform}-real-calibration",
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
    return result, verification, behavior, candidate_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/verification/task001-real-v04-calibration",
        help="Evaluator-repository-relative output root under results/.",
    )
    args = parser.parse_args()

    verify_burned_control_plane()
    source = args.source.resolve()
    require(source.is_dir(), f"source checkout does not exist: {source}")
    reset_source(source)
    output_root = ensure_output_root(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    plan = evaluator_plan_runner.load_plan(PLAN_PATH)
    require(plan["schema_version"] == "0.4", "calibration plan is not EvaluatorPlan v0.4")
    require(plan["execution_mode"] == "metadata_only", "calibration plan is not metadata-only")
    require(plan["verifier"]["adapter_version"] == "0.3.0", "calibration verifier version drift")
    plan_digest = canonical_digest(plan)

    straight_result, straight_verification, straight_behavior, straight_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="straightforward",
        transform="straightforward",
        objective_satisfied=True,
    )
    require(straight_verification["status"] == "passed", "v0.4 rejected straightforward candidate")
    require(
        straight_verification["decision_support"]["recommendation"] == "accept_candidate",
        "v0.4 did not support straightforward candidate",
    )
    require(
        straight_verification["metrics"].get("required_removed_substring_count") == 1
        and straight_verification["metrics"].get("matched_removed_substring_count") == 1,
        "straightforward transition did not satisfy required removal evidence",
    )

    decoy_result, decoy_verification, decoy_behavior, decoy_root = materialize_candidate(
        source=source,
        output_root=output_root,
        candidate_id="inert-decoy",
        transform="decoy",
        objective_satisfied=False,
    )
    require(decoy_verification["status"] == "failed", "v0.4 failed to reject inert decoy")
    require(
        decoy_verification["decision_support"]["recommendation"] == "reject_candidate",
        "v0.4 did not reject inert decoy",
    )
    require(
        decoy_verification["metrics"].get("required_removed_substring_count") == 1
        and decoy_verification["metrics"].get("matched_removed_substring_count") == 0,
        "decoy rejection is not explained by missing required removal evidence",
    )
    require(
        any(
            finding["category"] == "correctness"
            and "does not remove every verifier-owned required unsafe substring" in finding["summary"]
            for finding in decoy_verification["findings"]
        ),
        "decoy rejection lacks transition-correctness finding",
    )

    for verification in (straight_verification, decoy_verification):
        require(
            verification["verifier"]["adapter_version"] == "0.3.0",
            "VerificationResult verifier version drift",
        )
        require(
            verification["provenance"]["verifier_config_digest"] == plan_digest,
            "VerificationResult lost exact EvaluatorPlan digest",
        )
        require(
            verification.get("extensions", {}).get("org.idkmesh.evaluator_plan.execution_mode")
            == "metadata_only",
            "VerificationResult lost metadata-only EvaluatorPlan provenance",
        )
        require(
            verification.get("extensions", {}).get("org.idkmesh.local_verifier.semantic_match_mode")
            == "added_and_removed_line_substring_all",
            "VerificationResult lost v0.4 transition semantic mode",
        )

    summary = {
        "schema_version": "0.1",
        "source_revision": SOURCE_SHA,
        "task_id": TASK_ID,
        "burned_definition_digest": BURNED_DEFINITION_DIGEST,
        "evaluator_plan_id": plan["id"],
        "evaluator_plan_digest": plan_digest,
        "verifier_adapter_version": "0.3.0",
        "straightforward": {
            "result_manifest_digest": canonical_digest(straight_result),
            "verification_result_digest": canonical_digest(straight_verification),
            "verification_status": straight_verification["status"],
            "recommendation": straight_verification["decision_support"]["recommendation"],
            "behavior_all_rejected_as_unsafe_path": straight_behavior[
                "all_rejected_as_unsafe_path"
            ],
            "matched_removed_substrings": straight_verification["metrics"][
                "matched_removed_substring_count"
            ],
            "candidate_root": straight_root.relative_to(ROOT).as_posix(),
        },
        "inert_decoy": {
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_result_digest": canonical_digest(decoy_verification),
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "behavior_all_accepted": decoy_behavior["all_accepted"],
            "matched_removed_substrings": decoy_verification["metrics"][
                "matched_removed_substring_count"
            ],
            "candidate_root": decoy_root.relative_to(ROOT).as_posix(),
        },
        "calibration_passed": True,
        "metadata_only_verifier_executes_candidate_code": False,
        "behavioral_execution_is_separate_evidence_channel": True,
        "calibration_candidates_are_benchmark_outcomes": False,
        "automatic_candidate_selection": False,
        "merge_authority": False,
    }
    write_json(output_root / "calibration-summary.json", summary)
    reset_source(source)

    print("IDKMESH_TASK001_REAL_V04_CALIBRATION_BEGIN")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("IDKMESH_TASK001_REAL_V04_CALIBRATION_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalibrationError, OSError, json.JSONDecodeError, local_verifier.VerifierError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
