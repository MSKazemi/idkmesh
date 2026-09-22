#!/usr/bin/env python3
"""Publish the state of every benchmark cohort as one machine-readable report.

Issue #10 asks for *automated benchmark result publication*. The cohorts are
already contract-checked one at a time by ``tools/benchmark_cohort.py``, but
nothing answers the question a reader actually arrives with: **what has this
benchmark programme measured so far?** Answering it today means opening four
``cohort.json`` files and counting by hand, which is exactly the kind of thing
that goes stale silently.

This module derives the answer instead, and CI re-derives it on every change so
the published copy cannot drift from the cohorts it describes (``--check``).

What it deliberately does not do
--------------------------------

It does not compute a score, a ranking, or a pass rate across cohorts. Five
verified outcomes drawn from a single structural signature are a **baseline**,
not a comparison, and averaging them into a headline number would manufacture a
result the evidence does not support. The report carries the counts, the
signatures they came from, and a statement of what cannot be concluded from
them.

Determinism
-----------

No timestamps and no environment capture: the report is a pure function of the
committed cohorts, so a regeneration on any machine reproduces it byte for byte.
That is what makes ``--check`` a meaningful gate rather than a diff of clocks.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any, Dict, List

try:
    import tools.benchmark_cohort as bc

    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency-free CI legs take this path
    # tools.benchmark_cohort needs jsonschema, which the randomness-lab leg does
    # not install. Importing this module must still succeed there so unittest
    # discovery can collect and skip its tests rather than erroring out.
    bc = None
    JSONSCHEMA_AVAILABLE = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks"
REPORT_PATH = BENCHMARK_DIR / "publication.json"
MARKDOWN_PATH = BENCHMARK_DIR / "PUBLICATION.md"

SCHEMA_VERSION = "0.1"
GENERATOR = "tools/benchmark_publication.py"

#: Cohort stages, ordered from least to most complete, so the summary sorts by
#: progress rather than alphabetically.
STAGE_ORDER = ("scaffold", "collecting", "frozen", "burned")

#: An evidence status that carries a measured outcome. Anything else is a
#: definition without a result behind it.
MEASURED = "verified"


def discover(root: pathlib.Path = BENCHMARK_DIR) -> List[pathlib.Path]:
    """Every cohort definition under ``root``, in a stable order."""
    return sorted(root.glob("*/cohort.json"))


def _outcomes(cohort: Dict[str, Any]) -> Dict[str, Any]:
    outcomes: "collections.Counter[str]" = collections.Counter()
    signatures: "collections.Counter[str]" = collections.Counter()
    attempts = 0
    for task in cohort["tasks"]:
        for attempt in task.get("evidence", {}).get("attempts", []) or []:
            attempts += 1
            outcomes[attempt["outcome"]] += 1
            signature = attempt.get("structural_signature")
            if isinstance(signature, str):
                signatures[signature] += 1
    return {
        "attempts": attempts,
        "by_outcome": dict(sorted(outcomes.items())),
        "by_structural_signature": dict(sorted(signatures.items())),
        "distinct_structural_signatures": len(signatures),
    }


def summarize_cohort(path: pathlib.Path) -> Dict[str, Any]:
    """One cohort, described from its definition and its contract status."""
    cohort = json.loads(path.read_text(encoding="utf-8"))
    tasks = cohort["tasks"]
    families = sorted({task["family"] for task in tasks})
    required = sorted(cohort["required_families"])
    statuses = collections.Counter(
        task.get("evidence", {}).get("status") for task in tasks
    )

    try:
        bc.validate_cohort(cohort)
        contract = {"valid": True, "error": None}
    except bc.CohortError as exc:
        contract = {"valid": False, "error": str(exc)}

    return {
        "id": cohort["id"],
        "title": cohort["title"],
        "path": path.relative_to(ROOT).as_posix(),
        "stage": cohort["stage"],
        "definition_digest": bc.definition_digest(cohort),
        "taxonomy_frozen_before_outcomes": cohort["taxonomy_frozen_before_outcomes"],
        "tasks": len(tasks),
        "minimum_final_tasks": cohort["minimum_final_tasks"],
        "meets_minimum": len(tasks) >= cohort["minimum_final_tasks"],
        "required_families": required,
        "families_present": families,
        "missing_families": sorted(set(required) - set(families)),
        "splits": sorted({task.get("split") for task in tasks if task.get("split")}),
        "evidence_status": dict(sorted(statuses.items())),
        "measured_tasks": statuses.get(MEASURED, 0),
        "negative_cases": sum(1 for task in tasks if task.get("negative_case")),
        "authority": dict(sorted(cohort["authority"].items())),
        "contract": contract,
        "outcomes": _outcomes(cohort),
    }


def _statements(cohorts: List[Dict[str, Any]], totals: Dict[str, Any]) -> List[str]:
    """What a reader is entitled to conclude, and what they are not."""
    statements: List[str] = []
    measured = [c for c in cohorts if c["measured_tasks"]]
    if not measured:
        statements.append(
            "No cohort carries a measured outcome. Every task here is a frozen "
            "definition awaiting evidence."
        )
        return statements

    statements.append(
        f"{totals['measured_tasks']} of {totals['tasks']} tasks carry a "
        f"verified outcome, across {len(measured)} of {totals['cohorts']} cohorts."
    )
    signatures = set()
    for cohort in measured:
        signatures.update(cohort["outcomes"]["by_structural_signature"])
    if len(signatures) <= 1:
        only = next(iter(signatures), "none")
        statements.append(
            f"Every measured attempt comes from a single structural signature "
            f"({only}). These are baseline observations, not a comparison: no "
            f"diversity, replication or error-correlation claim can be drawn "
            f"from them, because there is nothing to compare against."
        )
    outcomes = collections.Counter()
    for cohort in measured:
        outcomes.update(cohort["outcomes"]["by_outcome"])
    if len(outcomes) == 1:
        only = next(iter(outcomes))
        statements.append(
            f"Every measured attempt resolved to '{only}'. A benchmark on which "
            f"nothing has yet failed has not been shown to discriminate."
        )
    return statements


def publication(root: pathlib.Path = BENCHMARK_DIR) -> Dict[str, Any]:
    cohorts = [summarize_cohort(path) for path in discover(root)]
    cohorts.sort(
        key=lambda c: (
            STAGE_ORDER.index(c["stage"]) if c["stage"] in STAGE_ORDER else -1,
            c["id"],
        )
    )
    by_stage: "collections.Counter[str]" = collections.Counter(
        c["stage"] for c in cohorts
    )
    totals = {
        "cohorts": len(cohorts),
        "tasks": sum(c["tasks"] for c in cohorts),
        "measured_tasks": sum(c["measured_tasks"] for c in cohorts),
        "attempts": sum(c["outcomes"]["attempts"] for c in cohorts),
        "contract_valid": sum(1 for c in cohorts if c["contract"]["valid"]),
        "by_stage": dict(sorted(by_stage.items())),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "totals": totals,
        "statements": _statements(cohorts, totals),
        "cohorts": cohorts,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    totals = report["totals"]
    lines: List[str] = [
        "# Benchmark cohort publication",
        "",
        "<!-- Generated by tools/benchmark_publication.py. Do not edit by hand:",
        "     CI regenerates this file and fails if it differs. -->",
        "",
        f"**{totals['cohorts']} cohorts · {totals['tasks']} tasks · "
        f"{totals['measured_tasks']} with a verified outcome · "
        f"{totals['attempts']} attempts**",
        "",
        "## What this shows",
        "",
    ]
    for statement in report["statements"]:
        lines.append(f"- {statement}")
    lines += [
        "",
        "## Cohorts",
        "",
        "| Cohort | Stage | Tasks | Verified | Attempts | Contract |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for cohort in report["cohorts"]:
        contract = "ok" if cohort["contract"]["valid"] else "**invalid**"
        lines.append(
            f"| [`{cohort['id']}`]({pathlib.Path(cohort['path']).parent.name}/) "
            f"| {cohort['stage']} | {cohort['tasks']} | {cohort['measured_tasks']} "
            f"| {cohort['outcomes']['attempts']} | {contract} |"
        )
    lines += ["", "## Detail", ""]
    for cohort in report["cohorts"]:
        lines += [
            f"### {cohort['id']}",
            "",
            f"{cohort['title']}",
            "",
            f"- Stage: `{cohort['stage']}`",
            f"- Definition digest: `{cohort['definition_digest']}`",
            f"- Tasks: {cohort['tasks']} (minimum {cohort['minimum_final_tasks']}, "
            f"met: {str(cohort['meets_minimum']).lower()})",
            f"- Families: {', '.join(f'`{f}`' for f in cohort['families_present'])}",
            f"- Evidence status: "
            + ", ".join(f"{k} {v}" for k, v in cohort["evidence_status"].items()),
        ]
        signatures = cohort["outcomes"]["by_structural_signature"]
        if signatures:
            lines.append(
                "- Structural signatures: "
                + ", ".join(f"`{k}` ×{v}" for k, v in signatures.items())
            )
        outcomes = cohort["outcomes"]["by_outcome"]
        if outcomes:
            lines.append(
                "- Outcomes: " + ", ".join(f"{k} {v}" for k, v in outcomes.items())
            )
        if cohort["missing_families"]:
            lines.append(
                "- **Missing required families**: "
                + ", ".join(f"`{f}`" for f in cohort["missing_families"])
            )
        if not cohort["contract"]["valid"]:
            lines.append(f"- **Contract error**: {cohort['contract']['error']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _serialize(report: Dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and exit non-zero if the committed files differ",
    )
    parser.add_argument("--output", type=str, default=str(REPORT_PATH))
    parser.add_argument("--markdown", type=str, default=str(MARKDOWN_PATH))
    parser.add_argument(
        "--stdout", action="store_true", help="print the report instead of writing it"
    )
    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    args = parse_args(argv)
    report = publication()
    payload = _serialize(report)
    markdown = render_markdown(report)

    if args.stdout:
        sys.stdout.write(payload)
        return 0

    json_path = pathlib.Path(args.output)
    md_path = pathlib.Path(args.markdown)

    if args.check:
        drift: List[str] = []
        for path, expected in ((json_path, payload), (md_path, markdown)):
            if not path.exists():
                drift.append(f"{path} is missing")
            elif path.read_text(encoding="utf-8") != expected:
                drift.append(f"{path} is out of date")
        if drift:
            for line in drift:
                print(f"benchmark publication: {line}", file=sys.stderr)
            print(
                "Regenerate with: PYTHONPATH=. python tools/benchmark_publication.py",
                file=sys.stderr,
            )
            return 1
        print("benchmark publication is up to date")
        return 0

    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    print(f"wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
