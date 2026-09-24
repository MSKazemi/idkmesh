"""Completed cross-engine observations must match the canonical observation plan."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import search_visibility_observation_import as importer
from scripts import search_visibility_observation_plan as plan


class SearchVisibilityObservationImportTests(unittest.TestCase):
    def _item(self):
        return plan.build_plan(
            sample="heads",
            surface_ids={"chatgpt-search"},
        )["items"][0]

    def _row(self, **overrides):
        item = self._item()
        row = {column: "" for column in importer.ALL_COLUMNS}
        for column in importer.PLAN_COLUMNS:
            row[column] = str(item[column])
        row.update(
            {
                "observed_at": "2026-09-24T00:30:00Z",
                "surfaced": "true",
                "position": "",
                "citation_url": "https://mskazemi.com/idkmesh/topics/ai-agent-verification.html",
                "evidence_ref": "manual/session-001",
                "notes": "IDKMesh was cited on the named product surface.",
            }
        )
        row.update(overrides)
        return row

    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=importer.ALL_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
        path.write_text(stream.getvalue(), encoding="utf-8")

    def _empty_ledger(self, path: Path) -> None:
        path.write_text(
            json.dumps({"schema_version": "0.1", "observations": []}),
            encoding="utf-8",
        )

    def test_templates_cover_balanced_head_and_full_plans(self) -> None:
        heads_plan = plan.build_plan(sample="heads")
        full_plan = plan.build_plan(sample="full")
        heads = importer.render_template(sample="heads").splitlines()
        full = importer.render_template(sample="full").splitlines()
        self.assertEqual(1 + heads_plan["summary"]["work_items"], len(heads))
        self.assertEqual(1 + full_plan["summary"]["work_items"], len(full))
        self.assertEqual(",".join(importer.ALL_COLUMNS), heads[0])

    def test_completed_row_becomes_one_candidate_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            self._write_csv(csv_path, [self._row(position="3")])
            self._empty_ledger(ledger)

            candidate = importer.import_rows(csv_path, ledger_path=ledger)

        self.assertEqual("0.1", candidate["schema_version"])
        self.assertEqual(1, len(candidate["observations"]))
        observation = candidate["observations"][0]
        self.assertEqual("chatgpt", observation["engine"])
        self.assertEqual("ai_answer", observation["surface"])
        self.assertEqual("manual_reproduction", observation["evidence_class"])
        self.assertTrue(observation["surfaced"])
        self.assertEqual(3, observation["position"])
        self.assertEqual("2026-09-24T00:30:00Z", observation["observed_at"])
        self.assertEqual(
            "manual/chatgpt-search/agent-verification/q01/20260924T003000Z",
            observation["id"],
        )

    def test_plan_controlled_query_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            self._write_csv(csv_path, [self._row(query="different query")])
            self._empty_ledger(ledger)
            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "query does not match canonical plan",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_non_surfaced_result_cannot_claim_position_or_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            self._write_csv(
                csv_path,
                [
                    self._row(
                        surfaced="false",
                        position="2",
                        citation_url="https://example.com/result",
                    )
                ],
            )
            self._empty_ledger(ledger)
            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "non-surfaced observation cannot claim",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_unexpected_csv_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            row = self._row()
            stream = io.StringIO(newline="")
            fields = [*importer.ALL_COLUMNS, "extra"]
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerow({**row, "extra": "unexpected"})
            csv_path.write_text(stream.getvalue(), encoding="utf-8")
            self._empty_ledger(ledger)
            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "unexpected column",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_citation_url_must_be_absolute_http_or_https(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            self._write_csv(
                csv_path,
                [self._row(citation_url="not-a-url")],
            )
            self._empty_ledger(ledger)
            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "citation_url must be an absolute http",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_timestamp_requires_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            self._write_csv(
                csv_path,
                [self._row(observed_at="2026-09-24T00:30:00")],
            )
            self._empty_ledger(ledger)
            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "must include a timezone",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_duplicate_observation_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "completed.csv"
            ledger = root / "ledger.json"
            row = self._row()
            self._write_csv(csv_path, [row])
            self._empty_ledger(ledger)
            first = importer.import_rows(csv_path, ledger_path=ledger)
            ledger.write_text(json.dumps(first), encoding="utf-8")

            with self.assertRaisesRegex(
                importer.ObservationImportError,
                "duplicate observation id",
            ):
                importer.import_rows(csv_path, ledger_path=ledger)

    def test_empty_or_unfinished_template_is_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "template.csv"
            ledger = root / "ledger.json"
            csv_path.write_text(
                importer.render_template(sample="heads"),
                encoding="utf-8",
            )
            self._empty_ledger(ledger)
            with self.assertRaises(importer.ObservationImportError):
                importer.import_rows(csv_path, ledger_path=ledger)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
