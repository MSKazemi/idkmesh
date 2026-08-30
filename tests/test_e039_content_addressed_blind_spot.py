"""Tests for E039: the content-addressed blind spot and the coordinated adversary.

The load-bearing claim of E039 is a *structural* one -- the panel reads the
artifact through one bit -- so the first class here re-derives it from the
running code rather than trusting the committed artifact. The rest pin the
construction (does the rebuilt panel really have the same marginal accuracy?),
the adversary (does it really start out identical to E036's?), and the record
(does the prose still say what the artifact says, including the clause that
came out false?).
"""

from __future__ import annotations

import json
import math
import pathlib
import random
import re
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e028_latent_defect_dimension as e028
import sim.e036_adversarial_contributors as e036
import sim.e039_content_addressed_blind_spot as e039

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "experiments" / "results" / "E039-content-addressed-blind-spot.json"
WRITE_UP = ROOT / "experiments" / "E039-content-addressed-blind-spot.md"
E036_RECORD = ROOT / "experiments" / "E036-adversarial-contributors.md"


def _report():
    with REPORT.open(encoding="utf-8") as handle:
        return json.load(handle)


class ContentBlindnessTest(unittest.TestCase):
    """Result 1, re-derived from the code rather than read off the artifact."""

    def test_verify_candidate_touches_the_candidate_exactly_once(self):
        import inspect

        source = inspect.getsource(sim.verify_candidate)
        body = source.split('"""', 2)[-1]
        uses = [line for line in body.splitlines() if re.search(r"\bc\b", line)]
        self.assertEqual(
            [u.strip() for u in uses],
            ["truth = viable(c)"],
            "verify_candidate now reads the candidate somewhere else; E039's "
            "Result 1 is a claim about this function and must be re-derived",
        )

    def test_two_candidates_with_one_bit_in_common_are_indistinguishable(self):
        out = e039.content_blindness(draws=500)
        self.assertTrue(out["distinct_candidates"])
        self.assertTrue(out["identical_decisions_within_viable"])
        self.assertTrue(out["identical_decisions_within_nonviable"])
        self.assertTrue(out["decisions_differ_across_the_viability_bit"])
        self.assertTrue(out["candidate_is_read_through_one_bit"])

    def test_the_proof_is_the_whole_sequence_not_a_summary_statistic(self):
        # A rate could match by luck; an identical 500-long decision sequence
        # on the same stream cannot. Guard that the probe compares sequences.
        import inspect

        source = inspect.getsource(e039.content_blindness)
        self.assertIn("decisions(viables[0]) == decisions(viables[1])", source)


class RegionCalibrationTest(unittest.TestCase):
    def test_the_region_carries_the_mass_the_coin_carried(self):
        base = e027.PANELS[e039.BASE_PANEL]
        region = e039.calibrate_region(target=base.blind_spot, draws=40_000)
        self.assertLessEqual(abs(region["calibration_error"]), 0.01)
        self.assertGreater(region["region_size"], 0)
        self.assertLess(region["region_size"], region["niche_count"])

    def test_calibration_is_deterministic(self):
        a = e039.calibrate_region(target=0.0556, draws=20_000)
        b = e039.calibrate_region(target=0.0556, draws=20_000)
        self.assertEqual(a, b)

    def test_diffuse_spreads_the_same_mass_over_more_niches(self):
        conc = e039.calibrate_region(target=0.0556, shape="concentrated", draws=40_000)
        diff = e039.calibrate_region(target=0.0556, shape="diffuse", draws=40_000)
        self.assertGreater(diff["region_size"], conc["region_size"])

    def test_an_unknown_shape_is_refused(self):
        with self.assertRaises(ValueError):
            e039.calibrate_region(target=0.05, shape="whatever")


