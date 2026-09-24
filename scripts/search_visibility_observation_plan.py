#!/usr/bin/env python3
"""Generate balanced cross-engine observation worklists from the canonical 100 intents.

This tool creates measurement work, not visibility evidence. A work item becomes
an observation only after a named product surface is actually queried and the
result is recorded under the search-visibility evidence contract.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "config" / "seo-topics-v1.json"
SURFACES = ROOT / "config" / "search-observation-surfaces-v0.1.json"
EVIDENCE_SCHEMA = ROOT / "schemas" / "search-visibility-observation-v0.1.schema.json"
METHOD = "cross-engine-100-intent-observation-plan-v0.1"


class ObservationPlanError(ValueError):
    """The observation plan violates its query/surface contract."""


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ObservationPlanError(f"{path}: expected a JSON object")
    return value


def _schema_enums() -> tuple[set[str], set[str], set[str]]:
    schema = load_json(EVIDENCE_SCHEMA)
    props = schema["$defs"]["observation"]["properties"]
    return (
        set(props["engine"]["enum"]),
        set(props["surface"]["enum"]),
        set(props["evidence_class"]["enum"]),
    )


def validate_surfaces(payload: dict[str, Any]) -> list[dict[str, str]]:
    if payload.get("version") != 1:
        raise ObservationPlanError("surface config version must be 1")
    if payload.get("status") != "observation_plan_only_not_visibility_evidence":
        raise ObservationPlanError("surface config must preserve the evidence boundary")

    rules = payload.get("rules")
    surfaces = payload.get("surfaces")
    if not isinstance(rules, dict) or not isinstance(surfaces, list):
        raise ObservationPlanError("surface config needs rules and surfaces")
    if rules.get("query_source") != "config/seo-topics-v1.json":
        raise ObservationPlanError("surface config must use the canonical SEO query source")
    if rules.get("evidence_schema") != "schemas/search-visibility-observation-v0.1.schema.json":
        raise ObservationPlanError("surface config must use the visibility evidence schema")
    if rules.get("full_query_count_per_surface") != 100:
        raise ObservationPlanError("full query count per surface must remain 100")
    if rules.get("head_query_count_per_surface") != 10:
        raise ObservationPlanError("head query count per surface must remain 10")
    primary_surface_count = rules.get("primary_surface_count")
    if not isinstance(primary_surface_count, int) or primary_surface_count < 1:
        raise ObservationPlanError("primary surface count must be a positive integer")

    allowed_engines, allowed_surfaces, allowed_evidence = _schema_enums()
    ids: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in surfaces:
        if not isinstance(item, dict):
            raise ObservationPlanError("every surface must be an object")
        required = ("id", "engine", "surface", "evidence_class", "label")
        for key in required:
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ObservationPlanError(f"surface is missing {key}")
        surface_id = item["id"]
        if surface_id in ids:
            raise ObservationPlanError(f"duplicate surface id: {surface_id}")
        ids.add(surface_id)
        if item["engine"] not in allowed_engines:
            raise ObservationPlanError(f"{surface_id}: unsupported engine {item['engine']}")
        if item["surface"] not in allowed_surfaces:
            raise ObservationPlanError(f"{surface_id}: unsupported surface {item['surface']}")
        if item["evidence_class"] not in allowed_evidence:
            raise ObservationPlanError(
                f"{surface_id}: unsupported evidence class {item['evidence_class']}"
            )
        normalized.append({key: item[key] for key in required})

    if len(normalized) != primary_surface_count:
        raise ObservationPlanError(
            f"expected {primary_surface_count} primary surfaces, found {len(normalized)}"
        )
    return normalized


def _query_rows(sample: str) -> list[dict[str, str | int]]:
    topics = load_json(TOPICS)
    clusters = topics.get("clusters")
    if not isinstance(clusters, list) or len(clusters) != 10:
        raise ObservationPlanError("canonical query source must contain 10 clusters")

    rows: list[dict[str, str | int]] = []
    seen: set[str] = set()
    for cluster in clusters:
        queries = cluster.get("queries")
        if not isinstance(queries, list) or len(queries) != 10:
            raise ObservationPlanError(
                f"{cluster.get('id', '<unknown>')}: expected 10 canonical queries"
            )
        selected = queries if sample == "full" else queries[:1]
        for index, query in enumerate(queries, start=1):
            if query in seen:
                raise ObservationPlanError(f"duplicate canonical query: {query}")
            seen.add(query)
            if query not in selected:
                continue
            rows.append(
                {
                    "cluster": cluster["id"],
                    "query_number": index,
                    "mapped_intent": query,
                    "query": query,
                    "target_url": cluster["url"],
                }
            )
    if len(seen) != 100:
        raise ObservationPlanError(f"expected 100 unique canonical queries, found {len(seen)}")
    expected = 100 if sample == "full" else 10
    if len(rows) != expected:
        raise ObservationPlanError(
            f"{sample}: expected {expected} selected queries, found {len(rows)}"
        )
    return rows


def build_plan(
    *,
    sample: str = "full",
    surface_ids: set[str] | None = None,
) -> dict[str, Any]:
    if sample not in {"full", "heads"}:
        raise ObservationPlanError("sample must be 'full' or 'heads'")

    surface_config = load_json(SURFACES)
    surfaces = validate_surfaces(surface_config)
    if surface_ids:
        known = {item["id"] for item in surfaces}
        unknown = sorted(surface_ids - known)
        if unknown:
            raise ObservationPlanError("unknown surface id(s): " + ", ".join(unknown))
        surfaces = [item for item in surfaces if item["id"] in surface_ids]
    if not surfaces:
        raise ObservationPlanError("at least one surface must be selected")

    queries = _query_rows(sample)
    items: list[dict[str, Any]] = []
    for surface in surfaces:
        for query in queries:
            plan_id = (
                f"{METHOD}/{surface['id']}/{query['cluster']}/"
                f"q{int(query['query_number']):02d}"
            )
            items.append(
                {
                    "plan_id": plan_id,
                    "engine": surface["engine"],
                    "product_surface": surface["id"],
                    "surface": surface["surface"],
                    "evidence_class": surface["evidence_class"],
                    "cluster": query["cluster"],
                    "mapped_intent": query["mapped_intent"],
                    "query": query["query"],
                    "target_url": query["target_url"],
                }
            )

    return {
        "version": 1,
        "method": METHOD,
        "status": "plan_only_not_observed_evidence",
        "sample": sample,
        "query_source": "config/seo-topics-v1.json",
        "surface_source": "config/search-observation-surfaces-v0.1.json",
        "summary": {
            "surfaces": len(surfaces),
            "queries_per_surface": len(queries),
            "work_items": len(items),
            "clusters": 10,
        },
        "items": items,
        "authority": {
            "visibility_claim": False,
            "ranking_claim": False,
            "citation_claim": False,
            "content_creation_authority": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def render_csv(plan: dict[str, Any]) -> str:
    columns = (
        "plan_id",
        "engine",
        "product_surface",
        "surface",
        "evidence_class",
        "cluster",
        "mapped_intent",
        "query",
        "target_url",
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for item in plan["items"]:
        writer.writerow({key: item[key] for key in columns})
    return stream.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", choices=("full", "heads"), default="full")
    parser.add_argument(
        "--surface",
        action="append",
        dest="surfaces",
        help="Limit to one surface id; repeat to include several.",
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        plan = build_plan(
            sample=args.sample,
            surface_ids=set(args.surfaces) if args.surfaces else None,
        )
    except (OSError, json.JSONDecodeError, KeyError, ObservationPlanError) as exc:
        parser.error(str(exc))

    if args.format == "json":
        rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_csv(plan)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    **plan["summary"],
                    "sample": plan["sample"],
                },
                sort_keys=True,
            )
        )
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
