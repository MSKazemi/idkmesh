"""Tests for E038: is an arm-blind gate an arm-neutral gate?

E037 measured that weakening the verifier panel *raises* the archive's lead and
ruled out the two obvious mechanisms, leaving "why" open. E038's answer is that
one of E037's own findings -- the gate is arm-blind -- does not imply what it
looks like it implies, because the arms are not equally exposed to the two
directions of verification error.

That claim lives or dies on comparisons between arms, so the tests here pin the
things that would let a comparison say nothing:

1. **the ranking functions must be arithmetic, not labels.** ``verdicts`` picks
   a least-viable arm, a most-exposed arm and a worst-damaged arm.
   :class:`VerdictTest` drives each of them with synthetic counters where the
   answer is known by construction, including cases where the prediction is
   *false*, so a clause that can only come out true is caught.
2. **base viability must be read where the gate cannot lie.** It is defined on
   the perfect panel, where the accept rate is the truth rate.
   :class:`BaseViabilityTest` pins that it is computed from
   ``viable_evaluations`` and not from an imperfect panel's accepts.
3. **the counters must be pooled, not averaged.** The arms have different
   denominators, so a per-seed rate averaged across seeds is not the pooled
   rate. :class:`PooledCounterTest` pins that the committed artifact's rates are
   the pooled ones.
"""

from __future__ import annotations

import json
import os
import re
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e033_goal_distance as e033
import sim.e034_goal_direction as e034
import sim.e037_ladder_under_panels as e037
import sim.e038_symmetric_gate_asymmetric_burden as e038

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
ARTIFACT = "E038-symmetric-gate-asymmetric-burden.json"
WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E038-symmetric-gate.md")
E037_WRITE_UP = os.path.join(REPO_ROOT, "experiments", "E037-ladder-under-panels.md")


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _arm(*, proposals=1000, viable=1000, attempts=1000, accepts=1000,
         false_accepts=0, false_rejects=0, utility=20.0):
    return {
        "proposal_attempts": proposals,
        "viable_evaluations": viable,
        "verification_attempts": attempts,
        "verification_accepts": accepts,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "post_change_utility_auc": utility * 10,
        "accept_rate": accepts / attempts if attempts else 0.0,
        "mean_utility_auc": utility,
    }


def _rows(**panels):
    """panel -> arm -> counters. Missing arms default to a clean, viable arm."""
    return {
        panel: {arm: arms.get(arm, _arm()) for arm in mbe.STRATEGIES}
        for panel, arms in panels.items()
    }


class BaseViabilityTest(unittest.TestCase):
    def test_it_is_the_true_viable_share_not_the_accept_share(self):
        rows = _rows(
            perfect={"random": _arm(proposals=1000, viable=400, accepts=400)},
        )
        self.assertAlmostEqual(e038.base_viability(rows)["random"], 0.4, places=6)

    def test_it_is_read_off_the_perfect_panel_only(self):
        rows = _rows(
            perfect={"random": _arm(proposals=1000, viable=400)},
            stress={"random": _arm(proposals=1000, viable=900)},
        )
        # The stress row would say 0.9 if the wrong panel were used.
        self.assertAlmostEqual(e038.base_viability(rows)["random"], 0.4, places=6)

    def test_a_zero_proposal_arm_does_not_divide_by_zero(self):
        rows = _rows(perfect={"random": _arm(proposals=0, viable=0)})
        self.assertEqual(e038.base_viability(rows)["random"], 0.0)


class ExposureTest(unittest.TestCase):
    def test_a_mostly_viable_arm_has_almost_no_false_accepts(self):
        rows = _rows(stress={"qd": _arm(false_accepts=5, false_rejects=95)})
        block = e038.exposure(rows, "stress")["qd"]
        self.assertAlmostEqual(block["false_accept_share"], 0.05, places=6)

    def test_a_mostly_junk_arm_is_dominated_by_false_accepts(self):
        rows = _rows(stress={"random": _arm(false_accepts=90, false_rejects=10)})
        block = e038.exposure(rows, "stress")["random"]
        self.assertAlmostEqual(block["false_accept_share"], 0.9, places=6)

    def test_an_errorless_panel_reports_a_zero_share_not_a_crash(self):
        rows = _rows(perfect={})
        for arm, block in e038.exposure(rows, "perfect").items():
            with self.subTest(arm=arm):
                self.assertEqual(block["errors"], 0)
                self.assertEqual(block["false_accept_share"], 0.0)


