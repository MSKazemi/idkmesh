#!/usr/bin/env python3
"""Normalize Bing Webmaster Tools AI Performance CSV exports without credentials.

The importer is intentionally offline. It consumes an owner-downloaded CSV,
retains only the selected report dimensions/metrics, and never requires a Bing
account token. Grounding-query matching against IDKMesh's canonical 100-intent
portfolio is exact after lowercase/whitespace normalization; semantic matches
remain a reviewed evidence task rather than an automatic claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "config" / "seo-topics-v1.json"
METHOD = "bing-ai-performance-csv-v0.1"
SITE_PREFIX = "https://mskazemi.com/idkmesh/"


class BingAIImportError(ValueError):
    """The exported report cannot be normalized safely."""


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _parse_date(value: str, label: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise BingAIImportError(f"{label} must be an ISO date: {value!r}") from exc


def _parse_count(value: str, *, row_number: int) -> int:
    compact = value.strip().replace(",", "")
    if not compact:
        raise BingAIImportError(f"row {row_number}: citation count is empty")
    try:
        number = int(compact)
    except ValueError as exc:
        raise BingAIImportError(
            f"row {row_number}: citation count must be an integer: {value!r}"
        ) from exc
    if number < 0:
        raise BingAIImportError(
            f"row {row_number}: citation count must be non-negative"
        )
    return number


def _portfolio_index() -> dict[str, dict[str, str]]:
    payload = json.loads(TOPICS.read_text(encoding="utf-8"))
    index: dict[str, dict[str, str]] = {}
    for cluster in payload["clusters"]:
        for query in cluster["queries"]:
            normalized = _normalize(query)
            if normalized in index:
                raise BingAIImportError(f"duplicate canonical intent: {query}")
            index[normalized] = {
                "mapped_intent": query,
                "cluster": cluster["id"],
                "canonical_target": cluster["url"],
            }
    if len(index) != 100:
        raise BingAIImportError(
            f"expected 100 canonical intents, found {len(index)}"
        )
    return index


def _csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BingAIImportError("CSV must be UTF-8 or UTF-8 with BOM") from exc

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise BingAIImportError("CSV has no header row")
    headers = [str(value) for value in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({str(key): str(value or "") for key, value in row.items()})
    return headers, rows, digest


def _require_columns(headers: list[str], required: list[str]) -> None:
    missing = [name for name in required if name not in headers]
    if missing:
        raise BingAIImportError(
            "CSV is missing configured column(s): " + ", ".join(missing)
        )


def _match(query: str, index: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return index.get(_normalize(query))


def normalize(
    *,
    input_path: Path,
    kind: str,
    window_start: str,
    window_end: str,
    citations_column: str,
    query_column: str | None = None,
    page_column: str | None = None,
    date_column: str | None = None,
) -> dict[str, Any]:
    start = _parse_date(window_start, "window_start")
    end = _parse_date(window_end, "window_end")
    if start > end:
        raise BingAIImportError("window_start must not be after window_end")

    headers, raw_rows, digest = _csv_rows(input_path)
    portfolio = _portfolio_index()

    required = [citations_column]
    if kind in {"grounding", "mapping"}:
        if not query_column:
            raise BingAIImportError(f"{kind} imports require --query-column")
        required.append(query_column)
    if kind in {"pages", "mapping"}:
        if not page_column:
            raise BingAIImportError(f"{kind} imports require --page-column")
        required.append(page_column)
    if kind == "timeline":
        if not date_column:
            raise BingAIImportError("timeline imports require --date-column")
        required.append(date_column)
    _require_columns(headers, required)

    rows: list[dict[str, Any]] = []
    exact_matches = 0
    for row_number, raw in enumerate(raw_rows, start=2):
        citations = _parse_count(raw[citations_column], row_number=row_number)
        row: dict[str, Any] = {"citations": citations}

        if kind in {"grounding", "mapping"}:
            query = raw[query_column or ""].strip()
            if not query:
                raise BingAIImportError(
                    f"row {row_number}: grounding query is empty"
                )
            row["grounding_query"] = query
            match = _match(query, portfolio)
            row["portfolio_exact_match"] = match
            if match is not None:
                exact_matches += 1

        if kind in {"pages", "mapping"}:
            page = raw[page_column or ""].strip()
            if not page.startswith(SITE_PREFIX):
                raise BingAIImportError(
                    f"row {row_number}: page must be under {SITE_PREFIX}: {page!r}"
                )
            row["page"] = page

        if kind == "timeline":
            stamp = _parse_date(raw[date_column or ""].strip(), f"row {row_number} date")
            if not start <= stamp <= end:
                raise BingAIImportError(
                    f"row {row_number}: date {stamp} is outside {start}..{end}"
                )
            row["date"] = stamp

        rows.append(row)

    return {
        "version": 1,
        "method": METHOD,
        "source": {
            "provider": "bing_webmaster_tools",
            "report": "ai_performance",
            "export_kind": kind,
            "window_start": start,
            "window_end": end,
            "input_sha256": digest,
        },
        "columns": {
            "citations": citations_column,
            "query": query_column,
            "page": page_column,
            "date": date_column,
        },
        "summary": {
            "rows": len(rows),
            "citation_count_sum": sum(int(row["citations"]) for row in rows),
            "portfolio_exact_match_rows": exact_matches,
        },
        "rows": rows,
        "limitations": [
            "bing_ai_performance_is_aggregated_and_not_a_complete_log_of_every_citation",
            "grounding_queries_are_grouped_phrases_not_exact_user_prompts",
            "exact_portfolio_match_does_not_capture_semantic_query_variants",
            "citation_activity_is_not_ranking_traffic_endorsement_or_causal_attribution",
        ],
        "authority": {
            "citation_observation": True,
            "ranking_claim": False,
            "traffic_claim": False,
            "causal_claim": False,
            "content_creation_authority": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind",
        choices=("grounding", "pages", "mapping", "timeline"),
        required=True,
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--citations-column", required=True)
    parser.add_argument("--query-column")
    parser.add_argument("--page-column")
    parser.add_argument("--date-column")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = normalize(
            input_path=args.input,
            kind=args.kind,
            window_start=args.window_start,
            window_end=args.window_end,
            citations_column=args.citations_column,
            query_column=args.query_column,
            page_column=args.page_column,
            date_column=args.date_column,
        )
    except (OSError, json.JSONDecodeError, BingAIImportError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "kind": result["source"]["export_kind"],
                "rows": result["summary"]["rows"],
                "citation_count_sum": result["summary"]["citation_count_sum"],
                "portfolio_exact_match_rows": result["summary"][
                    "portfolio_exact_match_rows"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
