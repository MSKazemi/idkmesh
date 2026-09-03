import ast
import gzip
import hashlib
import json
import math
import unittest
from pathlib import Path

from randomness_lab.r1 import R1ExperimentConfig, build_r1_conditions, run_r1_condition
from randomness_lab.r1_verifier_dependence import (
    DEFAULT_CORRELATIONS,
    DEFAULT_POOL_SIZES,
    DEFAULT_SWARM_SIZES,
    VerifierDependenceConfig,
    render_markdown,
    run_verifier_dependence,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/verifier-strictness-shock-seeds42-91.json.gz"
REPORT = ROOT / "results/experiments/r1/verifier-strictness-shock-seeds42-91.md"
WRITEUP = ROOT / "experiments/E041-verifier-strictness-shock.md"
EXPECTED_SHA256 = "15f2e1e40de098f44d73794cbc073ff83758249ab70e6a51338c8b3c85361fb9"


def _committed() -> dict:
    return json.loads(gzip.decompress(RESULT.read_bytes()))


class ConfigValidationTests(unittest.TestCase):
    def test_a_single_correlation_is_not_a_sweep(self) -> None:
        with self.assertRaises(ValueError):
            VerifierDependenceConfig(correlations=(0.5,))

    def test_correlations_stay_in_the_unit_interval(self) -> None:
        for bad in ((-0.1, 1.0), (0.0, 1.2)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    VerifierDependenceConfig(correlations=bad)

    def test_correlations_must_be_unique_and_ascending(self) -> None:
        for bad in ((1.0, 0.0), (0.0, 0.0, 1.0)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    VerifierDependenceConfig(correlations=bad)

    def test_both_endpoints_are_required(self) -> None:
        # rho=0 is the baseline every penalty is measured against and rho=1 is
        # the only cell with a closed form, so dropping either silently guts a
        # section rather than shrinking the run.
        for bad in ((0.0, 0.5), (0.5, 1.0)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    VerifierDependenceConfig(correlations=bad)

    def test_swarm_and_pool_sizes_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            VerifierDependenceConfig(swarm_sizes=(1, 5))
        with self.assertRaises(ValueError):
            VerifierDependenceConfig(swarm_sizes=(5, 3))
        with self.assertRaises(ValueError):
            VerifierDependenceConfig(pool_sizes=(0, 2))
        with self.assertRaises(ValueError):
            VerifierDependenceConfig(pool_sizes=(3, 2))


class LabStructureTests(unittest.TestCase):
    """The premise of the whole experiment, checked against r1.py directly.

    E040 closed by asking for a beta-binomial reshape of the verifier
    joint-failure distribution. These tests are what says that request cannot be
    met: there is no joint distribution over verifiers to reshape. If someone
    later gives the lab a real panel, these fail, which is the intended signal
    that E041's finding has been superseded rather than silently invalidated.
    """

    def test_exactly_one_verifier_reads_each_candidate(self) -> None:
        for arm in build_r1_conditions(R1ExperimentConfig(swarm_size=5)):
            result = run_r1_condition(arm, tasks=40, seed=42)
            for record in result["task_records"]:
                for candidate in record["candidates"]:
                    with self.subTest(arm=arm.name):
                        # A panel would need a sequence of decisions here.
                        self.assertIsInstance(candidate["verifier"], str)
                        self.assertIsInstance(candidate["accepted"], bool)

    def test_five_of_six_arms_carry_a_single_verifier(self) -> None:
        arms = build_r1_conditions(R1ExperimentConfig(swarm_size=5))
        singles = [arm.name for arm in arms if len(arm.verifiers) == 1]
        pools = [arm.name for arm in arms if len(arm.verifiers) > 1]
        self.assertEqual(len(singles), 5)
        self.assertEqual(pools, ["diverse_random_verifiers"])

    def test_the_verifier_pool_is_identically_parameterized(self) -> None:
        # The pool varies which verifier reads a candidate, never how good it
        # is, so it cannot add verifier independence that the pool lacks.
        arm = next(
            condition
            for condition in build_r1_conditions(R1ExperimentConfig(swarm_size=5))
            if condition.name == "diverse_random_verifiers"
        )
        self.assertEqual(
            len({(v.sensitivity, v.false_positive_rate) for v in arm.verifiers}), 1
        )

    def test_no_quorum_or_vote_aggregation_exists_in_the_lab(self) -> None:
        # Identifiers only. The words appear in prose here and in
        # r1_correlation_threshold.py, which cite E017's title; what would
        # matter is a quorum the code actually computes.
        banned = ("quorum", "vote", "majority", "consensus")
        for module in sorted((ROOT / "randomness_lab").glob("*.py")):
            tree = ast.parse(module.read_text(encoding="utf-8"))
            names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                elif isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
                elif isinstance(node, ast.arg):
                    names.add(node.arg)
                elif isinstance(node, ast.keyword) and node.arg:
                    names.add(node.arg)
            offenders = sorted(
                name for name in names if any(word in name.lower() for word in banned)
            )
            with self.subTest(module=module.name):
                self.assertEqual(offenders, [])


class CommittedPayloadTests(unittest.TestCase):
    def test_digest_and_shape(self) -> None:
        payload = RESULT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_SHA256)
        result = _committed()
        self.assertEqual(
            result["generator"], "randomness_lab.r1_verifier_dependence.v1"
        )
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertEqual(result["config"]["correlations"], list(DEFAULT_CORRELATIONS))
        self.assertEqual(result["config"]["swarm_sizes"], list(DEFAULT_SWARM_SIZES))
        self.assertEqual(result["config"]["pool_sizes"], list(DEFAULT_POOL_SIZES))
        self.assertEqual(len(result["marginals_and_joint"]), len(DEFAULT_CORRELATIONS))
        self.assertEqual(
            len(result["swarm_size_penalty"]["points"]), len(DEFAULT_SWARM_SIZES)
        )
        self.assertEqual(
            len(result["pool_dilution"]["points"]), len(DEFAULT_POOL_SIZES)
        )

    def test_the_structure_section_counted_one_verifier_per_candidate(self) -> None:
        structure = _committed()["structure"]
        self.assertEqual(structure["verifiers_per_candidate"], [1])
        self.assertGreater(structure["candidates_inspected"], 0)


class MarginalInvarianceTests(unittest.TestCase):
    """The shock does not move the marginals; it moves the within-task joint."""

    def test_accept_rates_track_sensitivity_and_false_positive_rate(self) -> None:
        closed = _committed()["closed_form_at_perfect_correlation"]
        sensitivity = closed["sensitivity"]
        false_positive_rate = closed["false_positive_rate"]
        for point in _committed()["marginals_and_joint"]:
            with self.subTest(rho=point["verifier_error_correlation"]):
                self.assertAlmostEqual(
                    point["accept_rate_given_good"], sensitivity, delta=0.01
                )
                self.assertAlmostEqual(
                    point["accept_rate_given_bad"], false_positive_rate, delta=0.01
                )

    def test_within_task_dependence_rises_with_the_correlation(self) -> None:
        points = _committed()["marginals_and_joint"]
        first = points[0]["within_task_accept_correlation"]
        last = points[-1]["within_task_accept_correlation"]
        self.assertGreater(last, first)
        # The parameter is meant to be a dependence knob; if the endpoints ever
        # stop separating, the knob has stopped working.
        self.assertGreater(last - first, 0.05)

    def test_a_shared_draw_nests_acceptance_by_candidate_quality(self) -> None:
        # At rho=1 one uniform decides the task. A draw below the
        # false-positive rate is necessarily below sensitivity, so any task
        # that accepted a bad candidate accepted every good one too.
        points = _committed()["marginals_and_joint"]
        perfect = next(
            point
            for point in points
            if point["verifier_error_correlation"] == 1.0
        )
        self.assertEqual(perfect["good_accepted_when_a_bad_one_was"], 1.0)
        self.assertGreater(perfect["nesting_denominator"], 0)
        independent = next(
            point
            for point in points
            if point["verifier_error_correlation"] == 0.0
        )
        self.assertLess(independent["good_accepted_when_a_bad_one_was"], 1.0)


class SingleAttemptInertnessTests(unittest.TestCase):
    def test_a_one_candidate_task_has_nothing_to_couple(self) -> None:
        section = _committed()["single_attempt_inertness"]
        for point in section["points"]:
            self.assertEqual(point["attempts_per_task"], 1)
        self.assertFalse(section["rho_zero_minus_rho_one"]["resolves"])

    def test_the_inert_interval_is_tight_enough_to_mean_something(self) -> None:
        # "Does not resolve" is only evidence of inertness if the interval
        # would have caught an effect the size of the one measured elsewhere.
        section = _committed()["single_attempt_inertness"]
        low, high = section["rho_zero_minus_rho_one"]["ci95"]
        penalty = _committed()["swarm_size_penalty"]["points"]
        largest = max(point["penalty"]["difference"] for point in penalty)
        self.assertLess(high - low, 2 * largest)


class ClosedFormTests(unittest.TestCase):
    def test_the_prediction_matches_every_headline_metric(self) -> None:
        closed = _committed()["closed_form_at_perfect_correlation"]
        self.assertLess(closed["max_absolute_error"], 0.005)
        for metric, error in closed["absolute_error"].items():
            with self.subTest(metric=metric):
                self.assertLess(error, 0.005)

    def test_the_closed_form_is_recomputable_from_the_reported_inputs(self) -> None:
        closed = _committed()["closed_form_at_perfect_correlation"]
        s = closed["sensitivity"]
        f = closed["false_positive_rate"]
        g = closed["probability_task_had_a_good_candidate"]
        g0 = closed["probability_first_candidate_was_good"]
        expected = {
            "abstention_rate": (1 - s) + (s - f) * (1 - g),
            "verified_success_rate": f * g0 + (s - f) * g,
            "false_acceptance_rate": f * (1 - g0),
        }
        for metric, value in expected.items():
            with self.subTest(metric=metric):
                self.assertAlmostEqual(closed["predicted"][metric], value, places=12)


class SwarmSizePenaltyTests(unittest.TestCase):
    def test_the_penalty_resolves_at_every_swarm_size(self) -> None:
        section = _committed()["swarm_size_penalty"]
        self.assertEqual(
            section["penalties_that_resolve"], len(section["points"])
        )
        for point in section["points"]:
            with self.subTest(swarm_size=point["swarm_size"]):
                self.assertGreater(point["penalty"]["difference"], 0.0)

    def test_the_penalty_does_not_amortize_over_swarm_size(self) -> None:
        section = _committed()["swarm_size_penalty"]
        self.assertLess(abs(section["penalty_slope_per_e_fold"]), 0.005)
        change = section["penalty_change_across_plateau"]
        self.assertFalse(change["resolves"])
        # The bound that matters: the interval excludes any reduction larger
        # than this fraction of the penalty being amortized away.
        penalty_at_plateau_start = next(
            point["penalty"]["difference"]
            for point in section["points"]
            if point["swarm_size"] == change["from_swarm_size"]
        )
        self.assertLess(abs(change["ci95"][0]), penalty_at_plateau_start)


class PoolDilutionTests(unittest.TestCase):
    def test_one_verifier_is_penalized_and_more_than_one_is_not(self) -> None:
        section = _committed()["pool_dilution"]
        single = next(p for p in section["points"] if p["pool_size"] == 1)
        self.assertTrue(single["penalty"]["resolves"])
        for point in section["points"]:
            if point["pool_size"] == 1:
                continue
            with self.subTest(pool_size=point["pool_size"]):
                self.assertFalse(point["penalty"]["resolves"])
        self.assertEqual(section["smallest_pool_that_does_not_resolve"], 2)

    def test_the_decay_is_faster_than_one_over_k(self) -> None:
        # 1/K is the obvious guess and it is wrong: a second verifier removes
        # far more than half, because abstention needs every verifier used in
        # the task to have drawn strict.
        section = _committed()["pool_dilution"]
        two = next(p for p in section["points"] if p["pool_size"] == 2)
        self.assertLess(
            two["penalty"]["difference"], two["one_over_k_prediction"]
        )

    def test_the_single_verifier_cell_matches_the_swarm_sweep(self) -> None:
        # Both sections measure the same cell; if they ever disagree, one of
        # them has drifted from the reference configuration.
        result = _committed()
        pool_single = next(
            p for p in result["pool_dilution"]["points"] if p["pool_size"] == 1
        )
        swarm_cell = next(
            p
            for p in result["swarm_size_penalty"]["points"]
            if p["swarm_size"] == result["config"]["penalty_swarm_size"]
        )
        self.assertAlmostEqual(
            pool_single["penalty"]["difference"],
            swarm_cell["penalty"]["difference"],
            places=12,
        )


class WriteupTests(unittest.TestCase):
    def test_the_writeup_penalty_table_matches_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        for point in _committed()["swarm_size_penalty"]["points"]:
            pattern = (
                rf"\|\s*{point['swarm_size']}\s*\|"
                rf"\s*{point['verified_success_rate_rho_zero']:.4f}\s*\|"
                rf"\s*{point['verified_success_rate_rho_one']:.4f}\s*\|"
                rf"\s*\+{point['penalty']['difference']:.4f}\s*\|"
            )
            with self.subTest(swarm_size=point["swarm_size"]):
                self.assertRegex(text, pattern)

    def test_the_writeup_marginals_table_matches_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        for point in _committed()["marginals_and_joint"]:
            row = (
                f"| {point['verifier_error_correlation']:.2f} "
                f"| {point['accept_rate_given_good']:.4f} "
                f"| {point['accept_rate_given_bad']:.4f} "
                f"| {point['within_task_accept_correlation']:.4f} "
                f"| {point['good_accepted_when_a_bad_one_was']:.4f} |"
            )
            with self.subTest(rho=point["verifier_error_correlation"]):
                self.assertIn(row, text)

    def test_the_writeup_closed_form_table_matches_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        closed = _committed()["closed_form_at_perfect_correlation"]
        for metric in closed["predicted"]:
            cells = (
                f"{closed['predicted'][metric]:.4f} "
                f"| {closed['observed'][metric]:.4f} "
                f"| {closed['absolute_error'][metric]:.4f} |"
            )
            with self.subTest(metric=metric):
                self.assertIn(cells, text)

    def test_the_writeup_pool_table_matches_the_artifact(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        for point in _committed()["pool_dilution"]["points"]:
            low, high = point["penalty"]["ci95"]
            row = (
                f"| {point['pool_size']} | {point['verifier_assignment']} "
                f"| {point['penalty']['difference']:+.4f} "
                f"| [{low:+.4f}, {high:+.4f}] "
                f"| {point['one_over_k_prediction']:.4f} |"
            )
            with self.subTest(pool_size=point["pool_size"]):
                self.assertIn(row, text)

    def test_the_writeup_scalar_claims_match_the_artifact(self) -> None:
        # Every loose number the prose quotes. These are the ones that go stale
        # silently when the grid is retuned and the tables are regenerated but
        # the sentences around them are not.
        text = WRITEUP.read_text(encoding="utf-8")
        result = _committed()
        inert = result["single_attempt_inertness"]["rho_zero_minus_rho_one"]
        penalty = result["swarm_size_penalty"]
        change = penalty["penalty_change_across_plateau"]
        for label, quoted in (
            ("inertness difference", f"`{inert['difference']:.4f}`"),
            (
                "inertness interval",
                f"`[{inert['ci95'][0]:+.4f}, {inert['ci95'][1]:+.4f}]`",
            ),
            (
                "closed-form max error",
                f"`{result['closed_form_at_perfect_correlation']['max_absolute_error']:.4f}`",
            ),
            ("penalty slope", f"`{penalty['penalty_slope_per_e_fold']:+.5f}`"),
            ("plateau change", f"`{change['change']:+.4f}`"),
            (
                "plateau interval",
                f"`[{change['ci95'][0]:+.4f}, {change['ci95'][1]:+.4f}]`",
            ),
        ):
            with self.subTest(claim=label):
                self.assertIn(quoted, text)

    def test_the_writeup_names_the_guardrail(self) -> None:
        text = WRITEUP.read_text(encoding="utf-8")
        self.assertIn("within-task strictness shock", text)
        self.assertIn("E040", text)

    def test_the_writeup_is_indexed(self) -> None:
        # A record missing from its own index is invisible to every reader and
        # to IDKGraph; only a test sees it.
        index = (ROOT / "experiments/README.md").read_text(encoding="utf-8")
        self.assertIn("E041-verifier-strictness-shock.md", index)


class ReplayTests(unittest.TestCase):
    def test_the_default_invocation_regenerates_the_committed_payload(self) -> None:
        # Value equality, not byte equality: the simulation goes through libm,
        # whose last-place rounding differs across CPUs and C libraries, so a
        # digest comparison would assert something about the machine.
        result = run_verifier_dependence(VerifierDependenceConfig())
        replayed = json.loads(json.dumps(result, sort_keys=True))
        self._assert_equivalent(replayed, _committed(), path="$")

        rendered = render_markdown(result).splitlines()
        self.assertEqual(
            rendered, REPORT.read_text(encoding="utf-8").splitlines()
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
