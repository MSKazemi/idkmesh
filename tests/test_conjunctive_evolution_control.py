from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import conjunctive_evolution_control as control  # noqa: E402

MATH_POLICY = json.loads((ROOT / "state/evolution-math-policy.json").read_text())
LIVE_POLICY = json.loads((ROOT / "config/evolution-policy-v1.json").read_text())


def history(*, verification=(50.0, 1.0), risk=(1.0, 50.0)):
    return {
        "beliefs": {
            "verification_strength": {"alpha": verification[0], "beta": verification[1]},
            "risk_debt": {"alpha": risk[0], "beta": risk[1]},
        }
    }


def live(*, mode="EXPLORE", blockers=None, capacity=0.9):
    return {
        "mode": mode,
        "blockers": list(blockers or []),
        "signals": {"review_capacity": capacity},
    }


class ConjunctiveEvolutionControlTests(unittest.TestCase):
    def test_perfect_history_cannot_override_live_guard(self):
        result = control.evaluate(
            history(), MATH_POLICY, live(mode="GUARD", blockers=["main_unprotected"]), LIVE_POLICY
        )
        self.assertTrue(result["history_confidence_pass"])
        self.assertFalse(result["hard_guard_pass"])
        self.assertFalse(result["bounded_experiment_escalation_candidate"])

    def test_good_history_and_clean_live_state_can_allow_bounded_experiment_candidate(self):
        result = control.evaluate(history(), MATH_POLICY, live(mode="EXPLORE", blockers=[], capacity=0.95), LIVE_POLICY)
        self.assertTrue(result["hard_guard_pass"])
        self.assertTrue(result["history_confidence_pass"])
        self.assertTrue(result["capacity_pass"])
        self.assertTrue(result["bounded_experiment_escalation_candidate"])

    def test_weak_bayesian_confidence_blocks_escalation_even_when_live_state_is_clean(self):
        result = control.evaluate(
            history(verification=(4.0, 4.0), risk=(4.0, 4.0)),
            MATH_POLICY,
            live(mode="EXPLORE", blockers=[], capacity=0.95),
            LIVE_POLICY,
        )
        self.assertFalse(result["history_confidence_pass"])
        self.assertFalse(result["bounded_experiment_escalation_candidate"])

    def test_low_review_capacity_blocks_escalation(self):
        result = control.evaluate(history(), MATH_POLICY, live(mode="EXPLORE", blockers=[], capacity=0.2), LIVE_POLICY)
        self.assertFalse(result["capacity_pass"])
        self.assertFalse(result["bounded_experiment_escalation_candidate"])

    def test_authority_is_always_non_integrating(self):
        result = control.evaluate(history(), MATH_POLICY, live(), LIVE_POLICY)
        authority = result["authority"]
        self.assertTrue(authority["recommendation_only"])
        for key in (
            "integration_authority",
            "approval_authority",
            "merge_authority",
            "branch_mutation_authority",
            "spending_authority",
        ):
            self.assertFalse(authority[key])

    def test_report_states_non_compensation_rule(self):
        result = control.evaluate(
            history(), MATH_POLICY, live(mode="GUARD", blockers=["main_unprotected"]), LIVE_POLICY
        )
        report = control.render(result)
        self.assertIn("Historical confidence cannot compensate", report)
        self.assertIn("Integration authority: **false**", report)


if __name__ == "__main__":
    unittest.main()
