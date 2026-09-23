"""Tests for marginal verifier evidence analysis (issue #693)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from idkmesh import gate_audit, marginal_evidence  # noqa: E402

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

SCHEMA_PATH = REPO_ROOT / "schemas" / "marginal-evidence-report-v0.1.schema.json"


def _flip(verdict: str) -> str:
    return "reject" if verdict == "accept" else "accept"


def make_matrix(
    *,
    count: int = 12,
    quorum: float = 0.5,
    error_sets: dict[str, set[int]] | None = None,
    probes: int = 0,
) -> dict:
    """Build a complete deterministic verdict matrix from verifier error sets."""
    error_sets = error_sets or {
        "v1": {0, 1, 2},
        "v2": {0, 1, 2},
        "v3": {3, 4, 5},
        "v4": {6, 7, 8},
        "v5": {0, 4, 8},
    }
    candidates = []
    for i in range(count):
        candidates.append(
            {
                "id": f"c{i:02d}",
                "ground_truth": "accept" if i % 2 == 0 else "reject",
            }
        )
    for i in range(probes):
        candidates.append(
            {
                "id": f"p{i:02d}",
                "ground_truth": "reject",
                "probe": True,
                "probe_kind": "seeded-defect",
            }
        )

    verifiers = []
    for verifier_id, wrong_rows in error_sets.items():
        verdicts = {}
        for i in range(count):
            truth = candidates[i]["ground_truth"]
            verdicts[f"c{i:02d}"] = _flip(truth) if i in wrong_rows else truth
        for i in range(probes):
            # Different deterministic probe behavior per verifier.
            verdicts[f"p{i:02d}"] = (
                "accept" if (i + len(verifier_id)) % 2 == 0 else "reject"
            )
        verifiers.append({"id": verifier_id, "verdicts": verdicts})

    return {
        "gate_id": "marginal-test",
        "evidence_class": "synthetic",
        "quorum": quorum,
        "candidates": candidates,
        "verifiers": verifiers,
    }


class InputContractTests(unittest.TestCase):
    def test_requires_known_current_verifier(self):
        with self.assertRaises(marginal_evidence.MarginalEvidenceInputError) as ctx:
            marginal_evidence.analyze(
                make_matrix(),
                current_verifier_ids=["ghost"],
            )
        self.assertIn("unknown verifier", str(ctx.exception))

    def test_rejects_overlap_between_current_and_candidate(self):
        with self.assertRaises(marginal_evidence.MarginalEvidenceInputError) as ctx:
            marginal_evidence.analyze(
                make_matrix(),
                current_verifier_ids=["v1", "v2"],
                candidate_verifier_ids=["v2", "v3"],
            )
        self.assertIn("both current and candidate", str(ctx.exception))

    def test_candidate_defaults_to_all_remaining_in_source_order(self):
        report = marginal_evidence.analyze(
            make_matrix(),
            current_verifier_ids=["v2", "v1"],
        )
        # Both current and candidate ids are canonicalized to source order so
        # equivalent CLI argument orderings have identical provenance.
        self.assertEqual(
            report["analysis"]["current_verifier_ids"], ["v1", "v2"]
        )
        self.assertEqual(
            [row["id"] for row in report["candidates"]],
            ["v3", "v4", "v5"],
        )

    def test_current_panel_argument_order_does_not_change_analysis_digest(self):
        data = make_matrix()
        first = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["v3"],
        )
        second = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v2", "v1"],
            candidate_verifier_ids=["v3"],
        )
        self.assertEqual(
            first["provenance"]["analysis_digest_sha256"],
            second["provenance"]["analysis_digest_sha256"],
        )
        self.assertEqual(first["current_panel"], second["current_panel"])

    def test_no_remaining_candidate_is_refused(self):
        data = make_matrix(error_sets={"v1": {0, 1}})
        with self.assertRaises(marginal_evidence.MarginalEvidenceInputError) as ctx:
            marginal_evidence.analyze(data, current_verifier_ids=["v1"])
        self.assertIn("no candidate verifiers remain", str(ctx.exception))

    def test_duplicate_current_ids_are_refused(self):
        with self.assertRaises(marginal_evidence.MarginalEvidenceInputError):
            marginal_evidence.analyze(
                make_matrix(),
                current_verifier_ids=["v1", "v1"],
            )

    def test_shared_gate_audit_parser_preserves_source_on_audit_time_error(self):
        text = json.dumps(make_matrix())
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_text(
                text,
                source="matrix.json",
                bootstrap={"replicates": 99, "seed": 0},
            )
        self.assertIn("matrix.json:", str(ctx.exception))
        self.assertIn("100", str(ctx.exception))

    def test_strict_text_parser_rejects_duplicate_json_keys(self):
        text = (
            '{"gate_id":"x","gate_id":"y","evidence_class":"synthetic",'
            '"candidates":[{"id":"c1","ground_truth":"accept"},'
            '{"id":"c2","ground_truth":"reject"}],'
            '"verifiers":[{"id":"v1","verdicts":{"c1":"accept","c2":"reject"}},'
            '{"id":"v2","verdicts":{"c1":"accept","c2":"reject"}}]}'
        )
        with self.assertRaises(marginal_evidence.MarginalEvidenceInputError) as ctx:
            marginal_evidence.analyze_text(
                text,
                current_verifier_ids=["v1"],
                candidate_verifier_ids=["v2"],
            )
        self.assertIn("duplicate JSON key", str(ctx.exception))


class ContributionSemanticsTests(unittest.TestCase):
    def test_report_is_diagnostic_only_and_never_selects_candidate(self):
        report = marginal_evidence.analyze(
            make_matrix(),
            current_verifier_ids=["v1", "v2", "v3"],
            candidate_verifier_ids=["v4", "v5"],
        )
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertNotIn("selected_verifier_id", report)
        self.assertNotIn("ranking", report)

    def test_identical_error_candidate_has_correlation_one(self):
        data = make_matrix(
            error_sets={
                "v1": {0, 1, 2},
                "v2": {0, 1, 2},
                "clone": {0, 1, 2},
            }
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["clone"],
        )
        row = report["candidates"][0]
        self.assertAlmostEqual(
            row["mean_error_correlation_with_current_panel"], 1.0, places=12
        )
        self.assertEqual(
            [p["error_correlation"] for p in row["pairwise_error_correlations"]],
            [1.0, 1.0],
        )

    def test_zero_variance_candidate_correlation_is_explicitly_unresolved(self):
        data = make_matrix(
            error_sets={
                "v1": {0, 1, 2},
                "v2": {3, 4, 5},
                "perfect": set(),
            }
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["perfect"],
        )
        row = report["candidates"][0]
        self.assertIsNone(row["mean_error_correlation_with_current_panel"])
        self.assertIn(
            "candidate_error_correlation_unmeasurable",
            row["unresolved_reasons"],
        )
        self.assertTrue(
            all(
                pair["error_correlation"] is None
                for pair in row["pairwise_error_correlations"]
            )
        )

    def test_transition_counts_distinguish_helpful_and_harmful_flips(self):
        # Four-member current panel has threshold 3 at quorum .5. Adding a
        # fifth keeps threshold 3, so one extra accept can flip a 2-2 reject.
        data = make_matrix(
            count=8,
            error_sets={
                # c0 truth accept: 2 accept / 2 reject -> current rejects wrong.
                # c1 truth reject: 2 accept / 2 reject -> current rejects right.
                "v1": {0, 1},
                "v2": {0, 1},
                "v3": set(),
                "v4": set(),
                # Candidate accepts both c0 and c1: fixes c0, breaks c1.
                "candidate": {1},
            },
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2", "v3", "v4"],
            candidate_verifier_ids=["candidate"],
        )
        counts = report["candidates"][0]["transition_counts"]
        self.assertGreaterEqual(counts["panel_decisions_changed_to_correct"], 1)
        self.assertGreaterEqual(counts["panel_decisions_changed_to_wrong"], 1)

    def test_candidate_that_worsens_gate_gets_warning(self):
        # Three perfect-ish current voters accept good rows by majority. Adding
        # a fourth bad voter can turn 2-1 accept into a 2-2 reject because ties
        # reject at quorum .5.
        data = make_matrix(
            count=10,
            error_sets={
                "v1": {0},
                "v2": {2},
                "v3": {4},
                "bad": {0, 2, 4, 6, 8},
            },
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2", "v3"],
            candidate_verifier_ids=["bad"],
        )
        row = report["candidates"][0]
        self.assertLess(row["panel_error_delta"], 0.0)
        self.assertTrue(
            any("increased panel error" in warning for warning in row["warnings"])
        )

    def test_probes_are_separate_from_headline_delta(self):
        base = make_matrix(probes=0)
        probed = make_matrix(probes=3)
        kwargs = {
            "current_verifier_ids": ["v1", "v2", "v3"],
            "candidate_verifier_ids": ["v4"],
        }
        base_report = marginal_evidence.analyze(base, **kwargs)
        probed_report = marginal_evidence.analyze(probed, **kwargs)
        self.assertEqual(
            base_report["candidates"][0]["panel_error_delta"],
            probed_report["candidates"][0]["panel_error_delta"],
        )
        self.assertIsNone(base_report["candidates"][0]["probe_effect"])
        self.assertIsNotNone(probed_report["candidates"][0]["probe_effect"])

    def test_censored_effective_vote_delta_is_not_subtracted(self):
        data = make_matrix(
            count=30,
            error_sets={
                "v1": set(),
                "v2": set(),
                "candidate": set(),
            },
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["candidate"],
        )
        row = report["candidates"][0]
        self.assertIsNone(row["delta_effective_votes"])
        self.assertTrue(row["current_effective_votes_censored"])
        self.assertTrue(row["augmented_effective_votes_censored"])
        self.assertIn(
            "current_effective_votes_censored", row["unresolved_reasons"]
        )


class FiniteSampleTests(unittest.TestCase):
    def test_less_than_five_rows_is_point_only_and_unresolved(self):
        data = make_matrix(count=4)
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["v3"],
            bootstrap={"replicates": 100, "seed": 7},
        )
        row = report["candidates"][0]
        self.assertEqual(row["status"], "unresolved")
        self.assertIn(
            "insufficient_non_probe_candidates_for_inference",
            row["unresolved_reasons"],
        )
        self.assertFalse(row["uncertainty"]["sufficient_for_inference"])

    def test_bootstrap_is_deterministic_for_same_seed(self):
        data = make_matrix(count=20)
        kwargs = {
            "current_verifier_ids": ["v1", "v2", "v3"],
            "candidate_verifier_ids": ["v4"],
            "bootstrap": {
                "replicates": 120,
                "seed": 41,
                "confidence_level": 0.9,
            },
        }
        first = marginal_evidence.analyze(data, **kwargs)
        second = marginal_evidence.analyze(data, **kwargs)
        self.assertEqual(
            first["candidates"][0]["uncertainty"],
            second["candidates"][0]["uncertainty"],
        )

    def test_bootstrap_resamples_current_and_augmented_panels_as_paired_rows(self):
        data = make_matrix(count=18)
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2", "v3"],
            candidate_verifier_ids=["v4"],
            bootstrap={"replicates": 100, "seed": 3},
        )
        section = report["candidates"][0]["uncertainty"]["panel_error_delta"]
        self.assertEqual(
            section["replicates_used"] + section["replicates_undefined"], 100
        )
        self.assertIsNotNone(section["ci_low"])
        self.assertIsNotNone(section["ci_high"])

    def test_identical_candidates_share_the_same_bootstrap_draws(self):
        data = make_matrix(
            count=20,
            error_sets={
                "v1": {0, 1, 2, 3},
                "v2": {0, 1, 4, 5},
                "candidate-a": {2, 6, 10},
                "candidate-b": {2, 6, 10},
            },
        )
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["candidate-a", "candidate-b"],
            bootstrap={"replicates": 120, "seed": 29},
        )
        first, second = report["candidates"]
        self.assertEqual(first["uncertainty"], second["uncertainty"])
        self.assertEqual(first["panel_error_delta"], second["panel_error_delta"])
        self.assertEqual(first["delta_effective_votes"], second["delta_effective_votes"])

    def test_bad_bootstrap_parameters_are_refused(self):
        for params in (
            {"replicates": 99, "seed": 0},
            {"replicates": 100, "seed": True},
            {"replicates": 100, "seed": 0, "confidence_level": 1.0},
            {"replicates": 100, "seed": 0, "extra": 1},
        ):
            with self.subTest(params=params):
                with self.assertRaises(
                    marginal_evidence.MarginalEvidenceInputError
                ):
                    marginal_evidence.analyze(
                        make_matrix(),
                        current_verifier_ids=["v1", "v2"],
                        candidate_verifier_ids=["v3"],
                        bootstrap=params,
                    )


class ExampleFixtureTests(unittest.TestCase):
    INPUT = REPO_ROOT / "examples" / "gate-audit" / "panel-votes.example.json"
    REPORT = (
        REPO_ROOT / "examples" / "gate-audit"
        / "marginal-evidence-report.example.json"
    )

    def test_committed_example_regenerates_exactly(self):
        data = json.loads(self.INPUT.read_text(encoding="utf-8"))
        expected = json.loads(self.REPORT.read_text(encoding="utf-8"))
        actual = marginal_evidence.analyze(
            data,
            current_verifier_ids=["reviewer-a", "reviewer-b"],
            candidate_verifier_ids=["reviewer-d"],
        )
        self.assertEqual(actual, expected)


class ProvenanceTests(unittest.TestCase):
    def test_analysis_digest_changes_when_panel_selection_changes(self):
        data = make_matrix()
        first = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["v3"],
        )
        second = marginal_evidence.analyze(
            data,
            current_verifier_ids=["v1", "v3"],
            candidate_verifier_ids=["v2"],
        )
        self.assertEqual(
            first["provenance"]["input_digest_sha256"],
            second["provenance"]["input_digest_sha256"],
        )
        self.assertNotEqual(
            first["provenance"]["analysis_digest_sha256"],
            second["provenance"]["analysis_digest_sha256"],
        )

    def test_render_json_is_strict_json(self):
        report = marginal_evidence.analyze(
            make_matrix(),
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["v3"],
        )
        rendered = marginal_evidence.render_json(report, pretty=True)
        self.assertEqual(json.loads(rendered)["schema"], marginal_evidence.SCHEMA_ID)


class SchemaTests(unittest.TestCase):
    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_report_validates_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = marginal_evidence.analyze(
            make_matrix(probes=2),
            current_verifier_ids=["v1", "v2", "v3"],
            candidate_verifier_ids=["v4", "v5"],
            bootstrap={"replicates": 100, "seed": 11},
        )
        jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_measured_status_with_unresolved_reason(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = marginal_evidence.analyze(
            make_matrix(),
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["v3"],
        )
        row = report["candidates"][0]
        row["status"] = "measured"
        row["unresolved_reasons"] = ["contradiction"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_numeric_delta_when_effective_votes_are_censored(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = marginal_evidence.analyze(
            make_matrix(
                count=30,
                error_sets={
                    "v1": set(),
                    "v2": set(),
                    "candidate": set(),
                },
            ),
            current_verifier_ids=["v1", "v2"],
            candidate_verifier_ids=["candidate"],
        )
        row = report["candidates"][0]
        self.assertTrue(row["current_effective_votes_censored"])
        row["delta_effective_votes"] = 0.0
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)



class CliTests(unittest.TestCase):
    EXAMPLE_INPUT = (
        REPO_ROOT / "examples" / "gate-audit" / "panel-votes.example.json"
    )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        )

    def test_gate_marginal_emits_report(self):
        proc = self.run_cli(
            "gate-marginal",
            str(self.EXAMPLE_INPUT),
            "--current", "reviewer-a",
            "--current", "reviewer-b",
            "--candidate", "reviewer-d",
            "--pretty",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema"], marginal_evidence.SCHEMA_ID)
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual([row["id"] for row in report["candidates"]], ["reviewer-d"])

    def test_gate_marginal_bootstrap_options_require_flag(self):
        proc = self.run_cli(
            "gate-marginal",
            str(self.EXAMPLE_INPUT),
            "--current", "reviewer-a",
            "--bootstrap-seed", "5",
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("require --bootstrap", proc.stderr)

    def test_gate_marginal_refuses_output_over_input(self):
        proc = self.run_cli(
            "gate-marginal",
            str(self.EXAMPLE_INPUT),
            "--current", "reviewer-a",
            "--out", str(self.EXAMPLE_INPUT),
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("would overwrite the verdict matrix", proc.stderr)


if __name__ == "__main__":
    unittest.main()
