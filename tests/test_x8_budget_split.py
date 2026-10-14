"""X8: the generate-versus-verify budget-split predictor (issue 981, H4, A6).

Everything here is synthetic.  Expected values are derived by hand or from closed forms,
never copied from the module under test, and the Monte Carlo twin of the pipeline is used
to check the closed form independently.
"""

from __future__ import annotations

import json
import math
import random
import unittest
from pathlib import Path

import sim.x8_budget_split as x8

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "experiments" / "results" / "X8-budget-split.json"
RECORD = ROOT / "experiments" / "X8-budget-split-predictor.md"

BENIGN = x8.Scenario(cost_ratio=0.1, budget=12.0, cross=0.0, verifier_icc=0.1, rule="majority")


class PrimitiveTests(unittest.TestCase):
    def test_need_votes(self) -> None:
        self.assertEqual([x8.need_votes(m, "majority") for m in (1, 2, 3, 4, 5)], [1, 2, 2, 3, 3])
        self.assertEqual([x8.need_votes(m, "unanimity") for m in (1, 3, 5)], [1, 3, 5])
        with self.assertRaises(ValueError):
            x8.need_votes(3, "plurality")

    def test_binomial_tail_matches_hand_values(self) -> None:
        self.assertAlmostEqual(x8.binomial_tail(3, 0.5, 2), 0.5)
        self.assertAlmostEqual(x8.binomial_tail(4, 0.25, 4), 0.25**4)
        self.assertEqual(x8.binomial_tail(3, 0.4, 0), 1.0)
        self.assertEqual(x8.binomial_tail(3, 0.4, 4), 0.0)
        # d = 1 (a verifier-blind task) accepts with certainty at every quorum
        self.assertEqual(x8.binomial_tail(7, 1.0, 7), 1.0)

    def test_task_outcome_matches_hand_computation(self) -> None:
        # n = 1, m = 1: pc = 0.5 * 0.9, pw = 0.5 * 0.2
        v, e, u = x8.task_outcome(0.5, 0.2, 1, 1, "majority", 0.1)
        self.assertAlmostEqual(v, 0.45)
        self.assertAlmostEqual(e, 0.10)
        self.assertAlmostEqual(u, 0.45)
        # n = 2: P(some accepted) = 1 - 0.45^2, split in the ratio pc : pw
        v2, e2, u2 = x8.task_outcome(0.5, 0.2, 2, 1, "majority", 0.1)
        reach = 1 - 0.45**2
        self.assertAlmostEqual(v2, 0.45 / 0.55 * reach)
        self.assertAlmostEqual(e2, 0.10 / 0.55 * reach)
        self.assertAlmostEqual(u2, 0.45**2)
        self.assertAlmostEqual(v2 + e2 + u2, 1.0)

    def test_blind_spot_tasks_cannot_be_rescued_by_more_workers_or_reads(self) -> None:
        # worker-blind task (p = 0): the value is 0 at every allocation
        for n, m in ((1, 1), (5, 3), (10, 9)):
            self.assertEqual(x8.task_outcome(0.0, 0.3, n, m, "majority", 0.1)[0], 0.0)
        # verifier-blind task (d = 1): every wrong candidate is accepted, so escapes
        # dominate and adding reads does not reduce them
        for m in (1, 9):
            self.assertGreater(x8.task_outcome(0.3, 1.0, 4, m, "majority", 0.1)[1], 0.6)

    def test_closed_form_agrees_with_monte_carlo(self) -> None:
        rng = random.Random(81)
        p, d, n, m, r = 0.4, 0.3, 3, 3, 0.1
        trials = 30000
        counts = {"correct": 0, "wrong": 0, "none": 0}
        for _ in range(trials):
            counts[x8.simulate_outcome(p, d, n, m, "majority", r, rng)] += 1
        v, e, u = x8.task_outcome(p, d, n, m, "majority", r)
        self.assertAlmostEqual(counts["correct"] / trials, v, delta=0.01)
        self.assertAlmostEqual(counts["wrong"] / trials, e, delta=0.01)
        self.assertAlmostEqual(counts["none"] / trials, u, delta=0.01)


