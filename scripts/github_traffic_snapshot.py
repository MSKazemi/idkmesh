#!/usr/bin/env python3
"""Collect real, aggregate GitHub repository traffic as optional discovery evidence.

GitHub Traffic API access requires an owner-authorized token with Administration
(read). Ordinary GITHUB_TOKEN credentials must not be treated as sufficient.
The script never persists credentials, identities, request headers, or raw API errors.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


VERSION = "github-traffic-snapshot-v0.1"
API_ROOT = "https://api.github.com/repos"
GetJSON = Callable[[str, str], Any]
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def _require(valid: bool, message: str) -> None:
    if not valid:
        raise ValueError(message)


def _count(value: Any, label: str) -> int:
    _require(type(value) is int and 0 <= value <= 10**12, f"{label} must be a non-negative integer")
    return value


def _timestamp(value: Any) -> str:
    _require(isinstance(value, str) and bool(value), "traffic timestamp must be a nonempty string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("traffic timestamp must be ISO 8601") from error
    _require(parsed.tzinfo is not None, "traffic timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "idkmesh-traffic-observatory",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Do not copy response bodies: they are not an evidence contract and may
        # contain unexpected private account information.
        raise RuntimeError(
            f"GitHub Traffic API HTTP {error.code}; verify the repository-scoped "
            "read-only Administration permission"
        ) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("GitHub Traffic API unavailable; no traffic snapshot collected") from None
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("GitHub Traffic API returned invalid JSON") from error


def _daily_totals(payload: Any, kind: str) -> dict[str, Any]:
    _require(isinstance(payload, dict), f"{kind} response must be an object")
    count = _count(payload.get("count"), f"{kind}.count")
    uniques = _count(payload.get("uniques"), f"{kind}.uniques")
    _require(uniques <= count, f"{kind}.uniques cannot exceed count")
    rows = payload.get(kind)
    _require(isinstance(rows, list) and len(rows) <= 31, f"{kind} daily rows must be a bounded list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        _require(isinstance(row, dict), f"{kind}[{index}] must be an object")
        stamp = _timestamp(row.get("timestamp"))
        _require(stamp not in seen, f"{kind} contains duplicate timestamp")
        seen.add(stamp)
        daily_count = _count(row.get("count"), f"{kind}[{index}].count")
        daily_uniques = _count(row.get("uniques"), f"{kind}[{index}].uniques")
        _require(daily_uniques <= daily_count, f"{kind}[{index}].uniques cannot exceed count")
        normalized.append({"timestamp": stamp, "count": daily_count, "uniques": daily_uniques})
    return {"count": count, "uniques": uniques, "daily": sorted(normalized, key=lambda item: item["timestamp"])}


def _referrers(payload: Any) -> list[dict[str, Any]]:
    _require(isinstance(payload, list) and len(payload) <= 100, "referrers must be a bounded list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(payload):
        _require(isinstance(row, dict), f"referrers[{index}] must be an object")
        name = row.get("referrer")
        _require(
            isinstance(name, str) and 0 < len(name) <= 255 and name.isprintable(),
            f"referrers[{index}].referrer must be a bounded printable name",
        )
        _require(name not in seen, "referrers must not contain duplicate names")
        seen.add(name)
        count = _count(row.get("count"), f"referrers[{index}].count")
        uniques = _count(row.get("uniques"), f"referrers[{index}].uniques")
        _require(uniques <= count, f"referrers[{index}].uniques cannot exceed count")
        normalized.append({"referrer": name, "count": count, "uniques": uniques})
    return normalized


def collect(
    repository: str,
    token: str,
    *,
    get_json: GetJSON = _get_json,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Collect three aggregate endpoints without collecting visitor identities."""
    _require(
        isinstance(repository, str)
        and bool(_REPOSITORY.fullmatch(repository))
        and all(not part.startswith(".") for part in repository.split("/")),
        "repository must be owner/name",
    )
    _require(bool(token), "owner-authorized GitHub Traffic token is required")
    stamp = _timestamp(collected_at) if collected_at is not None else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = f"{API_ROOT}/{repository}/traffic"
    views = _daily_totals(get_json(f"{base}/views", token), "views")
    clones = _daily_totals(get_json(f"{base}/clones", token), "clones")
    referrers = _referrers(get_json(f"{base}/popular/referrers", token))
    return {
        "version": 1,
        "method": VERSION,
        "source": {
            "provider": "github_repository_traffic_api",
            "repository": repository,
            "collected_at_utc": stamp,
            "window": "github_rolling_14_days",
            "referrers": "github_aggregate_top_referrers_only",
        },
        "views": views,
        "clones": clones,
        "referrers": referrers,
        "limitations": [
            "github_traffic_api_history_is_limited_to_the_recent_14_day_window",
            "daily_unique_counts_cannot_be_summed_to_obtain_window_unique_visitors",
            "top_referrers_are_not_exhaustive",
            "repo_views_are_not_website_page_views_or_search_console_clicks",
            "clones_and_views_are_not_proof_of_activation_or_contribution",
            "observed_traffic_does_not_establish_causality_or_correctness",
        ],
        "authority": {
            "correctness_claim": False,
            "causal_claim": False,
            "publication_authority": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TRAFFIC_READ_TOKEN")
    if not token:
        parser.error("GITHUB_TRAFFIC_READ_TOKEN is not configured; no traffic observation collected")
    result = collect(args.repository, token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "unique_repo_visitors_14d": result["views"]["uniques"],
        "total_repo_views_14d": result["views"]["count"],
        "unique_cloners_14d": result["clones"]["uniques"],
        "total_clones_14d": result["clones"]["count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
