"""Optimistic, compare-and-set append for the C9 GitHub-native durable ledger.

C9-B made one record, and a whole chain of records, deterministic and
verifiable. This module (C9-C) answers the next question: what happens when two
writers append to the same run's ledger at once? Git already has the right
primitive. ``git update-ref <ref> <new> <old>`` moves a ref only if it still
points at ``<old>``, atomically, so a writer that read a stale head loses
cleanly instead of overwriting the winner.

The protocol:

1. read a snapshot of the ledger (head commit plus every record, verified as a
   complete chain by :func:`serialize_github_ledger_chain`);
2. build the next record from that snapshot;
3. verify ``snapshot records + new record`` is still a valid chain, write the
   objects, and move the ref **only if it still points at the snapshot head**;
4. on a lost race raise :class:`LedgerConflict` carrying the actual head, and
   let the caller re-read, rebuild and retry (:meth:`GitLedger.append_with_retry`
   does this, bounded).

History is only ever extended: every commit has the previous head as its parent,
no ref is force-moved, and a failed or conflicting attempt writes nothing the ref
points at. The module performs local Git plumbing only. It never pushes, calls
GitHub, dispatches work, verifies or accepts a candidate, or merges; the record
authority ceiling from C9-A is enforced by the serializer on every append. The
GitHub evidence-branch adapter is C9-G; this is the concurrency proof it relies on.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from idkmesh.github_ledger_serialization import (
    SerializedGitHubLedgerRecord,
    serialize_github_ledger_chain,
    serialize_github_ledger_record,
)

REF_PREFIX = "refs/idkmesh/ledger/"
RECORDS_DIR = "records"
DEFAULT_MAX_ATTEMPTS = 16
_REF_RE = re.compile(r"refs/idkmesh/ledger/[A-Za-z0-9][A-Za-z0-9._/-]{0,200}\Z")
_NAME_RE = re.compile(r"(\d{20})\.json\Z")


class GitHubLedgerAppendError(RuntimeError):
    """Base class; ``code`` is a stable machine-readable reason."""

    code = "ledger_error"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class LedgerStorageError(GitHubLedgerAppendError):
    code = "storage_error"


class LedgerConflict(GitHubLedgerAppendError):
    """The ledger head moved since the snapshot the writer built from."""

    code = "head_conflict"

    def __init__(self, expected: str | None, actual: str | None) -> None:
        self.expected_commit = expected
        self.actual_commit = actual
        super().__init__(
            f"ledger head moved (expected {expected or 'empty'}, found {actual or 'empty'})"
        )


class LedgerConflictExhausted(GitHubLedgerAppendError):
    """Every bounded retry lost a race."""

    code = "conflict_retries_exhausted"


@dataclass(frozen=True, slots=True)
class LedgerHead:
    """Where the ledger stands: the commit and its last record."""

    commit: str | None
    sequence: int
    record_digest: str | None


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    head: LedgerHead
    records: tuple[dict[str, Any], ...]
    #: ``(file name, blob id)`` for every stored record, so an append can build
    #: the next tree without listing it again.
    entries: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AppendResult:
    appended: bool
    head: LedgerHead
    attempts: int


Builder = Callable[[LedgerHead, tuple[dict[str, Any], ...]], "Mapping[str, Any] | None"]

EMPTY_HEAD = LedgerHead(commit=None, sequence=0, record_digest=None)


def run_git(
    repository: Path,
    *args: str,
    input: bytes | None = None,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one ``git`` plumbing command in ``repository`` (shared by C9-C/C9-D)."""

    full_env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
    if env:
        full_env.update(env)
    try:
        done = subprocess.run(
            ["git", "-C", str(repository), *args],
            input=input,
            capture_output=True,
            env=full_env,
            check=False,
        )
    except OSError as exc:
        raise LedgerStorageError(f"cannot run git: {exc}") from exc
    if check and done.returncode != 0:
        raise LedgerStorageError(
            f"git {args[0]} failed: {done.stderr.decode('utf-8', 'replace').strip()[:300]}"
        )
    return done


def ledger_ref_for_run(run_id: str) -> str:
    """The ledger ref for a run: a digest of the id, so any id yields a valid ref."""

    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")
    return f"{REF_PREFIX}{hashlib.sha256(run_id.encode('utf-8')).hexdigest()}"


