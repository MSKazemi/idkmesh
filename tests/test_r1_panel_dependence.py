from __future__ import annotations

import dataclasses
import math
import random
import unittest

from randomness_lab.r1 import R1ExperimentConfig, Verifier, build_r1_conditions, run_r1_condition
from randomness_lab.verifier_dependence import sample_panel_correctness
from sim.e018_dependence_models import item_difficulty_error, shared_shock_error


def _binary_correlation(xs: list[int], ys: list[int]) -> float:
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    covariance = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    xx = sum((x - mx) ** 2 for x in xs)
    yy = sum((y - my) ** 2 for y in ys)
    return covariance / math.sqrt(xx * yy)


def _base_condition(**overrides):
    base = build_r1_conditions(R1ExperimentConfig(swarm_size=5))[0]
    verifiers = tuple(Verifier(f"panel-{i}") for i in range(1, 6))
    return dataclasses.replace(
        base,
        verifiers=verifiers,
        panel_size=5,
        verifier_error_correlation=0.0,
        **overrides,
    )


class PanelDependenceSamplerTests(unittest.TestCase):
    def test_shapes_are_sample_and_rng_identical_at_rho_endpoints(self) -> None:
        for rho in (0.0, 1.0):
            left = random.Random(2718)
            right = random.Random(2718)
            for _ in range(100):
                self.assertEqual(
                    sample_panel_correctness(5, 0.8, rho, "shared_shock", left),
                    sample_panel_correctness(5, 0.8, rho, "item_difficulty", right),
                )
            self.assertEqual(left.getstate(), right.getstate())

    def test_e018_analytic_models_also_agree_at_rho_endpoints(self) -> None:
        for rho in (0.0, 1.0):
            with self.subTest(rho=rho):
                self.assertAlmostEqual(
                    shared_shock_error(5, 0.8, rho, 0.5),
                    item_difficulty_error(5, 0.8, rho, 0.5),
                    places=15,
                )

    def test_intermediate_panel_error_matches_e018_oracle(self) -> None:
        trials = 40_000
        n = 5
        accuracy = 0.8
        rho = 0.4
        need = n // 2 + 1
        for shape, oracle in (
            ("shared_shock", shared_shock_error),
            ("item_difficulty", item_difficulty_error),
        ):
            with self.subTest(shape=shape):
                rng = random.Random(1729)
                errors = 0
                for _ in range(trials):
                    correct = sample_panel_correctness(n, accuracy, rho, shape, rng)
                    errors += sum(correct) < need
                measured = errors / trials
                expected = oracle(n, accuracy, rho, 0.5)
                self.assertAlmostEqual(measured, expected, delta=0.012)

    def test_correlation_parameter_matches_realized_pairwise_correlation(self) -> None:
        trials = 40_000
        target = 0.4
        for shape in ("shared_shock", "item_difficulty"):
            with self.subTest(shape=shape):
                rng = random.Random(314159)
                left: list[int] = []
                right: list[int] = []
                for _ in range(trials):
                    correct = sample_panel_correctness(5, 0.8, target, shape, rng)
                    left.append(int(correct[0]))
                    right.append(int(correct[1]))
                self.assertAlmostEqual(
                    _binary_correlation(left, right), target, delta=0.035
                )


class R1PanelDependenceIntegrationTests(unittest.TestCase):
    def test_rho_zero_uses_existing_panel_path_exactly_for_both_shapes(self) -> None:
        shared = run_r1_condition(
            _base_condition(panel_dependence_shape="shared_shock"),
            tasks=25,
            seed=41,
        )
        item = run_r1_condition(
            _base_condition(panel_dependence_shape="item_difficulty"),
            tasks=25,
            seed=41,
        )
        self.assertEqual(shared["task_records"], item["task_records"])
        self.assertEqual(shared["metrics"], item["metrics"])

    def test_rho_one_is_exactly_the_same_under_both_shapes(self) -> None:
        shared = run_r1_condition(
            _base_condition(
                panel_dependence_shape="shared_shock",
                panel_dependence_correlation=1.0,
            ),
            tasks=25,
            seed=43,
        )
        item = run_r1_condition(
            _base_condition(
                panel_dependence_shape="item_difficulty",
                panel_dependence_correlation=1.0,
            ),
            tasks=25,
            seed=43,
        )
        self.assertEqual(shared["task_records"], item["task_records"])
        self.assertEqual(shared["metrics"], item["metrics"])

    def test_dependent_panel_configuration_is_retained_in_result_metadata(self) -> None:
        result = run_r1_condition(
            _base_condition(
                panel_dependence_shape="item_difficulty",
                panel_dependence_correlation=0.4,
            ),
            tasks=3,
            seed=47,
        )
        condition = result["condition"]
        self.assertEqual(condition["panel_dependence_shape"], "item_difficulty")
        self.assertEqual(condition["panel_dependence_correlation"], 0.4)

    def test_positive_panel_dependence_requires_a_real_panel(self) -> None:
        base = build_r1_conditions(R1ExperimentConfig(swarm_size=5))[0]
        with self.assertRaises(ValueError):
            dataclasses.replace(base, panel_dependence_correlation=0.2)

    def test_positive_panel_dependence_is_not_silently_composed_with_strictness_shock(self) -> None:
        with self.assertRaises(ValueError):
            _base_condition(
                verifier_error_correlation=0.2,
                panel_dependence_correlation=0.2,
            )

    def test_dependent_panel_requires_common_verifier_marginals(self) -> None:
        base = build_r1_conditions(R1ExperimentConfig(swarm_size=5))[0]
        heterogeneous = (
            Verifier("v1", sensitivity=0.97, false_positive_rate=0.03),
            Verifier("v2", sensitivity=0.90, false_positive_rate=0.03),
            Verifier("v3", sensitivity=0.97, false_positive_rate=0.04),
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                base,
                verifiers=heterogeneous,
                panel_size=3,
                verifier_error_correlation=0.0,
                panel_dependence_correlation=0.2,
            )

    def test_panel_dependence_namespace_is_explicit(self) -> None:
        for shape in ("shared_shock", "item_difficulty"):
            condition = _base_condition(panel_dependence_shape=shape)
            self.assertEqual(condition.panel_dependence_shape, shape)
        with self.assertRaises(ValueError):
            _base_condition(panel_dependence_shape="verifier_error_correlation")


if __name__ == "__main__":
    unittest.main()
