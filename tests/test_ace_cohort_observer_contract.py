import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ace-cohort-observer.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


def _reuse_branch() -> str:
    """The body of `if (statusIssue) { ... }` guarding the reuse write."""
    start = TEXT.rindex("if (statusIssue) {")
    return TEXT[start:TEXT.index("} else {", start)]


class AceCohortObserverContractTests(unittest.TestCase):
    def test_privileged_observer_does_not_checkout_or_run_pr_code(self):
        self.assertNotIn("actions/checkout", TEXT)
        self.assertNotIn("run:", TEXT)

    def test_action_dependency_is_immutable(self):
        self.assertIn(
            "actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b",
            TEXT,
        )

    def test_bootstrap_seed_admission_requires_trusted_provenance(self):
        self.assertIn("trustedSeedAuthors", TEXT)
        self.assertIn("issue.author_association", TEXT)
        self.assertIn("trustedSeedAuthors.has(issue.author_association || 'NONE')", TEXT)
        self.assertIn("cohort=bootstrap-1", TEXT)

    def test_observatory_identity_is_workflow_owned(self):
        self.assertIn("const statusLabel = 'ace:cohort-observer';", TEXT)
        self.assertIn("labels: statusLabel,", TEXT)
        self.assertIn("ACE_COHORT_STATE", TEXT)

    def test_snapshot_does_not_claim_full_reproduction_number(self):
        self.assertIn("metric_scope: 'bootstrap_growth_seed_exposure'", TEXT)
        self.assertIn("full_r_community_ready: false", TEXT)
        self.assertIn("this observer alone must not claim the full reproduction number", TEXT.lower())

    def test_verification_label_is_observed_not_auto_applied(self):
        self.assertIn("const verifiedLabel = 'ace:verified-descendant';", TEXT)
        self.assertNotIn("labels: [verifiedLabel]", TEXT)

    def test_observer_never_auto_creates_cohort_two(self):
        self.assertIn("EVALUATE_COHORT_2", TEXT)
        self.assertNotIn("title: '[ACE] Bootstrap Cohort 2", TEXT)

    def test_observatory_selection_does_not_depend_on_listing_order(self):
        # `openIssues.find(...)` returned the first match in API listing order,
        # which is creation-descending, so a duplicate created later captured
        # every write and the original froze while still being linked.
        self.assertNotIn("openIssues.find(", TEXT)
        self.assertIn("const statusCandidates = labelledObservatories", TEXT)
        self.assertIn("let statusIssue = statusCandidates[0];", TEXT)

    def test_selection_sorts_candidates_by_issue_number(self):
        # The primary selection must sort, like the legacy migration below it.
        # Assert the sort is chained onto the candidate filter specifically:
        # counting occurrences would pass on the unfixed file, which already
        # sorts in two other places.
        self.assertIn(
            "const statusCandidates = labelledObservatories\n"
            "              .filter(issue => !issue.pull_request)\n"
            "              .sort((a, b) => a.number - b.number);",
            TEXT,
        )

    def test_duplicate_observatories_are_surfaced_not_silently_ignored(self):
        # The warning counts what will be open when the pass finishes, not what
        # was open when it started: the canonical observatory archived while a
        # fork of it is open is the case that leaves two open, and counting only
        # the already-open set is silent on exactly that one.
        self.assertIn("observatoriesLeftOpen.length > 1", TEXT)
        self.assertIn(
            "issue => issue.state === 'open' || issue === statusIssue", TEXT
        )
        self.assertIn("core.warning(", TEXT)

    # --- The duplicate-creation path -------------------------------------
    #
    # Selection resolved identity from a `state: 'open'` listing and fell
    # straight through to `issues.create` when that listing came back empty.
    # Closing the observatory therefore did not archive it: the next pass found
    # nothing, forked a duplicate at a new number, and the evidence series that
    # README.md and examples/community/ace-activation-gate-current.example.json
    # cite by number split in two. #410 is that fork of #109. The three tests
    # below fail on that file.

    def test_observatory_lookup_is_not_restricted_to_open_issues(self):
        self.assertIn(
            "const labelledObservatories = await github.paginate(github.rest.issues.listForRepo, {\n"
            "              owner,\n"
            "              repo,\n"
            "              state: 'all',\n"
            "              labels: statusLabel,\n"
            "              per_page: 100\n"
            "            });",
            TEXT,
        )
        # The whole-repository `state: 'open'` listing that fed selection is
        # gone. Nothing may reintroduce it under any name: an open-only listing
        # is exactly the condition that makes a closed observatory invisible.
        self.assertNotIn("const openIssues = await", TEXT)

    def test_legacy_migration_also_looks_past_open_issues(self):
        # The migration fallback shared the open-only listing, so it could not
        # rescue a closed pre-label observatory either.
        self.assertIn(
            "const allIssues = await github.paginate(github.rest.issues.listForRepo, {\n"
            "                owner,\n"
            "                repo,\n"
            "                state: 'all',\n"
            "                per_page: 100\n"
            "              });",
            TEXT,
        )
        self.assertIn("const legacy = allIssues", TEXT)

    def test_closed_observatory_is_reopened_rather_than_replaced(self):
        branch = _reuse_branch()
        self.assertIn("issue_number: statusIssue.number,", branch)
        self.assertIn("body,", branch)
        # Unconditional, so a body rewrite can never leave the observatory
        # closed and invisible to the next lookup.
        self.assertIn("state: 'open'", branch)
        # And a human is told, because a closed observatory means an issue
        # tidying pass treated workflow-owned state as a task.
        self.assertIn("statusIssue.state === 'closed'", branch)

    def test_creation_is_reachable_only_when_no_observatory_was_found(self):
        create = "await github.rest.issues.create({"
        self.assertEqual(1, TEXT.count(create))
        before = TEXT[: TEXT.index(create)]
        self.assertTrue(
            before.rstrip().endswith("} else {"),
            "issues.create is no longer the else-branch of `if (statusIssue)`, "
            "so a run can create a second observatory while one already exists",
        )
        self.assertIn("await github.rest.issues.update({", _reuse_branch())

    def test_permissions_do_not_include_contents_write(self):
        self.assertIn("contents: read", TEXT)
        self.assertNotIn("contents: write", TEXT)


if __name__ == "__main__":
    unittest.main()
