import copy
import unittest

from scripts.evidence_aggregation_fabric import (
    compose_evidence_lattice,
    make_signal,
    validate_signal,
)


MODELS = {
    "provenance": "deterministic-provenance-validation",
    "discrimination": "held-out-discrimination-screen",
    "correlation": "equicorrelation-effective-evidence",
    "contamination": "sharp-count-contamination-envelope",
    "sequential": "paired-union-hoeffding",
    "drift": "anytime-two-window-union-hoeffding",
    "hard_guard": "deterministic-governance-invariant",
}


def signal(signal_type, payload, *, scope="experiment:one", claim="improves-baseline", revision="abc123"):
    return make_signal(
        signal_id=f"sig-{signal_type}",
        producer=f"test/{signal_type}",
        scope_id=scope,
        claim_id=claim,
        signal_type=signal_type,
        observation_model=MODELS[signal_type],
        evidence_mass={"count": 10},
        uncertainty={"model_specific": True},
        assumptions=["test fixture"],
        failure_modes=["model misspecification"],
        evidence_refs=[f"artifact://{signal_type}"],
        source_revision=revision,
        authority_ceiling="propose" if signal_type == "sequential" else "recommend",
        payload=payload,
    )


def clear_signals():
    return [
        signal("provenance", {"valid": True}),
        signal("discrimination", {"passed": True}),
        signal("correlation", {"effective_votes": 3.0, "posterior_probability": 0.9}),
        signal("contamination", {"certificate": "support_certified", "max_faults": 1}),
        signal("sequential", {"decision": "experiment_candidate"}),
        signal("drift", {"detected_change": False}),
        signal("hard_guard", {"passed": True}),
    ]


class EvidenceAggregationFabricTests(unittest.TestCase):
    def test_all_clear_only_nominates_candidate(self):
        result = compose_evidence_lattice(clear_signals(), min_effective_votes=2.0)
        self.assertEqual(result["decision"], "experiment_candidate")
        self.assertEqual(result["authority"], "candidate_only")
        self.assertFalse(result["integration_authority"])
        self.assertEqual(result["blockers"], [])

    def test_no_scalar_confidence_is_manufactured(self):
        result = compose_evidence_lattice(clear_signals())
        self.assertIsNone(result["composite_confidence"])
        self.assertIsNone(result["scalarized_score"])
        self.assertFalse(result["double_counting_claim"])
        self.assertFalse(result["truth_claim"])
        self.assertFalse(result["sybil_resistance_claim"])

    def test_hard_guard_dominates_every_positive_channel(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "hard_guard":
                item["payload"] = {"passed": False}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "guarded")
        self.assertIn("hard_guard_failed", {b["code"] for b in result["blockers"]})

    def test_invalid_provenance_blocks_nomination(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "provenance":
                item["payload"] = {"valid": False}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "observe_invalid_provenance")

    def test_non_discriminating_verifier_blocks_before_correlation_strength(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "discrimination":
                item["payload"] = {"passed": False}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "observe_non_discriminating")

    def test_low_effective_evidence_blocks_even_with_high_posterior(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "correlation":
                item["payload"] = {"effective_votes": 0.75, "posterior_probability": 0.999}
        result = compose_evidence_lattice(signals, min_effective_votes=2.0)
        self.assertEqual(result["decision"], "observe_correlation_uncertainty")

    def test_adversarial_uncertainty_blocks_naive_positive_channels(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "contamination":
                item["payload"] = {"certificate": "uncertain_under_fault_budget", "max_faults": 2}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "observe_adversarial_uncertainty")

    def test_robust_rejection_is_not_overridden_by_sequential_candidate(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "contamination":
                item["payload"] = {"certificate": "reject_certified", "max_faults": 1}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "insufficient_support")

    def test_drift_blocks_pooled_candidate(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "drift":
                item["payload"] = {"detected_change": True}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "observe_drift")

    def test_sequential_insufficient_effect_is_preserved(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "sequential":
                item["payload"] = {"decision": "insufficient_effect"}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "insufficient_effect")

    def test_all_blockers_are_retained_even_when_hard_guard_wins(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "hard_guard":
                item["payload"] = {"passed": False}
            elif item["signal_type"] == "drift":
                item["payload"] = {"detected_change": True}
            elif item["signal_type"] == "contamination":
                item["payload"] = {"certificate": "uncertain_under_fault_budget"}
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "guarded")
        codes = {blocker["code"] for blocker in result["blockers"]}
        self.assertTrue({"hard_guard_failed", "regime_change_detected", "adversarial_uncertainty"}.issubset(codes))

    def test_missing_channel_fails_closed(self):
        signals = [item for item in clear_signals() if item["signal_type"] != "drift"]
        result = compose_evidence_lattice(signals)
        self.assertEqual(result["decision"], "observe_incomplete_evidence")
        self.assertEqual(result["missing_channels"], ["drift"])

    def test_scope_mismatch_is_rejected_not_averaged(self):
        signals = clear_signals()
        signals[-1] = signal("hard_guard", {"passed": True}, scope="experiment:other")
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_claim_mismatch_is_rejected(self):
        signals = clear_signals()
        signals[-1] = signal("hard_guard", {"passed": True}, claim="different-claim")
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_revision_mismatch_is_rejected(self):
        signals = clear_signals()
        signals[-1] = signal("hard_guard", {"passed": True}, revision="different-sha")
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_duplicate_channel_is_rejected(self):
        signals = clear_signals() + [signal("drift", {"detected_change": False})]
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_signal_requires_evidence_reference(self):
        broken = clear_signals()[0]
        broken["evidence_refs"] = []
        with self.assertRaises(ValueError):
            validate_signal(broken)

    def test_unknown_sequential_decision_fails_closed(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "sequential":
                item["payload"] = {"decision": "merge_now"}
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_negative_effective_votes_fails_closed(self):
        signals = clear_signals()
        for item in signals:
            if item["signal_type"] == "correlation":
                item["payload"] = {"effective_votes": -1.0}
        with self.assertRaises(ValueError):
            compose_evidence_lattice(signals)

    def test_control_booleans_reject_truthy_strings_and_numbers(self):
        cases = [
            ("hard_guard", {"passed": "false"}),
            ("provenance", {"valid": 1}),
            ("discrimination", {"passed": "true"}),
            ("drift", {"detected_change": "false"}),
        ]
        for signal_type, payload in cases:
            with self.subTest(signal_type=signal_type, payload=payload):
                signals = clear_signals()
                for item in signals:
                    if item["signal_type"] == signal_type:
                        item["payload"] = payload
                with self.assertRaises(ValueError):
                    compose_evidence_lattice(signals)

    def test_control_booleans_are_required_not_defaulted(self):
        for signal_type in ("hard_guard", "provenance", "discrimination", "drift"):
            with self.subTest(signal_type=signal_type):
                signals = clear_signals()
                for item in signals:
                    if item["signal_type"] == signal_type:
                        item["payload"] = {}
                with self.assertRaises(ValueError):
                    compose_evidence_lattice(signals)


if __name__ == "__main__":
    unittest.main()
