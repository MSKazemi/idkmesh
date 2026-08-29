from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evolution_live_governor as governor  # noqa: E402
import evolution_snapshot  # noqa: E402

POLICY = json.loads((ROOT / "state/evolution-live-policy.json").read_text())


def snapshot(
    *,
    protected: bool = False,
    ready: int = 2,
    draft: int = 1,
    issues: int = 4,
    reviewed: int = 0,
    external: int = 0,
    branches: int = 50,
    pin_ratio: float = 0.5,
) -> dict:
    prs = []
    for number in range(100, 100 + ready):
        prs.append(
            {
                "number": number,
                "draft": False,
                "labels": [],
                "independent_review_count": 1 if reviewed > 0 else 0,
                "independent_approval_count": 0,
            }
        )
        reviewed -= 1
    for number in range(200, 200 + draft):
        prs.append(
            {
                "number": number,
                "draft": True,
                "labels": [],
                "independent_review_count": 0,
                "independent_approval_count": 0,
            }
        )

    open_issues = []
    for number in range(1, 1 + issues):
        labels = (
            ["growth-seed", "good first issue"]
            if number == 1
            else (["research"] if number == 2 else [])
        )
        open_issues.append({"number": number, "labels": labels})

    return {
        "version": 1,
        "integration": {"main_protected": protected},
        "open_pull_requests": prs,
        "open_issues": open_issues,
        "external_participant_count": external,
        "branch_count": branches,
        "workflow_supply_chain": {
            "external_uses": 10,
            "pinned_uses": int(10 * pin_ratio),
            "pin_ratio": pin_ratio,
        },
        "project_memory": {
            "conversation_records": 10,
            "preservation_rule_present": True,
        },
        "collection": {},
    }


class LiveGovernorTests(unittest.TestCase):
    def test_capacity_recovers_when_open_work_decreases(self) -> None:
        low = governor.capacity_metrics(snapshot(ready=1, draft=0, issues=2), POLICY)
        high = governor.capacity_metrics(snapshot(ready=9, draft=4, issues=20), POLICY)
        self.assertGreater(low["capacity"], high["capacity"])
        self.assertLess(low["review_load"], high["review_load"])

    def test_unprotected_repository_is_hard_guard(self) -> None:
        result = governor.evaluate(snapshot(protected=False, ready=1, issues=2), POLICY)
        self.assertEqual(result["mode"], "GUARD")
        self.assertIn("main_unprotected", result["blockers"])
        self.assertFalse(result["authority"]["automatic_merge"])

    def test_independent_review_coverage_is_live_signal(self) -> None:
        result = governor.evaluate(
            snapshot(protected=True, ready=2, issues=1, reviewed=1, pin_ratio=1.0),
            POLICY,
        )
        self.assertAlmostEqual(result["review"]["review_coverage"], 0.5)
        self.assertIn("ready_prs_lack_independent_review", result["blockers"])

    def test_popularity_cannot_change_governor(self) -> None:
        base = snapshot(
            protected=True,
            ready=1,
            issues=2,
            reviewed=1,
            external=1,
            branches=10,
            pin_ratio=1.0,
        )
        altered = json.loads(json.dumps(base))
        altered.update(
            {
                "stars": 10**9,
                "forks": 10**8,
                "raw_comments": 10**9,
                "raw_commits": 10**9,
            }
        )
        self.assertEqual(governor.evaluate(base, POLICY), governor.evaluate(altered, POLICY))

    def test_homeostatic_potential_improves_with_guardrails(self) -> None:
        weak = governor.evaluate(
            snapshot(
                protected=False,
                ready=5,
                issues=10,
                external=0,
                branches=80,
                pin_ratio=0.4,
            ),
            POLICY,
        )
        strong = governor.evaluate(
            snapshot(
                protected=True,
                ready=1,
                issues=2,
                reviewed=1,
                external=2,
                branches=10,
                pin_ratio=1.0,
            ),
            POLICY,
        )
        self.assertLess(strong["homeostatic_potential"], weak["homeostatic_potential"])

    def test_workflow_pin_scan_distinguishes_floating_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "x.yml").write_text(
                "steps:\n"
                "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
                "  - uses: actions/setup-python@v7\n",
                encoding="utf-8",
            )
            result = evolution_snapshot.scan_workflow_pins(root)
            self.assertEqual(result["external_uses"], 2)
            self.assertEqual(result["pinned_uses"], 1)
            self.assertAlmostEqual(result["pin_ratio"], 0.5)

    def test_dependency_references_are_deduplicated(self) -> None:
        self.assertEqual(
            evolution_snapshot.references_from_text("See #12 #12 #13 #12"),
            [12, 13],
        )


if __name__ == "__main__":
    unittest.main()
