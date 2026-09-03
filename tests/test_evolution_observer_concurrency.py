"""A cancelling concurrency group must be keyed, or it cancels unrelated runs.

`cancel-in-progress: true` on a group whose key is the same for every pull
request means each new run cancels whichever is already running, across pull
requests that have nothing to do with each other. GitHub then renders the
cancelled run as a red check, so a correct pull request shows a failure whose job
log contains nothing but successful steps.

Measured on 2026-09-03 (issue #387): three branches pushed within 13 seconds
produced `cancelled`, `cancelled`, `success` on their advisory observations, in
push order -- last writer wins, which is exactly `cancel-in-progress` semantics.
The `pull_request` runs, keyed per pull request at workflow level, were 7/7 green
over the same period.

The rule enforced here is narrow on purpose: a group that cancels must contain
something that varies per run. It deliberately does *not* require every group to
be keyed -- an unkeyed group that only queues is a legitimate way to serialise
writers, which is what the canonical observer lineage needs.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
EVOLUTION_LOOP = WORKFLOWS / "evolution-loop.yml"

# Anything that differs between two concurrent runs.
PER_RUN_KEYS = (
    "github.ref",
    "github.event.pull_request.number",
    "github.event.number",
    "github.event.workflow_run.head_sha",
    "github.sha",
    "github.run_id",
    "github.head_ref",
)

# Groups that cancel and are not keyed, as of the fix for #387. These are real
# instances of the same defect, left for a separate change rather than widened
# into this one; the point of listing them is that the set cannot grow silently.
# Remove an entry when it is fixed -- a stale entry fails the test below.
KNOWN_UNKEYED_CANCELLING = {
    # workflow_dispatch + schedule only, so no pull request is affected: a manual
    # dispatch can cancel a running scheduled observation.
    ("collaboration-observables.yml", "workflow"),
    # push, pull_request_target, pull_request, issues, schedule. This is the same
    # defect as the one fixed here, and the same file already keys its other job
    # per pull request, so the pattern is known to its author.
    ("repository-math-portfolio.yml", "job:portfolio"),
}


def _concurrency_scopes(document: dict) -> list[tuple[str, dict]]:
    scopes: list[tuple[str, dict]] = []
    top = document.get("concurrency")
    if isinstance(top, dict):
        scopes.append(("workflow", top))
    for name, job in (document.get("jobs") or {}).items():
        if isinstance(job, dict) and isinstance(job.get("concurrency"), dict):
            scopes.append((f"job:{name}", job["concurrency"]))
    return scopes


def _cancels(concurrency: dict) -> bool:
    value = concurrency.get("cancel-in-progress")
    # A `${{ ... }}` expression cancels for at least one event, so it counts.
    return value is True or (isinstance(value, str) and "${{" in value)


def _keyed(group: str) -> bool:
    return any(key in group for key in PER_RUN_KEYS)


def _unkeyed_cancelling() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for scope, concurrency in _concurrency_scopes(document):
            if _cancels(concurrency) and not _keyed(str(concurrency.get("group", ""))):
                found.add((path.name, scope))
    return found


class AdvisoryObserverConcurrencyTests(unittest.TestCase):
    """The specific fix for #387."""

    def setUp(self) -> None:
        self.observe = yaml.safe_load(
            EVOLUTION_LOOP.read_text(encoding="utf-8")
        )["jobs"]["observe"]

    def test_the_observe_group_cancels(self) -> None:
        # If this ever stops cancelling, the per-pull-request key below is no
        # longer load-bearing and this whole test should be re-read.
        self.assertTrue(_cancels(self.observe["concurrency"]))

    def test_the_advisory_side_is_keyed_per_pull_request(self) -> None:
        group = self.observe["concurrency"]["group"]
        self.assertIn("advisory", group)
        self.assertIn("github.event.pull_request.number", group)

    def test_the_canonical_side_stays_a_single_lineage(self) -> None:
        # Artifact-backed Bayesian state must have one successor lineage, so the
        # canonical branch must NOT gain a per-run key. Keying it would let two
        # main-push observations fork the checkpoint chain.
        group = self.observe["concurrency"]["group"]
        canonical = group.split("||", 1)[1]
        self.assertIn("canonical", canonical)
        for key in PER_RUN_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, canonical)


class CancellingGroupsAreKeyedTests(unittest.TestCase):
    """The general rule, with the pre-existing instances pinned."""

    def test_no_new_unkeyed_cancelling_group_appears(self) -> None:
        unexpected = _unkeyed_cancelling() - KNOWN_UNKEYED_CANCELLING
        self.assertEqual(
            unexpected,
            set(),
            "a concurrency group that cancels must contain something that varies "
            "per run, or it cancels unrelated runs; see issue #387",
        )

    def test_the_known_list_has_no_stale_entries(self) -> None:
        # A fixed instance must be removed from the list, so the list keeps
        # meaning what it says rather than decaying into folklore.
        stale = KNOWN_UNKEYED_CANCELLING - _unkeyed_cancelling()
        self.assertEqual(stale, set())

    def test_the_evolution_observer_is_no_longer_among_them(self) -> None:
        self.assertNotIn(
            ("evolution-loop.yml", "job:observe"), _unkeyed_cancelling()
        )


if __name__ == "__main__":
    unittest.main()
