"""Guard the agent publication-backpressure instructions.

The repository deliberately tells coding agents to minimize PR-head churn because
each synchronize event can invalidate exact-head evidence and create another CI
wave. Keep the machine-facing AGENTS.md rule, contributor-facing explanation,
and Jules runbook aligned with the atomic writer.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AgentPublicationGuidanceTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_agents_file_names_atomic_writer_and_non_force_behavior(self):
        text = self.text("AGENTS.md")
        self.assertIn("Agent publication backpressure", text)
        self.assertIn("tools/github_atomic_commit.py", text)
        self.assertIn("one branch commit / one ref update", text)
        self.assertIn("non-force ref update", text)
        self.assertIn("Direct writes to `main` remain forbidden", text)

    def test_contributing_explains_ci_cost_of_per_file_commits(self):
        text = self.text("CONTRIBUTING.md")
        self.assertIn("avoid publishing one GitHub commit per file edit", text)
        self.assertIn("restart CI", text)
        self.assertIn("tools/github_atomic_commit.py", text)

    def test_jules_runbook_treats_ci_capacity_as_backpressure(self):
        text = self.text("docs/operations/JULES_AUTOMATION.md")
        self.assertIn("Branch-update backpressure", text)
        self.assertIn("minimize PR-head updates", text)
        self.assertIn("CI/review capacity as saturated", text)

    def test_guidance_does_not_grant_merge_authority(self):
        combined = "\n".join(
            [
                self.text("AGENTS.md"),
                self.text("CONTRIBUTING.md"),
                self.text("docs/operations/JULES_AUTOMATION.md"),
            ]
        )
        self.assertIn("Direct writes to `main` remain forbidden", combined)
        self.assertIn("No Jules task auto-merges `main`.", combined)


if __name__ == "__main__":
    unittest.main()
