import json
from pathlib import Path
import tempfile
import unittest

from idkmesh import marginal_evidence_benchmark as benchmark
from idkmesh import marginal_evidence_synthesis as synthesis


def _digest(label):
    import hashlib
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _config(**overrides):
    value = {
        "schema": synthesis.CONFIG_SCHEMA_ID,
        "synthesis_id": "cohort-synthesis-001",
        "evidence_class": "synthetic",
        "selection_rule_version": benchmark.SELECTION_RULE_VERSION,
        "benchmark_reports": ["b.json", "a.json"],
    }
    value.update(overrides)
    return value


def _report(
    benchmark_id,
    *,
    panel_error_delta=0.1,
    effective_votes_delta=0.2,
    evidence_class="synthetic",
    holdout_rows=20,
    unresolved_marginal=False,
):
    rows = []
    for strategy in benchmark.STRATEGIES:
        unresolved = (
            unresolved_marginal
            and strategy == benchmark.STRATEGY_MARGINAL
        )
        rows.append(
            {
                "strategy": strategy,
                "selection_status": (
                    "unresolved" if unresolved else "selected"
                ),
                "selected_verifier_id": (
                    None if unresolved else f"{strategy}-v"
                ),
                "status": (
                    "not_evaluated" if unresolved else "evaluated"
                ),
                "panel_error_delta": (
                    None if unresolved else panel_error_delta
                ),
                "delta_effective_votes": (
                    None if unresolved else effective_votes_delta
                ),
            }
        )
    return {
        "schema": benchmark.REPORT_SCHEMA_ID,
        "benchmark_id": benchmark_id,
        "gate_id": "gate.example",
        "evidence_class": evidence_class,
        "authority": benchmark.AUTHORITY,
        "analysis": {
            "selection_rule_version": benchmark.SELECTION_RULE_VERSION,
        },
        "splits": {
            "design": {
                "input_digest_sha256": _digest(
                    benchmark_id + ":design"
                ),
            },
            "holdout": {
                "input_digest_sha256": _digest(
                    benchmark_id + ":holdout"
                ),
                "non_probe_candidates": holdout_rows,
            },
        },
        "selection_plan": {
            "rule_version": benchmark.SELECTION_RULE_VERSION,
        },
        "holdout_results": rows,
    }


class ConfigContractTests(unittest.TestCase):
    def test_requires_at_least_two_reports(self):
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.validate_config(
                _config(benchmark_reports=["one.json"])
            )

    def test_normalizes_report_paths_as_a_set(self):
        first = synthesis.validate_config(_config())
        second = synthesis.validate_config(
            _config(benchmark_reports=["a.json", "b.json"])
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first["benchmark_reports"], ["a.json", "b.json"]
        )

    def test_rejects_duplicate_or_absolute_paths(self):
        for reports in (
            ["a.json", "a.json"],
            ["a.json", "/tmp/b.json"],
        ):
            with self.subTest(reports=reports):
                with self.assertRaises(
                    synthesis.MarginalEvidenceSynthesisInputError
                ):
                    synthesis.validate_config(
                        _config(benchmark_reports=reports)
                    )

    def test_rejects_other_selection_rule_version(self):
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.validate_config(
                _config(selection_rule_version="future-rule")
            )

    def test_referenced_paths_cannot_escape_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config(
                benchmark_reports=["a.json", "../b.json"]
            )
            path = root / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(
                synthesis.MarginalEvidenceSynthesisInputError
            ):
                synthesis.referenced_paths(path)


