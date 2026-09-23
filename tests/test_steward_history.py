"""Tests for offline Auto Draft PR Steward history aggregation."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from idkmesh import cli, steward_history, steward_report

ROOT = Path(__file__).resolve().parents[1]


def candidate(branch: str, head: str) -> dict:
    return {
        "branch": branch,
        "base": "main",
        "head_sha": head,
        "ahead_by": 1,
        "behind_by": 0,
    }


def report(
    *,
    generated_at: str,
    run_id: str | None,
    run_attempt: str | None = "1",
    repository: str = "MSKazemi/idkmesh",
    status: str = "completed",
    policy: str = "a" * 64,
    api: int | None = 4000,
    planned: list[dict] | None = None,
    created: list[dict] | None = None,
    skipped: list[dict] | None = None,
    blocked_reason: str | None = None,
) -> dict:
    planned = [] if planned is None else planned
    created = [] if created is None else created
    skipped = [] if skipped is None else skipped
    if status == "disabled":
        candidate_count = None
        blocked_reason = "policy_disabled"
        api = None
    elif status == "blocked":
        candidate_count = None
        blocked_reason = blocked_reason or "github_api_budget_low"
    else:
        candidate_count = len(planned)
        blocked_reason = None

    return {
        "schema": steward_report.SCHEMA_ID,
        "repository": repository,
        "generated_at": generated_at,
        "status": status,
        "dry_run": False,
        "policy": {
            "path": "config/auto-draft-pr.json",
            "sha256": policy,
        },
        "provenance": {
            "workflow": "Auto Draft PR Steward" if run_id else None,
            "run_id": run_id,
            "run_attempt": run_attempt if run_id else None,
            "trusted_head_sha": "f" * 40 if run_id else None,
        },
        "authority": dict(steward_report.EXPECTED_AUTHORITY),
        "candidate_count": candidate_count,
        "rate_limit_remaining": api,
        "blocked_reason": blocked_reason,
        "summary": {
            "planned": len(planned),
            "created": len(created),
            "skipped": len(skipped),
        },
        "planned": planned,
        "created": created,
        "skipped": skipped,
    }


def created_candidate(item: dict, number: int) -> dict:
    return {
        **item,
        "number": number,
        "url": f"https://github.com/MSKazemi/idkmesh/pull/{number}",
    }


def skipped_candidate(
    item: dict,
    reason: str,
    *,
    current_head: str | None = None,
) -> dict:
    value = {**item, "reason": reason}
    if current_head is not None:
        value["current_head_sha"] = current_head
    return value


class StewardHistoryDiscoveryTests(unittest.TestCase):
    def test_directory_discovery_reads_only_steward_report_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wanted = root / "one" / steward_history.REPORT_FILENAME
            wanted.parent.mkdir()
            wanted.write_text("{}", encoding="utf-8")
            unrelated = root / "unrelated.json"
            unrelated.write_text("not json", encoding="utf-8")
            found = steward_history.discover_report_files([root])
        self.assertEqual(found, [wanted])

    def test_explicit_renamed_report_file_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "renamed.json"
            path.write_text("{}", encoding="utf-8")
            found = steward_history.discover_report_files([path])
        self.assertEqual(found, [path])

    def test_same_resolved_file_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / steward_history.REPORT_FILENAME
            path.write_text("{}", encoding="utf-8")
            found = steward_history.discover_report_files([path, root])
        self.assertEqual(found, [path])

    def test_input_count_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.json"
            path.write_text("{}", encoding="utf-8")
            with mock.patch.object(steward_history, "MAX_HISTORY_INPUTS", 1):
                with self.assertRaisesRegex(
                    steward_history.StewardHistoryInputError,
                    "input count exceeds",
                ):
                    steward_history.discover_report_files([path, path])

    def test_discovered_report_count_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a", "b"):
                directory = root / name
                directory.mkdir()
                (directory / steward_history.REPORT_FILENAME).write_text(
                    "{}", encoding="utf-8"
                )
            with mock.patch.object(steward_history, "MAX_HISTORY_REPORTS", 1):
                with self.assertRaisesRegex(
                    steward_history.StewardHistoryInputError,
                    "report limit",
                ):
                    steward_history.discover_report_files([root])

    def test_directory_walk_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            with mock.patch.object(
                steward_history, "MAX_VISITED_DIRECTORIES", 1
            ):
                with self.assertRaisesRegex(
                    steward_history.StewardHistoryInputError,
                    "directory limit",
                ):
                    steward_history.discover_report_files([root])

    def test_empty_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                steward_history.StewardHistoryInputError,
                "no steward-report.json",
            ):
                steward_history.discover_report_files([tmp])


class StewardHistoryAggregationTests(unittest.TestCase):
    def _history_reports(self, root: Path):
        first = candidate("feat/created", "1" * 40)
        third_a = candidate("feat/moved", "2" * 40)
        third_b = candidate("docs/race", "3" * 40)
        return [
            (
                root / "later.json",
                report(
                    generated_at="2026-09-23T12:00:00Z",
                    run_id="103",
                    policy="b" * 64,
                    api=3000,
                    planned=[third_a, third_b],
                    skipped=[
                        skipped_candidate(
                            third_a,
                            "head_moved",
                            current_head="4" * 40,
                        ),
                        skipped_candidate(third_b, "pr_already_exists"),
                    ],
                ),
            ),
            (
                root / "first.json",
                report(
                    generated_at="2026-09-23T10:00:00Z",
                    run_id="101",
                    policy="a" * 64,
                    api=4000,
                    planned=[first],
                    created=[created_candidate(first, 701)],
                ),
            ),
            (
                root / "blocked.json",
                report(
                    generated_at="2026-09-23T11:00:00Z",
                    run_id="102",
                    status="blocked",
                    policy="b" * 64,
                    api=1000,
                    blocked_reason=(
                        "github_api_budget_low: remaining=1000, required=1500"
                    ),
                ),
            ),
        ]

    def test_history_orders_and_aggregates_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = steward_history.build_history(
                self._history_reports(Path(tmp))
            )
        self.assertEqual(history["report_count"], 3)
        self.assertEqual(
            history["status_counts"],
            {"completed": 2, "blocked": 1, "disabled": 0},
        )
        self.assertEqual(
            history["outcome_totals"],
            {
                "planned": 3,
                "created": 1,
                "skipped": 2,
                "head_moved": 1,
                "pr_already_exists": 1,
            },
        )
        self.assertEqual(
            history["api_budget"],
            {"observed_runs": 3, "min_remaining": 1000, "max_remaining": 4000},
        )
        self.assertEqual(history["policy"]["distinct_digests"], 2)
        self.assertEqual(history["policy"]["changes"], 1)
        self.assertEqual(history["policy"]["latest_sha256"], "b" * 64)
        self.assertEqual(
            [item["run_id"] for item in history["runs"]],
            ["101", "102", "103"],
        )
        self.assertEqual(history["integrity"]["algorithm"], "sha256")
        self.assertEqual(
            history["integrity"]["semantic_normalization"],
            steward_history.SEMANTIC_NORMALIZATION,
        )
        self.assertRegex(
            history["integrity"]["input_set_sha256"],
            r"^[0-9a-f]{64}$",
        )
        for run in history["runs"]:
            self.assertRegex(run["report_sha256"], r"^[0-9a-f]{64}$")

    def test_mixed_repositories_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = [
                (
                    root / "a.json",
                    report(
                        generated_at="2026-09-23T10:00:00Z",
                        run_id="1",
                    ),
                ),
                (
                    root / "b.json",
                    report(
                        generated_at="2026-09-23T11:00:00Z",
                        run_id="2",
                        repository="someone/else",
                    ),
                ),
            ]
            with self.assertRaisesRegex(
                steward_history.StewardHistoryInputError,
                "same repository",
            ):
                steward_history.build_history(reports)

    def test_duplicate_github_run_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = [
                (
                    root / "a.json",
                    report(
                        generated_at="2026-09-23T10:00:00Z",
                        run_id="123",
                    ),
                ),
                (
                    root / "b.json",
                    report(
                        generated_at="2026-09-23T11:00:00Z",
                        run_id="123",
                    ),
                ),
            ]
            with self.assertRaisesRegex(
                steward_history.StewardHistoryInputError,
                "duplicate GitHub workflow run identity",
            ):
                steward_history.build_history(reports)

    def test_local_reports_without_run_ids_can_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = steward_history.build_history(
                [
                    (
                        root / "a.json",
                        report(
                            generated_at="2026-09-23T10:00:00Z",
                            run_id=None,
                        ),
                    ),
                    (
                        root / "b.json",
                        report(
                            generated_at="2026-09-23T11:00:00Z",
                            run_id=None,
                        ),
                    ),
                ]
            )
        self.assertEqual(history["report_count"], 2)

    def test_semantic_report_digest_ignores_json_key_order(self):
        original = report(
            generated_at="2026-09-23T10:00:00Z",
            run_id="1",
        )
        reordered = dict(reversed(list(original.items())))
        self.assertEqual(
            steward_history.semantic_report_sha256(original),
            steward_history.semantic_report_sha256(reordered),
        )

    def test_input_set_digest_is_independent_of_local_source_path(self):
        payload = report(
            generated_at="2026-09-23T10:00:00Z",
            run_id="1",
        )
        first = steward_history.build_history(
            [(Path("/tmp/a.json"), payload)]
        )
        second = steward_history.build_history(
            [(Path("/different/machine/b.json"), payload)]
        )
        self.assertEqual(
            first["integrity"]["input_set_sha256"],
            second["integrity"]["input_set_sha256"],
        )

    def test_same_timestamp_order_is_semantic_not_path_based(self):
        first = report(
            generated_at="2026-09-23T10:00:00Z",
            run_id="100",
            policy="a" * 64,
        )
        second = report(
            generated_at="2026-09-23T10:00:00Z",
            run_id="200",
            policy="b" * 64,
        )
        history_a = steward_history.build_history(
            [
                (Path("/z/second.json"), second),
                (Path("/a/first.json"), first),
            ]
        )
        history_b = steward_history.build_history(
            [
                (Path("/z/first.json"), first),
                (Path("/a/second.json"), second),
            ]
        )
        self.assertEqual(
            [run["run_id"] for run in history_a["runs"]],
            ["100", "200"],
        )
        self.assertEqual(
            [run["run_id"] for run in history_b["runs"]],
            ["100", "200"],
        )
        self.assertEqual(
            history_a["integrity"]["input_set_sha256"],
            history_b["integrity"]["input_set_sha256"],
        )
        self.assertEqual(history_a["policy"]["changes"], 1)
        self.assertEqual(history_b["policy"]["changes"], 1)

    def test_integrity_binds_run_projection_not_only_report_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = steward_history.build_history(
                self._history_reports(Path(tmp))
            )
        history["runs"][0]["rate_limit_remaining"] = 3999
        history["api_budget"]["max_remaining"] = 3999
        with self.assertRaisesRegex(
            steward_history.StewardHistoryInputError,
            "does not match run evidence",
        ):
            steward_history.validate_history(history)

    def test_history_validator_detects_aggregate_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = steward_history.build_history(
                self._history_reports(Path(tmp))
            )
        history["status_counts"]["completed"] += 1
        with self.assertRaisesRegex(
            steward_history.StewardHistoryInputError,
            "status_counts.completed",
        ):
            steward_history.validate_history(history)

    def test_history_validator_detects_integrity_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = steward_history.build_history(
                self._history_reports(Path(tmp))
            )
        history["integrity"]["input_set_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            steward_history.StewardHistoryInputError,
            "does not match run evidence",
        ):
            steward_history.validate_history(history)

    @unittest.skipUnless(
        importlib.util.find_spec("jsonschema") is not None,
        "history schema validation requires jsonschema",
    )
    def test_history_validates_against_published_schema(self):
        from jsonschema import Draft202012Validator

        with tempfile.TemporaryDirectory() as tmp:
            history = steward_history.build_history(
                self._history_reports(Path(tmp))
            )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "auto-draft-pr-steward-history-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(history)


class StewardHistoryLoadAndRenderTests(unittest.TestCase):
    def _write(
        self,
        root: Path,
        name: str,
        payload: dict,
    ) -> Path:
        directory = root / name
        directory.mkdir(parents=True)
        path = directory / steward_history.REPORT_FILENAME
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_load_history_validates_each_report_and_ignores_other_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(
                root,
                "run-a",
                report(
                    generated_at="2026-09-23T10:00:00Z",
                    run_id="1",
                ),
            )
            (root / "other.json").write_text("{broken", encoding="utf-8")
            history = steward_history.load_history([root])
        self.assertEqual(history["report_count"], 1)

    def test_invalid_report_is_reported_with_source_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write(
                root,
                "run-a",
                report(
                    generated_at="2026-09-23T10:00:00Z",
                    run_id="1",
                ),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["authority"]["merge"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                steward_history.StewardHistoryInputError,
                "authority block",
            ):
                steward_history.load_history([root])

    def test_human_rendering_surfaces_history_and_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = steward_history.build_history(
                [
                    (
                        root / "run.json",
                        report(
                            generated_at="2026-09-23T10:00:00Z",
                            run_id="1",
                        ),
                    )
                ]
            )
        text = steward_history.render_history_text(history, details=True)
        self.assertIn("IDKMesh Auto Draft PR Steward History", text)
        self.assertIn("Reports: 1", text)
        self.assertIn("Authority: history is offline evidence only", text)
        self.assertIn("Runs:", text)
        self.assertIn("run.json", text)
        self.assertIn("Input set SHA-256:", text)
        self.assertIn("report_sha256=", text)

    def test_json_rendering_has_stable_schema_and_compact_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = steward_history.build_history(
                [
                    (
                        root / "run.json",
                        report(
                            generated_at="2026-09-23T10:00:00Z",
                            run_id="1",
                        ),
                    )
                ]
            )
        compact = steward_history.render_history_json(history)
        pretty = steward_history.render_history_json(history, pretty=True)
        self.assertEqual(json.loads(compact)["schema"], steward_history.HISTORY_SCHEMA)
        self.assertIn("integrity", json.loads(compact))
        self.assertNotIn("\n", compact)
        self.assertIn("\n  ", pretty)


class StewardHistoryCliTests(unittest.TestCase):
    def _write_report(self, root: Path) -> None:
        directory = root / "run"
        directory.mkdir()
        (directory / steward_history.REPORT_FILENAME).write_text(
            json.dumps(
                report(
                    generated_at="2026-09-23T10:00:00Z",
                    run_id="1",
                )
            ),
            encoding="utf-8",
        )

    def test_cli_prints_human_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_report(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(["steward-history", str(root), "--details"])
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("Reports: 1", stdout.getvalue())
        self.assertIn("Runs:", stdout.getvalue())

    def test_cli_prints_machine_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_report(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(["steward-history", str(root), "--json", "--pretty"])
        self.assertEqual(rc, 0)
        self.assertEqual(stderr.getvalue(), "")
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["schema"], steward_history.HISTORY_SCHEMA)

    def test_cli_rejects_conflicting_output_modes(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = cli.main(
                ["steward-history", ".", "--json", "--details"]
            )
        self.assertEqual(rc, 2)
        self.assertIn("--details cannot be combined with --json", stderr.getvalue())

    def test_cli_rejects_pretty_without_json(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = cli.main(["steward-history", ".", "--pretty"])
        self.assertEqual(rc, 2)
        self.assertIn("--pretty requires --json", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
