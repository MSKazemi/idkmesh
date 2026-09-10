import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-community-growth.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


def section(start: str, end: str | None = None) -> str:
    start_index = TEXT.index(start)
    if end is None:
        return TEXT[start_index:]
    return TEXT[start_index : TEXT.index(end, start_index)]


class AceConvergentRecoveryTests(unittest.TestCase):
    def test_singleton_ledger_writer_stays_globally_serialized(self) -> None:
        match = re.search(
            r"^concurrency:\n(?P<body>(?:  .*\n)+?)\njobs:",
            TEXT,
            re.MULTILINE,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("group: ace-community-growth", body)
        self.assertIn("cancel-in-progress: false", body)
        self.assertNotIn("github.event.pull_request.number", body)

    def test_trusted_seed_labels_reconcile_from_all_issue_state(self) -> None:
        recovery = section(
            "const allIssues = await github.paginate",
            "const issues = allIssues.filter",
        )
        self.assertIn("state: 'all'", recovery)
        self.assertIn("const unlabelledTrustedSeeds = allIssues", recovery)
        self.assertIn("(issue.body || '').includes('<!-- ACE_SEED')", recovery)
        self.assertIn(
            "trustedIssueAuthors.has(issue.author_association || 'NONE')",
            recovery,
        )
        self.assertIn("!labelsOf(issue).has('growth-seed')", recovery)
        self.assertIn("for (const issue of unlabelledTrustedSeeds)", recovery)
        self.assertIn("github.rest.issues.addLabels", recovery)

    def test_trusted_seed_recovery_does_not_depend_on_current_issue_payload(self) -> None:
        recovery = section(
            "const unlabelledTrustedSeeds = allIssues",
            "const issues = allIssues.filter",
        )
        self.assertNotIn("context.payload.issue", recovery)
        self.assertNotIn("event === 'issues'", recovery)
        self.assertNotIn("action === 'opened'", recovery)

    def test_spawn_recovery_scans_merged_opted_in_parents(self) -> None:
        recovery = section("// Conservative v0 actuator")
        self.assertIn("if (actuationAllowed)", recovery)
        self.assertIn("const eligibleSpawnParents = allIssues", recovery)
        self.assertIn("item.pull_request?.merged_at", recovery)
        self.assertIn("labelsOf(item).has('growth:spawn')", recovery)
        self.assertIn(
            "const missingSpawnParents = eligibleSpawnParents.filter",
            recovery,
        )
        self.assertNotIn("event === 'pull_request_target'", recovery)
        self.assertNotIn("context.payload.pull_request", recovery)

    def test_spawn_recovery_is_idempotent_and_authoritative(self) -> None:
        recovery = section("const missingSpawnParents = eligibleSpawnParents.filter")
        self.assertIn("labelsOf(item).has('growth-seed')", recovery)
        self.assertIn("(item.body || '').includes(marker)", recovery)
        self.assertNotIn("${pr.title}", recovery)

    def test_spawn_recovery_batch_is_bounded_and_fails_closed(self) -> None:
        recovery = section("// Conservative v0 actuator")
        self.assertIn("const MAX_AUTOMATIC_SPAWN_RECOVERY = 4;", recovery)
        guard = "if (missingSpawnParents.length > MAX_AUTOMATIC_SPAWN_RECOVERY)"
        loop = "for (const pr of missingSpawnParents)"
        self.assertIn(guard, recovery)
        self.assertIn("refusing partial or mass recovery", recovery)
        self.assertIn(loop, recovery)
        self.assertLess(recovery.index(guard), recovery.index(loop))
        self.assertEqual(
            recovery.count("title: `[Growth Seed] Reproduce or extend PR #${pr.number}`"),
            1,
        )

    def test_recovery_does_not_weaken_the_two_part_actuation_gate(self) -> None:
        self.assertIn(
            "const actuationAllowed = mainProtected && explicitActuationOptIn;",
            TEXT,
        )
        recovery = section("// Conservative v0 actuator")
        self.assertIn("if (actuationAllowed)", recovery)


if __name__ == "__main__":
    unittest.main()