class DamageTest(unittest.TestCase):
    def test_the_change_is_signed_against_the_baseline_panel(self):
        rows = _rows(
            perfect={"random": _arm(utility=20.0), "qd": _arm(utility=22.0)},
            stress={"random": _arm(utility=18.0), "qd": _arm(utility=22.5)},
        )
        block = e038.damage(rows, "stress")
        self.assertAlmostEqual(block["random"]["change"], -2.0, places=6)
        self.assertAlmostEqual(block["qd"]["change"], +0.5, places=6)


class VerdictTest(unittest.TestCase):
    def _supporting(self):
        """Counters that make every clause come out as predicted."""
        return _rows(
            perfect={
                "random": _arm(proposals=1000, viable=400, utility=20.0),
                "qd": _arm(proposals=1000, viable=970, utility=22.0),
            },
            stress={
                "random": _arm(
                    proposals=1000, viable=400, false_accepts=90, false_rejects=10,
                    utility=17.0,
                ),
                "qd": _arm(
                    proposals=1000, viable=970, false_accepts=5, false_rejects=95,
                    utility=22.4,
                ),
            },
        )

    def test_the_supporting_case_is_supported(self):
        block = e038.verdicts(self._supporting(), ["perfect", "stress"])
        self.assertTrue(block["supported"])
        self.assertEqual(block["met_count"], 4)
        self.assertEqual(block["least_viable_arm"], "random")
        self.assertEqual(block["most_false_accept_exposed_arm"]["stress"], "random")
        self.assertEqual(block["worst_damaged_arm"]["stress"], "random")

    def test_arms_with_similar_base_viability_kill_the_explanation(self):
        rows = self._supporting()
        rows["perfect"]["random"]["viable_evaluations"] = 960
        block = e038.verdicts(rows, ["perfect", "stress"])
        self.assertFalse(block["clauses"]["arms_differ_sharply_in_base_viability"])
        self.assertFalse(block["supported"])
        self.assertTrue(block["partially_supported"])

    def test_the_gap_threshold_is_a_constant_not_a_fitted_value(self):
        rows = self._supporting()
        # Exactly at the stated gap: 0.75 vs 0.95 is 0.20.
        rows["perfect"]["random"]["viable_evaluations"] = 750
        for arm in mbe.STRATEGIES:
            if arm != "random":
                rows["perfect"][arm]["viable_evaluations"] = 950
        block = e038.verdicts(rows, ["perfect", "stress"])
        self.assertAlmostEqual(block["base_viability_spread"], e038.VIABILITY_GAP, places=6)
        self.assertTrue(block["clauses"]["arms_differ_sharply_in_base_viability"])

    def test_damage_landing_on_a_viable_arm_breaks_the_third_clause(self):
        rows = self._supporting()
        rows["stress"]["qd"]["mean_utility_auc"] = 5.0
        block = e038.verdicts(rows, ["perfect", "stress"])
        self.assertEqual(block["worst_damaged_arm"]["stress"], "qd")
        self.assertFalse(
            block["clauses"]["the_least_viable_arm_takes_the_worst_utility_damage"]
        )
        self.assertFalse(block["clauses"]["the_archive_is_not_the_most_damaged_arm"])
        self.assertFalse(block["supported"])

    def test_exposure_landing_on_a_viable_arm_breaks_the_second_clause(self):
        rows = self._supporting()
        rows["stress"]["qd"]["false_accepts"] = 999
        block = e038.verdicts(rows, ["perfect", "stress"])
        self.assertEqual(block["most_false_accept_exposed_arm"]["stress"], "qd")
        self.assertFalse(
            block["clauses"][
                "the_least_viable_arm_is_the_most_exposed_to_false_accepts"
            ]
        )

    def test_every_clause_is_scored_against_a_written_expectation(self):
        block = e038.verdicts(self._supporting(), ["perfect", "stress"])
        self.assertEqual(sorted(block["clauses"]), sorted(e038.PREDICTION["clauses"]))
        self.assertEqual(sorted(block["met"]), sorted(e038.PREDICTION["clauses"]))


