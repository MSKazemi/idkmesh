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


class ReportSerializationTests(unittest.TestCase):
    """A report must be readable by a JSON parser that is not Python's."""

    @staticmethod
    def _non_discriminating_panel():
        """A panel below chance whose error vectors still correlate.

        Both conditions matter: mean accuracy <= 0.5 makes the effective-vote
        ceiling undefined, and a measurable correlation is what causes the
        ceiling to be computed at all.
        """
        candidates = [
            {"id": f"c{i}", "ground_truth": "accept" if i % 2 else "reject"}
            for i in range(8)
        ]

        def verdicts(flipped):
            return {
                cand["id"]: (
                    cand["ground_truth"] if i not in flipped
                    else ("reject" if cand["ground_truth"] == "accept"
                          else "accept"))
                for i, cand in enumerate(candidates)
            }

        return {
            "gate_id": "below-chance-panel",
            "evidence_class": "synthetic",
            "candidates": candidates,
            "verifiers": [
                {"id": "v1", "verdicts": verdicts({0, 1, 2, 3, 4})},
                {"id": "v2", "verdicts": verdicts({0, 1, 2, 3, 5})},
            ],
        }

    def test_undefined_ceiling_is_null_not_nan(self):
        # effective_n_ceiling returns NaN for a panel that does not
        # discriminate. Emitted verbatim it produced a bare NaN token: not JSON
        # anywhere outside Python, and invalid against the v0.1 schema.
        report = gate_audit.audit(self._non_discriminating_panel())
        self.assertLessEqual(report["panel"]["mean_verifier_accuracy"], 0.5)
        self.assertIsNotNone(
            report["panel"]["mean_pairwise_error_correlation"])
        self.assertIsNone(report["panel"]["effective_votes_ceiling"])

    def test_report_of_non_discriminating_panel_is_strict_json(self):
        rendered = gate_audit.render_json(
            gate_audit.audit(self._non_discriminating_panel()))

        def reject(token):
            raise AssertionError(f"report contains the non-JSON token {token}")

        json.loads(rendered, parse_constant=reject)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_non_discriminating_report_validates_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(
            gate_audit.audit(self._non_discriminating_panel()), schema)

    def test_render_json_refuses_non_finite_numbers(self):
        # The guard is what keeps a future non-finite value from silently
        # becoming a report nothing else can parse.
        with self.assertRaises(ValueError):
            gate_audit.render_json({"panel": {"effective_votes": math.nan}})


class MalformedInputDiagnosticsTests(unittest.TestCase):
    """Every refusal must name what is wrong and where, not just that it is."""

    def assert_refused(self, data, fragment):
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit(copy.deepcopy(data))
        self.assertIn(fragment, str(ctx.exception))

    def test_absent_key_is_reported_as_missing(self):
        data = minimal_input()
        del data["gate_id"]
        self.assert_refused(data, "missing required key 'gate_id'")

    def test_wrong_type_names_the_type_that_arrived(self):
        self.assert_refused(minimal_input(gate_id=7), "got a number")

    def test_empty_string_is_not_reported_as_a_string(self):
        self.assert_refused(minimal_input(gate_id=""), "got an empty string")

    def test_boolean_quorum_is_refused(self):
        # bool subclasses int, so an unguarded isinstance check accepted
        # "quorum": false as the quorum 0.0 - one accept vote carries the
        # panel, silently changing every number in the report.
        self.assert_refused(minimal_input(quorum=False), "got a boolean")
        self.assert_refused(minimal_input(quorum=True), "got a boolean")

    def test_out_of_range_quorum_is_refused(self):
        self.assert_refused(minimal_input(quorum=1.0), "[0, 1)")
        self.assert_refused(minimal_input(quorum=-0.5), "[0, 1)")

    def test_non_finite_quorum_is_refused(self):
        self.assert_refused(minimal_input(quorum=float("nan")), "[0, 1)")
        self.assert_refused(minimal_input(quorum=float("inf")), "[0, 1)")

    def test_candidate_without_id_is_located_by_position(self):
        data = minimal_input()
        del data["candidates"][1]["id"]
        self.assert_refused(data, "candidate #2")

    def test_verifier_without_id_is_located_by_position(self):
        data = minimal_input()
        del data["verifiers"][2]["id"]
        self.assert_refused(data, "verifier #3")

    def test_missing_ground_truth_is_reported_as_missing(self):
        data = minimal_input()
        del data["candidates"][0]["ground_truth"]
        self.assert_refused(data, "missing required key 'ground_truth'")

    def test_probe_kind_without_probe_flag_is_refused(self):
        # Accepted silently, this candidate joined the headline statistics and
        # the report carried no probe section at all - which reads as "no
        # probes breached" to anyone who asked for a breach rate.
        data = minimal_input()
        data["candidates"][2]["probe_kind"] = "seeded-defect"
        self.assert_refused(data, "probe_kind")

    def test_probe_kind_with_probe_flag_is_accepted(self):
        data = minimal_input()
        data["candidates"].append({
            "id": "p1", "ground_truth": "reject", "probe": True,
            "probe_kind": "prompt-injection"})
        for ver in data["verifiers"]:
            ver["verdicts"]["p1"] = "reject"
        report = gate_audit.audit(data)
        self.assertEqual(report["probes"]["by_kind"]["prompt-injection"],
                         {"total": 1, "breached": 0})

    def test_validate_input_enforces_the_two_candidate_minimum(self):
        # The specification documents this rule as enforced by validate_input,
        # so a caller using it as a pre-flight check must see it there and not
        # only when audit() runs.
        data = minimal_input()
        for cand in data["candidates"][1:]:
            cand["probe"] = True
            cand["ground_truth"] = "reject"
        for ver in data["verifiers"]:
            for cid in ("c2", "c3", "c4"):
                ver["verdicts"][cid] = "reject"
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.validate_input(data)
        self.assertIn("at least two non-probe", str(ctx.exception))


