#!/usr/bin/env python3
"""Deterministic guard against unintended GitHub issue auto-closure.

GitHub closes an issue whenever a closing keyword (``close``/``fix``/``resolve``
and their inflections) appears near an issue reference. It applies that rule to
pull request titles and bodies *and* to commit messages, and it ignores any
disclaimer written alongside the reference: a line reading
``Closes: Refs #<issue> (does not close)`` still closes that issue on merge.

That behaviour is hostile to this repository. Evidence pull requests routinely
land while an independent-human review gate stays open, so "refs" and "closes"
carry genuinely different meanings here. A silent auto-closure posts a false
"resolved" status on a public repository and dissolves the gate.

This module reports every keyword/reference pair that would close an issue,
except on the pull request template's sanctioned ``Closes on merge:`` line,
which is the explicit opt-in. It inspects text only: no network access, no
repository mutation, and no inference about whether a closure was desired.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

SCHEMA_VERSION = "closing-keyword-guard-v0.1"

# GitHub's documented closing keywords, with the inflections it accepts.
KEYWORD_PATTERN = r"clos(?:e|es|ed)|fix(?:|es|ed)|resolv(?:e|es|ed)"

# The reference forms GitHub resolves to an issue: bare, cross-repository,
# the legacy ``GH-`` form, and a full issue URL.
REFERENCE_PATTERN = (
    r"#\d+"
    r"|GH-\d+"
    r"|[A-Za-z0-9._-]+/[A-Za-z0-9._-]+#\d+"
    r"|https?://github\.com/[^/\s]+/[^/\s]+/issues/\d+"
)

# GitHub tolerates punctuation and a few filler words between the keyword and
# the reference; PR #315 was closed through ``Closes: Refs #152``. The window is
# deliberately generous, because a false positive costs one rephrasing while a
# false negative silently closes someone else's review gate.
GAP_LIMIT = 40

PAIR_RE = re.compile(
    rf"(?P<keyword>(?<![A-Za-z0-9_])(?:{KEYWORD_PATTERN})(?![A-Za-z0-9_]))"
    rf"(?P<gap>.{{0,{GAP_LIMIT}}}?)"
    rf"(?P<reference>{REFERENCE_PATTERN})",
    re.IGNORECASE | re.DOTALL,
)

# The pull request template's explicit opt-in line.
SANCTIONED_LINE_RE = re.compile(r"^\s*(?:[-*+]\s*)?closes on merge\b", re.IGNORECASE)

# A blank line ends the association in practice; do not report across one.
PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n")


@dataclass(frozen=True)
class Violation:
    """One keyword/reference pair that would close an issue."""

    source: str
    line: int
    keyword: str
    reference: str
    line_text: str
    message: str


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _line_text(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def scan_text(text: str, *, source: str) -> list[Violation]:
    """Report keyword/reference pairs in ``text`` that are not sanctioned."""

    violations: list[Violation] = []
    for match in PAIR_RE.finditer(text or ""):
        if PARAGRAPH_BREAK_RE.search(match.group("gap")):
            continue
        line_text = _line_text(text, match.start("keyword"))
        if SANCTIONED_LINE_RE.match(line_text):
            continue
        keyword = match.group("keyword")
        reference = match.group("reference")
        violations.append(
            Violation(
                source=source,
                line=_line_number(text, match.start("keyword")),
                keyword=keyword,
                reference=reference,
                line_text=line_text,
                message=(
                    f"{keyword!r} sits {len(match.group('gap'))} characters before "
                    f"{reference!r}, so merging would close that issue."
                ),
            )
        )
    return violations


def scan_sources(sources: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """Build a deterministic report over ``(source_name, text)`` pairs."""

    violations: list[Violation] = []
    scanned: list[str] = []
    for name, text in sources:
        scanned.append(name)
        violations.extend(scan_text(text, source=name))
    return {
        "schema_version": SCHEMA_VERSION,
        "sources_scanned": scanned,
        "violations": [asdict(v) for v in violations],
        "summary": {"sources": len(scanned), "violations": len(violations)},
    }


def serialize_report(report: dict[str, Any], *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


REMEDY = """
How to fix this:

  * If the merge SHOULD close the issue, move the reference onto the pull
    request template's line:
        - Closes on merge (leave blank unless the merge should close it): #<n>
  * Otherwise write the number without '#', for example "issue 152" or
    "PR 315", or move the reference onto the template's 'Refs:' line.

A parenthetical such as "(does not close)" does NOT prevent closure.
""".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text",
        action="append",
        default=[],
        metavar="NAME=TEXT",
        help="Inline source to scan, as NAME=TEXT.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="File source to scan, as NAME=PATH. A missing path is skipped.",
    )
    parser.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    sources: list[tuple[str, str]] = []
    for item in args.text:
        name, _, text = item.partition("=")
        sources.append((name, text))
    for item in args.file:
        name, _, raw = item.partition("=")
        path = Path(raw)
        if not path.is_file():
            continue
        sources.append((name, path.read_text(encoding="utf-8", errors="replace")))

    report = scan_sources(sources)

    if args.json:
        sys.stdout.write(serialize_report(report, pretty=args.pretty))
    else:
        for violation in report["violations"]:
            print(
                f"{violation['source']}:{violation['line']}: "
                f"{violation['keyword']} -> {violation['reference']}"
            )
            print(f"    {violation['line_text']}")
        print(f"sources scanned: {report['summary']['sources']}")
        print(f"closing-keyword violations: {report['summary']['violations']}")
        if report["violations"]:
            print()
            print(REMEDY)

    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
