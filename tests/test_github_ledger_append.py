"""C9-C optimistic append protocol, proven against real Git (issue #597).

Every test drives a real bare repository through ``git`` plumbing: a stale
writer loses, concurrent writers all land without losing an update, history only
grows, and a failed append leaves the ref where it was.

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

from idkmesh.github_ledger_append import (
    EMPTY_HEAD,
    GitLedger,
    LedgerConflict,
    LedgerConflictExhausted,
    LedgerHead,
)
from idkmesh.github_ledger_serialization import (
    GitHubLedgerSerializationError,
    serialize_github_ledger_record,
)

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
REF = "refs/idkmesh/ledger/run-fixture-001"
GIT = shutil.which("git")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def record_after(head: LedgerHead, tag: str) -> dict:
    """The next valid record for ``head``, distinguishable by ``tag``."""

    record = copy.deepcopy(_fixture("00000000000000000002.json"))
    if head.sequence == 0:
        record = copy.deepcopy(_fixture("00000000000000000001.json"))
        record["record_id"] = f"ledger/run-fixture-001/{tag}"
        record["event"]["event_id"] = f"fixture/event-{tag}"
        return record
    record["ledger_sequence"] = head.sequence + 1
    record["previous_record_digest"] = head.record_digest
    record["record_id"] = f"ledger/run-fixture-001/{tag}"
    record["event"]["event_id"] = f"fixture/event-{tag}"
    return record


@unittest.skipUnless(GIT, "git is required")
class LedgerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-ledger-")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "ledger.git"
        # Empty template: no inherited hooks, so the fixture is hermetic.
        subprocess.run([GIT, "init", "-q", "--bare", "--template=", str(self.repo)], check=True)
        self.ledger = self.make_ledger()

    def make_ledger(self) -> GitLedger:
        return GitLedger(
            self.repo, REF, author_name="IDKMesh ledger", author_email="ledger@idkmesh.invalid"
        )

    def ref_commit(self):
        done = subprocess.run(
            [GIT, "-C", str(self.repo), "rev-parse", "--verify", "-q", REF],
            capture_output=True, text=True,
        )
        return done.stdout.strip() or None

    def git(self, *args):
        return subprocess.run(
            [GIT, "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout


class AppendTests(LedgerCase):
    def test_an_empty_ledger_has_the_empty_head(self):
        self.assertEqual(self.ledger.head(), EMPTY_HEAD)
        self.assertEqual(self.ledger.read_records(), ())

    def test_records_append_in_order_and_read_back_as_a_verified_chain(self):
        head = self.ledger.head()
        for tag in ("a", "b", "c"):
            head = self.ledger.append(record_after(head, tag), expected=head)
        self.assertEqual(head.sequence, 3)
        records = self.ledger.read_records()
        self.assertEqual([r["ledger_sequence"] for r in records], [1, 2, 3])
        self.assertEqual(
            head.record_digest, serialize_github_ledger_record(records[-1]).record_digest
        )

    def test_history_is_linear_and_only_ever_extended(self):
        head = self.ledger.head()
        commits = []
        for tag in ("a", "b", "c"):
            head = self.ledger.append(record_after(head, tag), expected=head)
            commits.append(head.commit)
        chain = self.git("rev-list", "--reverse", REF).split()
        self.assertEqual(chain, commits)
        for older, newer in zip(commits, commits[1:]):
            self.git("merge-base", "--is-ancestor", older, newer)  # raises if not
        self.assertEqual(self.git("rev-list", "--merges", "--count", REF).strip(), "0")

    def test_each_commit_adds_exactly_one_record_and_rewrites_none(self):
        head = self.ledger.head()
        head = self.ledger.append(record_after(head, "a"), expected=head)
        first_blob = self.git("rev-parse", f"{head.commit}:records/{1:020d}.json").strip()
        head = self.ledger.append(record_after(head, "b"), expected=head)
        names = self.git("ls-tree", "--name-only", f"{head.commit}:records").split()
        self.assertEqual(names, [f"{1:020d}.json", f"{2:020d}.json"])
        self.assertEqual(
            self.git("rev-parse", f"{head.commit}:records/{1:020d}.json").strip(), first_blob
        )


class ConflictTests(LedgerCase):
    def test_a_stale_writer_loses_and_leaves_the_winners_record_alone(self):
        stale = self.ledger.head()  # both writers read the empty ledger
        winner = self.ledger.append(record_after(stale, "winner"), expected=stale)
        with self.assertRaises(LedgerConflict) as caught:
            self.ledger.append(record_after(stale, "loser"), expected=stale)
        self.assertEqual(caught.exception.code, "head_conflict")
        self.assertEqual(caught.exception.actual_commit, winner.commit)
        self.assertEqual(self.ref_commit(), winner.commit)
        self.assertEqual(
            [r["record_id"] for r in self.ledger.read_records()],
            ["ledger/run-fixture-001/winner"],
        )

    def test_the_underlying_ref_update_is_the_atomic_guard(self):
        # Bypass the pre-check: move the ref between snapshot and update.
        original = self.ledger.snapshot
        calls = {"n": 0}

        def racing_snapshot():
            snap = original()
            calls["n"] += 1
            if calls["n"] == 1:  # first read inside append(); then someone else wins
                other = self.make_ledger()
                other.append(record_after(snap.head, "sneaky"), expected=snap.head)
            return snap

        self.ledger.snapshot = racing_snapshot
        with self.assertRaises(LedgerConflict):
            self.ledger.append(record_after(EMPTY_HEAD, "late"), expected=EMPTY_HEAD)
        self.ledger.snapshot = original
        self.assertEqual(
            [r["record_id"] for r in self.ledger.read_records()],
            ["ledger/run-fixture-001/sneaky"],
        )

    @slow
    def test_concurrent_writers_all_land_without_losing_an_update(self):
        writers = 4
        barrier = threading.Barrier(writers)
        results, errors = [], []

        def write(index):
            ledger = self.make_ledger()
            barrier.wait()
            try:
                results.append(
                    ledger.append_with_retry(lambda head, _r: record_after(head, f"w{index}"))
                )
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(errors, [])
        records = self.ledger.read_records()
        self.assertEqual([r["ledger_sequence"] for r in records], list(range(1, writers + 1)))
        self.assertEqual(
            {r["record_id"] for r in records},
            {f"ledger/run-fixture-001/w{i}" for i in range(writers)},
        )
        self.assertTrue(all(r.appended for r in results))
        # With four racers released together at least one loses a race and retries.
        self.assertGreater(max(r.attempts for r in results), 1)

    @slow
    def test_retry_is_bounded(self):
        interfering = self.make_ledger()

        def always_loses(head, _records):
            # A rival lands between this writer's read and its append, every time.
            interfering.append(record_after(head, f"rival{head.sequence}"), expected=head)
            return record_after(head, "mine")

        with self.assertRaises(LedgerConflictExhausted):
            self.ledger.append_with_retry(always_loses, max_attempts=3)
        self.assertEqual(len(self.ledger.read_records()), 3)  # only the rivals

    def test_a_builder_may_decide_there_is_nothing_left_to_write(self):
        head = self.ledger.head()
        self.ledger.append(record_after(head, "a"), expected=head)
        result = self.ledger.append_with_retry(lambda _h, _r: None)
        self.assertFalse(result.appended)
        self.assertEqual(len(self.ledger.read_records()), 1)

    def test_max_attempts_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.ledger.append_with_retry(lambda *_: None, max_attempts=0)


class FailClosedTests(LedgerCase):
    def test_an_invalid_record_writes_nothing(self):
        head = self.ledger.head()
        head = self.ledger.append(record_after(head, "a"), expected=head)
        bad = record_after(head, "bad")
        bad["authority"]["merge"] = True
        before = self.ref_commit()
        with self.assertRaises(GitHubLedgerSerializationError):
            self.ledger.append(bad, expected=head)
        self.assertEqual(self.ref_commit(), before)

    def test_a_record_that_does_not_extend_the_chain_is_rejected(self):
        head = self.ledger.head()
        head = self.ledger.append(record_after(head, "a"), expected=head)
        broken = record_after(head, "b")
        broken["previous_record_digest"] = "sha256:" + "0" * 64
        before = self.ref_commit()
        with self.assertRaises(GitHubLedgerSerializationError):
            self.ledger.append(broken, expected=head)
        self.assertEqual(self.ref_commit(), before)

    def test_a_tampered_stored_record_is_detected_on_read(self):
        head = self.ledger.head()
        self.ledger.append(record_after(head, "a"), expected=head)
        head = self.ledger.head()
        self.ledger.append(record_after(head, "b"), expected=head)
        # Rewrite record 1 in a new commit chain the ledger did not produce.
        forged = copy.deepcopy(self.ledger.read_records()[0])
        forged["event"]["event_id"] = "forged"
        blob = subprocess.run(
            [GIT, "-C", str(self.repo), "hash-object", "-w", "--stdin"],
            input=json.dumps(forged), capture_output=True, text=True, check=True,
        ).stdout.strip()
        second = self.git("rev-parse", f"{REF}:records/{2:020d}.json").strip()
        sub = subprocess.run(
            [GIT, "-C", str(self.repo), "mktree"],
            input=f"100644 blob {blob}\t{1:020d}.json\n100644 blob {second}\t{2:020d}.json\n",
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        root = subprocess.run(
            [GIT, "-C", str(self.repo), "mktree"],
            input=f"040000 tree {sub}\trecords\n", capture_output=True, text=True, check=True,
        ).stdout.strip()
        env = {"GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x",
               "GIT_COMMITTER_EMAIL": "x@x", "PATH": "/usr/bin:/bin"}
        commit = subprocess.run(
            [GIT, "-C", str(self.repo), "commit-tree", root, "-p", self.ref_commit(), "-m", "forged"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout.strip()
        self.git("update-ref", REF, commit)
        with self.assertRaises(GitHubLedgerSerializationError):
            self.ledger.snapshot()

    def test_the_ref_must_live_under_the_ledger_namespace(self):
        for bad in ("refs/heads/main", "refs/idkmesh/ledger/", "refs/idkmesh/ledger/../x",
                    "refs/idkmesh/ledger/a.lock", "main"):
            with self.subTest(ref=bad):
                with self.assertRaises(ValueError):
                    GitLedger(self.repo, bad, author_name="a", author_email="a@a")

    def test_an_author_is_required(self):
        with self.assertRaises(ValueError):
            GitLedger(self.repo, REF, author_name=" ", author_email="a@a")


if __name__ == "__main__":
    unittest.main()