class AllocationTests(unittest.TestCase):
    def test_enumeration_respects_the_budget_and_bounds(self) -> None:
        for budget, c_v in ((6.0, 0.1), (12.0, 0.5)):
            allocations = x8.enumerate_allocations(budget, c_v)
            self.assertTrue(allocations)
            for n, m in allocations:
                self.assertGreaterEqual(n, 1)
                self.assertTrue(1 <= m <= x8.M_MAX)
                self.assertLessEqual(x8.allocation_cost((n, m), c_v), budget + 1e-9)
            self.assertEqual(len(allocations), len(set(allocations)))

    def test_baselines_are_feasible_grid_points_with_the_documented_shape(self) -> None:
        for scenario in x8.scenario_grid():
            grid = set(x8.enumerate_allocations(scenario.budget, scenario.cost_ratio))
            baselines = x8.baseline_allocations(scenario.budget, scenario.cost_ratio)
            self.assertEqual(set(baselines), set(x8.BASELINES))
            for name, allocation in baselines.items():
                self.assertIn(allocation, grid, (scenario.scenario_id, name))
            self.assertEqual(baselines["all_workers"][1], 1)
            self.assertEqual(baselines["all_verifiers"][0], 1)
            self.assertEqual(baselines["all_workers"][0], max(n for n, _ in grid))

    def test_argbest_breaks_ties_toward_the_cheaper_allocation(self) -> None:
        values = {(2, 1): 0.5, (1, 1): 0.5, (3, 1): 0.4}
        self.assertEqual(x8.argbest(values, 0.1), (1, 1))
        self.assertEqual(x8.argbest(values, 0.1, worst=True), (3, 1))


class FitTests(unittest.TestCase):
    def test_cluster_beta_binomial_recovers_known_mean_and_icc(self) -> None:
        rng = random.Random(5)
        a, b = x8.beta_shape(0.3, 0.3)
        sizes, hits = [], []
        for _ in range(4000):
            q = rng.betavariate(a, b)
            size = rng.choice((4, 8, 12))
            sizes.append(size)
            hits.append(sum(rng.random() < q for _ in range(size)))
        mean, icc = x8.fit_cluster_beta_binomial(sizes, hits)
        self.assertAlmostEqual(mean, 0.3, delta=0.02)
        self.assertAlmostEqual(icc, 0.3, delta=0.03)

    def test_fit_refuses_data_it_cannot_identify(self) -> None:
        with self.assertRaises(ValueError):
            x8.fit_cluster_beta_binomial([4, 4], [1, 2])
        with self.assertRaises(ValueError):
            x8.fit_model([])
        no_correct = [x8.TaskObservation(4, 0, 3, 5, 0) for _ in range(10)]
        with self.assertRaises(ValueError):
            x8.fit_model(no_correct)

    def test_cross_term_is_near_zero_without_coupling_and_positive_with_it(self) -> None:
        fitted = {}
        for cross in (0.0, 0.6):
            scenario = x8.Scenario(0.1, 12.0, cross, 0.5, "majority")
            world = scenario.world()
            rng = random.Random(11)
            tasks = x8.draw_tasks(world, 2000, rng)
            fitted[cross] = x8.fit_model(x8.run_pilot(world, tasks, 8, 4, rng))
        self.assertLess(abs(fitted[0.0].cross), 0.2)
        self.assertGreater(fitted[0.6].cross, 0.3)

    def test_predicted_surface_responds_to_the_cross_term(self) -> None:
        model = x8.FittedModel(0.35, 0.4, 0.35, 0.5, 0.1, 0.0, 200)
        allocations = x8.enumerate_allocations(12.0, 0.1)
        flat = x8.predicted_surface(model, allocations, "majority", cross=0.0)
        coupled = x8.predicted_surface(model, allocations, "majority", cross=0.9)
        gap = max(abs(flat[a][0] - coupled[a][0]) for a in allocations)
        self.assertGreater(gap, 1e-3)
        for triple in list(flat.values()) + list(coupled.values()):
            self.assertAlmostEqual(sum(triple), 1.0, places=9)


class HeldOutEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runs = [x8.run_replicate(BENIGN, r) for r in range(4)]

    def test_replicates_are_deterministic(self) -> None:
        again = x8.run_replicate(BENIGN, 0)
        self.assertEqual(again["strategies"], self.runs[0]["strategies"])
        self.assertEqual(again["fitted"], self.runs[0]["fitted"])

    def test_held_out_tasks_are_disjoint_from_the_pilot_draws(self) -> None:
        pilot, held, _ = x8.draw_split(BENIGN, 0)
        self.assertEqual(len(pilot), x8.PILOT_TASKS)
        self.assertEqual(len(held), x8.HELD_OUT_TASKS)

        # the two blind-spot atoms repeat by design; every other (p, d) is a fresh draw
        def interior(tasks: list[tuple[float, float]]) -> set[tuple[float, float]]:
            return {t for t in tasks if 0.0 < t[0] and t[1] < 1.0}

        self.assertTrue(interior(pilot) and interior(held))
        self.assertTrue(interior(pilot).isdisjoint(interior(held)))

    def test_held_out_calibration_of_the_predicted_surface(self) -> None:
        # Calibration on tasks the fit never saw.  The threshold is a deliberately loose
        # engineering bound (the committed artifact reports the real figure); a surface
        # off by more than 0.06 verified-value on average is not a usable predictor.
        for run in self.runs:
            self.assertLess(run["surface_mae"], 0.06)
        mean_regret = sum(r["strategies"]["predicted_joint"]["regret"] for r in self.runs) / len(self.runs)
        self.assertLess(mean_regret, 0.02)

    def test_broken_predictor_control_is_distinguished_from_the_real_one(self) -> None:
        # The control reads the same fitted predictions upside down.  If the harness could
        # not tell it from the predictor, a pass above would mean nothing.
        good = sum(r["strategies"]["predicted_joint"]["regret"] for r in self.runs) / len(self.runs)
        broken = sum(r["strategies"]["broken_predictor"]["regret"] for r in self.runs) / len(self.runs)
        random_pick = sum(r["strategies"]["random_allocation"]["regret"] for r in self.runs) / len(self.runs)
        self.assertGreater(broken, 0.15)
        self.assertGreater(broken, 10 * max(good, 1e-4))
        self.assertGreater(random_pick, good)

    def test_oracle_has_zero_regret_and_no_strategy_beats_it(self) -> None:
        for run in self.runs:
            self.assertEqual(run["strategies"]["oracle"]["regret"], 0.0)
            for name, pick in run["strategies"].items():
                self.assertGreaterEqual(pick["regret"], -1e-12, name)
                self.assertLessEqual(pick["cost"], BENIGN.budget + 1e-9, name)
                self.assertAlmostEqual(pick["V"] + pick["E"] + pick["U"], 1.0, places=9)

    def test_a_corrupted_fit_is_penalised_on_held_out_tasks(self) -> None:
        # Feed the allocator a model in which verifiers are near-perfect when they are not:
        # it then buys attempts and one read each, and must lose to the fitted model.
        world = BENIGN.world()
        rng = random.Random(3)
        held = x8.draw_tasks(world, 400, rng)
        pilot = x8.run_pilot(world, x8.draw_tasks(world, 200, rng), 8, 4, rng)
        fitted = x8.fit_model(pilot)
        corrupted = x8.FittedModel(fitted.worker_mean, fitted.worker_icc, 0.001, 0.02, 0.05, 0.0, 200)
        allocations = x8.enumerate_allocations(BENIGN.budget, BENIGN.cost_ratio)
        truth = x8.surface(held, allocations, BENIGN.rule, world.false_reject)
        good = x8.choose_split(fitted, BENIGN.budget, BENIGN.cost_ratio, BENIGN.rule)
        bad = x8.choose_split(corrupted, BENIGN.budget, BENIGN.cost_ratio, BENIGN.rule)
        self.assertGreater(truth[good][0], truth[bad][0] + 0.05)


