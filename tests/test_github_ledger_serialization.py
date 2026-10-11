from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from jsonschema import Draft202012Validator

from idkmesh.github_ledger_serialization import (
    GitHubLedgerSerializationError,
    serialize_github_ledger_chain,
    serialize_github_ledger_record,
)
from idkmesh.work_unit_binding import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "github-ledger"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
SCHEMA_PATH = ROOT / "schemas" / "github-ledger-record-v0.1.schema.json"


def _record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fixture_records() -> list[dict]:
    return [
        _record(FIXTURE_DIR / item["path"])
        for item in _manifest()["records"]
    ]


def _git(
    cwd: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


class GitHubLedgerSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )

    def test_frozen_fixture_records_validate_the_c9_a_schema(self) -> None:
        for document in _fixture_records():
            with self.subTest(sequence=document["ledger_sequence"]):
                self.validator.validate(document)

    def test_frozen_fixture_bytes_and_digests_are_deterministic(self) -> None:
        manifest = _manifest()
        records = []
        for item in manifest["records"]:
            with self.subTest(path=item["path"]):
                path = FIXTURE_DIR / item["path"]
                document = _record(path)
                rendered = serialize_github_ledger_record(document)
                self.assertEqual(rendered.content, path.read_bytes())
                self.assertEqual(
                    rendered.record_digest,
                    item["record_digest"],
                )
                self.assertEqual(
                    rendered.record_digest,
                    canonical_digest(document),
                )
                records.append(document)

        chain = serialize_github_ledger_chain(records)
        self.assertEqual(
            [item.record_digest for item in chain],
            [item["record_digest"] for item in manifest["records"]],
        )

    def test_key_order_does_not_change_canonical_bytes_or_digest(self) -> None:
        original = _fixture_records()[0]
        reordered = dict(reversed(list(original.items())))
        reordered["routing"] = dict(
            reversed(list(original["routing"].items()))
        )

        expected = serialize_github_ledger_record(original)
        actual = serialize_github_ledger_record(reordered)
        self.assertEqual(actual.content, expected.content)
        self.assertEqual(actual.record_digest, expected.record_digest)

    def test_writer_enforces_cross_field_attempt_number(self) -> None:
        document = _fixture_records()[1]
        document["attempt"]["attempt_number"] = 2
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "attempt_number_mismatch",
        ) as caught:
            serialize_github_ledger_record(document)
        self.assertEqual(
            caught.exception.code,
            "attempt_number_mismatch",
        )

    def test_writer_enforces_attempted_connector_is_selected_route(self) -> None:
        document = _fixture_records()[1]
        document["attempt"]["connector_id"] = "different-connector"
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "attempt_connector_mismatch",
        ) as caught:
            serialize_github_ledger_record(document)
        self.assertEqual(
            caught.exception.code,
            "attempt_connector_mismatch",
        )

    def test_writer_rejects_non_schema_float_before_serialization(self) -> None:
        document = _fixture_records()[0]
        document["routing"]["experimental_score"] = 0.5
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "non_canonical_number",
        ):
            serialize_github_ledger_record(document)

    def test_writer_requires_exact_all_false_authority_ceiling(self) -> None:
        document = _fixture_records()[0]
        del document["authority"]["merge"]
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "authority_forbidden",
        ):
            serialize_github_ledger_record(document)

        document = _fixture_records()[0]
        document["authority"]["merge"] = True
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "authority_forbidden",
        ):
            serialize_github_ledger_record(document)

    def test_complete_chain_rejects_gap_or_wrong_previous_digest(self) -> None:
        first, second = _fixture_records()

        gap = copy.deepcopy(second)
        gap["ledger_sequence"] = 3
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "sequence_gap",
        ):
            serialize_github_ledger_chain([first, gap])

        wrong_link = copy.deepcopy(second)
        wrong_link["previous_record_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "previous_digest_mismatch",
        ):
            serialize_github_ledger_chain([first, wrong_link])

    def test_complete_chain_rejects_identity_change_and_duplicate_event(
        self,
    ) -> None:
        first, second = _fixture_records()

        identity_changed = copy.deepcopy(second)
        identity_changed["run_id"] = "github-ledger-fixture/other-run"
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "chain_identity_changed",
        ):
            serialize_github_ledger_chain([first, identity_changed])

        duplicate = copy.deepcopy(second)
        duplicate["event"]["event_id"] = first["event"]["event_id"]
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "duplicate_event_id",
        ):
            serialize_github_ledger_chain([first, duplicate])

    def test_complete_chain_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(
            GitHubLedgerSerializationError,
            "empty_chain",
        ):
            serialize_github_ledger_chain([])

    @unittest.skipUnless(
        shutil.which("git"),
        "Git executable is required",
    )
    def test_local_git_fixture_second_commit_only_appends_next_record(
        self,
    ) -> None:
        first, second = _fixture_records()
        first_bytes = serialize_github_ledger_record(first).content
        second_bytes = serialize_github_ledger_record(second).content
        first_name = "00000000000000000001.json"
        second_name = "00000000000000000002.json"

        with tempfile.TemporaryDirectory() as raw_directory:
            repo = Path(raw_directory)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.name", "IDKMesh fixture")
            _git(
                repo,
                "config",
                "user.email",
                "fixture@idkmesh.invalid",
            )
            records = repo / "records"
            records.mkdir()

            fixed_env = os.environ.copy()
            fixed_env.update(
                {
                    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
                    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
                }
            )

            (records / first_name).write_bytes(first_bytes)
            _git(repo, "add", f"records/{first_name}")
            _git(
                repo,
                "commit",
                "-q",
                "-m",
                "fixture: append record 1",
                env=fixed_env,
            )
            first_commit = _git(
                repo,
                "rev-parse",
                "HEAD",
            ).decode().strip()

            (records / second_name).write_bytes(second_bytes)
            _git(repo, "add", f"records/{second_name}")
            _git(
                repo,
                "commit",
                "-q",
                "-m",
                "fixture: append record 2",
                env=fixed_env,
            )
            second_commit = _git(
                repo,
                "rev-parse",
                "HEAD",
            ).decode().strip()

            changed = _git(
                repo,
                "diff",
                "--name-status",
                first_commit,
                second_commit,
            ).decode()
            self.assertEqual(
                changed,
                f"A\trecords/{second_name}\n",
            )
            self.assertEqual(
                _git(
                    repo,
                    "show",
                    f"{first_commit}:records/{first_name}",
                ),
                first_bytes,
            )
            self.assertEqual(
                _git(
                    repo,
                    "show",
                    f"{second_commit}:records/{first_name}",
                ),
                first_bytes,
            )


if __name__ == "__main__":
    unittest.main()
