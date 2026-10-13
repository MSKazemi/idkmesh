"""C8-E owner-only checklist tests; unittest discovery must include these tests."""
import unittest

from idkmesh.github_bootstrap import (
    build_github_bootstrap_plan,
    render_owner_action_checklist,
)


class OwnerChecklistTests(unittest.TestCase):
    def test_owner_checklist_is_complete_and_deterministic(self):
        plan = build_github_bootstrap_plan(idkmesh_ref="a" * 40)
        output = render_owner_action_checklist(plan)
        self.assertEqual(output, render_owner_action_checklist(plan))
        self.assertTrue(output.endswith("\n"))
        for action in plan.owner_actions:
            self.assertEqual(output.count(f"- [ ] {action.code}:"), 1)
            self.assertIn(action.reason, output)
            self.assertTrue(action.requires_repository_owner)
            self.assertFalse(action.automatic)
        self.assertIn("a" * 40, output)
        self.assertIn("Do not paste secret values", output)
        self.assertIn("configure-preview-scope", output)
        self.assertIn("verify-pinned-runtime", output)
        self.assertIn("unavailable phases must stay fail-closed", output)
        self.assertNotIn("not implemented on current main", output)

    def test_owner_checklist_rejects_non_plan_input(self):
        with self.assertRaisesRegex(TypeError, "GitHubBootstrapPlan"):
            render_owner_action_checklist({"owner_actions": []})
