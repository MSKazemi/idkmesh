#!/usr/bin/env python3
"""CI entrypoint for Task 001 v0.4 calibration with separated control/source roots.

The burned source revision predates the later benchmark cohort index. Behavioral
path-boundary calibration needs a valid cohort JSON *outside* the historical
source checkout, but it must not pretend that the cohort file existed at that
source revision.

This wrapper therefore supplies the burned cohort definition from the
**evaluator-owned control checkout** while the target program under test remains
entirely from the exact frozen source checkout. It then delegates all candidate
construction, metadata-only verification, behavioral checks, and authority
assertions to ``task001_evaluator_calibration_v04`` unchanged.
"""

from __future__ import annotations

from pathlib import Path
import sys

import task001_evaluator_calibration_v04 as calibration

BURNED_DEFINITION_DIGEST = (
    "sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c"
)
CONTROL_COHORT = (
    calibration.ROOT / "benchmarks/phase-b2-first-five/cohort.json"
)


def evaluator_owned_outside_cohort_path(source: Path) -> Path:
    """Materialize a valid cohort fixture outside the immutable source checkout."""

    calibration.require(
        CONTROL_COHORT.is_file(),
        "evaluator control checkout lacks burned cohort definition",
    )
    cohort = calibration.load_json(CONTROL_COHORT)
    calibration.require(
        cohort.get("definition_digest") == BURNED_DEFINITION_DIGEST,
        "evaluator-owned cohort fixture is not the burned Phase B2 definition",
    )
    calibration.require(
        cohort.get("id") == "benchmark/phase-b2-first-five",
        "unexpected evaluator-owned cohort fixture identity",
    )

    outside = source.parent / "idkmesh-task001-outside-cohort.json"
    outside.write_text(CONTROL_COHORT.read_text(encoding="utf-8"), encoding="utf-8")
    return outside


def main() -> int:
    # Deliberately patch only fixture provenance. Candidate transformations,
    # verifier semantics, and behavioral assertions remain in the reviewed
    # calibration module and are not weakened here.
    calibration.outside_cohort_path = evaluator_owned_outside_cohort_path
    return calibration.main()


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
