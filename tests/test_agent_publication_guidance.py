"""Guard the agent publication-backpressure instructions.

The repository ships ``tools/github_atomic_commit.py`` so that an agent can
publish a multi-file candidate as one commit and one non-force ref update.
That tool only reduces CI pressure if the agent-facing contract actually tells
agents to use it, so the machine-facing rule in ``AGENTS.md``, the
contributor-facing explanation in ``CONTRIBUTING.md``, and the operational
runbook in ``docs/operations/JULES_AUTOMATION.md`` must stay aligned with each
other and with the tool that is on ``main``.

Without this guard the three surfaces can drift independently: the tool landed
in PR #646 while the agent-facing policy in PR #650 did not, leaving a shipped
helper that no agent contract pointed to.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

AGENTS = "AGENTS.md"
CONTRIBUTING = "CONTRIBUTING.md"
RUNBOOK = "docs/operations/JULES_AUTOMATION.md"
TOOL = "tools/github_atomic_commit.py"


class AgentPublicationGuidanceTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_atomic_writer_is_present_for_the_documented_policy(self) -> None:
        self.assertTrue(
            (ROOT / TOOL).is_file(),
            f"{TOOL} must exist for the publication policy to be actionable",
        )

    def test_agents_file_names_atomic_writer_and_non_force_behavior(self) -> None:
        text = self.text(AGENTS)
        self.assertIn("Agent publication backpressure", text)
        self.assertIn(TOOL, text)
        self.assertIn("one branch commit / one ref update", text)
        self.assertIn("non-force ref update", text)
        self.assertIn("Direct writes to `main` remain forbidden", text)

    def test_agents_file_treats_moved_head_as_stop_not_force_push(self) -> None:
        text = self.text(AGENTS)
        self.assertIn(
            "stop/replan condition, not permission to force-push",
            text,
        )

    def test_contributing_explains_ci_cost_of_per_file_commits(self) -> None:
        text = self.text(CONTRIBUTING)
        self.assertIn("avoid publishing one GitHub commit per file edit", text)
        self.assertIn("restart CI", text)
        self.assertIn(TOOL, text)

    def test_runbook_keeps_the_atomic_publication_reference(self) -> None:
        text = self.text(RUNBOOK)
        self.assertIn("Atomic multi-file publications for agent branches", text)
        self.assertIn(TOOL, text)
        self.assertIn("non-force ref update", text)

    def test_provider_owned_agents_are_not_exempt_from_the_rule(self) -> None:
        for path in (AGENTS, CONTRIBUTING):
            with self.subTest(surface=path):
                self.assertIn("Provider-owned agents", self.text(path))

    def test_guidance_does_not_grant_merge_authority(self) -> None:
        combined = "\n".join(
            self.text(path) for path in (AGENTS, CONTRIBUTING, RUNBOOK)
        )
        self.assertIn("Direct writes to `main` remain forbidden", combined)
        self.assertIn("No Jules task auto-merges `main`.", combined)


if __name__ == "__main__":
    unittest.main()
