import contextlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest

from idkmesh import cli


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"


def _projection(run_id, *, project_id, wu="work/a"):
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


class ProjectCliTests(unittest.TestCase):
    def run_cli(self, *args):
        """Run the CLI in-process (cheaper than a fresh interpreter per call).

        Returns an object with ``returncode``, ``stdout`` and ``stderr``, like
        ``subprocess.CompletedProcess``. argparse's ``--help`` and usage errors
        raise SystemExit, which is turned into the return code.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (
                    0 if exc.code is None else 1)
        return types.SimpleNamespace(
            returncode=code, stdout=out.getvalue(), stderr=err.getvalue())

    def create(self, tmp, store, index, **kwargs):
        path = Path(tmp) / f"projection-{index}.json"
        path.write_text(json.dumps(_projection(f"run/p-{index}", **kwargs)))
        proc = self.run_cli(
            "run", "create", str(path), "--store", str(store),
            "--idempotency-key", f"p-key-{index}",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def populated(self, tmp):
        store = Path(tmp) / "state.sqlite"
        specs = (
            dict(project_id="project.alpha", wu="work/a"),
            dict(project_id="project.alpha", wu="work/b"),
            dict(project_id="project.alpha", wu="work/a"),
            dict(project_id="project.alpha-2", wu="work/z"),
            dict(project_id="project.beta", wu="work/a"),
        )
        for index, spec in enumerate(specs):
            self.create(tmp, store, index, **spec)
        return store

    def test_status_reports_counts_by_state_and_distinct_work_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "project", "status", "project.alpha", "--store", str(store)
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = proc.stdout.splitlines()
            self.assertEqual(
                lines,
                [
                    "project: project.alpha",
                    "runs: 3",
                    "work_units: 2",
                    "proposed: 3",
                ],
            )

    def test_json_payload_is_compact_sorted_and_zero_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            proc = self.run_cli(
                "project", "status", "project.alpha", "--store", str(store),
                "--json",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(
                set(payload),
                {"project_id", "run_count", "runs_by_state", "work_unit_count"},
            )
            self.assertEqual(payload["run_count"], 3)
            self.assertEqual(payload["work_unit_count"], 2)
            self.assertEqual(len(payload["runs_by_state"]), 14)
            self.assertEqual(payload["runs_by_state"]["proposed"], 3)
            self.assertEqual(
                sum(payload["runs_by_state"].values()), payload["run_count"]
            )
            self.assertEqual(payload["runs_by_state"]["cancelled"], 0)
            self.assertEqual(
                proc.stdout.strip(),
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )

    def test_similarly_named_projects_are_not_confused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            for project_id, runs in (
                ("project.alpha", 3),
                ("project.alpha-2", 1),
                ("project.beta", 1),
            ):
                proc = self.run_cli(
                    "project", "status", project_id, "--store", str(store),
                    "--json",
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(json.loads(proc.stdout)["run_count"], runs)
            proc = self.run_cli(
                "project", "status", "project.alp", "--store", str(store)
            )
            self.assertEqual(proc.returncode, 2)

    def test_unknown_project_exits_2_with_a_stable_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.populated(tmp)
            text = self.run_cli(
                "project", "status", "project.missing", "--store", str(store)
            )
            self.assertEqual(text.returncode, 2)
            self.assertEqual(text.stdout, "")
            self.assertIn("project_not_found", text.stderr)
            machine = self.run_cli(
                "project", "status", "project.missing", "--store", str(store),
                "--json",
            )
            self.assertEqual(machine.returncode, 2)
            self.assertEqual(machine.stdout, "")
            self.assertEqual(
                json.loads(machine.stderr)["error"]["code"],
                "project_not_found",
            )

    def test_fresh_store_has_no_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "project", "status", "project.alpha",
                "--store", str(Path(tmp) / "state.sqlite"), "--json",
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(
                json.loads(proc.stderr)["error"]["code"], "project_not_found"
            )

    def test_help_lists_the_project_commands(self):
        top = self.run_cli("--help")
        self.assertEqual(top.returncode, 0, top.stderr)
        self.assertIn("project", top.stdout)
        for args in (("project", "--help"), ("project", "status", "--help")):
            proc = self.run_cli(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--store", self.run_cli("project", "status", "--help").stdout)


if __name__ == "__main__":
    unittest.main()