class PanelConstructionTest(unittest.TestCase):
    """The rebuilt panel must be marginally identical, not merely similar."""

    def test_marginal_accuracy_is_preserved_exactly(self):
        base = e027.PANELS[e039.BASE_PANEL]
        built = e039.content_addressed_panel()
        # Outside the region the built panel is `built.accuracy` accurate and
        # inside it is 0. Weighted by the region's mass that must come back to
        # the base panel's marginal accuracy.
        marginal = (1.0 - base.blind_spot) * built.accuracy
        self.assertAlmostEqual(marginal, base.accuracy, places=9)

    def test_the_scalar_blind_spot_is_removed_not_kept(self):
        built = e039.content_addressed_panel()
        self.assertEqual(built.blind_spot, 0.0)

    def test_size_correlation_and_quorum_are_carried_over(self):
        base = e027.PANELS[e039.BASE_PANEL]
        built = e039.content_addressed_panel()
        self.assertEqual(built.verifiers, base.verifiers)
        self.assertEqual(built.correlation, base.correlation)
        self.assertEqual(built.quorum, base.quorum)
        self.assertEqual(built.dependence, base.dependence)


class AdversaryMemoryTest(unittest.TestCase):
    def test_an_unseen_niche_scores_one_half(self):
        memory = e039.AdversaryMemory()
        self.assertEqual(memory.score((3, 3)), 0.5)

    def test_accepts_raise_the_score_and_rejects_lower_it(self):
        memory = e039.AdversaryMemory()
        for _ in range(10):
            memory.record((0, 0), True)
            memory.record((1, 1), False)
        self.assertGreater(memory.score((0, 0)), 0.5)
        self.assertLess(memory.score((1, 1)), 0.5)

    def test_reset_clears_everything(self):
        memory = e039.AdversaryMemory()
        memory.record((0, 0), True)
        memory.region_hits = 5
        memory.total = 7
        memory.reset()
        self.assertEqual(memory.score((0, 0)), 0.5)
        self.assertEqual(memory.region_hits, 0)
        self.assertEqual(memory.total, 0)


class CoordinatedAdversaryTest(unittest.TestCase):
    """It must *start* identical to E036's, or the contrast is confounded."""

    def _bound(self, coordinated: bool):
        return e039._candidate_class(
            fraction=1.0, effort=8, coordinated=coordinated, bins=8
        )

    def test_with_an_empty_memory_it_picks_what_e036_picks(self):
        e039.MEMORY.reset()
        blind = self._bound(False)
        smart = self._bound(True)
        for seed in range(25):
            a = blind.random(random.Random(seed))
            b = smart.random(random.Random(seed))
            self.assertEqual(
                a.traits,
                b.traits,
                "an adversary that has learned nothing must behave exactly "
                "like the goal-blind one",
            )

    def test_a_learned_niche_changes_the_choice(self):
        e039.MEMORY.reset()
        smart = self._bound(True)
        baseline = smart.random(random.Random(3))
        # Teach it that the niche it did *not* pick is the one that gets in.
        # The hostility coin is flipped before the draws, so replaying the
        # stream has to consume it too or the reconstruction is off by one.
        replay = random.Random(3)
        replay.random()
        drawn = [
            super(e036.AdversarialCandidate, smart).random(replay) for _ in range(8)
        ]
        rejected = [c for c in drawn if sim.niche(c, 8) != sim.niche(baseline, 8)]
        self.assertTrue(rejected, "need a draw in a different niche to teach")
        target = sim.niche(rejected[0], 8)
        for _ in range(40):
            e039.MEMORY.record(target, True)
        learned = smart.random(random.Random(3))
        e039.MEMORY.reset()
        self.assertEqual(sim.niche(learned, 8), target)

    def test_hostility_still_zeroes_integrity(self):
        e039.MEMORY.reset()
        smart = self._bound(True)
        c = smart.random(random.Random(11))
        self.assertEqual(c.traits[e028.LATENT_INDEX], e039.HOSTILE_INTEGRITY)
        self.assertFalse(e028.latent_viable(c))

    def test_a_zero_fraction_pool_is_never_hostile(self):
        klass = e039._candidate_class(fraction=0.0, effort=8, coordinated=True, bins=8)
        rng = random.Random(5)
        for _ in range(50):
            c = klass.random(rng)
            self.assertNotEqual(c.traits[e028.LATENT_INDEX], e039.HOSTILE_INTEGRITY)

    def test_a_bad_fraction_or_effort_is_refused(self):
        with self.assertRaises(ValueError):
            e039._candidate_class(fraction=1.5, effort=8, coordinated=True, bins=8)
        with self.assertRaises(ValueError):
            e039._candidate_class(fraction=0.1, effort=0, coordinated=True, bins=8)


