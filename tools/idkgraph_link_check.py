#!/usr/bin/env python3
"""Deterministic local Markdown link integrity over canonical IDKGraph T1 identities.

T2 deliberately does not define document or heading identity. It consumes
``idkgraph_markdown_index`` (T1) and adds a navigation/integrity layer:

- inspect inline Markdown links outside fenced/inline code;
- validate only repository-local Markdown-file and fragment targets;
- bind resolved links to canonical T1 document/heading IDs;
- report missing files, missing anchors, root escapes, and duplicate T1 IDs;
- emit deterministic JSON with no repository mutation or semantic inference.

GitHub-style anchors are navigation locators, not IDKGraph identities.

Local links to non-Markdown targets (directories, scripts, schemas, images) stay
outside this contract and are only counted, as ``ignored_non_markdown_links``.
They are not unchecked: ``tests/test_local_asset_link_integrity.py`` resolves
exactly that complement, so a rotted directory or script link still fails a gate.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

try:  # package import in tests
    from .idkgraph_markdown_index import SCHEMA_VERSION as T1_SCHEMA_VERSION
    from .idkgraph_markdown_index import build_index
except ImportError:  # direct ``python tools/...`` execution
    from idkgraph_markdown_index import SCHEMA_VERSION as T1_SCHEMA_VERSION
    from idkgraph_markdown_index import build_index

SCHEMA_VERSION = "idkgraph-link-check-v0.1"
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    source_path: str
    line: int
    raw_target: str
    message: str


@dataclass(frozen=True)
class ResolvedLink:
    source_path: str
    source_document_id: str
    line: int
    raw_target: str
    target_path: str
    target_document_id: str
    target_anchor: str | None
    target_heading_id: str | None


def _clean_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")].strip()

    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char.isspace():
            return value[:index]
    return value


def iter_inline_links(path: Path) -> Iterable[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fence_char: str | None = None
    fence_len = 0

    for line_number, line in enumerate(lines, 1):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_len = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                fence_char = None
                fence_len = 0
            continue
        if fence_char is not None:
            continue

        visible = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(visible):
            destination = _clean_destination(match.group(1))
            if destination:
                yield line_number, destination


def github_anchor_base(text: str) -> str:
    """Conservative GitHub-style locator derived from canonical T1 heading text.

    This is intentionally *not* an identity function. T1 heading IDs remain the
    only canonical heading identity. The locator exists solely to resolve
    Markdown ``#fragment`` navigation.
    """

    text = HTML_TAG_RE.sub("", text).strip().lower()
    chars: list[str] = []
    for char in text:
        if char.isspace():
            chars.append("-")
        elif char.isalnum() or char in "-_":
            chars.append(char)
    return "".join(chars)


def heading_anchor_index(document: dict[str, Any]) -> dict[str, str]:
    """Map navigation anchors to canonical T1 heading identities.

    Suffix allocation is global within one rendered document, not merely per
    base slug. This avoids collisions such as ``Repeat``, ``Repeat-1``,
    ``Repeat`` becoming ``repeat``, ``repeat-1``, ``repeat-1``. The final
    heading instead receives ``repeat-2`` while its canonical T1 identity is
    unchanged.
    """

    occupied: set[str] = set()
    result: dict[str, str] = {}
    headings = sorted(
        document["headings"],
        key=lambda item: (item["line"], item["heading_id"]),
    )
    for heading in headings:
        base = github_anchor_base(heading["text"])
        if not base:
            continue
        anchor = base
        suffix = 0
        while anchor in occupied:
            suffix += 1
            anchor = f"{base}-{suffix}"
        occupied.add(anchor)
        result[anchor] = heading["heading_id"]
    return result


def is_external(destination: str) -> bool:
    parsed = urlsplit(destination)
    return bool(parsed.scheme or parsed.netloc) or destination.startswith("//")


# Private aliases retained so existing internal references keep working; the
# public names above are what out-of-module callers (such as the local asset
# link guard) import, so link extraction cannot drift between the two.
_iter_inline_links = iter_inline_links
_is_external = is_external


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _identity_findings(documents: list[dict[str, Any]]) -> list[Finding]:
    locations: dict[str, list[str]] = {}
    for document in documents:
        locations.setdefault(document["document_id"], []).append(document["path"])
        for heading in document["headings"]:
            locations.setdefault(heading["heading_id"], []).append(
                f"{document['path']}:{heading['line']}"
            )

    findings: list[Finding] = []
    for identity, identity_locations in sorted(locations.items()):
        if len(identity_locations) > 1:
            findings.append(
                Finding(
                    severity="error",
                    category="duplicate_t1_identity",
                    source_path=identity_locations[0].split(":", 1)[0],
                    line=0,
                    raw_target=identity,
                    message="Canonical T1 identity appears more than once: "
                    + ", ".join(identity_locations),
                )
            )
    return findings


def check_links(root: Path) -> dict[str, Any]:
    root = root.resolve()
    t1 = build_index(root)
    documents: list[dict[str, Any]] = t1["documents"]
    by_path = {document["path"]: document for document in documents}
    anchors = {document["path"]: heading_anchor_index(document) for document in documents}

    findings = _identity_findings(documents)
    resolved: list[ResolvedLink] = []
    total_links = 0
    local_markdown_links = 0
    ignored_external = 0
    ignored_non_markdown = 0

    for document in documents:
        source_path = document["path"]
        source_file = root / source_path

        for line, raw_target in iter_inline_links(source_file):
            total_links += 1
            if is_external(raw_target):
                ignored_external += 1
                continue

            parsed = urlsplit(raw_target)
            path_text = unquote(parsed.path)
            fragment = unquote(parsed.fragment).strip().lower()

            if path_text and not path_text.lower().endswith(".md"):
                ignored_non_markdown += 1
                continue

            if path_text.startswith("/"):
                local_markdown_links += 1
                findings.append(
                    Finding(
                        severity="warning",
                        category="repository_absolute_markdown_link",
                        source_path=source_path,
                        line=line,
                        raw_target=raw_target,
                        message=(
                            "Repository-absolute Markdown link is ambiguous on GitHub; "
                            "use a repository-relative .md path."
                        ),
                    )
                )
                continue

            local_markdown_links += 1
            if not path_text:
                target_path = source_path
                target_file = source_file.resolve()
            else:
                target_file = (source_file.parent / path_text).resolve()
                if not _within_root(target_file, root):
                    findings.append(
                        Finding(
                            severity="error",
                            category="target_escapes_repository",
                            source_path=source_path,
                            line=line,
                            raw_target=raw_target,
                            message="Markdown link resolves outside the repository root.",
                        )
                    )
                    continue
                target_path = target_file.relative_to(root).as_posix()

            if not target_file.is_file() or target_path not in by_path:
                findings.append(
                    Finding(
                        severity="error",
                        category="missing_markdown_file",
                        source_path=source_path,
                        line=line,
                        raw_target=raw_target,
                        message=f"Markdown target does not exist in the canonical T1 index: {target_path}",
                    )
                )
                continue

            target_document = by_path[target_path]
            heading_id: str | None = None
            target_anchor: str | None = None
            if fragment:
                target_anchor = fragment
                heading_id = anchors[target_path].get(fragment)
                if heading_id is None:
                    findings.append(
                        Finding(
                            severity="error",
                            category="missing_markdown_anchor",
                            source_path=source_path,
                            line=line,
                            raw_target=raw_target,
                            message=(
                                f"Markdown target exists but anchor #{fragment} was not found "
                                f"in {target_path}."
                            ),
                        )
                    )
                    continue

            resolved.append(
                ResolvedLink(
                    source_path=source_path,
                    source_document_id=document["document_id"],
                    line=line,
                    raw_target=raw_target,
                    target_path=target_path,
                    target_document_id=target_document["document_id"],
                    target_anchor=target_anchor,
                    target_heading_id=heading_id,
                )
            )

    resolved.sort(
        key=lambda item: (
            item.source_path,
            item.line,
            item.raw_target,
            item.target_path,
            item.target_anchor or "",
        )
    )
    findings.sort(
        key=lambda item: (
            item.severity,
            item.category,
            item.source_path,
            item.line,
            item.raw_target,
            item.message,
        )
    )

    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "identity_contract": T1_SCHEMA_VERSION,
        "root": ".",
        "summary": {
            "documents_scanned": len(documents),
            "links_seen": total_links,
            "local_markdown_links": local_markdown_links,
            "resolved_local_markdown_links": len(resolved),
            "ignored_external_links": ignored_external,
            "ignored_non_markdown_links": ignored_non_markdown,
            "errors": errors,
            "warnings": warnings,
        },
        "resolved_links": [asdict(item) for item in resolved],
        "findings": [asdict(item) for item in findings],
        "authority": {
            "repository_write": False,
            "github_mutation": False,
            "semantic_inference": False,
            "identity_definition": False,
        },
    }


def serialize_report(report: dict[str, Any], *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repository root to inspect.")
    parser.add_argument("--output", help="Write deterministic JSON to this path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit 1 when deterministic integrity errors are present.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    report = check_links(root)
    payload = serialize_report(report, pretty=args.pretty)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    if args.fail_on_errors and report["summary"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
