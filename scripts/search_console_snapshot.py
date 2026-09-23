#!/usr/bin/env python3
"""Collect aggregate Google Search Console evidence for the IDKMesh discovery loop.

Uses the Search Analytics query endpoint with query+page dimensions. Output remains
observational: ranking/traffic data may guide discovery experiments but grants no
correctness, publication, policy, or merge authority.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable


VERSION = "google-search-console-snapshot-v0.1"
SEARCH_ANALYTICS_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
PostJSON = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]
PostForm = Callable[[str, dict[str, str]], dict[str, Any]]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Search Console request failed with HTTP {error.code}: {body[:500]}") from error
    _require(isinstance(value, dict), "Search Console response must be a JSON object")
    return value


def _post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OAuth token refresh failed with HTTP {error.code}: {body[:500]}") from error
    _require(isinstance(value, dict), "OAuth response must be a JSON object")
    return value


def resolve_access_token(
    access_token: str | None,
    refresh_token: str | None,
    client_id: str | None,
    client_secret: str | None,
    *,
    post_form: PostForm = _post_form,
) -> str:
    if access_token:
        return access_token
    if refresh_token and client_id and client_secret:
        response = post_form(
            TOKEN_ENDPOINT,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token = response.get("access_token")
        _require(isinstance(token, str) and token, "OAuth refresh response is missing access_token")
        return token
    raise ValueError(
        "configure GSC_ACCESS_TOKEN or GSC_REFRESH_TOKEN + GSC_CLIENT_ID + GSC_CLIENT_SECRET"
    )


def _portfolio_index(portfolio: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for cluster in portfolio.get("clusters") or []:
        cluster_id = str(cluster.get("id") or "")
        for query in cluster.get("queries") or []:
            normalized = " ".join(str(query).lower().split())
            if normalized:
                index[normalized] = cluster_id
    return index


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    impressions = sum(float(row["impressions"]) for row in rows)
    clicks = sum(float(row["clicks"]) for row in rows)
    weighted_position = sum(
        float(row["position"]) * float(row["impressions"]) for row in rows
    )
    return {
        "rows": len(rows),
        "clicks": round(clicks, 6),
        "impressions": round(impressions, 6),
        "ctr": round(clicks / impressions, 6) if impressions else None,
        "impression_weighted_position": (
            round(weighted_position / impressions, 6) if impressions else None
        ),
    }


def analyze_rows(
    rows: list[dict[str, Any]],
    portfolio: dict[str, Any],
    *,
    page_prefix: str | None,
) -> dict[str, Any]:
    portfolio_index = _portfolio_index(portfolio)
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        keys = row.get("keys")
        _require(isinstance(keys, list) and len(keys) == 2, "Search Console row must contain query and page keys")
        query, page = str(keys[0]), str(keys[1])
        if page_prefix and not page.startswith(page_prefix):
            continue
        normalized_query = " ".join(query.lower().split())
        impressions = float(row.get("impressions") or 0.0)
        clicks = float(row.get("clicks") or 0.0)
        ctr = float(row.get("ctr") or 0.0)
        position = float(row.get("position") or 0.0)
        _require(impressions >= 0 and clicks >= 0, "Search Console counts must be non-negative")
        _require(0 <= ctr <= 1, "Search Console CTR must be in [0, 1]")
        _require(position >= 0, "Search Console position must be non-negative")
        normalized_rows.append(
            {
                "query": query,
                "page": page,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": ctr,
                "position": position,
                "branded": "idkmesh" in normalized_query,
                "portfolio_cluster": portfolio_index.get(normalized_query),
            }
        )

    branded = [row for row in normalized_rows if row["branded"]]
    nonbranded = [row for row in normalized_rows if not row["branded"]]
    portfolio_rows = [row for row in nonbranded if row["portfolio_cluster"]]

    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in portfolio_rows:
        by_cluster.setdefault(str(row["portfolio_cluster"]), []).append(row)

    return {
        "rows": normalized_rows,
        "summary": {
            "all": _aggregate(normalized_rows),
            "branded": _aggregate(branded),
            "nonbranded": _aggregate(nonbranded),
            "portfolio_exact_matches": _aggregate(portfolio_rows),
            "portfolio_queries_with_observations": len(
                {row["query"].lower() for row in portfolio_rows}
            ),
        },
        "portfolio_clusters": {
            cluster: _aggregate(cluster_rows)
            for cluster, cluster_rows in sorted(by_cluster.items())
        },
    }


def collect(
    *,
    site_url: str,
    access_token: str,
    start_date: str,
    end_date: str,
    portfolio: dict[str, Any],
    page_prefix: str | None,
    max_rows: int = 100000,
    post_json: PostJSON = _post_json,
) -> dict[str, Any]:
    _require(site_url, "site_url is required")
    _require(max_rows > 0, "max_rows must be positive")
    endpoint = SEARCH_ANALYTICS_ENDPOINT.format(
        site=urllib.parse.quote(site_url, safe="")
    )
    row_limit = min(25000, max_rows)
    start_row = 0
    rows: list[dict[str, Any]] = []
    truncated = False

    while start_row < max_rows:
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query", "page"],
            "type": "web",
            "dataState": "final",
            "rowLimit": min(row_limit, max_rows - start_row),
            "startRow": start_row,
        }
        response = post_json(
            endpoint,
            payload,
            {"Authorization": f"Bearer {access_token}"},
        )
        page_rows = response.get("rows") or []
        _require(isinstance(page_rows, list), "Search Console rows must be an array")
        rows.extend(page_rows)
        if len(page_rows) < int(payload["rowLimit"]):
            break
        start_row += len(page_rows)
        if start_row >= max_rows:
            truncated = True
            break

    analyzed = analyze_rows(rows, portfolio, page_prefix=page_prefix)
    return {
        "version": 1,
        "method": VERSION,
        "source": {
            "provider": "google_search_console",
            "site_url": site_url,
            "page_prefix": page_prefix,
            "start_date": start_date,
            "end_date": end_date,
            "dimensions": ["query", "page"],
            "search_type": "web",
            "data_state": "final",
            "max_rows": max_rows,
            "truncated_by_local_cap": truncated,
        },
        **analyzed,
        "limitations": [
            "search_console_api_does_not_guarantee_all_rows_only_top_rows",
            "exact_portfolio_match_does_not_capture_semantic_query_variants",
            "search_observation_is_not_causal_attribution",
            "query_rows_are_aggregate_search_data_not_user_level_browsing_data",
        ],
        "authority": {
            "search_demand_observation": True,
            "causal_claim": False,
            "content_creation_authority": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--page-prefix", default="https://mskazemi.com/idkmesh/")
    parser.add_argument("--portfolio", type=Path, default=Path("config/discovery-query-portfolio-v0.1.json"))
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--lag-days", type=int, default=3)
    parser.add_argument("--max-rows", type=int, default=100000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    _require(args.days >= 1, "days must be positive")
    _require(args.lag_days >= 0, "lag-days must be non-negative")
    end = date.today() - timedelta(days=args.lag_days)
    start = end - timedelta(days=args.days - 1)

    token = resolve_access_token(
        os.environ.get("GSC_ACCESS_TOKEN"),
        os.environ.get("GSC_REFRESH_TOKEN"),
        os.environ.get("GSC_CLIENT_ID"),
        os.environ.get("GSC_CLIENT_SECRET"),
    )
    portfolio = json.loads(args.portfolio.read_text(encoding="utf-8"))
    result = collect(
        site_url=args.site_url,
        access_token=token,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        portfolio=portfolio,
        page_prefix=args.page_prefix or None,
        max_rows=args.max_rows,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "nonbranded_impressions": result["summary"]["nonbranded"]["impressions"],
                "nonbranded_clicks": result["summary"]["nonbranded"]["clicks"],
                "portfolio_queries_with_observations": result["summary"]["portfolio_queries_with_observations"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
