"""GitHub-native durable storage adapter for the C9 run ledger (slice C9-G).

The adapter stores compact ledger/admission documents on one dedicated orphan
branch. It never writes the configured protected/default application branch.
Remote updates are compare-and-set in Git terms: every candidate commit is a
child of the observed branch head and the GitHub ref update is requested with
``force=false``. If the branch moved, the update is not fast-forward and the
writer re-reads/rebuilds within a bounded retry budget.

This module owns storage only. It grants no dispatch, verification, acceptance,
integration, merge, ruleset, environment, or secret-management authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import base64
import hashlib
import json
import math
import re
import socket
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from idkmesh.github_ledger_admission import (
    ADMISSION_KIND,
    ADMISSION_SCHEMA_VERSION,
    Admission,
    AdmissionConflict,
)
from idkmesh.github_ledger_append import LedgerHead, ledger_ref_for_run
from idkmesh.github_ledger_recovery import RecoveredRunState, reconstruct_run_state
from idkmesh.github_ledger_serialization import (
    serialize_github_ledger_chain,
    serialize_github_ledger_record,
)


STORE_SCHEMA_VERSION = "0.1"
STORE_KIND = "idkmesh-github-ledger-store"
DEFAULT_LEDGER_BRANCH = "idkmesh-ledger"
DEFAULT_MAX_ATTEMPTS = 8
MARKER_PATH = ".idkmesh-ledger/store.json"
_API_BASE = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ACCEPT = "application/vnd.github+json"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]+\Z")
_SHA_RE = re.compile(r"[0-9a-f]{40,64}\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECORD_PATH_RE = re.compile(r"runs/([0-9a-f]{64})/records/(\d{20})\.json\Z")
_ADMISSION_PATH_RE = re.compile(r"admissions/([0-9a-f]{64})\.json\Z")
_DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class GitHubLedgerRemoteError(RuntimeError):
    """Stable GitHub-storage failure."""

    code = "github_ledger_remote_error"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class GitHubLedgerRemoteConflict(GitHubLedgerRemoteError):
    """The dedicated branch moved before a fast-forward-only update."""

    code = "github_ledger_remote_conflict"


class GitHubLedgerRemoteConflictExhausted(GitHubLedgerRemoteError):
    code = "github_ledger_remote_conflict_exhausted"


class GitHubLedgerRemoteStorageError(GitHubLedgerRemoteError):
    code = "github_ledger_remote_storage_error"


class GitHubGitDataTransportError(GitHubLedgerRemoteError):
    code = "github_git_data_error"

    def __init__(self, message: str, *, status: int | None = None) -> None:
        self.status = status
        super().__init__(message)


class GitHubGitDataConflict(GitHubGitDataTransportError):
    code = "github_git_data_conflict"


@dataclass(frozen=True, slots=True)
class GitTreeEntry:
    path: str
    mode: str
    kind: str
    sha: str


class GitHubGitDataTransport(Protocol):
    def get_branch_head(self, *, repository: str, branch: str) -> str | None: ...

    def get_commit_tree(self, *, repository: str, commit_sha: str) -> str: ...

    def get_tree(self, *, repository: str, tree_sha: str) -> tuple[GitTreeEntry, ...]: ...

    def get_blob(self, *, repository: str, blob_sha: str) -> bytes: ...

    def create_blob(self, *, repository: str, content: bytes) -> str: ...

    def create_tree(
        self,
        *,
        repository: str,
        base_tree_sha: str | None,
        files: Mapping[str, str],
    ) -> str: ...

    def create_commit(
        self,
        *,
        repository: str,
        message: str,
        tree_sha: str,
        parents: Sequence[str],
    ) -> str: ...

    def create_branch(self, *, repository: str, branch: str, commit_sha: str) -> None: ...

    def update_branch(self, *, repository: str, branch: str, commit_sha: str) -> None: ...


def _git_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise GitHubGitDataTransportError(f"{field} must be a 40- or 64-hex Git object id")
    return value


def _repository(value: object) -> str:
    if not isinstance(value, str) or _REPOSITORY_RE.fullmatch(value) is None:
        raise ValueError("repository must be in owner/name form")
    return value


def _branch(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError(f"{field} must be a non-empty branch name <= 255 chars")
    if _BRANCH_RE.fullmatch(value) is None:
        raise ValueError(f"{field} contains unsupported characters")
    if (
        value.startswith(("/", "."))
        or value.endswith(("/", ".", ".lock"))
        or "//" in value
        or ".." in value
        or "@{" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{field} is not a safe Git branch name")
    return value


def _canonical(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _run_hash(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()


def _dispatch_hash(dispatch_key: str) -> str:
    if not isinstance(dispatch_key, str) or not dispatch_key:
        raise ValueError("dispatch_key must be a non-empty string")
    return hashlib.sha256(dispatch_key.encode("utf-8")).hexdigest()


def run_record_path(run_id: str, sequence: int) -> str:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence must be an integer >= 1")
    return f"runs/{_run_hash(run_id)}/records/{sequence:020d}.json"


def admission_path(dispatch_key: str) -> str:
    return f"admissions/{_dispatch_hash(dispatch_key)}.json"


@dataclass(frozen=True, slots=True)
class GitHubLedgerBranchSnapshot:
    commit_sha: str
    tree_sha: str
    files: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class GitHubLedgerRemoteAppendResult:
    appended: bool
    head: LedgerHead
    attempts: int


@dataclass(frozen=True, slots=True)
class GitHubLedgerRemoteAdmissionResult:
    admission: Admission
    created: bool
    head: LedgerHead
    recorded: bool
    attempts: int


RemoteBuilder = Callable[[LedgerHead, tuple[dict[str, Any], ...]], Mapping[str, Any] | None]


class GitHubRestGitDataTransport:
    """Bounded fixed-host GitHub REST transport for Git database objects."""

    def __init__(
        self,
        *,
        token: str,
        timeout_seconds: int | float = 15,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        user_agent: str = "idkmesh/0.1",
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token must be a non-empty string")
        if any(ord(char) < 32 or ord(char) == 127 for char in token):
            raise ValueError("token must not contain control characters")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
            or timeout_seconds > 120
        ):
            raise ValueError("timeout_seconds must be finite and in (0, 120]")
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes < 1
            or max_response_bytes > _MAX_RESPONSE_BYTES
        ):
            raise ValueError(
                f"max_response_bytes must be in [1, {_MAX_RESPONSE_BYTES}]"
            )
        if not callable(opener):
            raise ValueError("opener must be callable")
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        if any(ord(char) < 32 or ord(char) == 127 for char in user_agent):
            raise ValueError("user_agent must not contain control characters")
        self._token = token
        self._timeout = float(timeout_seconds)
        self._max = max_response_bytes
        self._opener = opener
        self._user_agent = user_agent

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None = None,
        allow_not_found: bool = False,
        conflict_is_expected: bool = False,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        headers = {
            "Accept": _ACCEPT,
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": self._user_agent,
        }
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            context = self._opener(request, timeout=self._timeout)
            with context as response:
                status = int(getattr(response, "status", 200))
                payload = response.read(self._max + 1)
        except HTTPError as exc:
            status = int(exc.code)
            if allow_not_found and status == 404:
                return None
            if conflict_is_expected and status in {409, 422}:
                raise GitHubGitDataConflict(
                    "GitHub rejected a stale/non-fast-forward ref update",
                    status=status,
                ) from exc
            raise GitHubGitDataTransportError(
                f"GitHub Git-data request failed with HTTP {status}",
                status=status,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GitHubGitDataTransportError("GitHub Git-data request timed out") from exc
        except URLError as exc:
            raise GitHubGitDataTransportError("GitHub Git-data request is unavailable") from exc
        except OSError as exc:
            raise GitHubGitDataTransportError("GitHub Git-data request is unavailable") from exc

        if status not in expected:
            raise GitHubGitDataTransportError(
                f"GitHub Git-data request returned HTTP {status}",
                status=status,
            )
        if not isinstance(payload, bytes) or len(payload) > self._max:
            raise GitHubGitDataTransportError("GitHub Git-data response exceeds size bound")
        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubGitDataTransportError("GitHub Git-data response is malformed JSON") from exc

    @staticmethod
    def _object_payload(payload: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(payload, dict):
            raise GitHubGitDataTransportError(f"GitHub {label} response is not an object")
        return payload

    @staticmethod
    def _repo_url(repository: str, suffix: str) -> str:
        owner, name = _repository(repository).split("/", 1)
        return f"{_API_BASE}/repos/{owner}/{name}/{suffix}"

    def get_branch_head(self, *, repository: str, branch: str) -> str | None:
        branch_name = _branch(branch, "branch")
        encoded = quote(branch_name, safe="")
        payload = self._request(
            "GET",
            self._repo_url(repository, f"git/ref/heads/{encoded}"),
            allow_not_found=True,
        )
        if payload is None:
            return None
        payload = self._object_payload(payload, "branch-ref")
        try:
            ref = payload["ref"]
            obj = payload["object"]
            sha = obj["sha"]
            kind = obj["type"]
        except (KeyError, TypeError) as exc:
            raise GitHubGitDataTransportError("GitHub branch-ref response is malformed") from exc
        if ref != f"refs/heads/{branch_name}" or kind != "commit":
            raise GitHubGitDataTransportError("GitHub branch-ref identity is inconsistent")
        return _git_sha(sha, "branch head SHA")

    def get_commit_tree(self, *, repository: str, commit_sha: str) -> str:
        payload = self._object_payload(
            self._request("GET", self._repo_url(repository, f"git/commits/{commit_sha}")),
            "commit",
        )
        try:
            sha = payload["tree"]["sha"]
        except (KeyError, TypeError) as exc:
            raise GitHubGitDataTransportError("GitHub commit response lacks tree identity") from exc
        return _git_sha(sha, "commit tree SHA")

    def get_tree(self, *, repository: str, tree_sha: str) -> tuple[GitTreeEntry, ...]:
        payload = self._object_payload(
            self._request(
                "GET",
                self._repo_url(repository, f"git/trees/{tree_sha}?recursive=1"),
            ),
            "tree",
        )
        if payload.get("truncated") is True:
            raise GitHubGitDataTransportError("GitHub ledger tree response was truncated")
        raw = payload.get("tree")
        if not isinstance(raw, list):
            raise GitHubGitDataTransportError("GitHub tree response is malformed")
        result = []
        for item in raw:
            if not isinstance(item, dict):
                raise GitHubGitDataTransportError("GitHub tree entry is malformed")
            try:
                result.append(
                    GitTreeEntry(
                        item["path"], item["mode"], item["type"],
                        _git_sha(item["sha"], "tree entry SHA"),
                    )
                )
            except KeyError as exc:
                raise GitHubGitDataTransportError("GitHub tree entry is incomplete") from exc
        return tuple(result)

    def get_blob(self, *, repository: str, blob_sha: str) -> bytes:
        payload = self._object_payload(
            self._request("GET", self._repo_url(repository, f"git/blobs/{blob_sha}")),
            "blob",
        )
        if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
            raise GitHubGitDataTransportError("GitHub blob response is not base64 encoded")
        try:
            return base64.b64decode(payload["content"], validate=False)
        except (ValueError, TypeError) as exc:
            raise GitHubGitDataTransportError("GitHub blob base64 is malformed") from exc

    def create_blob(self, *, repository: str, content: bytes) -> str:
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        payload = self._object_payload(
            self._request(
                "POST",
                self._repo_url(repository, "git/blobs"),
                body={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
                expected=(201,),
            ),
            "create-blob",
        )
        return _git_sha(payload.get("sha"), "created blob SHA")

    def create_tree(
        self,
        *,
        repository: str,
        base_tree_sha: str | None,
        files: Mapping[str, str],
    ) -> str:
        body: dict[str, Any] = {
            "tree": [
                {"path": path, "mode": "100644", "type": "blob", "sha": sha}
                for path, sha in sorted(files.items())
            ]
        }
        if base_tree_sha is not None:
            body["base_tree"] = base_tree_sha
        payload = self._object_payload(
            self._request(
                "POST",
                self._repo_url(repository, "git/trees"),
                body=body,
                expected=(201,),
            ),
            "create-tree",
        )
        return _git_sha(payload.get("sha"), "created tree SHA")

    def create_commit(
        self,
        *,
        repository: str,
        message: str,
        tree_sha: str,
        parents: Sequence[str],
    ) -> str:
        payload = self._object_payload(
            self._request(
                "POST",
                self._repo_url(repository, "git/commits"),
                body={"message": message, "tree": tree_sha, "parents": list(parents)},
                expected=(201,),
            ),
            "create-commit",
        )
        return _git_sha(payload.get("sha"), "created commit SHA")

    def create_branch(self, *, repository: str, branch: str, commit_sha: str) -> None:
        commit_sha = _git_sha(commit_sha, "commit_sha")
        self._request(
            "POST",
            self._repo_url(repository, "git/refs"),
            body={"ref": f"refs/heads/{_branch(branch, 'branch')}", "sha": commit_sha},
            conflict_is_expected=True,
            expected=(201,),
        )

    def update_branch(self, *, repository: str, branch: str, commit_sha: str) -> None:
        commit_sha = _git_sha(commit_sha, "commit_sha")
        encoded = quote(_branch(branch, "branch"), safe="")
        self._request(
            "PATCH",
            self._repo_url(repository, f"git/refs/heads/{encoded}"),
            body={"sha": commit_sha, "force": False},
            conflict_is_expected=True,
            expected=(200,),
        )


class GitHubLedgerBranchStore:
    """Durable C9 store on one dedicated GitHub branch."""

    def __init__(
        self,
        *,
        repository: str,
        transport: GitHubGitDataTransport,
        default_branch: str,
        ledger_branch: str = DEFAULT_LEDGER_BRANCH,
        protected_branches: Sequence[str] = (),
    ) -> None:
        self.repository = _repository(repository)
        self.default_branch = _branch(default_branch, "default_branch")
        self.ledger_branch = _branch(ledger_branch, "ledger_branch")
        protected = {self.default_branch.casefold()}
        for branch in protected_branches:
            protected.add(_branch(branch, "protected_branch").casefold())
        if self.ledger_branch.casefold() in protected:
            raise ValueError("ledger_branch must not be a protected/application branch")
        self._transport = transport

    def _marker_document(self) -> dict[str, Any]:
        return {
            "schema_version": STORE_SCHEMA_VERSION,
            "kind": STORE_KIND,
            "repository": self.repository,
            "branch": self.ledger_branch,
        }

    def _initialize_branch(self) -> None:
        marker = self._transport.create_blob(
            repository=self.repository,
            content=_canonical(self._marker_document()),
        )
        tree = self._transport.create_tree(
            repository=self.repository,
            base_tree_sha=None,
            files={MARKER_PATH: marker},
        )
        commit = self._transport.create_commit(
            repository=self.repository,
            message="idkmesh ledger: initialize store",
            tree_sha=tree,
            parents=(),
        )
        try:
            self._transport.create_branch(
                repository=self.repository,
                branch=self.ledger_branch,
                commit_sha=commit,
            )
        except GitHubGitDataConflict:
            pass

    def snapshot(self) -> GitHubLedgerBranchSnapshot:
        head = self._transport.get_branch_head(
            repository=self.repository,
            branch=self.ledger_branch,
        )
        if head is None:
            self._initialize_branch()
            head = self._transport.get_branch_head(
                repository=self.repository,
                branch=self.ledger_branch,
            )
            if head is None:
                raise GitHubLedgerRemoteStorageError("ledger branch initialization did not persist")
        tree_sha = self._transport.get_commit_tree(repository=self.repository, commit_sha=head)
        entries = self._transport.get_tree(repository=self.repository, tree_sha=tree_sha)
        files: dict[str, str] = {}
        for entry in entries:
            if entry.kind == "tree":
                continue
            if entry.kind != "blob" or entry.mode != "100644":
                raise GitHubLedgerRemoteStorageError(f"unsupported ledger tree entry {entry.path!r}")
            if entry.path != MARKER_PATH and _RECORD_PATH_RE.fullmatch(entry.path) is None and _ADMISSION_PATH_RE.fullmatch(entry.path) is None:
                raise GitHubLedgerRemoteStorageError(f"unexpected file on dedicated ledger branch: {entry.path!r}")
            files[entry.path] = entry.sha
        marker_sha = files.get(MARKER_PATH)
        if marker_sha is None:
            raise GitHubLedgerRemoteStorageError("ledger branch marker is missing")
        marker_raw = self._transport.get_blob(repository=self.repository, blob_sha=marker_sha)
        try:
            marker = json.loads(marker_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubLedgerRemoteStorageError("ledger branch marker is malformed") from exc
        if marker != self._marker_document() or marker_raw != _canonical(marker):
            raise GitHubLedgerRemoteStorageError("ledger branch marker does not match this store")
        return GitHubLedgerBranchSnapshot(head, tree_sha, files)

    def _records_from_snapshot(
        self,
        snapshot: GitHubLedgerBranchSnapshot,
        run_id: str,
    ) -> tuple[dict[str, Any], ...]:
        digest = _run_hash(run_id)
        prefix = f"runs/{digest}/records/"
        selected = sorted(
            (path, sha) for path, sha in snapshot.files.items() if path.startswith(prefix)
        )
        if not selected:
            return ()
        records = []
        for path, blob_sha in selected:
            match = _RECORD_PATH_RE.fullmatch(path)
            if match is None or match.group(1) != digest:
                raise GitHubLedgerRemoteStorageError(f"invalid ledger record path {path!r}")
            raw = self._transport.get_blob(repository=self.repository, blob_sha=blob_sha)
            try:
                document = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GitHubLedgerRemoteStorageError(f"ledger record {path!r} is malformed") from exc
            if not isinstance(document, dict) or document.get("run_id") != run_id:
                raise GitHubLedgerRemoteStorageError(f"ledger record {path!r} is bound to another run")
            rendered = serialize_github_ledger_record(document)
            if raw != rendered.content or int(match.group(2)) != rendered.sequence:
                raise GitHubLedgerRemoteStorageError(f"ledger record {path!r} is not canonical")
            records.append(document)
        serialize_github_ledger_chain(records)
        return tuple(records)

    def read_run_records(self, run_id: str) -> tuple[dict[str, Any], ...]:
        return self._records_from_snapshot(self.snapshot(), run_id)

    def run_head(self, run_id: str) -> LedgerHead:
        snapshot = self.snapshot()
        records = self._records_from_snapshot(snapshot, run_id)
        if not records:
            return LedgerHead(snapshot.commit_sha, 0, None)
        item = serialize_github_ledger_record(records[-1])
        return LedgerHead(snapshot.commit_sha, item.sequence, item.record_digest)

    def _commit_file(
        self,
        snapshot: GitHubLedgerBranchSnapshot,
        *,
        path: str,
        content: bytes,
        message: str,
    ) -> str:
        blob = self._transport.create_blob(repository=self.repository, content=content)
        tree = self._transport.create_tree(
            repository=self.repository,
            base_tree_sha=snapshot.tree_sha,
            files={path: blob},
        )
        commit = self._transport.create_commit(
            repository=self.repository,
            message=message,
            tree_sha=tree,
            parents=(snapshot.commit_sha,),
        )
        try:
            self._transport.update_branch(
                repository=self.repository,
                branch=self.ledger_branch,
                commit_sha=commit,
            )
        except GitHubGitDataConflict as exc:
            raise GitHubLedgerRemoteConflict("ledger branch moved during update") from exc
        return commit

    def append_with_retry(
        self,
        run_id: str,
        build: RemoteBuilder,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> GitHubLedgerRemoteAppendResult:
        if not callable(build):
            raise TypeError("build must be callable")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        _run_hash(run_id)
        for attempt in range(1, max_attempts + 1):
            snapshot = self.snapshot()
            records = self._records_from_snapshot(snapshot, run_id)
            if records:
                last = serialize_github_ledger_record(records[-1])
                head = LedgerHead(snapshot.commit_sha, last.sequence, last.record_digest)
            else:
                head = LedgerHead(snapshot.commit_sha, 0, None)
            record = build(head, records)
            if record is None:
                return GitHubLedgerRemoteAppendResult(False, head, attempt)
            if not isinstance(record, Mapping) or record.get("run_id") != run_id:
                raise GitHubLedgerRemoteStorageError("builder returned a record for another run")
            item = serialize_github_ledger_record(record)
            for existing in records:
                if existing.get("record_id") == item.record_id:
                    current = serialize_github_ledger_record(existing)
                    if current.record_digest == item.record_digest:
                        return GitHubLedgerRemoteAppendResult(False, head, attempt)
                    raise GitHubLedgerRemoteStorageError("record_id already exists with different content")
            serialize_github_ledger_chain([*records, record])
            path = run_record_path(run_id, item.sequence)
            existing_blob = snapshot.files.get(path)
            if existing_blob is not None:
                raise GitHubLedgerRemoteStorageError("record sequence path already exists")
            try:
                commit = self._commit_file(
                    snapshot,
                    path=path,
                    content=item.content,
                    message=f"idkmesh ledger: append {item.record_id}",
                )
            except GitHubLedgerRemoteConflict:
                continue
            return GitHubLedgerRemoteAppendResult(
                True,
                LedgerHead(commit, item.sequence, item.record_digest),
                attempt,
            )
        raise GitHubLedgerRemoteConflictExhausted(
            f"ledger branch moved during all {max_attempts} attempts"
        )

    def append_record(
        self,
        record: Mapping[str, Any],
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> GitHubLedgerRemoteAppendResult:
        if not isinstance(record, Mapping):
            raise TypeError("record must be a mapping")
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("record.run_id must be a non-empty string")
        return self.append_with_retry(
            run_id,
            lambda _head, _records: record,
            max_attempts=max_attempts,
        )

    @staticmethod
    def _admission_document(admission: Admission) -> bytes:
        return _canonical(admission.to_document())

    def _read_admission_from_snapshot(
        self,
        snapshot: GitHubLedgerBranchSnapshot,
        dispatch_key: str,
    ) -> Admission | None:
        path = admission_path(dispatch_key)
        blob_sha = snapshot.files.get(path)
        if blob_sha is None:
            return None
        raw = self._transport.get_blob(repository=self.repository, blob_sha=blob_sha)
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubLedgerRemoteStorageError("stored admission is malformed") from exc
        required = {"schema_version", "kind", "dispatch_key", "request_digest", "run_id", "ledger_ref"}
        if (
            not isinstance(document, dict)
            or set(document) != required
            or document.get("schema_version") != ADMISSION_SCHEMA_VERSION
            or document.get("kind") != ADMISSION_KIND
            or document.get("dispatch_key") != dispatch_key
            or not isinstance(document.get("request_digest"), str)
            or _SHA256_RE.fullmatch(document["request_digest"]) is None
            or not isinstance(document.get("run_id"), str)
            or document.get("ledger_ref") != ledger_ref_for_run(document["run_id"])
            or raw != _canonical(document)
        ):
            raise GitHubLedgerRemoteStorageError("stored admission is inconsistent")
        return Admission(
            document["dispatch_key"],
            document["request_digest"],
            document["run_id"],
            document["ledger_ref"],
        )

    def read_admission(self, dispatch_key: str) -> Admission | None:
        return self._read_admission_from_snapshot(self.snapshot(), dispatch_key)

    def reserve_admission(
        self,
        admission: Admission,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> tuple[Admission, bool, str, int]:
        if not isinstance(admission, Admission):
            raise TypeError("admission must be Admission")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not isinstance(admission.request_digest, str) or _SHA256_RE.fullmatch(admission.request_digest) is None:
            raise ValueError("admission.request_digest must be a canonical sha256 digest")
        if admission.ledger_ref != ledger_ref_for_run(admission.run_id):
            raise ValueError("admission.ledger_ref does not match run_id")
        for attempt in range(1, max_attempts + 1):
            snapshot = self.snapshot()
            existing = self._read_admission_from_snapshot(snapshot, admission.dispatch_key)
            if existing is not None:
                if existing.request_digest != admission.request_digest:
                    raise AdmissionConflict(
                        f"dispatch key {admission.dispatch_key!r} was already admitted for a different request"
                    )
                return existing, False, snapshot.commit_sha, attempt
            try:
                commit = self._commit_file(
                    snapshot,
                    path=admission_path(admission.dispatch_key),
                    content=self._admission_document(admission),
                    message=f"idkmesh ledger: admit {_dispatch_hash(admission.dispatch_key)[:16]}",
                )
            except GitHubLedgerRemoteConflict:
                continue
            return admission, True, commit, attempt
        raise GitHubLedgerRemoteConflictExhausted(
            f"ledger branch moved during all {max_attempts} admission attempts"
        )

    def admit_dispatch(
        self,
        first_record: Mapping[str, Any],
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> GitHubLedgerRemoteAdmissionResult:
        item = serialize_github_ledger_record(first_record)
        if item.sequence != 1:
            raise ValueError("an admission opens a run with ledger_sequence 1")
        idempotency = first_record["idempotency"]
        dispatch_key = idempotency["dispatch_key"]
        request_digest = idempotency["request_digest"]
        if not isinstance(dispatch_key, str) or not dispatch_key:
            raise ValueError("idempotency.dispatch_key must be non-empty")
        if not isinstance(request_digest, str) or _SHA256_RE.fullmatch(request_digest) is None:
            raise ValueError("idempotency.request_digest must be a canonical sha256 digest")
        run_id = first_record["run_id"]
        candidate = Admission(dispatch_key, request_digest, run_id, ledger_ref_for_run(run_id))
        admission, created, _commit, attempts = self.reserve_admission(
            candidate,
            max_attempts=max_attempts,
        )
        records = self.read_run_records(admission.run_id)
        if admission.run_id != run_id:
            head = self.run_head(admission.run_id)
            return GitHubLedgerRemoteAdmissionResult(admission, created, head, False, attempts)
        if records:
            head = self.run_head(run_id)
            return GitHubLedgerRemoteAdmissionResult(admission, created, head, False, attempts)
        append = self.append_record(first_record, max_attempts=max_attempts)
        return GitHubLedgerRemoteAdmissionResult(
            admission,
            created,
            append.head,
            append.appended,
            attempts + append.attempts,
        )

    def recover_run(self, run_id: str) -> RecoveredRunState | None:
        records = self.read_run_records(run_id)
        return reconstruct_run_state(records) if records else None
