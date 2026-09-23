#!/usr/bin/env python3
"""Create one atomic GitHub commit from many UTF-8 file changes.

This tool exists for agent/automation branches where one Contents-API write per
file would create one commit and one pull-request synchronize event per file.

The publish sequence is deliberately narrow:

    expected branch head
      -> create blobs
      -> create one tree from the expected base tree
      -> create one commit with the expected head as parent
      -> re-check branch head
      -> non-force ref update

A branch move is fail-closed. The tool never force-updates a branch and refuses
to write the configured default branch unless explicitly allowed.

Examples:

    python tools/github_atomic_commit.py plan \
      --branch agent/my-work \
      --expected-head <sha> \
      --write idkmesh/a.py=/tmp/a.py \
      --write tests/test_a.py=/tmp/test_a.py \
      --delete old/file.txt

    GITHUB_TOKEN=... python tools/github_atomic_commit.py publish \
      --repository owner/repo \
      --branch agent/my-work \
      --expected-head <sha> \
      --message "agent: publish bounded candidate" \
      --write idkmesh/a.py=/tmp/a.py \
      --write tests/test_a.py=/tmp/test_a.py

Dry-run planning performs no GitHub mutation and does not require a token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request


_SHA = re.compile(r"[0-9a-f]{40}\Z")
_MODE = "100644"


class AtomicCommitError(RuntimeError):
    """Safe failure at the atomic GitHub publication boundary."""


def _repo_path(path: str) -> str:
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or "\\" in path
        or "\x00" in path
    ):
        raise AtomicCommitError(f"invalid repository path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AtomicCommitError(f"invalid repository path: {path!r}")
    return path


def _sha(value: str, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise AtomicCommitError(f"{field} must be a 40-character lowercase git SHA")
    return value


def _normalize_changes(
    writes: Mapping[str, str],
    deletes: list[str] | tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    normalized_writes = tuple(sorted((_repo_path(path), content) for path, content in writes.items()))
    normalized_deletes = tuple(sorted(_repo_path(path) for path in deletes))

    write_paths = [path for path, _ in normalized_writes]
    if len(write_paths) != len(set(write_paths)):
        raise AtomicCommitError("duplicate write path")
    if len(normalized_deletes) != len(set(normalized_deletes)):
        raise AtomicCommitError("duplicate delete path")
    overlap = sorted(set(write_paths).intersection(normalized_deletes))
    if overlap:
        raise AtomicCommitError(
            "path cannot be both written and deleted: " + ", ".join(overlap)
        )
    if not normalized_writes and not normalized_deletes:
        raise AtomicCommitError("at least one write or delete is required")
    for path, content in normalized_writes:
        if not isinstance(content, str):
            raise AtomicCommitError(f"write content for {path} must be UTF-8 text")
    return normalized_writes, normalized_deletes


def build_plan(
    *,
    branch: str,
    expected_head: str,
    writes: Mapping[str, str],
    deletes: list[str] | tuple[str, ...] = (),
    default_branch: str = "main",
    allow_default_branch: bool = False,
) -> dict[str, Any]:
    """Return a deterministic secret-free publication plan."""

    if not isinstance(branch, str) or not branch:
        raise AtomicCommitError("branch must be non-empty")
    if branch == default_branch and not allow_default_branch:
        raise AtomicCommitError(
            f"refusing direct write to default branch {default_branch!r}"
        )
    expected = _sha(expected_head, "expected_head")
    normalized_writes, normalized_deletes = _normalize_changes(writes, deletes)
    return {
        "version": 1,
        "branch": branch,
        "expected_head": expected,
        "default_branch": default_branch,
        "allow_default_branch": bool(allow_default_branch),
        "writes": [
            {
                "path": path,
                "bytes": len(content.encode("utf-8")),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
            for path, content in normalized_writes
        ],
        "deletes": list(normalized_deletes),
        "mutation_count": len(normalized_writes) + len(normalized_deletes),
        "publication_commits": 1,
        "force_ref_update": False,
    }


class GitHubGitDataAPI:
    """Small stdlib-only client for GitHub Git Data endpoints."""

    def __init__(self, token: str, repository: str, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise AtomicCommitError("GITHUB_TOKEN is required for publish")
        if not isinstance(repository, str) or repository.count("/") != 1:
            raise AtomicCommitError("repository must have owner/name form")
        self._token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self.repo_path = f"/repos/{repository}"

    def request(self, method: str, path: str, payload: Any = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "idkmesh-atomic-github-commit/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as exc:
            # Do not include request headers/token in the error.
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise AtomicCommitError(
                f"GitHub API {method} {path} failed with {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AtomicCommitError(f"GitHub API request failed: {exc.reason}") from exc

    def get_ref(self, branch: str) -> str:
        quoted = urllib.parse.quote(branch, safe="/")
        result = self.request("GET", f"{self.repo_path}/git/ref/heads/{quoted}")
        try:
            return _sha(str(result["object"]["sha"]), "branch head")
        except (KeyError, TypeError) as exc:
            raise AtomicCommitError("GitHub ref response is missing object.sha") from exc

    def get_commit_tree(self, commit_sha: str) -> str:
        result = self.request("GET", f"{self.repo_path}/git/commits/{_sha(commit_sha, 'commit_sha')}")
        try:
            return _sha(str(result["tree"]["sha"]), "tree sha")
        except (KeyError, TypeError) as exc:
            raise AtomicCommitError("GitHub commit response is missing tree.sha") from exc

    def create_blob(self, content: str) -> str:
        result = self.request(
            "POST",
            f"{self.repo_path}/git/blobs",
            {"content": content, "encoding": "utf-8"},
        )
        try:
            return _sha(str(result["sha"]), "blob sha")
        except (KeyError, TypeError) as exc:
            raise AtomicCommitError("GitHub blob response is missing sha") from exc

    def create_tree(self, base_tree: str, entries: list[dict[str, Any]]) -> str:
        result = self.request(
            "POST",
            f"{self.repo_path}/git/trees",
            {"base_tree": _sha(base_tree, "base_tree"), "tree": entries},
        )
        try:
            return _sha(str(result["sha"]), "tree sha")
        except (KeyError, TypeError) as exc:
            raise AtomicCommitError("GitHub tree response is missing sha") from exc

    def create_commit(self, message: str, tree_sha: str, parent_sha: str) -> str:
        result = self.request(
            "POST",
            f"{self.repo_path}/git/commits",
            {
                "message": message,
                "tree": _sha(tree_sha, "tree_sha"),
                "parents": [_sha(parent_sha, "parent_sha")],
            },
        )
        try:
            return _sha(str(result["sha"]), "commit sha")
        except (KeyError, TypeError) as exc:
            raise AtomicCommitError("GitHub commit response is missing sha") from exc

    def update_ref(self, branch: str, commit_sha: str) -> None:
        quoted = urllib.parse.quote(branch, safe="/")
        self.request(
            "PATCH",
            f"{self.repo_path}/git/refs/heads/{quoted}",
            {"sha": _sha(commit_sha, "commit_sha"), "force": False},
        )


def publish_atomic_commit(
    api: Any,
    *,
    branch: str,
    expected_head: str,
    message: str,
    writes: Mapping[str, str],
    deletes: list[str] | tuple[str, ...] = (),
    default_branch: str = "main",
    allow_default_branch: bool = False,
) -> dict[str, Any]:
    """Publish many changes with one commit and one non-force ref move.

    The branch head is checked before object creation and immediately before the
    ref update. Even if it moves after the second check, the non-force ref update
    still fails because the new commit is parented to the expected head rather
    than the concurrently advanced head.
    """

    plan = build_plan(
        branch=branch,
        expected_head=expected_head,
        writes=writes,
        deletes=deletes,
        default_branch=default_branch,
        allow_default_branch=allow_default_branch,
    )
    expected = plan["expected_head"]

    observed = api.get_ref(branch)
    if observed != expected:
        raise AtomicCommitError(
            f"branch head changed before publication: expected {expected}, observed {observed}"
        )

    base_tree = api.get_commit_tree(expected)
    normalized_writes, normalized_deletes = _normalize_changes(writes, deletes)

    entries: list[dict[str, Any]] = []
    for path, content in normalized_writes:
        blob_sha = api.create_blob(content)
        entries.append(
            {"path": path, "mode": _MODE, "type": "blob", "sha": blob_sha}
        )
    for path in normalized_deletes:
        entries.append({"path": path, "mode": _MODE, "type": "blob", "sha": None})

    tree_sha = api.create_tree(base_tree, entries)
    commit_sha = api.create_commit(message, tree_sha, expected)

    observed_again = api.get_ref(branch)
    if observed_again != expected:
        raise AtomicCommitError(
            f"branch head changed before ref update: expected {expected}, observed {observed_again}"
        )

    api.update_ref(branch, commit_sha)
    return {
        **plan,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "published": True,
    }


def _write_specs(values: list[str]) -> dict[str, str]:
    writes: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise AtomicCommitError("--write must use REPO_PATH=LOCAL_FILE")
        repo_path, local_path = value.split("=", 1)
        repo_path = _repo_path(repo_path)
        if repo_path in writes:
            raise AtomicCommitError(f"duplicate --write path: {repo_path}")
        writes[repo_path] = Path(local_path).read_text(encoding="utf-8")
    return writes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--branch", required=True)
        p.add_argument("--expected-head", required=True)
        p.add_argument("--default-branch", default="main")
        p.add_argument("--allow-default-branch", action="store_true")
        p.add_argument(
            "--write",
            action="append",
            default=[],
            metavar="REPO_PATH=LOCAL_FILE",
            help="UTF-8 file to include; may be repeated",
        )
        p.add_argument(
            "--delete",
            action="append",
            default=[],
            metavar="REPO_PATH",
            help="repository path to delete; may be repeated",
        )
        p.add_argument("--json", action="store_true", dest="json_output")

    plan = sub.add_parser("plan", help="validate and show an offline mutation plan")
    common(plan)

    publish = sub.add_parser("publish", help="publish one atomic GitHub commit")
    common(publish)
    publish.add_argument("--repository", required=True)
    publish.add_argument("--message", required=True)
    publish.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        writes = _write_specs(args.write)
        if args.command == "plan":
            result = build_plan(
                branch=args.branch,
                expected_head=args.expected_head,
                writes=writes,
                deletes=args.delete,
                default_branch=args.default_branch,
                allow_default_branch=args.allow_default_branch,
            )
        else:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise AtomicCommitError("GITHUB_TOKEN is required for publish")
            api = GitHubGitDataAPI(token, args.repository, args.api_url)
            result = publish_atomic_commit(
                api,
                branch=args.branch,
                expected_head=args.expected_head,
                message=args.message,
                writes=writes,
                deletes=args.delete,
                default_branch=args.default_branch,
                allow_default_branch=args.allow_default_branch,
            )
    except (AtomicCommitError, OSError, UnicodeError) as exc:
        print(f"atomic-github-commit: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(
            f"{'published' if result.get('published') else 'planned'}: "
            f"{result['mutation_count']} path(s), "
            f"{result['publication_commits']} commit"
        )
        if result.get("commit_sha"):
            print(f"commit: {result['commit_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
