#!/usr/bin/env python3
"""Standing freshness and source-liveness audit for the free-resource registry.

``scripts/free_resource_planner.py`` already rejects an offer whose evidence has
aged past its own ``source.max_age_days``. That check only runs when somebody
asks the planner to plan a task, and it is purely arithmetic on
``source.checked_at``. This tool adds the two things that arithmetic cannot do:

1. a standing report, so an offer that is about to expire is visible BEFORE a
   planning run silently drops it;
2. an opt-in liveness probe of each ``source.url``.

Contract boundary. This tool is read-only. It never rewrites the registry,
refreshes ``checked_at``, dispatches work, grants worker authority, or selects a
compute offer. A stale or unreachable offer is a finding for a human to act on,
not something this tool may repair. Re-dating an offer without re-reading its
terms is precisely the failure the registry's ``max_age_days`` exists to prevent.

Honest limitation of ``--check-sources``: an HTTP probe detects a DEAD link, not
a CHANGED policy. A provider that silently cuts a free quota, or a page that
still returns 200 while announcing its own retirement, is invisible here. Only a
human re-reading the page can refresh ``checked_at``. Treat a reachable source as
"the citation still resolves", never as "the terms still hold".
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "examples/resources/free-resource-registry-v0.1.json"
PLANNER = ROOT / "scripts/free_resource_planner.py"

FRESH = "fresh"
EXPIRING = "expiring"
STALE = "stale"

UNCHECKED = "unchecked"
REACHABLE = "reachable"
UNREACHABLE = "unreachable"

USER_AGENT = "idkmesh-free-resource-source-audit/0.1 (+https://github.com/MSKazemi/idkmesh)"


def _load_planner() -> Any:
    """Reuse the planner's registry validator instead of duplicating it."""
    spec = importlib.util.spec_from_file_location("free_resource_planner", PLANNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _parse_date(raw: str) -> dt.date:
    return dt.date.fromisoformat(raw)


def classify(age_days: int, max_age_days: int, warn_days: int) -> str:
    """Bucket one offer by how much of its evidence window is left."""
    remaining = max_age_days - age_days
    if remaining < 0:
        return STALE
    if remaining <= warn_days:
        return EXPIRING
    return FRESH


def probe_source(url: str, timeout: float) -> dict[str, Any]:
    """Best-effort liveness probe. Never raises; a failure IS the finding."""
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
        return {"liveness": REACHABLE, "http_status": status, "error": None}
    except urllib.error.HTTPError as exc:
        return {"liveness": UNREACHABLE, "http_status": int(exc.code), "error": f"HTTP {exc.code}"}
    except Exception as exc:  # network, DNS, TLS, timeout, malformed URL
        return {"liveness": UNREACHABLE, "http_status": None, "error": type(exc).__name__}


def audit(
    registry: dict[str, Any],
    *,
    as_of: dt.date,
    warn_days: int,
    check_sources: bool = False,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Produce a deterministic freshness report over every registry offer."""
    offers: list[dict[str, Any]] = []
    for offer in registry["offers"]:
        source = offer["source"]
        checked_at = _parse_date(source["checked_at"])
        max_age_days = int(source["max_age_days"])
        age_days = (as_of - checked_at).days
        record: dict[str, Any] = {
            "id": offer["id"],
            "status": offer["status"],
            "checked_at": source["checked_at"],
            "max_age_days": max_age_days,
            "age_days": age_days,
            "days_until_expiry": max_age_days - age_days,
            "expires_on": (checked_at + dt.timedelta(days=max_age_days)).isoformat(),
            "freshness": classify(age_days, max_age_days, warn_days),
            "url": source["url"],
            "liveness": UNCHECKED,
            "http_status": None,
            "error": None,
        }
        if check_sources:
            record.update(probe_source(source["url"], timeout))
        offers.append(record)

    counts = {level: sum(1 for o in offers if o["freshness"] == level) for level in (FRESH, EXPIRING, STALE)}
    unreachable = [o["id"] for o in offers if o["liveness"] == UNREACHABLE]
    return {
        "schema_version": "0.1",
        "tool": "free-resource-source-audit",
        "as_of": as_of.isoformat(),
        "registry_observed_at": registry["observed_at"],
        "warn_days": warn_days,
        "sources_checked": bool(check_sources),
        "offer_count": len(offers),
        "counts": counts,
        "unreachable_ids": sorted(unreachable),
        "offers": sorted(offers, key=lambda o: (o["days_until_expiry"], o["id"])),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"free-resource source audit  as_of={report['as_of']}  "
        f"registry_observed_at={report['registry_observed_at']}",
        f"offers={report['offer_count']}  fresh={report['counts'][FRESH]}  "
        f"expiring={report['counts'][EXPIRING]}  stale={report['counts'][STALE]}",
        "",
    ]
    for offer in report["offers"]:
        marker = {FRESH: "ok  ", EXPIRING: "WARN", STALE: "STALE"}[offer["freshness"]]
        liveness = "" if offer["liveness"] == UNCHECKED else f"  source={offer['liveness']}"
        if offer["error"]:
            liveness += f" ({offer['error']})"
        lines.append(
            f"{marker:5s} {offer['id']:38s} expires {offer['expires_on']} "
            f"({offer['days_until_expiry']:+d}d){liveness}"
        )
    return "\n".join(lines)


def _self_test() -> int:
    """Exercise the classifier and the report shape without touching the network."""
    assert classify(0, 30, 7) == FRESH
    assert classify(22, 30, 7) == FRESH
    assert classify(23, 30, 7) == EXPIRING, "boundary: exactly warn_days left is EXPIRING"
    assert classify(30, 30, 7) == EXPIRING, "boundary: last valid day is not yet stale"
    assert classify(31, 30, 7) == STALE, "boundary: one day past the window is STALE"

    registry = {
        "version": 1,
        "observed_at": "2026-01-01",
        "offers": [
            {
                "id": "synthetic-stale",
                "status": "available",
                "source": {"url": "https://example.invalid/a", "checked_at": "2026-01-01", "max_age_days": 10},
            },
            {
                "id": "synthetic-fresh",
                "status": "available",
                "source": {"url": "https://example.invalid/b", "checked_at": "2026-01-01", "max_age_days": 90},
            },
        ],
    }
    report = audit(registry, as_of=dt.date(2026, 2, 1), warn_days=7)
    assert report["counts"] == {FRESH: 1, EXPIRING: 0, STALE: 1}, report["counts"]
    assert report["offers"][0]["id"] == "synthetic-stale", "stalest offer must sort first"
    assert report["offers"][0]["days_until_expiry"] == -21, report["offers"][0]
    assert report["sources_checked"] is False
    assert all(o["liveness"] == UNCHECKED for o in report["offers"])
    print("OK: free_resource_source_audit self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("registry", nargs="?", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--as-of", default=None, help="ISO date; defaults to UTC today")
    parser.add_argument(
        "--warn-days",
        type=int,
        default=7,
        help="days of remaining evidence window at or below which an offer is 'expiring'",
    )
    parser.add_argument(
        "--check-sources",
        action="store_true",
        help="probe each source URL for liveness (requires network; off by default so the audit stays hermetic)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="per-source probe timeout in seconds")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument(
        "--fail-on",
        choices=("never", "stale", "expiring"),
        default="stale",
        help="exit non-zero when an offer at or past this level is present",
    )
    parser.add_argument(
        "--fail-on-unreachable",
        action="store_true",
        help="also exit non-zero when a source URL did not resolve (requires --check-sources)",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if args.warn_days < 0:
        parser.error("--warn-days must be >= 0")

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    _load_planner().validate_registry(registry)

    as_of = _parse_date(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc).date()
    report = audit(
        registry,
        as_of=as_of,
        warn_days=args.warn_days,
        check_sources=args.check_sources,
        timeout=args.timeout,
    )

    print(json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else render_text(report))

    exit_code = 0
    if args.fail_on != "never":
        triggering = {STALE} if args.fail_on == "stale" else {STALE, EXPIRING}
        if any(offer["freshness"] in triggering for offer in report["offers"]):
            exit_code = 1
    # Liveness gets its own switch. A probe failure can be a genuinely dead
    # citation or a transient 403/timeout from a docs host, so a scheduled audit
    # reports it without going red; a human re-checking the registry opts in.
    if args.fail_on_unreachable and report["unreachable_ids"]:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
