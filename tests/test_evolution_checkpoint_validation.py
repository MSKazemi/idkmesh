from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evolution_score  # noqa: E402
import repository_portfolio  # noqa: E402


MATH_POLICY = json.loads((ROOT / "state/evolution-math-policy.json").read_text(encoding="utf-8"))
PORTFOLIO_POLICY = json.loads(
    (ROOT / "state/repository-portfolio-policy.json").read_text(encoding="utf-8")
)


class EvolutionCheckpointValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = json.loads((ROOT / "state/evolution-state.json").read_text(encoding="utf-8"))
        self.records = evolution_score.load_event_ledger(ROOT / "state/evolution-events.jsonl")

    def test_repository_seed_is_valid(self) -> None:
        evolution_score.validate_evolution_state(self.state)
        evolution_score.validate_event_ledger(self.state, self.records)

    def test_unsupported_state_version_is_rejected_before_migration(self) -> None:
        self.state["version"] = 999
        with self.assertRaisesRegex(ValueError, "unsupported version"):
            evolution_score.migrate_state(self.state, MATH_POLICY)

    def test_forged_event_count_is_rejected(self) -> None:
        self.state["signals"]["events_seen"] = 999999
        with self.assertRaisesRegex(ValueError, "activity counts"):
            evolution_score.validate_evolution_state(self.state)

    def test_non_finite_belief_is_rejected(self) -> None:
        self.state["beliefs"]["goal_clarity"]["alpha"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite number"):
            evolution_score.validate_evolution_state(self.state)

    def test_ledger_must_match_latest_state_event(self) -> None:
        state = copy.deepcopy(self.state)
        state["signals"].update({"events_seen": 1, "last_event": "issues.opened", "last_actor": "alice"})
        state["activity_counts"] = {"event_kinds": {"issues.opened": 1}, "actors": {"alice": 1}}
        record = {
            "version": 2,
            "kind": "issues.closed",
            "actor": "alice",
            "repository": "MSKazemi/idkmesh",
            "ref": "refs/heads/main",
            "run_id": "123",
            "source": "issues",
            "timestamp": "2026-08-29T00:00:00+00:00",
            "checkpoint_source": "repository-seed",
        }
        evolution_score.validate_evolution_state(state)
        with self.assertRaisesRegex(ValueError, "latest kind"):
            evolution_score.validate_event_ledger(state, [record])

    def test_authority_policy_cannot_be_enabled_by_checkpoint(self) -> None:
        self.state["policy"]["autonomous_merge"] = True
        with self.assertRaisesRegex(ValueError, "must remain false"):
            evolution_score.validate_evolution_state(self.state)

    def test_untrusted_event_source_is_rejected(self) -> None:
        state = copy.deepcopy(self.state)
        state["updated_at"] = "2026-08-29T00:00:00+00:00"
        state["signals"].update(
            {
                "events_seen": 1,
                "last_event": "pull_request.opened",
                "last_actor": "alice",
            }
        )
        state["activity_counts"] = {
            "event_kinds": {"pull_request.opened": 1},
            "actors": {"alice": 1},
        }
        record = {
            "version": 2,
            "kind": "pull_request.opened",
            "actor": "alice",
            "repository": "MSKazemi/idkmesh",
            "ref": "refs/pull/1/merge",
            "run_id": "123",
            "source": "pull_request",
            "timestamp": state["updated_at"],
            "checkpoint_source": "repository-seed",
        }
        evolution_score.validate_evolution_state(state)
        with self.assertRaisesRegex(ValueError, "untrusted event source"):
            evolution_score.validate_event_ledger(state, [record])


class PortfolioCheckpointValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = json.loads(
            (ROOT / "state/repository-portfolio-state.json").read_text(encoding="utf-8")
        )
        self.evolution_state = json.loads(
            (ROOT / "state/evolution-state.json").read_text(encoding="utf-8")
        )

    def test_repository_seeds_are_valid(self) -> None:
        repository_portfolio.validate_portfolio_state(self.state, PORTFOLIO_POLICY)
        repository_portfolio.validate_evolution_health_state(self.evolution_state, MATH_POLICY)

    def test_invalid_arm_counter_is_rejected(self) -> None:
        self.state["arms"]["community"]["pulls"] = -1
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            repository_portfolio.validate_portfolio_state(self.state, PORTFOLIO_POLICY)

    def test_inconsistent_health_belief_is_rejected(self) -> None:
        self.evolution_state["fitness"]["community_health"] = 0.99
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            repository_portfolio.validate_evolution_health_state(self.evolution_state, MATH_POLICY)


if __name__ == "__main__":
    unittest.main()