class RegionVerifierTest(unittest.TestCase):
    def test_everything_in_the_region_is_decided_against_the_truth(self):
        region = frozenset({(0, 0), (7, 7)})
        with e039.blind_spot_landscape(
            fraction=0.0, effort=1, coordinated=False, region=region, bins=8
        ):
            rng = random.Random(1)
            stats = sim.VerificationStats()
            config = e039.content_addressed_panel()
            found = 0
            draw = random.Random(9)
            for _ in range(4000):
                c = e028.LatentCandidate.random(draw)
                if sim.niche(c, 8) not in region:
                    continue
                found += 1
                accepted = sim.verify_candidate(c, rng, config, stats)
                self.assertEqual(accepted, not e028.latent_viable(c))
            self.assertGreater(found, 0, "no candidate landed in the region")

    def test_the_landscape_restores_all_three_patched_names(self):
        before = (sim.Candidate, sim.viable, sim.verify_candidate)
        with e039.blind_spot_landscape(
            fraction=0.1, effort=2, coordinated=True, region=[(0, 0)], bins=8
        ):
            self.assertIsNot(sim.verify_candidate, before[2])
        self.assertEqual((sim.Candidate, sim.viable, sim.verify_candidate), before)

    def test_the_landscape_restores_on_an_exception(self):
        before = (sim.Candidate, sim.viable, sim.verify_candidate)
        with self.assertRaises(RuntimeError):
            with e039.blind_spot_landscape(
                fraction=0.1, effort=2, coordinated=True, region=[(0, 0)], bins=8
            ):
                raise RuntimeError("boom")
        self.assertEqual((sim.Candidate, sim.viable, sim.verify_candidate), before)

    def test_a_memoryless_cell_installs_no_region(self):
        with e039.blind_spot_landscape(
            fraction=0.0, effort=1, coordinated=False, region=None, bins=8
        ):
            rng = random.Random(2)
            stats = sim.VerificationStats()
            config = e027.PANELS["measured"]
            draw = random.Random(4)
            decided_against_truth = 0
            for _ in range(600):
                c = e028.LatentCandidate.random(draw)
                if sim.verify_candidate(c, rng, config, stats) != e028.latent_viable(c):
                    decided_against_truth += 1
            # Errors still happen -- it is an imperfect panel -- but they are
            # the panel's own, not a region's.
            self.assertLess(decided_against_truth, 600)


class StatisticsTest(unittest.TestCase):
    def test_a_zero_pooled_variance_is_not_reported_as_resolved(self):
        self.assertIsNone(e039.two_proportion_z(0, 10, 0, 10))
        self.assertIsNone(e039.two_proportion_z(10, 10, 10, 10))

    def test_an_obvious_difference_resolves(self):
        z = e039.two_proportion_z(90, 100, 10, 100)
        self.assertIsNotNone(z)
        self.assertGreater(z, e039.RESOLVED_Z)

    def test_the_sign_follows_the_first_argument(self):
        self.assertLess(e039.two_proportion_z(10, 100, 90, 100), 0.0)

    def test_empty_trials_are_refused_rather_than_dividing(self):
        self.assertIsNone(e039.two_proportion_z(0, 0, 1, 10))


