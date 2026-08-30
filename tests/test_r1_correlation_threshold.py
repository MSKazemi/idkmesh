import gzip
import hashlib
import json
import math
import re
from pathlib import Path
import unittest

from randomness_lab.r1_correlation_threshold import (
    CorrelationSweepConfig,
    DEFAULT_CORRELATIONS,
    render_markdown,
    run_correlation_sweep,
)
from randomness_lab.r1_scaling import R1ScalingConfig


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/diversity-correlation-threshold-seeds42-51.json.gz"
REPORT = ROOT / "results/experiments/r1/diversity-correlation-threshold-seeds42-51.md"
WRITEUP = ROOT / "experiments/E040-diversity-correlation-threshold.md"
EXPECTED_SHA256 = "017ac8b8ec829d291eae8a8eedee774d13504f0a7c181a4a43f73087c61aa155"

REFERENCE_CONFIG = R1ScalingConfig(
    tasks_per_trial=200,
    trials=10,
    base_seed=42,
    swarm_sizes=(1, 2, 5, 10),
    difficulty_levels=(("easy", 0.82), ("medium", 0.65), ("hard", 0.45)),
)


def _committed() -> dict:
    return json.loads(gzip.decompress(RESULT.read_bytes()))


class ConfigValidationTests(unittest.TestCase):
    def test_a_single_correlation_is_not_a_sweep(self) -> None:
        with self.assertRaises(ValueError):
            CorrelationSweepConfig(correlations=(0.25,))

    def test_correlations_stay_in_the_unit_interval(self) -> None:
        for bad in ((-0.1, 0.5), (0.5, 1.2)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    CorrelationSweepConfig(correlations=bad)

    def test_correlations_must_be_unique_and_ascending(self) -> None:
        for bad in ((0.5, 0.25), (0.25, 0.25)):
            with self.subTest(correlations=bad):
                with self.assertRaises(ValueError):
                    CorrelationSweepConfig(correlations=bad)


class CommittedPayloadTests(unittest.TestCase):
    def test_digest_and_shape(self) -> None:
        payload = RESULT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_SHA256)
        result = json.loads(gzip.decompress(payload))
        self.assertEqual(
            result["generator"], "randomness_lab.r1_correlation_threshold.v1"
        )
        self.assertEqual(result["evidence_level"], "synthetic_mechanism")
        self.assertEqual(result["config"]["correlations"], list(DEFAULT_CORRELATIONS))
        # 2 candidate families x 3 difficulties x 3 swarm sizes above the
        # baseline, at 7 correlations.
        self.assertEqual(len(result["thresholds"]), 18)
        self.assertEqual(len(result["points"]), 18 * len(DEFAULT_CORRELATIONS))

    def test_every_point_was_measured_at_an_equal_attempt_budget(self) -> None:
        # The whole comparison is meaningless if the arms did not spend the
        # same budget, so this is checked on every point rather than sampled.
        for point in _committed()["points"]:
            with self.subTest(point=point["candidate_family"]):
                self.assertTrue(point["equal_attempt_count"])
                self.assertTrue(point["equal_mean_compute_per_task"])
                self.assertEqual(point["baseline_family"], "homogeneous")


class SelfCheckTests(unittest.TestCase):
    def test_worker_diversity_arm_is_exactly_zero_at_perfect_correlation(self) -> None:
        # At rho=1.0 structural_diversity and identical_replication differ by a
        # profile label only. A non-zero delta there would be a harness defect,
        # not a finding, so it is pinned exactly rather than to a tolerance.
        cells = [
            point
            for point in _committed()["points"]
            if point["correlation"] == 1.0
            and point["candidate_family"] == "structural_diversity"
        ]
        self.assertEqual(len(cells), 9)
        for cell in cells:
            with self.subTest(difficulty=cell["difficulty"], n=cell["swarm_size"]):
                self.assertEqual(cell["mean_delta"], 0.0)

    def test_no_arm_resolves_an_advantage_at_perfect_correlation(self) -> None:
        result = _committed()
        self.assertTrue(result["self_check"]["arms_coincide_at_correlation_one"])
        for point in result["points"]:
            if point["correlation"] == 1.0:
                with self.subTest(family=point["candidate_family"]):
                    self.assertNotEqual(point["classification"], "positive")


class ThresholdSemanticsTests(unittest.TestCase):
    def test_threshold_fields_are_recomputable_from_the_points(self) -> None:
        result = _committed()
        grouped: dict[tuple[str, int, str], list[dict]] = {}
        for point in result["points"]:
            key = (
                point["difficulty"],
                point["swarm_size"],
                point["candidate_family"],
            )
            grouped.setdefault(key, []).append(point)
        for row in result["thresholds"]:
            key = (row["difficulty"], row["swarm_size"], row["candidate_family"])
            points = sorted(grouped[key], key=lambda item: item["correlation"])
            positive = [p for p in points if p["classification"] == "positive"]
            unresolved = [p for p in points if p["classification"] != "positive"]
            with self.subTest(key=key):
                self.assertEqual(
                    row["highest_resolved_positive_correlation"],
                    positive[-1]["correlation"] if positive else None,
                )
                self.assertEqual(
                    row["first_unresolved_correlation"],
                    unresolved[0]["correlation"] if unresolved else None,
                )

    def test_the_gap_between_the_two_boundaries_is_reported_not_hidden(self) -> None:
        # A non-monotone curve can resolve again above its first unresolved
        # point. The summary must keep both boundaries so that case stays
        # visible instead of being collapsed to whichever one is lower.
        for row in _committed()["thresholds"]:
            with self.subTest(family=row["candidate_family"], n=row["swarm_size"]):
                self.assertIn("highest_resolved_positive_correlation", row)
                self.assertIn("first_unresolved_correlation", row)


