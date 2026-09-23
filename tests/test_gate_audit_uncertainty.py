"""Tests for the gate-audit finite-sample bootstrap uncertainty (issue #520).

Four properties are load-bearing, mirroring the acceptance criteria on #520:

1. **v0.1 is untouched.** Omitting ``bootstrap`` must reproduce exactly
   today's ``gate-audit-report-v0.1`` document; every existing test in
   ``tests/test_gate_audit.py`` already re-proves this on the same code path,
   so this file adds only the omission checks specific to the new parameter.
2. **Cross-verifier dependence survives resampling.** The method resamples
   whole candidate rows, never verifier cells; a pair of verifiers with a
   perfect, non-constant (anti-)correlation must keep that exact value in
   every replicate where it is even measurable.
3. **Every edge case in #520 fails closed or returns an explicit undefined
   state**, never a misleading number: too few candidates, a replicate at or
   below chance, a replicate with no measurable correlation, and the
   table-resolution censoring effective-votes already has at the point
   estimate.
4. **Determinism.** A fixed seed reproduces the identical interval.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from idkmesh import gate_audit, gate_audit_uncertainty  # noqa: E402
from idkmesh.gate_audit import GateAuditInputError  # noqa: E402

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

EXAMPLE_INPUT = REPO_ROOT / "examples" / "gate-audit" / "panel-votes.example.json"
SCHEMA_V01_PATH = REPO_ROOT / "schemas" / "gate-audit-report-v0.1.schema.json"
SCHEMA_V02_PATH = REPO_ROOT / "schemas" / "gate-audit-report-v0.2.schema.json"


def minimal_input(**overrides):
    data = {
        "gate_id": "test-gate",
        "evidence_class": "synthetic",
        "candidates": [
            {"id": "c1", "ground_truth": "accept"},
            {"id": "c2", "ground_truth": "accept"},
            {"id": "c3", "ground_truth": "reject"},
            {"id": "c4", "ground_truth": "reject"},
        ],
        "verifiers": [
            {"id": "v1", "verdicts": {"c1": "accept", "c2": "accept",
                                      "c3": "reject", "c4": "accept"}},
            {"id": "v2", "verdicts": {"c1": "accept", "c2": "reject",
                                      "c3": "reject", "c4": "reject"}},
            {"id": "v3", "verdicts": {"c1": "accept", "c2": "accept",
                                      "c3": "accept", "c4": "reject"}},
        ],
    }
    data.update(overrides)
    return data


def panel(candidates, verifiers, **overrides):
    data = {
        "gate_id": "uncertainty-fixture",
        "evidence_class": "synthetic",
        "candidates": candidates,
        "verifiers": verifiers,
    }
    data.update(overrides)
    return data


class QuantileTests(unittest.TestCase):
    """The interpolation method must match what the module documents."""

    def test_matches_hand_computed_linear_interpolation(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(
            gate_audit_uncertainty._quantile(values, 0.0), 1.0)
        self.assertAlmostEqual(
            gate_audit_uncertainty._quantile(values, 1.0), 5.0)
        self.assertAlmostEqual(
            gate_audit_uncertainty._quantile(values, 0.25), 2.0)
        self.assertAlmostEqual(
            gate_audit_uncertainty._quantile(values, 0.1), 1.4)

    def test_single_value_list_returns_that_value(self):
        self.assertEqual(gate_audit_uncertainty._quantile([7.0], 0.5), 7.0)


class BackwardCompatibilityTests(unittest.TestCase):
    """Omitting ``bootstrap`` must reproduce exactly today's v0.1 report."""

    def test_default_report_has_no_uncertainty_key(self):
        report = gate_audit.audit(minimal_input())
        self.assertNotIn("uncertainty", report)
        self.assertEqual(report["schema"], gate_audit.SCHEMA_ID)

    def test_explicit_none_bootstrap_matches_the_default(self):
        self.assertEqual(
            gate_audit.audit(minimal_input()),
            gate_audit.audit(minimal_input(), bootstrap=None))

    def test_committed_example_still_regenerates_byte_for_byte(self):
        committed = json.loads(
            (REPO_ROOT / "examples" / "gate-audit"
             / "gate-audit-report.example.json").read_text(encoding="utf-8"))
        self.assertEqual(gate_audit.audit_file(EXAMPLE_INPUT), committed)


