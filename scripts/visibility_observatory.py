#!/usr/bin/env python3
"""Collect bounded visibility, SEO, and community-acquisition observables.

This observer deliberately separates discovery signals (stars, forks, search-facing
metadata) from correctness, verification, and integration authority. Popularity is
useful evidence about reach, never evidence that a change is correct.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.evolution_snapshot import GitHubObservationUnavailable, _is_bot, _request_json
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from evolution_snapshot import GitHubObservationUnavailable, _is_bot, _request_json


OBSERVATION_UNAVAILABLE_EXIT = 75
VERSION = "visibility-observatory-v0.1"
RequestJSON = Callable[[str, str, dict[str, Any] | None], Any]


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.h1_count = 0
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.json_ld_blocks = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): value or "" for key, value in attrs}
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = True
        elif lowered == "h1":
            self.h1_count += 1
        elif lowered == "meta":
            key = (values.get("name") or values.get("property") or "").lower()
            if key:
                self.meta[key] = values.get("content", "")
        elif lowered == "link":
            rel = values.get("rel", "").lower()
            if rel:
                self.links[rel] = values.get("href", "")
        elif lowered == "script" and values.get("type", "").lower() == "application/ld+json":
            self.json_ld_blocks += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _ratio(successes: int, total: int) -> float | None:
    return round(successes / total, 6) if total else None


def _site_observables(docs_dir: Path) -> dict[str, Any]:
    _require(docs_dir.is_dir(), f"docs directory not found: {docs_dir}")
    pages = sorted(docs_dir.rglob("*.html"))
    page_rows: list[dict[str, Any]] = []

    for path in pages:
        parser = _PageParser()
        parser.feed(path.read_text(encoding="utf-8"))
        robots = parser.meta.get("robots", "").lower()
        checks = {
            "title": bool(parser.title),
            "meta_description": bool(parser.meta.get("description")),
            "canonical": bool(parser.links.get("canonical")),
            "og_title": bool(parser.meta.get("og:title")),
            "og_description": bool(parser.meta.get("og:description")),
            "og_image": bool(parser.meta.get("og:image")),
            "json_ld": parser.json_ld_blocks > 0,
            "single_h1": parser.h1_count == 1,
            "indexable": "noindex" not in robots,
        }
        page_rows.append(
            {
                "path": path.relative_to(docs_dir.parent).as_posix(),
                "checks": checks,
                "passed": sum(checks.values()),
                "total": len(checks),
            }
        )

    check_names = (
        "title",
        "meta_description",
        "canonical",
        "og_title",
        "og_description",
        "og_image",
        "json_ld",
        "single_h1",
        "indexable",
    )
    coverage = {
        name: {
            "passed": sum(bool(row["checks"][name]) for row in page_rows),
            "pages": len(page_rows),
            "ratio": _ratio(sum(bool(row["checks"][name]) for row in page_rows), len(page_rows)),
        }
        for name in check_names
    }

    sitemap_path = docs_dir / "sitemap.xml"
    sitemap_urls = 0
    sitemap_valid = False
    if sitemap_path.is_file():
        try:
            root = ET.fromstring(sitemap_path.read_text(encoding="utf-8"))
            sitemap_urls = sum(1 for node in root.iter() if node.tag.endswith("url"))
            sitemap_valid = root.tag.endswith("urlset")
        except ET.ParseError:
            sitemap_valid = False

    total_checks = sum(int(row["total"]) for row in page_rows)
    passed_checks = sum(int(row["passed"]) for row in page_rows)
    return {
        "html_pages": len(page_rows),
        "technical_checks_passed": passed_checks,
        "technical_checks_total": total_checks,
        "technical_coverage": _ratio(passed_checks, total_checks),
        "coverage_by_check": coverage,
        "sitemap": {
            "present": sitemap_path.is_file(),
            "valid_urlset": sitemap_valid,
            "url_count": sitemap_urls,
        },
        "pages": page_rows,
    }


def _github_observables(
    repository: str,
    token: str,
    request_json: RequestJSON,
) -> dict[str, Any]:
    repo = request_json(f"/repos/{repository}", token, None)
    _require(isinstance(repo, dict), "repository metadata response must be an object")

    rows = request_json(
        f"/repos/{repository}/contributors",
        token,
        {"per_page": 100, "anon": "0"},
    )
    _require(isinstance(rows, list), "contributors response must be an array")
    contributors_truncated = len(rows) >= 100

    owner = repository.split("/", 1)[0].lower()
    external_humans = 0
    bot_contributors = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("contributors response contains a non-object item")
        login = str(row.get("login") or "")
        contributor_type = row.get("type")
        if not login:
            continue
        if _is_bot(login, contributor_type):
            bot_contributors += 1
            continue
        if login.lower() != owner:
            external_humans += 1

    return {
        "repository": repository,
        "discovery": {
            "stars": int(repo.get("stargazers_count") or 0),
            "forks": int(repo.get("forks_count") or 0),
            "subscribers": int(repo.get("subscribers_count") or 0),
            "topics": sorted(str(value) for value in (repo.get("topics") or [])),
        },
        "community_acquisition": {
            "external_commit_contributors_observed": external_humans,
            "bot_contributors_observed": bot_contributors,
            "contributors_page_truncated": contributors_truncated,
            "population_note": "GitHub contributors endpoint; commit attribution only, not all reviewers/researchers/documenters",
        },
        "repository_age": {
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
        },
    }


def observe(
    repository: str,
    token: str,
    docs_dir: Path,
    *,
    request_json: RequestJSON = _request_json,
) -> dict[str, Any]:
    _require(repository.count("/") == 1, "repository must be owner/name")
    github = _github_observables(repository, token, request_json)
    site = _site_observables(docs_dir)

    gaps: list[str] = []
    if site["technical_coverage"] != 1.0:
        gaps.append("technical_seo_metadata_incomplete")
    if not site["sitemap"]["present"] or not site["sitemap"]["valid_urlset"]:
        gaps.append("sitemap_missing_or_invalid")
    if github["community_acquisition"]["external_commit_contributors_observed"] == 0:
        gaps.append("no_external_commit_contributors_observed")
    gaps.append("search_impressions_and_nonbranded_query_coverage_not_collected")
    gaps.append("referring_domains_and_external_mentions_not_collected")
    gaps.append("visitor_to_contributor_conversion_not_collected")

    return {
        "version": 1,
        "method": VERSION,
        "github": github,
        "site": site,
        "gaps": gaps,
        "interpretation": {
            "stars_and_forks": "discovery/interest signals only; never correctness, trust, or integration evidence",
            "seo_metadata": "technical indexability signal only; not evidence of ranking or traffic",
            "external_contributors": "community-acquisition signal with incomplete contribution-type coverage",
        },
        "authority": {
            "correctness_claim": False,
            "ranking_claim": False,
            "policy_activation": False,
            "github_write": False,
            "merge_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    try:
        result = observe(args.repository, token, args.docs_dir)
    except GitHubObservationUnavailable as error:
        print(f"observation unavailable: {error}", file=sys.stderr)
        return OBSERVATION_UNAVAILABLE_EXIT

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "stars": result["github"]["discovery"]["stars"],
                "forks": result["github"]["discovery"]["forks"],
                "external_commit_contributors_observed": result["github"]["community_acquisition"]["external_commit_contributors_observed"],
                "technical_seo_coverage": result["site"]["technical_coverage"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