class SynthesisSemanticsTests(unittest.TestCase):
    def test_aggregates_descriptive_outcomes_without_ranking(self):
        report = synthesis.synthesize(
            [
                (
                    "a.json",
                    _report(
                        "a",
                        panel_error_delta=0.10,
                        holdout_rows=10,
                    ),
                ),
                (
                    "b.json",
                    _report(
                        "b",
                        panel_error_delta=-0.05,
                        holdout_rows=30,
                    ),
                ),
            ],
            config=_config(),
        )
        self.assertEqual(report["authority"], "diagnostic_only")
        self.assertEqual(report["analysis"]["benchmark_count"], 2)
        self.assertEqual(
            report["analysis"]["total_holdout_non_probe_candidates"],
            40,
        )
        row = report["strategies"][0]
        self.assertEqual(
            row["panel_error_delta"]["improved"], 1
        )
        self.assertEqual(
            row["panel_error_delta"]["worsened"], 1
        )
        self.assertAlmostEqual(
            row["panel_error_delta"]["macro_mean"],
            0.025,
        )
        self.assertAlmostEqual(
            row["panel_error_delta"]["holdout_row_weighted_mean"],
            -0.0125,
        )
        encoded = json.dumps(report)
        for forbidden in (
            "winner",
            "best_strategy",
            "ranking",
            "routing_recommendation",
        ):
            self.assertNotIn(f'"{forbidden}"', encoded)

    def test_unresolved_selection_stays_unresolved(self):
        report = synthesis.synthesize(
            [
                (
                    "a.json",
                    _report("a", unresolved_marginal=True),
                ),
                (
                    "b.json",
                    _report("b", unresolved_marginal=False),
                ),
            ],
            config=_config(),
        )
        marginal = report["strategies"][0]
        self.assertEqual(marginal["selection_resolved"], 1)
        self.assertEqual(marginal["selection_unresolved"], 1)
        self.assertEqual(marginal["holdout_not_evaluated"], 1)
        self.assertEqual(
            marginal["panel_error_delta"]["unresolved"], 1
        )
        self.assertEqual(
            marginal["effective_votes_delta"]["unresolved"], 1
        )

    def test_report_order_does_not_change_synthesis(self):
        config = _config()
        a = ("a.json", _report("a"))
        b = ("b.json", _report("b"))
        first = synthesis.synthesize([a, b], config=config)
        second = synthesis.synthesize([b, a], config=config)
        self.assertEqual(first, second)
        self.assertEqual(
            [c["benchmark_id"] for c in first["cohorts"]],
            ["a", "b"],
        )

    def test_mixed_evidence_classes_are_refused(self):
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.synthesize(
                [
                    ("a.json", _report("a")),
                    (
                        "b.json",
                        _report("b", evidence_class="observed"),
                    ),
                ],
                config=_config(),
            )

    def test_rule_version_mismatch_is_refused(self):
        changed = _report("b")
        changed["analysis"]["selection_rule_version"] = (
            "future-rule"
        )
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.synthesize(
                [
                    ("a.json", _report("a")),
                    ("b.json", changed),
                ],
                config=_config(),
            )

    def test_duplicate_split_evidence_is_refused(self):
        first = _report("a")
        second = _report("b")
        second["splits"]["holdout"][
            "input_digest_sha256"
        ] = first["splits"]["holdout"]["input_digest_sha256"]
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ) as ctx:
            synthesis.synthesize(
                [
                    ("a.json", first),
                    ("b.json", second),
                ],
                config=_config(),
            )
        self.assertIn("holdout split digest", str(ctx.exception))

    def test_duplicate_report_is_refused_even_under_two_paths(self):
        duplicate = _report("same")
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.synthesize(
                [
                    ("a.json", duplicate),
                    ("b.json", dict(duplicate)),
                ],
                config=_config(),
            )

    def test_strategy_order_is_fail_closed(self):
        changed = _report("b")
        changed["holdout_results"] = list(
            reversed(changed["holdout_results"])
        )
        with self.assertRaises(
            synthesis.MarginalEvidenceSynthesisInputError
        ):
            synthesis.synthesize(
                [
                    ("a.json", _report("a")),
                    ("b.json", changed),
                ],
                config=_config(),
            )


class FileAndRenderTests(unittest.TestCase):
    def test_synthesis_file_loads_relative_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.json").write_text(
                json.dumps(_report("a")),
                encoding="utf-8",
            )
            (root / "b.json").write_text(
                json.dumps(_report("b")),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(_config()),
                encoding="utf-8",
            )
            result = synthesis.synthesis_file(config_path)
            self.assertEqual(
                result["analysis"]["benchmark_count"], 2
            )
            self.assertEqual(
                [c["report"] for c in result["cohorts"]],
                ["a.json", "b.json"],
            )

    def test_render_json_is_strict_json(self):
        result = synthesis.synthesize(
            [
                ("a.json", _report("a")),
                ("b.json", _report("b")),
            ],
            config=_config(),
        )
        rendered = synthesis.render_json(
            result,
            pretty=True,
        )
        self.assertEqual(
            json.loads(rendered)["schema"],
            synthesis.REPORT_SCHEMA_ID,
        )


if __name__ == "__main__":
    unittest.main()