class EffectiveVoteResolutionTests(unittest.TestCase):
    """The headline number must never be a table edge or exceed the votes cast."""

    @staticmethod
    def _near_independent_panel(verifiers: int = 50, candidates: int = 400):
        """Accurate, uncorrelated verifiers: majority error underflows the table.

        This is not a contrived shape — it is what a panel of genuinely
        independent reviewers looks like, which is the regime the whole
        research line is about reaching.
        """
        import random

        rng = random.Random(7)
        cands = [
            {"id": f"c{i:04d}",
             "ground_truth": rng.choice(["accept", "reject"])}
            for i in range(candidates)
        ]
        vers = []
        for j in range(verifiers):
            verdicts = {}
            for cand in cands:
                truth = cand["ground_truth"]
                wrong = "reject" if truth == "accept" else "accept"
                verdicts[cand["id"]] = truth if rng.random() < 0.8 else wrong
            vers.append({"id": f"v{j:02d}", "verdicts": verdicts})
        return {
            "gate_id": "near-independent",
            "evidence_class": "synthetic",
            "candidates": cands,
            "verifiers": vers,
        }

    def test_effective_votes_never_exceed_the_votes_cast(self):
        # Uncapped, this reported 199 effective independent votes for a
        # 50-verifier panel: effective_n's table edge (nmax=201) printed as a
        # measurement, in the one sentence the report exists to say.
        report = gate_audit.audit(self._near_independent_panel())
        panel = report["panel"]
        self.assertLessEqual(panel["effective_votes"], panel["nominal_votes"])
        self.assertEqual(panel["effective_votes"], 50.0)

    def test_saturation_and_the_cap_are_both_named_in_warnings(self):
        report = gate_audit.audit(self._near_independent_panel())
        self.assertTrue(
            any("lower bound, not a measurement" in w
                for w in report["warnings"]),
            report["warnings"])
        self.assertTrue(
            any("exceeded the 50 votes actually cast" in w
                for w in report["warnings"]),
            report["warnings"])

    def test_the_markdown_headline_carries_the_capped_number(self):
        text = gate_audit.render_markdown(
            gate_audit.audit(self._near_independent_panel()))
        self.assertIn("50 verifiers ≈ 50.00 effective independent votes", text)

    def test_an_unsaturated_panel_is_left_alone(self):
        # The committed example resolves well inside the table: neither the
        # cap nor the saturation warning may touch a panel that measured a
        # real number.
        report = gate_audit.audit_file(EXAMPLE_INPUT)
        self.assertAlmostEqual(
            report["panel"]["effective_votes"], 1.6944444, places=6)
        for warning in report["warnings"]:
            self.assertNotIn("lower bound", warning)
            self.assertNotIn("votes actually cast", warning)

    def test_resolved_effective_votes_passes_nan_through_as_none(self):
        self.assertIsNone(
            gate_audit.resolved_effective_votes(float("nan"), 5))

    def test_table_max_is_the_largest_odd_size_below_nmax(self):
        self.assertEqual(gate_audit.effective_n_table_max(), 199)
        self.assertEqual(gate_audit.effective_n_table_max(nmax=11), 9)


