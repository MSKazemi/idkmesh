from __future__ import annotations

import copy
from email.message import Message
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
import unittest

from idkmesh.github_ledger_admission import AdmissionConflict
from idkmesh.github_ledger_github_store import (
    DEFAULT_LEDGER_BRANCH,
    GitHubGitDataConflict,
    GitHubLedgerBranchStore,
    GitHubLedgerRemoteStorageError,
    GitHubRestGitDataTransport,
    GitTreeEntry,
    MARKER_PATH,
)
from idkmesh.github_ledger_serialization import serialize_github_ledger_record


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "github-ledger" / "00000000000000000001.json"
REQUEST_DIGEST = "sha256:" + "c" * 64


def first_record(
    *,
    run_id: str = "run-A",
    dispatch_key: str = "dispatch-key",
    request_digest: str = REQUEST_DIGEST,
) -> dict:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    record = copy.deepcopy(record)
    record["run_id"] = run_id
    record["record_id"] = f"ledger/{run_id}/000001"
    record["event"]["event_id"] = f"event/{run_id}/1"
    record["idempotency"]["dispatch_key"] = dispatch_key
    record["idempotency"]["request_digest"] = request_digest
    return record


def next_record(previous: dict, *, tag: str = "next") -> dict:
    record = copy.deepcopy(previous)
    item = serialize_github_ledger_record(previous)
    record["ledger_sequence"] = previous["ledger_sequence"] + 1
    record["previous_record_digest"] = item.record_digest
    record["record_id"] = f"ledger/{record['run_id']}/{tag}"
    record["event"]["event_id"] = f"event/{record['run_id']}/{tag}"
    record["event"]["state"] = "previewed"
    record["event"]["event_type"] = "run.previewed"
    return record


