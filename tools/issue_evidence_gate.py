#!/usr/bin/env python3
"""Machine-check the preconditions that open research issues declare for themselves.

Several IDKMesh issues cannot be closed by writing code, because their own
acceptance text names a precondition that is a *measured property of the
repository* rather than a task: a held-out corpus that has to be collected, an
independent reviewer who has to appear, a contributor who has to come back.

Triage notes asserting "blocked" rot silently. This tool reads the evidence
surfaces the repository already publishes and reports, per issue, whether the
precondition it names is met -- so the claim is falsifiable and re-derived on
every run rather than trusted.

Evidence surfaces, all committed and all produced by other tools:

* ``randomness_lab.r1_readiness`` over every ``benchmarks/*/cohort.json`` --
  the preregistered fail-closed audit for a real R1 replay corpus.
* the newest ``results/collaboration/observables-*.json`` -- production
  collaboration observables (independent-review latency, contributor
  recurrence, ownership concentration, evidence-derived priors).
* ``.github/workflows/*.yml`` -- workflows that store state in an open issue
  body, which makes that issue a live state store rather than a task.

**This tool never decides that an issue is blocked.** It evaluates a registry of
preconditions that were each read off the issue's own text, and it fails when a
registered precondition has become *met* -- i.e. when the registry has gone
stale and an issue is actionable again. An unmet precondition is reported, not
an error; that is the steady state.

Issues with no registered precondition are reported as ``unclassified``. That is
deliberate: absence of a mechanical precondition is not evidence of blocking.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTRACT = "idkmesh-issue-evidence-gate-v0.1"

#: Minimum eligible work units the R1 preregistration requires. Read from each
#: cohort's own audit rather than hard-coded, with this only as a fallback.
DEFAULT_MINIMUM_WORK_UNITS = 20


# --------------------------------------------------------------------------
# evidence surfaces
# --------------------------------------------------------------------------

def _newest_observables(root: Path) -> Path | None:
    candidates = sorted((root / "results" / "collaboration").glob("observables-*.json"))
    return candidates[-1] if candidates else None


def collaboration_evidence(root: Path) -> Dict[str, Any]:
    """Read the newest published collaboration observables.

    Returns ``available: False`` rather than raising when no snapshot exists, so
    a fresh clone reports "cannot tell" instead of "not blocked".
    """
    path = _newest_observables(root)
    if path is None:
        return {"available": False, "source": None}
    report = json.loads(path.read_text())
    metrics = report.get("metrics", {})
    review = metrics.get("first_independent_review_latency", {})
    recurrence = metrics.get("contributor_recurrence", {})
    ownership = metrics.get("ownership_concentration", {})
    return {
        "available": True,
        "source": str(path.relative_to(root)),
        "independent_review_samples": int(review.get("samples", 0)),
        "closed_without_review": int(review.get("closed_without_review", 0)),
        "contributor_recurrence_trials": int(recurrence.get("trials", 0)),
        "distinct_actors": int(ownership.get("distinct_actors", 0)),
        "evidence_derived_strategy_priors": len(
            report.get("evidence_derived_strategy_priors", []) or []
        ),
    }


def corpus_evidence(root: Path, python: str | None = None) -> Dict[str, Any]:
    """Run the frozen R1 readiness audit over every cohort in the repository.

    The audit is authoritative here; this function only takes the best cohort,
    because one ready cohort is enough to unblock the issues that need one.
    """
    python = python or sys.executable
    cohorts = sorted((root / "benchmarks").glob("*/cohort.json"))
    rows: List[Dict[str, Any]] = []
    for cohort in cohorts:
        completed = subprocess.run(
            [python, "-m", "randomness_lab.r1_readiness",
             "--cohort", str(cohort.relative_to(root)),
             "--baseline-signature", "replication",
             "--diversity-signature", "replication",
             "--diversity-signature", "structural"],
            cwd=root, capture_output=True, text=True,
            env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        )
        if completed.returncode != 0 and not completed.stdout.strip():
            rows.append({"cohort": str(cohort.relative_to(root)),
                         "status": "audit_failed",
                         "stderr": completed.stderr.strip()[:400]})
            continue
        report = json.loads(completed.stdout)
        rows.append({
            "cohort": report.get("cohort_id", str(cohort.relative_to(root))),
            "status": report.get("status"),
            "eligible_work_units": report["coverage"]["eligible_work_units"],
            "cohort_tasks": report["coverage"]["cohort_tasks"],
            "minimum_required": report["configuration"].get(
                "minimum_eligible_work_units", DEFAULT_MINIMUM_WORK_UNITS),
            "supports_empirical_r1_claim": report.get("supports_empirical_r1_claim"),
        })
    eligible = [r.get("eligible_work_units", 0) for r in rows]
    minimums = [r.get("minimum_required", DEFAULT_MINIMUM_WORK_UNITS)
                for r in rows if "minimum_required" in r]
    return {
        "available": bool(rows),
        "cohorts": rows,
        "best_eligible_work_units": max(eligible) if eligible else 0,
        "minimum_required": min(minimums) if minimums else DEFAULT_MINIMUM_WORK_UNITS,
    }


ISSUE_STATE_WRITE = re.compile(r"issues\.update\s*\(")
ISSUE_NUMBER_LITERAL = re.compile(r"issue_number:\s*(\d+)")


def workflow_evidence(root: Path) -> Dict[str, Any]:
    """Find workflows that treat an open issue as a state store.

    An issue whose body a workflow writes to is live infrastructure: closing it
    does not complete work, it removes a running system's storage.
    """
    writers: List[str] = []
    literals: Dict[str, List[int]] = {}
    for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text()
        name = workflow.name
        if ISSUE_STATE_WRITE.search(text):
            writers.append(name)
        found = sorted({int(m) for m in ISSUE_NUMBER_LITERAL.findall(text)})
        if found:
            literals[name] = found
    return {
        "available": True,
        "state_writing_workflows": writers,
        "hard_coded_issue_numbers": literals,
        "referenced_issue_numbers": sorted({n for v in literals.values() for n in v}),
    }


def node_evidence(root: Path) -> Dict[str, Any]:
    return {"available": True, "node_directory_present": (root / "node").is_dir()}


# --------------------------------------------------------------------------
# preconditions
# --------------------------------------------------------------------------

def _p_real_corpus(ev: Dict[str, Any]) -> Dict[str, Any]:
    corpus = ev["corpus"]
    required = corpus["minimum_required"]
    observed = corpus["best_eligible_work_units"]
    return {
        "code": "eligible_held_out_work_units",
        "observed": observed,
        "required": f">= {required}",
        "met": observed >= required,
        "source": "randomness_lab.r1_readiness over benchmarks/*/cohort.json",
    }


def _p_independent_review(ev: Dict[str, Any]) -> Dict[str, Any]:
    collab = ev["collaboration"]
    observed = collab.get("independent_review_samples", 0) if collab["available"] else None
    return {
        "code": "independent_reviews_exist",
        "observed": observed,
        "required": ">= 1",
        "met": bool(observed),
        "source": collab.get("source"),
    }


def _p_recurring_contributors(ev: Dict[str, Any]) -> Dict[str, Any]:
    collab = ev["collaboration"]
    observed = collab.get("contributor_recurrence_trials", 0) if collab["available"] else None
    return {
        "code": "recurring_contributor_trials",
        "observed": observed,
        "required": ">= 1",
        "met": bool(observed),
        "source": collab.get("source"),
    }


def _p_multiple_actors(ev: Dict[str, Any]) -> Dict[str, Any]:
    collab = ev["collaboration"]
    observed = collab.get("distinct_actors", 0) if collab["available"] else None
    return {
        "code": "distinct_actors",
        "observed": observed,
        "required": ">= 2",
        "met": bool(observed and observed >= 2),
        "source": collab.get("source"),
    }


def _p_evidence_priors(ev: Dict[str, Any]) -> Dict[str, Any]:
    collab = ev["collaboration"]
    observed = collab.get("evidence_derived_strategy_priors", 0) if collab["available"] else None
    return {
        "code": "evidence_derived_strategy_priors",
        "observed": observed,
        "required": ">= 1",
        "met": bool(observed),
        "source": collab.get("source"),
    }


def _p_node_directory(ev: Dict[str, Any]) -> Dict[str, Any]:
    present = ev["node"]["node_directory_present"]
    return {
        "code": "canonical_node_directory",
        "observed": present,
        "required": True,
        "met": present,
        "source": "filesystem: node/",
    }


def _p_not_a_state_store(ev: Dict[str, Any]) -> Dict[str, Any]:
    workflows = ev["workflows"]
    writers = workflows["state_writing_workflows"]
    return {
        "code": "no_workflow_stores_state_in_an_issue",
        "observed": writers,
        "required": "no workflow writes issue bodies",
        "met": not writers,
        "source": ".github/workflows/*.yml",
    }


PRECONDITIONS = {
    "real_corpus": _p_real_corpus,
    "independent_review": _p_independent_review,
    "recurring_contributors": _p_recurring_contributors,
    "multiple_actors": _p_multiple_actors,
    "evidence_priors": _p_evidence_priors,
    "node_directory": _p_node_directory,
    "not_a_state_store": _p_not_a_state_store,
}


#: Each entry was read off the issue's own acceptance text or verified in code.
#: ``note`` records where, so a reader can check the mapping rather than trust it.
REGISTRY: Dict[int, Dict[str, Any]] = {
    9: {
        "preconditions": ["recurring_contributors"],
        "note": "title asks for the first 10 recurring contributors; recurrence "
                "is measured, and the measurement currently has no trials.",
    },
    10: {
        "preconditions": ["multiple_actors"],
        "note": "a repository-driven community engine needs a community; "
                "ownership concentration reports a single distinct actor.",
    },
    11: {
        "preconditions": ["node_directory"],
        "note": "activation targets a canonical idkmesh-node that is not in the tree.",
    },
    23: {
        "preconditions": ["not_a_state_store"],
        "note": "ace-community-growth.yml writes ACE_STATE into an open ledger "
                "issue body and ace-cohort-observer.yml reads issue 23 as its "
                "fallback ledger. Closing it removes a running workflow's storage.",
    },
    30: {
        "preconditions": ["real_corpus"],
        "note": "the harness acceptance boxes are ticked; the evidence gate "
                "requires eligible held-out real coding work units.",
    },
    70: {
        "preconditions": ["real_corpus"],
        "note": "collect and publish the first held-out real coding corpus.",
    },
    96: {
        "preconditions": ["real_corpus"],
        "note": "the R3 real-task phase evolves on training tasks and must confirm\n"
                "on a new frozen held-out corpus; no cohort in the tree has one\n"
                "eligible work unit.",
    },
    109: {
        "preconditions": ["not_a_state_store"],
        "note": "the bootstrap cohort observatory is located by scanning open "
                "issues and its ledger body is rewritten in place.",
    },
    138: {
        "preconditions": ["independent_review"],
        "note": "asks for an independent inspection; no pull request in the "
                "production snapshot has an independent review.",
    },
    151: {
        "preconditions": ["independent_review"],
        "note": "asks for an independent audit; same measurement.",
    },
    152: {
        "preconditions": ["independent_review"],
        "note": "gated on issue 167, which is itself an independent review request.",
    },
    167: {
        "preconditions": ["independent_review"],
        "note": "asks an independent reviewer to inspect an orphan cohort.",
    },
    86: {
        "preconditions": ["evidence_priors"],
        "note": "P0 item 4 replaces hand-authored evolution priors with "
                "GitHub-derived evidence; the published priors list is empty. "
                "Items 2 and 5 are already met, so this is a partial gate.",
        "partial": True,
    },
}


def audit(root: Path | None = None, python: str | None = None) -> Dict[str, Any]:
    root = root or REPO_ROOT
    evidence = {
        "collaboration": collaboration_evidence(root),
        "corpus": corpus_evidence(root, python=python),
        "workflows": workflow_evidence(root),
        "node": node_evidence(root),
    }

    issues: Dict[str, Any] = {}
    stale: List[int] = []
    for number, entry in sorted(REGISTRY.items()):
        checks = [PRECONDITIONS[name](evidence) for name in entry["preconditions"]]
        met = all(check["met"] for check in checks)
        issues[str(number)] = {
            "preconditions": checks,
            "all_preconditions_met": met,
            "status": "actionable" if met else "waiting_on_evidence",
            "partial_gate": bool(entry.get("partial")),
            "note": entry["note"],
        }
        if met:
            stale.append(number)

    return {
        "contract": CONTRACT,
        "authority": {
            "decides_whether_an_issue_is_blocked": False,
            "reports_measured_preconditions": True,
        },
        "evidence": evidence,
        "issues": issues,
        "registered_issues": sorted(REGISTRY),
        "newly_actionable": sorted(stale),
        "interpretation": (
            "A precondition that is not met is the expected steady state and is "
            "not an error. A precondition that has become met means the registry "
            "is stale: the issue can be worked now and its entry should be "
            "removed. Issues absent from the registry are unclassified -- no "
            "mechanical precondition was read off their text, which is not "
            "evidence that they are blocked."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="write the report here as JSON")
    parser.add_argument(
        "--require-no-stale-entries", action="store_true",
        help="exit non-zero when a registered precondition has become met",
    )
    args = parser.parse_args(argv)

    report = audit()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n")
    else:
        print(text)

    if args.require_no_stale_entries and report["newly_actionable"]:
        numbers = ", ".join(str(n) for n in report["newly_actionable"])
        print(
            f"stale registry: preconditions are now met for issue(s) {numbers}; "
            "work them or remove their entries",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
