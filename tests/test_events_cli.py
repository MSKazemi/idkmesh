"""`idkmesh events list` over the canonical event stream (ADR-0023, #741)."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"
CREATED = {
    0: "2026-10-02T10:00:00Z",
    1: "2026-10-02T10:01:00Z",
    2: "2026-10-02T10:02:00Z",
}
CANCELLED_AT = "2026-10-02T10:05:00Z"


def _projection(run_id, *, project_id="project.test", wu="work/a"):
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-product-spine-run",
        "run_id": run_id,
        "request_digest": "sha256:" + "a" * 64,
        "project_id": project_id,
        "work_unit": {
            "id": wu,
            "version": 1,
            "digest": "sha256:" + "b" * 64,
            "source_revision": SHA,
        },
        "routing": {
            "policy_version": "c1-v0.1",
            "authority_mode": "agent_candidate",
            "admitted_connectors": [],
        },
        "state": "proposed",
        "attempts": [],
        "evidence_report_digest": None,
        "human_decision_record_digest": None,
        "authority": {
            "canonical_state_write": False,
            "git_push": False,
            "merge": False,
        },
    }


def _event_schema():
    path = ROOT / "schemas" / "idkmesh-event-v0.1.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class EventsCliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def create(self, tmp, store, index, **kwargs):
        path = Path(tmp) / f"projection-{index}.json"
        path.write_text(json.dumps(_projection(f"run/ev-{index}", **kwargs)))
        proc = self.run_cli(
            "run", "create", str(path), "--store", str(store),
            "--idempotency-key", f"ev-key-{index}",
            "--created-at", CREATED[index],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def populated(self, tmp):
        """Three runs created, then run/ev-1 cancelled: four events."""
        store = Path(tmp) / "state.sqlite"
        specs = (
            dict(project_id="project.alpha", wu="work/a"),
            dict(project_id="project.alpha", wu="work/b"),
            dict(project_id="project.beta", wu="work/a"),
        )
        for index, spec in enumerate(specs):
            self.create(tmp, store, index, **spec)
        proc = self.run_cli(
            "run", "cancel", "run/ev-1", "--store", str(store),
            "--updated-at", CANCELLED_AT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return store

    def list_json(self, store, *extra):
        proc = self.run_cli(
            "events", "list", "--store", str(store), "--json", *extra
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_events_list_is_empty_for_a_fresh_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli("events", "list", "--store", str(store))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no retained events", proc.stdout)
            payload = self.list_json(store)
            self.assertEqual(payload["items"], [])
            self.assertIsNone(payload["page"]["next_cursor"])

    def test_events_list_is_ordered_by_sequence_and_matches_the_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            payload = self.list_json(store)

            self.assertEqual(payload["kind"], "idkmesh-list")
            items = payload["items"]
            self.assertEqual([i["sequence"] for i in items], [1, 2, 3, 4])
            self.assertEqual(
                [i["event_type"] for i in items],
                ["run.created", "run.created", "run.created", "run.cancelled"],
            )
            validator = _event_schema()
            for item in items:
                validator.validate(item)
            self.assertEqual(items[0]["event_id"], "evt-000000000001")

    def test_event_timestamps_are_the_supplied_ones_not_a_clock_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            items = self.list_json(store)["items"]
            self.assertEqual(
                [i["occurred_at"] for i in items],
                [CREATED[0], CREATED[1], CREATED[2], CANCELLED_AT],
            )

    def test_events_carry_provenance_and_reserve_decision_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            created, cancelled = (
                self.list_json(store)["items"][0],
                self.list_json(store)["items"][3],
            )
            self.assertEqual(created["run_id"], "run/ev-0")
            self.assertEqual(created["project_id"], "project.alpha")
            self.assertEqual(created["work_unit_id"], "work/a")
            self.assertEqual(created["source_revision"], SHA)
            self.assertEqual(created["authority_class"], "local_control")
            self.assertEqual(created["principal"]["type"], "unauthenticated_local")
            self.assertEqual(cancelled["payload"]["previous_state"], "proposed")
            self.assertEqual(cancelled["payload"]["state"], "cancelled")
            for event in (created, cancelled):
                self.assertTrue(event["payload_digest"].startswith("sha256:"))
                self.assertNotIn(
                    event["authority_class"],
                    ("verifier_recommendation", "human_decision"),
                )

    def test_events_list_text_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli("events", "list", "--store", str(store))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(
                f"1\t{CREATED[0]}\trun.created\trun/ev-0", proc.stdout
            )
            self.assertIn(
                f"4\t{CANCELLED_AT}\trun.cancelled\trun/ev-1", proc.stdout
            )

    def test_events_list_paginates_without_skipping_or_repeating(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            page1 = self.list_json(store, "--limit", "3")
            self.assertEqual([i["sequence"] for i in page1["items"]], [1, 2, 3])
            cursor = page1["page"]["next_cursor"]
            self.assertIsNotNone(cursor)
            page2 = self.list_json(store, "--limit", "3", "--cursor", cursor)
            self.assertEqual([i["sequence"] for i in page2["items"]], [4])
            self.assertIsNone(page2["page"]["next_cursor"])

    def test_events_list_filters_are_exact_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            by_project = self.list_json(store, "--project-id", "project.beta")
            self.assertEqual(
                [i["run_id"] for i in by_project["items"]], ["run/ev-2"]
            )
            by_run = self.list_json(store, "--run-id", "run/ev-1")
            self.assertEqual(
                [i["event_type"] for i in by_run["items"]],
                ["run.created", "run.cancelled"],
            )
            by_work_unit = self.list_json(store, "--work-unit-id", "work/a")
            self.assertEqual(
                [i["run_id"] for i in by_work_unit["items"]],
                ["run/ev-0", "run/ev-2"],
            )
            by_type = self.list_json(store, "--event-type", "run.cancelled")
            self.assertEqual(len(by_type["items"]), 1)
            self.assertEqual(
                self.list_json(store, "--run-id", "run/ev")["items"], []
            )

    def test_events_list_combines_filters_with_pagination(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            page1 = self.list_json(
                store, "--project-id", "project.alpha", "--limit", "2"
            )
            self.assertEqual([i["sequence"] for i in page1["items"]], [1, 2])
            page2 = self.list_json(
                store, "--project-id", "project.alpha", "--limit", "2",
                "--cursor", page1["page"]["next_cursor"],
            )
            self.assertEqual([i["sequence"] for i in page2["items"]], [4])

    def test_events_list_rejects_an_unknown_event_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "events", "list", "--store", str(store),
                "--event-type", "run.exploded", "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_event_type"
            )

    def test_events_list_rejects_a_cursor_it_did_not_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli(
                "events", "list", "--store", str(store),
                "--cursor", "not-a-real-cursor", "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_cursor"
            )

    def test_events_list_rejects_a_run_list_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            run_page = json.loads(self.run_cli(
                "run", "list", "--store", str(store), "--limit", "1", "--json",
            ).stdout)
            proc = self.run_cli(
                "events", "list", "--store", str(store), "--json",
                "--cursor", run_page["page"]["next_cursor"],
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_cursor"
            )

    def test_events_list_rejects_an_out_of_range_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli(
                "events", "list", "--store", str(store),
                "--limit", "0", "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_limit"
            )

    def test_an_idempotent_replay_does_not_emit_a_second_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            self.create(tmp, store, 0, project_id="project.alpha", wu="work/a")
            self.create(tmp, store, 0, project_id="project.alpha", wu="work/a")
            self.assertEqual(len(self.list_json(store)["items"]), 1)

    def test_events_help_describes_the_command_and_its_limits(self):
        proc = self.run_cli("events", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("list", proc.stdout)
        listing = self.run_cli("events", "list", "--help")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        for flag in (
            "--store", "--limit", "--cursor", "--project-id", "--run-id",
            "--work-unit-id", "--event-type", "--json",
        ):
            self.assertIn(flag, listing.stdout)

    def test_control_tower_help_lists_the_sse_client_flag(self):
        proc = self.run_cli("control-tower", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--max-sse-clients", proc.stdout)


if __name__ == "__main__":
    unittest.main()