class MemoryGitDataTransport:
    """Tiny Git object database with fast-forward-only branch updates."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, dict[str, str]] = {}
        self.commits: dict[str, tuple[str, tuple[str, ...], str]] = {}
        self.branches: dict[str, str] = {}
        self.update_calls: list[str] = []
        self.create_branch_calls: list[str] = []
        self.conflict_once = False
        self._counter = 0

    def _sha(self, prefix: str) -> str:
        self._counter += 1
        return hashlib.sha1(f"{prefix}:{self._counter}".encode()).hexdigest()

    def get_branch_head(self, *, repository: str, branch: str) -> str | None:
        return self.branches.get(branch)

    def get_commit_tree(self, *, repository: str, commit_sha: str) -> str:
        return self.commits[commit_sha][0]

    def get_tree(self, *, repository: str, tree_sha: str) -> tuple[GitTreeEntry, ...]:
        return tuple(
            GitTreeEntry(path, "100644", "blob", sha)
            for path, sha in sorted(self.trees[tree_sha].items())
        )

    def get_blob(self, *, repository: str, blob_sha: str) -> bytes:
        return self.blobs[blob_sha]

    def create_blob(self, *, repository: str, content: bytes) -> str:
        sha = self._sha("blob")
        self.blobs[sha] = content
        return sha

    def create_tree(
        self,
        *,
        repository: str,
        base_tree_sha: str | None,
        files: dict[str, str],
    ) -> str:
        tree = dict(self.trees.get(base_tree_sha, {}))
        tree.update(files)
        sha = self._sha("tree")
        self.trees[sha] = tree
        return sha

    def create_commit(
        self,
        *,
        repository: str,
        message: str,
        tree_sha: str,
        parents: tuple[str, ...],
    ) -> str:
        sha = self._sha("commit")
        self.commits[sha] = (tree_sha, tuple(parents), message)
        return sha

    def create_branch(self, *, repository: str, branch: str, commit_sha: str) -> None:
        self.create_branch_calls.append(branch)
        if branch in self.branches:
            raise GitHubGitDataConflict("branch already exists")
        self.branches[branch] = commit_sha

    def update_branch(self, *, repository: str, branch: str, commit_sha: str) -> None:
        self.update_calls.append(branch)
        current = self.branches[branch]
        if self.conflict_once:
            self.conflict_once = False
            tree_sha = self.commits[current][0]
            rival = self.create_commit(
                repository=repository,
                message="synthetic rival",
                tree_sha=tree_sha,
                parents=(current,),
            )
            self.branches[branch] = rival
            raise GitHubGitDataConflict("synthetic race")
        if self.commits[commit_sha][1] != (current,):
            raise GitHubGitDataConflict("non-fast-forward")
        self.branches[branch] = commit_sha


class GitHubLedgerBranchStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = MemoryGitDataTransport()
        self.store = GitHubLedgerBranchStore(
            repository="MSKazemi/idkmesh",
            transport=self.transport,
            default_branch="main",
        )

    def test_initializes_an_orphan_dedicated_branch_only(self) -> None:
        snapshot = self.store.snapshot()
        tree_sha, parents, _message = self.transport.commits[snapshot.commit_sha]
        self.assertEqual(parents, ())
        self.assertEqual(set(self.transport.trees[tree_sha]), {MARKER_PATH})
        self.assertEqual(self.transport.create_branch_calls, [DEFAULT_LEDGER_BRANCH])
        self.assertEqual(self.transport.update_calls, [])
        self.assertNotIn("main", self.transport.branches)

    def test_refuses_default_or_explicitly_protected_application_branch(self) -> None:
        with self.assertRaises(ValueError):
            GitHubLedgerBranchStore(
                repository="MSKazemi/idkmesh",
                transport=self.transport,
                default_branch="main",
                ledger_branch="main",
            )
        with self.assertRaises(ValueError):
            GitHubLedgerBranchStore(
                repository="MSKazemi/idkmesh",
                transport=self.transport,
                default_branch="main",
                ledger_branch="release",
                protected_branches=("release",),
            )

    def test_append_read_and_exact_replay_are_idempotent(self) -> None:
        record = first_record()
        first = self.store.append_record(record)
        before = self.transport.branches[DEFAULT_LEDGER_BRANCH]
        replay = self.store.append_record(record)
        self.assertTrue(first.appended)
        self.assertFalse(replay.appended)
        self.assertEqual(self.transport.branches[DEFAULT_LEDGER_BRANCH], before)
        self.assertEqual(self.store.read_run_records("run-A"), (record,))

    def test_remote_branch_conflict_is_retried_from_a_fresh_snapshot(self) -> None:
        self.store.snapshot()
        self.transport.conflict_once = True
        result = self.store.append_record(first_record())
        self.assertTrue(result.appended)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(self.transport.update_calls, [DEFAULT_LEDGER_BRANCH] * 2)

    def test_builder_rebuilds_next_record_after_a_branch_race(self) -> None:
        self.store.append_record(first_record())
        self.transport.conflict_once = True
        calls = []

        def build(head, records):
            calls.append((head.sequence, len(records)))
            return next_record(records[-1], tag=f"candidate-{len(calls)}")

        result = self.store.append_with_retry("run-A", build)
        self.assertTrue(result.appended)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(calls, [(1, 1), (1, 1)])
        self.assertEqual(len(self.store.read_run_records("run-A")), 2)

    def test_admission_replay_and_conflict_match_c9_d(self) -> None:
        first = self.store.admit_dispatch(first_record(run_id="run-A", dispatch_key="K"))
        duplicate = self.store.admit_dispatch(first_record(run_id="run-B", dispatch_key="K"))
        self.assertTrue(first.created and first.recorded)
        self.assertFalse(duplicate.created)
        self.assertFalse(duplicate.recorded)
        self.assertEqual(duplicate.admission.run_id, "run-A")
        self.assertEqual(self.store.read_run_records("run-B"), ())
        with self.assertRaises(AdmissionConflict):
            self.store.admit_dispatch(
                first_record(
                    run_id="run-A",
                    dispatch_key="K",
                    request_digest="sha256:" + "d" * 64,
                )
            )

    def test_recovery_reads_only_the_durable_branch_records(self) -> None:
        self.store.append_record(first_record())
        recovered = self.store.recover_run("run-A")
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.run_id, "run-A")
        self.assertEqual(recovered.state, "proposed")
        self.assertIsNone(self.store.recover_run("unknown-run"))

    def test_unexpected_blob_on_dedicated_branch_fails_closed(self) -> None:
        snapshot = self.store.snapshot()
        rogue_blob = self.transport.create_blob(
            repository="MSKazemi/idkmesh",
            content=b"secret-or-unowned-data\n",
        )
        tree = self.transport.create_tree(
            repository="MSKazemi/idkmesh",
            base_tree_sha=snapshot.tree_sha,
            files={"README.md": rogue_blob},
        )
        commit = self.transport.create_commit(
            repository="MSKazemi/idkmesh",
            message="rogue",
            tree_sha=tree,
            parents=(snapshot.commit_sha,),
        )
        self.transport.branches[DEFAULT_LEDGER_BRANCH] = commit
        with self.assertRaises(GitHubLedgerRemoteStorageError):
            self.store.snapshot()


class FakeResponse:
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


class FakeOpener:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class GitHubRestGitDataTransportTests(unittest.TestCase):
    def test_branch_update_is_explicitly_fast_forward_only(self) -> None:
        opener = FakeOpener([FakeResponse(b"{}")])
        transport = GitHubRestGitDataTransport(token="secret", opener=opener)
        transport.update_branch(
            repository="MSKazemi/idkmesh",
            branch="idkmesh-ledger",
            commit_sha="a" * 40,
        )
        request, _timeout = opener.calls[0]
        self.assertEqual(request.method, "PATCH")
        self.assertTrue(request.full_url.endswith("/git/refs/heads/idkmesh-ledger"))
        self.assertEqual(
            json.loads(request.data),
            {"sha": "a" * 40, "force": False},
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")

    def test_root_commit_and_dedicated_branch_use_git_data_endpoints(self) -> None:
        opener = FakeOpener(
            [
                FakeResponse(json.dumps({"sha": "1" * 40}).encode(), status=201),
                FakeResponse(json.dumps({"sha": "2" * 40}).encode(), status=201),
            ]
        )
        transport = GitHubRestGitDataTransport(token="secret", opener=opener)
        commit = transport.create_commit(
            repository="MSKazemi/idkmesh",
            message="root",
            tree_sha="3" * 40,
            parents=(),
        )
        transport.create_branch(
            repository="MSKazemi/idkmesh",
            branch="idkmesh-ledger",
            commit_sha=commit,
        )
        commit_request = opener.calls[0][0]
        ref_request = opener.calls[1][0]
        self.assertEqual(json.loads(commit_request.data)["parents"], [])
        self.assertEqual(json.loads(ref_request.data)["ref"], "refs/heads/idkmesh-ledger")
        self.assertTrue(ref_request.full_url.endswith("/git/refs"))

    def test_non_fast_forward_response_is_a_distinct_conflict(self) -> None:
        error = HTTPError(
            "https://api.github.com/synthetic",
            409,
            "conflict",
            Message(),
            None,
        )
        transport = GitHubRestGitDataTransport(
            token="secret-token",
            opener=FakeOpener([error]),
        )
        with self.assertRaises(GitHubGitDataConflict) as caught:
            transport.update_branch(
                repository="MSKazemi/idkmesh",
                branch="idkmesh-ledger",
                commit_sha="a" * 40,
            )
        self.assertNotIn("secret-token", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
