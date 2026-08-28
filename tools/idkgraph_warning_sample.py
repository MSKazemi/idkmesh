#!/usr/bin/env python3
"""Select a deterministic review cohort from IDKGraph observatory findings.

This tool is intentionally read-only with respect to the repository. It turns a
large warning population into a reproducible bounded cohort for human/evidence
triage. Selection is based on SHA-256 ranking, not Python hash/random state, so
input ordering and interpreter hash randomization cannot change the cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.idkgraph_observatory import build_observatory

SCHEMA_VERSION = "idkgraph-warning-sample-v0.1"
DEFAULT_CATEGORY = "orphan_document_candidate"
DEFAULT_SEED = "idkgraph-p1-orphans-v1"


def _canonical_candidate_payload(finding: dict[str, Any]) -> str:
    """Return the stable fields used to identify one warning candidate."""
    payload = {
        "category": finding.get("category"),
        "line": finding.get("line", 0),
        "message": finding.get("message", ""),
        "source_id": finding.get("source_id"),
        "source_path": finding.get("source_path"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def selection_hash(finding: dict[str, Any], seed: str) -> str:
    payload = f"{seed}\0{_canonical_candidate_payload(finding)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sample_findings(
    findings: Iterable[dict[str, Any]],
    *,
    category: str,
    sample_size: int,
    seed: str,
) -> tuple[list[dict[str, Any]], int]:
    """Return a stable bounded cohort and the total eligible population size."""
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1")
    if not category:
        raise ValueError("category must not be empty")
    if not seed:
        raise ValueError("seed must not be empty")

    eligible = [
        dict(finding)
        for finding in findings
        if isinstance(finding, dict) and finding.get("category") == category
    ]
    ranked = sorted(
        eligible,
        key=lambda finding: (
            selection_hash(finding, seed),
            str(finding.get("source_path") or ""),
            str(finding.get("source_id") or ""),
            int(finding.get("line") or 0),
        ),
    )

    cohort: list[dict[str, Any]] = []
    for rank, finding in enumerate(ranked[:sample_size], start=1):
        cohort.append(
            {
                "rank": rank,
                "selection_hash": selection_hash(finding, seed),
                "severity": finding.get("severity"),
                "category": finding.get("category"),
                "source_path": finding.get("source_path"),
                "source_id": finding.get("source_id"),
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
                "evidence": finding.get("evidence", {}),
                "review": {
                    "classification": "unreviewed",
                    "notes": "",
                    "recommended_action": "",
                },
            }
        )
    return cohort, len(eligible)


def build_sample(
    root: Path,
    *,
    category: str = DEFAULT_CATEGORY,
    sample_size: int = 15,
    seed: str = DEFAULT_SEED,
) -> dict[str, Any]:
    root = root.resolve()
    _, observatory = build_observatory(root)
    cohort, population_size = sample_findings(
        observatory.get("findings", []),
        category=category,
        sample_size=sample_size,
        seed=seed,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_revision": observatory.get("source_revision"),
        "source_revision_method": observatory.get("source_revision_method"),
        "observatory_schema_version": observatory.get("schema_version"),
        "category": category,
        "seed": seed,
        "requested_sample_size": sample_size,
        "population_size": population_size,
        "sample_size": len(cohort),
        "candidates": cohort,
        "authority": {
            "repository_write": False,
            "github_mutation": False,
            "semantic_inference": False,
            "automatic_repair": False,
            "integration": False,
        },
    }


def serialize_sample(sample: dict[str, Any], *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(sample, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(sample, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _validate_output_location(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError("output must be outside the scanned repository tree")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repository root to inspect.")
    parser.add_argument("--category", default=DEFAULT_CATEGORY, help="Finding category to sample.")
    parser.add_argument("--sample-size", type=int, default=15, help="Maximum cohort size.")
    parser.add_argument("--seed", default=DEFAULT_SEED, help="Stable public sampling seed.")
    parser.add_argument("--output", required=True, help="JSON output path outside the scanned tree.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    output = Path(args.output)
    try:
        _validate_output_location(root, output)
        sample = build_sample(
            root,
            category=args.category,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_sample(sample, pretty=args.pretty), encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
