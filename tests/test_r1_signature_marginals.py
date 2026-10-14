"""Tests for the read-only R1 per-signature marginal-success post-processor.

Every report built here is a synthetic fixture constructed in the test. None of it
is real R1 evidence.
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from randomness_lab import r1_signature_marginals as marginals
from randomness_lab.r1_replay import ReplayCandidate, ReplayConfig, run_replay_analysis


def candidate(result_id, task, attempt, signature, good):
    return ReplayCandidate(
        result_manifest_id=result_id,
        work_unit_id=task,
        attempt=attempt,
        worker_id="w-" + result_id,
        structural_signature=signature,
        structural_signature_source="synthetic fixture",
        verified_good=good,
        independent_test_pass=None,
        regression_finding=False,
        security_finding=False,
        compute_units=1.0,
        human_minutes=0.0,
        observed_wall_seconds=1.0,
        verifier_signatures=(),
    )


def synthetic_report():
    """Synthetic fixture: A succeeds 3/4, B succeeds 1/3 over three work units."""
    rows = [
        candidate("a1", "t1", 1, "sig-A", True),
        candidate("a2", "t1", 2, "sig-A", True),
        candidate("a3", "t2", 1, "sig-A", True),
        candidate("a4", "t2", 2, "sig-A", False),
        candidate("b1", "t1", 1, "sig-B", True),
        candidate("b2", "t2", 1, "sig-B", False),
        candidate("b3", "t3", 1, "sig-B", False),
        candidate("a5", "t3", 1, "sig-A", True),
        candidate("a6", "t3", 2, "sig-A", False),
    ]
    diagnostics = {
        "conclusive_candidates": len(rows),
        "excluded": {
            "no_independent_verification": 2,
            "inconclusive_or_conflicting_verification": 1,
        },
    }
    report = run_replay_analysis(
        rows,
        ReplayConfig(bootstrap_trials=2, baseline_signature="sig-A"),
        normalization_diagnostics=diagnostics,
    )
    report["evidence_class"] = "synthetic_fixture"
    return report


DIGEST = "sha256:" + "0" * 64


class WilsonTests(unittest.TestCase):
    def test_hand_computed_cases(self):
        low, high = marginals.wilson_interval(1, 1)
        self.assertAlmostEqual(low, 0.2065, places=3)
        self.assertAlmostEqual(high, 1.0, places=9)
        low, high = marginals.wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.2366, places=3)
        self.assertAlmostEqual(high, 0.7634, places=3)
        low, high = marginals.wilson_interval(0, 10)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.2775, places=3)

    def test_no_trials_and_bad_counts(self):
        self.assertIsNone(marginals.wilson_interval(0, 0))
        with self.assertRaises(ValueError):
            marginals.wilson_interval(3, 2)


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = synthetic_report()
        cls.summary = marginals.summarize_report(
            cls.report, DIGEST, allow_synthetic_fixture=True
        )

    def test_per_signature_counts_and_rates(self):
        by_sig = {row["structural_signature"]: row for row in self.summary["signatures"]}
        self.assertEqual(list(by_sig), ["sig-A", "sig-B"])
        a, b = by_sig["sig-A"], by_sig["sig-B"]
        self.assertEqual(
            (a["candidates_analysed"], a["independently_verified_successes"]), (6, 4)
        )
        self.assertEqual(a["independently_verified_failures"], 2)
        self.assertAlmostEqual(a["success_rate"], 4 / 6)
        self.assertEqual(a["work_units_covered"], 3)
        self.assertEqual(
            (b["candidates_analysed"], b["independently_verified_successes"]), (3, 1)
        )
        self.assertEqual(
            a["wilson_95_interval"], list(marginals.wilson_interval(4, 6))
        )
        self.assertEqual(self.summary["candidates_analysed_total"], 9)

    def test_inconclusive_reported_not_counted(self):
        self.assertEqual(self.summary["inconclusive_excluded"]["total"], 3)
        self.assertEqual(
            self.summary["inconclusive_excluded"]["by_reason"],
            {
                "inconclusive_or_conflicting_verification": 1,
                "no_independent_verification": 2,
            },
        )
        counted = sum(r["candidates_analysed"] for r in self.summary["signatures"])
        self.assertEqual(counted, 9)

    def test_non_boolean_verdict_fails_closed(self):
        for bad in (None, "true", 1):
            report = copy.deepcopy(self.report)
            report["candidate_index"][0]["verified_good"] = bad
            with self.assertRaises(marginals.MarginalsError):
                marginals.summarize_report(report, DIGEST, allow_synthetic_fixture=True)

    def test_malformed_reports_fail_closed(self):
        def mutate(change):
            report = copy.deepcopy(self.report)
            change(report)
            return report

        cases = [
            lambda r: r.update(status="insufficient_data"),
            lambda r: r.update(experiment="other"),
            lambda r: r.pop("candidate_index"),
            lambda r: r["normalization"].update(conclusive_candidates=1),
            lambda r: r["normalization"]["excluded"].update(x=-1),
            lambda r: r["candidate_index"].append(dict(r["candidate_index"][0])),
            lambda r: r.update(signature_failure_correlations={}),
        ]
        for change in cases:
            with self.assertRaises(marginals.MarginalsError):
                marginals.summarize_report(
                    mutate(change), DIGEST, allow_synthetic_fixture=True
                )
        with self.assertRaises(marginals.MarginalsError):
            marginals.summarize_report([], DIGEST)

    def test_correlations_copied_unchanged_and_order_deterministic(self):
        self.assertEqual(
            self.summary["signature_failure_correlations"],
            self.report["signature_failure_correlations"],
        )
        self.assertEqual(self.summary["replay_config"], self.report["config"])
        again = marginals.summarize_report(
            copy.deepcopy(self.report), DIGEST, allow_synthetic_fixture=True
        )
        self.assertEqual(
            json.dumps(again, sort_keys=True), json.dumps(self.summary, sort_keys=True)
        )


class SyntheticMarkerTests(unittest.TestCase):
    def test_flagged_input_refused_without_opt_in(self):
        with self.assertRaises(marginals.SyntheticInputRefused):
            marginals.summarize_report(synthetic_report(), DIGEST)
        report = synthetic_report()
        del report["evidence_class"]
        report["synthetic"] = True
        with self.assertRaises(marginals.SyntheticInputRefused):
            marginals.summarize_report(report, DIGEST)

    def test_marker_propagated_with_opt_in(self):
        summary = marginals.summarize_report(
            synthetic_report(), DIGEST, allow_synthetic_fixture=True
        )
        self.assertEqual(summary["evidence_class"], "synthetic_fixture")

    def test_unmarked_input_is_not_labelled_synthetic_or_real(self):
        report = synthetic_report()
        del report["evidence_class"]
        summary = marginals.summarize_report(report, DIGEST)
        self.assertEqual(
            summary["evidence_class"], "replay_report_derivative_provenance_unchecked"
        )


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = marginals.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_digest_binding_and_no_writes_beside_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in"
            src.mkdir()
            report_path = src / "report.json"
            report_path.write_text(json.dumps(synthetic_report()), encoding="utf-8")
            before_bytes = report_path.read_bytes()
            digest = "sha256:" + hashlib.sha256(before_bytes).hexdigest()

            code, out, err = self.run_cli([str(report_path), "--allow-synthetic-fixture"])
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(json.loads(out)["input_report"]["sha256"], digest)
            self.assertEqual(sorted(p.name for p in src.iterdir()), ["report.json"])

            dest = Path(tmp) / "out" / "summary.json"
            code, out, _ = self.run_cli(
                [str(report_path), "--allow-synthetic-fixture", "--output", str(dest)]
            )
            self.assertEqual((code, out), (0, ""))
            self.assertEqual(
                json.loads(dest.read_text())["input_report"]["sha256"], digest
            )
            self.assertEqual(sorted(p.name for p in src.iterdir()), ["report.json"])

            # A changed report must change the bound digest.
            report = synthetic_report()
            report["candidate_index"][0]["verified_good"] = False
            report_path.write_text(json.dumps(report), encoding="utf-8")
            code, out, _ = self.run_cli([str(report_path), "--allow-synthetic-fixture"])
            self.assertNotEqual(json.loads(out)["input_report"]["sha256"], digest)

            code, _, err = self.run_cli(
                [str(report_path), "--allow-synthetic-fixture", "--output", str(report_path)]
            )
            self.assertEqual(code, 2)
            self.assertIn("must not be the input", err)

    def test_refusals_exit_2_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(synthetic_report()), encoding="utf-8")
            dest = Path(tmp) / "summary.json"
            code, out, err = self.run_cli([str(report_path), "--output", str(dest)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("synthetic", err)
            self.assertFalse(dest.exists())
            report_path.write_text("{not json", encoding="utf-8")
            code, _, _ = self.run_cli([str(report_path)])
            self.assertEqual(code, 2)
            code, _, _ = self.run_cli([str(Path(tmp) / "missing.json")])
            self.assertEqual(code, 2)


class IsolationTests(unittest.TestCase):
    def test_module_does_not_import_the_replay(self):
        source = Path(marginals.__file__).read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        self.assertFalse([name for name in imported if "r1_replay" in name])


if __name__ == "__main__":
    unittest.main()
