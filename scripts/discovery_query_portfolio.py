#!/usr/bin/env python3
"""Validate and summarize the versioned discovery-query portfolio.

The portfolio is a hypothesis map for non-branded search intent. It does not claim
query demand, ranking, traffic, or conversion until authoritative search analytics
are attached by a separate observer.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


VERSION = "discovery-query-portfolio-v0.1"


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def validate(portfolio: dict[str, Any], root: Path) -> dict[str, Any]:
    _require(portfolio.get("version") == 1, "portfolio version must be 1")
    _require(
        portfolio.get("status") == "hypothesis_seed_not_search_demand_evidence",
        "portfolio status must preserve the hypothesis/evidence boundary",
    )
    rules = portfolio.get("rules")
    clusters = portfolio.get("clusters")
    _require(isinstance(rules, dict), "rules must be an object")
    _require(isinstance(clusters, list), "clusters must be an array")

    expected_clusters = int(rules.get("exact_cluster_count", 0))
    expected_queries = int(rules.get("exact_queries_per_cluster", 0))
    _require(expected_clusters > 0, "exact_cluster_count must be positive")
    _require(expected_queries > 0, "exact_queries_per_cluster must be positive")
    _require(
        len(clusters) == expected_clusters,
        f"expected exactly {expected_clusters} clusters",
    )
    _require(rules.get("branded_queries_allowed") is False, "branded queries must be disabled")
    _require(rules.get("authority") == "recommendation_only", "portfolio authority must be recommendation_only")

    query_source = portfolio.get("query_source")
    _require(
        query_source == "config/seo-topics-v1.json",
        "portfolio must declare config/seo-topics-v1.json as the canonical query source",
    )
    source_path = root / str(query_source)
    _require(source_path.is_file(), f"canonical query source is missing: {query_source}")
    seo_topics = load_json(source_path)
    seo_clusters = seo_topics.get("clusters")
    _require(isinstance(seo_clusters, list), "canonical SEO topic clusters must be an array")
    canonical_by_id = {
        str(cluster.get("id") or ""): cluster
        for cluster in seo_clusters
        if isinstance(cluster, dict)
    }
    _require(
        len(canonical_by_id) == expected_clusters,
        "canonical SEO query source must contain the expected cluster count",
    )

    seen_cluster_ids: set[str] = set()
    seen_queries: set[str] = set()
    target_counts: Counter[str] = Counter()
    target_cluster_counts: Counter[str] = Counter()
    missing_targets: list[str] = []
    missing_evidence: list[str] = []
    cluster_rows: list[dict[str, Any]] = []

    for cluster in clusters:
        _require(isinstance(cluster, dict), "cluster must be an object")
        cluster_id = cluster.get("id")
        label = cluster.get("label")
        target = cluster.get("canonical_target")
        evidence_refs = cluster.get("evidence_refs")
        queries = cluster.get("queries")

        _require(isinstance(cluster_id, str) and cluster_id, "cluster id is required")
        _require(cluster_id not in seen_cluster_ids, f"duplicate cluster id: {cluster_id}")
        seen_cluster_ids.add(cluster_id)
        _require(isinstance(label, str) and label, f"{cluster_id}: label is required")
        _require(isinstance(target, str) and target, f"{cluster_id}: canonical_target is required")
        _require(isinstance(evidence_refs, list) and evidence_refs, f"{cluster_id}: evidence_refs are required")
        _require(isinstance(queries, list), f"{cluster_id}: queries must be an array")
        _require(
            len(queries) == expected_queries,
            f"{cluster_id}: expected exactly {expected_queries} queries",
        )

        normalized: list[str] = []
        for query in queries:
            _require(isinstance(query, str) and query.strip(), f"{cluster_id}: query must be non-empty")
            value = " ".join(query.lower().split())
            _require("idkmesh" not in value, f"{cluster_id}: branded query is not allowed: {query}")
            _require(value not in seen_queries, f"duplicate query: {query}")
            seen_queries.add(value)
            normalized.append(value)


        canonical = canonical_by_id.get(cluster_id)
        _require(
            isinstance(canonical, dict),
            f"{cluster_id}: cluster is absent from the canonical SEO query source",
        )
        _require(
            label == canonical.get("title"),
            f"{cluster_id}: analytics label must match the canonical SEO title",
        )
        _require(
            target == canonical.get("path"),
            f"{cluster_id}: analytics target must match the canonical SEO topic path",
        )
        canonical_queries = canonical.get("queries")
        _require(
            isinstance(canonical_queries, list) and queries == canonical_queries,
            f"{cluster_id}: analytics queries must match the canonical SEO query source exactly",
        )

        target_counts[target] += len(normalized)
        target_cluster_counts[target] += 1
        if not (root / target).is_file():
            missing_targets.append(target)

        missing_for_cluster: list[str] = []
        for ref in evidence_refs:
            _require(isinstance(ref, str) and ref, f"{cluster_id}: evidence ref must be non-empty")
            if not (root / ref).exists():
                missing_evidence.append(ref)
                missing_for_cluster.append(ref)

        cluster_rows.append(
            {
                "id": cluster_id,
                "label": label,
                "query_count": len(normalized),
                "canonical_target": target,
                "canonical_target_exists": (root / target).is_file(),
                "evidence_ref_count": len(evidence_refs),
                "missing_evidence_refs": sorted(missing_for_cluster),
            }
        )

    expected_total = expected_clusters * expected_queries
    _require(len(seen_queries) == expected_total, f"expected exactly {expected_total} unique queries")

    _require(not missing_targets, "missing canonical targets: " + ", ".join(sorted(set(missing_targets))))
    _require(not missing_evidence, "missing evidence refs: " + ", ".join(sorted(set(missing_evidence))))

    target_rows = [
        {
            "canonical_target": target,
            "query_count": target_counts[target],
            "cluster_count": target_cluster_counts[target],
        }
        for target in sorted(target_counts)
    ]
    max_target_queries = max(target_counts.values(), default=0)

    return {
        "version": 1,
        "method": VERSION,
        "portfolio_status": portfolio["status"],
        "canonical_query_source": str(query_source),
        "summary": {
            "clusters": len(clusters),
            "queries": len(seen_queries),
            "distinct_canonical_targets": len(target_counts),
            "max_queries_on_one_canonical_target": max_target_queries,
            "all_canonical_targets_exist": True,
            "all_evidence_refs_exist": True,
        },
        "clusters": cluster_rows,
        "target_concentration": target_rows,
        "interpretation": {
            "query_presence": "hypothesis coverage only; not evidence of search volume or user demand",
            "target_concentration": "diagnostic for overloaded canonical pages; not an instruction to create thin pages",
            "next_evidence": "attach aggregate Search Console/Bing observations before changing query priorities",
        },
        "authority": {
            "search_demand_claim": False,
            "ranking_claim": False,
            "content_creation_authority": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--portfolio",
        type=Path,
        default=Path("config/discovery-query-portfolio-v0.1.json"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = validate(load_json(args.portfolio), args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
