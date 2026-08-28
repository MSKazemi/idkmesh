#!/usr/bin/env python3
"""Typed evidence-lattice composition for the IDKMesh Algorithm Collaboration Fabric.

The fabric deliberately does not multiply correlation confidence, adversarial
certificates, sequential confidence, and drift status into one scalar. Those
channels answer different questions under different assumptions. This module
validates their provenance/scope alignment and composes them conjunctively into a
bounded recommendation with an explicit blocker trace.

It is decision support only. It cannot manufacture merge, approval, compute, or
repository-write authority.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

AUTHORITY_LEVELS = {"observe": 0, "recommend": 1, "propose": 2}
CHANNEL_TYPES = {
    "provenance",
    "discrimination",
    "correlation",
    "contamination",
    "sequential",
    "drift",
    "hard_guard",
}


def _finite(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def make_signal(
    *,
    signal_id: str,
    producer: str,
    scope_id: str,
    claim_id: str,
    signal_type: str,
    observation_model: str,
    evidence_mass: Any,
    uncertainty: Any,
    assumptions: Sequence[str],
    failure_modes: Sequence[str],
    evidence_refs: Sequence[str],
    source_revision: str,
    authority_ceiling: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct and validate a typed ACF evidence signal."""
    signal = {
        "signal_id": signal_id,
        "producer": producer,
        "scope_id": scope_id,
        "claim_id": claim_id,
        "signal_type": signal_type,
        "observation_model": observation_model,
        "evidence_mass": evidence_mass,
        "uncertainty": uncertainty,
        "assumptions": list(assumptions),
        "failure_modes": list(failure_modes),
        "evidence_refs": list(evidence_refs),
        "source_revision": source_revision,
        "authority_ceiling": authority_ceiling,
        "payload": dict(payload),
    }
    validate_signal(signal)
    return signal