class InsufficientCandidatesTests(unittest.TestCase):
    """Fewer than the minimum candidates must skip inference, not fake it."""

    def _tiny_panel(self):
        candidates = [
            {"id": "c1", "ground_truth": "accept"},
            {"id": "c2", "ground_truth": "reject"},
        ]
        verifiers = [{"id": "v1", "verdicts": {"c1": "accept", "c2": "reject"}}]
        return panel(candidates, verifiers)

    def test_sufficient_for_inference_is_false_and_sections_are_null(self):
        report = gate_audit.audit(
            self._tiny_panel(), bootstrap={"seed": 0, "replicates": 100})
        unc = report["uncertainty"]
        self.assertFalse(unc["sufficient_for_inference"])
        for key in ("panel_error", "mean_verifier_accuracy",
                    "mean_pairwise_error_correlation", "effective_votes"):
            self.assertIsNone(unc[key])

    def test_warning_names_the_shortfall(self):
        report = gate_audit.audit(
            self._tiny_panel(), bootstrap={"seed": 0, "replicates": 100})
        self.assertTrue(
            any("below the minimum" in w for w in report["warnings"]),
            report["warnings"])

    def test_schema_is_still_v0_2_when_bootstrap_was_requested(self):
        report = gate_audit.audit(
            self._tiny_panel(), bootstrap={"seed": 0, "replicates": 100})
        self.assertEqual(report["schema"], "gate-audit-report-v0.2")


class DeterminismTests(unittest.TestCase):
    @pytest.mark.slow
    def test_same_seed_and_replicates_reproduce_identically(self):
        first = gate_audit.audit(
            json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8")),
            bootstrap={"seed": 123, "replicates": 300})
        second = gate_audit.audit(
            json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8")),
            bootstrap={"seed": 123, "replicates": 300})
        self.assertEqual(first["uncertainty"], second["uncertainty"])
        self.assertEqual(gate_audit.render_json(first),
                          gate_audit.render_json(second))

    @pytest.mark.slow
    def test_different_seed_can_change_the_interval(self):
        input_data = json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8"))
        a = gate_audit.audit(
            input_data, bootstrap={"seed": 1, "replicates": 300})
        b = gate_audit.audit(
            input_data, bootstrap={"seed": 2, "replicates": 300})
        # Not asserting they always differ (they could coincide by chance);
        # asserting the seed is actually threaded through to the PRNG.
        self.assertEqual(a["uncertainty"]["seed"], 1)
        self.assertEqual(b["uncertainty"]["seed"], 2)


class PerfectPanelTests(unittest.TestCase):
    """Zero panel error must degenerate to a point interval, not error out."""

    def _perfect_panel(self):
        candidates = [
            {"id": f"c{i}", "ground_truth": "accept" if i % 2 else "reject"}
            for i in range(8)
        ]
        verdicts = {c["id"]: c["ground_truth"] for c in candidates}
        verifiers = [
            {"id": "v1", "verdicts": verdicts},
            {"id": "v2", "verdicts": verdicts},
            {"id": "v3", "verdicts": verdicts},
        ]
        return panel(candidates, verifiers)

    def test_panel_error_and_accuracy_intervals_are_degenerate_points(self):
        report = gate_audit.audit(
            self._perfect_panel(), bootstrap={"seed": 0, "replicates": 200})
        unc = report["uncertainty"]
        self.assertEqual(unc["panel_error"]["ci_low"], 0.0)
        self.assertEqual(unc["panel_error"]["ci_high"], 0.0)
        self.assertEqual(unc["mean_verifier_accuracy"]["ci_low"], 1.0)
        self.assertEqual(unc["mean_verifier_accuracy"]["ci_high"], 1.0)

    def test_effective_votes_interval_is_the_constant_floor_not_censored(self):
        report = gate_audit.audit(
            self._perfect_panel(), bootstrap={"seed": 0, "replicates": 200})
        eff = report["uncertainty"]["effective_votes"]
        self.assertEqual(eff["ci_low"], 1.0)
        self.assertEqual(eff["ci_high"], 1.0)
        self.assertFalse(eff["ci_high_censored"])


