#!/usr/bin/env python3
"""Deterministic Markdown document and heading identity for IDKGraph P0.

Identity rule:
- document ID = SHA-256("document\0" + repository-relative POSIX path), truncated to 24 hex chars.
- heading ID = SHA-256(
    "heading\0" + path + "\0" + level + "\0" + normalized heading text + "\0" + occurrence
  ), truncated to 24 hex chars.
- occurrence is 1-based among headings in the same document with the same normalized text and level.

Source line is metadata and is intentionally excluded from identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "idkgraph-markdown-index-v0.1"

ATX_HEADING = re.compile(r"^[ \t]{0,3}(#{1,6})(?:[ \t]+|$)(.*)$")
SETEXT_UNDERLINE = re.compile(r"^[ \t]{0,3}(=+|-+)[ \t]*$")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")


def normalize_heading_text(text: str) -> str:
    """Normalize heading text without lossy ASCII-only slugification."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[ \t]+#+[ \t]*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _digest(*parts: str) -> str:
    payload = chr(0).join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def document_id(relative_path: str) -> str:
    return f"doc:{_digest('document', relative_path)}"


def heading_id(relative_path: str, level: int, normalized_text: str, occurrence: int) -> str:
    return f"heading:{_digest('heading', relative_path, str(level), normalized_text, str(occurrence))}"


def _iter_headings(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    """Yield ``(line_number, level, raw_text)`` for ATX and setext headings.

    Fenced code blocks are skipped. Setext headings use the source line containing
    the heading text, not the underline line.
    """
    in_fence = False
    fence_char = ""
    fence_len = 0

    i = 0
    while i < len(lines):
        line = lines[i]
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
            i += 1
            continue

        if in_fence:
            i += 1
            continue

        atx = ATX_HEADING.match(line)
        if atx:
            level = len(atx.group(1))
            raw_text = atx.group(2)
            yield i + 1, level, raw_text
            i += 1
            continue

        if i + 1 < len(lines) and line.strip():
            underline = SETEXT_UNDERLINE.match(lines[i + 1])
            if underline:
                level = 1 if underline.group(1).startswith("=") else 2
                yield i + 1, level, line.strip()
                i += 2
                continue

        i += 1


def parse_markdown(path: Path, root: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()

    occurrences: dict[tuple[int, str], int] = defaultdict(int)
    headings: list[dict[str, Any]] = []

    for line_number, level, raw_text in _iter_headings(lines):
        text = normalize_heading_text(raw_text)
        if not text:
            continue
        key = (level, text)
        occurrences[key] += 1
        occurrence = occurrences[key]
        headings.append(
            {
                "heading_id": heading_id(relative_path, level, text, occurrence),
                "text": text,
                "level": level,
                "occurrence": occurrence,
                "line": line_number,
            }
        )

    return {
        "path": relative_path,
        "document_id": document_id(relative_path),
        "headings": headings,
    }


def discover_markdown(root: Path) -> list[Path]:
    root = root.resolve()
    paths = [
        path
        for path in root.rglob("*.md")
        if ".git" not in path.relative_to(root).parts and path.is_file()
    ]
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    documents = [parse_markdown(path, root) for path in discover_markdown(root)]
    return {"schema_version": SCHEMA_VERSION, "documents": documents}


def serialize_index(index: dict[str, Any], pretty: bool = False) -> str:
    if pretty:
        return json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit deterministic Markdown document/heading identities for IDKGraph."
    )
    parser.add_argument("root", nargs="?", default=".", help="Repository root to scan.")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    payload = serialize_index(build_index(root), pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
