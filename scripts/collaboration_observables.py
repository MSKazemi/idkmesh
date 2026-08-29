#!/usr/bin/env python3
"""Derive deterministic collaboration observables from a frozen GitHub snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.metric_uncertainty import beta_binomial_summary
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from metric_uncertainty import beta_binomial_summary

VERSION = "collaboration-observables-v0.1"


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"invalid timestamp: {value}") from error
    _require(parsed.tzinfo is not None, "timestamps must include a timezone")
    return parsed


def _hours(start: str, end: str) -> float:
    value = (_time(end) - _time(start)).total_seconds() / 3600.0
    _require(value >= 0, "event timestamps must not precede creation")
    return value


def _is_bot(login: str) -> bool:
    lowered = login.lower()
    return lowered.endswith("[bot]") or lowered in {"github-actions", "github-actions[bot]"}


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires observations")
    position = probability * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _bootstrap_median(values: list[float], seed_material: str) -> dict[str, Any]:
    if not values:
        return {"model": "right-censored-descriptive-v1", "samples": 0, "median_hours": None, "bootstrap_interval_95": None}
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16)
    generator = random.Random(seed)
    draws = [
        statistics.median(generator.choices(values, k=len(values)))
        for _ in range(1000)
    ]
    return {
        "model": "deterministic-bootstrap-median-v1",
        "samples": len(values),
        "median_hours": round(statistics.median(values), 6),
        "bootstrap_interval_95": [round(_percentile(draws, 0.025), 6), round(_percentile(draws, 0.975), 6)],
        "bootstrap_replicates": 1000,
    }


def _hhi(values: list[str], population: str) -> dict[str, Any]:
    counts = Counter(values)
    total = sum(counts.values())
    score = 0.0 if total == 0 else sum((count / total) ** 2 for count in counts.values())
    return {
        "model": "observed-share-hhi-v1",
        "population": population,
        "observations": total,
        "distinct_actors": len(counts),
        "hhi": round(score, 6),
        "counts": dict(sorted(counts.items())),
        "uncertainty": "descriptive_snapshot_no_population_inference",
    }


def analyze(snapshot: dict[str, Any]) -> dict[str, Any]:
    _require(snapshot.get("version") == 1, "snapshot version must be 1")
    repository = snapshot.get("repository")
    cutoff = snapshot.get("cutoff_at")
    pulls = snapshot.get("pull_requests")
    contributors = snapshot.get("contributors")
    inventory_complete = snapshot.get("inventory_complete")
    _require(isinstance(repository, str) and "/" in repository, "repository must be owner/name")
    _require(isinstance(cutoff, str), "cutoff_at is required")
    cutoff_time = _time(cutoff)
    _require(isinstance(pulls, list), "pull_requests must be an array")
    _require(isinstance(contributors, list), "contributors must be an array")
    _require(isinstance(inventory_complete, bool), "inventory_complete must be a boolean")

    first_review_hours: list[float] = []
    cycle_hours: list[float] = []
    queue_ages: list[float] = []
    reviewers: list[str] = []
    owners: list[str] = []
    ci_passed = 0
    ci_total = 0
    debt_ids: set[str] = set()
    strategies: dict[str, list[bool]] = {}
    seen_numbers: set[int] = set()

    for row in sorted(pulls, key=lambda item: int(item.get("number", -1))):
        _require(isinstance(row, dict), "pull request must be an object")
        number = row.get("number")
        _require(isinstance(number, int) and number > 0 and number not in seen_numbers, "pull request numbers must be unique positive integers")
        seen_numbers.add(number)
        created = row.get("created_at")
        created_time = _time(created)
        _require(created_time <= cutoff_time, "pull request occurs after cutoff")
        review_ready_at = row.get("review_ready_at")
        first_review = row.get("first_independent_review_at")
        closed = row.get("closed_at")
        if first_review is not None:
            _require(isinstance(review_ready_at, str), "reviewed pull request requires review_ready_at")
            _require(_time(first_review) <= cutoff_time, "review occurs after cutoff")
            first_review_hours.append(_hours(review_ready_at, first_review))
        if closed is not None:
            _require(_time(closed) <= cutoff_time, "closure occurs after cutoff")
            cycle_hours.append(_hours(created, closed))
        if row.get("review_ready") is True and closed is None:
            _require(isinstance(review_ready_at, str), "review-ready pull request requires review_ready_at")
            age = (cutoff_time - _time(review_ready_at)).total_seconds() / 3600.0
            _require(age >= 0, "open pull request occurs after cutoff")
            queue_ages.append(age)
        author = row.get("author")
        _require(isinstance(author, str) and author, "pull request author is required")
        normalized_reviewers = set()
        for login in row.get("independent_reviewers") or []:
            _require(isinstance(login, str) and login, "reviewer login must be non-empty")
            normalized = login.lower()
            _require(normalized != author.lower() and not _is_bot(normalized),
                     "independent reviewer cannot be author or bot")
            normalized_reviewers.add(normalized)
        reviewers.extend(sorted(normalized_reviewers))
        for login in row.get("changed_file_owners") or []:
            _require(isinstance(login, str) and login, "owner login must be non-empty")
            owners.append(login.lower())
        checks = row.get("ci_checks") or {}
        passed, total = checks.get("passed", 0), checks.get("total", 0)
        _require(isinstance(passed, int) and isinstance(total, int) and 0 <= passed <= total, "CI check counts are invalid")
        ci_passed += passed
        ci_total += total
        for finding_id in row.get("structural_debt_finding_ids") or []:
            _require(isinstance(finding_id, str) and finding_id,
                     "structural debt finding ID must be non-empty")
            debt_ids.add(finding_id)
        strategy = row.get("strategy")
        if strategy is not None:
            _require(isinstance(strategy, str) and strategy, "strategy must be non-empty")
            _require(isinstance(row.get("verified_useful"), bool), "strategy observations require verified_useful")
            _require(row.get("verification_independent") is True,
                     "strategy outcomes require independent verification")
            strategies.setdefault(strategy, []).append(row["verified_useful"])

    recurring = 0
    contributor_ids: set[str] = set()
    for row in contributors:
        _require(isinstance(row, dict), "contributor must be an object")
        login = row.get("login")
        _require(isinstance(login, str) and login and login.lower() not in contributor_ids,
                 "contributor logins must be unique and non-empty")
        contributor_ids.add(login.lower())
        timestamps = row.get("meaningful_contributions")
        _require(isinstance(timestamps, list) and timestamps, "contributor requires meaningful contributions")
        parsed = sorted(_time(value) for value in timestamps)
        _require(
            len(set(parsed)) == len(parsed),
            "meaningful contribution timestamps must be unique per contributor",
        )
        _require(parsed[-1] <= cutoff_time, "contribution occurs after cutoff")
        recurring += len(parsed) >= 2

    prior_rows = []
    for strategy, outcomes in sorted(strategies.items()):
        summary = beta_binomial_summary(sum(outcomes), len(outcomes))
        prior_rows.append({"strategy": strategy, "evidence": summary})
    denominator = sum(row["evidence"]["posterior_mean"] for row in prior_rows)
    for row in prior_rows:
        row["normalized_weight"] = round(row["evidence"]["posterior_mean"] / denominator, 6) if denominator else 0.0

    queue_summary = {
        "model": "point_in_time_queue-v1",
        "open_review_ready": len(queue_ages),
        "median_age_hours": round(statistics.median(queue_ages), 6) if queue_ages else None,
        "p95_age_hours": round(_percentile(queue_ages, 0.95), 6) if queue_ages else None,
        "cutoff_at": cutoff,
    }
    return {
        "version": 1,
        "method": VERSION,
        "source": {"repository": repository, "cutoff_at": cutoff, "natural_language_trusted": False},
        "metrics": {
            "first_independent_review_latency": {
                **_bootstrap_median(first_review_hours, repository + cutoff + ":review"),
                "right_censored": sum(
                    1
                    for row in pulls
                    if row.get("first_independent_review_at") is None
                    and row.get("closed_at") is None
                ),
                "closed_without_review": sum(
                    1
                    for row in pulls
                    if row.get("first_independent_review_at") is None
                    and row.get("closed_at") is not None
                ),
            },
            "cycle_latency": {**_bootstrap_median(cycle_hours, repository + cutoff + ":cycle"), "right_censored": sum(1 for row in pulls if row.get("closed_at") is None)},
            "review_concentration": _hhi(reviewers, "independent_reviewer_pull_request_pairs"),
            "ownership_concentration": _hhi(owners, "changed_file_owner_attributions"),
            "contributor_recurrence": beta_binomial_summary(recurring, len(contributors)),
            "ci_evidence": beta_binomial_summary(ci_passed, ci_total),
            "review_queue": queue_summary,
            "structural_debt": {"model": "bounded_inventory_count-v1", "observed_findings": len(debt_ids), "finding_ids": sorted(debt_ids), "pull_requests_observed": len(pulls), "inventory_complete": inventory_complete},
        },
        "evidence_derived_strategy_priors": prior_rows,
        "authority": {"causal_claim": False, "policy_activation": False, "github_write": False},
    }


def serialize(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = serialize(analyze(json.loads(args.snapshot.read_text(encoding="utf-8"))))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
