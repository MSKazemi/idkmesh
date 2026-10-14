"""Nightly tests for E049: the committed artifact against a fresh replay.

These re-run real 50-agent, 50-generation seeds, so they cost seconds rather than
milliseconds and are marked ``sim``. The fast, tiny-configuration tests are in
``test_e049_derived_measurements.py``.

What they establish, in order of importance:

1. the replay reproduces E024's committed ``aggregate`` block digest-for-digest,
   so E049 measures E024's arms and not a lookalike;
2. the first seeds of the committed per-seed record can be re-derived exactly;
3. the headline reading in the record is arithmetic on the artifact, not a
   transcription.
"""

from __future__ import annotations

import importlib.util
import json
import os
import unittest

import sim.e049_derived_measurements as e049
import sim.matched_budget_emergence as mbe

# Marked `sim`: this module replays a committed experiment artifact, so it costs
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
E049 = os.path.join(RESULTS, "E049-derived-measurements.json")
REPLAYED_SEEDS = 4


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class CommittedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = _load(E049)
        cls.e024 = _load(E024)

    def test_configuration_is_the_committed_e024_configuration(self):
        config = self.artifact["configuration"]
        reference = self.e024["configuration"]
        for key in ("seed_start", "seeds", "agents", "generations", "change_at", "bins"):
            self.assertEqual(config[key], reference[key], key)
        self.assertEqual(config["verification"], reference["verification"])

    def test_the_artifact_records_a_matching_replay_of_e024(self):
        check = self.artifact["replay_check"]
        self.assertTrue(check["matches"])
        self.assertEqual(check["committed_aggregate_sha256"], check["replayed_aggregate_sha256"])
        self.assertEqual(
            check["committed_aggregate_sha256"], e049.canonical_digest(self.e024["aggregate"])
        )

    def test_first_seeds_re_derive_exactly_from_the_committed_record(self):
        optimum = e049.reference_optimum()["optimum_utility"]
        self.assertEqual(optimum, self.artifact["threshold_rule"]["optimum"]["optimum_utility"])
        key = e049._key(e049.PRIMARY_FRACTION)
        improvement = e049.improvement_key(e049.PRIMARY_MODE, e049.PRIMARY_MATERIALITY)
        config = self.artifact["configuration"]
        for index in range(REPLAYED_SEEDS):
            seed = config["seed_start"] + index
            payload, traces = e049.replay_seed(
                seed, config["agents"], config["generations"], config["change_at"], config["bins"]
            )
            # The replay is E024's own payload, so E024's row for this seed is intact.
            self.assertEqual(
                payload,
                mbe.run_seed(
                    seed, config["agents"], config["generations"], config["change_at"], config["bins"]
                ),
            )
            rows = e049.seed_metrics(
                payload, traces, optimum, config["change_at"], config["bins"]
            )
            for strategy in e049.STRATEGIES:
                committed = self.artifact["per_seed_primary"][strategy]
                row = rows[strategy]
                self.assertEqual(
                    row["recovery"][key]["first_passage"],
                    committed["recovery_first_passage"][index],
                )
                self.assertEqual(
                    row["recovery"][key]["sustained"], committed["recovery_sustained"][index]
                )
                self.assertEqual(
                    row["coverage"][key]["good_post"], committed["good_niches_post_change"][index]
                )
                self.assertEqual(
                    row["coverage"][key]["viable_post"],
                    committed["viable_niches_post_change"][index],
                )
                self.assertEqual(
                    row["improvement"][improvement]["improvements"],
                    committed["improvements"][index],
                )

    def test_archive_recovery_summary_is_arithmetic_on_the_per_seed_record(self):
        committed = self.artifact["per_seed_primary"]
        for strategy in e049.STRATEGIES:
            reached = sum(1 for v in committed[strategy]["recovery_first_passage"] if v is not None)
            self.assertEqual(
                self.artifact["aggregate"][strategy]["recovery_first_passage"]["reached"], reached
            )

    def test_unmeasured_quantities_are_listed_and_not_given_a_proxy(self):
        text = " ".join(self.artifact["not_measured"])
        for topic in ("human attention", "novelty", "churn"):
            self.assertIn(topic, text)
        self.assertNotIn("novelty", json.dumps(self.artifact["aggregate"]))


if __name__ == "__main__":
    unittest.main()
