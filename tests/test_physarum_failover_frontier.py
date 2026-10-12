"""PHY-1 burden-matched failover frontier (issue #630).

Runs the frontier through the real ``sim/physarum_compute_routing_stress.py``
module and checks it against the retained completion sweep. All numbers are
synthetic; replays compare by value within 1e-6, never by bytes.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SIM_DIR = ROOT / "sim"
RESULTS = ROOT / "experiments" / "results"
TOLERANCE = 1e-6


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SIM_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = _load("physarum_compute_routing_sim")
stress = _load("physarum_compute_routing_stress")

FRONTIER = json.loads(
    (RESULTS / "PHY-1-failover-frontier.json").read_text(encoding="utf-8")
)
COMPLETION = json.loads(
    (RESULTS / "PHY-1-completion-sweep.json").read_text(encoding="utf-8")
)

CELL_KEYS = (
    "mean_route_burden_per_task",
    "success_rate",
    "mean_gap_to_frontier",
    "gap_standard_error",
)


class RetryProbabilityTests(unittest.TestCase):
    """The new knob must not disturb the published failover arm."""

    WINDOW = dict(epochs=24, tasks_per_epoch=10, seed=5)

    def _run(self, **kwargs):
        return stress.run_strategy(
            "multipath-failover",
            stress.environment_by_name("transient-a-outage"),
            **self.WINDOW,
            **kwargs,
        )

    def test_probability_one_is_the_published_failover_arm(self):
        self.assertEqual(self._run(), self._run(retry_probability=1.0))

    def test_probability_zero_never_retries(self):
        result = self._run(retry_probability=0.0)
        self.assertEqual(result["retry_rate"], 0.0)
        self.assertEqual(result["route_attempts"], result["attempts"])

    def test_retry_rate_and_burden_grow_with_probability(self):
        rows = [
            self._run(retry_probability=p) for p in (0.0, 0.5, 1.0)
        ]
        rates = [row["retry_rate"] for row in rows]
        burdens = [row["mean_route_burden_per_task"] for row in rows]
        self.assertEqual(rates, sorted(rates))
        self.assertLess(rates[0], rates[-1])
        self.assertLess(burdens[0], burdens[-1])

    def test_out_of_range_probability_fails_closed(self):
        for bad in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                self._run(retry_probability=bad)

    def test_other_strategies_ignore_the_knob(self):
        environment = stress.environment_by_name("abrupt-shift")
        kwargs = dict(seed=3, epochs=12, tasks_per_epoch=5)
        self.assertEqual(
            stress.run_strategy("physarum", environment, **kwargs),
            stress.run_strategy(
                "physarum", environment, retry_probability=0.0, **kwargs
            ),
        )


class FrontierGeometryTests(unittest.TestCase):
    def test_envelope_drops_points_that_cost_more_for_no_gain(self):
        points = [(2.0, 0.8), (2.2, 0.9), (2.1, 0.85), (2.3, 0.88)]
        self.assertEqual(
            stress.pareto_envelope(points),
            [(2.0, 0.8), (2.1, 0.85), (2.2, 0.9)],
        )

    def test_interpolation_and_range_status(self):
        points = [(2.0, 0.8), (3.0, 1.0)]
        value, status = stress.frontier_interpolate(points, 2.5)
        self.assertAlmostEqual(value, 0.9)
        self.assertEqual(status, "within-range")
        self.assertEqual(
            stress.frontier_interpolate(points, 1.0),
            (0.8, "below-frontier-floor"),
        )
        self.assertEqual(
            stress.frontier_interpolate(points, 4.0),
            (1.0, "above-frontier-ceiling"),
        )


class FailoverFrontierIntegrationTests(unittest.TestCase):
    """Drive the real simulator end to end on a small window."""

    WINDOW = dict(seed_start=1, seeds=2, epochs=12, tasks_per_epoch=5)

    def test_report_is_deterministic_and_labelled_synthetic(self):
        names = ["abrupt-shift"]
        first = stress.failover_frontier(environment_names=names, **self.WINDOW)
        second = stress.failover_frontier(environment_names=names, **self.WINDOW)
        self.assertEqual(first, second)
        self.assertIn("not empirical evidence", first["model_warning"])
        cell = first["environments"]["abrupt-shift"]
        self.assertEqual(
            set(cell), {"frontier", "physarum", "discounted-thompson"}
        )
        self.assertEqual(len(cell["frontier"]), len(first["retry_probabilities"]))
        for strategy in ("physarum", "discounted-thompson"):
            self.assertIn(
                cell[strategy]["verdict"],
                {
                    "above-frontier",
                    "on-frontier",
                    "below-frontier",
                    "uncompared",
                    "dominated-by-frontier-endpoint",
                },
            )

    def test_requires_a_real_frontier_and_positive_samples(self):
        with self.assertRaises(ValueError):
            stress.failover_frontier(seeds=0)
        with self.assertRaises(ValueError):
            stress.failover_frontier(retry_probabilities=(1.0,))

    def test_cli_emits_frontier_json(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = stress.main(
                [
                    "--failover-frontier",
                    "--environment",
                    "stationary",
                    "--seeds",
                    "1",
                    "--epochs",
                    "10",
                    "--tasks-per-epoch",
                    "4",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(set(payload["topologies"]), {"dense"})

    def test_cli_rejects_incompatible_modes(self):
        with self.assertRaises(SystemExit):
            stress.main(["--failover-frontier", "--parameter-sweep"])


class RetainedFrontierArtifactTests(unittest.TestCase):
    """The retained artifact must agree with the code and with PHY-1."""

    def test_artifact_is_synthetic_and_keeps_the_negative_decision(self):
        self.assertIn("not empirical evidence", FRONTIER["model_warning"])
        self.assertEqual(FRONTIER["recommendation"], "reject-promotion")
        for key in ("seed_start", "seeds", "epochs", "tasks_per_epoch"):
            self.assertEqual(FRONTIER[key], COMPLETION[key], key)
        self.assertEqual(set(FRONTIER["topologies"]), {"sparse", "dense"})
        for environments in FRONTIER["topologies"].values():
            self.assertEqual(
                {env.name for env in stress.ENVIRONMENTS}, set(environments)
            )

    def test_full_retry_point_equals_the_published_failover_arm(self):
        """p=1 must reproduce PHY-1's failover numbers (arm comparability)."""
        success, burden = COMPLETION["topology_value_format"]
        self.assertEqual((success, burden), ("success_rate", "mean_route_burden_per_task"))
        for topology, environments in FRONTIER["topologies"].items():
            published = COMPLETION["topology_summary"][topology]
            for environment, cell in environments.items():
                want = published[environment]["multipath-failover"]
                got = cell["frontier"]["1"]
                self.assertAlmostEqual(got[success], want[0], delta=TOLERANCE)
                self.assertAlmostEqual(got[burden], want[1], delta=TOLERANCE)

    def test_strategy_rows_match_the_published_matrix(self):
        for topology, environments in FRONTIER["topologies"].items():
            published = COMPLETION["topology_summary"][topology]
            for environment, cell in environments.items():
                for strategy in ("physarum", "discounted-thompson"):
                    want = published[environment][strategy]
                    row = cell[strategy]
                    self.assertAlmostEqual(
                        row["success_rate"], want[0], delta=TOLERANCE
                    )
                    self.assertAlmostEqual(
                        row["mean_route_burden_per_task"],
                        want[1],
                        delta=TOLERANCE,
                    )

    def test_verdicts_follow_the_declared_rule(self):
        margin = FRONTIER["margin_standard_errors"]
        for environments in FRONTIER["topologies"].values():
            for cell in environments.values():
                points = [
                    (v["mean_route_burden_per_task"], v["success_rate"])
                    for v in cell["frontier"].values()
                ]
                endpoint = stress.pareto_envelope(points)[-1]
                for strategy in ("physarum", "discounted-thompson"):
                    row = cell[strategy]
                    status = row["frontier_status"]
                    if status == "below-frontier-floor":
                        want = "uncompared"
                    elif (
                        status == "above-frontier-ceiling"
                        and row["success_rate"] < endpoint[1]
                        and row["mean_route_burden_per_task"] > endpoint[0]
                    ):
                        want = "dominated-by-frontier-endpoint"
                    elif row["mean_gap_to_frontier"] > margin * row["gap_standard_error"]:
                        want = "above-frontier"
                    elif row["mean_gap_to_frontier"] < -margin * row["gap_standard_error"]:
                        want = "below-frontier"
                    else:
                        want = "on-frontier"
                    self.assertEqual(row["verdict"], want)

    def test_retained_cell_replays_from_committed_code(self):
        """One cheap cell recomputed from code and seeds, compared by value."""
        retained = FRONTIER["topologies"]["sparse"]["abrupt-shift"]
        window = {k: FRONTIER[k] for k in ("seed_start", "seeds", "epochs", "tasks_per_epoch")}
        replay = stress.failover_frontier(
            environment_names=["abrupt-shift"],
            topology_name="sparse",
            **window,
        )["environments"]["abrupt-shift"]
        self._assert_cell(retained, replay)

    @pytest.mark.sim
    def test_every_retained_cell_replays_from_committed_code(self):
        window = {k: FRONTIER[k] for k in ("seed_start", "seeds", "epochs", "tasks_per_epoch")}
        for topology, environments in FRONTIER["topologies"].items():
            replay = stress.failover_frontier(
                topology_name=topology, **window
            )["environments"]
            self.assertEqual(set(replay), set(environments))
            for environment, retained in environments.items():
                self._assert_cell(retained, replay[environment])

    def _assert_cell(self, retained, replay):
        for p, point in retained["frontier"].items():
            for key, value in point.items():
                self.assertAlmostEqual(
                    replay["frontier"][p][key], value, delta=TOLERANCE
                )
        for strategy in ("physarum", "discounted-thompson"):
            self.assertEqual(
                retained[strategy]["verdict"], replay[strategy]["verdict"]
            )
            self.assertEqual(
                retained[strategy]["seeds_above_frontier"],
                replay[strategy]["seeds_above_frontier"],
            )
            for key in CELL_KEYS:
                self.assertAlmostEqual(
                    retained[strategy][key],
                    replay[strategy][key],
                    delta=TOLERANCE,
                )


if __name__ == "__main__":
    unittest.main()