class PublishedFindingTests(unittest.TestCase):
    """Every number E040 quotes has to still be in the artifact it cites."""

    def test_seventeen_of_eighteen_curves_are_proportional(self) -> None:
        result = _committed()
        proportional = [
            row
            for row in result["thresholds"]
            if row["retained_independence_fit"]["proportional"]
        ]
        self.assertEqual(len(proportional), 17)
        self.assertEqual(
            result["summary"]["curves_proportional_to_retained_independence"], 17
        )
        exceptions = [
            row
            for row in result["thresholds"]
            if not row["retained_independence_fit"]["proportional"]
        ]
        self.assertEqual(
            [
                (
                    row["candidate_family"],
                    row["difficulty"],
                    row["swarm_size"],
                )
                for row in exceptions
            ],
            [("diverse_verifiers", "medium", 2)],
        )

    def test_the_advantage_resolves_at_the_one_measured_correlation(self) -> None:
        result = _committed()
        self.assertEqual(result["summary"]["curves_resolved_at_measured_reference"], 18)
        self.assertEqual(result["measured_reference_correlation"]["value"], 0.5873)
        for row in result["thresholds"]:
            with self.subTest(family=row["candidate_family"], n=row["swarm_size"]):
                self.assertTrue(row["resolved_at_measured_reference"]["bracketed"])

    def test_only_the_two_smallest_cells_stop_resolving_before_perfect_correlation(
        self,
    ) -> None:
        early = sorted(
            (row["candidate_family"], row["difficulty"], row["swarm_size"])
            for row in _committed()["thresholds"]
            if row["first_unresolved_correlation"] is not None
            and row["first_unresolved_correlation"] < 1.0
        )
        self.assertEqual(
            early,
            [
                ("diverse_verifiers", "easy", 2),
                ("structural_diversity", "easy", 2),
            ],
        )

    def test_verifier_assignment_buys_nothing_distinguishable(self) -> None:
        result = _committed()
        increments = result["verifier_assignment_increment"]
        self.assertEqual(len(increments), 9)
        # Five of nine positive is a coin flip, and the claim in E040 Result 3
        # is that the sign does not hold. Pin the count so a change that made
        # the increment consistent would fail here and force a rewrite.
        self.assertEqual(
            result["summary"]["cells_where_verifier_assignment_raised_the_slope"], 5
        )
        for row in increments:
            with self.subTest(difficulty=row["difficulty"], n=row["swarm_size"]):
                self.assertLess(abs(row["verifier_assignment_increment"]), 0.02)
                self.assertLess(abs(row["increment_share_of_worker_slope"]), 0.10)

    def test_writeup_slope_table_matches_the_artifact(self) -> None:
        # The write-up quotes worker-diversity slopes in a hand-written table.
        # Recompute the comparison from the payload so the prose cannot drift
        # away from the evidence it cites.
        slopes = {
            (row["difficulty"], row["swarm_size"]): row["retained_independence_fit"][
                "slope"
            ]
            for row in _committed()["thresholds"]
            if row["candidate_family"] == "structural_diversity"
        }
        text = WRITEUP.read_text(encoding="utf-8")
        found = 0
        for difficulty in ("easy", "medium", "hard"):
            match = re.search(
                rf"^\| {difficulty} \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \|$",
                text,
                re.MULTILINE,
            )
            self.assertIsNotNone(match, msg=f"no slope row for {difficulty}")
            for swarm_size, quoted in zip((2, 5, 10), match.groups()):
                with self.subTest(difficulty=difficulty, n=swarm_size):
                    self.assertAlmostEqual(
                        float(quoted), slopes[(difficulty, swarm_size)], places=4
                    )
                    found += 1
        self.assertEqual(found, 9)


class ReplayTests(unittest.TestCase):
    def test_the_default_invocation_regenerates_the_committed_payload(self) -> None:
        # Value equality, not byte equality: the simulation goes through libm
        # (`exp`, `**`), whose last-place rounding differs across CPUs and C
        # libraries, so a digest comparison would assert something about the
        # machine rather than about this code.
        result = run_correlation_sweep(
            CorrelationSweepConfig(
                base=REFERENCE_CONFIG, correlations=DEFAULT_CORRELATIONS
            )
        )
        replayed = json.loads(json.dumps(result, sort_keys=True))
        self._assert_equivalent(replayed, _committed(), path="$")

        rendered = render_markdown(result).splitlines()
        self.assertEqual(
            len(rendered), len(REPORT.read_text(encoding="utf-8").splitlines())
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
