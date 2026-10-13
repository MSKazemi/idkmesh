#!/usr/bin/env python3
"""Preflight and lease-guarded retirement of explicitly superseded GitHub branches.

This is a separate, operator-invoked deletion boundary: never a merge or review
substitute. Dry-run is the default and verifies live remote state. Execution
requires an explicit human attestation and a clean, current main checkout.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://api.github.com"
SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
BRANCH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._/-]*\Z")
ACK = "I_REVIEWED_BRANCH_EVIDENCE_AND_EXTERNAL_REFERENCES"


class RetirementError(RuntimeError):
    """Action blocked; never treat this as a cleanup success."""


@dataclass(frozen=True)
class Candidate:
    name: str
    head: str
    closed_pr: int
    merged_replacement_pr: int


def _valid_branch(name: Any) -> bool:
    return (
        isinstance(name, str)
        and len(name) <= 200
        and BRANCH.fullmatch(name) is not None
        and not any(part in {"", ".", ".."} or part.endswith(".lock") for part in name.split("/"))
        and ".." not in name
        and not name.endswith(".")
    )


def load_manifest(path: Path) -> tuple[str, str, tuple[Candidate, ...]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RetirementError("retirement manifest cannot be read") from exc
    if not isinstance(document, dict) or set(document) != {"repository", "default_branch", "candidates"}:
        raise RetirementError("unexpected retirement manifest shape")
    repo, default, entries = (document[key] for key in ("repository", "default_branch", "candidates"))
    if (
        not isinstance(repo, str)
        or REPO.fullmatch(repo) is None
        or repo != "MSKazemi/idkmesh"
        or default != "main"
    ):
        raise RetirementError("retirement manifest must target canonical MSKazemi/idkmesh main")
    if not isinstance(entries, list) or not entries or len(entries) > 20:
        raise RetirementError("retirement candidates must be a bounded, nonempty list")
    candidates = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "head", "closed_pr", "merged_replacement_pr"}:
            raise RetirementError("unexpected retirement candidate shape")
        name, head = entry["name"], entry["head"]
        if not _valid_branch(name) or name == default or name in seen:
            raise RetirementError("invalid, duplicate, or canonical retirement branch")
        if not isinstance(head, str) or SHA.fullmatch(head) is None:
            raise RetirementError("retirement requires a full lowercase 40-character head SHA")
        for key in ("closed_pr", "merged_replacement_pr"):
            if type(entry[key]) is not int or entry[key] < 1:
                raise RetirementError("retirement PR numbers must be positive integers")
        candidates.append(Candidate(name, head, entry["closed_pr"], entry["merged_replacement_pr"]))
        seen.add(name)
    return repo, default, tuple(candidates)


class Client:
    def __init__(self, token: str | None) -> None:
        self.token = token

    def get(self, path: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "idkmesh-branch-retirement/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(API + path, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RetirementError(f"GitHub returned HTTP {exc.code} during retirement preflight") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise RetirementError("GitHub retirement preflight unavailable") from exc


def _repo_path(repository: str) -> str:
    owner, name = repository.split("/", 1)
    return f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"


def current_main(client: Client, repository: str, default: str) -> str:
    info = client.get(_repo_path(repository) + "/branches/" + quote(default, safe=""))
    sha = info.get("commit", {}).get("sha") if isinstance(info, dict) else None
    if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
        raise RetirementError("cannot establish current canonical main commit")
    return sha


def verify(client: Client, repository: str, default: str, candidate: Candidate) -> None:
    """Fail closed unless old PR is superseded and branch head is unchanged."""
    path = _repo_path(repository)
    branch = client.get(path + "/branches/" + quote(candidate.name, safe=""))
    if (
        not isinstance(branch, dict)
        or not isinstance(branch.get("commit"), dict)
        or branch.get("protected") is not False
        or branch["commit"].get("sha") != candidate.head
    ):
        raise RetirementError(f"{candidate.name}: branch moved, protected, or unknown")

    owner = repository.split("/", 1)[0]
    params = urlencode({"state": "open", "head": f"{owner}:{candidate.name}", "per_page": 100})
    open_prs = client.get(path + "/pulls?" + params)
    if not isinstance(open_prs, list) or open_prs:
        raise RetirementError(f"{candidate.name}: an open PR exists or PR lookup failed")

    old = client.get(path + f"/pulls/{candidate.closed_pr}")
    if not isinstance(old, dict):
        raise RetirementError(f"{candidate.name}: malformed original PR evidence")
    head = old.get("head") or {}
    if not isinstance(head, dict):
        raise RetirementError(f"{candidate.name}: malformed original PR head")
    if (
        old.get("state") != "closed"
        or old.get("merged_at") is not None
        or head.get("sha") != candidate.head
        or head.get("ref") != candidate.name
        or (head.get("repo") or {}).get("full_name") != repository
    ):
        raise RetirementError(f"{candidate.name}: original closed-PR evidence mismatch")

    # A closed PR is not enough by itself: its preserved GitHub PR-head ref
    # must still resolve to the historical exact commit before retiring the
    # only named source branch. This is read-only, and failure blocks deletion.
    archived_ref = f"refs/pull/{candidate.closed_pr}/head"
    archived = client.get(path + f"/git/ref/pull/{candidate.closed_pr}/head")
    if (
        not isinstance(archived, dict)
        or archived.get("ref") != archived_ref
        or not isinstance(archived.get("object"), dict)
        or archived["object"].get("type") != "commit"
        or archived["object"].get("sha") != candidate.head
    ):
        raise RetirementError(f"{candidate.name}: preserved PR-head ref unavailable or mismatched")

    successor = client.get(path + f"/pulls/{candidate.merged_replacement_pr}")
    if not isinstance(successor, dict):
        raise RetirementError(f"{candidate.name}: malformed replacement PR evidence")
    merge_sha = successor.get("merge_commit_sha")
    if successor.get("merged_at") is None or not isinstance(merge_sha, str) or SHA.fullmatch(merge_sha) is None:
        raise RetirementError(f"{candidate.name}: no verified merged replacement")
    ancestry = client.get(path + "/compare/" + merge_sha + "..." + quote(default, safe=""))
    if (not isinstance(ancestry, dict)
            or ancestry.get("status") not in {"ahead", "identical"}
            or ancestry.get("behind_by") != 0):
        raise RetirementError(f"{candidate.name}: replacement is not in current main ancestry")


def _git(*args: str, cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RetirementError("local Git command is unavailable or timed out") from exc
    if result.returncode:
        raise RetirementError("local Git precondition or lease-guarded push failed")
    return result.stdout.strip()


def verify_local_checkout(repository: str, main_sha: str, cwd: Path) -> None:
    remote = _git("remote", "get-url", "origin", cwd=cwd)
    allowed = {
        f"https://github.com/{repository}.git",
        f"https://github.com/{repository}",
        f"git@github.com:{repository}.git",
        f"ssh://git@github.com/{repository}.git",
    }
    if remote not in allowed:
        raise RetirementError("origin is not the audited GitHub repository")
    # Git can send pushes somewhere other than its fetch URL through
    # remote.origin.pushurl or url.*.pushInsteadOf. Inspect *all effective*
    # destinations instead of assuming that checking the fetch URL is enough.
    push_urls = _git("remote", "get-url", "--push", "--all", "origin", cwd=cwd).splitlines()
    if len(push_urls) != 1 or push_urls[0] != remote:
        raise RetirementError("origin has an unexpected or multiple Git push destinations")
    # A mirror remote must never be a destination for a narrow destructive
    # command, even if a particular Git version rejects mixed mirror/refspecs.
    if _git(
        "config", "--get", "--bool", "--default", "false",
        "remote.origin.mirror", cwd=cwd,
    ) != "false":
        raise RetirementError("origin must not be configured as a push mirror")
    if _git("branch", "--show-current", cwd=cwd) != "main":
        raise RetirementError("checkout must be on main")
    if _git("rev-parse", "HEAD", cwd=cwd) != main_sha:
        raise RetirementError("local main is not the currently verified GitHub main")
    if _git("status", "--porcelain", cwd=cwd):
        raise RetirementError("checkout must be clean")


def run(
    client: Client,
    repository: str,
    default: str,
    candidates: tuple[Candidate, ...],
    *,
    execute: bool,
    attestation: str | None,
    cwd: Path,
) -> list[dict[str, str]]:
    if execute and attestation != ACK:
        raise RetirementError("execution requires explicit evidence/reference attestation")
    if execute and len(candidates) != 1:
        raise RetirementError("execution requires exactly one selected branch per invocation")
    main_sha = current_main(client, repository, default)
    for candidate in candidates:
        verify(client, repository, default, candidate)
    if execute:
        verify_local_checkout(repository, main_sha, cwd)
        if current_main(client, repository, default) != main_sha:
            raise RetirementError("main moved during retirement preflight")
    result = []
    for candidate in candidates:
        if execute:
            # Recheck immediately before deletion; Git's explicit lease prevents
            # deleting a ref that advanced after the check. No force fallback.
            verify(client, repository, default, candidate)
            if current_main(client, repository, default) != main_sha:
                raise RetirementError("main changed during retirement")
            # Revalidate the local checkout and effective push destination
            # immediately before EVERY non-atomic branch deletion. One
            # preflight is insufficient if config changes between candidates.
            verify_local_checkout(repository, main_sha, cwd)
            _git(
                "push", "--porcelain", "--no-verify", "--no-follow-tags",
                f"--force-with-lease=refs/heads/{candidate.name}:{candidate.head}",
                "origin", f":refs/heads/{candidate.name}", cwd=cwd,
            )
        result.append({"branch": candidate.name, "head": candidate.head,
                       "status": "retired" if execute else "eligible_after_manual_evidence_review"})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--branch", help="Exact manifest branch; required for destructive execution")
    parser.add_argument("--execute", action="store_true", help="Delete one exact reviewed ref after independent approval")
    parser.add_argument("--attest", help="Human confirmation that exact SHA, evidence and external references were reviewed")
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        repo, default, candidates = load_manifest(args.manifest)
        if args.execute and args.branch is None:
            raise RetirementError("--execute requires one explicit --branch")
        if args.branch is not None:
            selected = tuple(item for item in candidates if item.name == args.branch)
            if len(selected) != 1:
                raise RetirementError("selected --branch is not in the frozen retirement manifest")
            candidates = selected
        outcome = run(Client(os.environ.get("GITHUB_TOKEN")), repo, default, candidates,
                      execute=args.execute, attestation=args.attest, cwd=args.checkout)
    except RetirementError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"repository": repo, "mode": "executed" if args.execute else "dry_run",
                      "candidates": outcome}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
