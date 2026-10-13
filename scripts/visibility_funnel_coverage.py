#!/usr/bin/env python3
"""Report which IDKMesh discovery-to-contribution stages are actually observable.

Inputs are read-only aggregate snapshots with different windows/populations. Never
infer cross-source conversion rates, follow visitors, or infer verified outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any


VERSION = "visibility-funnel-coverage-v0.1"
CANONICAL_PREFIX = "https://mskazemi.com/idkmesh/"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def count(value: Any, label: str, *, integer: bool = False) -> int | float:
    if integer:
        require(type(value) is int and 0 <= value <= 10**12, f"{label} must be a nonnegative integer")
        return value
    require(type(value) in (int, float), f"{label} must be a finite nonnegative number")
    require(math.isfinite(value) and 0 <= value <= 10**12, f"{label} must be a finite nonnegative number")
    return value


def iso_date(value: Any, label: str) -> str:
    require(isinstance(value, str), f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO date") from error
    require(parsed.isoformat() == value, f"{label} must be YYYY-MM-DD")
    return value


def stage(stage_id: str, status: str, *, metric: dict[str, Any] | None = None,
          window: str | None = None, boundary: str) -> dict[str, Any]:
    return {"id": stage_id, "status": status, "metric": metric,
            "window": window, "boundary": boundary}


def assess(visibility: dict[str, Any], *,
           search_console: dict[str, Any] | None = None,
           github_traffic: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create an aggregate coverage map, not a purported conversion funnel."""
    require(isinstance(visibility, dict) and visibility.get("version") == 1,
            "visibility observatory v1 object is required")
    github = visibility.get("github")
    require(isinstance(github, dict), "visibility.github must be an object")
    repository = github.get("repository")
    require(isinstance(repository, str) and repository.count("/") == 1 and repository,
            "visibility.github.repository is invalid")
    acquisition = github.get("community_acquisition")
    require(isinstance(acquisition, dict), "visibility acquisition evidence is required")
    contributors = count(acquisition.get("external_commit_contributors_observed"),
                         "external contributors", integer=True)
    truncated = acquisition.get("contributors_page_truncated")
    require(type(truncated) is bool, "contributors_page_truncated must be boolean")

    search_stage = stage(
        "nonbranded_search", "unavailable",
        boundary="No Search Console snapshot: missing evidence, not zero impressions.")
    if search_console is not None:
        require(isinstance(search_console, dict) and search_console.get("version") == 1,
                "Search Console v1 snapshot required")
        source = search_console.get("source")
        require(isinstance(source, dict) and source.get("provider") == "google_search_console",
                "Search Console source provider is invalid")
        require(source.get("page_prefix") == CANONICAL_PREFIX and
                source.get("dimensions") == ["query", "page"] and
                source.get("search_type") == "web" and source.get("data_state") == "final",
                "Search Console scope or final-data contract is invalid")
        start = iso_date(source.get("start_date"), "Search Console start_date")
        end = iso_date(source.get("end_date"), "Search Console end_date")
        require(start <= end, "Search Console date window is reversed")
        truncated_gsc = source.get("truncated_by_local_cap")
        require(type(truncated_gsc) is bool, "Search Console truncation flag must be boolean")
        summary = search_console.get("summary")
        require(isinstance(summary, dict) and isinstance(summary.get("nonbranded"), dict),
                "Search Console nonbranded summary required")
        nonbranded = summary["nonbranded"]
        impressions = count(nonbranded.get("impressions"), "GSC impressions")
        clicks = count(nonbranded.get("clicks"), "GSC clicks")
        require(clicks <= impressions, "GSC clicks cannot exceed impressions")
        queries = count(summary.get("portfolio_queries_with_observations"),
                        "observed portfolio queries", integer=True)
        search_stage = stage(
            "nonbranded_search", "observed",
            metric={"impressions": impressions, "clicks": clicks,
                    "exact_portfolio_queries": queries, "locally_truncated": truncated_gsc},
            window=f"{start}/{end}",
            boundary="Aggregate Search Console query/page rows are not sessions or site visits; top-row omissions are possible.")

    github_stage = stage(
        "github_repository_visits", "unavailable",
        boundary="No owner-authorized GitHub Traffic snapshot: missing evidence, not zero views.")
    if github_traffic is not None:
        require(isinstance(github_traffic, dict) and github_traffic.get("version") == 1,
                "GitHub Traffic v1 snapshot required")
        source = github_traffic.get("source")
        require(isinstance(source, dict) and source.get("provider") == "github_repository_traffic_api",
                "GitHub Traffic source provider is invalid")
        require(source.get("repository") == repository and
                source.get("window") == "github_rolling_14_days",
                "GitHub Traffic repository or window mismatch")
        require(isinstance(source.get("collected_at_utc"), str) and
                source["collected_at_utc"].endswith("Z"),
                "GitHub Traffic collection timestamp missing")
        views = github_traffic.get("views")
        require(isinstance(views, dict), "GitHub Traffic views required")
        total_views = count(views.get("count"), "GitHub repository views", integer=True)
        uniques = count(views.get("uniques"), "GitHub unique visitors", integer=True)
        require(uniques <= total_views, "GitHub unique visitors cannot exceed views")
        github_stage = stage(
            "github_repository_visits", "observed",
            metric={"views": total_views, "unique_visitors": uniques},
            window="rolling_14_days_at_" + source["collected_at_utc"],
            boundary="GitHub repo page views are not website visits, linked search clicks, or people who tried the tool.")

    stages = [
        search_stage,
        stage("website_visits", "unavailable",
              boundary="No website visit/sessions collection is connected; Search Console clicks are not visits."),
        github_stage,
        stage("first_interaction", "unavailable",
              boundary="Stars/forks are cumulative interest proxies, not attributable first interactions."),
        stage("external_commit_contributors", "partial_proxy" if truncated else "proxy",
              metric={"observed_external_commit_contributors": contributors,
                      "contributors_page_truncated": truncated},
              window="GitHub contributor endpoint snapshot, not a time-bounded cohort",
              boundary="Commit attribution misses issue authors, reviewers, and unmerged or non-code contributors."),
        stage("first_verified_contribution", "unavailable",
              boundary="No linked evidence of accepted, independently verified first contributions."),
        stage("recurring_verified_contributor", "unavailable",
              boundary="No time-bound repeat contribution or retention cohort is available."),
    ]
    transitions = [
        {"from": left["id"], "to": right["id"],
         "status": "not_attributable", "rate": None,
         "reason": "No shared, time-aligned, attributable cohort across these sources."}
        for left, right in zip(stages, stages[1:])
    ]
    observed = [row["id"] for row in stages if row["status"] == "observed"]
    missing = [row["id"] for row in stages if row["status"] == "unavailable"]
    next_step = ("connect_google_search_console" if search_console is None else
                 "connect_read_only_github_traffic" if github_traffic is None else
                 "design_privacy_preserving_aggregate_website_visits")
    return {
        "version": 1,
        "method": VERSION,
        "repository": repository,
        "stages": stages,
        "transitions": transitions,
        "summary": {
            "direct_stages_observed": len(observed),
            "direct_stage_ids": observed,
            "missing_stage_ids": missing,
            "conversion_rates_estimable": 0,
            "next_measurement_action": next_step,
        },
        "limitations": [
            "no_cross_source_user_or_session_linking",
            "search_and_repo_traffic_use_different_populations_and_windows",
            "external_contributors_are_commit_attribution_proxies_not_verified_adoption",
            "recorded_zero_is_distinct_from_missing_observation",
            "no_identity_cookie_fingerprint_or_tracking_data_collected",
        ],
        "authority": {
            "recommendation_only": True,
            "correctness_claim": False,
            "causal_claim": False,
            "automatic_publication": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path}: JSON object required")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visibility", required=True, type=Path)
    parser.add_argument("--search-console", type=Path)
    parser.add_argument("--github-traffic", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = assess(
        load_object(args.visibility),
        search_console=load_object(args.search_console) if args.search_console is not None else None,
        github_traffic=load_object(args.github_traffic) if args.github_traffic is not None else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
