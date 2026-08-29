#!/usr/bin/env python3
"""Calibrate the frozen Phase B2 Task 001 evaluator after the first real outcome.

This probe is deliberately post-outcome *evidence*, not a rewrite of the frozen
benchmark definition. It checks two properties against the exact frozen Task 001
WorkUnit/EvaluatorPlan:

1. the straightforward repository-boundary fix is independently rejected only
   because the verifier expects an exact added line rather than a text fragment;
2. a scope-valid decoy can satisfy that exact-line predicate while leaving the
   original absolute-path boundary bug intact.

If both are observed, the frozen evaluator has demonstrated one false negative
and one false positive for the task objective. The correct response is to retain
that negative result and exclude the task from scored evidence in this frozen
cohort, not to weaken or rewrite the evaluator after seeing the outcome.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
TOOLS = ROOT / "tools"
for path in (EXPERIMENTS, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import benchmark_cohort  # noqa: E402
import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402

SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/001-cohort-path-boundary"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-001-cohort-path-boundary.work-unit.json"
PLAN_PATH = ROOT / "benchmarks/phase-b2-first-five/evaluators/task-001-cohort-path-boundary.evaluator-plan.json"
COHORT_PATH = ROOT / "benchmarks/phase-b2-first-five/cohort.json"
EXPECTED_FRAGMENT = "resolve_repo_file(args.cohort"
DECOY_BLOCK = '\n\n_TASK001_EVALUATOR_DECOY = """\nresolve_repo_file(args.cohort\n"""\n'
PROBE_WORKER_ID = "idkmesh-phase-b2-task001-evaluator-calibration-probe"
PROBE_VERSION = "0.1"


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


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


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeError(f"expected JSON object: {path}")
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
        raise ProbeError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_straightforward_outcome(evidence_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_root = evidence_root / "attempt-001"
    result_path = candidate_root / "result-manifest.json"
    patch_path = candidate_root / "candidate.patch"
    require(result_path.is_file() and patch_path.is_file(), "straightforward candidate bundle is incomplete")

    work_unit = load_json(WORK_UNIT_PATH)
    plan = load_json(PLAN_PATH)
    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH,
        result_manifest_path=result_path,
        candidate_root=candidate_root,
        plan_path=PLAN_PATH,
    )
    write_json(evidence_root / "straightforward-verification-result.json", verification)

    require(verification["status"] == "failed", "straightforward candidate was not rejected as observed")
    require(
        verification["decision_support"]["recommendation"] == "reject_candidate",
        "straightforward candidate rejection recommendation drifted",
    )
    checks = {item["id"]: item for item in verification["checks"]}
    require(checks["result-manifest-schema"]["status"] == "passed", "straightforward ResultManifest did not pass")
    require(checks["independent-review"]["status"] == "failed", "straightforward independent-review did not fail")
    diagnostics = json.loads(checks["independent-review"]["diagnostics"])
    require(diagnostics["scope"]["violations"] == [], "straightforward candidate has a scope violation")
    require(diagnostics["artifact"]["declared_digest"] == diagnostics["artifact"]["observed_digest"], "straightforward patch digest failed")
    require(diagnostics["logs"]["coverage_violations"] == [], "straightforward candidate log coverage failed")
    require(all(item.get("matches") is True for item in diagnostics["logs"]["logs"]), "straightforward candidate log digest failed")

    patch_text = patch_path.read_text(encoding="utf-8")
    added_lines = local_verifier.parse_added_lines(patch_text)
    required_text = list(plan["backend"]["required_added_text"])
    require(required_text == [EXPECTED_FRAGMENT], "frozen Task 001 semantic commitment drifted")
    missing_exact = list(diagnostics["semantic"]["missing_added_text"])
    require(missing_exact == required_text, "straightforward semantic failure is not the frozen exact-line expectation")
    substring_hits = {
        expected: [line for line in added_lines if expected in line]
        for expected in required_text
    }
    require(all(substring_hits[expected] for expected in required_text), "straightforward patch lacks the intended resolver text even as a substring")
    require(all(expected not in added_lines for expected in required_text), "frozen exact-line predicate unexpectedly matched straightforward patch")

    negative = load_json(evidence_root / "negative-evidence.json")
    require(negative.get("passed") is True, "straightforward patched source did not pass the seeded unsafe-path regression checks")

    return verification, {
        "required_added_text": required_text,
        "added_lines": added_lines,
        "missing_exact_lines": missing_exact,
        "substring_hits": substring_hits,
        "negative_evidence_digest": canonical_digest(negative),
    }


def prove_boundary_bypass(source: Path) -> dict[str, Any]:
    """Prove the frozen source still accepts an absolute cohort path."""

    with tempfile.TemporaryDirectory(prefix="idkmesh-task001-outside-") as raw:
        outside = Path(raw) / "outside-cohort.json"
        outside.write_text(COHORT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        proc = run(
            [
                sys.executable,
                TARGET_REL,
                "definition-digest",
                "--cohort",
                str(outside.resolve()),
            ],
            cwd=source,
            check=False,
        )
        accepted_absolute_path = proc.returncode == 0 and proc.stdout.strip().startswith("sha256:")
        return {
            "absolute_path": str(outside.resolve()),
            "returncode": proc.returncode,
            "accepted_absolute_path": accepted_absolute_path,
            "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
            "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
            "stdout_excerpt": proc.stdout.strip()[:300],
            "stderr_excerpt": proc.stderr.strip()[:300],
        }


def build_decoy_result(
    *,
    work_unit: dict[str, Any],
    patch_bytes: bytes,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    elapsed: float,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    required_validator_ids = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    worker_config = {
        "schema_version": "0.1",
        "purpose": "frozen-evaluator-calibration",
        "source_revision": SOURCE_SHA,
        "target": TARGET_REL,
        "decoy_block": DECOY_BLOCK,
    }
    result = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/evaluator-decoy/attempt-001",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": PROBE_WORKER_ID,
            "type": "system",
            "adapter": "adversarial-evaluator-calibration",
            "adapter_version": PROBE_VERSION,
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
                "description": "Adversarial evaluator-calibration patch; intentionally does not solve the Task 001 path-boundary objective.",
            }
        ],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {
            "changed_path_count": 1,
            "objective_satisfied": 0,
            "boundary_bypass_retained": 1,
        },
        "resources": {
            "wall_seconds": elapsed,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": "Adversarial calibration candidate: adds the frozen evaluator's exact expected line as inert text while deliberately leaving the original absolute-path boundary bug unchanged.",
            "claims": [
                "This candidate intentionally does not satisfy the WorkUnit objective.",
                "It exists only to test whether the frozen metadata-only evaluator can be Goodharted by its predeclared exact-line predicate.",
                "Evaluator support for this candidate would be a false positive, not acceptance evidence.",
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
                    "phase-b2-task001-evaluator-probe": PROBE_VERSION,
                    "git": run(["git", "--version"], cwd=ROOT).stdout.strip(),
                },
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids,
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Adversarial calibration only; verifier result must not be treated as integration authority.",
        },
        "extensions": {
            "org.idkmesh.benchmark.task_id": TASK_ID,
            "org.idkmesh.evaluator_calibration": True,
            "org.idkmesh.objective_intentionally_unsatisfied": True,
            "org.idkmesh.authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        },
    }
    local_verifier.validate_schema(result, local_verifier.RESULT_MANIFEST_SCHEMA, "decoy ResultManifest")
    return result


def run_decoy_probe(source: Path, evidence_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source must be clean before decoy probe")
    pre_bypass = prove_boundary_bypass(source)
    require(pre_bypass["accepted_absolute_path"] is True, "frozen source no longer demonstrates the indexed path-boundary bug")

    target = source / TARGET_REL
    started_at = utc_now()
    started = time.monotonic()
    with target.open("a", encoding="utf-8") as handle:
        handle.write(DECOY_BLOCK)

    compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
    require(compile_proc.returncode == 0, f"decoy candidate is not valid Python: {compile_proc.stderr}")
    post_bypass = prove_boundary_bypass(source)
    require(post_bypass["accepted_absolute_path"] is True, "decoy unexpectedly repaired the path-boundary bug")

    patch_text = run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--", TARGET_REL],
        cwd=source,
    ).stdout
    patch_bytes = patch_text.encode("utf-8")
    added_lines = local_verifier.parse_added_lines(patch_text)
    require(EXPECTED_FRAGMENT in added_lines, "decoy patch did not satisfy frozen exact-line predicate")
    changed = run(["git", "diff", "--name-only", "HEAD", "--", TARGET_REL], cwd=source).stdout.splitlines()
    require(changed == [TARGET_REL], f"decoy changed unexpected paths: {changed}")

    finished_at = utc_now()
    elapsed = max(0.0, time.monotonic() - started)
    stdout = (
        "Phase B2 Task 001 evaluator calibration decoy\n"
        "py_compile=passed\n"
        "boundary_bypass_before=true\n"
        "boundary_bypass_after=true\n"
        f"frozen_exact_line={EXPECTED_FRAGMENT}\n"
    ).encode("utf-8")
    stderr = compile_proc.stderr.encode("utf-8")

    candidate_root = evidence_root / "evaluator-decoy"
    candidate_root.mkdir(parents=True, exist_ok=True)
    (candidate_root / "candidate.patch").write_bytes(patch_bytes)
    (candidate_root / "stdout.txt").write_bytes(stdout)
    (candidate_root / "stderr.txt").write_bytes(stderr)

    work_unit = load_json(WORK_UNIT_PATH)
    result = build_decoy_result(
        work_unit=work_unit,
        patch_bytes=patch_bytes,
        stdout_bytes=stdout,
        stderr_bytes=stderr,
        elapsed=elapsed,
        started_at=started_at,
        finished_at=finished_at,
    )
    result_path = candidate_root / "result-manifest.json"
    write_json(result_path, result)

    verification = evaluator_plan_runner.run_fixture(
        work_unit_path=WORK_UNIT_PATH,
        result_manifest_path=result_path,
        candidate_root=candidate_root,
        plan_path=PLAN_PATH,
    )
    write_json(evidence_root / "evaluator-decoy-verification-result.json", verification)
    require(verification["status"] == "passed", "frozen evaluator did not accept the exact-line decoy as predicted")
    require(
        verification["decision_support"]["recommendation"] == "accept_candidate",
        "frozen evaluator did not recommend acceptance for the decoy",
    )

    return verification, {
        "pre_decoy_boundary_bypass": pre_bypass,
        "post_decoy_boundary_bypass": post_bypass,
        "added_lines": added_lines,
        "candidate_patch_digest": sha256_bytes(patch_bytes),
        "result_manifest_digest": canonical_digest(result),
    }


def prospective_exclusion(evidence_root: Path, reason: str) -> dict[str, Any]:
    cohort = load_json(COHORT_PATH)
    frozen_digest = cohort["definition_digest"]
    derived = copy.deepcopy(cohort)
    matches = [task for task in derived["tasks"] if task["id"] == TASK_ID]
    require(len(matches) == 1, "frozen cohort does not contain exactly one Task 001")
    matches[0]["evidence"] = {
        "status": "excluded",
        "attempts": [],
        "exclusion_reason": reason,
    }
    summary = benchmark_cohort.validate_cohort(derived, require_evidence=False)
    require(summary["excluded_tasks"] == 1, "prospective exclusion did not exclude exactly Task 001")
    require(summary["pending_tasks"] == 4, "prospective exclusion changed other task evidence")
    require(summary["verified_tasks"] == 0, "prospective exclusion invented verified evidence")
    require(summary["definition_digest"] == frozen_digest, "prospective exclusion changed frozen definition digest")
    write_json(evidence_root / "prospective-cohort-exclusion.json", derived)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    evidence_root = args.evidence_root.resolve()
    require(source.is_dir(), f"source checkout missing: {source}")
    require(evidence_root.is_dir(), f"straightforward evidence root missing: {evidence_root}")
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", "source must be reset before evaluator probe")

    plan = load_json(PLAN_PATH)
    straightforward_verification, straightforward = load_straightforward_outcome(evidence_root)
    decoy_verification, decoy = run_decoy_probe(source, evidence_root)

    exclusion_reason = (
        "Frozen Task 001 evaluator calibration failed: it rejected a straightforward patch that passed the "
        "task's seeded unsafe-path regressions because required_added_text is matched as an exact added line, "
        "then accepted an inert exact-line decoy while the original absolute-path boundary bug remained. "
        "Retain this as a benchmark/evaluator negative result; do not rewrite the frozen evaluator after outcome."
    )
    cohort_summary = prospective_exclusion(evidence_root, exclusion_reason)

    finding = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/frozen-evaluator-calibration",
        "classification": "frozen_evaluator_false_negative_and_false_positive",
        "source_revision": SOURCE_SHA,
        "work_unit_digest": load_json(PLAN_PATH)["binding"]["work_unit_digest"],
        "evaluator_plan_digest": canonical_digest(plan),
        "frozen_required_added_text": list(plan["backend"]["required_added_text"]),
        "straightforward_candidate": {
            "verification_status": straightforward_verification["status"],
            "recommendation": straightforward_verification["decision_support"]["recommendation"],
            "verification_result_digest": canonical_digest(straightforward_verification),
            **straightforward,
        },
        "decoy_candidate": {
            "objective_intentionally_unsatisfied": True,
            "verification_status": decoy_verification["status"],
            "recommendation": decoy_verification["decision_support"]["recommendation"],
            "verification_result_digest": canonical_digest(decoy_verification),
            **decoy,
        },
        "prospective_cohort": {
            "excluded_tasks": cohort_summary["excluded_tasks"],
            "pending_tasks": cohort_summary["pending_tasks"],
            "verified_tasks": cohort_summary["verified_tasks"],
            "definition_digest": cohort_summary["definition_digest"],
            "definition_digest_unchanged": True,
        },
        "recommended_action": "exclude_task_from_scored_frozen_cohort_and_define_a_new_evaluator_in_a_future_version_or_cohort",
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
    write_json(evidence_root / "evaluator-calibration-finding.json", finding)

    markdown = f"""# Phase B2 Task 001 evaluator calibration\n\n**Classification:** frozen evaluator false negative + false positive.\n\n- frozen source: `{SOURCE_SHA}`\n- frozen evaluator plan: `{finding['evaluator_plan_digest']}`\n- required added-line entry: `{EXPECTED_FRAGMENT}`\n- straightforward correct fix: **rejected** by frozen evaluator\n- straightforward seeded absolute/traversal regressions: **passed**\n- adversarial inert decoy: **accepted** by frozen evaluator\n- absolute-path boundary after decoy: **still vulnerable**\n- prospective benchmark treatment: **exclude Task 001 from scored evidence**\n- frozen definition digest unchanged: **yes** (`{cohort_summary['definition_digest']}`)\n- human integration decision: **pending**\n\nThe result is not a reason to rewrite the evaluator after seeing outcomes. It is evidence that this frozen evaluator does not discriminate the Task 001 objective reliably. A corrected evaluator should be defined prospectively in a new benchmark version/cohort. No candidate selection, approval, push, merge, or canonical-state authority is granted by this probe.\n"""
    (evidence_root / "evidence-summary.md").write_text(markdown, encoding="utf-8")

    print(json.dumps(finding, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProbeError,
        benchmark_cohort.CohortError,
        evaluator_plan_runner.EvaluatorPlanError,
        local_verifier.VerifierError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
