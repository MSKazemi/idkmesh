"""Nightly tests for E050: the committed artifact against a fresh re-derivation.

These re-run real 50-agent, 50-generation seeds, so they cost seconds rather than
milliseconds and are marked ``sim``. The fast, tiny-configuration tests are in
``test_e050_churn.py``.

What they establish, in order of importance:

1. the ``f = 0`` cell reproduces E024's committed ``aggregate`` block
   digest-for-digest, so E050 extends E024's arms and not a lookalike;
2. the first seeds of the committed per-seed record can be re-derived exactly, at
   ``f = 0`` and in churned cells of both models;
3. the summaries in the record are arithmetic on the per-seed record, and the
   number of p-values the multiple-comparison note quotes is the number reported.
"""

from __future__ import annotations

import importlib.util
import json
import os
import unittest

import sim.e050_churn as e050
import sim.matched_budget_emergence as mbe

# Marked `sim`: this module re-derives a committed experiment artifact, so it costs
# seconds rather than milliseconds. `make test` (the pre-commit tier) runs
# `-m "not sim"` and skips it; `make nightly` runs `-m sim`. CI is unaffected --
# the PR gate runs a plain `pytest` with no marker filter.
#
# The import is guarded the way tests/test_schema_validity.py guards
# `jsonschema`: narrow workflow jobs run this module through `python -m unittest`
# on a bare interpreter, and a module-scope `import pytest` there would make the
# job fail to collect the file at all.
if importlib.util.find_spec("pytest") is not None:
    import pytest

    pytestmark = pytest.mark.sim
else:  # pragma: no cover - the bare-interpreter CI jobs take this path
    pytestmark = ()


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
E024 = os.path.join(RESULTS, "E024-matched-budget-emergence-100-seed-summary.json")
E050 = os.path.join(RESULTS, "E050-churn.json")
REPLAYED_SEEDS = 2
MAX_ARTIFACT_BYTES = 300 * 1024


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _walk(value, key):
    if isinstance(value, dict):
        return sum((1 if k == key else 0) + _walk(v, key) for k, v in value.items())
    if isinstance(value, list):
        return sum(_walk(v, key) for v in value)
    return 0


class CommittedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = _load(E050)
        cls.e024 = _load(E024)
        cls.config = cls.artifact["configuration"]

    def test_the_artifact_is_modest_in_size(self):
        self.assertLess(os.path.getsize(E050), MAX_ARTIFACT_BYTES)

    def test_configuration_is_the_committed_e024_configuration(self):
        reference = self.e024["configuration"]
        for key in ("seed_start", "seeds", "agents", "generations", "change_at", "bins"):
            self.assertEqual(self.config[key], reference[key], key)
        self.assertEqual(self.config["verification"], reference["verification"])

    def test_the_zero_churn_cell_reproduces_the_committed_e024_aggregate(self):
        check = self.artifact["reference_check"]["committed_e024"]
        self.assertTrue(check["matches"])
        self.assertEqual(check["committed_aggregate_sha256"], check["replayed_aggregate_sha256"])
        self.assertEqual(
            check["committed_aggregate_sha256"], e050.canonical_digest(self.e024["aggregate"])
        )

    def test_the_memory_model_leaves_the_state_free_arms_identical_by_digest(self):
        identical = self.artifact["reference_check"]["memory_model_arm_rows_identical_to_no_churn"]
        for arm in e050.STATE_FREE_ARMS:
            self.assertTrue(identical[arm], arm)
            self.assertTrue(all(identical[arm].values()), arm)
        self.assertFalse(all(identical["majority"].values()))

    def test_first_seeds_re_derive_exactly_in_every_sampled_cell(self):
        per_seed = self.artifact["per_seed_post_change_utility_auc"]
        cells = [(e050.MEMORY, 0.0), (e050.MEMORY, 0.5), (e050.COLD_START, 0.5), (e050.COLD_START, 1.0)]
        for index in range(REPLAYED_SEEDS):
            seed = self.config["seed_start"] + index
            args = (self.config["agents"], self.config["generations"],
                    self.config["change_at"], self.config["bins"])
            reference = {row["strategy"]: row for row in mbe.run_seed(seed, *args)["results"]}
            for model, fraction in cells:
                rows = e050.run_churn_seed(seed, *args, e050.Churn(fraction, model))
                if fraction == 0.0:
                    self.assertEqual(rows, reference)
                for arm in e050.STRATEGIES:
                    self.assertEqual(
                        rows[arm]["post_change_utility_auc"],
                        per_seed[model][f"{fraction:g}"][arm][index],
                        (seed, model, fraction, arm),
                    )

    def test_catastrophe_counts_are_arithmetic_on_the_per_seed_record(self):
        threshold = self.config["catastrophe_threshold_auc"]
        self.assertEqual(threshold, e050.catastrophe_threshold(
            self.config["generations"], self.config["change_at"]))
        for model, by_fraction in self.artifact["per_seed_post_change_utility_auc"].items():
            for fraction, arms in by_fraction.items():
                for arm, values in arms.items():
                    stated = self.artifact["aggregate"][model][fraction][arm]["catastrophic_seeds"]
                    self.assertEqual(stated, sum(1 for v in values if v < threshold))

    def test_sign_changes_are_recomputed_from_the_reported_leads(self):
        for model, arms in self.artifact["lead_sign_changes"].items():
            for arm, entry in arms.items():
                leads = {float(f): v for f, v in entry["archive_lead_by_fraction"].items()}
                recomputed = e050.first_sign_change(leads)
                self.assertEqual(
                    entry["first_sign_change_fraction"], recomputed["first_sign_change_fraction"]
                )
                self.assertEqual(entry["bracket"], recomputed["bracket"])

    def test_the_quoted_comparison_count_is_the_reported_count(self):
        models = self.config["models"]
        fractions = self.config["fractions"]
        counts = e050.comparison_count(models, fractions)
        self.assertEqual(self.artifact["multiple_comparisons"]["p_values_reported"], counts)
        lead = self.artifact["paired_against_archive"]
        listed = _walk(lead, "p_value") - _walk(lead[models[-1]]["0"], "p_value") * (len(models) - 1)
        listed += _walk(self.artifact["own_effect_of_churn"], "p_value")
        self.assertEqual(listed, counts["total"])
        self.assertEqual(
            self.artifact["multiple_comparisons"]["bonferroni_alpha_0.05"],
            round(0.05 / counts["total"], 6),
        )

    def test_the_record_says_what_it_does_not_measure(self):
        text = " ".join(self.artifact["not_measured"])
        for topic in ("leaves with its authors", "real people", "malicious"):
            self.assertIn(topic, text)
        self.assertIn("synthetic", self.artifact["evidence_level"])


if __name__ == "__main__":
    unittest.main()