class UndefinedMetricReplicatesTests(unittest.TestCase):
    """A metric undefined in every replicate must say so, not omit itself."""

    def test_single_verifier_leaves_correlation_undefined_throughout(self):
        candidates = [
            {"id": f"c{i}", "ground_truth": "accept" if i % 2 else "reject"}
            for i in range(6)
        ]
        verifiers = [{"id": "v1", "verdicts": {
            c["id"]: c["ground_truth"] for c in candidates}}]
        report = gate_audit.audit(
            panel(candidates, verifiers),
            bootstrap={"seed": 0, "replicates": 200})
        corr = report["uncertainty"]["mean_pairwise_error_correlation"]
        self.assertEqual(corr["replicates_used"], 0)
        self.assertEqual(corr["replicates_undefined"], 200)
        self.assertIsNone(corr["ci_low"])
        self.assertIsNone(corr["ci_high"])
        self.assertTrue(any(
            "correlation interval is undefined for every replicate" in w
            for w in report["warnings"]))

    def test_always_wrong_verifier_leaves_effective_votes_undefined(self):
        candidates = [
            {"id": f"c{i}", "ground_truth": "accept" if i % 2 else "reject"}
            for i in range(6)
        ]

        def flip(gt):
            return "reject" if gt == "accept" else "accept"

        verifiers = [
            {"id": "v1", "verdicts": {
                c["id"]: flip(c["ground_truth"]) for c in candidates}},
            {"id": "v2", "verdicts": {
                c["id"]: flip(c["ground_truth"]) for c in candidates}},
        ]
        report = gate_audit.audit(
            panel(candidates, verifiers),
            bootstrap={"seed": 0, "replicates": 200})
        eff = report["uncertainty"]["effective_votes"]
        self.assertEqual(eff["replicates_used"], 0)
        self.assertEqual(eff["replicates_undefined"], 200)
        self.assertIsNone(eff["ci_low"])
        self.assertTrue(any(
            "effective-votes interval is undefined for every replicate" in w
            for w in report["warnings"]))


class DependencePreservationTests(unittest.TestCase):
    """The resampling unit must be the whole candidate row, not a cell.

    Two verifiers built to be perfectly anti-correlated (phi = -1 exactly)
    stay exactly anti-correlated in every replicate where the resample still
    has variance. If the implementation ever resampled verifier cells
    independently instead of candidate rows, this would fail: decoupling the
    two verifiers' draws would not, in general, preserve a perfect
    correlation.
    """

    def _anti_correlated_panel(self):
        candidates = [
            {"id": f"c{i:02d}", "ground_truth": "accept" if i % 2 else "reject"}
            for i in range(12)
        ]

        def flip(gt):
            return "reject" if gt == "accept" else "accept"

        # v1 wrong on odd-indexed candidates, right on even; v2 the exact
        # complement. Both error vectors have real variance (neither is
        # constant, unlike "always right" / "always wrong") and are exact
        # complements of each other, so phi == -1 wherever it is defined.
        v1_verdicts: dict[str, str] = {}
        v2_verdicts: dict[str, str] = {}
        for i, c in enumerate(candidates):
            gt = c["ground_truth"]
            if i % 2 == 0:
                v1_verdicts[c["id"]] = gt
                v2_verdicts[c["id"]] = flip(gt)
            else:
                v1_verdicts[c["id"]] = flip(gt)
                v2_verdicts[c["id"]] = gt
        verifiers = [
            {"id": "v1", "verdicts": v1_verdicts},
            {"id": "v2", "verdicts": v2_verdicts},
        ]
        return panel(candidates, verifiers)

    def test_correlation_stays_exactly_minus_one_whenever_defined(self):
        report = gate_audit.audit(
            self._anti_correlated_panel(),
            bootstrap={"seed": 5, "replicates": 500})
        corr = report["uncertainty"]["mean_pairwise_error_correlation"]
        self.assertGreater(
            corr["replicates_used"], 0,
            "no replicate had variance; strengthen the fixture rather than "
            "weaken this test")
        self.assertAlmostEqual(corr["ci_low"], -1.0, places=9)
        self.assertAlmostEqual(corr["ci_high"], -1.0, places=9)
        self.assertAlmostEqual(
            report["panel"]["mean_pairwise_error_correlation"], -1.0, places=9)


