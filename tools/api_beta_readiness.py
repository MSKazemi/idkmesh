#!/usr/bin/env python3
"""API v1 beta release gate: required evidence, item by item (issue #747).

Issue 747 says "API v1 beta" must name a reproducible tagged contract and a
qualification report, "not simply the existence of endpoints". It lists the
evidence a release needs. This tool is that list, evaluated:

* every required item has a declared status -- ``satisfied``, ``partial`` or
  ``unmet`` -- a one-line statement of what is still missing when it is not
  satisfied, and the repository files that back the claim;
* the evidence files are **verified to exist**, so a renamed or deleted
  document turns its item ``unverified`` instead of silently staying green;
* items that the API release qualification run measures (``make qualify-api``)
  are not taken on faith: they read ``results/api-qualification/report.json``
  and are only ``satisfied`` when the relevant checks in that report passed,
  and the report is for the current git revision;
* the tagged-revision item is checked against git: ``HEAD`` must be exactly
  tagged ``api-v1-beta*`` and the tree clean.

The declared statuses are claims a maintainer edits in the same change that
closes a gap; the tests pin that a ``satisfied`` item has evidence and no
recorded gap, and that the item list still matches the issue. The tool never
tags or publishes anything.

Exit codes: 0 ready (or ``--no-fail``), 1 at least one item is not satisfied,
2 the check could not run.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "idkmesh-api-beta-readiness/v1"
QUALIFICATION_REPORT = Path("results/api-qualification/report.json")
TAG_PREFIX = "api-v1-beta"

SATISFIED, PARTIAL, UNMET, UNVERIFIED = "satisfied", "partial", "unmet", "unverified"


@dataclass(frozen=True)
class Item:
    id: str
    requirement: str
    declared: str
    evidence: tuple[str, ...] = ()
    gap: str = ""
    #: Groups of qualification checks that must all pass for this item.
    qualification_groups: tuple[str, ...] = ()
    #: Special evaluator name (``git_tag``) for items git alone can decide.
    probe: str = ""


# The wording follows the "Required release evidence" list of issue 747.
ITEMS: tuple[Item, ...] = (
    Item(
        "tagged-revision",
        "exact tagged source revision",
        UNMET,
        gap=f"no `{TAG_PREFIX}*` tag exists on a clean HEAD; tag only after every other item is satisfied",
        probe="git_tag",
    ),
    Item(
        "surface-inventory",
        "API surface inventory",
        SATISFIED,
        evidence=("docs/planning/API_V1_SURFACE_CATALOG_2026-09-23.md", "openapi.yaml"),
    ),
    Item(
        "schemas-frozen",
        "all promised objects schema-frozen",
        PARTIAL,
        evidence=("schemas/README.md", "tools/openapi_ref_check.py"),
        gap="Human Decision and decisions/attempts sub-resources are promised but unbuilt (issue 740)",
        qualification_groups=("contract",),
    ),
    Item(
        "conformance",
        "OpenAPI / runtime / schema conformance green",
        SATISFIED,
        evidence=("tests/test_api_contract_conformance.py", "tests/test_openapi_document.py"),
        qualification_groups=("contract",),
    ),
    Item(
        "compatibility-report",
        "compatibility report",
        SATISFIED,
        evidence=("tools/schema_compat_check.py", "tools/api_release_qualification.py"),
        qualification_groups=("contract",),
    ),
    Item(
        "security-profile",
        "security profile declared",
        PARTIAL,
        evidence=(
            "docs/specifications/CONTROL_TOWER_LOCAL_API_V0_1.md",
            "tests/test_api_security_matrix.py",
        ),
        gap="loopback single-token profile only; the network/multi-user profile is undefined (issue 743)",
        qualification_groups=("security",),
    ),
    Item(
        "authority-matrix",
        "identity / authority matrix documented",
        PARTIAL,
        evidence=("docs/specifications/ENTERPRISE_AUTHORIZATION_V0_1.md",),
        gap="no API-level matrix mapping endpoints to principals and permissions (issues 670, 743)",
    ),
    Item(
        "idempotency",
        "mutation idempotency evidence where applicable",
        SATISFIED,
        evidence=(
            "tests/test_product_spine_idempotency.py",
            "tests/test_api_state_idempotency_properties.py",
        ),
    ),
    Item(
        "persistence",
        "persistence / replay semantics documented",
        SATISFIED,
        evidence=(
            "docs/specifications/API_STORAGE_PROFILES_V0_1.md",
            "tests/test_api_storage_integrity.py",
        ),
    ),
    Item(
        "reliability",
        "reliability / load qualification",
        SATISFIED,
        evidence=("tools/api_load_soak.py", "tests/test_control_tower_limits.py"),
        qualification_groups=("reliability", "fuzz"),
    ),
    Item(
        "slo-observability",
        "SLO / observability proof",
        SATISFIED,
        evidence=("docs/specifications/API_OBSERVABILITY_V0_1.md", "tests/test_api_observability.py"),
    ),
    Item(
        "sdk-docs",
        "SDK and docs published",
        PARTIAL,
        evidence=("idkmesh/api_client.py", "tests/test_api_client.py"),
        gap="Python client exists but is unpublished (issue 769); the typed web client is not built (issue 746)",
        qualification_groups=("client",),
    ),
    Item(
        "deprecation-policy",
        "migration / deprecation policy published",
        PARTIAL,
        evidence=("docs/specifications/API_CONVENTIONS_V0_1.md",),
        gap="deprecation rules exist (conventions section 20); no published migration guide for a beta consumer",
    ),
    Item(
        "clean-install-demo",
        "clean install and reproducible demo",
        SATISFIED,
        evidence=("tools/api_clean_install_demo.py", "docs/RUN_LIFECYCLE_TUTORIAL.md"),
        qualification_groups=("install",),
    ),
)

RELEASE_NOTE_MUST_STATE = (
    "what is stable",
    "what remains experimental",
    "localhost versus multi-user support",
    "authority limitations",
    "known limits and unsupported operations",
)


@dataclass
class Result:
    item: Item
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.item.id,
            "requirement": self.item.requirement,
            "status": self.status,
            "declared": self.item.declared,
            "gap": self.item.gap,
            "reasons": self.reasons,
            "evidence": list(self.item.evidence),
        }


Runner = Callable[[Sequence[str], Path], str | None]


def _git(argv: Sequence[str], root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *argv], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def load_qualification(root: Path) -> dict | None:
    path = root / QUALIFICATION_REPORT
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _qualification_reasons(report: dict | None, groups: Sequence[str], head: str | None) -> list[str]:
    """Why the qualification report does not back a group (empty means it does)."""
    if report is None:
        return [f"no qualification report; run `make qualify-api` ({', '.join(groups)})"]
    reasons = []
    if head and report.get("git_revision") != head:
        reasons.append("qualification report is for a different git revision")
    if report.get("git_dirty"):
        reasons.append("qualification report was taken on a dirty tree")
    checks = report.get("checks") or []
    for group in groups:
        members = [c for c in checks if c.get("group") == group]
        if not members:
            reasons.append(f"qualification report has no `{group}` checks")
        elif any(c.get("status") != "passed" for c in members):
            bad = [c.get("id") for c in members if c.get("status") != "passed"]
            reasons.append(f"`{group}` checks not passed: {', '.join(map(str, bad))}")
    return reasons


def evaluate(
    root: Path,
    items: Sequence[Item] = ITEMS,
    git: Runner = _git,
) -> list[Result]:
    head = git(["rev-parse", "HEAD"], root)
    report = load_qualification(root)
    results: list[Result] = []
    for item in items:
        reasons: list[str] = []
        missing = [path for path in item.evidence if not (root / path).exists()]
        if missing:
            results.append(
                Result(item, UNVERIFIED, [f"evidence not found: {', '.join(missing)}"])
            )
            continue
        status = item.declared
        if item.probe == "git_tag":
            tags = (git(["tag", "--points-at", "HEAD"], root) or "").split()
            beta = [tag for tag in tags if tag.startswith(TAG_PREFIX)]
            dirty = bool(git(["status", "--porcelain"], root))
            if beta and not dirty:
                status = SATISFIED
            else:
                reasons.append(
                    f"HEAD has no `{TAG_PREFIX}*` tag" if not beta else "working tree is dirty"
                )
        if item.qualification_groups and status == SATISFIED:
            problems = _qualification_reasons(report, item.qualification_groups, head)
            if problems:
                status = UNVERIFIED
                reasons.extend(problems)
        if status != SATISFIED and item.gap:
            reasons.append(item.gap)
        results.append(Result(item, status, reasons))
    return results


def verdict(results: Sequence[Result]) -> str:
    return "ready" if all(r.status == SATISFIED for r in results) else "not ready"


def render(results: Sequence[Result]) -> str:
    lines = [f"API v1 beta readiness: {verdict(results).upper()}"]
    for r in results:
        lines.append(f"  {r.status:<10} {r.item.id:<22} {r.item.requirement}")
        lines.extend(f"             - {reason}" for reason in r.reasons)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    lines.append("  totals: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    lines.append(
        "  the release note must state: " + "; ".join(RELEASE_NOTE_MUST_STATE)
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument(
        "--no-fail", action="store_true", help="exit 0 even when the release is not ready"
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / "tools").is_dir():
        print(f"error: {root} does not look like the repository root", file=sys.stderr)
        return 2
    results = evaluate(root)
    if args.json:
        print(
            json.dumps(
                {
                    "schema": REPORT_SCHEMA,
                    "verdict": verdict(results),
                    "items": [r.to_dict() for r in results],
                    "release_note_must_state": list(RELEASE_NOTE_MUST_STATE),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render(results))
    return 0 if args.no_fail or verdict(results) == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
