"""Tests for the ``idkmesh gate-audit-dependence`` product surface (#654).

Mirrors ``tests/test_gate_audit.py``'s structure. Three properties matter:

1. **Numerical parity with gate-audit's own phi.** Every pair value must
   equal ``idkmesh.gate_audit.phi`` computed directly on the same error
   vectors, so this module cannot quietly drift onto a second implementation.
2. **Binding to the same input digest.** A dependence report and a gate-audit
   report computed from the same verdict matrix must carry the identical
   ``provenance.input_digest_sha256``, since that is what lets a reader prove
   the two artifacts describe the same audited panel.
3. **The emitted report obeys its schema.** The committed example report is
   regenerated from the committed example input and compared, so the pair
   cannot drift apart.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from idkmesh import gate_audit, gate_audit_dependence  # noqa: E402

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

EXAMPLE_INPUT = REPO_ROOT / "examples" / "gate-audit" / "panel-votes.example.json"
EXAMPLE_REPORT = (
    REPO_ROOT / "examples" / "gate-audit"
    / "gate-audit-dependence-report.example.json")
SCHEMA_PATH = REPO_ROOT / "schemas" / "gate-audit-dependence-v0.1.schema.json"


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


class ComputeTests(unittest.TestCase):

    def test_every_pair_is_present_exactly_once(self):
        report = gate_audit_dependence.compute(minimal_input())
        seen = {(p["verifier_a"], p["verifier_b"]) for p in report["pairs"]}
        expected = set(itertools.combinations(["v1", "v2", "v3"], 2))
        self.assertEqual(seen, expected)
        self.assertEqual(len(report["pairs"]), len(expected))

    def test_pair_order_is_sorted_independent_of_input_order(self):
        forward = gate_audit_dependence.compute(minimal_input())
        data = minimal_input()
        data["verifiers"] = list(reversed(data["verifiers"]))
        reversed_input = gate_audit_dependence.compute(data)
        self.assertEqual(forward["verifier_ids"], sorted(["v1", "v2", "v3"]))
        self.assertEqual(
            [(p["verifier_a"], p["verifier_b"]) for p in forward["pairs"]],
            [(p["verifier_a"], p["verifier_b"])
             for p in reversed_input["pairs"]])

    def test_phi_error_matches_gate_audit_phi_directly(self):
        data = minimal_input()
        truth = {c["id"]: c["ground_truth"] for c in data["candidates"]}
        error_vectors = {
            ver["id"]: [
                0 if ver["verdicts"][c["id"]] == truth[c["id"]] else 1
                for c in data["candidates"]
            ]
            for ver in data["verifiers"]
        }
        report = gate_audit_dependence.compute(data)
        for pair in report["pairs"]:
            expected = gate_audit.phi(
                error_vectors[pair["verifier_a"]],
                error_vectors[pair["verifier_b"]])
            if math.isnan(expected):
                self.assertFalse(pair["measurable"])
                self.assertIsNone(pair["phi_error"])
            else:
                self.assertTrue(pair["measurable"])
                self.assertAlmostEqual(pair["phi_error"], expected, places=12)

    def test_only_non_probe_candidates_feed_the_pairwise_statistics(self):
        # A probe that only one verifier gets right must not move phi_error;
        # gate-audit's headline panel statistics ignore probes too, and the
        # two artifacts must keep describing the same audited population.
        data = minimal_input()
        without_probe = gate_audit_dependence.compute(data)

        data["candidates"].append(
            {"id": "p1", "ground_truth": "reject", "probe": True})
        for ver in data["verifiers"]:
            ver["verdicts"]["p1"] = "reject"
        # Flip one verifier's probe verdict so a naive implementation that
        # folded probes into the error vectors would change phi_error.
        data["verifiers"][0]["verdicts"]["p1"] = "accept"
        with_probe = gate_audit_dependence.compute(data)

        self.assertEqual(with_probe["non_probe_candidate_count"],
                          without_probe["non_probe_candidate_count"])
        self.assertEqual(with_probe["pairs"], without_probe["pairs"])

    def test_zero_variance_pair_is_unmeasurable_not_zero(self):
        data = minimal_input()
        # v1 becomes a perfect verifier: zero error variance.
        data["verifiers"][0]["verdicts"] = {
            c["id"]: c["ground_truth"] for c in data["candidates"]
        }
        report = gate_audit_dependence.compute(data)
        v1_pairs = [p for p in report["pairs"]
                    if "v1" in (p["verifier_a"], p["verifier_b"])]
        self.assertTrue(v1_pairs)
        for pair in v1_pairs:
            self.assertFalse(pair["measurable"])
            self.assertIsNone(pair["phi_error"])
        self.assertIn(
            "recorded as unmeasurable, not as independent",
            " ".join(report["warnings"]))

    def test_joint_and_marginal_error_counts(self):
        data = minimal_input()
        report = gate_audit_dependence.compute(data)
        by_pair = {(p["verifier_a"], p["verifier_b"]): p
                   for p in report["pairs"]}
        # v1 errs on c3 only; v2 errs on c1... wait, compute directly instead
        # of restating ground truth by hand for every candidate:
        truth = {c["id"]: c["ground_truth"] for c in data["candidates"]}
        errors = {
            ver["id"]: {
                c["id"]
                for c in data["candidates"]
                if ver["verdicts"][c["id"]] != truth[c["id"]]
            }
            for ver in data["verifiers"]
        }
        for (a, b), pair in by_pair.items():
            self.assertEqual(
                pair["joint_error_count"], len(errors[a] & errors[b]))
            self.assertEqual(pair["a_error_count"], len(errors[a]))
            self.assertEqual(pair["b_error_count"], len(errors[b]))

    def test_single_verifier_has_no_pairs_and_warns(self):
        data = minimal_input()
        data["verifiers"] = data["verifiers"][:1]
        report = gate_audit_dependence.compute(data)
        self.assertEqual(report["pairs"], [])
        self.assertIn("fewer than two verifiers", " ".join(report["warnings"]))

    def test_report_shape(self):
        report = gate_audit_dependence.compute(minimal_input())
        self.assertEqual(report["schema"], "gate-audit-dependence-v0.1")
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(report["gate_id"], "test-gate")
        self.assertEqual(report["evidence_class"], "synthetic")
        self.assertEqual(report["verifier_ids"], ["v1", "v2", "v3"])
        self.assertIn("input_digest_sha256", report["provenance"])
        self.assertEqual(
            report["provenance"]["tool"], "idkmesh gate-audit-dependence")

    def test_never_emits_a_per_verifier_aggregate_field(self):
        # #654: this artifact must stay pairwise-only, never a global
        # per-verifier reputation/independence score.
        report = gate_audit_dependence.compute(minimal_input())
        self.assertNotIn("verifiers", report)
        for verifier_id in report["verifier_ids"]:
            self.assertNotIsInstance(verifier_id, dict)


class InputDigestBindingTests(unittest.TestCase):
    """The load-bearing property: the two artifacts prove the same input."""

    def test_digest_matches_gate_audit_report_for_the_same_input(self):
        data = minimal_input()
        dependence_report = gate_audit_dependence.compute(data)
        audit_report = gate_audit.audit(data)
        self.assertEqual(
            dependence_report["provenance"]["input_digest_sha256"],
            audit_report["provenance"]["input_digest_sha256"])

    def test_digest_changes_when_a_verdict_changes(self):
        data = minimal_input()
        base = gate_audit_dependence.compute(data)["provenance"][
            "input_digest_sha256"]
        data["verifiers"][0]["verdicts"]["c1"] = "reject"
        changed = gate_audit_dependence.compute(data)["provenance"][
            "input_digest_sha256"]
        self.assertNotEqual(base, changed)


class ContractTests(unittest.TestCase):
    """The same strict verdict-matrix contract gate-audit enforces."""

    def test_missing_evidence_class_is_refused(self):
        data = minimal_input()
        del data["evidence_class"]
        with self.assertRaises(gate_audit_dependence.GateAuditInputError):
            gate_audit_dependence.dependence_text(json.dumps(data))

    def test_incomplete_verdict_matrix_is_refused(self):
        data = minimal_input()
        del data["verifiers"][0]["verdicts"]["c4"]
        with self.assertRaises(gate_audit_dependence.GateAuditInputError):
            gate_audit_dependence.dependence_text(json.dumps(data))


class CommittedExampleTests(unittest.TestCase):
    """The example pair in examples/gate-audit/ cannot drift apart."""

    def test_example_report_matches_regenerated_output(self):
        regenerated = gate_audit_dependence.dependence_file(EXAMPLE_INPUT)
        committed = json.loads(EXAMPLE_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(regenerated, committed)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_example_report_matches_its_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        committed = json.loads(EXAMPLE_REPORT.read_text(encoding="utf-8"))
        jsonschema.validate(committed, schema)

    def test_example_shares_input_digest_with_gate_audit_report(self):
        dependence = json.loads(EXAMPLE_REPORT.read_text(encoding="utf-8"))
        audit_report_path = (
            REPO_ROOT / "examples" / "gate-audit"
            / "gate-audit-report.example.json")
        audit_report = json.loads(
            audit_report_path.read_text(encoding="utf-8"))
        self.assertEqual(
            dependence["provenance"]["input_digest_sha256"],
            audit_report["provenance"]["input_digest_sha256"])


class RenderJsonTests(unittest.TestCase):

    def test_render_json_is_strict_no_bare_nan(self):
        report = gate_audit_dependence.compute(minimal_input())
        rendered = gate_audit_dependence.render_json(report)
        # json.loads with default parse_constant would accept a bare NaN;
        # round-tripping through the standard library's strict decoder here
        # would not catch it, so assert on the text directly.
        self.assertNotIn("NaN", rendered)
        self.assertEqual(json.loads(rendered), report)

    def test_render_json_pretty_is_still_valid_json(self):
        report = gate_audit_dependence.compute(minimal_input())
        rendered = gate_audit_dependence.render_json(report, pretty=True)
        self.assertEqual(json.loads(rendered), report)


class CliTests(unittest.TestCase):
    """The packaged CLI surface, exercised as a subprocess like a user would."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            cwd=REPO_ROOT, capture_output=True, text=True)

    def test_cli_matches_the_committed_example(self):
        proc = self.run_cli("gate-audit-dependence", str(EXAMPLE_INPUT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        committed = json.loads(EXAMPLE_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(proc.stdout), committed)

    def test_cli_missing_input_file(self):
        proc = self.run_cli("gate-audit-dependence", "/no/such/file.json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("input file not found", proc.stderr)

    def test_cli_out_refuses_to_overwrite_the_input(self):
        proc = self.run_cli(
            "gate-audit-dependence", str(EXAMPLE_INPUT),
            "--out", str(EXAMPLE_INPUT))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("is the input file", proc.stderr)

    def test_cli_help_lists_the_command(self):
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("gate-audit-dependence", proc.stdout)


if __name__ == "__main__":
    unittest.main()
