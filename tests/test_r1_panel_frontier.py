"""The panel frontier sweep, and the guardrails that stop it being misread.

The sweep exists to answer #380's real question -- not "does a panel help" but
"does it still help once you pay for it". Three of its guardrails are load
bearing and are tested as behaviour rather than left as prose:

* it must never reduce the grid to a mean over dependence shape, because the
  two shapes move in opposite directions in parts of it and the average cancels
  a real effect;
* it must separate a *decisive* billing reversal from a cell sitting near a tie,
  because the raw count reads 85% at two seeds and 45-52% at sixteen to
  thirty-two, and the difference is entirely tie-flipping;
* it must carry its own sample-size sensitivity, so an underpowered run cannot
  be quoted as a finding.
"""

from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path

from randomness_lab.r1_panel_frontier import (
    DEFAULT_SEEDS,
    SAMPLE_SIZE_SENSITIVITY,
    PanelFrontierConfig,
    count_billing_disagreements,
    measure_frontier,
    render_markdown,
    run_panel_frontier,
    summarise_billing_sensitivity,
    summarise_shape_separation,
)

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/experiments/r1/panel-frontier-seeds42-65.json.gz"

# Small enough to run in the suite; the committed payload uses the defaults.
FAST = PanelFrontierConfig(tasks=40, seeds=(42, 43, 44, 45))


class FrontierShapeTests(unittest.TestCase):
    def test_the_grid_covers_every_need_from_one_to_k(self) -> None:
        cells = measure_frontier(FAST)
        for panel_size in FAST.panel_sizes:
            needs = {c["need"] for c in cells if c["panel_size"] == panel_size}
            self.assertEqual(
                needs,
                set(range(1, panel_size + 1)),
                "the quorum must be swept across its whole range; a prior result "
                "in this repository survives only on a sub-range of `need`.",
            )

    def test_single_verifier_cells_are_not_duplicated_across_shapes(self) -> None:
        cells = measure_frontier(FAST)
        singles = [c for c in cells if c["panel_size"] == 1]
        self.assertTrue(singles)
        self.assertEqual(
            len({c["shape"] for c in singles}),
            1,
            "at k=1 there is nothing to be dependent with, so emitting the cell "
            "once per shape would double-count it in every summary.",
        )

    def test_both_shapes_and_both_billings_are_present_for_real_panels(self) -> None:
        cells = [c for c in measure_frontier(FAST) if c["panel_size"] > 1]
        self.assertEqual({c["shape"] for c in cells}, set(FAST.shapes))
        self.assertEqual({c["billing"] for c in cells}, set(FAST.billings))


class ShapeSeparationTests(unittest.TestCase):
    def test_separation_is_reported_per_cell_never_averaged(self) -> None:
        rows = summarise_shape_separation(measure_frontier(FAST))
        self.assertTrue(rows)
        for row in rows:
            for key in ("panel_size", "need", "correlation", "billing"):
                self.assertIn(key, row, "a row must identify its own cell")

    def test_the_shapes_coincide_at_zero_correlation(self) -> None:
        """They share a code path there, so any difference is a defect."""

        rows = summarise_shape_separation(measure_frontier(FAST))
        zero = [r for r in rows if r["correlation"] == 0.0]
        self.assertTrue(zero)
        for row in zero:
            self.assertAlmostEqual(row["utility_delta"], 0.0, places=12)


