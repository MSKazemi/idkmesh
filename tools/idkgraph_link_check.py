#!/usr/bin/env python3
"""Deterministic repository-local Markdown link diagnostics for IDKGraph P0."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.idkgraph_markdown_index import discover_markdown, parse_markdown

SCHEMA_VERSION = "idkgraph-link-diagnostics-v0.1"
INLINE_LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
REFERENCE_LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\[[^\]\n]*\]")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
EXPLICIT_HTML_ID = re.compile(r"<[^>]+\bid=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
EXTERNAL_SCHEMES = {"http", "https", "mailto", "ftp", "ftps", "tel", "data"}
GITHUB_NAVIGATION_ROOTS = {"actions", "commit", "commits", "compare", "discussions", "issues", "pull", "pulls", "releases"}


def github_like_anchor_base(text: str) -> str:
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\-\s]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def anchor_index(path: Path, root: Path) -> set[str]:
    parsed = parse_markdown(path, root)
    anchors: set[str] = set()
    for heading in parsed["headings"]:
        base = github_like_anchor_base(heading["text"])
        if not base:
            continue
        anchor = base
        suffix = 0
        while anchor in anchors:
            suffix += 1
            anchor = f"{base}-{suffix}"
        anchors.add(anchor)
    text = path.read_text(encoding="utf-8")
    for match in EXPLICIT_HTML_ID.finditer(text):
        anchors.add(unicodedata.normalize("NFC", match.group(1)))
    return anchors


def _iter_non_fenced_lines(lines: list[str]) -> Iterable[tuple[int, str]]:
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line_number, line in enumerate(lines, start=1):
        fence_match = FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            char = marker[0]
            if not in_fence:
                in_fence = True
                fence_char = char
                fence_len = len(marker)
            elif char == fence_char and len(marker) >= fence_len:
                in_fence = False
                fence_char = ""
                fence_len = 0
            continue
        if not in_fence:
            yield line_number, line


def _extract_destination(raw_target: str) -> str | None:
    value = raw_target.strip()
    if not value:
        return None
    if value.startswith("<"):
        end = value.find(">")
        return None if end < 0 else value[1:end]
    return value.split(maxsplit=1)[0]


def _looks_like_github_navigation(decoded_path: str) -> bool:
    parts = [part for part in decoded_path.replace("\\", "/").split("/") if part not in {"", "."}]
    parent_count = 0
    while parts and parts[0] == "..":
        parent_count += 1
        parts.pop(0)
    return parent_count > 0 and bool(parts) and parts[0] in GITHUB_NAVIGATION_ROOTS


def _resolve_exclusions(root: Path, excluded_paths: Iterable[str | Path]) -> tuple[list[Path], list[str]]:
    resolved: list[tuple[str, Path]] = []
    for raw in excluded_paths:
        relative = Path(raw)
        if relative.is_absolute():
            raise ValueError(f"exclude path must be repository-relative: {raw}")
        candidate = (root / relative).resolve()
        try:
            normalized = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"exclude path is outside repository root: {raw}") from exc
        if not candidate.exists():
            raise ValueError(f"exclude path does not exist: {raw}")
        resolved.append((normalized, candidate))
    resolved.sort(key=lambda item: item[0])
    return [item[1] for item in resolved], [item[0] for item in resolved]


def _finding(*, source: str, line: int, raw_target: str, normalized_target_path: str | None, target_anchor: str | None, category: str, severity: str) -> dict[str, Any]:
    return {
        "source_document": source,
        "line": line,
        "raw_target": raw_target,
        "normalized_target_path": normalized_target_path,
        "target_anchor": target_anchor,
        "category": category,
        "severity": severity,
    }


def check_repository(root: Path, excluded_paths: Iterable[str | Path] = ()) -> dict[str, Any]:
    root = root.resolve()
    exclusions, normalized_exclusions = _resolve_exclusions(root, excluded_paths)
    documents = [
        path for path in discover_markdown(root)
        if not any(path == excluded or excluded in path.parents for excluded in exclusions)
    ]
    anchor_cache: dict[Path, set[str]] = {}
    findings: list[dict[str, Any]] = []
    links_checked = 0
    external_links_skipped = 0

    for source_path in documents:
        source_rel = source_path.relative_to(root).as_posix()
        lines = source_path.read_text(encoding="utf-8").splitlines()
        for line_number, line in _iter_non_fenced_lines(lines):
            for match in REFERENCE_LINK.finditer(line):
                findings.append(_finding(source=source_rel, line=line_number, raw_target=match.group(0), normalized_target_path=None, target_anchor=None, category="unsupported_reference_link", severity="warning"))

            for match in INLINE_LINK.finditer(line):
                raw_target = match.group(1)
                destination = _extract_destination(raw_target)
                links_checked += 1
                if destination is None:
                    findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=None, target_anchor=None, category="unsupported_inline_destination", severity="warning"))
                    continue

                parsed = urlsplit(destination)
                scheme = parsed.scheme.lower()
                if scheme in EXTERNAL_SCHEMES or parsed.netloc or destination.startswith("//"):
                    external_links_skipped += 1
                    continue
                if scheme:
                    findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=None, target_anchor=unquote(parsed.fragment) or None, category="unsupported_uri_scheme", severity="warning"))
                    continue

                decoded_path = unquote(parsed.path)
                target_anchor = unquote(parsed.fragment) or None
                if decoded_path.startswith("/"):
                    findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=None, target_anchor=target_anchor, category="unsupported_root_absolute_link", severity="warning"))
                    continue

                candidate = (source_path.parent / decoded_path).resolve() if decoded_path else source_path.resolve()
                try:
                    relative_candidate = candidate.relative_to(root)
                except ValueError:
                    if _looks_like_github_navigation(decoded_path):
                        findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=None, target_anchor=target_anchor, category="github_navigation_link", severity="warning"))
                    else:
                        findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=None, target_anchor=target_anchor, category="outside_repository", severity="error"))
                    continue

                normalized_path = relative_candidate.as_posix()
                if not candidate.exists():
                    findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=normalized_path, target_anchor=target_anchor, category="missing_file", severity="error"))
                    continue

                if target_anchor:
                    if not candidate.is_file() or candidate.suffix.lower() != ".md":
                        findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=normalized_path, target_anchor=target_anchor, category="unsupported_anchor_target", severity="warning"))
                        continue
                    anchors = anchor_cache.setdefault(candidate, anchor_index(candidate, root))
                    if target_anchor not in anchors:
                        findings.append(_finding(source=source_rel, line=line_number, raw_target=raw_target, normalized_target_path=normalized_path, target_anchor=target_anchor, category="missing_anchor", severity="error"))

    findings.sort(key=lambda item: (item["source_document"], item["line"], item["raw_target"], item["category"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "documents_scanned": len(documents),
        "links_checked": links_checked,
        "external_links_skipped": external_links_skipped,
        "excluded_paths": normalized_exclusions,
        "error_count": sum(item["severity"] == "error" for item in findings),
        "warning_count": sum(item["severity"] == "warning" for item in findings),
        "findings": findings,
    }


def serialize_report(report: dict[str, Any], pretty: bool = False) -> str:
    if pretty:
        return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repository-local Markdown links deterministically.")
    parser.add_argument("root", nargs="?", default=".", help="Repository or fixture root.")
    parser.add_argument("--output", help="Write JSON report to this file instead of stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATH", help="Repository-relative file/directory to exclude from this scan; repeatable.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero when deterministic broken-link errors are present.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")
    try:
        report = check_repository(root, excluded_paths=args.exclude)
    except ValueError as exc:
        parser.error(str(exc))

    payload = serialize_report(report, pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 1 if args.fail_on_error and report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
