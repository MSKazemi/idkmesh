#!/usr/bin/env python3
"""Notify IndexNow about recently changed public documentation URLs.

IndexNow is a discovery/freshness notification, not evidence of indexing or
ranking. The verification key is intentionally public because the protocol
requires search engines to fetch it from the same host/path namespace.

By default only sitemap URLs whose truthful <lastmod> is within the last three
UTC dates are submitted. Use --all for an explicit full resubmission.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SITEMAP = ROOT / "docs" / "sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = "mskazemi.com"
KEY = "7c1f6d4a9b2e3c8f5a0d1e7b4c6f8a2d"
KEY_LOCATION = f"https://{HOST}/idkmesh/{KEY}.txt"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def sitemap_entries() -> list[tuple[str, date]]:
    tree = ElementTree.parse(SITEMAP)
    entries: list[tuple[str, date]] = []
    for element in tree.findall("sm:url", NS):
        loc = element.findtext("sm:loc", default="", namespaces=NS).strip()
        raw = element.findtext("sm:lastmod", default="", namespaces=NS).strip()
        if not loc or not raw:
            continue
        entries.append((loc, date.fromisoformat(raw[:10])))
    return entries


def recently_changed(days: int, today: date | None = None) -> list[str]:
    if days < 1:
        raise ValueError("days must be >= 1")
    now = today or date.today()
    cutoff = now - timedelta(days=days - 1)
    return [url for url, stamp in sitemap_entries() if cutoff <= stamp <= now]


def payload(urls: list[str]) -> dict[str, object]:
    for url in urls:
        if not url.startswith(f"https://{HOST}/idkmesh/"):
            raise ValueError(f"URL outside verified IndexNow path: {url}")
    return {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }


def submit(urls: list[str], timeout: float = 20.0) -> int:
    if not urls:
        print("No recently changed sitemap URLs to submit.")
        return 0
    body = json.dumps(payload(urls), separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        print(f"IndexNow rejected submission: HTTP {error.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as error:
        print(f"IndexNow submission failed: {error}", file=sys.stderr)
        return 1

    if status not in (200, 202):
        print(f"Unexpected IndexNow response: HTTP {status}", file=sys.stderr)
        return 1

    print(f"IndexNow accepted {len(urls)} URL(s): HTTP {status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    urls = [url for url, _ in sitemap_entries()] if args.all else recently_changed(args.days)
    if args.dry_run:
        print(json.dumps(payload(urls), indent=2))
        return 0
    return submit(urls)


if __name__ == "__main__":
    raise SystemExit(main())
