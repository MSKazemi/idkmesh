#!/usr/bin/env python3
"""Bind the real node -> verifier E2E harness to current frozen contracts."""

from __future__ import annotations

import node_verifier_e2e as e2e

# Keep the reusable historical harness stable, but bind the active replay to the
# current exact worker candidate and current evaluator-plan contract.
e2e.CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"
_original_build_plan = e2e.build_plan


def _current_build_plan(work_unit):
    plan = _original_build_plan(work_unit)
    plan["backend"]["required_log_types"] = ["stdout", "stderr"]
    plan["verifier"]["adapter_version"] = "0.1.1"
    return plan


e2e.build_plan = _current_build_plan

if __name__ == "__main__":
    raise SystemExit(e2e.main())