class PredictionScoringTest(unittest.TestCase):
    def _cell(self, shape, adversary, fraction, catastrophes, shares=None):
        arms = e039.STRATEGIES
        return {
            "panel_shape": shape,
            "adversary": adversary,
            "adversary_fraction": fraction,
            "seeds": 100,
            "catastrophic_seeds": {s: catastrophes for s in arms},
            "region_share": shares or {s: 0.1 for s in arms},
        }

    def _cells(self, coordinated_addressed=90, shares=None):
        return [
            self._cell("memoryless", "goal-blind", 0.10, 10),
            self._cell("memoryless", "coordinated", 0.10, 10),
            self._cell("content-addressed", "goal-blind", 0.10, 10),
            self._cell(
                "content-addressed", "coordinated", 0.10, coordinated_addressed, shares
            ),
        ]

    def test_a_clean_sweep_is_reported_as_supported(self):
        shares = {s: 0.1 for s in e039.STRATEGIES}
        shares[e039.ARCHIVE_ARM] = 0.9
        out = e039.prediction_outcome(
            self._cells(shares=shares),
            {"candidate_is_read_through_one_bit": True},
            headline_fraction=0.10,
        )
        self.assertTrue(out["supported"])
        self.assertEqual(out["clauses_met"], out["clauses_total"])

    def test_a_failed_exposure_clause_is_counted_as_failed(self):
        shares = {s: 0.9 for s in e039.STRATEGIES}
        shares[e039.ARCHIVE_ARM] = 0.01
        out = e039.prediction_outcome(
            self._cells(shares=shares),
            {"candidate_is_read_through_one_bit": True},
            headline_fraction=0.10,
        )
        self.assertFalse(out["supported"])
        self.assertFalse(out["per_clause"]["the_archive_is_the_most_exposed_arm"])

    def test_an_attack_that_does_nothing_fails_the_attack_clause(self):
        out = e039.prediction_outcome(
            self._cells(coordinated_addressed=10),
            {"candidate_is_read_through_one_bit": True},
            headline_fraction=0.10,
        )
        self.assertFalse(out["per_clause"]["coordination_pays_against_a_content_addressed_panel"])

    def test_an_attack_in_the_wrong_direction_does_not_count_as_the_attack(self):
        # Resolved, but *fewer* catastrophes under coordination. That is not
        # the predicted attack and must not be scored as one.
        out = e039.prediction_outcome(
            self._cells(coordinated_addressed=0),
            {"candidate_is_read_through_one_bit": True},
            headline_fraction=0.10,
        )
        self.assertFalse(
            out["per_clause"]["coordination_pays_against_a_content_addressed_panel"]
        )

    def test_the_null_clauses_are_named_as_nulls(self):
        out = e039.prediction_outcome(
            self._cells(),
            {"candidate_is_read_through_one_bit": True},
            headline_fraction=0.10,
        )
        self.assertEqual(
            sorted(out["null_clauses"]),
            [
                "content_addressing_alone_is_not_the_attack",
                "coordination_is_worthless_against_a_memoryless_panel",
            ],
        )
        self.assertIn("not evidence", out["null_clause_caveat"].lower() + " ")

    def test_a_missing_cell_is_an_error_not_a_silent_default(self):
        with self.assertRaises(KeyError):
            e039.prediction_outcome(
                self._cells()[:2],
                {"candidate_is_read_through_one_bit": True},
                headline_fraction=0.10,
            )


