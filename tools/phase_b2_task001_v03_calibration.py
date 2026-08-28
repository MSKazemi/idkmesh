#!/usr/bin/env python3
"""Calibrate EvaluatorPlan v0.3 against the burned Phase B2 Task 001 outcome.

This is post-burn calibration evidence, not a benchmark candidate run. It uses the
exact straightforward and inert-decoy patch bytes preserved by PR #158, then
checks two independent layers:

1. metadata-only EvaluatorPlan v0.3 must support the straightforward patch and
   reject the known inert decoy under the prospective structural substring rule;
2. a separate trusted behavioral regression on the frozen source must show the
   straightforward patch blocks absolute out-of-repository cohort paths while
   the decoy leaves that vulnerability intact.

The behavioral probe is deliberately separate from the metadata-only verifier.
It executes only fixed, checked-in calibration patches on the immutable public
source revision; it does not turn the patch verifier into a code-execution
backend and grants no selection, approval, push, merge, or canonical-write
authority.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import evaluator_plan_runner  # noqa: E402
import local_verifier  # noqa: E402

SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/001-cohort-path-boundary"
TARGET_REL = "tools/benchmark_cohort.py"
WORK_UNIT_PATH = ROOT / "benchmarks/phase-b2-first-five/work-units/task-001-cohort-path-boundary.work-unit.json"
PLAN_PATH = ROOT / "verification/fixtures/phase-b2-task001-v03-calibration.evaluator-plan.json"
STRAIGHT_PATCH = ROOT / "verification/fixtures/phase-b2-task001-v03/straightforward/candidate.patch"
DECOY_PATCH = ROOT / "verification/fixtures/phase-b2-task001-v03/decoy/candidate.patch"
STRAIGHT_PATCH_DIGEST = "sha256:9248e19254bf46bf11ac254dca3302eccdcc2f498117e07f3c86ce0b9f3bb65a"
DECOY_PATCH_DIGEST = "sha256:f315def3f8d16b4eb3ec7ea3a56ab73d696d08a6cf58b60b06e9e297c3997c17"
CALIBRATION_VERSION = "0.1"


class CalibrationError(RuntimeError):
    """Raised when the calibration matrix drifts or becomes inconclusive."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CalibrationError(message)


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
        raise CalibrationError(f"expected JSON object: {path}")
    return value


