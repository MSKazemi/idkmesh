#!/usr/bin/env python3
"""Audit the IDKMesh conversation archive against its manifest.

This tool deliberately checks only repository-observable invariants. It cannot
know that an external chat happened if no artifact was ever committed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "project-memory" / "conversation-manifest.json"
CONVERSATIONS = ROOT / "docs" / "conversations"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = data.get("records", [])

    errors: list[str] = []
    if not isinstance(records, list) or not all(isinstance(x, str) for x in records):
        errors.append("manifest records must be a list of strings")
        records = []

    if len(records) != len(set(records)):
        errors.append("manifest contains duplicate paths")

    if records != sorted(records):
        errors.append("manifest records must be sorted for deterministic review")

    manifest_paths = set(records)
    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for path in CONVERSATIONS.glob("*.md")
        if path.is_file()
    }

    missing_files = sorted(manifest_paths - actual_paths)
    unindexed_files = sorted(actual_paths - manifest_paths)

    for path in missing_files:
        errors.append(f"manifest points to missing conversation: {path}")
    for path in unindexed_files:
        errors.append(f"conversation exists but is not indexed: {path}")

    for rel in sorted(actual_paths):
        path = ROOT / rel
        if path.stat().st_size < 100:
            errors.append(f"conversation record is suspiciously small: {rel}")

    print(
        json.dumps(
            {
                "manifest_version": data.get("version"),
                "indexed_records": len(manifest_paths),
                "actual_records": len(actual_paths),
                "missing_files": missing_files,
                "unindexed_files": unindexed_files,
                "ok": not errors,
            },
            indent=2,
            sort_keys=True,
        )
    )

    if errors:
        print("\nProject memory audit failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
