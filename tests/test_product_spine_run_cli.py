import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"


def _projection(**overrides):
    value = {
        "schema_version": "0.1",
        "kind": "idkmesh-product-spine-run",
        "run_id": "run/cli-1",
        "request_digest": "sha256:" + "a" * 64,
        "project_id": "project.test",
        "work_unit": {
            "id": "work/test-1",
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
    for key, child in overrides.items():
        if key in {"work_unit", "routing", "authority"}:
            value[key].update(child)
        else:
            value[key] = child
    return value


class ProductSpineRunCliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, "-m", "idkmesh.cli", *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )

    def write_projection(self, directory, data=None):
        path = Path(directory) / "run.json"
        path.write_text(
            json.dumps(
                _projection() if data is None else data,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def test_run_create_and_status_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = self.write_projection(tmp)
            store = Path(tmp) / "state.sqlite"

            created = self.run_cli(
                "run",
                "create",
                str(projection),
                "--store",
                str(store),
                "--idempotency-key",
                "request-1",
                "--created-at",
                "2026-09-24T15:30:00Z",
            )
            status = self.run_cli(
                "run",
                "status",
                "run/cli-1",
                "--store",
                str(store),
            )

        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIn(
            "created: run/cli-1 state=proposed",
            created.stdout,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("run: run/cli-1", status.stdout)
        self.assertIn("state: proposed", status.stdout)
        self.assertIn("project: project.test", status.stdout)
        self.assertIn("merge_authority: no", status.stdout)

    def test_exact_create_replay_is_deterministic_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = self.write_projection(tmp)
            store = Path(tmp) / "state.sqlite"
            args = (
                "run",
                "create",
                str(projection),
                "--store",
                str(store),
                "--idempotency-key",
                "request-1",
                "--created-at",
                "2026-09-24T15:30:00Z",
                "--json",
            )
            first = self.run_cli(*args)
            second = self.run_cli(*args)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
        self.assertTrue(first_payload["created"])
        self.assertFalse(first_payload["replayed"])
        self.assertFalse(second_payload["created"])
        self.assertTrue(second_payload["replayed"])
        self.assertEqual(
            first_payload["run"],
            second_payload["run"],
        )
        self.assertFalse(
            second_payload["provider_execution_terminated"]
        )
        self.assertFalse(second_payload["candidate_accepted"])
        self.assertFalse(second_payload["merge_authority"])

    def test_run_cancel_uses_lifecycle_and_does_not_claim_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = self.write_projection(tmp)
            store = Path(tmp) / "state.sqlite"
            created = self.run_cli(
                "run",
                "create",
                str(projection),
                "--store",
                str(store),
                "--idempotency-key",
                "request-1",
                "--created-at",
                "2026-09-24T15:30:00Z",
            )
            self.assertEqual(
                created.returncode,
                0,
                created.stderr,
            )
            cancelled = self.run_cli(
                "run",
                "cancel",
                "run/cli-1",
                "--store",
                str(store),
                "--updated-at",
                "2026-09-24T15:31:00Z",
            )
            status = self.run_cli(
                "run",
                "status",
                "run/cli-1",
                "--store",
                str(store),
                "--json",
            )

        self.assertEqual(
            cancelled.returncode,
            0,
            cancelled.stderr,
        )
        self.assertIn(
            "provider_execution_terminated: no",
            cancelled.stdout,
        )
        self.assertIn("merge_authority: no", cancelled.stdout)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["run"]["state"], "cancelled")
        self.assertFalse(
            payload["provider_execution_terminated"]
        )

    def test_create_requires_proposed_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = self.write_projection(
                tmp,
                _projection(state="previewed"),
            )
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli(
                "run",
                "create",
                str(projection),
                "--store",
                str(store),
                "--idempotency-key",
                "request-1",
                "--created-at",
                "2026-09-24T15:30:00Z",
                "--json",
            )

        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(
            payload["error"]["code"],
            "create_requires_proposed",
        )

    def test_changed_projection_under_same_key_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "state.sqlite"
            first_path = Path(tmp) / "first.json"
            second_path = Path(tmp) / "second.json"
            first_path.write_text(
                json.dumps(_projection()),
                encoding="utf-8",
            )
            second_path.write_text(
                json.dumps(
                    _projection(
                        project_id="project.changed"
                    )
                ),
                encoding="utf-8",
            )
            first = self.run_cli(
                "run",
                "create",
                str(first_path),
                "--store",
                str(store),
                "--idempotency-key",
                "same-key",
                "--created-at",
                "2026-09-24T15:30:00Z",
            )
            second = self.run_cli(
                "run",
                "create",
                str(second_path),
                "--store",
                str(store),
                "--idempotency-key",
                "same-key",
                "--created-at",
                "2026-09-24T15:31:00Z",
                "--json",
            )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 2)
        payload = json.loads(second.stderr)
        self.assertEqual(
            payload["error"]["code"],
            "idempotency_conflict",
        )

    def test_strict_json_rejects_duplicate_keys_and_nonstandard_numbers(self):
        documents = (
            (
                '{"schema_version":"0.1","schema_version":"0.1"}',
                "duplicate JSON key",
            ),
            (
                '{"schema_version":NaN}',
                "non-standard JSON constant",
            ),
        )
        for text, expected in documents:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as tmp:
                    projection = Path(tmp) / "run.json"
                    projection.write_text(
                        text,
                        encoding="utf-8",
                    )
                    proc = self.run_cli(
                        "run",
                        "create",
                        str(projection),
                        "--store",
                        str(Path(tmp) / "state.sqlite"),
                        "--idempotency-key",
                        "request-1",
                        "--json",
                    )
                self.assertEqual(proc.returncode, 2)
                payload = json.loads(proc.stderr)
                self.assertEqual(
                    payload["error"]["code"],
                    "run_control_error",
                )
                self.assertIn(
                    expected,
                    payload["error"]["message"],
                )

    def test_missing_projection_and_unknown_run_have_stable_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = self.run_cli(
                "run",
                "create",
                str(Path(tmp) / "missing.json"),
                "--store",
                str(Path(tmp) / "state.sqlite"),
                "--idempotency-key",
                "request-1",
                "--json",
            )
            unknown = self.run_cli(
                "run",
                "status",
                "run/missing",
                "--store",
                str(Path(tmp) / "state.sqlite"),
                "--json",
            )

        self.assertEqual(missing.returncode, 2)
        self.assertEqual(
            json.loads(missing.stderr)["error"]["code"],
            "run_control_error",
        )
        self.assertEqual(unknown.returncode, 2)
        self.assertEqual(
            json.loads(unknown.stderr)["error"]["code"],
            "run_not_found",
        )

    def test_invalid_timestamp_fails_before_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection = self.write_projection(tmp)
            store = Path(tmp) / "state.sqlite"
            proc = self.run_cli(
                "run",
                "create",
                str(projection),
                "--store",
                str(store),
                "--idempotency-key",
                "request-1",
                "--created-at",
                "not-a-time",
                "--json",
            )

        self.assertEqual(proc.returncode, 2)
        self.assertEqual(
            json.loads(proc.stderr)["error"]["code"],
            "invalid_timestamp",
        )

    def test_run_help_states_bounded_non_dispatch_authority(self):
        proc = self.run_cli("run", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("create", proc.stdout)
        self.assertIn("status", proc.stdout)
        self.assertIn("cancel", proc.stdout)
        self.assertIn("do not dispatch providers", proc.stdout)


if __name__ == "__main__":
    unittest.main()
