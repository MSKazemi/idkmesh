import json
import math
import unittest

from sim import review_capacity_governor as governor


class ReviewCapacityTests(unittest.TestCase):
    def test_capacity_has_expected_midpoint_and_is_monotone(self) -> None:
        self.assertAlmostEqual(governor.capacity(governor.DEFAULT_K), 0.5)
        self.assertGreater(governor.capacity(2.0), governor.capacity(8.0))
        self.assertGreater(governor.capacity(8.0), governor.capacity(14.0))

    def test_equilibrium_matches_logistic_fixed_point(self) -> None:
        predicted = governor.equilibrium_load(
            potential_arrivals=3.0,
            service=1.0,
            k=8.0,
            tau=2.0,
        )
        expected = 8.0 + 2.0 * math.log(2.0)
        self.assertAlmostEqual(predicted, expected, places=12)
        self.assertAlmostEqual(3.0 * governor.capacity(predicted, 8.0, 2.0), 1.0)

    def test_logistic_feedback_bounds_overload_that_open_loop_accumulates(self) -> None:
        open_loop = governor.simulate(
            "open-loop",
            potential_arrivals=3.0,
            service=1.0,
            steps=400,
        )
        logistic = governor.simulate(
            "logistic",
            potential_arrivals=3.0,
            service=1.0,
            steps=400,
        )

        self.assertEqual(open_loop["final_load"], 800.0)
        self.assertGreater(open_loop["peak_load"], 100.0)
        self.assertLess(logistic["peak_load"], 12.0)
        self.assertAlmostEqual(
            float(logistic["final_load"]),
            governor.equilibrium_load(3.0, 1.0),
            places=6,
        )
        self.assertGreater(logistic["total_throttled"], 0.0)

    def test_under_capacity_does_not_invent_backlog(self) -> None:
        for policy in governor.POLICIES:
            with self.subTest(policy=policy):
                result = governor.simulate(
                    policy,
                    potential_arrivals=0.5,
                    service=1.0,
                    steps=100,
                )
                self.assertEqual(result["final_load"], 0.0)
                self.assertEqual(result["peak_load"], 0.0)

    def test_zero_service_is_reported_as_unbounded_without_non_json_numbers(self) -> None:
        result = governor.simulate(
            "logistic",
            potential_arrivals=1.0,
            service=0.0,
            steps=20,
        )
        self.assertEqual(result["predicted_equilibrium_load"], "unbounded")
        json.dumps(result, allow_nan=False)

    def test_experiment_is_deterministic_and_non_authoritative(self) -> None:
        left = governor.run_experiment((0.5, 2.0, 3.0), steps=50)
        right = governor.run_experiment((0.5, 2.0, 3.0), steps=50)
        self.assertEqual(left, right)
        self.assertFalse(left["policy_activation_allowed"])
        self.assertEqual(left["status"], "deterministic_toy_model")
        self.assertEqual(left["experiment_id"], "E044")
        json.dumps(left, allow_nan=False)

    def test_invalid_parameters_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            governor.capacity(-1.0)
        with self.assertRaises(ValueError):
            governor.capacity(1.0, tau=0.0)
        with self.assertRaises(ValueError):
            governor.simulate("unknown", potential_arrivals=1.0)
        with self.assertRaises(ValueError):
            governor.simulate("logistic", potential_arrivals=1.0, steps=0)
        with self.assertRaises(ValueError):
            governor.run_experiment(())


if __name__ == "__main__":
    unittest.main()
