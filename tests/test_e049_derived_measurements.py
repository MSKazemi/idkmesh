"""Fast tests for E049: derived measurements replayed from the E024 arms.

E049 is a post-hoc reader of E024, so the properties worth pinning are the ones a
reader could silently get wrong:

1. the replay really is E024 -- same seeds, same streams, identical payload, and
   the instrument that records verdicts leaves nothing behind;
2. recovery is judged on an absolute scale and right-censored, so an arm that
   stands still cannot "recover";
3. niche coverage is one function applied to every arm's accepted trace, so it is
   not ``archive_size`` by another name;
4. the improvement count and the paired tests have fixed, stated directions.

Everything here uses a tiny configuration so the whole module stays far below the
unit tier's CPU budget. The tests that replay the committed 100-seed artifact are
in ``test_e049_committed_artifact.py`` and run nightly.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import sim.e049_derived_measurements as e049
import sim.matched_budget_emergence as mbe

sim = mbe.sim

AGENTS, GENERATIONS, CHANGE_AT, BINS = 12, 10, 5, 4
HORIZON = GENERATIONS - CHANGE_AT
# The landscape's optimum under the changed goal, fixed here so no fast test pays
# for the reference grid. `ReferenceOptimumTests` checks the value itself.
OPTIMUM = 0.9

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E024_ARTIFACT = os.path.join(
    REPO_ROOT, "experiments", "results", "E024-matched-budget-emergence-100-seed-summary.json"
)
# canonical_digest() of the committed E024 `aggregate` block. If E024's artifact is
# regenerated this must be updated deliberately, which is the point of pinning it.
E024_AGGREGATE_DIGEST = "64419a7dcc7f913688efefae1e994302fb043e596a7ed8c32cd0097f4190f78a"


_REPLAYS = {}


def _replay(seed):
    """One replay per seed for the tests that only read it; the ones that compare
    against a fresh run call ``replay_seed`` themselves."""
    if seed not in _REPLAYS:
        _REPLAYS[seed] = e049.replay_seed(seed, AGENTS, GENERATIONS, CHANGE_AT, BINS)
    return _REPLAYS[seed]


def _candidate(adaptability: float = 0.5, reliability: float = 0.5) -> "sim.Candidate":
    return sim.Candidate((reliability, adaptability, 0.5, 0.5, 0.5))


def _tiny_measure(**overrides):
    kwargs = dict(
        seeds=2,
        seed_start=7,
        agents=AGENTS,
        generations=GENERATIONS,
        change_at=CHANGE_AT,
        bins=BINS,
        resamples=20,
        reference={"optimum_utility": OPTIMUM, "optimum_traits": [], "method": "fixture"},
    )
    kwargs.update(overrides)
    return e049.measure(**kwargs)


class ReferenceOptimumTests(unittest.TestCase):
    def test_optimum_is_the_changed_goal_ceiling_and_not_an_arm_output(self):
        # A coarse grid contains the optimum exactly, so this is cheap and exact.
        reference = e049.reference_optimum(step=0.05)
        self.assertEqual(reference["optimum_utility"], OPTIMUM)
        self.assertEqual(reference["optimum_traits"][0], 1.0)
        candidate = sim.Candidate(tuple(reference["optimum_traits"]))
        self.assertTrue(sim.viable(candidate))

    def test_threshold_is_a_fraction_of_the_optimum(self):
        self.assertAlmostEqual(e049.threshold_for(0.9, OPTIMUM), 0.81)


class ReplayTests(unittest.TestCase):
    def test_replay_payload_is_exactly_the_e024_payload(self):
        payload, _ = _replay(7)
        self.assertEqual(
            payload, mbe.run_seed(7, AGENTS, GENERATIONS, CHANGE_AT, BINS)
        )

    def test_replay_is_identical_under_an_imperfect_panel_that_consumes_the_verifier_stream(self):
        # A perfect panel draws nothing from the verifier stream, so only an
        # imperfect one can reveal a recorder that perturbs it.
        panel = sim.VerificationConfig(verifiers=5, accuracy=0.75, correlation=0.5)
        payload, traces = e049.replay_seed(
            4, AGENTS, GENERATIONS, CHANGE_AT, BINS, verification=panel
        )
        self.assertEqual(
            payload,
            mbe.run_seed(4, AGENTS, GENERATIONS, CHANGE_AT, BINS, verification=panel),
        )
        rejected = sum(1 for _, _, ok in traces["random"] if not ok)
        self.assertGreater(rejected, 0)

    def test_replay_attributes_one_verdict_per_proposal_to_its_generation(self):
        _, traces = _replay(7)
        self.assertEqual(tuple(traces), e049.STRATEGIES)
        for records in traces.values():
            self.assertEqual(len(records), AGENTS * GENERATIONS)
            for generation in range(GENERATIONS):
                self.assertEqual(
                    sum(1 for g, _, _ in records if g == generation), AGENTS
                )

    def test_recorded_acceptances_match_the_arms_own_counters(self):
        payload, traces = _replay(7)
        for row in payload["results"]:
            accepted = sum(1 for _, _, ok in traces[row["strategy"]] if ok)
            self.assertEqual(accepted, row["verification_accepts"])

    def test_recording_wrapper_is_removed_after_a_run_and_after_an_error(self):
        original = mbe.sim.verify_candidate
        _replay(7)
        self.assertIs(mbe.sim.verify_candidate, original)
        with self.assertRaises(RuntimeError):
            with e049._recording_verifier([]):
                self.assertIsNot(mbe.sim.verify_candidate, original)
                raise RuntimeError("boom")
        self.assertIs(mbe.sim.verify_candidate, original)

    def test_replay_does_not_perturb_a_later_unwrapped_run(self):
        before = mbe.run_seed(9, AGENTS, GENERATIONS, CHANGE_AT, BINS)
        e049.replay_seed(9, AGENTS, GENERATIONS, CHANGE_AT, BINS)
        self.assertEqual(before, mbe.run_seed(9, AGENTS, GENERATIONS, CHANGE_AT, BINS))

    def test_the_committed_e024_aggregate_is_the_one_this_module_replays_against(self):
        with open(E024_ARTIFACT, encoding="utf-8") as handle:
            committed = json.load(handle)
        self.assertEqual(e049.canonical_digest(committed["aggregate"]), E024_AGGREGATE_DIGEST)

    def test_aggregate_rebuild_uses_e024s_own_statistics(self):
        payloads = [_replay(7)[0], _replay(8)[0]]
        rebuilt = e049.e024_aggregate_from_payloads(payloads)
        direct = mbe.sweep(2, 7, AGENTS, GENERATIONS, CHANGE_AT, BINS)["aggregate"]
        self.assertEqual(rebuilt, direct)


class RecoveryTimeTests(unittest.TestCase):
    TRACE = [0.1, 0.2, 0.5, 0.9, 0.4, 0.95]  # change at index 2

    def test_first_passage_counts_generations_after_the_change(self):
        self.assertEqual(e049.recovery_time(self.TRACE, 2, 0.8), 1)

    def test_meeting_the_bar_in_the_change_generation_is_zero_not_missing(self):
        self.assertEqual(e049.recovery_time([0.0, 0.9, 0.2], 1, 0.8), 0)

    def test_never_reaching_the_bar_is_censored_not_zero(self):
        self.assertIsNone(e049.recovery_time([0.1, 0.1, 0.3, 0.3], 2, 0.8))
        self.assertEqual(e049.censored_time(None, HORIZON), HORIZON)
        self.assertEqual(e049.censored_time(0, HORIZON), 0)

    def test_pre_change_values_cannot_satisfy_the_bar(self):
        self.assertIsNone(e049.recovery_time([0.99, 0.99, 0.1, 0.1], 2, 0.8))

    def test_sustained_requires_staying_above_the_bar_to_the_end(self):
        # Spikes to 0.9 at post index 1 but is back at 0.4 afterwards: first
        # passage succeeds, sustained settles only at the final 0.95.
        self.assertEqual(e049.recovery_time(self.TRACE, 2, 0.8, sustained=True), 3)
        self.assertIsNone(e049.recovery_time([0.1, 0.1, 0.9, 0.4], 2, 0.8, sustained=True))
        self.assertEqual(e049.recovery_time([0.1, 0.1, 0.9, 0.9], 2, 0.8, sustained=True), 0)

    def test_a_flat_low_plateau_is_not_a_recovery_unlike_the_self_relative_field(self):
        flat = [0.2] * 8
        legacy = sim._summary("x", flat, sim.VerificationStats(), 0, 4)
        self.assertEqual(legacy["recovery_generations"], 0)
        self.assertIsNone(e049.recovery_time(flat, 4, 0.8))


class NicheCoverageTests(unittest.TestCase):
    def _records(self):
        a, b = _candidate(adaptability=0.1), _candidate(adaptability=0.9)
        c = _candidate(adaptability=0.45)  # a third niche, reached only by a rejected proposal
        nonviable = sim.Candidate((0.0, 0.5, 0.5, 0.5, 0.5))  # reliability below the floor
        return [
            (0, a, True),  # before the change: ignored
            (CHANGE_AT, a, True),
            (CHANGE_AT, b, True),
            (CHANGE_AT + 1, c, False),  # rejected: ignored
            (CHANGE_AT + 1, nonviable, True),  # falsely accepted, not viable: ignored
        ], a, b, nonviable

    def test_only_accepted_viable_post_change_candidates_count(self):
        records, a, b, nonviable = self._records()
        self.assertFalse(sim.viable(nonviable))
        niches = {sim.niche(x, BINS) for x in (a, b, _candidate(adaptability=0.45))}
        self.assertEqual(len(niches), 3)
        counts = e049.niche_coverage(records, CHANGE_AT, BINS, good_threshold=0.0)
        self.assertEqual(counts, {"viable_post": 2, "good_post": 2})

    def test_good_niches_apply_the_changed_goal_threshold(self):
        records, a, b, _ = self._records()
        ua, ub = sim.utility(a, sim.CHANGED_GOAL), sim.utility(b, sim.CHANGED_GOAL)
        self.assertGreater(ub, ua)
        midpoint = (ua + ub) / 2.0
        counts = e049.niche_coverage(records, CHANGE_AT, BINS, good_threshold=midpoint)
        self.assertEqual(counts, {"viable_post": 2, "good_post": 1})

    def test_the_same_trace_scores_the_same_whichever_arm_owns_it(self):
        records, *_ = self._records()
        scores = {
            arm: e049.niche_coverage(records, CHANGE_AT, BINS, 0.0) for arm in e049.STRATEGIES
        }
        self.assertEqual(len({json.dumps(v, sort_keys=True) for v in scores.values()}), 1)

    def test_coverage_is_defined_for_arms_whose_archive_size_is_zero(self):
        payload, traces = _replay(7)
        sizes = {row["strategy"]: row["archive_size"] for row in payload["results"]}
        self.assertEqual(sizes["planner"], 0)
        planner = e049.niche_coverage(traces["planner"], CHANGE_AT, BINS, 0.0)
        self.assertGreater(planner["viable_post"], 0)
        for strategy in e049.STRATEGIES:
            counts = e049.niche_coverage(traces[strategy], CHANGE_AT, BINS, 0.0)
            self.assertLessEqual(counts["viable_post"], BINS * BINS)


class ImprovementTests(unittest.TestCase):
    def _records(self):
        # Changed-goal utility rises with adaptability (weight 0.35).
        low, mid, high, higher = (
            _candidate(adaptability=x) for x in (0.40, 0.50, 0.60, 0.605)
        )
        records = [
            (0, mid, True),  # verified before the change
            (CHANGE_AT, low, True),  # worse than what was carried
            (CHANGE_AT, high, True),  # improvement
            (CHANGE_AT + 1, higher, True),  # tiny improvement (+0.00175)
            (CHANGE_AT + 1, _candidate(adaptability=1.0), False),  # rejected: no credit
        ]
        return records, (low, mid, high, higher)

    def test_values_are_ordered_as_the_fixture_assumes(self):
        _, (low, mid, high, higher) = self._records()
        u = [sim.utility(c, sim.CHANGED_GOAL) for c in (low, mid, high, higher)]
        self.assertEqual(u, sorted(u))
        self.assertLess(u[3] - u[2], 0.01)

    def test_carry_over_credits_only_beating_the_pre_change_best(self):
        records, _ = self._records()
        strict = e049.improvement_events(records, CHANGE_AT, 0.0, mode="carry")
        self.assertEqual(strict["improvements"], 2)
        self.assertEqual(strict["proposals"], 4)
        material = e049.improvement_events(records, CHANGE_AT, 0.01, mode="carry")
        self.assertEqual(material["improvements"], 1)

    def test_fresh_mode_also_credits_refinding_what_was_held(self):
        records, _ = self._records()
        fresh = e049.improvement_events(records, CHANGE_AT, 0.0, mode="fresh")
        # low, then high, then higher: three records from a zero start.
        self.assertEqual(fresh["improvements"], 3)

    def test_a_rejected_candidate_is_never_an_improvement(self):
        records, _ = self._records()
        only_rejected = [(CHANGE_AT, _candidate(adaptability=1.0), False)]
        self.assertEqual(
            e049.improvement_events(only_rejected, CHANGE_AT)["improvements"], 0
        )

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            e049.improvement_events([], CHANGE_AT, mode="nope")


class StatisticsTests(unittest.TestCase):
    def test_sign_test_is_exact_and_two_sided(self):
        self.assertEqual(e049.sign_test_p(0, 0), 1.0)
        self.assertAlmostEqual(e049.sign_test_p(5, 0), 2 / 32)
        self.assertEqual(e049.sign_test_p(5, 5), 1.0)
        self.assertEqual(e049.sign_test_p(3, 7), e049.sign_test_p(7, 3))

    def test_a_vanishing_p_is_not_rounded_to_zero(self):
        p = e049.sign_test_p(100, 0)
        self.assertGreater(p, 0.0)
        self.assertLess(p, 1e-25)

    def test_mcnemar_is_the_sign_test_on_discordant_pairs(self):
        self.assertEqual(e049.mcnemar_exact(14, 0), e049.sign_test_p(14, 0))

    def test_clopper_pearson_matches_the_closed_form_at_the_edges(self):
        edge = e049.clopper_pearson(0, 10)
        self.assertEqual(edge["ci95_low"], 0.0)
        self.assertAlmostEqual(edge["ci95_high"], 1 - 0.025 ** (1 / 10), places=5)
        full = e049.clopper_pearson(10, 10)
        self.assertEqual(full["ci95_high"], 1.0)
        self.assertAlmostEqual(full["ci95_low"], 0.025 ** (1 / 10), places=5)

    def test_bootstrap_is_deterministic_per_label_and_varies_across_labels(self):
        values = [1.0, 2.0, 3.0, 4.0, 10.0]
        first = e049.bootstrap_mean_ci(values, "a", 50)
        self.assertEqual(first, e049.bootstrap_mean_ci(values, "a", 50))
        self.assertNotEqual(first, e049.bootstrap_mean_ci(values, "b", 50))
        self.assertEqual(first["mean"], 4.0)
        self.assertLessEqual(first["ci95_low"], first["mean"])
        self.assertGreaterEqual(first["ci95_high"], first["mean"])

    def test_ratio_is_undefined_not_infinite_when_nothing_improved(self):
        ratio = e049.bootstrap_ratio_ci([10.0, 10.0], [0.0, 0.0], "z", 20)
        self.assertIsNone(ratio["ratio"])
        pooled = e049.bootstrap_ratio_ci([10.0, 10.0], [1.0, 3.0], "z", 20)
        self.assertEqual(pooled["ratio"], 5.0)


class PairedDirectionTests(unittest.TestCase):
    """Hand-built seeds so a flipped comparison cannot pass as a lucky draw."""

    def _row(self, recovery, good, improvements):
        key = e049._key(e049.PRIMARY_FRACTION)
        improvement = {
            e049.improvement_key(mode, m): {"improvements": improvements, "proposals": 100}
            for mode in e049.IMPROVEMENT_MODES
            for m in e049.SENSITIVITY_MATERIALITY
        }
        return {
            "horizon": HORIZON,
            "post_change_utility_auc": 1.0,
            "recovery": {key: {"first_passage": recovery, "sustained": recovery}},
            "coverage": {key: {"good_post": good, "viable_post": good}},
            "improvement": improvement,
        }

    def _seeds(self, qd, other, n=6):
        out = []
        for _ in range(n):
            seed = {s: self._row(*other) for s in e049.STRATEGIES}
            seed[e049.ARCHIVE_ARM] = self._row(*qd)
            out.append(seed)
        return out

    def test_a_faster_more_diverse_archive_wins_every_pair(self):
        seeds = self._seeds(qd=(0, 9, 5), other=(3, 2, 1))
        report = e049.paired_against_archive(seeds, resamples=20)["random"]
        time = report["recovery_first_passage"]["time_sign_test"]
        self.assertEqual((time["archive_faster"], time["other_faster"]), (6, 0))
        self.assertEqual(report["niches_good_post_change"]["archive_higher"], 6)
        self.assertEqual(report["improvements"]["other_higher"], 0)
        self.assertGreater(report["niches_good_post_change"]["paired_mean_difference"]["mean"], 0)

    def test_a_censored_baseline_loses_and_two_censored_arms_tie(self):
        seeds = self._seeds(qd=(0, 1, 1), other=(None, 1, 1))
        report = e049.paired_against_archive(seeds, resamples=20)["planner"]
        mc = report["recovery_first_passage"]["mcnemar_reached"]
        self.assertEqual((mc["archive_only"], mc["other_only"], mc["neither"]), (6, 0, 0))
        tied = e049.paired_against_archive(
            self._seeds(qd=(None, 1, 1), other=(None, 1, 1)), resamples=20
        )["planner"]["recovery_first_passage"]
        self.assertEqual(tied["time_sign_test"]["ties"], 6)
        self.assertEqual(tied["time_sign_test"]["p_exact_two_sided"], 1.0)
        self.assertEqual(tied["mcnemar_reached"]["neither"], 6)

    def test_a_baseline_that_wins_is_reported_as_winning(self):
        seeds = self._seeds(qd=(4, 1, 0), other=(0, 8, 3))
        report = e049.paired_against_archive(seeds, resamples=20)["majority"]
        self.assertEqual(report["recovery_first_passage"]["time_sign_test"]["other_faster"], 6)
        self.assertEqual(report["niches_good_post_change"]["other_higher"], 6)
        self.assertLess(report["niches_good_post_change"]["paired_mean_difference"]["mean"], 0)


class MeasureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _tiny_measure()

    def test_same_seeds_give_an_identical_report(self):
        self.assertEqual(self.report, _tiny_measure())

    def test_report_covers_all_five_arms_with_no_archive_size_dependence(self):
        report = self.report
        self.assertEqual(tuple(report["aggregate"]), e049.STRATEGIES)
        for arm in e049.STRATEGIES:
            self.assertIn("niches_good_post_change", report["aggregate"][arm])
            self.assertEqual(len(report["per_seed_primary"][arm]["improvements"]), 2)
        self.assertNotIn("archive_size", json.dumps(report["aggregate"]))
        self.assertEqual(
            set(report["paired_against_archive"]), set(e049.STRATEGIES) - {e049.ARCHIVE_ARM}
        )

    def test_the_multiple_comparison_count_is_the_number_of_tests_reported(self):
        reported = 0
        for entry in self.report["paired_against_archive"].values():
            for key in entry:
                reported += 2 if key.startswith("recovery_") else 1
        self.assertEqual(reported, self.report["multiple_comparisons"]["paired_tests_reported"])

    def test_report_states_what_it_does_not_measure(self):
        text = " ".join(self.report["not_measured"])
        for topic in ("human attention", "novelty", "churn"):
            self.assertIn(topic, text)

    def test_replay_check_flags_a_mismatch_with_the_committed_artifact(self):
        # A 3-seed tiny run cannot reproduce the 100-seed artifact, and must say so.
        check = e049.compare_to_committed_e024(
            [_replay(7)[0], _replay(8)[0]], Path(E024_ARTIFACT)
        )
        self.assertFalse(check["matches"])
        self.assertEqual(check["committed_aggregate_sha256"], E024_AGGREGATE_DIGEST)

    def test_fewer_than_two_seeds_is_refused(self):
        with self.assertRaises(ValueError):
            e049.measure(seeds=1, reference={"optimum_utility": OPTIMUM})


if __name__ == "__main__":
    unittest.main()
