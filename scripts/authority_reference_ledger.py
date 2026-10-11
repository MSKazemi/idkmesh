#!/usr/bin/env python3
"""Validate and summarize human-reviewed external-reference evidence.

No network requests, backlink scraping, search-rank inference, or authority score.
Only reviewed direct-link claims are counted in the reviewed bucket; classification
is an owner attestation, not proof of source independence.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

KINDS = {"project_authored", "syndication", "external_unknown", "independent"}
REVIEWS = {"unreviewed", "owner_reviewed"}
LINKS = {"not_checked", "mention_only", "direct_link_checked"}
FIELDS = {"id", "source_url", "target_url", "cluster_id", "kind", "review_status", "link_status", "first_observed", "note"}
_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?\Z")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _url(value: object, *, source: bool) -> tuple[str, str]:
    require(isinstance(value, str) and len(value) <= 2048, "URL must be a bounded string")
    require(not any(c in value for c in " \\\r\n\t<>()[]|`"), "URL contains unsupported characters")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and bool(parsed.hostname), "URL must be absolute HTTPS")
    require(parsed.username is None and parsed.password is None and parsed.port is None, "URL must not contain credentials or a port")
    require(not parsed.query and not parsed.fragment, "URL must not contain query parameters or fragment")
    host = parsed.hostname.lower()
    require("." in host and not host.endswith((".local", ".internal", ".test", ".example")), "URL must name a public domain")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("URL must name a domain rather than an IP address")
    require(host.encode("idna").decode("ascii") == host, "URL host must be canonical IDNA ASCII")
    if source:
        require(host not in {"mskazemi.com", "www.mskazemi.com"}, "owned site cannot be an external reference")
        if host in {"github.com", "www.github.com"}:
            require(not parsed.path.lower().startswith("/mskazemi/"), "own GitHub cannot be an external reference")
    return host, value


def validate(ledger: dict, topics: dict) -> list[dict]:
    require(isinstance(ledger, dict) and set(ledger) == {"version", "references"}, "ledger requires version and references only")
    require(ledger["version"] == 1, "ledger version must be 1")
    refs = ledger["references"]
    require(isinstance(refs, list) and len(refs) <= 500, "references must be a bounded array")
    require(isinstance(topics, dict) and isinstance(topics.get("clusters"), list), "canonical topic map is required")
    canonical = {cluster["id"]: cluster["url"] for cluster in topics["clusters"]}
    require(len(canonical) == 10, "expected ten canonical topic clusters")
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    validated = []
    for item in refs:
        require(isinstance(item, dict) and set(item) == FIELDS, "reference has missing or unknown fields")
        identifier = item["id"]
        require(isinstance(identifier, str) and bool(_ID.fullmatch(identifier)), "reference id is not a safe slug")
        require(identifier not in seen_ids, "duplicate reference id")
        seen_ids.add(identifier)
        host, source_url = _url(item["source_url"], source=True)
        _, target_url = _url(item["target_url"], source=False)
        cluster = item["cluster_id"]
        require(cluster in canonical and target_url == canonical[cluster], "reference target must match the canonical cluster URL")
        pair = (source_url, target_url)
        require(pair not in seen_pairs, "duplicate source/target reference")
        seen_pairs.add(pair)
        require(item["kind"] in KINDS, "invalid reference kind")
        require(item["review_status"] in REVIEWS, "invalid review status")
        require(item["link_status"] in LINKS, "invalid link status")
        require(isinstance(item["first_observed"], str), "first_observed must be a date")
        try:
            observed = date.fromisoformat(item["first_observed"])
        except ValueError as error:
            raise ValueError("first_observed is not a valid ISO date") from error
        require(observed.isoformat() == item["first_observed"], "first_observed must use YYYY-MM-DD")
        note = item["note"]
        require(isinstance(note, str) and 1 <= len(note) <= 280 and "\n" not in note, "reference note must be bounded single-line text")
        if item["review_status"] == "unreviewed":
            require(item["link_status"] != "direct_link_checked", "unreviewed reference cannot claim a checked direct link")
        validated.append({**item, "source_host": host})
    return sorted(validated, key=lambda row: row["id"])


def render(ledger: dict, topics: dict) -> str:
    refs = validate(ledger, topics)
    clusters = topics["clusters"]
    checked = [r for r in refs if r["kind"] == "independent" and r["review_status"] == "owner_reviewed" and r["link_status"] == "direct_link_checked"]
    domains = sorted({r["source_host"] for r in checked})
    canonical_payload = {"version": 1, "references": [{key: value for key, value in row.items() if key != "source_host"} for row in refs]}
    digest = hashlib.sha256(json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    lines = [
        "# External authority evidence (owner-attested)", "",
        "> This report counts only records committed to the ledger, not all existing web links.",
        '> "Owner-reviewed" means manually classified by a project editor, not independently audited.',
        "> No live crawling, outreach, ranking, or verification authority occurs here.", "",
        f"- Recorded source/target references: **{len(refs)}**",
        f"- Owner-reviewed direct-link claims classified independent: **{len(checked)}**",
        f"- Distinct claimed independent referring hosts: **{len(domains)}**",
        f"- Canonical clusters with such claims: **{len({r['cluster_id'] for r in checked})} of 10**",
        f"- Ledger SHA-256 (canonical JSON): `{digest}`", "",
        "## Coverage by search-intent cluster", "",
        "| Cluster | All records | Owner-reviewed independent direct-link claims |", "| --- | ---: | ---: |",
    ]
    for cluster in clusters:
        cid = cluster["id"]
        lines.append(f"| `{cid}` | {sum(r['cluster_id'] == cid for r in refs)} | {sum(r['cluster_id'] == cid for r in checked)} |")
    lines.extend(["", "## Owner-reviewed direct-link claims", ""])
    if not checked:
        lines.append("None recorded. This does **not** mean there are zero real-world citations or backlinks.")
    else:
        lines.extend(["| First observed | Referring host | Canonical target cluster |", "| --- | --- | --- |"])
        for item in checked:
            lines.append(f"| {item['first_observed']} | `{item['source_host']}` | `{item['cluster_id']}` |")
    lines.extend(["", "## Interpretation", "",
                  "Project-authored and syndicated articles are distribution, not independent authority.",
                  "Unknown or unreviewed references are never counted as reviewed independent direct links.",
                  "Repeated links on one host do not create multiple independent referring hosts.",
                  "No cross-engine citation score, SEO ranking, causal traffic claim, or automatic outreach authority is inferred.",
                  "See [the record ledger](authority-references.json) for the original dated source URLs and classification notes.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=Path("evidence/search-visibility/authority-references.json"))
    parser.add_argument("--topics", type=Path, default=Path("config/seo-topics-v1.json"))
    parser.add_argument("--report", type=Path, default=Path("evidence/search-visibility/AUTHORITY_REPORT.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render(json.loads(args.ledger.read_text(encoding="utf-8")), json.loads(args.topics.read_text(encoding="utf-8")))
    if args.check:
        if not args.report.is_file() or args.report.read_text(encoding="utf-8") != rendered:
            print("authority report is out of date; regenerate without --check")
            return 1
        print("authority reference ledger and report verified")
        return 0
    args.report.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