class CensoringTests(unittest.TestCase):
    """A censored point estimate can produce a censored CI upper bound too."""

    @staticmethod
    def _near_independent_panel(verifiers: int = 12, candidates: int = 80):
        import random

        rng = random.Random(7)
        cands = [
            {"id": f"c{i:04d}", "ground_truth": rng.choice(["accept", "reject"])}
            for i in range(candidates)
        ]
        vers = []
        for j in range(verifiers):
            verdicts = {}
            for cand in cands:
                truth = cand["ground_truth"]
                wrong = "reject" if truth == "accept" else "accept"
                verdicts[cand["id"]] = truth if rng.random() < 0.85 else wrong
            vers.append({"id": f"v{j:02d}", "verdicts": verdicts})
        return panel(cands, vers)

    def test_saturated_point_estimate_can_carry_a_censored_ci_high(self):
        report = gate_audit.audit(
            self._near_independent_panel(),
            bootstrap={"seed": 3, "replicates": 150})
        self.assertTrue(
            gate_audit.is_saturated(report["panel"]["effective_votes"]))
        eff = report["uncertainty"]["effective_votes"]
        self.assertTrue(eff["ci_high_censored"])
        self.assertEqual(eff["ci_high"], 199.0)

    @staticmethod
    def _comfortably_resolved_panel(verifiers: int = 5, candidates: int = 150):
        # More candidates than the committed example: with only ~12 the
        # bootstrap's own resampling noise can occasionally touch the table
        # edge even when the point estimate does not, which is a true
        # property of the interval, not something this test should assume
        # away. A larger, moderate-accuracy panel keeps the whole interval
        # away from the table edge instead.
        import random

        rng = random.Random(11)
        cands = [
            {"id": f"c{i:04d}", "ground_truth": rng.choice(["accept", "reject"])}
            for i in range(candidates)
        ]
        vers = []
        for j in range(verifiers):
            verdicts = {}
            for cand in cands:
                truth = cand["ground_truth"]
                wrong = "reject" if truth == "accept" else "accept"
                verdicts[cand["id"]] = truth if rng.random() < 0.75 else wrong
            vers.append({"id": f"v{j:02d}", "verdicts": verdicts})
        return panel(cands, vers)

    def test_unsaturated_panel_is_not_marked_censored(self):
        report = gate_audit.audit(
            self._comfortably_resolved_panel(),
            bootstrap={"seed": 0, "replicates": 150})
        self.assertFalse(gate_audit.is_saturated(
            report["panel"]["effective_votes"]))
        eff = report["uncertainty"]["effective_votes"]
        self.assertFalse(eff["ci_high_censored"])
        self.assertLess(eff["ci_high"], 199.0)


class ParameterValidationTests(unittest.TestCase):
    def test_replicates_below_minimum_is_refused(self):
        with self.assertRaises(GateAuditInputError) as ctx:
            gate_audit.audit(minimal_input(),
                              bootstrap={"seed": 0, "replicates": 99})
        self.assertIn("100", str(ctx.exception))

    def test_replicates_at_minimum_is_accepted(self):
        report = gate_audit.audit(minimal_input(),
                                   bootstrap={"seed": 0, "replicates": 100})
        self.assertEqual(report["uncertainty"]["replicates"], 100)

    def test_boolean_seed_is_refused(self):
        with self.assertRaises(GateAuditInputError):
            gate_audit.audit(minimal_input(),
                              bootstrap={"seed": True, "replicates": 100})

    def test_confidence_level_out_of_range_is_refused(self):
        for bad in (0.0, 1.0, 1.5, -0.1):
            with self.subTest(bad=bad):
                with self.assertRaises(GateAuditInputError):
                    gate_audit.audit(
                        minimal_input(),
                        bootstrap={"seed": 0, "replicates": 100,
                                   "confidence_level": bad})


class SchemaValidationTests(unittest.TestCase):
    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_bootstrap_report_validates_against_v0_2_schema(self):
        schema = json.loads(SCHEMA_V02_PATH.read_text(encoding="utf-8"))
        report = gate_audit.audit_file(
            EXAMPLE_INPUT, bootstrap={"seed": 0, "replicates": 300})
        jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_insufficient_candidates_report_validates_against_v0_2_schema(self):
        schema = json.loads(SCHEMA_V02_PATH.read_text(encoding="utf-8"))
        data = panel(
            [{"id": "c1", "ground_truth": "accept"},
             {"id": "c2", "ground_truth": "reject"}],
            [{"id": "v1", "verdicts": {"c1": "accept", "c2": "reject"}}])
        report = gate_audit.audit(data, bootstrap={"seed": 0, "replicates": 100})
        jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_v0_1_report_does_not_validate_against_v0_2_schema(self):
        # additionalProperties: false plus a required "uncertainty" key
        # should refuse a report that never computed one.
        schema = json.loads(SCHEMA_V02_PATH.read_text(encoding="utf-8"))
        report = gate_audit.audit_file(EXAMPLE_INPUT)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_v0_2_report_does_not_validate_against_v0_1_schema(self):
        # The "schema" const differs and v0.1 forbids the extra "uncertainty"
        # key: a v0.2 document must not silently pass as v0.1.
        schema = json.loads(SCHEMA_V01_PATH.read_text(encoding="utf-8"))
        report = gate_audit.audit_file(
            EXAMPLE_INPUT, bootstrap={"seed": 0, "replicates": 100})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)


