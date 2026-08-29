#!/usr/bin/env python3
"""Finalize Phase B2 Task 001 calibration evidence against the burned cohort.

The first-five cohort is already burned on main because its frozen semantic
fragments conflict with verifier v0.1.1 exact added-line semantics. This tool
adds a stronger calibration observation without changing that decision:

- the straightforward Task 001 fix is rejected (false negative);
- an inert exact-line decoy is accepted while the absolute-path bug remains
  (false positive).

The output is diagnostic evidence only. It grants no candidate-selection,
canonical-write, approval, push, or merge authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2"
TASK_ID = "benchmark/phase-b2/001-cohort-path-boundary"
EXPECTED_DEFINITION_DIGEST = "sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c"
EXPECTED_FRAGMENT = "resolve_repo_file(args.cohort"
COHORT_PATH = ROOT / "benchmarks/phase-b2-first-five/cohort.json"
TARGET_REL = "tools/benchmark_cohort.py"


class BurnEvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BurnEvidenceError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BurnEvidenceError(f"expected JSON object: {path}")
    return value


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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


def parse_review_diagnostics(verification: dict[str, Any]) -> dict[str, Any]:
    matches = [item for item in verification["checks"] if item["id"] == "independent-review"]
    require(len(matches) == 1, "VerificationResult does not contain exactly one independent-review check")
    return json.loads(matches[0]["diagnostics"])


def prove_decoy_still_vulnerable(source: Path) -> dict[str, Any]:
    require(run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() == SOURCE_SHA, "source SHA drift")
    with tempfile.TemporaryDirectory(prefix="idkmesh-task001-burn-evidence-") as raw:
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
        )
        return {
            "returncode": proc.returncode,
            "accepted_absolute_path": proc.returncode == 0 and proc.stdout.strip().startswith("sha256:"),
            "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
            "stderr_sha256": sha256_bytes(proc.stderr.encode("utf-8")),
            "stdout_excerpt": proc.stdout.strip()[:300],
            "stderr_excerpt": proc.stderr.strip()[:300],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    evidence_root = args.evidence_root.resolve()
    require(source.is_dir(), f"source checkout missing: {source}")
    require(evidence_root.is_dir(), f"evidence root missing: {evidence_root}")

    straightforward = load_json(evidence_root / "straightforward-verification-result.json")
    decoy = load_json(evidence_root / "evaluator-decoy-verification-result.json")
    decoy_result = load_json(evidence_root / "evaluator-decoy/result-manifest.json")
    negative = load_json(evidence_root / "negative-evidence.json")
    cohort = load_json(COHORT_PATH)

    require(straightforward["status"] == "failed", "straightforward candidate is not the observed verifier rejection")
    require(
        straightforward["decision_support"]["recommendation"] == "reject_candidate",
        "straightforward verifier recommendation drift",
    )
    straight_diag = parse_review_diagnostics(straightforward)
    require(straight_diag["scope"]["violations"] == [], "straightforward candidate has scope violations")
    require(straight_diag["semantic"]["missing_added_text"] == [EXPECTED_FRAGMENT], "straightforward failure is not exact-line semantic mismatch")
    require(
        any(EXPECTED_FRAGMENT in line for line in straight_diag["semantic"]["observed_added_lines"]),
        "straightforward candidate does not contain the intended semantic fragment",
    )
    require(negative.get("passed") is True, "straightforward candidate did not pass seeded unsafe-path regressions")

    require(decoy["status"] == "passed", "decoy was not accepted by frozen evaluator")
    require(decoy["decision_support"]["recommendation"] == "accept_candidate", "decoy acceptance recommendation drift")
    decoy_diag = parse_review_diagnostics(decoy)
    require(decoy_diag["scope"]["violations"] == [], "decoy escaped WorkUnit scope")
    require(decoy_diag["semantic"]["missing_added_text"] == [], "decoy did not satisfy frozen exact-line predicate")
    require(EXPECTED_FRAGMENT in decoy_diag["semantic"]["observed_added_lines"], "decoy exact line not observed")
    require(decoy_result["extensions"].get("org.idkmesh.objective_intentionally_unsatisfied") is True, "decoy ResultManifest lost calibration marker")

    boundary = prove_decoy_still_vulnerable(source)
    require(boundary["accepted_absolute_path"] is True, "decoy source no longer demonstrates the absolute-path boundary bug")

    require(cohort["id"] == "benchmark/phase-b2-first-five", "unexpected cohort id")
    require(cohort["stage"] == "burned", "first-five cohort is no longer burned")
    require(cohort["definition_digest"] == EXPECTED_DEFINITION_DIGEST, "burned cohort definition digest drift")
    require(all(task["evidence"]["status"] == "excluded" for task in cohort["tasks"]), "burned cohort no longer excludes all five tasks")
    task1 = [task for task in cohort["tasks"] if task["id"] == TASK_ID]
    require(len(task1) == 1, "burned cohort missing Task 001")
    require("exact" in task1[0]["evidence"]["exclusion_reason"].lower(), "Task 001 exclusion no longer records exact-line mismatch")
    burn = cohort.get("extensions", {}).get("org.idkmesh.phase_b2", {}).get("burn", {})
    require(burn.get("successor_issue") == 157, "burned cohort successor issue drift")

    finding = {
        "schema_version": "0.1",
        "id": f"{TASK_ID}/frozen-evaluator-calibration",
        "classification": "frozen_evaluator_false_negative_and_false_positive",
        "source_revision": SOURCE_SHA,
        "definition_digest": cohort["definition_digest"],
        "cohort_stage": cohort["stage"],
        "successor_issue": 157,
        "straightforward_candidate": {
            "verification_result_digest": canonical_digest(straightforward),
            "verification_status": straightforward["status"],
            "recommendation": straightforward["decision_support"]["recommendation"],
            "seeded_negative_regressions_passed": True,
            "missing_exact_added_text": straight_diag["semantic"]["missing_added_text"],
            "semantic_fragment_present_inside_real_added_line": True,
            "scope_violations": [],
        },
        "decoy_candidate": {
            "verification_result_digest": canonical_digest(decoy),
            "result_manifest_digest": canonical_digest(decoy_result),
            "verification_status": decoy["status"],
            "recommendation": decoy["decision_support"]["recommendation"],
            "objective_intentionally_unsatisfied": True,
            "exact_added_text_satisfied": True,
            "scope_violations": [],
            "absolute_path_boundary_still_vulnerable": True,
            "boundary_observation": boundary,
        },
        "interpretation": (
            "The frozen Task 001 evaluator is not calibrated to the task objective under verifier v0.1.1 exact-line semantics: "
            "it rejects the straightforward fix yet accepts an inert semantic decoy while the indexed security bug remains."
        ),
        "recommended_action": (
            "Retain the first-five cohort as burned diagnostic evidence and fix semantic matching only through the explicitly "
            "versioned successor contract tracked by issue #157; do not reinterpret or mutate frozen evaluator digests."
        ),
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

    markdown = f"""# Phase B2 Task 001 evaluator calibration\n\n**Observed:** frozen evaluator false negative + false positive.\n\n- frozen source: `{SOURCE_SHA}`\n- frozen definition digest: `{EXPECTED_DEFINITION_DIGEST}`\n- cohort status on current `main`: **burned / all five tasks excluded**\n- straightforward correct fix: **rejected**\n- straightforward absolute/traversal regression checks: **passed**\n- inert exact-line decoy: **accepted**\n- absolute-path bug after decoy: **still present**\n- successor contract issue: **#157**\n- human integration decision: **pending**\n\nThis strengthens the existing burn decision. The evaluator is not merely too strict: its exact-line proxy is also gameable. The correct response is a prospectively versioned successor evaluator contract, not a post-outcome reinterpretation of the frozen plan. No canonical write, candidate selection, approval, push, or merge authority is granted by this evidence.\n"""
    (evidence_root / "evidence-summary.md").write_text(markdown, encoding="utf-8")

    print(json.dumps(finding, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BurnEvidenceError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
