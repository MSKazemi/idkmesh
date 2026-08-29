from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVOLUTION = ROOT / ".github" / "workflows" / "evolution-loop.yml"
PORTFOLIO = ROOT / ".github" / "workflows" / "repository-math-portfolio.yml"
KERNEL = ROOT / ".github" / "workflows" / "mathematical-evolution-kernel.yml"


class EvolutionWorkflowSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evolution = EVOLUTION.read_text(encoding="utf-8")
        self.portfolio = PORTFOLIO.read_text(encoding="utf-8")

    def test_selected_checkpoint_downloads_fail_closed(self) -> None:
        for workflow in (self.evolution, self.portfolio):
            self.assertNotIn("continue-on-error: true", workflow)

        self.assertIn(
            "name: evolution-checkpoint-v2-${{ steps.previous.outputs.run_id }}",
            self.evolution,
        )
        self.assertIn(
            "test -f /tmp/previous-evolution/state/evolution-state.json",
            self.evolution,
        )
        self.assertIn(
            "test -f /tmp/previous-evolution/state/evolution-events.jsonl",
            self.evolution,
        )
        self.assertIn("validate_event_ledger(state, load_event_ledger", self.evolution)

        self.assertIn(
            "name: repository-portfolio-checkpoint-v2-${{ steps.previous_portfolio.outputs.run_id }}",
            self.portfolio,
        )
        self.assertIn(
            "test -f /tmp/previous-portfolio/repository-portfolio-state.json",
            self.portfolio,
        )
        self.assertIn("validate_portfolio_state(load_json", self.portfolio)
        self.assertIn(
            "name: evolution-checkpoint-v2-${{ steps.evolution.outputs.run_id }}",
            self.portfolio,
        )
        self.assertIn(
            "test -f /tmp/evolution/state/evolution-state.json",
            self.portfolio,
        )
        self.assertIn("validate_evolution_health_state(load_json", self.portfolio)

    def test_checkpoint_selection_requires_one_exact_unexpired_artifact(self) -> None:
        for workflow in (self.evolution, self.portfolio):
            self.assertIn(".expired == false and .name == $name", workflow)
            self.assertIn('select(.event == "issues" or .event == "push"', workflow)
            self.assertIn("exclude_pull_requests=true", workflow)
            self.assertIn("gh api --paginate", workflow)
            self.assertNotIn('.event == "pull_request_target"', workflow)
            self.assertIn('if [[ "$count" -gt 1 ]]', workflow)
            self.assertIn('if [[ "$count" -eq 1 ]]', workflow)
            self.assertNotIn(".workflow_runs[0].id", workflow)
            self.assertNotIn("|| echo 0", workflow)

    def test_checkpoint_manifests_bind_provenance_and_content(self) -> None:
        self.assertIn("evolution-checkpoint-manifest.json", self.evolution)
        self.assertIn("scripts/checkpoint_manifest.py", self.evolution)
        self.assertIn("checkpoint-manifest.json", self.portfolio)
        self.assertIn("scripts/checkpoint_manifest.py", self.portfolio)
        for workflow in (self.evolution, self.portfolio):
            self.assertIn('--head-sha "$SELECTED_HEAD_SHA"', workflow)
            self.assertIn('--event-name "$SELECTED_EVENT_NAME"', workflow)

    def test_live_observer_has_no_pull_request_review_trigger(self) -> None:
        trigger_block = self.evolution.split("permissions: {}", 1)[0]
        self.assertNotIn("pull_request_review:", trigger_block)

    def test_kernel_smoke_event_uses_trusted_source_fixture(self) -> None:
        kernel = KERNEL.read_text(encoding="utf-8")
        self.assertIn("--source workflow_dispatch", kernel)
        self.assertNotIn('--source "Mathematical Evolution Kernel"', kernel)

    def test_live_jobs_use_trusted_checkout_and_read_only_permissions(self) -> None:
        for workflow in (self.evolution, self.portfolio):
            self.assertIn("ref: ${{ github.event.repository.default_branch }}", workflow)
            self.assertIn("persist-credentials: false", workflow)
            self.assertNotIn("contents: write", workflow)
            self.assertNotIn("issues: write", workflow)
            self.assertNotIn("pull-requests: write", workflow)

    def test_external_actions_are_immutable_sha_pinned(self) -> None:
        for path in (EVOLUTION, PORTFOLIO):
            workflow = path.read_text(encoding="utf-8")
            for action in re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE):
                if action.startswith("./"):
                    continue
                self.assertRegex(action, r"@[0-9a-f]{40}$", action)

    def test_raw_repository_text_is_not_retained(self) -> None:
        self.assertIn(
            "test ! -e /tmp/repository-portfolio-checkpoint/repository-snapshot.json",
            self.portfolio,
        )
        checkpoint_block = self.portfolio.split(
            "- name: Assemble replayable checkpoint without raw bodies", 1
        )[1].split("- name: Publish replayable portfolio evidence", 1)[0]
        self.assertNotIn("cp /tmp/repository-snapshot.json", checkpoint_block)


if __name__ == "__main__":
    unittest.main()