class VerdictRuleTests(unittest.TestCase):
    @staticmethod
    def _replicates(joint: list[float], baseline: list[float]) -> list[dict]:
        out = []
        for j, b in zip(joint, baseline):
            strategies = {name: {"V": b} for name in x8.STRATEGIES}
            strategies["predicted_joint"] = {"V": j}
            out.append({"strategies": strategies})
        return out

    def test_the_rule_distinguishes_win_tie_and_loss(self) -> None:
        noise = [0.001, -0.001, 0.002, -0.002, 0.0, 0.001, -0.001, 0.0]
        base = [0.4 + n for n in noise]
        win = self._replicates([b + 0.05 for b in base], base)
        tie = self._replicates([b + n * 0.5 for b, n in zip(base, reversed(noise))], base)
        loss = self._replicates([b - 0.05 for b in base], base)
        self.assertEqual(x8.scenario_verdict(win)["verdict"], "predicted_wins")
        self.assertEqual(x8.scenario_verdict(tie)["verdict"], "tie")
        self.assertEqual(x8.scenario_verdict(loss)["verdict"], "baseline_wins")

    def test_one_matching_baseline_is_enough_to_withhold_a_win(self) -> None:
        base = [0.4, 0.41, 0.39, 0.4, 0.405, 0.395]
        replicates = self._replicates([b + 0.05 for b in base], base)
        for r, b in zip(replicates, base):
            r["strategies"]["fifty_fifty"]["V"] = b + 0.05 + (0.001 if b > 0.4 else -0.001)
        self.assertNotEqual(x8.scenario_verdict(replicates)["verdict"], "predicted_wins")


class CommittedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_artifact_is_labelled_synthetic_and_self_consistent(self) -> None:
        result = self.result
        self.assertEqual(result["generator"], x8.GENERATOR)
        self.assertEqual(result["evidence_class"], "synthetic")
        self.assertEqual(result["scenarios_run"], len(x8.scenario_grid()))
        self.assertEqual(sum(result["totals"].values()), result["scenarios_run"])
        body = {k: v for k, v in result.items() if k != "digest"}
        self.assertEqual(result["digest"], x8.canonical_digest(body))
        self.assertEqual(result["design"]["replicates"], x8.REPLICATES)
        self.assertEqual(result["design"]["pilot_tasks"], x8.PILOT_TASKS)
        self.assertEqual(result["small_pilot"]["design"]["pilot_tasks"], x8.SMALL_PILOT_TASKS)

    def test_artifact_keeps_the_controls_that_make_the_comparison_meaningful(self) -> None:
        regret = self.result["mean_regret"]
        self.assertEqual(regret["oracle"], 0.0)
        self.assertGreater(regret["broken_predictor"], 10 * regret["predicted_joint"])
        self.assertGreater(regret["random_allocation"], regret["predicted_joint"])

    def test_first_scenario_replicate_reproduces_from_scratch(self) -> None:
        row = self.result["scenarios"][0]
        scenario = x8.scenario_grid()[0]
        self.assertEqual(row["scenario"], scenario.scenario_id)
        run = x8.run_replicate(scenario, 0)
        self.assertEqual(run["strategies"]["predicted_joint"]["allocation"], row["replicate_picks"][0])
        for name in x8.STRATEGIES:
            self.assertAlmostEqual(run["strategies"][name]["regret"], row["replicate_regrets"][name][0], places=8)

    def test_every_scenario_verdict_follows_the_preregistered_rule(self) -> None:
        for row in self.result["scenarios"]:
            zs = [row["versus_baseline"][b]["z"] for b in x8.BASELINES]
            if all(z > x8.Z_DECISIVE for z in zs):
                expected = "predicted_wins"
            elif any(z < -x8.Z_DECISIVE for z in zs):
                expected = "baseline_wins"
            else:
                expected = "tie"
            self.assertEqual(row["verdict"], expected, row["scenario"])

    def test_record_states_the_artifact_numbers(self) -> None:
        # documented numbers need an invariant: the record may not drift from the artifact
        text = RECORD.read_text(encoding="utf-8")
        totals = self.result["totals"]
        n = self.result["scenarios_run"]
        self.assertIn(f"{totals['predicted_wins']} of {n}", text)
        self.assertIn("synthetic", text.lower())
        self.assertIn(self.result["digest"][:12], text)
        self.assertTrue(math.isfinite(self.result["mean_surface_mae"]))


if __name__ == "__main__":
    unittest.main()
