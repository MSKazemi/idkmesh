import json
import math
import unittest

from sim import e040_review_capacity as e040


class ReviewCapacityTests(unittest.TestCase):
    def test_capacity_has_expected_midpoint_and_is_monotone(self) -> None:
        self.assertAlmostEqual(e040.capacity(e040.DEFAULT_K), 0.5)
        self.assertGreater(e040.capacity(2.0), e040.capacity(8.0))
        self.assertGreater(e040.capacity(8.0), e040.capacity(14.0))

    def test_equilibrium_matches_logistic_fixed_point(self) -> None:
        predicted = e040.equilibrium_load(
            potential_arrivals=3.0,
            service=1.0,
            k=8.0,
            tau=2.0,
        )
        expected = 8.0 + 2.0 * math.log(2.0)
        self.assertAlmostEqual(predicted, expected, places=12)
        self.assertAlmostEqual(3.0 * e040.capacity(predicted, 8.0, 2.0), 1.0)

    def test_logistic_feedback_bounds_overload_that_open_loop_accumulates(self) -> None:
        open_loop = e040.simulate(
            "open-loop",
            potential_arrivals=3.0,
            service=1.0,
            steps=400,
        )
        logistic = e040.simulate(
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
            e040.equilibrium_load(3.0, 1.0),
            places=6,
        )
        self.assertGreater(logistic["total_throttled"], 0.0)

    def test_under_capacity_does_not_invent_backlog(self) -> None:
        for policy in e040.POLICIES:
            with self.subTest(policy=policy):
                result = e040.simulate(
                    policy,
                    potential_arrivals=0.5,
                    service=1.0,
                    steps=100,
                )
                self.assertEqual(result["final_load"], 0.0)
                self.assertEqual(result["peak_load"], 0.0)

    def test_zero_service_is_reported_as_unbounded_without_non_json_numbers(self) -> None:
        result = e040.simulate(
            "logistic",
            potential_arrivals=1.0,
            service=0.0,
            steps=20,
        )
        self.assertEqual(result["predicted_equilibrium_load"], "unbounded")
        json.dumps(result, allow_nan=False)

    def test_experiment_is_deterministic_and_non_authoritative(self) -> None:
        left = e040.run_experiment((0.5, 2.0, 3.0), steps=50)
        right = e040.run_experiment((0.5, 2.0, 3.0), steps=50)
        self.assertEqual(left, right)
        self.assertFalse(left["policy_activation_allowed"])
        self.assertEqual(left["status"], "deterministic_toy_model")
        self.assertEqual(left["experiment_id"], "E040")
        json.dumps(left, allow_nan=False)

    def test_invalid_parameters_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            e040.capacity(-1.0)
        with self.assertRaises(ValueError):
            e040.capacity(1.0, tau=0.0)
        with self.assertRaises(ValueError):
            e040.simulate("unknown", potential_arrivals=1.0)
        with self.assertRaises(ValueError):
            e040.simulate("logistic", potential_arrivals=1.0, steps=0)
        with self.assertRaises(ValueError):
            e040.run_experiment(())


if __name__ == "__main__":
    unittest.main()
