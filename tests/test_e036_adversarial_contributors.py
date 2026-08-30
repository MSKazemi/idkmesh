"""Tests for E036: contributors who optimise to pass the gate.

E026-E028 model verification failing by accident. E036 models it failing to an
opponent, so the tests here pin the three things that would make the result an
artefact rather than a finding:

1. **The control must be an identity, not an approximation.** At
   ``fraction = 0.0`` the hostile branch never touches the rng, so a sweep must
   be *bit-identical* to E028's, the way E027's cost-0.0 column is.
   :class:`ControlTest` proves it on the stream and on a full sweep.
2. **The adversary must actually be adversarial.** Effort 1 has to be
   indistinguishable from an honest contributor on apparent quality, effort 8
   has to look strictly *better* than honest, and both have to be certainly
   non-viable. Otherwise "effort" is a label rather than a mechanism.
3. **The two attack channels must stay separated.** A hostile contributor both
   occupies a proposal slot (starvation) and, on an imperfect panel, gets
   accepted (poisoning). The perfect panel admits nothing, so it isolates
   starvation; if starvation alone moved the archive, every other cell would be
   confounded. :class:`StarvationControlTest` reads that off the artifact.

The verdict machinery is tested for reachability the same way E035's is: a
prediction that cannot come out false is not a prediction.
"""

from __future__ import annotations

import json
import os
import random
import re
import statistics
import unittest

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e028_latent_defect_dimension as e028
import sim.e036_adversarial_contributors as e036

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
WRITE_UP = os.path.join(
    REPO_ROOT, "experiments", "E036-adversarial-contributors.md"
)
ARTIFACT = "E036-adversarial-contributors.json"


