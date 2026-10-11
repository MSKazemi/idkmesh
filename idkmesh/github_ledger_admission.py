"""Idempotent admission for the C9 GitHub-native durable ledger (slice C9-D).

A dispatch is identified by its deterministic ``dispatch_key``. The same key
arriving twice -- a replayed webhook, a duplicate label event, two automations
acting on the same ready issue -- must resolve to the **one** run that was
admitted first, never to a second run.

The admission is a tiny immutable record stored on its own ref,
``refs/idkmesh/admissions/<sha256(dispatch_key)>``, created with the same Git
compare-and-set that protects the ledger: ``git update-ref <ref> <new>
<all-zero id>`` succeeds for exactly one creator and fails for every other. The
loser reads the winner's admission and returns it.

Semantics (matching the Product Spine's idempotency contract):

* first arrival: the admission is created, then the run's first ledger record
  is appended through :class:`GitLedger`;
* exact replay (same ``dispatch_key`` and ``request_digest``): the existing
  admission is returned and nothing new is written -- except that if a crash
  left an admitted run with an empty ledger, the replay completes the first
  record when it is for that same run;
* conflicting replay (same ``dispatch_key``, different ``request_digest``): fails
  closed with :class:`AdmissionConflict`; the original admission is untouched.

Local Git plumbing only. It never pushes, calls GitHub, dispatches work to a
provider, verifies or accepts a candidate, or merges. Admission is a *record*
that a dispatch was admitted; it grants no authority to execute anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from idkmesh.github_ledger_append import (
    GitHubLedgerAppendError,
    GitLedger,
    LedgerConflict,
    LedgerHead,
    LedgerStorageError,
    ledger_ref_for_run,
    run_git,
)
from idkmesh.github_ledger_serialization import serialize_github_ledger_record

ADMISSION_REF_PREFIX = "refs/idkmesh/admissions/"
ADMISSION_KIND = "idkmesh-ledger-admission"
ADMISSION_SCHEMA_VERSION = "0.1"
_BLOB = "admission.json"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class AdmissionConflict(GitHubLedgerAppendError):
    """The dispatch key was already admitted for a different request."""

    code = "admission_conflict"


class AdmissionInvalid(GitHubLedgerAppendError):
    """The first record cannot start an admission."""

    code = "admission_invalid"


@dataclass(frozen=True, slots=True)
class Admission:
    dispatch_key: str
    request_digest: str
    run_id: str
    ledger_ref: str

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": ADMISSION_SCHEMA_VERSION,
            "kind": ADMISSION_KIND,
            "dispatch_key": self.dispatch_key,
            "request_digest": self.request_digest,
            "run_id": self.run_id,
            "ledger_ref": self.ledger_ref,
        }


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    admission: Admission
    #: True only for the call that created the admission.
    created: bool
    #: Head of the run's ledger after this call.
    head: LedgerHead
    #: True when this call appended the run's first ledger record.
    recorded: bool


def admission_ref(dispatch_key: str) -> str:
    if not isinstance(dispatch_key, str) or not dispatch_key:
        raise ValueError("dispatch_key must be a non-empty string")
    return ADMISSION_REF_PREFIX + hashlib.sha256(dispatch_key.encode("utf-8")).hexdigest()


def _canonical(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _read_admission(repo: Path, ref: str) -> Admission | None:
    done = run_git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False)
    if done.returncode != 0:
        return None
    commit = done.stdout.decode().strip()
    blob = run_git(repo, "cat-file", "blob", f"{commit}:{_BLOB}").stdout
    try:
        document = json.loads(blob)
    except ValueError as exc:
        raise LedgerStorageError(f"admission {ref} is not JSON: {exc}") from exc
    keys = {"schema_version", "kind", "dispatch_key", "request_digest", "run_id", "ledger_ref"}
    if (
        not isinstance(document, dict)
        or set(document) != keys
        or document["kind"] != ADMISSION_KIND
        or document["schema_version"] != ADMISSION_SCHEMA_VERSION
        or document["ledger_ref"] != ledger_ref_for_run(str(document["run_id"]))
        or admission_ref(str(document["dispatch_key"])) != ref
    ):
        raise LedgerStorageError(f"admission {ref} is malformed or does not match its ref")
    return Admission(
        document["dispatch_key"], document["request_digest"], document["run_id"],
        document["ledger_ref"],
    )


def _create_admission(repo: Path, ref: str, admission: Admission, author: tuple[str, str]) -> bool:
    """Create the admission ref iff it does not exist; True for the one winner."""

    blob = run_git(
        repo, "hash-object", "-w", "--stdin", input=_canonical(admission.to_document())
    ).stdout.decode().strip()
    tree = run_git(repo, "mktree", input=f"100644 blob {blob}\t{_BLOB}\n".encode()).stdout.decode().strip()
    env = {
        "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1],
        "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1],
    }
    commit = run_git(
        repo, "commit-tree", tree, "-m", f"admission: {admission.run_id}", env=env
    ).stdout.decode().strip()
    zero = "0" * len(commit)
    return run_git(repo, "update-ref", ref, commit, zero, check=False).returncode == 0


def admit_dispatch(
    repository: str | Path,
    first_record: Mapping[str, Any],
    *,
    author_name: str,
    author_email: str,
) -> AdmissionResult:
    """Admit the dispatch that ``first_record`` opens, exactly once.

    ``first_record`` must be a valid ledger sequence-1 record; its
    ``idempotency.dispatch_key`` and ``idempotency.request_digest`` identify the
    dispatch and its ``run_id`` names the run to open.
    """

    if not author_name.strip() or not author_email.strip():
        raise ValueError("author_name and author_email are required")
    repo = Path(repository)
    item = serialize_github_ledger_record(first_record)  # fail-closed validation
    if item.sequence != 1:
        raise AdmissionInvalid("an admission opens a run with ledger_sequence 1")
    idempotency = first_record["idempotency"]
    dispatch_key = idempotency["dispatch_key"]
    request_digest = idempotency["request_digest"]
    if not isinstance(dispatch_key, str) or not dispatch_key:
        raise AdmissionInvalid("idempotency.dispatch_key must be a non-empty string")
    if not isinstance(request_digest, str) or _SHA256.fullmatch(request_digest) is None:
        raise AdmissionInvalid("idempotency.request_digest must be a sha256 digest")
    run_id = first_record["run_id"]

    ref = admission_ref(dispatch_key)
    candidate = Admission(dispatch_key, request_digest, run_id, ledger_ref_for_run(run_id))
    created = False
    existing = _read_admission(repo, ref)
    if existing is None:
        created = _create_admission(repo, ref, candidate, (author_name, author_email))
        existing = candidate if created else _read_admission(repo, ref)
        if existing is None:  # the creator's ref vanished: storage is not behaving
            raise LedgerStorageError(f"admission {ref} could not be created or read")

    if existing.request_digest != request_digest:
        raise AdmissionConflict(
            f"dispatch key {dispatch_key!r} was already admitted for a different request"
        )

    ledger = GitLedger(
        repo, existing.ledger_ref, author_name=author_name, author_email=author_email
    )
    recorded = False
    snapshot = ledger.snapshot()
    if snapshot.head.sequence == 0 and existing.run_id == run_id:
        # First arrival, or a replay that finds a crash between admission and the
        # first record: write it, tolerating a concurrent completer.
        try:
            head = ledger.append(first_record, expected=snapshot.head)
            recorded = True
        except LedgerConflict:
            head = ledger.head()
    else:
        head = snapshot.head
    return AdmissionResult(existing, created, head, recorded)
