"""Tests for the ``idkmesh gate-audit`` product surface.

Three properties are load-bearing and each gets its own coverage:

1. **Parity with the research record.** The packaged math must equal
   ``sim/e015_analyze.py`` / ``sim/e016_analyze.py`` on the same inputs, so
   product numbers stay comparable with the published E015/E017 results.
2. **The input contract is strict.** A missing verdict is refused, never
   imputed, because imputation changes the correlation structure the audit
   exists to measure.
3. **The emitted report obeys its schema.** The committed example report is
   regenerated from the committed example input and compared, so the pair
   cannot drift apart.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from idkmesh import gate_audit  # noqa: E402

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

EXAMPLE_INPUT = REPO_ROOT / "examples" / "gate-audit" / "panel-votes.example.json"
EXAMPLE_REPORT = (
    REPO_ROOT / "examples" / "gate-audit" / "gate-audit-report.example.json")
SCHEMA_PATH = REPO_ROOT / "schemas" / "gate-audit-report-v0.1.schema.json"


def _load_sim(name: str):
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "sim" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


class ParityWithResearchRecordTests(unittest.TestCase):
    """The packaged math equals the sim modules it was cut from."""

    @classmethod
    def setUpClass(cls):
        cls.e015 = _load_sim("e015_analyze")
        cls.e016 = _load_sim("e016_analyze")

    def test_effective_n_matches_e015(self):
        for err, acc in [(0.2083, 0.7956), (0.05, 0.9), (0.001, 0.8),
                         (0.45, 0.6), (0.3, 0.51)]:
            with self.subTest(err=err, acc=acc):
                ours = gate_audit.effective_n(err, acc, 0.5)
                theirs = self.e015.effective_n(err, acc, 0.5)
                self.assertAlmostEqual(ours, theirs, places=9)

    def test_effective_n_ceiling_matches_e015(self):
        for acc, rho in [(0.9, 0.125), (0.7956, 0.5873), (0.8, 0.05),
                         (0.95, 0.3)]:
            with self.subTest(acc=acc, rho=rho):
                ours = gate_audit.effective_n_ceiling(acc, rho)
                theirs = self.e015.effective_n_ceiling(acc, rho)
                self.assertAlmostEqual(ours, theirs, places=9)

    def test_heuristic_matches_e015(self):
        self.assertAlmostEqual(
            gate_audit.heuristic_effective_n(25, 0.5873),
            self.e015.heuristic_effective_n(25, 0.5873), places=12)

    def test_phi_matches_e016(self):
        x = [0, 1, 1, 0, 1, 0, 0, 1]
        y = [0, 1, 0, 0, 1, 1, 0, 1]
        self.assertAlmostEqual(
            gate_audit.phi(x, y), self.e016.phi(x, y), places=12)

    def test_phi_zero_variance_is_nan(self):
        self.assertTrue(math.isnan(gate_audit.phi([0, 0, 0], [0, 1, 0])))

    def test_e015_documented_optimism_case_reproduces(self):
        # E015's headline: at p=0.90, rho=0.125 the heuristic promises ~8
        # effective verifiers against a ceiling of ~4.59.
        ceiling = gate_audit.effective_n_ceiling(0.90, 0.125)
        self.assertAlmostEqual(ceiling, 4.59, delta=0.05)
        # The heuristic converges to 1/rho = 8 regardless of accuracy, sailing
        # past the real ceiling.
        self.assertGreater(gate_audit.heuristic_effective_n(1001, 0.125), ceiling)


class InputContractTests(unittest.TestCase):
    def assert_refused(self, data, fragment):
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit(copy.deepcopy(data))
        self.assertIn(fragment, str(ctx.exception))

    def test_valid_minimal_input_audits(self):
        report = gate_audit.audit(minimal_input())
        self.assertEqual(report["schema"], "gate-audit-report-v0.1")
        self.assertEqual(report["panel"]["nominal_votes"], 3)

    def test_missing_evidence_class_is_refused(self):
        data = minimal_input()
        del data["evidence_class"]
        self.assert_refused(data, "evidence_class")

    def test_missing_verdict_is_refused_not_imputed(self):
        data = minimal_input()
        del data["verifiers"][0]["verdicts"]["c4"]
        self.assert_refused(data, "missing verdicts")

    def test_unknown_candidate_verdict_is_refused(self):
        data = minimal_input()
        data["verifiers"][0]["verdicts"]["ghost"] = "accept"
        self.assert_refused(data, "unknown candidates")

    def test_probe_with_accept_ground_truth_is_refused(self):
        data = minimal_input()
        data["candidates"].append(
            {"id": "p1", "ground_truth": "accept", "probe": True})
        self.assert_refused(data, "KNOWN-BAD")

    def test_duplicate_ids_are_refused(self):
        data = minimal_input()
        data["candidates"].append(dict(data["candidates"][0]))
        self.assert_refused(data, "duplicate candidate id")

    def test_fewer_than_two_non_probe_candidates_is_refused(self):
        data = minimal_input()
        for cand in data["candidates"][1:]:
            cand["probe"] = True
            cand["ground_truth"] = "reject"
        for ver in data["verifiers"]:
            for cid in ("c2", "c3", "c4"):
                ver["verdicts"][cid] = "reject"
        self.assert_refused(data, "at least two non-probe")


class AuditSemanticsTests(unittest.TestCase):
    def test_perfectly_correlated_panel_collapses_to_one_vote(self):
        # Three clones of one verifier: measured effective votes must be ~1,
        # which is the E017 phenomenon the product exists to surface.
        verdicts = {"c1": "accept", "c2": "reject", "c3": "reject",
                    "c4": "accept", "c5": "accept", "c6": "reject"}
        data = {
            "gate_id": "clones",
            "evidence_class": "synthetic",
            "candidates": [
                {"id": "c1", "ground_truth": "accept"},
                {"id": "c2", "ground_truth": "accept"},
                {"id": "c3", "ground_truth": "reject"},
                {"id": "c4", "ground_truth": "reject"},
                {"id": "c5", "ground_truth": "accept"},
                {"id": "c6", "ground_truth": "reject"},
            ],
            "verifiers": [
                {"id": f"v{i}", "verdicts": dict(verdicts)} for i in range(3)
            ],
        }
        report = gate_audit.audit(data)
        panel = report["panel"]
        self.assertAlmostEqual(
            panel["mean_pairwise_error_correlation"], 1.0, places=12)
        self.assertAlmostEqual(panel["effective_votes"], 1.0, places=9)
        # Panel error equals the single verifier's error rate.
        self.assertAlmostEqual(panel["error"], 1 / 3, places=12)

    def test_probe_breach_rate_counts_majority_accepts_only(self):
        data = minimal_input()
        data["candidates"] += [
            {"id": "p1", "ground_truth": "reject", "probe": True,
             "probe_kind": "seeded-defect"},
            {"id": "p2", "ground_truth": "reject", "probe": True,
             "probe_kind": "seeded-defect"},
        ]
        # p1 accepted by 2/3 (breach), p2 accepted by 1/3 (held).
        votes = {"v1": {"p1": "accept", "p2": "accept"},
                 "v2": {"p1": "accept", "p2": "reject"},
                 "v3": {"p1": "reject", "p2": "reject"}}
        for ver in data["verifiers"]:
            ver["verdicts"].update(votes[ver["id"]])
        report = gate_audit.audit(data)
        self.assertEqual(report["probes"]["total"], 2)
        self.assertEqual(report["probes"]["breached"], 1)
        self.assertEqual(
            report["probes"]["by_kind"]["seeded-defect"],
            {"total": 2, "breached": 1})

    def test_probes_do_not_move_headline_panel_statistics(self):
        base = gate_audit.audit(minimal_input())
        with_probe = minimal_input()
        with_probe["candidates"].append(
            {"id": "p1", "ground_truth": "reject", "probe": True})
        for ver in with_probe["verifiers"]:
            ver["verdicts"]["p1"] = "accept"
        probed = gate_audit.audit(with_probe)
        self.assertEqual(base["panel"]["error"], probed["panel"]["error"])
        self.assertEqual(
            base["panel"]["mean_verifier_accuracy"],
            probed["panel"]["mean_verifier_accuracy"])

    def test_non_discriminating_panel_reports_null_effective_votes(self):
        data = minimal_input()
        # Invert every verdict so each verifier is mostly wrong.
        for ver in data["verifiers"]:
            for cid, verdict in ver["verdicts"].items():
                ver["verdicts"][cid] = (
                    "accept" if verdict == "reject" else "reject")
        report = gate_audit.audit(data)
        self.assertIsNone(report["panel"]["effective_votes"])
        self.assertTrue(
            any("does not discriminate" in w for w in report["warnings"]))

    def test_report_is_deterministic_and_digest_bound(self):
        a = gate_audit.audit(minimal_input())
        b = gate_audit.audit(minimal_input())
        self.assertEqual(a, b)
        changed = minimal_input(gate_id="other-gate")
        c = gate_audit.audit(changed)
        self.assertNotEqual(
            a["provenance"]["input_digest_sha256"],
            c["provenance"]["input_digest_sha256"])


class CommittedExampleTests(unittest.TestCase):
    """The committed example pair regenerates exactly and passes the schema."""

    def test_report_example_regenerates_from_input_example(self):
        report = gate_audit.audit_file(EXAMPLE_INPUT)
        committed = json.loads(EXAMPLE_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report, committed)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_generated_report_validates_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = gate_audit.audit_file(EXAMPLE_INPUT)
        jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_minimal_report_validates_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(gate_audit.audit(minimal_input()), schema)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        )

    def test_cli_emits_report_and_markdown(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            md = Path(tmp) / "report.md"
            proc = self.run_cli(
                "gate-audit", str(EXAMPLE_INPUT),
                "--out", str(out), "--markdown", str(md), "--pretty")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "gate-audit-report-v0.1")
            text = md.read_text(encoding="utf-8")
            self.assertIn("effective independent votes", text)
            self.assertIn("not acceptance authority", text)

    def test_cli_refuses_contract_violation_with_exit_2(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            data = minimal_input()
            del data["evidence_class"]
            bad.write_text(json.dumps(data), encoding="utf-8")
            proc = self.run_cli("gate-audit", str(bad))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("evidence_class", proc.stderr)

    def test_cli_missing_file_exits_2(self):
        proc = self.run_cli("gate-audit", "/nonexistent/votes.json")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