def run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONUNBUFFERED": "1",
    }
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
        raise CalibrationError(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def required_validator_ids(work_unit: dict[str, Any]) -> list[str]:
    return sorted(
        item["id"]
        for item in work_unit["validators"]
        if item.get("required") is True
    )


def build_result_manifest(
    *,
    label: str,
    work_unit: dict[str, Any],
    patch_bytes: bytes,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
) -> dict[str, Any]:
    timestamp = utc_now()
    worker_config = {
        "schema_version": "0.1",
        "purpose": "phase-b2-task001-v03-calibration",
        "label": label,
        "source_revision": SOURCE_SHA,
        "patch_digest": sha256_bytes(patch_bytes),
    }
    manifest = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/v03-calibration/{label}/attempt-001",
        "work_unit_id": work_unit["id"],
        "work_unit_version": work_unit["version"],
        "attempt": 1,
        "worker": {
            "id": f"idkmesh-v03-calibration-{label}",
            "type": "system",
            "adapter": "static-calibration-fixture",
            "adapter_version": CALIBRATION_VERSION,
        },
        "status": "succeeded",
        "started_at": timestamp,
        "finished_at": timestamp,
        "produced_artifacts": [
            {
                "id": "candidate-patch",
                "type": "patch",
                "locator": "candidate.patch",
                "digest": sha256_bytes(patch_bytes),
                "media_type": "text/x-diff",
                "description": f"Preserved Phase B2 Task 001 {label} calibration patch.",
            }
        ],
        "logs": [
            {"type": "stdout", "locator": "stdout.txt", "digest": sha256_bytes(stdout_bytes)},
            {"type": "stderr", "locator": "stderr.txt", "digest": sha256_bytes(stderr_bytes)},
        ],
        "metrics": {
            "calibration_fixture": 1,
            "objective_expected_satisfied": int(label == "straightforward"),
        },
        "resources": {
            "wall_seconds": 0.0,
            "compute_units": 0.0,
            "human_minutes": 0.0,
            "tokens": 0,
        },
        "self_report": {
            "summary": f"Static post-burn {label} calibration fixture; not benchmark outcome evidence.",
            "claims": [
                "Worker self-report is not acceptance.",
                "This fixture exists only to calibrate the versioned evaluator semantics.",
            ],
        },
        "provenance": {
            "work_unit_digest": canonical_digest(work_unit),
            "source_revision": SOURCE_SHA,
            "worker_config_digest": canonical_digest(worker_config),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tool_versions": {"phase-b2-task001-v03-calibration": CALIBRATION_VERSION},
            },
        },
        "verification_request": {
            "expected_validator_ids": required_validator_ids(work_unit),
            "evidence_artifact_ids": ["candidate-patch"],
            "notes": "Post-burn calibration only; evaluator recommendation is not integration authority.",
        },
        "extensions": {
            "org.idkmesh.calibration.label": label,
            "org.idkmesh.calibration.post_burn": True,
            "org.idkmesh.authority": {
                "canonical_state_write": False,
                "git_push": False,
                "merge": False,
                "automatic_candidate_selection": False,
            },
        },
    }
    local_verifier.validate_schema(
        manifest,
        local_verifier.RESULT_MANIFEST_SCHEMA,
        f"{label} calibration ResultManifest",
    )
    return manifest


def metadata_calibration(label: str, patch_path: Path) -> dict[str, Any]:
    work_unit = load_json(WORK_UNIT_PATH)
    plan = load_json(PLAN_PATH)
    patch_bytes = patch_path.read_bytes()
    expected_digest = STRAIGHT_PATCH_DIGEST if label == "straightforward" else DECOY_PATCH_DIGEST
    require(sha256_bytes(patch_bytes) == expected_digest, f"{label}: preserved PR #158 patch bytes drifted")
    require(plan["schema_version"] == "0.3", "calibration plan must use EvaluatorPlan v0.3")
    require(plan["verifier"]["adapter_version"] == "0.2.0", "calibration verifier version drifted")
    require(plan["binding"]["source_revision"] == SOURCE_SHA, "calibration plan source drifted")
    require(plan["binding"]["work_unit_digest"] == canonical_digest(work_unit), "calibration plan WorkUnit digest drifted")

    stdout_bytes = f"phase-b2-v03-calibration={label}\n".encode("utf-8")
    stderr_bytes = b""
    with tempfile.TemporaryDirectory(prefix=f"idkmesh-v03-{label}-") as raw:
        candidate_root = Path(raw)
        (candidate_root / "candidate.patch").write_bytes(patch_bytes)
        (candidate_root / "stdout.txt").write_bytes(stdout_bytes)
        (candidate_root / "stderr.txt").write_bytes(stderr_bytes)
        manifest = build_result_manifest(
            label=label,
            work_unit=work_unit,
            patch_bytes=patch_bytes,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
        )
        manifest_path = candidate_root / "result-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verification = evaluator_plan_runner.run_fixture(
            work_unit_path=WORK_UNIT_PATH,
            result_manifest_path=manifest_path,
            candidate_root=candidate_root,
            plan_path=PLAN_PATH,
        )

    expected_status = "passed" if label == "straightforward" else "failed"
    expected_recommendation = "accept_candidate" if label == "straightforward" else "reject_candidate"
    require(verification["status"] == expected_status, f"{label}: v0.3 verification status drifted")
    require(
        verification["decision_support"]["recommendation"] == expected_recommendation,
        f"{label}: v0.3 recommendation drifted",
    )
    require(
        verification["verifier"]["adapter_version"] == "0.2.0",
        f"{label}: VerificationResult verifier version drifted",
    )
    require(
        verification["provenance"]["verifier_config_digest"] == canonical_digest(plan),
        f"{label}: VerificationResult plan digest drifted",
    )
    return {
        "label": label,
        "patch_digest": expected_digest,
        "verification_status": verification["status"],
        "recommendation": verification["decision_support"]["recommendation"],
        "verification_result_digest": canonical_digest(verification),
    }


