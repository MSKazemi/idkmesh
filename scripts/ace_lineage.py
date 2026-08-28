#!/usr/bin/env python3
"""Extract and validate ACE_LINEAGE blocks from Markdown.

This utility is intentionally read-only. It turns GitHub-native Markdown metadata
into deterministic validated lineage records that later observers/controllers can
consume without interpreting natural-language prose.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "ace-lineage-v0.1.schema.json"
BLOCK_RE = re.compile(r"<!--\s*ACE_LINEAGE\s*\n(?P<payload>.*?)\n\s*ACE_LINEAGE\s*-->", re.DOTALL)
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class LineageError(RuntimeError):
    pass


def load_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def normalize_ref(ref: dict[str, Any]) -> str:
    repo = ref["repo"]
    kind = ref["kind"]
    if kind in {"issue", "pr"}:
        return f"{repo}#{kind}:{ref['number']}"
    return f"{repo}#commit:{str(ref['sha']).lower()}"


def lineage_identity(record: dict[str, Any]) -> str:
    explicit = record.get("lineage_id")
    if explicit:
        return f"lineage:{explicit}"
    return "|".join(
        [
            normalize_ref(record["parent"]),
            normalize_ref(record["seed"]),
            normalize_ref(record["descendant"]),
            record["descendant_type"],
        ]
    )


def _require_rfc3339(value: Any, label: str) -> None:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        raise LineageError(f"{label} must be an RFC3339 timestamp with timezone")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LineageError(f"{label} is not a valid calendar timestamp") from exc


def validate_record(record: dict[str, Any], validator: Draft202012Validator) -> None:
    errors = sorted(validator.iter_errors(record), key=lambda error: list(error.absolute_path))
    if errors:
        lines = ["ACE lineage record failed schema validation:"]
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            lines.append(f"- {location}: {error.message}")
        raise LineageError("\n".join(lines))

    # Draft 2020-12 treats `format` primarily as annotation unless a validator
    # configuration explicitly enables assertion semantics. Make the protocol's
    # timestamp boundary deterministic instead of relying on library defaults.
    _require_rfc3339(record["recorded_at"], "recorded_at")
    verification = record.get("verification")
    if verification is not None:
        _require_rfc3339(verification["verified_at"], "verification.verified_at")


def extract_markdown(text: str) -> list[dict[str, Any]]:
    validator = load_validator()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, match in enumerate(BLOCK_RE.finditer(text), start=1):
        try:
            record = json.loads(match.group("payload"))
        except json.JSONDecodeError as exc:
            raise LineageError(f"ACE_LINEAGE block {index} is not valid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise LineageError(f"ACE_LINEAGE block {index} must contain a JSON object")
        validate_record(record, validator)
        identity = lineage_identity(record)
        if identity in seen:
            raise LineageError(f"duplicate ACE lineage identity: {identity}")
        seen.add(identity)
        records.append(record)

    return records


def receipt(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity": lineage_identity(record),
        "parent": normalize_ref(record["parent"]),
        "seed": normalize_ref(record["seed"]),
        "descendant": normalize_ref(record["descendant"]),
        "descendant_type": record["descendant_type"],
        "status": record["status"],
        "recorded_at": record["recorded_at"],
        "verified": record["status"] == "verified",
        "reviewer_minutes": float(record.get("reviewer_minutes", 0.0)),
        "verifier": (record.get("verification") or {}).get("verifier"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", help="Markdown file containing zero or more ACE_LINEAGE blocks")
    parser.add_argument("--require", action="store_true", help="fail when no ACE_LINEAGE block is present")
    args = parser.parse_args()

    path = Path(args.markdown)
    records = extract_markdown(path.read_text(encoding="utf-8"))
    if args.require and not records:
        raise LineageError(f"no ACE_LINEAGE blocks found in {path}")

    print(json.dumps([receipt(record) for record in records], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LineageError as exc:
        print(str(exc))
        raise SystemExit(2)
