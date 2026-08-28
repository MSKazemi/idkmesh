#!/usr/bin/env python3
"""Validate and summarize human IDKGraph P1 review-session evidence.

This tool never classifies repository documents. It only validates a reviewer-supplied
session for the frozen cohort and computes descriptive metrics from those supplied
judgments.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

SCHEMA_VERSION = "0.1"
EXPERIMENT = "idkgraph-p1-orphan-cohort-1-independent-review"
SEED = "idkgraph-p1-orphans-v1"
FROZEN_SOURCE_REVISION = "d0bafb7fe64a5d15db82e721a281e0dee2d3cc30"

COHORT = [
    "docs/conversations/2026-08-28-target-execution-convergence-followup.md",
    "docs/community/ACE_LINEAGE_PROTOCOL.md",
    "docs/research/R2_SCALE_REGIME_SWEEP.md",
    "docs/findings/2026-08-28-agent-ecosystem-and-idkmesh-evolution.md",
    "docs/conversations/2026-08-28-free-resource-mesh-integration-outcome.md",
    "docs/conversations/2026-08-28-framework-and-multidisciplinary-collaboration.md",
    "docs/conversations/2026-08-28-continue-ace-consolidation-and-live-capacity.md",
    "docs/architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md",
    "docs/findings/science-blockchain-sources-2026-08-28.md",
    "docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md",
    "docs/conversations/2026-08-28-run-evidence-and-replay-continuation.md",
    "docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md",
    "docs/security/ACE_THREAT_MODEL.md",
    "docs/conversations/2026-08-28-repository-audit-resource-contract-boundary.md",
    "docs/conversations/2026-08-28-verification-orchestration-collaboration.md",
]

# Canonicalized labels from the frozen AI-assisted/evidence-backed PR #166 audit.
REFERENCE_LABELS = {
    COHORT[0]: "intentional_memory",
    COHORT[1]: "navigation_gap",
    COHORT[2]: "navigation_gap",
    COHORT[3]: "reference_evidence",
    COHORT[4]: "intentional_memory",
    COHORT[5]: "intentional_memory",
    COHORT[6]: "intentional_memory",
    COHORT[7]: "navigation_gap",
    COHORT[8]: "reference_evidence",
    COHORT[9]: "navigation_gap",
    COHORT[10]: "intentional_memory",
    COHORT[11]: "navigation_gap",
    COHORT[12]: "navigation_gap",
    COHORT[13]: "intentional_memory",
    COHORT[14]: "intentional_memory",
}

ALLOWED_LABELS = {
    "navigation_gap",
    "intentional_memory",
    "reference_evidence",
    "uncertain",
    "other",
}
ALLOWED_ANCHORING = {
    "blind_to_original_labels",
    "saw_original_labels_after_own_review",
    "saw_original_labels_before_review",
}
ALLOWED_CHANGE_TYPES = {"link", "index", "move", "archive_review", "none", "other"}
PLACEHOLDERS = {"", "REPLACE", "REPLACE_WITH_GITHUB_LOGIN_OR_PUBLIC_PSEUDONYM"}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_session(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["session must be a JSON object"]

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION!r}")
    if data.get("experiment") != EXPERIMENT:
        errors.append(f"experiment must equal {EXPERIMENT!r}")

    cohort = data.get("cohort")
    if not isinstance(cohort, dict):
        errors.append("cohort must be an object")
    else:
        if cohort.get("seed") != SEED:
            errors.append(f"cohort.seed must equal {SEED!r}")
        if cohort.get("frozen_source_revision") != FROZEN_SOURCE_REVISION:
            errors.append("cohort.frozen_source_revision does not match the frozen cohort")
        if cohort.get("candidate_count") != len(COHORT):
            errors.append(f"cohort.candidate_count must equal {len(COHORT)}")

    reviewer = data.get("reviewer")
    if not isinstance(reviewer, dict):
        errors.append("reviewer must be an object")
    else:
        public_id = reviewer.get("public_id")
        if not isinstance(public_id, str) or public_id.strip() in PLACEHOLDERS:
            errors.append("reviewer.public_id must be a non-placeholder public identifier")
        statement = reviewer.get("independence_statement")
        if not isinstance(statement, str) or not statement.strip():
            errors.append("reviewer.independence_statement must be non-empty")
        if reviewer.get("anchoring_state") not in ALLOWED_ANCHORING:
            errors.append("reviewer.anchoring_state is invalid")

    timing = data.get("timing")
    if not isinstance(timing, dict):
        errors.append("timing must be an object")
    else:
        active = timing.get("active_review_minutes")
        if not _finite_number(active) or float(active) <= 0:
            errors.append("timing.active_review_minutes must be a finite number > 0")
        interruption = timing.get("interruption_minutes")
        if interruption is not None and (not _finite_number(interruption) or float(interruption) < 0):
            errors.append("timing.interruption_minutes must be null or a finite number >= 0")
        for key in ("started_at", "completed_at"):
            value = timing.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(f"timing.{key} must be null or a string")

    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        return errors + ["reviews must be an array"]
    if len(reviews) != len(COHORT):
        errors.append(f"reviews must contain exactly {len(COHORT)} entries")

    seen_ranks: set[int] = set()
    seen_paths: set[str] = set()
    for index, review in enumerate(reviews):
        prefix = f"reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue

        rank = review.get("rank")
        expected_rank = index + 1
        if rank != expected_rank:
            errors.append(f"{prefix}.rank must equal {expected_rank}")
        if isinstance(rank, int):
            if rank in seen_ranks:
                errors.append(f"{prefix}.rank duplicates rank {rank}")
            seen_ranks.add(rank)

        path = review.get("path")
        expected_path = COHORT[index] if index < len(COHORT) else None
        if path != expected_path:
            errors.append(f"{prefix}.path does not match frozen cohort rank {expected_rank}")
        if isinstance(path, str):
            if path in seen_paths:
                errors.append(f"{prefix}.path duplicates {path}")
            seen_paths.add(path)

        label = review.get("label")
        if label not in ALLOWED_LABELS:
            errors.append(f"{prefix}.label is invalid")

        confidence = review.get("confidence")
        if not _finite_number(confidence) or not 0 <= float(confidence) <= 1:
            errors.append(f"{prefix}.confidence must be finite and in [0, 1]")

        if not isinstance(review.get("recommend_change"), bool):
            errors.append(f"{prefix}.recommend_change must be boolean")
        change_type = review.get("proposed_change_type")
        if change_type not in ALLOWED_CHANGE_TYPES:
            errors.append(f"{prefix}.proposed_change_type is invalid")

        evidence = review.get("evidence_note")
        if not isinstance(evidence, str) or evidence.strip() in PLACEHOLDERS:
            errors.append(f"{prefix}.evidence_note must be a non-placeholder explanation")

        if label == "other":
            other_label = review.get("other_label")
            if not isinstance(other_label, str) or not other_label.strip():
                errors.append(f"{prefix}.other_label is required when label='other'")

    return errors


def _action_bucket(label: str) -> str:
    if label == "navigation_gap":
        return "action"
    if label in {"intentional_memory", "reference_evidence"}:
        return "no_immediate_action"
    return "unresolved"


def summarize_session(data: dict) -> dict:
    reviews = data["reviews"]
    active_minutes = float(data["timing"]["active_review_minutes"])
    label_counts = Counter(review["label"] for review in reviews)
    exact_matches = sum(
        1 for review in reviews if review["label"] == REFERENCE_LABELS[review["path"]]
    )
    recommended_change_count = sum(1 for review in reviews if review["recommend_change"])

    matrix = {
        "reference_action": {"action": 0, "no_immediate_action": 0, "unresolved": 0},
        "reference_no_immediate_action": {"action": 0, "no_immediate_action": 0, "unresolved": 0},
    }
    disagreements: list[dict] = []

    for review in reviews:
        reference_label = REFERENCE_LABELS[review["path"]]
        reference_bucket = _action_bucket(reference_label)
        reviewer_bucket = _action_bucket(review["label"])
        row = "reference_action" if reference_bucket == "action" else "reference_no_immediate_action"
        matrix[row][reviewer_bucket] += 1
        if review["label"] != reference_label:
            disagreements.append(
                {
                    "rank": review["rank"],
                    "path": review["path"],
                    "reference_label": reference_label,
                    "reviewer_label": review["label"],
                    "confidence": review["confidence"],
                }
            )

    return {
        "schema_version": "0.1",
        "experiment": EXPERIMENT,
        "cohort": {
            "candidate_count": len(COHORT),
            "seed": SEED,
            "frozen_source_revision": FROZEN_SOURCE_REVISION,
        },
        "reviewer": {
            "public_id": data["reviewer"]["public_id"],
            "anchoring_state": data["reviewer"]["anchoring_state"],
        },
        "descriptive_metrics": {
            "exact_label_matches": exact_matches,
            "exact_label_agreement": exact_matches / len(COHORT),
            "reviewer_label_counts": dict(sorted(label_counts.items())),
            "action_confusion_matrix": matrix,
            "active_review_minutes": active_minutes,
            "minutes_per_candidate": active_minutes / len(COHORT),
            "recommended_change_count": recommended_change_count,
            "minutes_per_recommended_change": (
                active_minutes / recommended_change_count if recommended_change_count else None
            ),
            "disagreement_count": len(disagreements),
        },
        "disagreements": disagreements,
        "interpretation_boundary": [
            "These metrics describe one frozen cohort and do not estimate global detector precision.",
            "Agreement with the prior classification is not a correctness target.",
            "The tool validates and summarizes human-entered judgments; it does not classify documents.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="Completed review-session JSON")
    parser.add_argument("--output", type=Path, help="Optional path for computed JSON metrics")
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.session.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid review session: {exc}", file=sys.stderr)
        return 2

    errors = validate_session(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    summary = summarize_session(data)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
