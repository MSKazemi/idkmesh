#!/usr/bin/env python3
"""CI entrypoint for Task 001 v0.4 calibration with separated control/source roots.

The exact burned source revision predates the later first-five cohort index. The
behavioral path-boundary probe therefore uses a self-contained scaffold built
only from files that existed at the frozen source SHA. Separately, this wrapper
requires the current evaluator control plane to retain the original cohort as
burned with its original definition digest.
"""

from __future__ import annotations

import sys

import task001_evaluator_calibration_v04 as calibration

BURNED_DEFINITION_DIGEST = (
    "sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c"
)
CONTROL_COHORT = calibration.ROOT / "benchmarks/phase-b2-first-five/cohort.json"


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
        all(task.get("evidence", {}).get("status") == "excluded" for task in cohort.get("tasks", [])),
        "burned Phase B2 cohort contains a non-excluded task outcome",
    )


def main() -> int:
    verify_control_plane_burn()
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