def make_external_cohort(source: Path, output: Path) -> None:
    """Ask the unmodified frozen source to emit its own schema-valid scaffold fixture."""

    code = (
        "import json,sys; "
        "sys.path.insert(0,'tools'); "
        "import benchmark_cohort; "
        "print(json.dumps(benchmark_cohort._fixture_cohort(), sort_keys=True))"
    )
    proc = run([sys.executable, "-c", code], cwd=source)
    value = json.loads(proc.stdout)
    require(isinstance(value, dict), "frozen source did not produce a cohort fixture object")
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def behavioral_calibration(
    *,
    label: str,
    source: Path,
    patch_path: Path,
    should_block_absolute_path: bool,
) -> dict[str, Any]:
    source = source.resolve()
    require(source.is_dir(), f"{label}: frozen source checkout missing: {source}")
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, f"{label}: source SHA drift")
    require(run(["git", "status", "--porcelain"], cwd=source).stdout == "", f"{label}: source checkout must start clean")

    with tempfile.TemporaryDirectory(prefix=f"idkmesh-v03-external-{label}-") as raw:
        outside = Path(raw) / "outside-cohort.json"
        make_external_cohort(source, outside)

        run(["git", "apply", "--check", str(patch_path.resolve())], cwd=source)
        run(["git", "apply", str(patch_path.resolve())], cwd=source)
        compile_proc = run([sys.executable, "-m", "py_compile", TARGET_REL], cwd=source, check=False)
        require(compile_proc.returncode == 0, f"{label}: patched calibration source does not compile")

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

    blocked = proc.returncode != 0 and "unsafe path" in proc.stderr
    accepted = proc.returncode == 0 and proc.stdout.strip().startswith("sha256:")
    if should_block_absolute_path:
        require(blocked, f"{label}: straightforward fix did not fail closed on absolute cohort path")
    else:
        require(accepted, f"{label}: preserved inert decoy no longer demonstrates the absolute-path bypass")

    return {
        "label": label,
        "absolute_path_blocked": blocked,
        "absolute_path_accepted": accepted,
        "returncode": proc.returncode,
        "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--straight-source", required=True, type=Path)
    parser.add_argument("--decoy-source", required=True, type=Path)
    args = parser.parse_args()

    straightforward_meta = metadata_calibration("straightforward", STRAIGHT_PATCH)
    decoy_meta = metadata_calibration("decoy", DECOY_PATCH)
    straightforward_behavior = behavioral_calibration(
        label="straightforward",
        source=args.straight_source,
        patch_path=STRAIGHT_PATCH,
        should_block_absolute_path=True,
    )
    decoy_behavior = behavioral_calibration(
        label="decoy",
        source=args.decoy_source,
        patch_path=DECOY_PATCH,
        should_block_absolute_path=False,
    )

    result = {
        "schema_version": "0.1",
        "classification": "phase_b2_task001_v03_legitimate_vs_decoy_calibration",
        "source_revision": SOURCE_SHA,
        "evaluator_plan_digest": canonical_digest(load_json(PLAN_PATH)),
        "straightforward": {
            "metadata_only": straightforward_meta,
            "behavioral": straightforward_behavior,
        },
        "decoy": {
            "metadata_only": decoy_meta,
            "behavioral": decoy_behavior,
        },
        "evidence_strength": {
            "substring_semantics": "structural_only",
            "behavioral_gate": "required_for_security_correctness_claim",
        },
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
            "automatic_candidate_selection": False,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CalibrationError,
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
