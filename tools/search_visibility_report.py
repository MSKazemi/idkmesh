#!/usr/bin/env python3
"""Render the committed search/answer-engine visibility evidence ledger."""

from __future__ import annotations

import collections
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOPIC_MAP = ROOT / "config" / "seo-topics-v1.json"
LEDGER = ROOT / "evidence" / "search-visibility" / "observations.json"
REPORT = ROOT / "evidence" / "search-visibility" / "REPORT.md"
SITE_PREFIX = "https://mskazemi.com/idkmesh/"


class VisibilityError(ValueError):
    """The committed visibility evidence violates its semantic contract."""


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def intent_index() -> dict[str, str]:
    payload = load_json(TOPIC_MAP)
    index: dict[str, str] = {}
    for cluster in payload["clusters"]:
        for query in cluster["queries"]:
            if query in index:
                raise VisibilityError(f"duplicate mapped intent: {query}")
            index[query] = cluster["id"]
    return index


def observations() -> list[dict[str, Any]]:
    payload = load_json(LEDGER)
    if payload.get("schema_version") != "0.1":
        raise VisibilityError("unsupported visibility ledger schema version")
    raw = payload.get("observations")
    if not isinstance(raw, list):
        raise VisibilityError("observations must be a list")

    intents = intent_index()
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise VisibilityError("every observation must be an object")
        obs_id = item.get("id")
        if not isinstance(obs_id, str) or not obs_id:
            raise VisibilityError("every observation needs an id")
        if obs_id in seen_ids:
            raise VisibilityError(f"duplicate observation id: {obs_id}")
        seen_ids.add(obs_id)

        mapped = item.get("mapped_intent")
        if mapped not in intents:
            raise VisibilityError(f"{obs_id}: unknown mapped_intent {mapped!r}")

        target = item.get("target_url")
        if not isinstance(target, str) or not target.startswith(SITE_PREFIX):
            raise VisibilityError(f"{obs_id}: target_url must be under {SITE_PREFIX}")

        surfaced = item.get("surfaced")
        if not isinstance(surfaced, bool):
            raise VisibilityError(f"{obs_id}: surfaced must be boolean")
        if not surfaced and item.get("citation_url"):
            raise VisibilityError(f"{obs_id}: non-surfaced observation cannot cite a result")

        position = item.get("position")
        if position is not None and (
            not isinstance(position, int) or isinstance(position, bool) or position < 1
        ):
            raise VisibilityError(f"{obs_id}: position must be a positive integer or null")

        copy = dict(item)
        copy["cluster"] = intents[mapped]
        normalized.append(copy)

    return sorted(
        normalized,
        key=lambda item: (
            item.get("observed_at", ""),
            item.get("engine", ""),
            item["id"],
        ),
    )


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    engines: dict[str, dict[str, int]] = {}
    for engine in sorted({row.get("engine", "unknown") for row in rows}):
        subset = [row for row in rows if row.get("engine") == engine]
        engines[engine] = {
            "observations": len(subset),
            "surfaced": sum(1 for row in subset if row["surfaced"]),
            "intents_observed": len({row["mapped_intent"] for row in subset}),
            "intents_surfaced": len(
                {row["mapped_intent"] for row in subset if row["surfaced"]}
            ),
        }

    clusters: dict[str, dict[str, int]] = {}
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["cluster"]].append(row)
    for cluster in sorted(grouped):
        subset = grouped[cluster]
        clusters[cluster] = {
            "observations": len(subset),
            "surfaced": sum(1 for row in subset if row["surfaced"]),
            "intents_observed": len({row["mapped_intent"] for row in subset}),
            "intents_surfaced": len(
                {row["mapped_intent"] for row in subset if row["surfaced"]}
            ),
        }

    return {
        "observations": len(rows),
        "positive_observations": sum(1 for row in rows if row["surfaced"]),
        "intents_observed": len({row["mapped_intent"] for row in rows}),
        "intents_surfaced": len(
            {row["mapped_intent"] for row in rows if row["surfaced"]}
        ),
        "engines": engines,
        "clusters": clusters,
    }


def render(rows: list[dict[str, Any]]) -> str:
    data = summary(rows)
    lines = [
        "# Search and answer-engine visibility report",
        "",
        "> Evidence boundary: this is a deterministic summary of recorded observations,",
        "> not a cross-engine ranking score, traffic forecast, or guarantee of visibility.",
        "",
        "## Current evidence",
        "",
        f"- Recorded observations: **{data['observations']}**",
        f"- Positive surfaced observations: **{data['positive_observations']}**",
        f"- Of the 100 mapped intents, observed at least once: **{data['intents_observed']}**",
        f"- Of the 100 mapped intents, surfaced at least once: **{data['intents_surfaced']}**",
        "",
    ]

    if not rows:
        lines.extend(
            [
                "No post-deployment search or answer-engine observations have been",
                "committed yet. That is an evidence state, not a failure: repository",
                "configuration can establish crawl/index eligibility, but actual search",
                "visibility must be observed after deployment.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## By engine",
                "",
                "| Engine | Observations | Surfaced | Intents observed | Intents surfaced |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for engine, stats in data["engines"].items():
            lines.append(
                f"| {engine} | {stats['observations']} | {stats['surfaced']} | "
                f"{stats['intents_observed']} | {stats['intents_surfaced']} |"
            )
        lines.append("")

        lines.extend(
            [
                "## By semantic cluster",
                "",
                "| Cluster | Observations | Surfaced | Intents observed | Intents surfaced |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for cluster, stats in data["clusters"].items():
            lines.append(
                f"| {cluster} | {stats['observations']} | {stats['surfaced']} | "
                f"{stats['intents_observed']} | {stats['intents_surfaced']} |"
            )
        lines.append("")

        lines.extend(
            [
                "## Observation log",
                "",
                "| Observed at | Engine | Surface | Mapped intent | Surfaced | Target | Evidence |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in rows:
            evidence = (
                row.get("citation_url")
                or row.get("evidence_ref")
                or "recorded observation"
            )
            yes_no = "yes" if row["surfaced"] else "no"
            lines.append(
                f"| {row.get('observed_at', '')} | {row.get('engine', '')} | "
                f"{row.get('surface', '')} | {row['mapped_intent']} | {yes_no} | "
                f"{row['target_url']} | {evidence} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- A single manual reproduction applies only to that dated product surface and query.",
            "- Search positions from one engine are not averaged with AI-answer citations from another.",
            "- IndexNow acceptance means a change was submitted for discovery; it does not prove indexing.",
            "- Crawler-health checks prove retrievability from the monitor's network path, not ranking.",
            "- Re-prioritize the 100-intent map only when repeated observations or webmaster data justify it.",
            "",
            "Source ledger: `evidence/search-visibility/observations.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.write(render(observations()))
    except (OSError, json.JSONDecodeError, VisibilityError) as exc:
        print(f"search visibility report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
