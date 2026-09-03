import gzip
import hashlib
import json
import math
import random
import unittest
from dataclasses import replace
from pathlib import Path

from randomness_lab.model import (
    CorrelatedBernoulliEnvironment,
    ItemDifficultyEnvironment,
    Worker,
)
from randomness_lab.r1 import (
    WORKER_DEPENDENCE_SHAPES,
    R1ExperimentConfig,
    build_r1_conditions,
    run_r1_condition,
)
from randomness_lab.r1_dependence_shape import (
    DEFAULT_CORRELATIONS,
    DEFAULT_SWARM_SIZES,
    E040_PUBLISHED_SLOPES,
    PROPORTIONALITY_THRESHOLD,
    SHAPES,
    DependenceShapeConfig,
    render_markdown,
    run_dependence_shape,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/worker-dependence-shape-seeds42-51.json.gz"
REPORT = ROOT / "results/experiments/r1/worker-dependence-shape-seeds42-51.md"
WRITEUP = ROOT / "experiments/E042-worker-dependence-shape.md"
E040_WRITEUP = ROOT / "experiments/E040-diversity-correlation-threshold.md"
EXPECTED_SHA256 = "b357841d483d3d11d75b050cbfa601f1bf6c213eef7b2e1edb4e71a429b0c9cb"


def _committed() -> dict:
    return json.loads(gzip.decompress(RESULT.read_bytes()))


class ConfigValidationTests(unittest.TestCase):
    def test_a_single_correlation_is_not_a_sweep(self) -> None:
        with self.assertRaises(ValueError):
            DependenceShapeConfig(correlations=(0.5,))

    def test_both_endpoints_are_required(self) -> None:
        # The fit is forced through the origin at rho=1, and rho=0 is the
        # independent reference; dropping either guts the comparison.
        for bad in ((0.0, 0.5), (0.5, 1.0)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    DependenceShapeConfig(correlations=bad)

    def test_correlations_must_be_unique_and_ascending(self) -> None:
        for bad in ((1.0, 0.0), (0.0, 0.0, 1.0)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    DependenceShapeConfig(correlations=bad)

    def test_the_equivalence_check_cannot_be_made_meaningless(self) -> None:
        with self.assertRaises(ValueError):
            DependenceShapeConfig(equivalence_tasks=10)

    def test_swarm_sizes_and_difficulties_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            DependenceShapeConfig(swarm_sizes=(1, 5))
        with self.assertRaises(ValueError):
            DependenceShapeConfig(swarm_sizes=(5, 2))
        with self.assertRaises(ValueError):
            DependenceShapeConfig(difficulties=(("a", 0.5), ("a", 0.6)))
        with self.assertRaises(ValueError):
            DependenceShapeConfig(difficulties=(("a", 1.5),))


class EnvironmentContractTests(unittest.TestCase):
    """The new shape must be a reparameterization, not a different experiment."""

    def test_heterogeneous_workers_are_refused_not_approximated(self) -> None:
        workers = [Worker("a", 0.6), Worker("b", 0.7)]
        with self.assertRaises(ValueError):
            ItemDifficultyEnvironment(0.5).sample(workers, random.Random(42))

    def test_the_one_r1_arm_with_heterogeneous_workers_is_the_bandit(self) -> None:
        # If another arm ever gains heterogeneous workers, this experiment's
        # coverage silently shrinks; that should fail loudly instead.
        arms = build_r1_conditions(R1ExperimentConfig(swarm_size=5))
        heterogeneous = sorted(
            arm.name
            for arm in arms
            if len({p.worker.success_probability for p in arm.profiles}) > 1
        )
        self.assertEqual(heterogeneous, ["bandit_selected"])

    def test_the_shapes_coincide_in_distribution_at_both_endpoints(self) -> None:
        # In distribution, not draw for draw: the two consume the random stream
        # differently (the shared shock spends a draw on its coin, the
        # beta-binomial spends one on the difficulty), so identical seeds do not
        # give identical sequences even where the laws agree.
        size, quality, tasks = 5, 0.68, 20_000
        workers = [Worker(f"w{i}", quality) for i in range(size)]
        for correlation in (0.0, 1.0):
            summaries = {}
            for shape, environment in (
                ("shared_shock", CorrelatedBernoulliEnvironment(correlation)),
                ("item_difficulty", ItemDifficultyEnvironment(correlation)),
            ):
                rng = random.Random(1234)
                failures = []
                for _ in range(tasks):
                    outcomes = environment.sample(workers, rng)
                    failures.append(sum(1 for w in workers if not outcomes[w.name]))
                summaries[shape] = (
                    sum(failures) / (tasks * size),
                    failures.count(size) / tasks,
                    failures.count(0) / tasks,
                )
            with self.subTest(correlation=correlation):
                for left, right in zip(summaries["shared_shock"],
                                       summaries["item_difficulty"]):
                    self.assertAlmostEqual(left, right, delta=0.015)

    def test_the_registry_covers_exactly_the_two_shapes(self) -> None:
        self.assertEqual(sorted(WORKER_DEPENDENCE_SHAPES), sorted(SHAPES))

    def test_an_unknown_shape_is_rejected(self) -> None:
        arm = build_r1_conditions(R1ExperimentConfig(swarm_size=5))[3]
        with self.assertRaises(ValueError):
            replace(arm, worker_dependence_shape="bogus")

    def test_the_default_shape_is_the_historical_one(self) -> None:
        # Every committed R1 artifact was produced under the shared shock. If
        # the default ever moves, they all silently stop reproducing.
        for arm in build_r1_conditions(R1ExperimentConfig(swarm_size=5)):
            with self.subTest(arm=arm.name):
                self.assertEqual(arm.worker_dependence_shape, "shared_shock")

    def test_the_default_reproduces_the_unshaped_environment(self) -> None:
        arm = next(
            a
            for a in build_r1_conditions(R1ExperimentConfig(swarm_size=5))
            if a.name == "structural_diversity"
        )
        explicit = replace(arm, worker_dependence_shape="shared_shock")
        for seed in (42, 43):
            with self.subTest(seed=seed):
                self.assertEqual(
                    run_r1_condition(arm, tasks=60, seed=seed,
                                     retain_task_records=False)["metrics"],
                    run_r1_condition(explicit, tasks=60, seed=seed,
                                     retain_task_records=False)["metrics"],
                )


class CommittedPayloadTests(unittest.TestCase):
    def test_digest_and_shape(self) -> None:
        payload = RESULT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_SHA256)
        result = _committed()
        self.assertEqual(
            result["generator"], "randomness_lab.r1_dependence_shape.v1"
        )
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertEqual(result["config"]["correlations"], list(DEFAULT_CORRELATIONS))
        self.assertEqual(result["config"]["swarm_sizes"], list(DEFAULT_SWARM_SIZES))
        # 2 families x 3 difficulties x 3 swarm sizes.
        self.assertEqual(len(result["curves"]), 18)
        self.assertEqual(
            len(result["shape_equivalence"]), len(DEFAULT_CORRELATIONS)
        )


class ShapeEquivalenceTests(unittest.TestCase):
    def test_the_marginal_error_rate_is_the_same_under_both_shapes(self) -> None:
        for row in _committed()["shape_equivalence"]:
            with self.subTest(rho=row["error_correlation"]):
                self.assertAlmostEqual(
                    row["shared_shock"]["marginal_error_rate"],
                    row["item_difficulty"]["marginal_error_rate"],
                    delta=0.01,
                )

    def test_both_shapes_hit_the_configured_correlation(self) -> None:
        for row in _committed()["shape_equivalence"]:
            for shape in SHAPES:
                with self.subTest(rho=row["error_correlation"], shape=shape):
                    self.assertAlmostEqual(
                        row[shape]["measured_pairwise_correlation"],
                        row["error_correlation"],
                        delta=0.01,
                    )

    def test_the_shapes_differ_only_in_the_joint_tail(self) -> None:
        rows = _committed()["shape_equivalence"]
        for row in rows:
            shock = row["shared_shock"]["probability_whole_panel_failed"]
            item = row["item_difficulty"]["probability_whole_panel_failed"]
            with self.subTest(rho=row["error_correlation"]):
                if row["error_correlation"] in (0.0, 1.0):
                    self.assertAlmostEqual(shock, item, delta=0.01)
                else:
                    # This gap is the entire mechanism of the experiment. If it
                    # ever closes, the two shapes have stopped differing and
                    # every slope comparison below is measuring noise.
                    self.assertGreater(shock, item)


class CrossRunnerTests(unittest.TestCase):
    """E040's decision item 4: a cross-runner check belongs in the suite."""

    def test_the_shared_shock_slopes_reproduce_e040_exactly(self) -> None:
        reproduction = _committed()["summary"]["e040_reproduction"]
        self.assertEqual(len(reproduction["cells"]), len(E040_PUBLISHED_SLOPES))
        self.assertLess(reproduction["max_absolute_difference"], 5e-5)

    def test_the_reproduction_recovers_e040s_own_exception_cell(self) -> None:
        # E040 reports 17 of 18 curves at R2 >= 0.99, the exception being
        # diverse_verifiers / medium / N=2 at 0.9852. Recovering that cell, by
        # value, is the strongest evidence the two runners agree.
        e040_text = E040_WRITEUP.read_text(encoding="utf-8")
        self.assertIn("0.9852", e040_text)
        curve = next(
            c
            for c in _committed()["curves"]
            if c["family"] == "diverse_random_verifiers"
            and c["difficulty"] == "medium"
            and c["swarm_size"] == 2
        )
        self.assertEqual(f"{curve['shared_shock']['r_squared']:.4f}", "0.9852")
        self.assertLess(
            curve["shared_shock"]["r_squared"], PROPORTIONALITY_THRESHOLD
        )

    def test_the_shared_shock_proportionality_count_matches_e040(self) -> None:
        self.assertEqual(
            _committed()["summary"]["proportional_curves"]["shared_shock"], 17
        )


class FindingTests(unittest.TestCase):
    def test_e040s_hedge_does_not_hold(self) -> None:
        # E040 predicted the corrected shape would shrink the slopes. It does
        # the opposite in the large majority of curves.
        summary = _committed()["summary"]
        self.assertFalse(summary["e040_hedge_direction_holds"])
        self.assertGreater(summary["curves_where_the_slope_rose"], 12)
        self.assertGreater(summary["mean_slope_change_fraction"], 0.0)

    def test_proportionality_is_substantially_a_property_of_the_shape(self) -> None:
        counts = _committed()["summary"]["proportional_curves"]
        self.assertLess(counts["item_difficulty"], counts["shared_shock"])
        # E040's headline was 17 of 18. If the corrected shape kept nearly all
        # of them, the finding would be a rounding difference rather than a
        # result, so this asserts the gap is large.
        self.assertLessEqual(counts["item_difficulty"], 12)

    def test_every_curve_reports_both_shapes_and_a_change(self) -> None:
        for curve in _committed()["curves"]:
            with self.subTest(curve=(curve["family"], curve["difficulty"],
                                     curve["swarm_size"])):
                for shape in SHAPES:
                    self.assertIn("slope", curve[shape])
                    self.assertIn("r_squared", curve[shape])
                    self.assertEqual(
                        len(curve[shape]["points"]), len(DEFAULT_CORRELATIONS)
                    )
                self.assertAlmostEqual(
                    curve["slope_change"],
                    curve["item_difficulty"]["slope"]
                    - curve["shared_shock"]["slope"],
                    places=12,
                )

    def test_the_worker_diversity_arm_is_pinned_to_zero_at_perfect_correlation(
        self,
    ) -> None:
        # At rho=1 structural_diversity and identical_replication differ by a
        # profile label and nothing else, under either shape. A harness
        # self-check, not a finding — E040 asserts the same thing.
        for curve in _committed()["curves"]:
            if curve["family"] != "structural_diversity":
                continue
            for shape in SHAPES:
                last = curve[shape]["points"][-1]
                with self.subTest(shape=shape, difficulty=curve["difficulty"],
                                  swarm_size=curve["swarm_size"]):
                    self.assertEqual(last["correlation"], 1.0)
                    self.assertAlmostEqual(last["mean_delta"], 0.0, places=12)

    def test_the_verifier_arm_is_not_pinned_and_matches_e040s_range(self) -> None:
        # E040 Result 4: the diverse_verifiers arm still varies verifier
        # assignment at rho=1, so it is not pinned, and its observed deltas
        # there "run from -0.0145 to +0.0235". Recovering that interval is a
        # second cross-runner check, on a quantity nobody fitted.
        deltas = [
            curve["shared_shock"]["points"][-1]["mean_delta"]
            for curve in _committed()["curves"]
            if curve["family"] == "diverse_random_verifiers"
        ]
        self.assertEqual(len(deltas), 9)
        self.assertAlmostEqual(min(deltas), -0.0145, places=4)
        self.assertAlmostEqual(max(deltas), 0.0235, places=4)
        e040_text = E040_WRITEUP.read_text(encoding="utf-8")
        self.assertIn("-0.0145", e040_text)
        self.assertIn("+0.0235", e040_text)


class WriteupTests(unittest.TestCase):
    def test_the_writeup_slope_table_matches_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        for curve in _committed()["curves"]:
            row = (
                f"| {curve['family']} | {curve['difficulty']} "
                f"| {curve['swarm_size']} "
                f"| {curve['shared_shock']['slope']:.4f} "
                f"| {curve['shared_shock']['r_squared']:.4f} "
                f"| {curve['item_difficulty']['slope']:.4f} "
                f"| {curve['item_difficulty']['r_squared']:.4f} "
                f"| {curve['slope_change_fraction']:+.1%} |"
            )
            with self.subTest(curve=(curve["family"], curve["difficulty"],
                                     curve["swarm_size"])):
                self.assertIn(row, text)

    def test_the_writeup_scalar_claims_match_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        summary = _committed()["summary"]
        for label, quoted in (
            ("rose", f"**{summary['curves_where_the_slope_rose']} of 18**"),
            ("shared-shock proportional",
             f"`{summary['proportional_curves']['shared_shock']} of 18`"),
            ("item-difficulty proportional",
             f"`{summary['proportional_curves']['item_difficulty']} of 18`"),
            ("mean change", f"`{summary['mean_slope_change_fraction']:+.1%}`"),
        ):
            with self.subTest(claim=label):
                self.assertIn(quoted, text)

    def test_the_writeup_keeps_the_guardrail(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        # The finding is easy to overstate. These are the load-bearing hedges.
        self.assertIn("E020", text)
        self.assertIn("Neither shape is right", text)
        self.assertIn("E040", text)

    def test_the_writeup_is_indexed(self) -> None:
        index = (ROOT / "experiments/README.md").read_text(encoding="utf-8")
        self.assertIn("E042-worker-dependence-shape.md", index)


class ReplayTests(unittest.TestCase):
    def test_the_default_invocation_regenerates_the_committed_payload(self) -> None:
        # Value equality, not byte equality: the simulation goes through libm
        # and betavariate, whose last-place rounding differs across CPUs and C
        # libraries, so a digest comparison would assert something about the
        # machine rather than about this code.
        result = run_dependence_shape(DependenceShapeConfig())
        replayed = json.loads(json.dumps(result, sort_keys=True))
        self._assert_equivalent(replayed, _committed(), path="$")

        self.assertEqual(
            render_markdown(result).splitlines(),
            REPORT.read_text(encoding="utf-8").splitlines(),
        )

    def _assert_equivalent(self, actual, expected, *, path: str) -> None:
        self.assertIs(type(actual), type(expected), msg=path)
        if isinstance(expected, dict):
            self.assertEqual(sorted(actual), sorted(expected), msg=path)
            for key in expected:
                self._assert_equivalent(actual[key], expected[key], path=f"{path}.{key}")
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), msg=path)
            for index, item in enumerate(expected):
                self._assert_equivalent(actual[index], item, path=f"{path}[{index}]")
        elif isinstance(expected, float):
            self.assertTrue(
                math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12),
                msg=f"{path}: {actual!r} is not within tolerance of {expected!r}",
            )
        else:
            self.assertEqual(actual, expected, msg=path)


if __name__ == "__main__":
    unittest.main()