class CommittedReportTest(unittest.TestCase):
    def setUp(self):
        self.report = _report()

    def test_the_artifact_is_e039(self):
        self.assertEqual(self.report["experiment_id"], "E039")
        self.assertEqual(self.report["experiment"], e039.EXPERIMENT)

    def test_the_prediction_is_the_one_in_the_module(self):
        self.assertEqual(self.report["prediction"], e039.PREDICTION)

    def test_the_prediction_was_stated_before_the_run(self):
        self.assertTrue(self.report["prediction"]["stated_before_run"])

    def test_the_scoring_reproduces_from_the_cells(self):
        recomputed = e039.prediction_outcome(
            self.report["cells"],
            self.report["content_blindness"],
            headline_fraction=self.report["configuration"]["headline_fraction"],
        )
        self.assertEqual(recomputed, self.report["outcome"])

    def test_the_mechanism_block_reproduces_from_the_cells(self):
        recomputed = e039.mechanism(
            self.report["cells"],
            headline_fraction=self.report["configuration"]["headline_fraction"],
        )
        self.assertEqual(recomputed, self.report["mechanism"])

    def test_every_pairing_was_checked(self):
        for cell in self.report["cells"]:
            self.assertEqual(
                cell["pairing_checks"],
                cell["seeds"] * len(e039.STRATEGIES),
                "an exposure record was not matched to the arm that made it",
            )

    def test_the_exposure_clause_is_recorded_as_falsified(self):
        # This is the point of the record. If a later edit makes the clause
        # pass, it is because the clause was rewritten, not because the world
        # changed -- so the test asserts the *failure*.
        self.assertFalse(
            self.report["outcome"]["per_clause"]["the_archive_is_the_most_exposed_arm"]
        )
        self.assertFalse(self.report["outcome"]["supported"])

    def test_the_mechanism_block_is_marked_post_hoc(self):
        self.assertTrue(self.report["mechanism"]["stated_after_the_run"])

    def test_the_region_is_a_strict_subset_of_the_niche_grid(self):
        for shape in ("concentrated", "diffuse"):
            region = self.report["regions"][shape]
            self.assertGreater(region["region_size"], 0)
            self.assertLess(region["region_size"], region["niche_count"])

    def test_the_panels_differ_only_in_where_the_blind_spot_lives(self):
        memoryless = self.report["panels"]["memoryless"]
        addressed = self.report["panels"]["content_addressed"]
        self.assertEqual(memoryless["verifiers"], addressed["verifiers"])
        self.assertEqual(memoryless["correlation"], addressed["correlation"])
        self.assertEqual(addressed["blind_spot"], 0.0)
        self.assertGreater(addressed["accuracy"], memoryless["accuracy"])

    def test_limitations_name_the_construction_and_the_nulls(self):
        text = " ".join(self.report["limitations"]).lower()
        self.assertIn("construction", text)
        self.assertIn("null", text)


class WriteUpTest(unittest.TestCase):
    def setUp(self):
        self.text = WRITE_UP.read_text(encoding="utf-8")
        self.report = _report()

    def test_the_write_up_exists_and_names_the_experiment(self):
        self.assertIn("E039", self.text)

    def test_the_falsified_clause_is_stated_in_the_prose(self):
        lowered = self.text.lower()
        self.assertTrue(
            "falsif" in lowered or "came out backwards" in lowered,
            "the record must say the exposure clause failed",
        )

    def test_the_clause_count_matches_the_artifact(self):
        outcome = self.report["outcome"]
        expected = f"{outcome['clauses_met']} of {outcome['clauses_total']}"
        self.assertIn(expected, self.text)

    def test_the_archive_region_share_is_quoted_correctly(self):
        share = self.report["mechanism"]["archive_region_share"]
        self.assertIn(f"{share:.4f}", self.text)

    def test_the_post_hoc_reading_is_labelled_post_hoc(self):
        self.assertIn("post-hoc", self.text.lower())

    def test_the_one_bit_result_is_in_the_prose(self):
        self.assertIn("one bit", self.text.lower())


class SupersededRecordTest(unittest.TestCase):
    def test_e036_points_forward_to_e039(self):
        text = E036_RECORD.read_text(encoding="utf-8")
        self.assertIn("E039", text)

    def test_e036_still_states_its_own_next_step(self):
        text = E036_RECORD.read_text(encoding="utf-8")
        self.assertIn("coordinated", text.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