def validate_signal(signal: Mapping[str, Any]) -> None:
    required = {
        "signal_id",
        "producer",
        "scope_id",
        "claim_id",
        "signal_type",
        "observation_model",
        "evidence_mass",
        "uncertainty",
        "assumptions",
        "failure_modes",
        "evidence_refs",
        "source_revision",
        "authority_ceiling",
        "payload",
    }
    missing = sorted(required - set(signal))
    if missing:
        raise ValueError(f"signal missing required fields: {', '.join(missing)}")
    for key in (
        "signal_id",
        "producer",
        "scope_id",
        "claim_id",
        "observation_model",
        "source_revision",
    ):
        if not isinstance(signal[key], str) or not signal[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if signal["signal_type"] not in CHANNEL_TYPES:
        raise ValueError(f"unknown signal_type: {signal['signal_type']}")
    if signal["authority_ceiling"] not in AUTHORITY_LEVELS:
        raise ValueError("authority_ceiling must be observe, recommend, or propose")
    if not isinstance(signal["payload"], Mapping):
        raise ValueError("payload must be an object")
    for key in ("assumptions", "failure_modes", "evidence_refs"):
        value = signal[key]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings")
    if not signal["evidence_refs"]:
        raise ValueError("evidence_refs must not be empty")


def _index_signals(signals: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if not signals:
        raise ValueError("at least one signal is required")
    indexed: dict[str, Mapping[str, Any]] = {}
    ids: set[str] = set()
    scopes: set[str] = set()
    claims: set[str] = set()
    revisions: set[str] = set()
    for signal in signals:
        validate_signal(signal)
        signal_id = str(signal["signal_id"])
        if signal_id in ids:
            raise ValueError(f"duplicate signal_id: {signal_id}")
        ids.add(signal_id)
        signal_type = str(signal["signal_type"])
        if signal_type in indexed:
            raise ValueError(f"duplicate signal_type: {signal_type}")
        indexed[signal_type] = signal
        scopes.add(str(signal["scope_id"]))
        claims.add(str(signal["claim_id"]))
        revisions.add(str(signal["source_revision"]))
    if len(scopes) != 1:
        raise ValueError("all evidence signals must have the same scope_id")
    if len(claims) != 1:
        raise ValueError("all evidence signals must have the same claim_id")
    if len(revisions) != 1:
        raise ValueError("all evidence signals must use the same source_revision")
    return indexed


def compose_evidence_lattice(
    signals: Sequence[Mapping[str, Any]],
    *,
    min_effective_votes: float = 1.0,
) -> dict[str, Any]:
    """Compose heterogeneous evidence channels without scalarizing them.

    Required channels:
      provenance, discrimination, correlation, contamination, sequential, drift,
      and hard_guard.

    Each channel keeps its own model and uncertainty semantics. A positive
    experiment nomination requires every blocking channel to be adequate, while
    all detected blockers are preserved in the output for auditability.
    """
    threshold = _finite(min_effective_votes, "min_effective_votes")
    if threshold < 0.0:
        raise ValueError("min_effective_votes must be non-negative")
    indexed = _index_signals(signals)
    missing = sorted(CHANNEL_TYPES - set(indexed))
    if missing:
        return {
            "method": "typed-evidence-lattice-v1",
            "decision": "observe_incomplete_evidence",
            "authority": "candidate_only",
            "missing_channels": missing,
            "blockers": [
                {
                    "channel": "fabric",
                    "code": "missing_channels",
                    "detail": ",".join(missing),
                }
            ],
            "channels": {key: indexed[key] for key in sorted(indexed)},
            "composite_confidence": None,
            "scalarized_score": None,
            "double_counting_claim": False,
            "integration_authority": False,
        }

    scope_id = str(next(iter(indexed.values()))["scope_id"])
    claim_id = str(next(iter(indexed.values()))["claim_id"])
    source_revision = str(next(iter(indexed.values()))["source_revision"])
    blockers: list[dict[str, Any]] = []

    hard_guard_ok = bool(indexed["hard_guard"]["payload"].get("passed", False))
    provenance_ok = bool(indexed["provenance"]["payload"].get("valid", False))
    discrimination_ok = bool(indexed["discrimination"]["payload"].get("passed", False))

    correlation_payload = indexed["correlation"]["payload"]
    effective_votes = _finite(correlation_payload.get("effective_votes", 0.0), "effective_votes")
    if effective_votes < 0.0:
        raise ValueError("effective_votes must be non-negative")
    correlation_adequate = effective_votes >= threshold

    contamination_payload = indexed["contamination"]["payload"]
    contamination_certificate = str(
        contamination_payload.get("certificate", "uncertain_under_fault_budget")
    )
    if contamination_certificate not in {
        "support_certified",
        "reject_certified",
        "uncertain_under_fault_budget",
    }:
        raise ValueError("unknown contamination certificate")

    sequential_payload = indexed["sequential"]["payload"]
    sequential_decision = str(sequential_payload.get("decision", "observe"))
    if sequential_decision not in {
        "experiment_candidate",
        "observe",
        "insufficient_effect",
        "observe_low_ess",
        "observe_clipped",
        "guarded",
    }:
        raise ValueError("unknown sequential decision")

    drift_payload = indexed["drift"]["payload"]
    drift_detected = bool(drift_payload.get("detected_change", False))

    if not hard_guard_ok:
        blockers.append(
            {"channel": "hard_guard", "code": "hard_guard_failed", "detail": "governance guard failed"}
        )
    if not provenance_ok:
        blockers.append(
            {"channel": "provenance", "code": "invalid_provenance", "detail": "evidence provenance/admission failed"}
        )
    if not discrimination_ok:
        blockers.append(
            {"channel": "discrimination", "code": "non_discriminating", "detail": "verification instrument failed discrimination screen"}
        )
    if not correlation_adequate:
        blockers.append(
            {
                "channel": "correlation",
                "code": "low_effective_evidence",
                "detail": f"effective_votes={effective_votes} < {threshold}",
            }
        )
    if contamination_certificate == "uncertain_under_fault_budget":
        blockers.append(
            {
                "channel": "contamination",
                "code": "adversarial_uncertainty",
                "detail": "fault-budget envelope overlaps the decision region",
            }
        )
    elif contamination_certificate == "reject_certified":
        blockers.append(
            {
                "channel": "contamination",
                "code": "robust_rejection",
                "detail": "every admissible honest-report mean rejects support",
            }
        )
    if drift_detected:
        blockers.append(
            {
                "channel": "drift",
                "code": "regime_change_detected",
                "detail": "temporal evidence should not be pooled across the detected change without review",
            }
        )
    if sequential_decision != "experiment_candidate":
        blockers.append(
            {
                "channel": "sequential",
                "code": "sequential_not_candidate",
                "detail": sequential_decision,
            }
        )

    # Decision priority is intentionally non-compensatory. Keep all blockers in
    # the artifact, while exposing one bounded operational recommendation.
    codes = {blocker["code"] for blocker in blockers}
    if "hard_guard_failed" in codes:
        decision = "guarded"
    elif "invalid_provenance" in codes:
        decision = "observe_invalid_provenance"
    elif "non_discriminating" in codes:
        decision = "observe_non_discriminating"
    elif "low_effective_evidence" in codes:
        decision = "observe_correlation_uncertainty"
    elif "robust_rejection" in codes:
        decision = "insufficient_support"
    elif "adversarial_uncertainty" in codes:
        decision = "observe_adversarial_uncertainty"
    elif "regime_change_detected" in codes:
        decision = "observe_drift"
    elif "sequential_not_candidate" in codes:
        decision = (
            "insufficient_effect"
            if sequential_decision == "insufficient_effect"
            else "observe"
        )
    else:
        decision = "experiment_candidate"

    maximum_input_authority = max(
        AUTHORITY_LEVELS[str(signal["authority_ceiling"])] for signal in indexed.values()
    )
    return {
        "method": "typed-evidence-lattice-v1",
        "scope_id": scope_id,
        "claim_id": claim_id,
        "source_revision": source_revision,
        "decision": decision,
        "authority": "candidate_only",
        "maximum_input_authority_level": maximum_input_authority,
        "min_effective_votes": threshold,
        "blockers": blockers,
        "channels": {key: indexed[key] for key in sorted(indexed)},
        # Deliberately absent as a meaningful number. These fields make scalar
        # collapse visibly impossible for downstream consumers expecting this API.
        "composite_confidence": None,
        "scalarized_score": None,
        "double_counting_claim": False,
        "truth_claim": False,
        "sybil_resistance_claim": False,
        "integration_authority": False,
    }


def _demo_signal(signal_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    models = {
        "provenance": "deterministic-provenance-validation",
        "discrimination": "held-out-discrimination-screen",
        "correlation": "equicorrelation-effective-evidence",
        "contamination": "sharp-count-contamination-envelope",
        "sequential": "paired-union-hoeffding",
        "drift": "anytime-two-window-union-hoeffding",
        "hard_guard": "deterministic-governance-invariant",
    }
    return make_signal(
        signal_id=f"demo-{signal_type}",
        producer=f"demo/{signal_type}/v1",
        scope_id="experiment:demo-policy",
        claim_id="candidate-improves-baseline",
        signal_type=signal_type,
        observation_model=models[signal_type],
        evidence_mass={"kind": "demo", "count": 64},
        uncertainty={"model_specific": True},
        assumptions=["demo fixture"],
        failure_modes=["model misspecification"],
        evidence_refs=[f"artifact://demo/{signal_type}"],
        source_revision="demo-revision-001",
        authority_ceiling="propose" if signal_type == "sequential" else "recommend",
        payload=payload,
    )


def build_demo() -> dict[str, Any]:
    base = [
        _demo_signal("provenance", {"valid": True}),
        _demo_signal("discrimination", {"passed": True}),
        _demo_signal(
            "correlation",
            {"posterior_probability": 0.92, "effective_votes": 3.4},
        ),
        _demo_signal(
            "contamination",
            {
                "certificate": "support_certified",
                "max_faults": 1,
                "honest_mean_lower": 0.72,
                "honest_mean_upper": 0.91,
            },
        ),
        _demo_signal(
            "sequential",
            {
                "decision": "experiment_candidate",
                "lower_confidence": 0.14,
                "upper_confidence": 0.31,
            },
        ),
        _demo_signal("drift", {"detected_change": False}),
        _demo_signal("hard_guard", {"passed": True}),
    ]
    all_clear = compose_evidence_lattice(base, min_effective_votes=2.0)

    adversarial = [dict(signal) for signal in base]
    for signal in adversarial:
        if signal["signal_type"] == "contamination":
            signal["payload"] = {
                "certificate": "uncertain_under_fault_budget",
                "max_faults": 2,
                "honest_mean_lower": 0.42,
                "honest_mean_upper": 0.85,
            }
    adversarial_block = compose_evidence_lattice(adversarial, min_effective_votes=2.0)

    drifted = [dict(signal) for signal in base]
    for signal in drifted:
        if signal["signal_type"] == "drift":
            signal["payload"] = {"detected_change": True}
    drift_block = compose_evidence_lattice(drifted, min_effective_votes=2.0)

    guarded = [dict(signal) for signal in base]
    for signal in guarded:
        if signal["signal_type"] == "hard_guard":
            signal["payload"] = {"passed": False}
    hard_guard_block = compose_evidence_lattice(guarded, min_effective_votes=2.0)

    return {
        "all_channels_clear": all_clear,
        "adversarial_uncertainty_blocks": adversarial_block,
        "drift_blocks": drift_block,
        "hard_guard_dominates": hard_guard_block,
        "invariants": {
            "all_clear_can_only_nominate": all_clear["decision"] == "experiment_candidate"
            and all_clear["authority"] == "candidate_only",
            "no_composite_confidence": all_clear["composite_confidence"] is None
            and all_clear["scalarized_score"] is None,
            "adversarial_channel_blocks": adversarial_block["decision"]
            == "observe_adversarial_uncertainty",
            "drift_channel_blocks": drift_block["decision"] == "observe_drift",
            "hard_guard_non_compensation": hard_guard_block["decision"] == "guarded",
            "integration_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="emit a deterministic demonstration")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    if not args.demo:
        parser.error("--demo is currently required")
    payload = build_demo()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