class MarkdownRenderingTests(unittest.TestCase):
    def test_uncertainty_table_present_when_bootstrap_requested(self):
        report = gate_audit.audit_file(
            EXAMPLE_INPUT, bootstrap={"seed": 0, "replicates": 300})
        text = gate_audit.render_markdown(report)
        self.assertIn("## Finite-sample uncertainty", text)
        self.assertIn("| Metric | Point | CI low | CI high |", text)
        self.assertIn("Panel error", text)
        self.assertIn("Effective votes", text)

    def test_no_uncertainty_section_without_bootstrap(self):
        report = gate_audit.audit_file(EXAMPLE_INPUT)
        self.assertNotIn(
            "Finite-sample uncertainty", gate_audit.render_markdown(report))

    def test_insufficient_candidates_renders_a_skip_note(self):
        data = panel(
            [{"id": "c1", "ground_truth": "accept"},
             {"id": "c2", "ground_truth": "reject"}],
            [{"id": "v1", "verdicts": {"c1": "accept", "c2": "reject"}}])
        report = gate_audit.audit(data, bootstrap={"seed": 0, "replicates": 100})
        text = gate_audit.render_markdown(report)
        self.assertIn("Skipped:", text)
        self.assertIn("below the minimum", text)


def assert_close(case: unittest.TestCase, actual, expected, path: str = "$"):
    """Recursively compare, tolerating a last-bit float difference.

    `phi()` (unchanged v0.1 code this module calls thousands of times per
    audit) sums floats with the plain `sum()` builtin, whose summation
    algorithm for floats changed in Python 3.12 (compensated/Neumaier
    summation replaced naive left-to-right addition). The same seeded
    bootstrap can therefore round a correlation value to a different last
    representable bit on 3.11 versus 3.12+, even though the resampling
    itself (and every integer-valued computation in this module) is exactly
    reproducible. Structural fields (strings, ints, bools, keys) are still
    compared exactly; only floats get a tolerance, and it is tight enough
    (1e-9) that it could not hide a real regression.
    """
    if isinstance(expected, float) and isinstance(actual, float):
        case.assertAlmostEqual(actual, expected, places=9, msg=path)
    elif isinstance(expected, dict) and isinstance(actual, dict):
        case.assertEqual(set(actual), set(expected), path)
        for key in expected:
            assert_close(case, actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list) and isinstance(actual, list):
        case.assertEqual(len(actual), len(expected), path)
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert_close(case, a, e, f"{path}[{i}]")
    else:
        case.assertEqual(actual, expected, path)


class CommittedV02ExampleTests(unittest.TestCase):
    """The committed v0.2 example regenerates with the CLI defaults.

    Compared by value, not by byte-for-byte JSON equality — see
    ``assert_close``.
    """

    EXAMPLE_REPORT_V02 = (
        REPO_ROOT / "examples" / "gate-audit"
        / "gate-audit-report-v0.2.example.json")

    @pytest.mark.slow
    def test_regenerates_from_the_same_input_with_cli_default_bootstrap_params(self):
        report = gate_audit.audit_file(
            EXAMPLE_INPUT,
            bootstrap={
                "seed": 0,
                "replicates": gate_audit_uncertainty.DEFAULT_REPLICATES,
                "confidence_level": gate_audit_uncertainty.DEFAULT_CONFIDENCE_LEVEL,
            })
        committed = json.loads(
            self.EXAMPLE_REPORT_V02.read_text(encoding="utf-8"))
        assert_close(self, report, committed)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_committed_v0_2_example_validates_against_its_schema(self):
        schema = json.loads(SCHEMA_V02_PATH.read_text(encoding="utf-8"))
        committed = json.loads(
            self.EXAMPLE_REPORT_V02.read_text(encoding="utf-8"))
        jsonschema.validate(committed, schema)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        )

    def test_bootstrap_flag_emits_v0_2_with_uncertainty(self):
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT), "--bootstrap",
            "--bootstrap-replicates", "200", "--bootstrap-seed", "9")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema"], "gate-audit-report-v0.2")
        self.assertEqual(report["uncertainty"]["replicates"], 200)
        self.assertEqual(report["uncertainty"]["seed"], 9)

    def test_bootstrap_options_without_bootstrap_flag_are_refused(self):
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT), "--bootstrap-seed", "1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("require --bootstrap", proc.stderr)

    def test_replicates_below_minimum_is_refused_with_exit_2(self):
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT), "--bootstrap",
            "--bootstrap-replicates", "10")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("100", proc.stderr)

    def test_default_cli_invocation_is_unaffected(self):
        proc = self.run_cli("gate-audit", str(EXAMPLE_INPUT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema"], "gate-audit-report-v0.1")
        self.assertNotIn("uncertainty", report)


if __name__ == "__main__":
    unittest.main()
