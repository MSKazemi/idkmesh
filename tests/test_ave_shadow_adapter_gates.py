"""Regression pins for the #644 hard gates and the lexicographic ordering.

``test_ave_shadow_adapter.py`` pins the digest and source-revision gates and the
reliability-neutrality rules.  The issue also lists six further hard gates and an
eight-step ordering; this module pins each of them one at a time so a refactor
cannot silently drop one.  Every case is a pure function of a literal fixture:
no clock, no network, no randomness.
"""

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent

_spec = importlib.util.spec_from_file_location(
    "ave_shadow_adapter_fixtures",
    HERE / "test_ave_shadow_adapter.py",
)
fixtures = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = fixtures
assert _spec.loader is not None
_spec.loader.exec_module(fixtures)

# Hard-gate ids exactly as the adapter emits them.
ALL_GATES = {
    "work-unit-v0.2",
    "exact-work-unit-digest",
    "work-unit-id-version-binding",
    "source-revision-binding",
    "verifier-pool-binding",
    "evaluator-sovereignty",
    "zero-project-spend",
    "independent-verification-policy",
    "required-validator-binding",
}


def failed_gates(plan):
    return {g["id"] for g in plan["hard_gates"] if g["status"] == "fail"}


def chosen(plan):
    return fixtures.selected_ids(plan)


class HardGateTests(unittest.TestCase):
    """Each gate failing alone must freeze an abstention, not drop the plan."""

    def build_failing(self, mutate_wu=None, mutate_plan=None, pool_overrides=None):
        wu = fixtures.work_unit()
        plan = fixtures.evaluator_plan(wu)
        if mutate_plan is not None:
            mutate_plan(plan)
        if mutate_wu is not None:
            # Mutate after the plan digest was taken only where the test wants a
            # digest-consistent plan, so re-bind the digest to isolate one gate.
            mutate_wu(wu)
            plan["binding"]["work_unit_digest"] = fixtures.adapter.canonical_digest(wu)
            plan["binding"]["work_unit_version"] = wu["version"]
            plan["binding"]["work_unit_id"] = wu["id"]
        result = fixtures.build(
            wu,
            [fixtures.candidate("v1", "family-a")],
            plan=plan,
            pool_overrides=pool_overrides,
        )
        return result

    def assert_only_gate_fails(self, result, gate_id):
        self.assertEqual(failed_gates(result), {gate_id})
        self.assertIsNone(result["recommendation"]["selected_choice_id"])
        # The observation is kept: a frozen plan with the gates recorded.
        self.assertEqual({g["id"] for g in result["hard_gates"]}, ALL_GATES)
        self.assertFalse(result["authority"]["dispatch"])

    def test_baseline_fixture_passes_every_gate(self):
        result = self.build_failing()
        self.assertEqual(failed_gates(result), set())
        self.assertEqual({g["id"] for g in result["hard_gates"]}, ALL_GATES)
        self.assertIsNotNone(result["recommendation"]["selected_choice_id"])

    def test_work_unit_id_binding_mismatch(self):
        def mutate(plan):
            plan["binding"]["work_unit_id"] = "someone/else"

        result = self.build_failing(mutate_plan=mutate)
        # Digest still matches the unmodified WorkUnit; only id/version differ.
        self.assert_only_gate_fails(result, "work-unit-id-version-binding")

    def test_work_unit_version_binding_mismatch(self):
        def mutate(plan):
            plan["binding"]["work_unit_version"] = 2

        result = self.build_failing(mutate_plan=mutate)
        self.assert_only_gate_fails(result, "work-unit-id-version-binding")

    def test_pool_repository_binding_mismatch(self):
        result = self.build_failing(pool_overrides={"repository": "other/repo"})
        self.assert_only_gate_fails(result, "verifier-pool-binding")

    def test_pool_work_unit_binding_mismatch(self):
        result = self.build_failing(pool_overrides={"work_unit_id": "other/unit"})
        self.assert_only_gate_fails(result, "verifier-pool-binding")

    def test_evaluator_sovereignty_missing(self):
        def mutate(plan):
            plan["policy"]["require_verifier_distinct_from_worker"] = False

        result = self.build_failing(mutate_plan=mutate)
        self.assert_only_gate_fails(result, "evaluator-sovereignty")

    def test_nonzero_project_spend(self):
        def mutate(wu):
            wu["budget"]["project_spend_usd_max"] = 0.01

        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "zero-project-spend")

    def test_paid_fallback_allowed(self):
        def mutate(wu):
            wu["budget"]["paid_fallback_allowed"] = True

        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "zero-project-spend")

    def test_boolean_spend_is_not_accepted_as_zero(self):
        def mutate(wu):
            wu["budget"]["project_spend_usd_max"] = False

        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "zero-project-spend")

    def test_independent_verification_not_required(self):
        def mutate(wu):
            wu["verification_policy"]["independent_from_worker"] = False

        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "independent-verification-policy")

    def test_evaluator_plan_omits_required_validator(self):
        def mutate(wu):
            wu["validators"].append(
                {"id": "extra-check", "type": "test", "required": True}
            )

        # Digest is re-bound by build_failing, so only coverage is wrong.
        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "required-validator-binding")

    def test_unsupported_work_unit_schema_version(self):
        def mutate(wu):
            wu["schema_version"] = "0.1"

        result = self.build_failing(mutate_wu=mutate)
        self.assert_only_gate_fails(result, "work-unit-v0.2")

    def test_gate_failure_does_not_mutate_inputs(self):
        wu = fixtures.work_unit()
        plan = fixtures.evaluator_plan(wu)
        plan["policy"]["require_verifier_distinct_from_worker"] = False
        before = (copy.deepcopy(wu), copy.deepcopy(plan))
        fixtures.build(wu, [fixtures.candidate("v1", "family-a")], plan=plan)
        self.assertEqual((wu, plan), before)


