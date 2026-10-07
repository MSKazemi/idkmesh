#!/usr/bin/env python3
"""Require an explicit migration note for every schema version successor.

Issue #737 ("breaking changes require explicit version bump/migration note")
splits that rule in two halves. ``tools/schema_compat_check.py`` enforces the
version bump: any in-place breaking edit to a shipped ``schemas/*.json`` is
rejected, so a breaking change can only ship as a new, separately versioned
file. This module enforces the second half -- the migration note. The new
file must land with an explicit note in the ``Schema migrations`` section of
``schemas/README.md`` naming the exact file it supersedes, so a consumer of
the old contract can always find what changed and how to move.

## Mechanical rule

Every ``schemas/<family>-v<N>.<M>.schema.json`` file belongs to a version
family, ordered by ``(N, M)``. Every version above the lowest is a
*successor* and needs exactly one ledger entry in the ``Schema migrations``
section:

    - `<successor>.schema.json` supersedes `<predecessor>.schema.json`: <note>

The predecessor named must be the successor's immediate predecessor in its
family, both files must exist, the note must be substantive (at least
``NOTE_MIN_CHARS`` characters), and no successor may be listed twice or be
missing. Unversioned legacy files (``work-unit.schema.json`` and the other
open documents recorded in ``schemas/README.md``) and single-version families
need no entry: there is nothing to migrate from.

This module has no third-party dependency; the PR Gate runs it before
``pip install``, exactly like ``tools/schema_compat_check.py`` and
``tools/openapi_ref_check.py`` (``tests/test_ci_local_gate_parity.py`` pins
that shape).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas"
LEDGER_PATH = SCHEMAS_DIR / "README.md"
LEDGER_SECTION = "## Schema migrations"

VERSIONED_NAME = re.compile(
    r"^(?P<family>.+)-v(?P<major>\d+)\.(?P<minor>\d+)\.schema\.json$"
)
LEDGER_ENTRY = re.compile(
    r"^\s*-\s+`(?P<new>[^`]+\.schema\.json)`\s+supersedes\s+"
    r"`(?P<old>[^`]+\.schema\.json)`:\s*(?P<note>.+?)\s*$",
    re.M,
)
NOTE_MIN_CHARS = 20


def version_families(schemas_dir: Path) -> dict[str, dict[tuple[int, int], str]]:
    """Return {family: {(major, minor): filename}} for versioned schema files."""
    families: dict[str, dict[tuple[int, int], str]] = {}
    for path in sorted(schemas_dir.glob("*.schema.json")):
        match = VERSIONED_NAME.match(path.name)
        if match is None:
            continue
        version = (int(match.group("major")), int(match.group("minor")))
        families.setdefault(match.group("family"), {})[version] = path.name
    return families


def successors(schemas_dir: Path) -> dict[str, str]:
    """Return {successor filename: immediate predecessor filename}.

    A version is a successor when its family holds at least one lower
    version; the predecessor is the highest version below it.
    """
    result: dict[str, str] = {}
    for versions in version_families(schemas_dir).values():
        ordered = sorted(versions)
        for previous, current in zip(ordered, ordered[1:]):
            result[versions[current]] = versions[previous]
    return result


def ledger_section(text: str) -> str | None:
    """Return the body of the ``Schema migrations`` section, or None if absent."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == LEDGER_SECTION:
            body = []
            for follow in lines[index + 1 :]:
                if follow.startswith("## "):
                    break
                body.append(follow)
            return "\n".join(body)
    return None


def parse_ledger(text: str) -> list[dict[str, str]] | None:
    """Return the ledger entries, or None when the section is missing."""
    section = ledger_section(text)
    if section is None:
        return None
    return [
        {"new": match["new"], "old": match["old"], "note": match["note"]}
        for match in LEDGER_ENTRY.finditer(section)
    ]


def check(schemas_dir: Path = SCHEMAS_DIR, ledger_text: str | None = None) -> list[str]:
    """Return migration-note violations; empty means the ledger is complete."""
    if ledger_text is None:
        ledger_text = LEDGER_PATH.read_text(encoding="utf-8")
    entries = parse_ledger(ledger_text)
    if entries is None:
        return [
            f"{LEDGER_SECTION!r} section missing from schemas/README.md; every "
            "version successor needs a migration note there"
        ]

    violations: list[str] = []
    expected = successors(schemas_dir)
    existing = {path.name for path in schemas_dir.glob("*.schema.json")}

    by_new: dict[str, dict[str, str]] = {}
    for entry in entries:
        if entry["new"] in by_new:
            violations.append(
                f"{entry['new']}: more than one ledger entry; a successor needs "
                "exactly one migration note"
            )
        by_new[entry["new"]] = entry

    for name, predecessor in sorted(expected.items()):
        entry = by_new.get(name)
        if entry is None:
            violations.append(
                f"{name}: version successor has no migration note; add "
                f"'- `{name}` supersedes `{predecessor}`: <note>' to the "
                f"{LEDGER_SECTION} section of schemas/README.md"
            )
            continue
        if entry["old"] != predecessor:
            violations.append(
                f"{name}: ledger says it supersedes {entry['old']}, but its "
                f"immediate predecessor is {predecessor}"
            )
        if len(entry["note"].strip()) < NOTE_MIN_CHARS:
            violations.append(
                f"{name}: migration note is missing or too short to state what "
                "changed and how to migrate"
            )

    for name in sorted(set(by_new) - set(expected)):
        if name in existing:
            violations.append(
                f"{name}: ledger entry names a file that is not a version "
                "successor; only successors need migration notes"
            )
        else:
            violations.append(
                f"{name}: ledger entry names a file that does not exist in schemas/"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    violations = check()
    if args.json:
        print(json.dumps({"violations": violations}, indent=2, sort_keys=True))
    elif violations:
        print("schema-migration-note-check: missing or wrong migration note(s):")
        for violation in violations:
            print(f"  - {violation}")
        print(
            "\nBreaking changes ship as new, separately versioned files "
            "(ADR-0020) and every successor needs an explicit migration note "
            "in the Schema migrations section of schemas/README.md."
        )
    else:
        print("schema-migration-note-check: every version successor has its note")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
