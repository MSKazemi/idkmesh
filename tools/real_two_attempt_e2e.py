#!/usr/bin/env python3
"""Generate two real frozen-node bundles, verify both, and render run evidence.

This is an evidence harness over the existing two-attempt coordinator. Worker
execution remains outside coordinator core: two exact-SHA node runs produce two
isolated bundles, then the coordinator consumes them through the execution-neutral
`result-bundle` adapter and one evaluator-owned EvaluatorPlan v0.2.

The resulting Run Evidence Report is non-selecting and leaves integration to an
external human/governance decision.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"
SOURCE_SHA = "b1397a9be91da6570e8ae370de4fa9f4bc44df5c"
EXPECTED_ADDED_TEXT = "<!-- idkmesh-node candidate smoke -->"
PLAN_TEMPLATE = "verification/fixtures/patch-smoke-evaluator-plan-v0.2.json"


class E2EError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E2EError(f"expected JSON object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise E2EError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def candidate_env(candidate: Path, home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    xdg = home / "xdg"
    xdg.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONPATH": str(candidate / "node" / "src"),
        "PYTHONUNBUFFERED": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


def derive_plan(evaluator_root: Path, work_unit: dict[str, Any]) -> dict[str, Any]:
    template = load_json(evaluator_root / PLAN_TEMPLATE)
    require(template.get("schema_version") == "0.2", "canonical plan template is not v0.2")
    require(template.get("execution_mode") == "metadata_only", "canonical plan is not metadata-only")
    require(template.get("backend", {}).get("type") == "unified_diff", "canonical plan is not unified_diff")

    plan = copy.deepcopy(template)
    plan["id"] = f"verification/real-two-attempt-{CANDIDATE_SHA[:7]}-plan"
    plan["binding"] = {
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
    }
    plan["candidate_artifact_id"] = "candidate-patch"
    plan["required_validator_ids"] = sorted(
        item["id"] for item in work_unit["validators"] if item.get("required") is True
    )
    plan["backend"]["max_candidate_bytes"] = 1_000_000
    plan["backend"]["max_log_bytes"] = 262_144
    plan["backend"]["required_added_text"] = [EXPECTED_ADDED_TEXT]
    required_logs = set(plan["backend"].get("required_log_types", []))
    require({"stdout", "stderr"}.issubset(required_logs), "plan does not require stdout/stderr")
    plan.setdefault("extensions", {})["org.idkmesh.real_two_attempt"] = {
        "candidate_sha": CANDIDATE_SHA,
        "purpose": "two real isolated node bundles routed through one independent EvaluatorPlan",
    }
    return plan


def repo_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--output-root",
        default="results/orchestration/real-two-attempt-520ad2c",
        help="Evaluator-repository-relative output root under results/.",
    )
    args = parser.parse_args()

    evaluator_root = Path(__file__).resolve().parents[1]
    candidate = args.candidate.resolve()
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=candidate).stdout.strip()
    require(actual_sha == CANDIDATE_SHA, f"candidate SHA drift: {actual_sha}")

    output_root = (evaluator_root / args.output_root).resolve()
    try:
        relative_root = output_root.relative_to(evaluator_root)
    except ValueError as exc:
        raise E2EError("output root escapes evaluator repository") from exc
    require(relative_root.parts and relative_root.parts[0] == "results", "output must remain under results/")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    source_fixture = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"
    work_unit = load_json(source_fixture)
    require(work_unit["provenance"]["source_revision"] == SOURCE_SHA, "WorkUnit source revision drift")

    work_unit_path = output_root / "work-unit.json"
    plan_path = output_root / "evaluator-plan.json"
    config_path = output_root / "config.json"
    run_path = output_root / "run.json"
    report_path = output_root / "evidence-report.json"
    report_md_path = output_root / "evidence-report.md"
    evidence_path = output_root / "e2e-evidence.json"
    write_json(work_unit_path, work_unit)

    attempt_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="idkmesh-real-two-attempt-") as raw_temp:
        temp_root = Path(raw_temp)
        for ordinal in (1, 2):
            attempt_id = f"attempt-{ordinal:03d}"
            bundle = output_root / attempt_id
            proc = run(
                [
                    sys.executable,
                    "-m",
                    "idkmesh_node",
                    "run",
                    str(source_fixture),
                    "--output",
                    str(bundle),
                ],
                cwd=candidate,
                env=candidate_env(candidate, temp_root / f"home-{ordinal}"),
                check=False,
            )
            require(
                proc.returncode == 0,
                f"{attempt_id} real node execution failed:\n{proc.stdout}\n{proc.stderr}",
            )
            result_path = bundle / "result-manifest.json"
            result = load_json(result_path)
            require(result["status"] == "succeeded", f"{attempt_id} ResultManifest is not succeeded")
            require(
                result["provenance"]["work_unit_digest"] == canonical_digest(work_unit),
                f"{attempt_id} WorkUnit binding drift",
            )
            require(result["provenance"]["source_revision"] == SOURCE_SHA, f"{attempt_id} source drift")
            patch_artifacts = [item for item in result["produced_artifacts"] if item["id"] == "candidate-patch"]
            require(len(patch_artifacts) == 1, f"{attempt_id} must expose exactly one candidate patch")
            attempt_rows.append(
                {
                    "attempt_id": attempt_id,
                    "bundle": bundle,
                    "result_path": result_path,
                    "result": result,
                    "result_digest": canonical_digest(result),
                    "patch_digest": patch_artifacts[0]["digest"],
                }
            )

    require(
        attempt_rows[0]["bundle"] != attempt_rows[1]["bundle"],
        "attempts did not use isolated output bundles",
    )
    require(
        attempt_rows[0]["result"]["id"] != attempt_rows[1]["result"]["id"],
        "two real worker attempts produced the same ResultManifest id",
    )
    require(
        attempt_rows[0]["patch_digest"] == attempt_rows[1]["patch_digest"],
        "deterministic smoke attempts produced different candidate patch bytes",
    )

    # Evaluator control is created after both worker bundles exist and outside
    # either candidate bundle.
    plan = derive_plan(evaluator_root, work_unit)
    write_json(plan_path, plan)
    for row in attempt_rows:
        require(row["bundle"] not in plan_path.parents, "EvaluatorPlan is inside a candidate bundle")

    config = {
        "schema_version": "0.1",
        "run_id": f"real-two-attempt-{CANDIDATE_SHA[:7]}",
        "work_unit": repo_relative(evaluator_root, work_unit_path),
        "evaluator_plan": repo_relative(evaluator_root, plan_path),
        "attempts": [
            {
                "attempt_id": row["attempt_id"],
                "worker_adapter": "result-bundle",
                "result_manifest": repo_relative(evaluator_root, row["result_path"]),
                "candidate_root": repo_relative(evaluator_root, row["bundle"]),
            }
            for row in attempt_rows
        ],
    }
    write_json(config_path, config)

    # Preserve both coordinator and presentation-layer invariants before using
    # the real bundles.
    run([sys.executable, "experiments/two_attempt_orchestrator.py", "self-test"], cwd=evaluator_root)
    run([sys.executable, "experiments/run_evidence_report.py", "self-test"], cwd=evaluator_root)

    generate = run(
        [
            sys.executable,
            "experiments/run_evidence_report.py",
            "generate",
            "--config",
            repo_relative(evaluator_root, config_path),
            "--run-output",
            repo_relative(evaluator_root, run_path),
            "--report-json",
            repo_relative(evaluator_root, report_path),
            "--report-markdown",
            repo_relative(evaluator_root, report_md_path),
        ],
        cwd=evaluator_root,
    )
    require("wrote run record" in generate.stdout, "evidence generator did not report success")

    replay = run(
        [
            sys.executable,
            "experiments/run_evidence_report.py",
            "replay-check",
            "--config",
            repo_relative(evaluator_root, config_path),
            "--run-record",
            repo_relative(evaluator_root, run_path),
        ],
        cwd=evaluator_root,
    )
    replay_record = json.loads(replay.stdout)
    require(replay_record.get("match") is True, "saved real run did not replay exactly")

    run_record = load_json(run_path)
    report = load_json(report_path)
    require(run_record["run_state"] == "completed", "real two-attempt run did not complete")
    require(run_record["attempt_order"] == ["attempt-001", "attempt-002"], "attempt order drift")
    require(run_record["summary"]["attempt_count"] == 2, "run lost an attempt")
    require(run_record["summary"]["control_failures"] == 0, "run has a control failure")
    require(run_record["summary"]["candidates_supported"] == 2, "both real candidates were not supported")
    require(run_record["summary"]["candidates_rejected"] == 0, "unexpected real candidate rejection")
    require(run_record["verification_control"]["kind"] == "evaluator_plan", "run lost EvaluatorPlan identity")
    require(run_record["verification_control"]["backend"] == "unified_diff", "run lost unified_diff backend")
    require(run_record["verification_control"]["digest"] == canonical_digest(plan), "run plan digest drift")

    expected_authority = {
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
        "automatic_candidate_selection": False,
    }
    require(run_record["authority"] == expected_authority, "orchestrator gained integration authority")
    for attempt in run_record["attempts"]:
        require(attempt["state"] == "verified", f"{attempt['attempt_id']} was not verified")
        require(
            attempt["verification"]["recommendation"] == "accept_candidate",
            f"{attempt['attempt_id']} was not independently supported",
        )
        require(
            attempt["verification"]["result_manifest_digest"] == attempt["result_manifest"]["digest"],
            f"{attempt['attempt_id']} verification lost ResultManifest binding",
        )
        require(
            attempt["verification"]["work_unit_digest"] == run_record["work_unit"]["digest"],
            f"{attempt['attempt_id']} verification lost WorkUnit binding",
        )

    require(report["summary"]["attempt_count"] == 2, "report lost an attempt")
    require(report["summary"]["supported"] == 2, "report did not preserve two supported attempts")
    require(report["summary"]["rejected"] == 0, "report invented a rejection")
    require(report["summary"]["control_errors"] == 0, "report invented a control error")
    require(report["summary"]["verification_disagreement"] is False, "identical smoke outcomes disagree")
    require(
        report["human_decision"] == {
            "status": "pending",
            "selected_attempt_id": None,
            "integration_authority": "external_human_or_governance",
        },
        "report selected a candidate or gained integration authority",
    )
    require(report["authority"] == expected_authority, "report gained write/select/merge authority")

    evidence = {
        "schema_version": "0.1",
        "candidate_sha": CANDIDATE_SHA,
        "source_revision": SOURCE_SHA,
        "work_unit_digest": canonical_digest(work_unit),
        "evaluator_plan_digest": canonical_digest(plan),
        "config_digest": canonical_digest(config),
        "run_digest": canonical_digest(run_record),
        "report_digest": canonical_digest(report),
        "replay": replay_record,
        "attempts": [
            {
                "attempt_id": row["attempt_id"],
                "result_manifest_id": row["result"]["id"],
                "result_manifest_digest": row["result_digest"],
                "candidate_patch_digest": row["patch_digest"],
                "verification_semantic_digest": next(
                    attempt["verification"]["semantic_digest"]
                    for attempt in run_record["attempts"]
                    if attempt["attempt_id"] == row["attempt_id"]
                ),
                "recommendation": "accept_candidate",
            }
            for row in attempt_rows
        ],
        "summary": copy.deepcopy(report["summary"]),
        "human_decision": copy.deepcopy(report["human_decision"]),
        "authority": copy.deepcopy(report["authority"]),
        "worker_execution_inside_orchestrator": False,
        "candidate_code_executed_by_verifier": False,
    }
    write_json(evidence_path, evidence)
    print("IDKMESH_REAL_TWO_ATTEMPT_E2E_BEGIN")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("IDKMESH_REAL_TWO_ATTEMPT_E2E_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (E2EError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
