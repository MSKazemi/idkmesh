"""Tests for the held-out marginal-evidence benchmark (issue #693)."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from idkmesh import marginal_evidence_benchmark as benchmark  # noqa: E402

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

CONFIG_SCHEMA_PATH = (
    REPO_ROOT
    / "schemas"
    / "marginal-evidence-benchmark-config-v0.1.schema.json"
)
REPORT_SCHEMA_PATH = (
    REPO_ROOT
    / "schemas"
    / "marginal-evidence-benchmark-report-v0.1.schema.json"
)


def _flip(verdict: str) -> str:
    return "reject" if verdict == "accept" else "accept"


def make_matrix(
    prefix: str,
    *,
    count: int = 20,
    quorum: float = 0.5,
    error_sets: dict[str, set[int]] | None = None,
    probes: int = 0,
) -> dict:
    error_sets = error_sets or {
        "v1": {0, 1, 2, 3},
        "v2": {0, 1, 4, 5},
        "v3": {2, 6, 10},
        "v4": {0, 1, 2, 3},
        "v5": {7, 8, 9},
    }
    candidates = []
    for i in range(count):
        candidates.append(
            {
                "id": f"{prefix}-c{i:03d}",
                "ground_truth": "accept" if i % 2 == 0 else "reject",
            }
        )
    for i in range(probes):
        candidates.append(
            {
                "id": f"{prefix}-p{i:03d}",
                "ground_truth": "reject",
                "probe": True,
                "probe_kind": "seeded-defect",
            }
        )

    verifiers = []
    for verifier_id, wrong_rows in error_sets.items():
        verdicts = {}
        for i in range(count):
            candidate = candidates[i]
            truth = candidate["ground_truth"]
            verdicts[candidate["id"]] = (
                _flip(truth) if i in wrong_rows else truth
            )
        for i in range(probes):
            verdicts[f"{prefix}-p{i:03d}"] = (
                "accept" if (i + len(verifier_id)) % 2 == 0 else "reject"
            )
        verifiers.append({"id": verifier_id, "verdicts": verdicts})

    return {
        "gate_id": "heldout-benchmark-gate",
        "evidence_class": "synthetic",
        "quorum": quorum,
        "candidates": candidates,
        "verifiers": verifiers,
    }


def make_config(**overrides) -> dict:
    config = {
        "schema": benchmark.CONFIG_SCHEMA_ID,
        "benchmark_id": "benchmark-test",
        "design_matrix": "design.json",
        "holdout_matrix": "holdout.json",
        "current_verifier_ids": ["v1", "v2"],
        "candidate_verifier_ids": ["v3", "v4", "v5"],
        "verifier_families": {
            "v1": "family-a",
            "v2": "family-a",
            "v3": "family-b",
            "v4": "family-a",
            "v5": "family-c",
        },
        "random_seed": 17,
        "bootstrap": {
            "replicates": 100,
            "seed": 23,
            "confidence_level": 0.9,
        },
    }
    config.update(overrides)
    return config


def _fake_row(
    verifier_id: str,
    *,
    delta: float,
    low: float,
    high: float,
    accuracy: float = 0.8,
    correlation: float | None = 0.0,
    status: str = "measured",
) -> dict:
    return {
        "id": verifier_id,
        "status": status,
        "delta_effective_votes": delta,
        "standalone_accuracy": accuracy,
        "mean_error_correlation_with_current_panel": correlation,
        "uncertainty": {
            "sufficient_for_inference": True,
            "replicates": 100,
            "effective_votes_delta": {
                "ci_low": low,
                "ci_high": high,
                "replicates_used": 100,
                "replicates_undefined": 0,
            },
        },
    }


class ConfigContractTests(unittest.TestCase):
    def test_config_requires_exact_family_coverage(self):
        config = make_config()
        del config["verifier_families"]["v5"]
        with self.assertRaises(
            benchmark.MarginalEvidenceBenchmarkInputError
        ) as ctx:
            benchmark.validate_config(config)
        self.assertIn("exactly cover", str(ctx.exception))

    def test_current_and_candidate_ids_must_not_overlap(self):
        config = make_config(candidate_verifier_ids=["v2", "v3"])
        config["verifier_families"] = {
            "v1": "a",
            "v2": "a",
            "v3": "b",
        }
        with self.assertRaises(
            benchmark.MarginalEvidenceBenchmarkInputError
        ) as ctx:
            benchmark.validate_config(config)
        self.assertIn("overlap", str(ctx.exception))

    def test_config_rejects_duplicate_json_keys(self):
        text = (
            '{"schema":"marginal-evidence-benchmark-config-v0.1",'
            '"benchmark_id":"a","benchmark_id":"b"}'
        )
        with self.assertRaises(
            benchmark.MarginalEvidenceBenchmarkInputError
        ) as ctx:
            benchmark._parse_json_text(text, source="config.json")
        self.assertIn("duplicate JSON key", str(ctx.exception))

    def test_config_matrix_path_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(design_matrix="../outside.json")
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(
                benchmark.MarginalEvidenceBenchmarkInputError
            ) as ctx:
                benchmark.referenced_paths(config_path)
            self.assertIn("escapes", str(ctx.exception))


class SplitIntegrityTests(unittest.TestCase):
    def test_design_and_holdout_candidate_ids_must_be_disjoint(self):
        design = make_matrix("same")
        holdout = make_matrix("same")
        with self.assertRaises(
            benchmark.MarginalEvidenceBenchmarkInputError
        ) as ctx:
            benchmark.benchmark(design, holdout, config=make_config())
        self.assertIn("must be disjoint", str(ctx.exception))

    def test_holdout_verdict_changes_do_not_change_selection_plan(self):
        design = make_matrix("design")
        holdout_a = make_matrix("holdout")
        holdout_b = copy.deepcopy(holdout_a)

        for verifier in holdout_b["verifiers"]:
            for candidate in holdout_b["candidates"]:
                cid = candidate["id"]
                if candidate.get("probe", False):
                    continue
                verifier["verdicts"][cid] = _flip(
                    verifier["verdicts"][cid]
                )

        first = benchmark.benchmark(
            design,
            holdout_a,
            config=make_config(),
        )
        second = benchmark.benchmark(
            design,
            holdout_b,
            config=make_config(),
        )
        self.assertEqual(first["selection_plan"], second["selection_plan"])
        self.assertNotEqual(
            first["splits"]["holdout"]["input_digest_sha256"],
            second["splits"]["holdout"]["input_digest_sha256"],
        )

    def test_gate_semantics_must_match_between_splits(self):
        design = make_matrix("design", quorum=0.5)
        holdout = make_matrix("holdout", quorum=0.6)
        with self.assertRaises(
            benchmark.MarginalEvidenceBenchmarkInputError
        ) as ctx:
            benchmark.benchmark(design, holdout, config=make_config())
        self.assertIn("same quorum", str(ctx.exception))


class SelectorTests(unittest.TestCase):
    def test_marginal_selector_requires_interval_separation(self):
        rows = [
            _fake_row("a", delta=2.0, low=1.2, high=2.8),
            _fake_row("b", delta=0.5, low=-0.1, high=0.9),
            _fake_row("c", delta=0.1, low=-0.2, high=0.4),
        ]
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "selected")
        self.assertEqual(selected["selected_verifier_id"], "a")

    def test_marginal_selector_fails_closed_when_intervals_overlap(self):
        rows = [
            _fake_row("a", delta=2.0, low=0.5, high=3.0),
            _fake_row("b", delta=1.0, low=0.2, high=1.5),
        ]
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "unresolved")
        self.assertIsNone(selected["selected_verifier_id"])
        self.assertEqual(
            selected["reason_code"],
            "marginal_ordering_not_interval_separated",
        )

    def test_marginal_selector_stops_without_positive_interval_support(self):
        rows = [
            _fake_row("a", delta=0.4, low=-0.1, high=0.9),
            _fake_row("b", delta=-0.8, low=-1.2, high=-0.4),
        ]
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "unresolved")
        self.assertIsNone(selected["selected_verifier_id"])
        self.assertEqual(
            selected["reason_code"],
            "marginal_gain_not_positive_with_interval_support",
        )

    def test_marginal_selector_does_not_fallback_from_unresolved_metric(self):
        rows = [
            _fake_row("a", delta=2.0, low=1.5, high=2.5),
            _fake_row("b", delta=0.0, low=-0.5, high=0.5),
        ]
        rows[1]["delta_effective_votes"] = None
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "unresolved")
        self.assertEqual(
            selected["reason_code"],
            "unresolved_design_effective_vote_metrics",
        )

    def test_marginal_selector_requires_all_bootstrap_replicates_resolved(self):
        rows = [
            _fake_row("a", delta=2.0, low=1.5, high=2.5),
            _fake_row("b", delta=0.2, low=0.1, high=0.3),
        ]
        section = rows[0]["uncertainty"]["effective_votes_delta"]
        section["replicates_used"] = 99
        section["replicates_undefined"] = 1
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "unresolved")
        self.assertEqual(
            selected["reason_code"],
            "unresolved_design_effective_vote_metrics",
        )

    def test_marginal_selector_is_not_blocked_by_correlation_only_status(self):
        rows = [
            _fake_row(
                "a",
                delta=2.0,
                low=1.5,
                high=2.5,
                correlation=None,
                status="unresolved",
            ),
            _fake_row("b", delta=0.0, low=-0.5, high=0.5),
        ]
        selected = benchmark._select_marginal(rows)
        self.assertEqual(selected["status"], "selected")
        self.assertEqual(selected["selected_verifier_id"], "a")

    def test_correlation_selector_fails_closed_if_any_candidate_unmeasurable(self):
        rows = [
            _fake_row("a", delta=1.0, low=0.5, high=1.5, correlation=0.1),
            _fake_row("b", delta=0.0, low=-0.5, high=0.5, correlation=None),
        ]
        selected = benchmark._select_correlation(rows)
        self.assertEqual(selected["status"], "unresolved")
        self.assertIsNone(selected["selected_verifier_id"])

    def test_random_selector_is_deterministic(self):
        rows = [
            _fake_row("a", delta=1.0, low=0.5, high=1.5),
            _fake_row("b", delta=0.0, low=-0.5, high=0.5),
            _fake_row("c", delta=-1.0, low=-1.5, high=-0.5),
        ]
        first = benchmark._select_random(rows, 123)
        second = benchmark._select_random(rows, 123)
        self.assertEqual(first, second)

    def test_family_first_prefers_unrepresented_family_then_accuracy(self):
        rows = [
            _fake_row("v3", delta=0.0, low=-1, high=1, accuracy=0.7),
            _fake_row("v4", delta=0.0, low=-1, high=1, accuracy=0.99),
            _fake_row("v5", delta=0.0, low=-1, high=1, accuracy=0.8),
        ]
        families = {
            "v1": "a",
            "v2": "a",
            "v3": "b",
            "v4": "a",
            "v5": "c",
        }
        selected = benchmark._select_family(
            rows,
            current_ids=["v1", "v2"],
            families=families,
        )
        self.assertEqual(selected["selected_verifier_id"], "v5")


class EndToEndTests(unittest.TestCase):
    def test_report_contains_five_strategies_and_no_winner(self):
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(
            [item["strategy"] for item in report["selection_plan"]["selectors"]],
            list(benchmark.STRATEGIES),
        )
        self.assertEqual(
            [item["strategy"] for item in report["holdout_results"]],
            list(benchmark.STRATEGIES),
        )
        self.assertNotIn("winner", report)
        self.assertNotIn("selected_verifier_id", report)

    def test_small_design_set_leaves_marginal_strategy_unresolved(self):
        report = benchmark.benchmark(
            make_matrix("design", count=4),
            make_matrix("holdout", count=8),
            config=make_config(),
        )
        marginal = report["selection_plan"]["selectors"][0]
        self.assertEqual(marginal["strategy"], benchmark.STRATEGY_MARGINAL)
        self.assertEqual(marginal["status"], "unresolved")
        result = report["holdout_results"][0]
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIsNone(result["selected_verifier_id"])

    def test_selection_plan_digest_is_bound_into_provenance(self):
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        self.assertEqual(
            report["selection_plan"]["digest_sha256"],
            report["provenance"]["selection_plan_digest_sha256"],
        )

    def test_selection_plan_is_bound_to_exact_design_matrix(self):
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        self.assertEqual(
            report["selection_plan"]["design_input_digest_sha256"],
            report["splits"]["design"]["input_digest_sha256"],
        )


class CommittedExampleTests(unittest.TestCase):
    CONFIG = (
        REPO_ROOT
        / "examples"
        / "gate-audit"
        / "marginal-evidence-benchmark-config.example.json"
    )

    def test_committed_example_runs_and_preserves_split_separation(self):
        report = benchmark.benchmark_file(self.CONFIG)
        self.assertEqual(
            report["benchmark_id"], "heldout-marginal-example-v0.1"
        )
        self.assertNotEqual(
            report["splits"]["design"]["input_digest_sha256"],
            report["splits"]["holdout"]["input_digest_sha256"],
        )
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(len(report["selection_plan"]["selectors"]), 5)


class FileAndCliTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        (root / "design.json").write_text(
            json.dumps(make_matrix("design")),
            encoding="utf-8",
        )
        (root / "holdout.json").write_text(
            json.dumps(make_matrix("holdout")),
            encoding="utf-8",
        )
        config_path = root / "config.json"
        config_path.write_text(json.dumps(make_config()), encoding="utf-8")
        return config_path

    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )

    def test_benchmark_file_loads_relative_matrices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_fixture(Path(temp_dir))
            report = benchmark.benchmark_file(config_path)
            self.assertEqual(report["benchmark_id"], "benchmark-test")

    def test_cli_emits_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_fixture(Path(temp_dir))
            proc = self.run_cli(
                "gate-marginal-benchmark",
                str(config_path),
                "--pretty",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["schema"], benchmark.REPORT_SCHEMA_ID)

    def test_cli_refuses_output_over_design_matrix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            proc = self.run_cli(
                "gate-marginal-benchmark",
                str(config_path),
                "--out",
                str(root / "design.json"),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("design matrix", proc.stderr)
            # The evidence file must still be valid after the refused command.
            json.loads((root / "design.json").read_text(encoding="utf-8"))


class SchemaTests(unittest.TestCase):
    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_config_validates_against_schema(self):
        schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(make_config(), schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_report_validates_against_schema(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design", probes=2),
            make_matrix("holdout", probes=2),
            config=make_config(),
        )
        jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_unresolved_selector_with_selected_id(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design", count=4),
            make_matrix("holdout", count=8),
            config=make_config(),
        )
        selector = report["selection_plan"]["selectors"][0]
        self.assertEqual(selector["status"], "unresolved")
        selector["selected_verifier_id"] = "v3"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_reordered_selector_rows(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        selectors = report["selection_plan"]["selectors"]
        selectors[0], selectors[1] = selectors[1], selectors[0]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_truncated_selector_rows(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        report["selection_plan"]["selectors"].pop()
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_reordered_holdout_rows(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        rows = report["holdout_results"]
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_schema_rejects_evaluated_row_with_unresolved_candidate_status(self):
        schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
        report = benchmark.benchmark(
            make_matrix("design"),
            make_matrix("holdout"),
            config=make_config(),
        )
        evaluated = next(
            row for row in report["holdout_results"]
            if row["status"] == "evaluated"
        )
        evaluated["holdout_candidate_status"] = "unresolved"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(report, schema)


if __name__ == "__main__":
    unittest.main()
