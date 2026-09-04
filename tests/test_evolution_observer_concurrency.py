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

Deliberately text-based rather than YAML-parsed: the PR Gate installs only
`pytest` and `requirements-phase0.txt` (jsonschema alone), so `import yaml` would
pass locally and fail in the gate. That is the same constraint recorded in
tests/test_workflow_ci_hygiene.py, and it is why every `concurrency:` block this
file reads is written on single lines.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


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
    ("collaboration-observables.yml", "collaboration-observables"),
    # push, pull_request_target, pull_request, issues, schedule. This is the same
    # defect as the one fixed here, and the same file already keys its other job
    # per pull request, so the pattern is known to its author.
    ("repository-math-portfolio.yml", "repository-math-portfolio-observer"),
}

_BLOCK = re.compile(
    r"^(?P<indent>[ ]*)concurrency:\s*$(?P<body>(?:\n(?:[ ]*#[^\n]*|(?P=indent)[ ]+[^\n]*|[ ]*))*)",
    re.MULTILINE,
)
_GROUP = re.compile(r"^\s*group:\s*(?P<value>.+?)\s*$", re.MULTILINE)
_CANCEL = re.compile(r"^\s*cancel-in-progress:\s*(?P<value>.+?)\s*$", re.MULTILINE)


def concurrency_blocks(text: str) -> list[tuple[str, str]]:
    """(group, cancel-in-progress) for every `concurrency:` block in a workflow."""
    blocks = []
    for match in _BLOCK.finditer(text):
        body = match.group("body")
        group = _GROUP.search(body)
        cancel = _CANCEL.search(body)
        if group:
            blocks.append(
                (group.group("value"), cancel.group("value") if cancel else "")
            )
    return blocks


def _cancels(cancel_value: str) -> bool:
    # A `${{ ... }}` expression cancels for at least one event, so it counts.
    return cancel_value.strip() == "true" or "${{" in cancel_value


def _keyed(group: str) -> bool:
    return any(key in group for key in PER_RUN_KEYS)


def unkeyed_cancelling() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for group, cancel in concurrency_blocks(text):
            if _cancels(cancel) and not _keyed(group):
                found.add((path.name, group))
    return found


def observe_group() -> str:
    text = EVOLUTION_LOOP.read_text(encoding="utf-8")
    groups = [g for g, _ in concurrency_blocks(text) if "evolution-observer" in g]
    if len(groups) != 1:
        raise AssertionError(f"expected one evolution-observer group, got {groups}")
    return groups[0]


class ParserSelfTests(unittest.TestCase):
    """The scan must not pass by finding nothing."""

    def test_the_parser_finds_concurrency_blocks(self) -> None:
        total = sum(
            len(concurrency_blocks(p.read_text(encoding="utf-8")))
            for p in WORKFLOWS.glob("*.yml")
        )
        # A regex that silently matched nothing would make every check below
        # vacuously true, so pin a floor well under the current count.
        self.assertGreater(total, 5)

    def test_the_parser_reads_group_and_cancel_together(self) -> None:
        blocks = concurrency_blocks(
            "concurrency:\n"
            "  group: example-${{ github.ref }}\n"
            "  cancel-in-progress: true\n"
        )
        self.assertEqual(blocks, [("example-${{ github.ref }}", "true")])


class AdvisoryObserverConcurrencyTests(unittest.TestCase):
    """The specific fix for #387."""

    def test_the_observe_group_cancels(self) -> None:
        # If this ever stops cancelling, the per-pull-request key below is no
        # longer load-bearing and this whole test should be re-read.
        text = EVOLUTION_LOOP.read_text(encoding="utf-8")
        cancels = [
            c for g, c in concurrency_blocks(text) if "evolution-observer" in g
        ]
        self.assertEqual(len(cancels), 1)
        self.assertTrue(_cancels(cancels[0]))

    def test_the_advisory_side_is_keyed_per_pull_request(self) -> None:
        group = observe_group()
        self.assertIn("advisory", group)
        self.assertIn("github.event.pull_request.number", group)

    def test_the_canonical_side_stays_a_single_lineage(self) -> None:
        # Artifact-backed Bayesian state must have one successor lineage, so the
        # canonical branch must NOT gain a per-run key. Keying it would let two
        # main-push observations fork the checkpoint chain.
        canonical = observe_group().split("||", 1)[1]
        self.assertIn("canonical", canonical)
        for key in PER_RUN_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, canonical)


class CancellingGroupsAreKeyedTests(unittest.TestCase):
    """The general rule, with the pre-existing instances pinned."""

    def test_no_new_unkeyed_cancelling_group_appears(self) -> None:
        unexpected = unkeyed_cancelling() - KNOWN_UNKEYED_CANCELLING
        self.assertEqual(
            unexpected,
            set(),
            "a concurrency group that cancels must contain something that varies "
            "per run, or it cancels unrelated runs; see issue #387",
        )

    def test_the_known_list_has_no_stale_entries(self) -> None:
        # A fixed instance must be removed from the list, so the list keeps
        # meaning what it says rather than decaying into folklore.
        self.assertEqual(KNOWN_UNKEYED_CANCELLING - unkeyed_cancelling(), set())

    def test_the_evolution_observer_is_no_longer_among_them(self) -> None:
        offenders = {group for name, group in unkeyed_cancelling()}
        self.assertNotIn(observe_group(), offenders)


if __name__ == "__main__":
    unittest.main()