class RiskTargetTests(unittest.TestCase):
    def test_critical_matches_high_floor(self):
        wu = fixtures.work_unit(risk="critical", minimum=1)
        self.assertEqual(fixtures.adapter._risk_target(wu), 3)

    def test_low_uses_floor_of_one_over_zero_minimum(self):
        wu = fixtures.work_unit(risk="low", minimum=0)
        self.assertEqual(fixtures.adapter._risk_target(wu), 1)

    def test_critical_selects_three_distinct_families(self):
        wu = fixtures.work_unit(risk="critical")
        result = fixtures.build(
            wu,
            [
                fixtures.candidate("a", "family-a"),
                fixtures.candidate("b", "family-b"),
                fixtures.candidate("c", "family-c"),
                fixtures.candidate("d", "family-d"),
            ],
        )
        self.assertEqual(len(chosen(result)), 3)
        self.assertEqual(
            result["recommendation"]["selected_choice_id"].count("+"), 2
        )


class LexicographicOrderTests(unittest.TestCase):
    """Steps 2-8 of the issue's ordering, each decided by exactly one signal."""

    def pick(self, candidates, risk="low"):
        result = fixtures.build(fixtures.work_unit(risk=risk), candidates)
        return chosen(result)

    def test_step1_family_diversity_dominates_everything_below(self):
        # One-verifier target would pick the better single; with medium risk the
        # distinct-family pair must win over a same-family pair with far more
        # live evidence.
        ids = self.pick(
            [
                fixtures.candidate("a1", "fa", alpha=90, beta=1, samples=500),
                fixtures.candidate("a2", "fa", alpha=90, beta=1, samples=500),
                fixtures.candidate("b1", "fb", alpha=1, beta=1, samples=2),
            ],
            risk="medium",
        )
        self.assertIn("b1", ids)

    def test_step2_fewer_correlation_signals_beats_better_reliability(self):
        ids = self.pick(
            [
                fixtures.candidate(
                    "correlated", "fa", alpha=90, beta=1, samples=500,
                    shared_model=True, shared_runtime=True,
                ),
                # No live support at all: step 2 must still outrank step 3.
                fixtures.candidate(
                    "clean", "fb", basis="synthetic", alpha=2, beta=2, samples=4,
                ),
            ]
        )
        self.assertEqual(ids, ["clean"])

    def test_step2_counts_each_signal_separately(self):
        ids = self.pick(
            [
                fixtures.candidate("both", "fa", shared_model=True, shared_runtime=True),
                fixtures.candidate("one", "fb", shared_model=True),
            ]
        )
        self.assertEqual(ids, ["one"])

    def test_step3_live_support_beats_sample_count_and_reliability(self):
        ids = self.pick(
            [
                # No fresh same-domain live support despite a huge synthetic prior.
                fixtures.candidate(
                    "synthetic", "fa", basis="synthetic",
                    alpha=99, beta=1, samples=900,
                ),
                fixtures.candidate("live", "fb", alpha=2, beta=2, samples=3),
            ]
        )
        self.assertEqual(ids, ["live"])

    def test_step4_more_live_samples_beats_higher_mean(self):
        ids = self.pick(
            [
                fixtures.candidate("few", "fa", alpha=19, beta=1, samples=4),
                fixtures.candidate("many", "fb", alpha=6, beta=4, samples=40),
            ]
        )
        self.assertEqual(ids, ["many"])

    def test_step5_higher_posterior_mean_when_samples_tie(self):
        ids = self.pick(
            [
                fixtures.candidate("weak", "fa", alpha=5, beta=5, samples=10),
                fixtures.candidate("strong", "fb", alpha=9, beta=1, samples=10),
            ]
        )
        self.assertEqual(ids, ["strong"])

    def test_step6_lower_review_units_when_reliability_ties(self):
        ids = self.pick(
            [
                fixtures.candidate("costly", "fa", review=5.0),
                fixtures.candidate("cheap", "fb", review=1.0),
            ]
        )
        self.assertEqual(ids, ["cheap"])

    def test_step7_lower_queue_load_when_review_ties(self):
        ids = self.pick(
            [
                fixtures.candidate("busy", "fa", queue=9.0),
                fixtures.candidate("idle", "fb", queue=0.0),
            ]
        )
        self.assertEqual(ids, ["idle"])

    def test_step8_id_tie_break_is_deterministic(self):
        pool = [
            fixtures.candidate("zeta", "fa"),
            fixtures.candidate("alpha", "fb"),
        ]
        self.assertEqual(self.pick(pool), ["alpha"])
        self.assertEqual(self.pick(list(reversed(pool))), ["alpha"])

    def test_no_global_reputation_leaks_across_work_units(self):
        # The same verifier, evaluated for a wrong-domain pool, earns no
        # positive ordering: the live-supported tier must not credit it.
        wu = fixtures.work_unit()
        wrong = fixtures.candidate("wrong", "fa", domain="other-domain", samples=500)
        right = fixtures.candidate("right", "fb", alpha=2, beta=2, samples=3)
        result = fixtures.build(wu, [wrong, right])
        self.assertEqual(chosen(result), ["right"])


class AuthorityBoundaryTests(unittest.TestCase):
    def test_every_plan_is_advisory_only(self):
        wu = fixtures.work_unit()
        for candidates in (
            [fixtures.candidate("v1", "fa")],
            [fixtures.candidate("v1", "fa", available=False)],  # abstention
        ):
            result = fixtures.build(wu, candidates)
            authority = result["authority"]
            self.assertTrue(authority, "authority block must be present")
            self.assertIs(authority["advisory_only"], True)
            self.assertFalse(
                any(v for k, v in authority.items() if k != "advisory_only"),
                authority,
            )


if __name__ == "__main__":
    unittest.main()
