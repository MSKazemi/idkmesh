#!/usr/bin/env python3
"""Fail-closed activation gate for ACE Phase B.

This module is intentionally offline and deterministic. It does not call GitHub
or mutate repository state. A separate observer/integration layer may build the
input snapshot, but stronger ACE actuation must remain disabled unless every
required check in this gate passes.

The output field ``activation_gate_passed`` is designed to feed the shadow
controller introduced by ACE v1. Missing, malformed, stale, or explicitly
blocked evidence causes a BLOCK decision.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

REQUIRED_COMPONENTS = (
    "observer",
    "lineage",
    "security",
    "controller",
    "integration_protection",
)

ACCEPTED_STATUS = "accepted"
MAX_PUBLIC_WRITE_BUDGET = 1


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any, name: str, minimum: float | None = None) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} must be numeric")
    result = float(value)
    _require(math.isfinite(result), f"{name} must be finite")
    if minimum is not None:
        _require(result >= minimum, f"{name} must be >= {minimum}")
    return result


def _boolean(value: Any, name: str) -> bool:
    _require(isinstance(value, bool), f"{name} must be boolean")
    return bool(value)


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    _require(snapshot.get("version") == 1, "snapshot version must be 1")

    components = snapshot.get("components")
    _require(isinstance(components, dict), "components must be an object")
    for name in REQUIRED_COMPONENTS:
        component = components.get(name)
        _require(isinstance(component, dict), f"components.{name} must be an object")
        status = component.get("status")
        _require(status in {"accepted", "pending", "blocked", "failed"}, f"components.{name}.status invalid")
        source = component.get("source")
        _require(isinstance(source, str) and source.strip(), f"components.{name}.source must be non-empty")

    descendants = snapshot.get("descendant_evidence")
    _require(isinstance(descendants, dict), "descendant_evidence must be an object")
    verified_count = descendants.get("verified_count")
    _require(isinstance(verified_count, int) and not isinstance(verified_count, bool), "descendant_evidence.verified_count must be an integer")
    _require(verified_count >= 0, "descendant_evidence.verified_count must be >= 0")
    _boolean(descendants.get("independently_verified"), "descendant_evidence.independently_verified")
    source = descendants.get("source")
    _require(isinstance(source, str) and source.strip(), "descendant_evidence.source must be non-empty")

    capacity = snapshot.get("review_capacity")
    _require(isinstance(capacity, dict), "review_capacity must be an object")
    capacity_value = _number(capacity.get("capacity"), "review_capacity.capacity", 0.0)
    _require(capacity_value <= 1.0, "review_capacity.capacity must be <= 1")
    minimum_capacity = _number(capacity.get("minimum_capacity"), "review_capacity.minimum_capacity", 0.0)
    _require(minimum_capacity <= 1.0, "review_capacity.minimum_capacity must be <= 1")
    _boolean(capacity.get("readable"), "review_capacity.readable")
    _boolean(capacity.get("single_writer"), "review_capacity.single_writer")
    age = _number(capacity.get("snapshot_age_hours"), "review_capacity.snapshot_age_hours", 0.0)
    max_age = _number(capacity.get("max_snapshot_age_hours"), "review_capacity.max_snapshot_age_hours", 0.0)
    _require(max_age > 0.0, "review_capacity.max_snapshot_age_hours must be > 0")
    _require(age >= 0.0, "review_capacity.snapshot_age_hours must be >= 0")

    safety = snapshot.get("safety")
    _require(isinstance(safety, dict), "safety must be an object")
    budget = safety.get("public_write_budget")
    _require(isinstance(budget, int) and not isinstance(budget, bool), "safety.public_write_budget must be an integer")
    _require(budget >= 0, "safety.public_write_budget must be >= 0")
    _boolean(safety.get("autonomous_merge_enabled"), "safety.autonomous_merge_enabled")
    _boolean(safety.get("governance_mutation_enabled"), "safety.governance_mutation_enabled")
    _boolean(safety.get("untrusted_code_execution_enabled"), "safety.untrusted_code_execution_enabled")
    _boolean(safety.get("secrets_access_enabled"), "safety.secrets_access_enabled")
    _boolean(safety.get("mass_notification_enabled"), "safety.mass_notification_enabled")


def _check(name: str, passed: bool, reason: str, source: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "reason": reason,
        "source": source,
    }


def evaluate(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)

    checks: list[dict[str, Any]] = []
    components = snapshot["components"]

    for name in REQUIRED_COMPONENTS:
        component = components[name]
        passed = component["status"] == ACCEPTED_STATUS
        checks.append(
            _check(
                f"component:{name}",
                passed,
                "reviewed/accepted" if passed else f"status={component['status']}",
                component["source"],
            )
        )

    descendants = snapshot["descendant_evidence"]
    descendant_passed = descendants["verified_count"] >= 1 and descendants["independently_verified"]
    checks.append(
        _check(
            "real_verified_descendant_evidence",
            descendant_passed,
            (
                f"verified_count={descendants['verified_count']}, independently_verified={descendants['independently_verified']}"
            ),
            descendants["source"],
        )
    )

    capacity = snapshot["review_capacity"]
    capacity_fresh = capacity["snapshot_age_hours"] <= capacity["max_snapshot_age_hours"]
    capacity_passed = (
        capacity["readable"]
        and capacity["single_writer"]
        and capacity_fresh
        and capacity["capacity"] >= capacity["minimum_capacity"]
    )
    checks.append(
        _check(
            "review_capacity",
            capacity_passed,
            (
                f"capacity={capacity['capacity']:.3f}, minimum={capacity['minimum_capacity']:.3f}, "
                f"readable={capacity['readable']}, single_writer={capacity['single_writer']}, "
                f"age_hours={capacity['snapshot_age_hours']:.3f}/{capacity['max_snapshot_age_hours']:.3f}"
            ),
            capacity.get("source"),
        )
    )

    safety = snapshot["safety"]
    write_budget_passed = safety["public_write_budget"] <= MAX_PUBLIC_WRITE_BUDGET
    checks.append(
        _check(
            "bounded_public_write_budget",
            write_budget_passed,
            f"budget={safety['public_write_budget']}, max={MAX_PUBLIC_WRITE_BUDGET}",
        )
    )

    forbidden_capabilities = {
        "autonomous_merge_enabled": safety["autonomous_merge_enabled"],
        "governance_mutation_enabled": safety["governance_mutation_enabled"],
        "untrusted_code_execution_enabled": safety["untrusted_code_execution_enabled"],
        "secrets_access_enabled": safety["secrets_access_enabled"],
        "mass_notification_enabled": safety["mass_notification_enabled"],
    }
    forbidden_enabled = sorted(name for name, enabled in forbidden_capabilities.items() if enabled)
    checks.append(
        _check(
            "forbidden_capabilities_disabled",
            not forbidden_enabled,
            "all forbidden capabilities disabled" if not forbidden_enabled else f"enabled={','.join(forbidden_enabled)}",
        )
    )

    passed = all(check["passed"] for check in checks)
    blockers = [check["name"] for check in checks if not check["passed"]]

    return {
        "version": 1,
        "decision": "PASS" if passed else "BLOCK",
        "activation_gate_passed": passed,
        "required_controller_mode_if_blocked": None if passed else "SHADOW",
        "max_public_write_budget": MAX_PUBLIC_WRITE_BUDGET,
        "blockers": blockers,
        "checks": checks,
        "invariant": "ACE Phase B remains disabled unless every independent evidence, capacity, protection, and safety check passes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the ACE Phase-B activation gate")
    parser.add_argument("snapshot", help="Path to activation-gate snapshot JSON")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    result = evaluate(snapshot)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
