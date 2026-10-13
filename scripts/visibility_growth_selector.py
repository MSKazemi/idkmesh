#!/usr/bin/env python3
"""Select at most one bounded visibility/community growth experiment.

This controller is recommendation-only. It diagnoses the narrowest observed bottleneck
from repository-visible evidence and optional Search Console evidence. It never
publishes content, contacts people, creates issues, mutates branches, or merges code.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


VERSION = "visibility-growth-selector-v0.2"

try:
    from scripts.authority_reference_ledger import validate as validate_authority_references
except ModuleNotFoundError:  # Direct execution sets sys.path to scripts/.
    from authority_reference_ledger import validate as validate_authority_references


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
    _require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                 for value in thresholds.values()), "thresholds must be finite non-negative numbers")
    _require(authority.get("recommendation_only") is True, "policy must remain recommendation-only")
    for forbidden in (
        "automatic_content_publication",
        "automatic_outreach",
        "automatic_issue_creation",
        "merge_authority",
    ):
        _require(authority.get(forbidden) is False, f"{forbidden} must remain disabled")



def _metric(value: Any, name: str, *, integer: bool = False) -> float | int:
    if integer:
        _require(type(value) is int and 0 <= value <= 1_000_000, f"{name} must be a non-negative integer")
        return value
    _require(type(value) in (int, float) and math.isfinite(value) and
             0 <= value <= 1e12, f"{name} must be a finite non-negative number")
    return float(value)


def _search_evidence(snapshot: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(snapshot, dict) and snapshot.get("version") == 1,
             "Search Console v1 evidence required")
    source = snapshot.get("source")
    _require(isinstance(source, dict) and
             source.get("provider") == "google_search_console" and
             source.get("page_prefix") == "https://mskazemi.com/idkmesh/" and
             source.get("dimensions") == ["query", "page"] and
             source.get("search_type") == "web" and
             source.get("data_state") == "final",
             "Search Console provider, canonical page scope, or final-data contract invalid")
    truncated = source.get("truncated_by_local_cap")
    _require(type(truncated) is bool, "Search Console row-cap flag must be boolean")
    summary = snapshot.get("summary")
    _require(isinstance(summary, dict) and isinstance(summary.get("nonbranded"), dict),
             "Search Console nonbranded summary required")
    nonbranded = summary["nonbranded"]
    impressions = _metric(nonbranded.get("impressions"), "nonbranded impressions")
    clicks = _metric(nonbranded.get("clicks"), "nonbranded clicks")
    _require(clicks <= impressions, "Search Console clicks cannot exceed impressions")
    ctr = nonbranded.get("ctr")
    if ctr is not None:
        ctr = _metric(ctr, "nonbranded CTR")
        _require(ctr <= 1, "nonbranded CTR must not exceed one")
    observed = _metric(summary.get("portfolio_queries_with_observations"),
                       "portfolio queries observed", integer=True)
    _require(observed <= 100, "portfolio queries observed cannot exceed 100")
    return {
        "impressions": impressions, "clicks": clicks, "ctr": ctr,
        "observed_portfolio_queries": observed,
        "locally_truncated": truncated,
        "boundary": "Final query/page aggregation may omit some Google rows even without local truncation.",
    }


def _authority_evidence(ledger: dict[str, Any] | None,
                        topics: dict[str, Any] | None) -> dict[str, Any] | None:
    if ledger is None:
        _require(topics is None, "authority topics require a ledger")
        return None
    _require(topics is not None, "authority ledger requires canonical topics")
    rows = validate_authority_references(ledger, topics)
    checked = [
        row for row in rows
        if row["kind"] == "independent"
        and row["review_status"] == "owner_reviewed"
        and row["link_status"] == "direct_link_checked"
    ]
    return {
        "recorded_sources": len(rows),
        "owner_attested_independent_direct_link_claims": len(checked),
        "distinct_referring_hosts_claimed": len({row["source_host"] for row in checked}),
        "clusters_with_claimed_references": len({row["cluster_id"] for row in checked}),
        "boundary": "Owner attestation, not independently authenticated editorial independence.",
    }


def _funnel_evidence(funnel: dict[str, Any] | None,
                     repository: str | None) -> dict[str, Any] | None:
    if funnel is None:
        return None
    _require(isinstance(funnel, dict) and funnel.get("version") == 1 and
             funnel.get("method") == "visibility-funnel-coverage-v0.1",
             "funnel coverage v1 evidence required")
    _require(isinstance(repository, str) and funnel.get("repository") == repository,
             "funnel coverage repository mismatch")
    summary = funnel.get("summary")
    transitions = funnel.get("transitions")
    _require(isinstance(summary, dict) and isinstance(transitions, list) and
             len(transitions) == 6, "funnel coverage summary/transitions malformed")
    observed = _metric(summary.get("direct_stages_observed"), "direct stages observed", integer=True)
    _require(observed <= 2 and summary.get("conversion_rates_estimable") == 0 and
             type(summary.get("conversion_rates_estimable")) is int,
             "funnel coverage cannot assert conversion attribution")
    missing = summary.get("missing_stage_ids")
    _require(isinstance(missing, list) and all(isinstance(item, str) for item in missing),
             "funnel missing-stage IDs required")
    _require(all(isinstance(row, dict) and row.get("status") == "not_attributable"
                 and row.get("rate") is None for row in transitions),
             "funnel transitions cannot claim conversion rates")
    return {
        "direct_stages_observed": observed,
        "missing_stage_ids": sorted(set(missing)),
        "conversion_rates_estimable": 0,
        "boundary": "Aggregate coverage evidence does not link search visitors to contributors.",
    }

def select(
    visibility: dict[str, Any],
    portfolio: dict[str, Any],
    policy: dict[str, Any],
    *,
    search_console: dict[str, Any] | None,
    authority_ledger: dict[str, Any] | None = None,
    authority_topics: dict[str, Any] | None = None,
    funnel_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_policy(policy)

    site = visibility.get("site") or {}
    github = visibility.get("github") or {}
    acquisition = github.get("community_acquisition") or {}
    summary = portfolio.get("summary") or {}
    thresholds = policy["thresholds"]

    technical = _metric(site.get("technical_coverage"), "technical SEO coverage")
    _require(technical <= 1, "technical SEO coverage cannot exceed one")
    _require(type(summary.get("queries")) is int and summary["queries"] == 100,
             "canonical portfolio must have exactly 100 query hypotheses")
    search = _search_evidence(search_console) if search_console is not None else None
    authority = _authority_evidence(authority_ledger, authority_topics)
    funnel = _funnel_evidence(funnel_coverage, github.get("repository"))

    candidate: dict[str, Any]

    if (
        technical < 1.0
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
    elif search is None:
        candidate = {
            "id": "connect-search-console",
            "type": "measurement_instrumentation",
            "reason": "Technical SEO is measurable, but non-branded impressions/clicks are not yet observed.",
            "experiment": "Configure read-only Google Search Console credentials and collect the first 28-day baseline before changing content strategy.",
            "requires_admin": True,
        }
    elif search["locally_truncated"]:
        candidate = {
            "id": "inspect-truncated-search-evidence",
            "type": "measurement_quality_review",
            "reason": "Search Console hit the local row cap; missing queries may distort the intent/CTR comparison.",
            "experiment": "Inspect pagination/cap and the affected canonical query pages before making content or title changes.",
            "requires_admin": False,
        }
    else:
        impressions = search["impressions"]
        ctr = search["ctr"]
        observed_queries = search["observed_portfolio_queries"]
        external_contributors = _metric(
            acquisition.get("external_commit_contributors_observed"),
            "external commit contributors", integer=True
        )

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
        elif authority is not None and authority["owner_attested_independent_direct_link_claims"] == 0:
            candidate = {
                "id": "review-one-independent-reference",
                "type": "authority_evidence_review",
                "reason": "No owner-reviewed independent direct-link claims are recorded; this does not mean the web has no links.",
                "experiment": "Examine one genuine third-party technical reference or invite one independent experiment reproduction; record it only after a human verifies source ownership and the actual link.",
                "requires_admin": False,
            }
        elif funnel is not None and "first_verified_contribution" in funnel["missing_stage_ids"]:
            candidate = {
                "id": "design-verified-contribution-cohort",
                "type": "measurement_design",
                "reason": "The V5 coverage report has no first-verified-contributor cohort; commit attribution is only a proxy.",
                "experiment": "Define a privacy-safe, verification-linked and time-bounded contributor cohort before estimating retention or onboarding conversion.",
                "requires_admin": False,
            }
        else:
            candidate = {
                "id": "measure-authority-and-funnel",
                "type": "measurement_expansion",
                "reason": "Basic discovery/acquisition evidence exists; remaining gaps need independent reference review and valid contributor cohorts.",
                "experiment": "Close one unresolved attribution or authority evidence gap using reviewable first-party observations before increasing promotion.",
                "requires_admin": False,
            }

    return {
        "version": 1,
        "method": VERSION,
        "selected_experiment": candidate,
        "candidate_count": 1,
        "policy_status": policy["status"],
        "threshold_provenance": policy["provenance"],
        "evidence": {
            "search_console": search,
            "authority_references": authority,
            "funnel_coverage": funnel,
        },
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
    parser.add_argument("--authority-ledger", type=Path)
    parser.add_argument("--authority-topics", type=Path,
                        default=Path("config/seo-topics-v1.json"))
    parser.add_argument("--funnel-coverage", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    search_console = load_json(args.search_console) if args.search_console is not None else None
    ledger = load_json(args.authority_ledger) if args.authority_ledger is not None else None
    topics = load_json(args.authority_topics) if ledger is not None else None
    funnel = load_json(args.funnel_coverage) if args.funnel_coverage is not None else None
    result = select(
        load_json(args.visibility),
        load_json(args.portfolio),
        load_json(args.policy),
        search_console=search_console,
        authority_ledger=ledger,
        authority_topics=topics,
        funnel_coverage=funnel,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["selected_experiment"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