class PooledCounterTest(unittest.TestCase):
    """Rates must be pooled over runs, not averaged over per-seed rates."""

    @classmethod
    def setUpClass(cls):
        cls.report = _load(ARTIFACT)

    def test_each_accept_rate_is_the_pooled_ratio(self):
        for panel in self.report["panels"]:
            for arm, row in self.report["per_panel"][panel].items():
                with self.subTest(panel=panel, arm=arm):
                    self.assertAlmostEqual(
                        row["accept_rate"],
                        row["verification_accepts"] / row["verification_attempts"],
                        places=6,
                    )

    def test_the_budget_is_matched_across_arms_on_every_panel(self):
        for panel in self.report["panels"]:
            attempts = {
                row["proposal_attempts"]
                for row in self.report["per_panel"][panel].values()
            }
            with self.subTest(panel=panel):
                self.assertEqual(len(attempts), 1)

    def test_every_panel_ran_the_same_number_of_runs(self):
        expected = self.report["seeds"] * len(self.report["goals"])
        self.assertEqual(self.report["runs_per_panel"], expected)


class CommittedReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _load(ARTIFACT)

    def test_the_verdicts_are_a_function_of_the_committed_counters(self):
        fresh = e038.verdicts(self.report["per_panel"], self.report["panels"])
        self.assertEqual(self.report["verdicts"], fresh)

    def test_the_exposure_block_is_a_function_of_the_committed_counters(self):
        for panel in self.report["panels"]:
            with self.subTest(panel=panel):
                self.assertEqual(
                    self.report["exposure"][panel],
                    e038.exposure(self.report["per_panel"], panel),
                )

    def test_the_damage_block_is_a_function_of_the_committed_counters(self):
        for panel, block in self.report["damage"].items():
            with self.subTest(panel=panel):
                self.assertEqual(block, e038.damage(self.report["per_panel"], panel))

    def test_the_perfect_panel_makes_no_verification_errors(self):
        for arm, row in self.report["per_panel"]["perfect"].items():
            with self.subTest(arm=arm):
                self.assertEqual(row["false_accepts"], 0)
                self.assertEqual(row["false_rejects"], 0)

    def test_the_probe_goals_are_e037s_probe_goals(self):
        sweep = _load("E034-goal-direction.json")
        expected = {
            trait: [round(w, 9) for w in goal]
            for trait, goal in e037.leakage_goals(sweep).items()
        }
        self.assertEqual(self.report["goals"], expected)

    def test_the_panels_are_e037s_panels(self):
        self.assertEqual(self.report["panels"], list(e037.PANEL_ORDER))


class WriteUpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WRITE_UP, encoding="utf-8") as handle:
            cls.text = handle.read()
        cls.report = _load(ARTIFACT)

    def test_every_arms_base_viability_is_in_the_record(self):
        for arm, value in self.report["verdicts"]["base_viability"].items():
            with self.subTest(arm=arm):
                self.assertIn(f"{value:.4f}", self.text)

    def test_the_named_arms_are_the_artifacts_named_arms(self):
        verdicts = self.report["verdicts"]
        self.assertIn(f"`{verdicts['least_viable_arm']}`", self.text)
        for panel, arm in verdicts["worst_damaged_arm"].items():
            with self.subTest(panel=panel):
                self.assertIn(f"`{arm}`", self.text)

    def test_the_outcome_is_stated_as_measured(self):
        verdicts = self.report["verdicts"]
        word = (
            "supported"
            if verdicts["supported"]
            else ("partially supported" if verdicts["partially_supported"] else "not supported")
        )
        self.assertIn(word, self.text.lower())
        self.assertIn(f"{verdicts['met_count']} of {verdicts['clause_count']}", self.text)

    def test_the_association_is_not_written_as_an_intervention(self):
        # E038 never manipulates base viability; the record must say so.
        self.assertIn("association", self.text.lower())
        self.assertIn("## Limitations", self.text)
        self.assertIn("## Decision", self.text)

    def test_the_record_carries_the_threshold_it_judged_against(self):
        self.assertIn(f"{e038.VIABILITY_GAP}", self.text)


class SupersededRecordTest(unittest.TestCase):
    """E037 left the question open; its record must carry the answer."""

    @classmethod
    def setUpClass(cls):
        with open(E037_WRITE_UP, encoding="utf-8") as handle:
            cls.text = handle.read()

    def test_e037_points_forward_to_e038(self):
        self.assertIn("E038", self.text)
        self.assertIn("E038-symmetric-gate.md", self.text)

    def test_the_open_question_is_marked_answered(self):
        self.assertNotIn("why is not established", self.text)
        self.assertIn("E038", self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
