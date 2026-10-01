import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"


def _projection(run_id, *, project_id="project.test", wu="work/a", version=1,
                digest_char="b"):
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-product-spine-run",
        "run_id": run_id,
        "request_digest": "sha256:" + "a" * 64,
        "project_id": project_id,
        "work_unit": {
            "id": wu,
            "version": version,
            "digest": "sha256:" + digest_char * 64,
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


class WorkUnitCliTests(unittest.TestCase):
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
        path.write_text(json.dumps(_projection(f"run/wu-{index}", **kwargs)))
        proc = self.run_cli(
            "run", "create", str(path), "--store", str(store),
            "--idempotency-key", f"wu-key-{index}",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def populated(self, tmp):
        store = Path(tmp) / "state.sqlite"
        specs = (
            dict(wu="work/b", project_id="project.alpha"),
            dict(wu="work/a", project_id="project.alpha"),
            dict(wu="work/a", project_id="project.beta", version=2,
                 digest_char="c"),
            dict(wu="work/c", project_id="project.beta"),
        )
        for index, spec in enumerate(specs):
            self.create(tmp, store, index, **spec)
        return store

    def test_work_unit_list_is_empty_for_a_fresh_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli("work-unit", "list", "--store", str(store))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("no retained work units", proc.stdout)

    def test_work_unit_list_json_is_ordered_by_id_with_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "work-unit", "list", "--store", str(store), "--json"
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["kind"], "idkmesh-list")
            self.assertEqual(
                [item["id"] for item in payload["items"]],
                ["work/a", "work/b", "work/c"],
            )
            work_a = payload["items"][0]
            self.assertEqual(work_a["run_count"], 2)
            self.assertEqual(
                [rev["version"] for rev in work_a["revisions"]], [1, 2]
            )
            self.assertIsNone(payload["page"]["next_cursor"])

    def test_work_unit_list_text_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli("work-unit", "list", "--store", str(store))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("work/a\truns=2\trevisions=2", proc.stdout)

    def test_work_unit_list_paginates_with_a_returned_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            page1 = json.loads(self.run_cli(
                "work-unit", "list", "--store", str(store),
                "--limit", "2", "--json",
            ).stdout)
            self.assertEqual(
                [item["id"] for item in page1["items"]],
                ["work/a", "work/b"],
            )
            cursor = page1["page"]["next_cursor"]
            self.assertIsNotNone(cursor)
            page2 = json.loads(self.run_cli(
                "work-unit", "list", "--store", str(store),
                "--limit", "2", "--cursor", cursor, "--json",
            ).stdout)
            self.assertEqual(
                [item["id"] for item in page2["items"]], ["work/c"]
            )
            self.assertIsNone(page2["page"]["next_cursor"])

    def test_work_unit_list_filters_by_project_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            payload = json.loads(self.run_cli(
                "work-unit", "list", "--store", str(store),
                "--project-id", "project.beta", "--json",
            ).stdout)
            self.assertEqual(
                [item["id"] for item in payload["items"]],
                ["work/a", "work/c"],
            )
            self.assertEqual(payload["items"][0]["run_count"], 1)

    def test_work_unit_list_rejects_a_cursor_it_did_not_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli(
                "work-unit", "list", "--store", str(store),
                "--cursor", "not-a-real-cursor", "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_cursor"
            )

    def test_work_unit_list_rejects_a_run_list_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            run_page = json.loads(self.run_cli(
                "run", "list", "--store", str(store),
                "--limit", "1", "--json",
            ).stdout)
            proc = self.run_cli(
                "work-unit", "list", "--store", str(store), "--json",
                "--cursor", run_page["page"]["next_cursor"],
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "invalid_cursor"
            )

    def test_work_unit_status_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "work-unit", "status", "work/a", "--store", str(store),
                "--json",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["id"], "work/a")
            self.assertEqual(payload["run_count"], 2)
            text = self.run_cli(
                "work-unit", "status", "work/a", "--store", str(store)
            )
            self.assertIn("work_unit: work/a", text.stdout)

    def test_work_unit_status_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "work-unit", "status", "work/missing", "--store", str(store),
                "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"],
                "work_unit_not_found",
            )

    def test_help_lists_the_work_unit_commands(self):
        top = self.run_cli("--help")
        self.assertEqual(top.returncode, 0, top.stderr)
        self.assertIn("work-unit", top.stdout)
        for args in (("work-unit", "--help"), ("work-unit", "list", "--help"),
                     ("work-unit", "status", "--help")):
            proc = self.run_cli(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("work-unit", proc.stdout)


if __name__ == "__main__":
    unittest.main()
