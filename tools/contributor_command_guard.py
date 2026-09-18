#!/usr/bin/env python3
"""Guard current contributor documentation against executable-command drift.

The guard intentionally inspects the repository's canonical contributor and
first-contact surfaces: ``README.md``, ``AGENTS.md``, ``CONTRIBUTING.md``,
``docs/TESTING.md``, ``Makefile``, and ``pytest.ini``. Historical GitHub issues
and pull-request prose are evidence, not live configuration, so they are
deliberately outside this tool's scope.

The checks are narrow and deterministic:

* every ``make <target>`` shown in canonical Markdown code/inline-code exists in
  the current Makefile;
* all canonical contributor docs expose the same baseline setup/test/integration
  commands plus a direct-Python pytest path;
* canonical docs do not assert that committed testing infrastructure is absent
  or unmerged;
* when ``pytest.ini`` sets ``pythonpath = .``, shell examples must not reintroduce
  ``PYTHONPATH=.`` as a pytest requirement.

No network access, issue scraping, mutation, timing measurement, or external
package is involved. This is a consistency check over committed text and
executable entry points, not a claim that every documented platform has been
independently exercised.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DOCS = ("README.md", "AGENTS.md", "CONTRIBUTING.md", "docs/TESTING.md")
REQUIRED_COMMANDS = ("make setup", "make test", "make integration")

MAKE_TARGET_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_-]*):(?:\s|$)", re.MULTILINE
)
MAKE_COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_-])make[ \t]+([A-Za-z0-9][A-Za-z0-9_-]*)\b"
)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
DIRECT_PYTEST_RE = re.compile(r"\bpython(?:\.exe)?\s+-m\s+pytest\b", re.IGNORECASE)
PYTHONPATH_ASSIGNMENT_RE = re.compile(
    r"(?:^|[;\s])(?:PYTHONPATH\s*=\s*\.|\$env:PYTHONPATH\s*=\s*[\"']?\.[\"']?)",
    re.IGNORECASE,
)
PYTEST_RE = re.compile(r"\b(?:python(?:\.exe)?\s+-m\s+pytest|pytest)\b", re.IGNORECASE)

# These patterns describe a *current-state assertion*. Keep them deliberately
# grammatical rather than fuzzy so a correction such as "if an older issue
# says these targets are unmerged, treat that as history" remains valid
# provenance and does not trip the guard.
STALE_CURRENT_STATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "unmerged-make-command",
        re.compile(
            r"\b(?:do not|don't)\s+(?:assume|depend\s+on|use)\b.{0,80}"
            r"\bunmerged\b.{0,40}\bmake\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "makefile-not-current",
        re.compile(
            r"\b(?:the\s+)?Makefile\s+(?:is|remains)\s+(?:still\s+)?"
            r"(?:unmerged|absent|missing|not\s+on\s+main)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "testkit-not-current",
        re.compile(
            r"\bscripts/testkit\.py\s+(?:is|remains)\s+(?:still\s+)?"
            r"(?:unmerged|absent|missing|not\s+on\s+main)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, order=True)
class Finding:
    """One deterministic contributor-documentation inconsistency."""

    source: str
    code: str
    detail: str

    def render(self) -> str:
        return f"{self.source}: [{self.code}] {self.detail}"


def parse_makefile_targets(text: str) -> set[str]:
    """Return simple named Makefile targets exposed to contributors."""

    return {match.group(1) for match in MAKE_TARGET_RE.finditer(text)}


def fenced_code_blocks(text: str) -> list[str]:
    """Return Markdown fenced-code bodies without interpreting the language."""

    blocks: list[str] = []
    current: list[str] | None = None
    fence_char: str | None = None
    fence_len = 0

    for line in text.splitlines():
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if current is None:
            if marker:
                token = marker.group(1)
                fence_char = token[0]
                fence_len = len(token)
                current = []
            continue

        if marker and marker.group(1)[0] == fence_char and len(marker.group(1)) >= fence_len:
            blocks.append("\n".join(current))
            current = None
            fence_char = None
            fence_len = 0
            continue
        current.append(line)

    return blocks


def command_segments(text: str) -> Iterable[str]:
    """Yield code surfaces where Markdown presents literal commands."""

    yield from fenced_code_blocks(text)
    for match in INLINE_CODE_RE.finditer(text):
        yield match.group(1)


def documented_make_targets(text: str) -> set[str]:
    """Extract ``make <target>`` only from literal-code Markdown surfaces."""

    targets: set[str] = set()
    for segment in command_segments(text):
        targets.update(match.group(1) for match in MAKE_COMMAND_RE.finditer(segment))
    return targets


def _uses_obsolete_pytest_pythonpath(block: str) -> bool:
    return bool(PYTHONPATH_ASSIGNMENT_RE.search(block) and PYTEST_RE.search(block))


def inspect_document(
    *,
    name: str,
    text: str,
    make_targets: set[str],
    pytest_root_is_configured: bool,
) -> list[Finding]:
    """Check one canonical Markdown document against current executable state."""

    findings: list[Finding] = []

    for target in sorted(documented_make_targets(text) - make_targets):
        findings.append(
            Finding(
                source=name,
                code="missing-make-target",
                detail=f"documents `make {target}`, but Makefile has no {target!r} target",
            )
        )

    for command in REQUIRED_COMMANDS:
        if command not in text:
            findings.append(
                Finding(
                    source=name,
                    code="missing-canonical-command",
                    detail=f"does not expose the canonical `{command}` entry point",
                )
            )
        )

    if DIRECT_PYTEST_RE.search(text) is None:
        findings.append(
            Finding(
                source=name,
                code="missing-direct-python-fallback",
                detail="does not document a direct `python -m pytest` fallback",
            )
        )

    for code, pattern in STALE_CURRENT_STATE_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    source=name,
                    code=code,
                    detail="states that committed testing infrastructure is absent or unmerged",
                )
            )

    if pytest_root_is_configured:
        for index, block in enumerate(fenced_code_blocks(text), start=1):
            if _uses_obsolete_pytest_pythonpath(block):
                findings.append(
                    Finding(
                        source=name,
                        code="obsolete-pytest-pythonpath",
                        detail=(
                            f"fenced code block {index} reintroduces `PYTHONPATH=.` for pytest "
                            "even though pytest.ini sets `pythonpath = .`"
                        ),
                    )
                )

    return findings


def inspect_repository(root: Path = REPO_ROOT) -> list[Finding]:
    """Check only canonical committed contributor surfaces under ``root``."""

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    pytest_ini = (root / "pytest.ini").read_text(encoding="utf-8")
    make_targets = parse_makefile_targets(makefile)
    pytest_root_is_configured = bool(
        re.search(r"^\s*pythonpath\s*=\s*\.\s*$", pytest_ini, re.MULTILINE)
    )

    findings: list[Finding] = []
    docs: dict[str, str] = {}
    for name in CANONICAL_DOCS:
        text = (root / name).read_text(encoding="utf-8")
        docs[name] = text
        findings.extend(
            inspect_document(
                name=name,
                text=text,
                make_targets=make_targets,
                pytest_root_is_configured=pytest_root_is_configured,
            )
        )

    # The POSIX Makefile is convenience, not the only supported path. Keep the
    # platform-specific direct-Python guidance discoverable in both contributor
    # and testing docs. AGENTS.md already exposes the portable Python fallback;
    # it need not duplicate PowerShell syntax.
    for name in ("CONTRIBUTING.md", "docs/TESTING.md"):
        if "Windows" not in docs[name]:
            findings.append(
                Finding(
                    source=name,
                    code="missing-windows-fallback",
                    detail="does not mention the supported Windows/direct-Python path",
                )
            )

    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to inspect (default: this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        findings = inspect_repository(args.root.resolve())
    except (OSError, UnicodeError) as exc:
        print(f"contributor-command-guard: inspection failed: {exc}", file=sys.stderr)
        return 2

    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if findings:
        print(
            f"contributor-command-guard: {len(findings)} finding(s)", file=sys.stderr
        )
        return 1

    print("contributor-command-guard: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
