#!/usr/bin/env python3
"""Deterministic repository-local Markdown link diagnostics for IDKGraph P0.

Scope is intentionally conservative:
- inline Markdown links of the form ``[label](target)``;
- repository-relative targets only;
- Markdown heading anchors derived from the T1 heading extractor;
- external URLs are skipped without network access;
- reference-style Markdown links are reported as unsupported warnings rather
  than guessed.

The checker distinguishes deterministic missing-file and missing-anchor errors.
It does not judge whether a valid link is semantically useful.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

from tools.idkgraph_markdown_index import discover_markdown, parse_markdown

SCHEMA_VERSION = "idkgraph-link-diagnostics-v0.1"

INLINE_LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
REFERENCE_LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\[[^\]\n]*\]")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
EXPLICIT_HTML_ID = re.compile(r"<[^>]+\bid=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
EXTERNAL_SCHEMES = {"http", "https", "mailto", "ftp", "ftps", "tel", "data", "javascript"}


def github_like_anchor_base(text: str) -> str:
    """Return a deterministic GitHub-like heading slug.

    This is a deliberately small approximation for ordinary repository
    headings: Unicode is preserved, text is lowercased, punctuation other than
    ``-``/``_`` is removed, and whitespace becomes ``-``. Complex rendered
    Markdown inside headings is outside this P0 parser's promise.
    """
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\-\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text


def anchor_index(path: Path, root: Path) -> set[str]:
    """Build deterministic heading/explicit-ID anchors for one Markdown file.

    Suffix allocation is collision-aware across all generated slugs. For
    example, headings ``Repeat``, ``Repeat-1``, ``Repeat`` become
    ``repeat``, ``repeat-1``, ``repeat-2`` rather than producing a duplicate.
    """
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
        if end < 0:
            return None
        return value[1:end]
    # Markdown permits an optional title after whitespace. URL-escaped spaces
    # remain part of the destination and are decoded later.
    return value.split(maxsplit=1)[0]


def _finding(
    *,
    source: str,
    line: int,
    raw_target: str,
    normalized_target_path: str | None,
    target_anchor: str | None,
    category: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "source_document": source,
        "line": line,
        "raw_target": raw_target,
        "normalized_target_path": normalized_target_path,
        "target_anchor": target_anchor,
        "category": category,
        "severity": severity,
    }


def check_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    documents = discover_markdown(root)
    anchor_cache: dict[Path, set[str]] = {}
    findings: list[dict[str, Any]] = []
    links_checked = 0
    external_links_skipped = 0

    for source_path in documents:
        source_rel = source_path.relative_to(root).as_posix()
        lines = source_path.read_text(encoding="utf-8").splitlines()

        for line_number, line in _iter_non_fenced_lines(lines):
            # Reference-style links are deliberately not resolved in P0 because
            # their definitions and shortcut forms require a broader parser.
            for match in REFERENCE_LINK.finditer(line):
                findings.append(
                    _finding(
                        source=source_rel,
                        line=line_number,
                        raw_target=match.group(0),
                        normalized_target_path=None,
                        target_anchor=None,
                        category="unsupported_reference_link",
                        severity="warning",
                    )
                )

            for match in INLINE_LINK.finditer(line):
                raw_target = match.group(1)
                destination = _extract_destination(raw_target)
                links_checked += 1

                if destination is None:
                    findings.append(
                        _finding(
                            source=source_rel,
                            line=line_number,
                            raw_target=raw_target,
                            normalized_target_path=None,
                            target_anchor=None,
                            category="unsupported_inline_destination",
                            severity="warning",
                        )
                    )
                    continue

                parsed = urlsplit(destination)
                scheme = parsed.scheme.lower()
                if scheme in EXTERNAL_SCHEMES or parsed.netloc or destination.startswith("//"):
                    external_links_skipped += 1
                    continue
                if scheme:
                    findings.append(
                        _finding(
                            source=source_rel,
                            line=line_number,
                            raw_target=raw_target,
                            normalized_target_path=None,
                            target_anchor=unquote(parsed.fragment) or None,
                            category="unsupported_uri_scheme",
                            severity="warning",
                        )
                    )
                    continue

                decoded_path = unquote(parsed.path)
                target_anchor = unquote(parsed.fragment) or None

                if decoded_path.startswith("/"):
                    findings.append(
                        _finding(
                            source=source_rel,
                            line=line_number,
                            raw_target=raw_target,
                            normalized_target_path=None,
                            target_anchor=target_anchor,
                            category="unsupported_root_absolute_link",
                            severity="warning",
                        )
                    )
                    continue

                if decoded_path:
                    candidate = (source_path.parent / decoded_path).resolve()
                else:
                    candidate = source_path.resolve()

                try:
                    relative_candidate = candidate.relative_to(root)
                except ValueError:
                    findings.append(
                        _finding(
                            source=source_rel,
                            line=line_number,
                            raw_target=raw_target,
                            normalized_target_path=None,
                            target_anchor=target_anchor,
                            category="outside_repository",
                            severity="error",
                        )
                    )
                    continue

                normalized_path = relative_candidate.as_posix()
                if not candidate.exists():
                    findings.append(
                        _finding(
                            source=source_rel,
                            line=line_number,
                            raw_target=raw_target,
                            normalized_target_path=normalized_path,
                            target_anchor=target_anchor,
                            category="missing_file",
                            severity="error",
                        )
                    )
                    continue

                if target_anchor:
                    if not candidate.is_file() or candidate.suffix.lower() != ".md":
                        findings.append(
                            _finding(
                                source=source_rel,
                                line=line_number,
                                raw_target=raw_target,
                                normalized_target_path=normalized_path,
                                target_anchor=target_anchor,
                                category="unsupported_anchor_target",
                                severity="warning",
                            )
                        )
                        continue

                    anchors = anchor_cache.setdefault(candidate, anchor_index(candidate, root))
                    if target_anchor not in anchors:
                        findings.append(
                            _finding(
                                source=source_rel,
                                line=line_number,
                                raw_target=raw_target,
                                normalized_target_path=normalized_path,
                                target_anchor=target_anchor,
                                category="missing_anchor",
                                severity="error",
                            )
                        )

    findings.sort(
        key=lambda item: (
            item["source_document"],
            item["line"],
            item["raw_target"],
            item["category"],
        )
    )
    error_count = sum(item["severity"] == "error" for item in findings)
    warning_count = sum(item["severity"] == "warning" for item in findings)

    return {
        "schema_version": SCHEMA_VERSION,
        "documents_scanned": len(documents),
        "links_checked": links_checked,
        "external_links_skipped": external_links_skipped,
        "error_count": error_count,
        "warning_count": warning_count,
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
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero when deterministic broken-link errors are present.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    report = check_repository(root)
    payload = serialize_report(report, pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    return 1 if args.fail_on_error and report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