class BillingDecisivenessTests(unittest.TestCase):
    def test_a_reversal_is_only_decisive_when_both_sides_are(self) -> None:
        rows = summarise_billing_sensitivity(measure_frontier(FAST))
        summary = count_billing_disagreements(rows)
        self.assertLessEqual(
            summary["cells_that_change_verdict_decisively"],
            summary["cells_that_change_verdict"],
            "a decisive reversal is a strict subset of a raw reversal",
        )

    def test_a_margin_inside_its_own_noise_is_not_decisive(self) -> None:
        """The assertion the `decisive <= raw` check cannot make.

        Marking every reversal decisive satisfies a subset test trivially --
        verified by mutation, which is how this test came to exist. What must
        hold is the definition itself: a margin that does not clear two
        standard errors is not a result.
        """

        rows = summarise_billing_sensitivity(measure_frontier(FAST))
        indecisive = [r for r in rows if abs(r["utility_vs_single_verifier"])
                      <= 2 * r["margin_stderr"]]
        self.assertTrue(
            indecisive,
            "no cell in this grid sits inside its own noise, so this test "
            "cannot discriminate; widen the grid or lower the sample size.",
        )
        for row in indecisive:
            self.assertFalse(
                row["decisive"],
                f"cell k={row['panel_size']} need={row['need']} "
                f"rho={row['correlation']} has margin "
                f"{row['utility_vs_single_verifier']:+.4f} against stderr "
                f"{row['margin_stderr']:.4f}, which is inside the noise, yet is "
                "reported as decisive.",
            )

    def test_every_margin_carries_its_standard_error(self) -> None:
        for row in summarise_billing_sensitivity(measure_frontier(FAST)):
            self.assertIn("margin_stderr", row)
            self.assertGreaterEqual(row["margin_stderr"], 0.0)
            self.assertIsInstance(row["decisive"], bool)

    def test_the_sample_size_sensitivity_is_published(self) -> None:
        """An underpowered run must be visible in the artifact itself."""

        raw = SAMPLE_SIZE_SENSITIVITY["raw_reversals_of_80"]
        self.assertGreater(
            raw["2x60"],
            raw["24x250"],
            "the recorded sensitivity must still show that a small run "
            "overstates the effect; if this inverts, re-measure it.",
        )


class CommittedPayloadTests(unittest.TestCase):
    def test_the_payload_exists_and_declares_its_generator(self) -> None:
        self.assertTrue(RESULT.is_file(), f"{RESULT} is missing")
        payload = json.loads(gzip.decompress(RESULT.read_bytes()).decode("utf-8"))
        self.assertEqual(payload["generator"], "randomness_lab.r1_panel_frontier.v1")
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("sample_size_sensitivity", payload)
        self.assertIn("simulator", payload["interpretation_guardrail"].lower())

    def test_the_payload_is_not_underpowered(self) -> None:
        """The artifact must be generated at the sample size the module documents.

        This exists because it was not. The committed payload was generated at
        three seeds while the dataclass default said twenty-four: `main` builds
        its config from argparse, whose own `--seeds` default had been left
        behind, so the CLI silently won. The headline assertion below still
        passed, because it happens to hold at three seeds too -- a green test
        over an artifact measured at the exact sample size this module warns
        reports double the effect.
        """

        payload = json.loads(gzip.decompress(RESULT.read_bytes()).decode("utf-8"))
        seeds = payload["config"]["seeds"]
        self.assertGreaterEqual(
            len(seeds),
            len(DEFAULT_SEEDS),
            f"the committed payload was generated with {len(seeds)} seeds, "
            f"fewer than the documented default of {len(DEFAULT_SEEDS)}. Its "
            f"numbers are not the ones this module claims to report -- "
            f"regenerate it with the defaults.",
        )
        self.assertGreaterEqual(payload["config"]["tasks"], 250)

    def test_the_headline_negative_result_holds_in_the_payload(self) -> None:
        """Charging per read, no cell in the grid pays for its panel.

        This is the one robust finding: it holds at every sample size tested.
        The `per_candidate` advantage does not -- it appears only at 250 tasks
        and vanishes at 120 -- so it is deliberately not asserted here.
        """

        payload = json.loads(gzip.decompress(RESULT.read_bytes()).decode("utf-8"))
        per_verifier = [
            row
            for row in payload["billing_sensitivity"]
            if row["billing"] == "per_verifier"
        ]
        self.assertTrue(per_verifier)
        self.assertEqual(
            sum(1 for row in per_verifier if row["beats_single_verifier"]),
            0,
            "a panel billed per read beat a single verifier somewhere in the "
            "grid; the headline result has changed and needs re-writing.",
        )


class RenderTests(unittest.TestCase):
    def test_markdown_names_the_decisive_count_and_the_guardrail(self) -> None:
        text = render_markdown(run_panel_frontier(FAST))
        self.assertIn("simulator", text.lower())
        self.assertIn("Shape separation", text)


if __name__ == "__main__":
    unittest.main()