class InputFileHandlingTests(unittest.TestCase):
    """Reading the file is where a newcomer's first failure actually happens."""

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name: str, payload: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(payload)
        return path

    def test_utf8_bom_is_tolerated(self):
        # Windows Notepad and PowerShell add a BOM. The old failure quoted
        # Python's "decode using utf-8-sig", which is advice about the reader.
        path = self.write(
            "bom.json",
            b"\xef\xbb\xbf" + json.dumps(minimal_input()).encode("utf-8"))
        report = gate_audit.audit_file(path)
        self.assertEqual(report["gate_id"], "test-gate")

    def test_bom_does_not_change_the_input_digest(self):
        plain = self.write(
            "plain.json", json.dumps(minimal_input()).encode("utf-8"))
        with_bom = self.write(
            "bom2.json",
            b"\xef\xbb\xbf" + json.dumps(minimal_input()).encode("utf-8"))
        self.assertEqual(
            gate_audit.audit_file(plain)["provenance"]["input_digest_sha256"],
            gate_audit.audit_file(with_bom)["provenance"][
                "input_digest_sha256"])

    def test_non_utf8_input_is_refused_with_an_actionable_message(self):
        path = self.write(
            "utf16.json", json.dumps(minimal_input()).encode("utf-16"))
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_file(path)
        self.assertIn("UTF-8", str(ctx.exception))

    def test_python_only_json_extensions_are_refused(self):
        # json.loads accepts NaN/Infinity; nothing else does. The report's
        # input digest promises a canonicalization other implementations can
        # recompute, which an input only Python can read would break.
        for token in ("NaN", "Infinity", "-Infinity"):
            data = json.dumps(minimal_input())
            path = self.write(
                "ext.json",
                data[:-1].encode("utf-8") + f', "note": {token}}}'.encode())
            with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
                gate_audit.audit_file(path)
            self.assertIn(token, str(ctx.exception))

    def test_duplicate_object_keys_are_refused(self):
        # json.loads keeps the last value; other implementations keep the
        # first or refuse the document, so the input digest cannot mean what
        # it claims. Worse, a repeated candidate id inside one `verdicts`
        # object silently rewrote the verifier accuracy being measured.
        raw = json.dumps(minimal_input())
        duplicated = raw.replace(
            '"gate_id": "test-gate"',
            '"gate_id": "first", "gate_id": "second"', 1)
        path = self.write("dup.json", duplicated.encode("utf-8"))
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_file(path)
        self.assertIn("duplicate JSON key 'gate_id'", str(ctx.exception))

    def test_duplicate_verdict_keys_are_refused(self):
        raw = json.dumps(minimal_input()).replace(
            '"c1": "accept", "c2": "accept"',
            '"c1": "accept", "c1": "reject", "c2": "accept"', 1)
        path = self.write("dupverdict.json", raw.encode("utf-8"))
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_file(path)
        self.assertIn("duplicate JSON key 'c1'", str(ctx.exception))

    def test_contract_violation_names_the_file(self):
        data = minimal_input()
        del data["evidence_class"]
        path = self.write("bad.json", json.dumps(data).encode("utf-8"))
        with self.assertRaises(gate_audit.GateAuditInputError) as ctx:
            gate_audit.audit_file(path)
        self.assertIn(path.name, str(ctx.exception))

    def test_unreachable_input_stays_an_oserror(self):
        # Failing to reach the file is not a contract violation, and the CLI
        # relies on the distinction to word its message.
        with self.assertRaises(OSError):
            gate_audit.audit_file(self.dir)


class CliFailureModeTests(unittest.TestCase):
    """No caller-fixable failure may reach a traceback or an exit code of 1.

    The specification promises exit 0 or exit 2 with the violation named on
    stderr. Every case below previously printed a traceback and exited 1.
    """

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
            env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        )

    def assert_clean_failure(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_directory_as_input(self):
        self.assert_clean_failure(
            self.run_cli("gate-audit", str(REPO_ROOT / "examples")),
            "is a directory")

    def test_out_into_a_missing_directory(self):
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT),
            "--out", str(self.dir / "missing" / "report.json"))
        self.assert_clean_failure(proc, "cannot write the JSON report")

    def test_markdown_into_a_missing_directory(self):
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT), "--out", str(self.dir / "r.json"),
            "--markdown", str(self.dir / "missing" / "report.md"))
        self.assert_clean_failure(proc, "cannot write the Markdown summary")

    def test_out_and_markdown_on_one_path_is_refused(self):
        # This exited 0 and left only the Markdown file, discarding the JSON
        # evidence that the report's input digest exists to bind.
        collision = self.dir / "report"
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT),
            "--out", str(collision), "--markdown", str(collision))
        self.assert_clean_failure(proc, "one report would overwrite the other")
        self.assertFalse(collision.exists())

    def test_out_onto_the_input_file_is_refused(self):
        votes = self.dir / "votes.json"
        votes.write_text(json.dumps(minimal_input()), encoding="utf-8")
        original = votes.read_bytes()
        proc = self.run_cli(
            "gate-audit", str(votes), "--out", str(votes))
        self.assert_clean_failure(proc, "is the input file")
        self.assertEqual(votes.read_bytes(), original)

    def test_non_utf8_input(self):
        path = self.dir / "utf16.json"
        path.write_bytes(json.dumps(minimal_input()).encode("utf-16"))
        self.assert_clean_failure(
            self.run_cli("gate-audit", str(path)), "UTF-8")

    def test_bom_input_succeeds(self):
        path = self.dir / "bom.json"
        path.write_bytes(
            b"\xef\xbb\xbf" + json.dumps(minimal_input()).encode("utf-8"))
        proc = self.run_cli("gate-audit", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout)["schema"], "gate-audit-report-v0.1")

    def test_successful_run_writes_both_files_and_says_nothing(self):
        out = self.dir / "report.json"
        md = self.dir / "report.md"
        proc = self.run_cli(
            "gate-audit", str(EXAMPLE_INPUT), "--out", str(out),
            "--markdown", str(md))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")
        self.assertTrue(out.exists() and md.exists())


if __name__ == "__main__":
    unittest.main()
