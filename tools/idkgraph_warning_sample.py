#!/usr/bin/env python3
"""Select a reproducible bounded cohort from IDKGraph observatory findings.

This P1 helper does not change detector semantics. It ranks eligible findings by
SHA-256 over a public seed plus stable finding identity fields, then returns the
first N. The goal is to support bounded review without alphabetical/path-order
bias or bulk remediation pressure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

SCHEMA_VERSION = "idkgraph-warning-sample-v0.1"


def _rank(seed: str, finding: dict[str, Any]) -> str:
    payload = "\0".join(
        [
            seed,
            str(finding.get("category") or ""),
            str(finding.get("source_id") or ""),
            str(finding.get("source_path") or ""),
            str(finding.get("line") or 0),
        ]
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sample_findings(
    observatory: dict[str, Any],
    *,
    category: str,
    size: int,
    seed: str,
) -> dict[str, Any]:
    if size < 0:
        raise ValueError("size must be >= 0")
    eligible = [
        finding
        for finding in observatory.get("findings", [])
        if isinstance(finding, dict) and finding.get("category") == category
    ]
    ranked = sorted(
        eligible,
        key=lambda finding: (
            _rank(seed, finding),
            str(finding.get("source_id") or ""),
            str(finding.get("source_path") or ""),
        ),
    )
    selected = []
    for finding in ranked[:size]:
        selected.append(
            {
                "rank_hash": _rank(seed, finding),
                "category": finding.get("category"),
                "severity": finding.get("severity"),
                "source_id": finding.get("source_id"),
                "source_path": finding.get("source_path"),
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_revision": observatory.get("source_revision"),
        "observatory_schema_version": observatory.get("schema_version"),
        "category": category,
        "seed": seed,
        "requested_size": size,
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "sample": selected,
    }


def serialize_sample(sample: dict[str, Any], pretty: bool = False) -> str:
    if pretty:
        return json.dumps(sample, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(sample, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observatory", help="Path to observatory.json")
    parser.add_argument("--category", required=True, help="Exact finding category to sample")
    parser.add_argument("--size", type=int, default=15, help="Maximum cohort size")
    parser.add_argument("--seed", required=True, help="Public deterministic sampling seed")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args(argv)

    try:
        observatory = json.loads(Path(args.observatory).read_text(encoding="utf-8"))
        sample = sample_findings(
            observatory,
            category=args.category,
            size=args.size,
            seed=args.seed,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    payload = serialize_sample(sample, pretty=args.pretty)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
