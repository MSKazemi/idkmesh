#!/usr/bin/env python3
"""CI entrypoint for Task 001 v0.4 calibration on the canonical #171 verifier.

The exact burned source revision predates the later first-five cohort index. The
behavioral path-boundary probe therefore uses the self-contained scaffold built
by ``task001_evaluator_calibration_v04`` from files that existed at the frozen
source SHA. Separately, this wrapper verifies that the durable public cohort is
still the same burned pre-outcome commitment.

The final #170 calibration harness also contained one assertion coupled to the
*wording* of its divergent verifier finding. Canonical #171 rejects the same
decoy but uses a different finding sentence. This wrapper defers only that one
prose-coupled assertion and replaces it after the run with stronger checks over
#171's machine-readable ``semantic_removed_substrings`` observation and metrics.
Candidate construction, pass/reject expectations, behavioral assertions, plan
binding, and verifier semantics are not changed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import task001_evaluator_calibration_v04 as calibration

BURNED_DEFINITION_DIGEST = (
    "sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c"
)
CONTROL_COHORT = calibration.ROOT / "benchmarks/phase-b2-first-five/cohort.json"
REMOVED_REQUIREMENT = "(ROOT / args.cohort).resolve()"
PROSE_COUPLED_ASSERTION = (
    "decoy rejection lacks removed-transformation correctness evidence"
)
DEFAULT_OUTPUT_ROOT = "results/verification/task001-v04-calibration"


def verify_control_plane_burn() -> None:
    """Fail closed if the durable burned cohort was rewritten or resurrected."""

    calibration.require(
        CONTROL_COHORT.is_file(),
        "evaluator control checkout lacks burned cohort definition",
    )
    cohort = calibration.load_json(CONTROL_COHORT)
    calibration.require(
        cohort.get("id") == "benchmark/phase-b2-first-five",
        "unexpected evaluator-owned cohort identity",
    )
    calibration.require(
        cohort.get("stage") == "burned",
        "Phase B2 first-five control cohort is no longer burned",
    )
    calibration.require(
        cohort.get("definition_digest") == BURNED_DEFINITION_DIGEST,
        "burned Phase B2 definition digest drift",
    )
    calibration.require(
        all(
            task.get("evidence", {}).get("status") == "excluded"
            for task in cohort.get("tasks", [])
        ),
        "burned Phase B2 cohort contains a non-excluded task outcome",
    )


def requested_output_root() -> Path:
    raw = DEFAULT_OUTPUT_ROOT
    if "--output-root" in sys.argv:
        index = sys.argv.index("--output-root")
        calibration.require(
            index + 1 < len(sys.argv),
            "--output-root is missing its value",
        )
        raw = sys.argv[index + 1]
    return calibration.ensure_output_root(raw)


def verify_canonical_removed_transition_evidence(output_root: Path) -> None:
    """Assert #171's structured decoy evidence, independent of prose wording."""

    path = output_root / "inert-decoy" / "verification-result.json"
    calibration.require(path.is_file(), "canonical decoy VerificationResult is missing")
    value = calibration.load_json(path)

    calibration.require(
        value.get("status") == "failed",
        "canonical v0.4 did not fail the inert decoy",
    )
    calibration.require(
        value.get("decision_support", {}).get("recommendation") == "reject_candidate",
        "canonical v0.4 did not recommend rejecting the inert decoy",
    )
    calibration.require(
        value.get("verifier", {}).get("adapter_version") == "0.3.0",
        "canonical decoy result is not verifier adapter 0.3.0",
    )

    independent = next(
        (
            check
            for check in value.get("checks", [])
            if check.get("id") == "independent-review"
        ),
        None,
    )
    calibration.require(
        isinstance(independent, dict),
        "canonical decoy result omitted independent-review",
    )
    diagnostics = json.loads(independent.get("diagnostics") or "{}")
    removed = diagnostics.get("semantic_removed_substrings")
    calibration.require(
        isinstance(removed, dict),
        "canonical decoy result omitted semantic_removed_substrings diagnostics",
    )
    calibration.require(
        removed.get("parse_error") is None,
        "canonical decoy transition evidence has a patch parse error",
    )
    calibration.require(
        REMOVED_REQUIREMENT in removed.get("required_removed_substrings", []),
        "canonical decoy diagnostics lost the required removed substring",
    )
    calibration.require(
        REMOVED_REQUIREMENT in removed.get("missing_substrings", []),
        "canonical decoy diagnostics do not prove the unsafe substring remained unremoved",
    )
    calibration.require(
        value.get("metrics", {}).get("required_removed_substring_count") == 1,
        "canonical decoy result has unexpected required removal count",
    )
    calibration.require(
        value.get("metrics", {}).get("matched_removed_substring_count") == 0,
        "canonical decoy result unexpectedly matched the required removal",
    )
    calibration.require(
        any(
            finding.get("category") == "correctness"
            for finding in value.get("findings", [])
        ),
        "canonical decoy rejection lacks a correctness finding",
    )


def main() -> int:
    verify_control_plane_burn()
    output_root = requested_output_root()

    original_require = calibration.require

    def canonical_compat_require(condition: bool, message: str) -> None:
        if message == PROSE_COUPLED_ASSERTION:
            # #170 asserted its own verifier's finding *sentence*. Defer only
            # that wording check; structured canonical evidence is required
            # immediately after the unchanged calibration run completes.
            return
        original_require(condition, message)

    calibration.require = canonical_compat_require
    try:
        result = calibration.main()
    finally:
        calibration.require = original_require

    verify_canonical_removed_transition_evidence(output_root)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        calibration.CalibrationError,
        OSError,
        calibration.json.JSONDecodeError,
        calibration.local_verifier.VerifierError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