def _load(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def _bound(fraction, effort, sigma=e028.INTEGRITY_SIGMA_DEFAULT):
    return e036._candidate_class(
        fraction=fraction, effort=effort, integrity_sigma=sigma
    )


class AdversaryMechanicsTest(unittest.TestCase):
    def test_a_hostile_artifact_is_certainly_defective(self):
        cls = _bound(1.0, 4)
        rng = random.Random(3)
        for _ in range(500):
            candidate = cls.random(rng)
            self.assertEqual(
                candidate.traits[e028.LATENT_INDEX], e036.ADVERSARY_INTEGRITY
            )
            self.assertFalse(e028.latent_viable(candidate))

    def test_a_hostile_artifact_still_respects_the_trait_budget(self):
        """The attack is on integrity, not on the budget contract."""
        cls = _bound(1.0, 8)
        rng = random.Random(5)
        for _ in range(500):
            candidate = cls.random(rng)
            self.assertLessEqual(
                sum(candidate.traits[: e028.LATENT_INDEX]), sim.BUDGET + 1e-9
            )

    def test_effort_one_is_indistinguishable_from_an_honest_contributor(self):
        """A faulty contributor ships junk but does not try to look good."""
        hostile = _bound(1.0, 1)
        honest = _bound(0.0, 1)
        rng = random.Random(101)
        hostile_quality = statistics.fmean(
            sim.unchecked_robust_quality(hostile.random(rng)) for _ in range(20000)
        )
        rng = random.Random(101)
        honest_quality = statistics.fmean(
            sim.unchecked_robust_quality(honest.random(rng)) for _ in range(20000)
        )
        # Not bit-equal: a hostile draw spends one rng call on the coin, so the
        # two streams diverge. The claim is distributional -- effort 1 buys the
        # adversary nothing that shows.
        self.assertAlmostEqual(hostile_quality, honest_quality, delta=0.005)

    def test_effort_makes_a_hostile_artifact_look_better_than_an_honest_one(self):
        """This is the mechanism. Without it 'strategic' means nothing."""
        honest = statistics.fmean(
            sim.unchecked_robust_quality(_bound(0.0, 1).random(random.Random(7 + i)))
            for i in range(1500)
        )
        previous = None
        for effort in (1, 4, 8):
            quality = statistics.fmean(
                sim.unchecked_robust_quality(
                    _bound(1.0, effort).random(random.Random(7 + i))
                )
                for i in range(1500)
            )
            with self.subTest(effort=effort):
                if previous is not None:
                    self.assertGreater(quality, previous)
                previous = quality
        self.assertGreater(previous, honest)

    def test_the_realised_hostile_share_is_the_requested_fraction(self):
        for fraction in (0.05, 0.2, 0.4):
            cls = _bound(fraction, 2)
            rng = random.Random(23)
            drawn = [cls.random(rng) for _ in range(20000)]
            realised = sum(
                1
                for c in drawn
                if c.traits[e028.LATENT_INDEX] == e036.ADVERSARY_INTEGRITY
            ) / len(drawn)
            with self.subTest(fraction=fraction):
                self.assertAlmostEqual(realised, fraction, delta=0.015)

    def test_mutation_is_hostile_at_the_same_rate(self):
        """Measured from a healthy parent, so clamping cannot inflate the count."""
        healthy = self._healthy_parent()
        cls = _bound(0.5, 4)
        parent = cls(healthy.traits)
        rng = random.Random(29)
        children = [parent.mutate(rng) for _ in range(20000)]
        realised = sum(
            1
            for c in children
            if c.traits[e028.LATENT_INDEX] == e036.ADVERSARY_INTEGRITY
        ) / len(children)
        self.assertAlmostEqual(realised, 0.5, delta=0.02)

    @staticmethod
    def _healthy_parent():
        cls = _bound(0.0, 1)
        rng = random.Random(1)
        for _ in range(2000):
            candidate = cls.random(rng)
            if candidate.traits[e028.LATENT_INDEX] > 0.7:
                return candidate
        raise AssertionError("no healthy parent drawn")

    def test_a_healthy_lineage_never_produces_the_adversarys_signature(self):
        """So integrity == 0.0 identifies a hostile artifact in an audit."""
        parent = self._healthy_parent()
        rng = random.Random(77)
        self.assertEqual(
            sum(
                1
                for _ in range(20000)
                if parent.mutate(rng).traits[e028.LATENT_INDEX]
                == e036.ADVERSARY_INTEGRITY
            ),
            0,
        )

    def test_a_poisoned_lineage_stays_poisoned(self):
        """0.0 is five mutation sigmas below the floor, so the defect is heritable."""
        cls = _bound(0.0, 1)
        poisoned = cls(
            self._healthy_parent().traits[: e028.LATENT_INDEX]
            + (e036.ADVERSARY_INTEGRITY,)
        )
        rng = random.Random(77)
        children = [poisoned.mutate(rng) for _ in range(20000)]
        self.assertFalse(any(e028.latent_viable(c) for c in children))
        clamped = sum(
            1
            for c in children
            if c.traits[e028.LATENT_INDEX] == e036.ADVERSARY_INTEGRITY
        ) / len(children)
        self.assertGreater(clamped, 0.4)

    def test_the_configuration_is_validated(self):
        for bad in ({"fraction": -0.1}, {"fraction": 1.5}, {"effort": 0}):
            kwargs = {
                "fraction": 0.1,
                "effort": 2,
                "integrity_sigma": e028.INTEGRITY_SIGMA_DEFAULT,
            }
            kwargs.update(bad)
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    e036._candidate_class(**kwargs)


class LandscapeTest(unittest.TestCase):
    def test_the_landscape_is_restored_even_on_an_exception(self):
        modules = e028._landscape_modules()
        before = [(m.Candidate, m.viable) for m in modules]
        with self.assertRaises(RuntimeError):
            with e036.adversarial_landscape(fraction=0.5, effort=2):
                raise RuntimeError("boom")
        self.assertEqual([(m.Candidate, m.viable) for m in modules], before)

    def test_every_module_that_owns_the_landscape_is_patched(self):
        modules = e028._landscape_modules()
        self.assertTrue(modules)
        with e036.adversarial_landscape(fraction=0.5, effort=2) as cls:
            for module in modules:
                with self.subTest(module=module.__name__):
                    self.assertIs(module.Candidate, cls)
                    self.assertIs(module.viable, e028.latent_viable)


class ControlTest(unittest.TestCase):
    """Zero fraction must be E028 exactly, not approximately."""

    def test_zero_fraction_consumes_no_randomness(self):
        adversarial, baseline = random.Random(97), random.Random(97)
        cls = _bound(0.0, 8)
        latent = e028._candidate_class(e028.INTEGRITY_SIGMA_DEFAULT)
        for _ in range(400):
            self.assertEqual(
                cls.random(adversarial).traits, latent.random(baseline).traits
            )
        self.assertEqual(adversarial.random(), baseline.random())

    def test_a_zero_fraction_sweep_is_bit_identical_to_e028(self):
        report = e036.identity_check(
            seeds=4, seed_start=1, agents=16, generations=12, change_at=6, bins=8
        )
        self.assertTrue(report["identical"])
        for panel, row in report["by_panel"].items():
            with self.subTest(panel=panel):
                self.assertTrue(row["identical"])

    def test_the_panels_are_e027s_panels_by_reference(self):
        """So a cell here is comparable with the same cell in E027 and E028."""
        self.assertEqual(e036.PANEL_ORDER, e027.PANEL_ORDER)
        for name in e036.PANEL_ORDER:
            with self.subTest(panel=name):
                self.assertEqual(
                    e036.PANELS[name].as_dict(), e027.PANELS[name].as_dict()
                )


class VerdictTest(unittest.TestCase):
    """Every verdict must be reachable, or the prediction cannot be falsified."""

    @staticmethod
    def _cell(panel, fraction, effort, qd, majority, defect=0.0):
        return {
            "panel": panel,
            "adversary_fraction": fraction,
            "adversary_effort": effort,
            "catastrophic_seeds": {"qd": qd, "majority": majority},
            "retained_defect_rate": {"qd": defect},
            "post_change_utility_auc": {"qd": 20.0},
        }

    def test_advantage_is_the_baseline_minus_the_archive(self):
        self.assertEqual(
            e036.catastrophe_advantage(self._cell("measured", 0.1, 1, 3, 40)), 37
        )

    def test_a_prediction_can_come_out_supported(self):
        cells = [
            self._cell("measured", 0.0, 1, 0, 40),
            self._cell("measured", 0.1, 1, 0, 40),
            self._cell("measured", 0.0, 8, 0, 40),
            self._cell("measured", 0.1, 8, 30, 40),
        ]
        outcome = e036.prediction_outcome(cells)
        self.assertTrue(outcome["advantage_shrinks_with_effort"])
        self.assertTrue(outcome["archive_loses_its_zero_record"])
        self.assertTrue(outcome["supported"])
        self.assertFalse(outcome["partially_supported"])

    def test_a_prediction_can_come_out_falsified(self):
        cells = [
            self._cell("measured", 0.0, 1, 0, 40),
            self._cell("measured", 0.1, 1, 0, 40),
            self._cell("measured", 0.0, 8, 0, 40),
            self._cell("measured", 0.1, 8, 0, 40),
        ]
        outcome = e036.prediction_outcome(cells)
        self.assertFalse(outcome["supported"])
        self.assertFalse(outcome["archive_loses_its_zero_record"])
        self.assertEqual(outcome["panels_where_the_archive_lost_a_clean_record"], [])

    def test_half_a_prediction_is_reported_as_half(self):
        cells = [
            self._cell("measured", 0.0, 1, 0, 40),
            self._cell("measured", 0.1, 1, 0, 40),
            self._cell("measured", 0.0, 8, 0, 40),
            self._cell("measured", 0.1, 8, 5, 90),
        ]
        outcome = e036.prediction_outcome(cells)
        self.assertTrue(outcome["archive_loses_its_zero_record"])
        self.assertFalse(outcome["advantage_shrinks_with_effort"])
        self.assertTrue(outcome["partially_supported"])
        self.assertFalse(outcome["supported"])

    def test_a_panel_that_was_already_failing_cannot_lose_a_clean_record(self):
        """Only a panel whose zero-fraction archive was clean can lose one."""
        cells = [
            self._cell("stress", 0.0, 1, 60, 70),
            self._cell("stress", 0.1, 1, 80, 70),
            self._cell("stress", 0.0, 8, 60, 70),
            self._cell("stress", 0.1, 8, 90, 70),
        ]
        outcome = e036.prediction_outcome(cells)
        self.assertEqual(outcome["panels_where_the_archive_lost_a_clean_record"], [])

    def test_the_perfect_panel_is_excluded_from_grading(self):
        graded = [
            self._cell("measured", 0.0, 1, 0, 40),
            self._cell("measured", 0.1, 1, 0, 40),
            self._cell("measured", 0.0, 8, 0, 40),
            self._cell("measured", 0.1, 8, 30, 40),
        ]
        with_control = graded + [
            self._cell("perfect", 0.0, 1, 0, 11),
            self._cell("perfect", 0.1, 8, 0, 11),
        ]
        self.assertEqual(
            e036.prediction_outcome(graded)["advantage_by_effort"],
            e036.prediction_outcome(with_control)["advantage_by_effort"],
        )


class CommittedMatrixTest(unittest.TestCase):
    def setUp(self):
        self.report = _load(ARTIFACT)
        self.cells = self.report["cells"]
        self.config = self.report["configuration"]

    def _cell(self, panel, fraction, effort):
        for cell in self.cells:
            if (
                cell["panel"] == panel
                and cell["adversary_fraction"] == fraction
                and cell["adversary_effort"] == effort
            ):
                return cell
        raise AssertionError(f"no cell for {panel} {fraction} {effort}")

    def test_the_matrix_is_the_shape_the_module_defines(self):
        self.assertEqual(
            len(self.cells),
            len(e036.PANEL_ORDER) * len(e036.FRACTIONS) * len(e036.EFFORTS),
        )
        self.assertEqual(tuple(self.config["adversary_fractions"]), e036.FRACTIONS)
        self.assertEqual(tuple(self.config["adversary_efforts"]), e036.EFFORTS)
        self.assertEqual(tuple(self.config["strategies"]), mbe.STRATEGIES)

    def test_the_zero_fraction_column_exists_on_every_panel(self):
        for panel in e036.PANEL_ORDER:
            for effort in e036.EFFORTS:
                with self.subTest(panel=panel, effort=effort):
                    self.assertIsNotNone(self._cell(panel, 0.0, effort))

    def test_the_control_column_does_not_depend_on_effort(self):
        """At fraction zero nobody is hostile, so effort cannot matter."""
        for panel in e036.PANEL_ORDER:
            first = self._cell(panel, 0.0, e036.EFFORTS[0])
            for effort in e036.EFFORTS[1:]:
                with self.subTest(panel=panel, effort=effort):
                    self.assertEqual(
                        self._cell(panel, 0.0, effort)["catastrophic_seeds"],
                        first["catastrophic_seeds"],
                    )

    def test_the_prediction_was_recorded_before_the_run(self):
        self.assertTrue(self.report["prediction"]["stated_before_run"])
        for key in ("claim", "reasoning", "falsified_if"):
            with self.subTest(key=key):
                self.assertTrue(self.report["prediction"][key].strip())

    def test_the_committed_outcome_agrees_with_the_module(self):
        self.assertEqual(
            e036.prediction_outcome(self.cells), self.report["outcome"]
        )

    def test_the_budget_contract_is_identical_in_every_cell(self):
        self.assertEqual(
            self.config["evaluation_budget_per_strategy_per_seed"],
            self.config["agents"] * self.config["generations"],
        )


class StarvationControlTest(unittest.TestCase):
    """The perfect panel separates starvation from poisoning."""

    def setUp(self):
        self.report = _load(ARTIFACT)
        self.perfect = [c for c in self.report["cells"] if c["panel"] == "perfect"]

    def test_the_perfect_panel_admits_no_hostile_artifact(self):
        self.assertTrue(self.perfect)
        for cell in self.perfect:
            for strategy, rate in cell["retained_defect_rate"].items():
                with self.subTest(
                    fraction=cell["adversary_fraction"], strategy=strategy
                ):
                    self.assertEqual(rate, 0.0)

    def test_starvation_alone_does_not_move_the_archive(self):
        """If it did, every poisoning cell would be confounded by it."""
        control = self.report["outcome"]["starvation_only_control"]
        self.assertTrue(control["admits_no_defect"])
        self.assertTrue(control["archive_unmoved"])
        self.assertEqual(control["archive_catastrophes"], [0])

    def test_starvation_costs_the_archive_almost_nothing(self):
        control = self.report["outcome"]["starvation_only_control"]
        baseline = [
            c["post_change_utility_auc"]["qd"]
            for c in self.perfect
            if c["adversary_fraction"] == 0.0
        ][0]
        self.assertLess(control["worst_archive_auc_loss"] / baseline, 0.05)


class WriteUpTest(unittest.TestCase):
    def setUp(self):
        with open(WRITE_UP, encoding="utf-8") as handle:
            self.text = handle.read()
        self.report = _load(ARTIFACT)

    def test_the_write_up_states_the_prediction_and_its_grade(self):
        self.assertRegex(self.text, r"(?m)^## .*prediction")
        outcome = self.report["outcome"]
        verdict = (
            "supported"
            if outcome["supported"]
            else "falsified"
            if not outcome["partially_supported"]
            else "partially"
        )
        self.assertRegex(self.text, rf"(?i){verdict}")

    def _catastrophe_table(self):
        """Parse the panel-by-effort archive table out of the write-up.

        Parsed rather than substring-searched: ``assertIn("58", text)`` is
        satisfied by any number that merely contains 58, which let a wrong
        headline number through when this was first written.
        """
        fractions = self.report["configuration"]["adversary_fractions"]
        rows = {}
        for line in self.text.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            if len(cells) != len(fractions) + 2:
                continue
            match = re.fullmatch(r"k=(\d+)", cells[1])
            if match is None or cells[0] not in e036.PANEL_ORDER:
                continue
            if not all(re.fullmatch(r"\d+", c) for c in cells[2:]):
                continue
            rows[(cells[0], int(match.group(1)))] = [int(c) for c in cells[2:]]
        return rows

    def test_the_archive_table_matches_the_artifact_cell_for_cell(self):
        rows = self._catastrophe_table()
        self.assertEqual(
            len(rows), len(e036.PANEL_ORDER) * len(e036.EFFORTS)
        )
        fractions = self.report["configuration"]["adversary_fractions"]
        by_key = {
            (c["panel"], c["adversary_effort"]): c for c in self.report["cells"]
        }
        for (panel, effort), values in rows.items():
            for fraction, value in zip(fractions, values):
                cell = next(
                    c
                    for c in self.report["cells"]
                    if c["panel"] == panel
                    and c["adversary_effort"] == effort
                    and c["adversary_fraction"] == fraction
                )
                with self.subTest(panel=panel, effort=effort, fraction=fraction):
                    self.assertEqual(value, cell["catastrophic_seeds"]["qd"])
        self.assertTrue(by_key)

    def test_the_worst_cell_is_named_in_the_prose(self):
        """The headline number must be stated, not only tabulated."""
        worst = max(
            (c for c in self.report["cells"] if c["panel"] == "measured"),
            key=lambda c: c["catastrophic_seeds"]["qd"],
        )
        self.assertRegex(
            self.text, rf"`{worst['catastrophic_seeds']['qd']}`"
        )

    def test_the_write_up_carries_the_starvation_control(self):
        self.assertRegex(self.text, r"(?i)starvation")
        self.assertRegex(self.text, r"(?i)perfect")

    def test_the_write_up_has_the_standard_sections(self):
        for heading in ("Design", "Reproduction", "Limitations", "Decision"):
            with self.subTest(heading=heading):
                self.assertRegex(self.text, rf"(?m)^## .*{heading}")

    def test_the_write_up_names_the_issue_gap_it_closes(self):
        self.assertRegex(self.text, r"(?i)malicious|adversar")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