class GitLedger:
    """One run's append-only ledger, stored as a linear history on one Git ref."""

    def __init__(
        self,
        repository: str | Path,
        ref: str,
        *,
        author_name: str,
        author_email: str,
    ) -> None:
        if _REF_RE.fullmatch(ref) is None or ".." in ref or ref.endswith(("/", ".lock")):
            raise ValueError(f"ref must be a valid name under {REF_PREFIX}")
        if not author_name.strip() or not author_email.strip():
            raise ValueError("author_name and author_email are required")
        self._repo = Path(repository)
        self._ref = ref
        self._author = (author_name, author_email)

    # ----- git plumbing ------------------------------------------------------

    def _git(self, *args: str, input: bytes | None = None, check: bool = True,
             env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
        return run_git(self._repo, *args, input=input, check=check, env=env)

    def _head_commit(self) -> str | None:
        done = self._git("rev-parse", "--verify", "-q", f"{self._ref}^{{commit}}", check=False)
        if done.returncode == 0:
            return done.stdout.decode().strip()
        if done.returncode == 1 and not done.stderr.strip():
            return None  # the ref does not exist yet
        raise LedgerStorageError(f"cannot resolve {self._ref}: {done.stderr.decode()[:200]}")

    # ----- reading -----------------------------------------------------------

    def snapshot(self) -> LedgerSnapshot:
        """The head commit and its fully verified chain, read from one commit."""

        commit = self._head_commit()
        if commit is None:
            return LedgerSnapshot(EMPTY_HEAD, ())
        listing = self._git("ls-tree", "-r", commit, "--", f"{RECORDS_DIR}/").stdout.decode()
        entries: list[tuple[str, str]] = []
        for line in listing.splitlines():
            meta, _, path = line.partition("\t")
            mode, kind, blob = meta.split()
            name = path.rsplit("/", 1)[-1]
            if kind != "blob" or _NAME_RE.fullmatch(name) is None:
                raise LedgerStorageError(f"unexpected ledger entry {path!r}")
            entries.append((name, blob))
        entries.sort()
        contents = self._read_blobs([blob for _, blob in entries])
        records = []
        for (name, _blob), content in zip(entries, contents):
            try:
                records.append(json.loads(content))
            except ValueError as exc:
                raise LedgerStorageError(f"ledger entry {name} is not JSON: {exc}") from exc
        chain = serialize_github_ledger_chain(records)  # raises on any broken link
        for (name, _blob), item in zip(entries, chain):
            if name != f"{item.sequence:020d}.json":
                raise LedgerStorageError(f"entry {name} does not match its sequence")
        last = chain[-1]
        return LedgerSnapshot(
            LedgerHead(commit, last.sequence, last.record_digest), tuple(records), tuple(entries)
        )

    def _read_blobs(self, blobs: list[str]) -> list[bytes]:
        """Read several blobs with one ``git cat-file --batch`` process."""

        if not blobs:
            return []
        out = self._git("cat-file", "--batch", input=("\n".join(blobs) + "\n").encode()).stdout
        contents, offset = [], 0
        for blob in blobs:
            end = out.index(b"\n", offset)
            header = out[offset:end].split()
            if len(header) != 3 or header[0].decode() != blob or header[1] != b"blob":
                raise LedgerStorageError(f"unexpected cat-file output for {blob}")
            size = int(header[2])
            contents.append(out[end + 1 : end + 1 + size])
            offset = end + 1 + size + 1
        return contents

    def head(self) -> LedgerHead:
        return self.snapshot().head

    def read_records(self) -> tuple[dict[str, Any], ...]:
        return self.snapshot().records

    # ----- writing -----------------------------------------------------------

    def append(self, record: Mapping[str, Any], *, expected: LedgerHead) -> LedgerHead:
        """Append ``record`` only if the ledger head is still ``expected``.

        Raises :class:`LedgerConflict` if the head moved, and the serializer's
        error (fail-closed, nothing written) if ``record`` does not extend the
        verified chain.
        """

        snapshot = self.snapshot()
        if snapshot.head.commit != expected.commit:
            raise LedgerConflict(expected.commit, snapshot.head.commit)
        return self._append_from(snapshot, record)

    def _append_from(self, snapshot: LedgerSnapshot, record: Mapping[str, Any]) -> LedgerHead:
        """Append on top of ``snapshot``; the ref update is the real guard.

        The caller holds a verified snapshot it just read, so re-reading the
        ledger here would only repeat work: if the head has moved since, the
        compare-and-set below fails and the caller retries from a fresh read.
        """

        expected = snapshot.head
        item: SerializedGitHubLedgerRecord = serialize_github_ledger_record(record)
        serialize_github_ledger_chain([*snapshot.records, record])  # extends the chain?

        blob = self._git("hash-object", "-w", "--stdin", input=item.content).stdout.decode().strip()
        name = f"{item.sequence:020d}.json"
        subtree_entries = [f"100644 blob {sha}\t{n}" for n, sha in snapshot.entries]
        subtree_entries.append(f"100644 blob {blob}\t{name}")
        new_subtree = self._git(
            "mktree", input=("\n".join(sorted(subtree_entries, key=lambda e: e.split("\t", 1)[1])) + "\n").encode()
        ).stdout.decode().strip()
        root = self._git(
            "mktree", input=f"040000 tree {new_subtree}\t{RECORDS_DIR}\n".encode()
        ).stdout.decode().strip()

        author_env = {
            "GIT_AUTHOR_NAME": self._author[0], "GIT_AUTHOR_EMAIL": self._author[1],
            "GIT_COMMITTER_NAME": self._author[0], "GIT_COMMITTER_EMAIL": self._author[1],
        }
        parents = ["-p", snapshot.head.commit] if snapshot.head.commit else []
        commit = self._git(
            "commit-tree", root, *parents, "-m", f"ledger: append {item.record_id}", env=author_env
        ).stdout.decode().strip()

        old = snapshot.head.commit or "0" * len(commit)
        moved = self._git("update-ref", self._ref, commit, old, check=False)
        if moved.returncode != 0:
            raise LedgerConflict(expected.commit, self._head_commit())
        return LedgerHead(commit, item.sequence, item.record_digest)

    def append_with_retry(
        self, build: Builder, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS
    ) -> AppendResult:
        """Build-and-append, re-reading and rebuilding after every lost race.

        ``build(head, records)`` returns the next record, or ``None`` when there
        is nothing (left) to write -- for example because a retry discovers the
        event is already recorded. Bounded: after ``max_attempts`` lost races it
        raises :class:`LedgerConflictExhausted` rather than looping.
        """

        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        for attempt in range(1, max_attempts + 1):
            snapshot = self.snapshot()
            record = build(snapshot.head, snapshot.records)
            if record is None:
                return AppendResult(False, snapshot.head, attempt)
            try:
                head = self._append_from(snapshot, record)
            except LedgerConflict:
                continue
            return AppendResult(True, head, attempt)
        raise LedgerConflictExhausted(f"lost the race {max_attempts} times")
