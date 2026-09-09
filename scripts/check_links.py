#!/usr/bin/env python3
"""One read-only local/CI gate for Markdown and tracked non-Markdown links.

T1/T2 remain responsible for Markdown identity and anchor validation. Asset
resolution is extracted from tests/test_local_asset_link_integrity.py so tests
and contributors use the same implementation. Only tests/fixtures/ sources are
excluded. External URLs are never requested. GitHub navigation-route exemptions
and repository-absolute asset exclusions retain the existing guard's scope;
this is not a complete CommonMark parser or a website availability checker.

Exit 0: no non-fixture findings; 1: findings; 2: inspection unavailable/invalid.
Run from any directory; an optional root selects another Git working tree.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idkgraph_link_check import check_links, is_external, iter_inline_links
from tools.idkgraph_markdown_index import build_index

EXCLUDED_PREFIXES = ("tests/fixtures/",)
GITHUB_ROUTES = frozenset({
    "issues", "pull", "pulls", "discussions", "wiki", "blob", "tree", "raw",
    "actions", "releases", "tags", "labels", "milestones", "projects",
    "security", "compare", "commits", "commit",
})


def _github_route(path_text: str) -> str | None:
    segments = [s for s in path_text.split("/") if s not in ("", ".")]
    while segments and segments[0] == "..":
        segments.pop(0)
    return segments[0] if segments and segments[0] in GITHUB_ROUTES else None


def tracked_paths(root: Path) -> frozenset[str]:
    """Tracked files and implied POSIX directories; unavailable Git raises.

    Untracked/generated assets must not make a broken link pass locally when
    it would fail in a fresh checkout. No files are added to the Git index.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root,
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")
    known: set[str] = set()
    for entry in listed.split("\0"):
        if entry:
            known.add(entry)
            known.update(
                p.as_posix() for p in PurePosixPath(entry).parents
                if p != PurePosixPath(".")
            )
    return frozenset(known)


def classify_link(
    root: Path, source_path: str, raw_target: str,
    known: frozenset[str] | None = None,
) -> str:
    """Classify a raw local asset URL as exists/github_route/missing/escapes.

    Parse URL syntax before decoding the path, exactly once. For example,
    %23 is a filename character, not a fragment separator introduced mid-scan.
    Index membership is authoritative, as in the pre-existing asset guard.
    """
    if known is None:
        known = tracked_paths(root)
    path_text = unquote(urlsplit(raw_target).path)
    route = _github_route(path_text)
    target = (root / source_path).parent / path_text
    try:
        resolved = target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "github_route" if route else "escapes"
    if resolved == ".":
        return "exists"
    if route and resolved not in known:
        return "github_route"
    return "exists" if resolved in known else "missing"


def collect_local_non_markdown_links(
    root: Path, known: frozenset[str] | None = None,
) -> list[tuple[str, int, str, str]]:
    """Return source, line, raw destination and verdict in deterministic order."""
    if known is None:
        known = tracked_paths(root)
    results: list[tuple[str, int, str, str]] = []
    for document in build_index(root)["documents"]:
        source = document["path"]
        if source.startswith(EXCLUDED_PREFIXES):
            continue
        for line, raw_target in iter_inline_links(root / source):
            if is_external(raw_target):
                continue
            path_text = unquote(urlsplit(raw_target).path)
            if (not path_text or path_text.lower().endswith(".md")
                    or path_text.startswith("/")):
                continue
            # Keep the ORIGINAL URL. Passing path_text here decodes it twice and
            # can turn an encoded filename suffix into URL syntax or another file.
            results.append(
                (source, line, raw_target, classify_link(root, source, raw_target, known))
            )
    return sorted(results)


def check_repository_links(root: Path) -> dict[str, Any]:
    """Combine the unchanged T2 report and its complementary asset guard."""
    root = root.resolve()
    known = tracked_paths(root)  # Fail before scanning when Git is unavailable.
    markdown = check_links(root)
    assets = collect_local_non_markdown_links(root, known)
    findings = [
        dict(f) for f in markdown["findings"]
        if not f["source_path"].startswith(EXCLUDED_PREFIXES)
    ]
    for source, line, raw_target, verdict in assets:
        if verdict in ("missing", "escapes"):
            findings.append({
                "severity": "error",
                "category": ("missing_local_asset" if verdict == "missing"
                             else "asset_escapes_repository"),
                "source_path": source, "line": line, "raw_target": raw_target,
                "message": ("Local asset is absent from the Git index."
                            if verdict == "missing" else
                            "Local asset escapes the repository and is not a GitHub route."),
            })
    findings.sort(key=lambda f: (f["source_path"], f["line"], f["category"], f["raw_target"]))
    return {
        "schema_version": "local-link-gate-v0.1",
        "root": ".",
        "summary": {
            "documents_scanned": markdown["summary"]["documents_scanned"],
            "local_asset_links": len(assets),
            "findings": len(findings),
        },
        "findings": findings,
        "authority": {"repository_write": False, "network": False, "github_mutation": False},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(ROOT), help="Git working tree to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit a deterministic JSON report.")
    args = parser.parse_args(argv)
    try:
        report = check_repository_links(Path(args.root))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"link inspection unavailable: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        for finding in report["findings"]:
            print(f"{finding['severity']}: {finding['source_path']}:{finding['line']} "
                  f"{finding['message']} ({finding['raw_target']})")
        print(f"non-fixture link findings: {report['summary']['findings']}")
        print(f"local asset links checked: {report['summary']['local_asset_links']}")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
