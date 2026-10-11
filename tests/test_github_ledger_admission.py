"""C9-D idempotent admission, proven against real Git (issue #597).

Duplicate dispatch must resolve to the one run admitted first, whether the
duplicate arrives later, concurrently, or after a crash between admission and the
first ledger record.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

import idkmesh.github_ledger_admission as admission_module
from idkmesh.github_ledger_admission import (
    Admission,
    AdmissionConflict,
    AdmissionInvalid,
    _create_admission,
    admission_ref,
    admit_dispatch,
)
from idkmesh.github_ledger_append import (
    GitLedger,
    LedgerStorageError,
    ledger_ref_for_run,
)
from idkmesh.github_ledger_serialization import GitHubLedgerSerializationError

# The statistical concurrency tests are marked `slow` (nightly tier): each one
# spawns hundreds of git processes and the unit tier has almost no CPU headroom.
# The deterministic race proof (a ref moved between snapshot and update) stays in
# the per-PR tier. As in tests/test_benchmark_publication.py the marker is a tier
# hint only: without pytest it degrades to a no-op instead of failing collection.
if importlib.util.find_spec("pytest") is not None:
    import pytest

    slow = pytest.mark.slow
else:  # pragma: no cover - exercised only where pytest is absent

    def slow(obj):
        return obj

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github-ledger"
GIT = shutil.which("git")
AUTHOR = {"author_name": "IDKMesh ledger", "author_email": "ledger@idkmesh.invalid"}
KEY = "dispatch:github/mskazemi/idkmesh/issue-597:1:attempt-1"
DIGEST = "sha256:" + "c" * 64


def first_record(run_id="run-A", key=KEY, digest=DIGEST) -> dict:
    record = json.loads((FIXTURES / "00000000000000000001.json").read_text(encoding="utf-8"))
    record = copy.deepcopy(record)
    record["run_id"] = run_id
    record["record_id"] = f"ledger/{run_id}/000001"
    record["event"]["event_id"] = f"event/{run_id}/1"
    record["idempotency"]["dispatch_key"] = key
    record["idempotency"]["request_digest"] = digest
    return record


@unittest.skipUnless(GIT, "git is required")
class AdmissionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-admission-")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "ledger.git"
        subprocess.run([GIT, "init", "-q", "--bare", "--template=", str(self.repo)], check=True)

    def git(self, *args):
        return subprocess.run(
            [GIT, "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout

    def refs(self, prefix):
        return [r.split()[-1] for r in self.git("for-each-ref", prefix).splitlines()]

    def ref_commit(self, ref):
        done = subprocess.run(
            [GIT, "-C", str(self.repo), "rev-parse", "--verify", "-q", ref],
            capture_output=True, text=True,
        )
        return done.stdout.strip() or None

    def admit(self, record):
        return admit_dispatch(self.repo, record, **AUTHOR)


class AdmitTests(AdmissionCase):
    def test_first_arrival_creates_the_admission_and_the_first_record(self):
        result = self.admit(first_record())
        self.assertTrue(result.created)
        self.assertTrue(result.recorded)
        self.assertEqual(result.admission.run_id, "run-A")
        self.assertEqual(result.admission.ledger_ref, ledger_ref_for_run("run-A"))
        self.assertEqual(result.head.sequence, 1)
        ledger = GitLedger(self.repo, result.admission.ledger_ref, **{
            "author_name": "x", "author_email": "x@x"})
        self.assertEqual([r["run_id"] for r in ledger.read_records()], ["run-A"])

    def test_exact_replay_returns_the_existing_run_and_writes_nothing(self):
        first = self.admit(first_record())
        admission_commit = self.ref_commit(admission_ref(KEY))
        ledger_commit = self.ref_commit(first.admission.ledger_ref)
        replay = self.admit(first_record())
        self.assertFalse(replay.created)
        self.assertFalse(replay.recorded)
        self.assertEqual(replay.admission, first.admission)
        self.assertEqual(replay.head, first.head)
        self.assertEqual(self.ref_commit(admission_ref(KEY)), admission_commit)
        self.assertEqual(self.ref_commit(first.admission.ledger_ref), ledger_commit)

    def test_a_duplicate_for_another_run_resolves_to_the_first_run(self):
        first = self.admit(first_record(run_id="run-A"))
        duplicate = self.admit(first_record(run_id="run-B"))
        self.assertFalse(duplicate.created)
        self.assertEqual(duplicate.admission.run_id, "run-A")
        self.assertIsNone(self.ref_commit(ledger_ref_for_run("run-B")))
        self.assertEqual(self.refs("refs/idkmesh/ledger/"), [first.admission.ledger_ref])

    def test_a_create_that_loses_a_race_returns_the_winner_without_overwriting(self):
        # Deterministic stand-in for two admitters racing: this one's read saw no
        # admission, but another admitter created it before this one's create.
        # Only the compare-and-set against the all-zero id stands between this
        # call and silently replacing the first run.
        first = self.admit(first_record(run_id="run-A"))
        admission_commit = self.ref_commit(admission_ref(KEY))
        real_read = admission_module._read_admission
        calls = {"n": 0}

        def stale_first_read(repo, ref):
            calls["n"] += 1
            return None if calls["n"] == 1 else real_read(repo, ref)

        admission_module._read_admission = stale_first_read
        try:
            late = self.admit(first_record(run_id="run-B"))
        finally:
            admission_module._read_admission = real_read
        self.assertFalse(late.created)
        self.assertEqual(late.admission.run_id, "run-A")
        self.assertEqual(self.ref_commit(admission_ref(KEY)), admission_commit)
        self.assertEqual(late.head, first.head)

    def test_the_same_key_with_a_different_request_fails_closed(self):
        first = self.admit(first_record())
        before = (self.ref_commit(admission_ref(KEY)), self.ref_commit(first.admission.ledger_ref))
        with self.assertRaises(AdmissionConflict) as caught:
            self.admit(first_record(digest="sha256:" + "d" * 64))
        self.assertEqual(caught.exception.code, "admission_conflict")
        after = (self.ref_commit(admission_ref(KEY)), self.ref_commit(first.admission.ledger_ref))
        self.assertEqual(before, after)

    def test_different_keys_admit_independently(self):
        a = self.admit(first_record(run_id="run-A", key=KEY + "-a"))
        b = self.admit(first_record(run_id="run-B", key=KEY + "-b"))
        self.assertTrue(a.created and b.created)
        self.assertEqual(len(self.refs("refs/idkmesh/admissions/")), 2)
        self.assertEqual(len(self.refs("refs/idkmesh/ledger/")), 2)


@slow
class ConcurrencyTests(AdmissionCase):
    def race(self, records):
        barrier = threading.Barrier(len(records))
        results, errors = [], []

        def run(record):
            barrier.wait()
            try:
                results.append(admit_dispatch(self.repo, record, **AUTHOR))
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(r,)) for r in records]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(errors, [])
        return results

    def test_concurrent_duplicates_admit_exactly_one_run(self):
        results = self.race([first_record(run_id=f"run-{i}") for i in range(4)])
        self.assertEqual(sum(r.created for r in results), 1)
        self.assertEqual(len({r.admission.run_id for r in results}), 1)
        winner = results[0].admission
        self.assertEqual(self.refs("refs/idkmesh/ledger/"), [winner.ledger_ref])
        records = GitLedger(self.repo, winner.ledger_ref, author_name="x", author_email="x@x").read_records()
        self.assertEqual(len(records), 1)

    def test_concurrent_exact_replays_record_the_first_entry_once(self):
        results = self.race([first_record() for _ in range(4)])
        self.assertEqual(sum(r.created for r in results), 1)
        self.assertEqual(sum(r.recorded for r in results), 1)
        ledger = GitLedger(self.repo, results[0].admission.ledger_ref, author_name="x", author_email="x@x")
        self.assertEqual(len(ledger.read_records()), 1)
        self.assertEqual(self.git("rev-list", "--count", results[0].admission.ledger_ref).strip(), "1")


class RecoveryTests(AdmissionCase):
    def crash_after_admission(self, record):
        """Admission created, process died before the first ledger record."""

        item = record["idempotency"]
        admission = Admission(item["dispatch_key"], item["request_digest"], record["run_id"],
                              ledger_ref_for_run(record["run_id"]))
        self.assertTrue(_create_admission(
            self.repo, admission_ref(item["dispatch_key"]), admission, ("x", "x@x")))
        return admission

    def test_a_replay_completes_the_first_record_after_a_crash(self):
        admission = self.crash_after_admission(first_record())
        self.assertIsNone(self.ref_commit(admission.ledger_ref))
        replay = self.admit(first_record())
        self.assertFalse(replay.created)
        self.assertTrue(replay.recorded)
        self.assertEqual(replay.head.sequence, 1)
        again = self.admit(first_record())
        self.assertFalse(again.recorded)
        self.assertEqual(again.head, replay.head)

    def test_a_duplicate_for_another_run_does_not_complete_someone_elses_run(self):
        admission = self.crash_after_admission(first_record(run_id="run-A"))
        other = self.admit(first_record(run_id="run-B"))
        self.assertFalse(other.recorded)
        self.assertEqual(other.admission.run_id, "run-A")
        self.assertIsNone(self.ref_commit(admission.ledger_ref))
        self.assertIsNone(self.ref_commit(ledger_ref_for_run("run-B")))


class FailClosedTests(AdmissionCase):
    def test_only_a_sequence_one_record_can_open_a_run(self):
        record = json.loads((FIXTURES / "00000000000000000002.json").read_text(encoding="utf-8"))
        with self.assertRaises(AdmissionInvalid):
            self.admit(record)
        self.assertEqual(self.refs("refs/idkmesh/"), [])

    def test_a_record_that_enables_authority_creates_nothing(self):
        record = first_record()
        record["authority"]["dispatch"] = True
        with self.assertRaises(GitHubLedgerSerializationError):
            self.admit(record)
        self.assertEqual(self.refs("refs/idkmesh/"), [])

    def test_a_malformed_stored_admission_is_a_storage_error_not_a_guess(self):
        self.admit(first_record())
        ref = admission_ref(KEY)
        blob = subprocess.run(
            [GIT, "-C", str(self.repo), "hash-object", "-w", "--stdin"],
            input='{"kind":"nope"}', capture_output=True, text=True, check=True).stdout.strip()
        tree = subprocess.run(
            [GIT, "-C", str(self.repo), "mktree"], input=f"100644 blob {blob}\tadmission.json\n",
            capture_output=True, text=True, check=True).stdout.strip()
        env = {"GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x",
               "GIT_COMMITTER_EMAIL": "x@x", "PATH": "/usr/bin:/bin"}
        commit = subprocess.run(
            [GIT, "-C", str(self.repo), "commit-tree", tree, "-m", "bad"],
            capture_output=True, text=True, check=True, env=env).stdout.strip()
        self.git("update-ref", ref, commit)
        with self.assertRaises(LedgerStorageError):
            self.admit(first_record())

    def test_an_author_is_required(self):
        with self.assertRaises(ValueError):
            admit_dispatch(self.repo, first_record(), author_name="", author_email="a@a")


if __name__ == "__main__":
    unittest.main()
