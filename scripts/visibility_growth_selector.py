#!/usr/bin/env python3
"""Select at most one bounded visibility/community growth experiment.

This controller is recommendation-only. It diagnoses the narrowest observed bottleneck
from repository-visible evidence and optional Search Console evidence. It never
publishes content, contacts people, creates issues, mutates branches, or merges code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERSION = "visibility-growth-selector-v0.1"


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    _require(policy.get("version") == 1, "policy version must be 1")
    _require(
        policy.get("status") == "bootstrap_thresholds_require_calibration",
        "policy status must preserve bootstrap uncertainty",
    )
    thresholds = policy.get("thresholds")
    provenance = policy.get("provenance")
    authority = policy.get("authority")
    _require(isinstance(thresholds, dict), "thresholds must be an object")
    _require(isinstance(provenance, dict), "provenance must be an object")
    _require(isinstance(authority, dict), "authority must be an object")
    _require(set(thresholds) == set(provenance), "every threshold must declare provenance")
    _require(all(float(value) >= 0 for value in thresholds.values()), "thresholds must be non-negative")
    _require(authority.get("recommendation_only") is True, "policy must remain recommendation-only")
    for forbidden in (
        "automatic_content_publication",
        "automatic_outreach",
        "automatic_issue_creation",
        "merge_authority",
    ):
        _require(authority.get(forbidden) is False, f"{forbidden} must remain disabled")


def select(
    visibility: dict[str, Any],
    portfolio: dict[str, Any],
    policy: dict[str, Any],
    *,
    search_console: dict[str, Any] | None,
) -> dict[str, Any]:
    validate_policy(policy)

    site = visibility.get("site") or {}
    github = visibility.get("github") or {}
    acquisition = github.get("community_acquisition") or {}
    summary = portfolio.get("summary") or {}
    thresholds = policy["thresholds"]

    _require(isinstance(site.get("technical_coverage"), (int, float)), "visibility technical_coverage is required")
    _require(isinstance(summary.get("queries"), int), "portfolio summary queries is required")

    candidate: dict[str, Any]

    if (
        float(site["technical_coverage"]) < 1.0
        or not bool((site.get("sitemap") or {}).get("present"))
        or not bool((site.get("sitemap") or {}).get("valid_urlset"))
    ):
        candidate = {
            "id": "repair-technical-seo",
            "type": "technical_seo_repair",
            "reason": "One or more deterministic technical SEO/AEO checks are incomplete.",
            "experiment": "Repair the smallest failing canonical/meta/structured-data/sitemap defect and rerun the observatory.",
            "requires_admin": False,
        }
    elif search_console is None:
        candidate = {
            "id": "connect-search-console",
            "type": "measurement_instrumentation",
            "reason": "Technical SEO is measurable, but non-branded impressions/clicks are not yet observed.",
            "experiment": "Configure read-only Google Search Console credentials and collect the first 28-day baseline before changing content strategy.",
            "requires_admin": True,
        }
    else:
        nonbranded = ((search_console.get("summary") or {}).get("nonbranded") or {})
        impressions = float(nonbranded.get("impressions") or 0.0)
        ctr = nonbranded.get("ctr")
        observed_queries = int(
            (search_console.get("summary") or {}).get("portfolio_queries_with_observations") or 0
        )
        external_contributors = int(acquisition.get("external_commit_contributors_observed") or 0)

        if impressions < float(thresholds["minimum_nonbranded_impressions_28d"]):
            candidate = {
                "id": "investigate-nonbranded-discovery",
                "type": "discovery_diagnosis",
                "reason": (
                    f"Observed non-branded impressions ({impressions:.0f}) are below the bootstrap "
                    f"threshold ({float(thresholds['minimum_nonbranded_impressions_28d']):.0f})."
                ),
                "experiment": "Inspect indexed canonical pages and observed query coverage, then improve one evidence-backed intent surface rather than creating many keyword pages.",
                "requires_admin": False,
            }
        elif ctr is not None and float(ctr) < float(thresholds["minimum_nonbranded_ctr"]):
            candidate = {
                "id": "improve-serp-snippet",
                "type": "search_snippet_experiment",
                "reason": (
                    f"Non-branded CTR ({float(ctr):.4f}) is below the bootstrap threshold "
                    f"({float(thresholds['minimum_nonbranded_ctr']):.4f})."
                ),
                "experiment": "Change the title/description of one high-impression low-CTR canonical page, keep the content claim unchanged, and compare the next observation window.",
                "requires_admin": False,
            }
        elif observed_queries < int(thresholds["minimum_portfolio_queries_observed"]):
            candidate = {
                "id": "refine-intent-map",
                "type": "query_portfolio_calibration",
                "reason": (
                    f"Only {observed_queries} exact portfolio queries have observations; "
                    "the hypothesis map is weakly connected to real demand."
                ),
                "experiment": "Use observed non-branded queries to revise one intent cluster while preserving canonical-page consolidation and evidence requirements.",
                "requires_admin": False,
            }
        elif external_contributors == 0:
            candidate = {
                "id": "improve-contributor-conversion",
                "type": "community_activation_experiment",
                "reason": "Search discovery is observed but no external commit contributor is visible in the bounded acquisition signal.",
                "experiment": "Improve one visitor-to-first-contribution path: runnable quickstart, bounded starter task, or reproduction challenge; measure whether an external contributor reaches verified work.",
                "requires_admin": False,
            }
        else:
            candidate = {
                "id": "measure-authority-and-funnel",
                "type": "measurement_expansion",
                "reason": "Basic discovery and acquisition signals exist; the next missing evidence is independent authority/referral and funnel attribution.",
                "experiment": "Add one read-only authority/referral measurement source before increasing promotion or content volume.",
                "requires_admin": False,
            }

    return {
        "version": 1,
        "method": VERSION,
        "selected_experiment": candidate,
        "candidate_count": 1,
        "policy_status": policy["status"],
        "threshold_provenance": policy["provenance"],
        "interpretation": {
            "selection": "one bootstrap recommendation from currently observed bottlenecks; not a causal optimum",
            "no_op": "future versions may emit no-op when evidence does not justify an experiment",
        },
        "authority": dict(policy["authority"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visibility", type=Path, required=True)
    parser.add_argument("--portfolio", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/visibility-growth-policy-v0.1.json"))
    parser.add_argument("--search-console", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    search_console = (
        load_json(args.search_console)
        if args.search_console is not None and args.search_console.exists()
        else None
    )
    result = select(
        load_json(args.visibility),
        load_json(args.portfolio),
        load_json(args.policy),
        search_console=search_console,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["selected_experiment"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
