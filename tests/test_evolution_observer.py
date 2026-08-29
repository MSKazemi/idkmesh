from __future__ import annotations

from email.message import Message
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import repository_evolution_score as evolution_score  # noqa: E402
import evolution_snapshot  # noqa: E402

POLICY = json.loads((ROOT / "config/evolution-policy-v1.json").read_text())


def snapshot(*, protected=False, ready=2, draft=1, issues=4, reviewed=0, external=0, branches=50, pin_ratio=0.5):
    prs = []
    for number in range(100, 100 + ready):
        prs.append({
            "number": number,
            "kind": "pull_request",
            "draft": False,
            "labels": [],
            "references": [91] if number != 91 else [],
            "independent_review_count": 1 if reviewed > 0 else 0,
            "independent_approval_count": 0,
        })
        reviewed -= 1
    for number in range(200, 200 + draft):
        prs.append({"number": number, "kind": "pull_request", "draft": True, "labels": [], "references": [], "independent_review_count": 0, "independent_approval_count": 0})
    open_issues = []
    for number in range(1, 1 + issues):
        labels = ["growth-seed", "good first issue"] if number == 1 else (["research"] if number == 2 else [])
        open_issues.append({"number": number, "kind": "issue", "labels": labels, "references": [100] if number == 2 and ready else []})
    return {
        "version": 1,
        "source": {"repository": "MSKazemi/idkmesh", "event_kind": "test"},
        "integration": {"main_protected": protected},
        "open_issues": open_issues,
        "open_pull_requests": prs,
        "recent_merged_pull_requests_30d": 5,
        "external_participant_count": external,
        "branch_count": branches,
        "workflow_supply_chain": {"external_uses": 10, "pinned_uses": int(10 * pin_ratio), "pin_ratio": pin_ratio, "floating": []},
        "project_memory": {"conversation_records": 10, "preservation_rule_present": True, "completeness_claim": False},
        "collection": {},
    }


class EvolutionObserverTests(unittest.TestCase):
    @staticmethod
    def _http_error(*, body: str, remaining: str | None = None) -> HTTPError:
        headers = Message()
        if remaining is not None:
            headers["X-RateLimit-Remaining"] = remaining
        return HTTPError(
            "https://api.github.com/repos/example/repository",
            403,
            "Forbidden",
            headers,
            io.BytesIO(body.encode("utf-8")),
        )

    def test_capacity_recovers_when_open_work_decreases(self):
        high = evolution_score.capacity_metrics(snapshot(ready=8, draft=4, issues=20), POLICY)
        low = evolution_score.capacity_metrics(snapshot(ready=1, draft=0, issues=2), POLICY)
        self.assertGreater(low["capacity"], high["capacity"])
        self.assertLess(low["review_load"], high["review_load"])

    def test_unprotected_repository_enters_guard_mode(self):
        result = evolution_score.evaluate(snapshot(protected=False, ready=1, issues=2), POLICY)
        self.assertEqual(result["mode"], "GUARD")
        self.assertIn("main_unprotected", result["blockers"])
        self.assertTrue(result["authority"]["recommendation_only"])
        self.assertFalse(result["authority"]["automatic_merge"])

    def test_replicator_weights_normalize_and_keep_exploration_floor(self):
        result = evolution_score.evaluate(snapshot(protected=True, ready=6, issues=10), POLICY)
        weights = result["strategy_weights"]
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        self.assertTrue(all(value > 0 for value in weights.values()))

    def test_high_load_raises_consolidation_pressure(self):
        high = evolution_score.evaluate(snapshot(protected=True, ready=10, draft=4, issues=20), POLICY)
        low = evolution_score.evaluate(snapshot(protected=True, ready=0, draft=0, issues=1), POLICY)
        self.assertGreater(high["strategy_pressure"]["consolidate"], low["strategy_pressure"]["consolidate"])

    def test_popularity_fields_do_not_change_result(self):
        base = snapshot(protected=True, ready=1, issues=2, external=1, pin_ratio=1.0, branches=10)
        altered = json.loads(json.dumps(base))
        altered["stars"] = 1_000_000
        altered["forks"] = 500_000
        altered["raw_comments"] = 99_999_999
        self.assertEqual(evolution_score.evaluate(base, POLICY), evolution_score.evaluate(altered, POLICY))

    def test_dependency_references_are_deduplicated(self):
        refs = evolution_snapshot.references_from_text("See #12 #12 and #13, then #12")
        self.assertEqual(refs, [12, 13])

    def test_rate_limit_exhaustion_has_distinct_unavailable_outcome(self):
        error = self._http_error(body='{"message":"API rate limit exceeded"}', remaining="0")
        with mock.patch.object(evolution_snapshot, "urlopen", side_effect=error):
            with self.assertRaises(evolution_snapshot.GitHubObservationUnavailable):
                evolution_snapshot._request_json("/repos/example/repository", "token")

    def test_unrelated_forbidden_response_remains_a_failure(self):
        error = self._http_error(body='{"message":"Resource not accessible by integration"}', remaining="42")
        with mock.patch.object(evolution_snapshot, "urlopen", side_effect=error):
            with self.assertRaises(HTTPError):
                evolution_snapshot._request_json("/repos/example/repository", "token")

    def test_cli_does_not_write_partial_snapshot_when_observation_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "snapshot.json"
            argv = [
                "evolution_snapshot.py",
                "--repository",
                "example/repository",
                "--event-kind",
                "test",
                "--output",
                str(output),
            ]
            unavailable = evolution_snapshot.GitHubObservationUnavailable("rate limit")
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(evolution_snapshot.os.environ, {"GITHUB_TOKEN": "token"}, clear=True),
                mock.patch.object(evolution_snapshot, "collect", side_effect=unavailable),
            ):
                self.assertEqual(evolution_snapshot.main(), evolution_snapshot.OBSERVATION_UNAVAILABLE_EXIT)
            self.assertFalse(output.exists())

    def test_reference_extraction_is_bounded_and_structural_only(self):
        text = "ignore words and URLs " + " ".join(f"#{number}" for number in range(1, 80))
        refs = evolution_snapshot.references_from_text(text)
        self.assertEqual(refs, list(range(1, 33)))
        self.assertEqual(len(refs), 32)

    def test_independent_review_excludes_author_and_bots(self):
        item = {
            "number": 77,
            "draft": False,
            "labels": [],
            "body": "Refs #35 #91",
            "created_at": "2026-08-28T10:00:00Z",
            "user": {"login": "author", "type": "User"},
            "head": {"sha": "current-head"},
        }
        reviews = [
            {"state": "APPROVED", "commit_id": "current-head", "user": {"login": "author", "type": "User"}},
            {"state": "APPROVED", "commit_id": "current-head", "user": {"login": "ci-bot[bot]", "type": "Bot"}},
            {"state": "COMMENTED", "commit_id": "current-head", "user": {"login": "reviewer-one", "type": "User"}},
            {"state": "APPROVED", "commit_id": "current-head", "user": {"login": "reviewer-two", "type": "User"}},
            {"state": "APPROVED", "commit_id": "stale-head", "user": {"login": "reviewer-three", "type": "User"}},
        ]
        now = evolution_snapshot.datetime(2026, 8, 28, 16, tzinfo=evolution_snapshot.timezone.utc)
        normalized = evolution_snapshot._normalize_pr(item, now, reviews)
        self.assertEqual(normalized["references"], [35, 91])
        self.assertEqual(normalized["independent_review_count"], 1)
        self.assertEqual(normalized["independent_approval_count"], 1)

    def test_current_head_changes_requested_is_review_evidence_but_not_approval(self):
        item = {
            "number": 78,
            "draft": False,
            "labels": [],
            "body": "",
            "created_at": "2026-08-28T10:00:00Z",
            "user": {"login": "author", "type": "User"},
            "head": {"sha": "current-head"},
        }
        reviews = [
            {"state": "CHANGES_REQUESTED", "commit_id": "current-head", "user": {"login": "reviewer", "type": "User"}},
        ]
        now = evolution_snapshot.datetime(2026, 8, 28, 16, tzinfo=evolution_snapshot.timezone.utc)
        normalized = evolution_snapshot._normalize_pr(item, now, reviews)
        self.assertEqual(normalized["independent_review_count"], 1)
        self.assertEqual(normalized["independent_approval_count"], 0)

    def test_latest_current_head_review_state_controls_evidence(self):
        item = {
            "number": 79,
            "draft": False,
            "labels": [],
            "body": "",
            "created_at": "2026-08-28T10:00:00Z",
            "user": {"login": "author", "type": "User"},
            "head": {"sha": "current-head"},
        }
        reviews = [
            {"id": 1, "state": "APPROVED", "commit_id": "current-head", "submitted_at": "2026-08-28T11:00:00Z", "user": {"login": "reviewer", "type": "User"}},
            {"id": 2, "state": "DISMISSED", "commit_id": "current-head", "submitted_at": "2026-08-28T12:00:00Z", "user": {"login": "reviewer", "type": "User"}},
        ]
        now = evolution_snapshot.datetime(2026, 8, 28, 16, tzinfo=evolution_snapshot.timezone.utc)
        normalized = evolution_snapshot._normalize_pr(item, now, reviews)
        self.assertEqual(normalized["independent_review_count"], 0)
        self.assertEqual(normalized["independent_approval_count"], 0)

    def test_truncated_review_history_fails_closed(self):
        item = {
            "number": 80,
            "draft": False,
            "labels": [],
            "body": "",
            "created_at": "2026-08-28T10:00:00Z",
            "user": {"login": "author", "type": "User"},
            "head": {"sha": "current-head"},
        }
        reviews = [
            {"state": "APPROVED", "commit_id": "current-head", "user": {"login": "reviewer", "type": "User"}},
        ]
        now = evolution_snapshot.datetime(2026, 8, 28, 16, tzinfo=evolution_snapshot.timezone.utc)
        normalized = evolution_snapshot._normalize_pr(item, now, reviews, reviews_truncated=True)
        self.assertEqual(normalized["independent_review_count"], 0)
        self.assertEqual(normalized["independent_approval_count"], 0)

    def test_workflow_pin_scan_detects_floating_and_pinned_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "x.yml").write_text(
                "steps:\n"
                "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
                "  - uses: actions/setup-python@v7\n"
                "  - uses: ./local-action\n",
                encoding="utf-8",
            )
            result = evolution_snapshot.scan_workflow_pins(root)
            self.assertEqual(result["external_uses"], 2)
            self.assertEqual(result["pinned_uses"], 1)
            self.assertAlmostEqual(result["pin_ratio"], 0.5)
            self.assertEqual(result["floating"][0]["ref"], "v7")

    def test_workflow_avoids_per_comment_observation_amplification(self):
        workflow = (ROOT / ".github" / "workflows" / "evolution-loop.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  issue_comment:\n", workflow)

    def test_workflow_does_not_publish_incomplete_observations(self):
        workflow = (ROOT / ".github" / "workflows" / "evolution-loop.yml").read_text(encoding="utf-8")
        self.assertIn("status\" -eq 75", workflow)
        self.assertGreaterEqual(workflow.count("if: steps.observation.outputs.available == 'true'"), 5)
        self.assertIn("No decision, recommendation, or Bayesian checkpoint was published", workflow)

    def test_ready_pr_review_coverage_is_measured_independently(self):
        s = snapshot(protected=True, ready=2, issues=1, reviewed=1)
        result = evolution_score.evaluate(s, POLICY)
        self.assertAlmostEqual(result["review"]["review_coverage"], 0.5)
        self.assertIn("ready_prs_lack_independent_review", result["blockers"])

    def test_control_energy_falls_when_guardrails_improve(self):
        weak = evolution_score.evaluate(snapshot(protected=False, ready=4, issues=10, reviewed=0, external=0, branches=80, pin_ratio=0.4), POLICY)
        strong = evolution_score.evaluate(snapshot(protected=True, ready=1, issues=2, reviewed=1, external=2, branches=10, pin_ratio=1.0), POLICY)
        self.assertLess(strong["control_energy_proxy"], weak["control_energy_proxy"])


if __name__ == "__main__":
    unittest.main()


class PriorityUncertaintyTests(unittest.TestCase):
    """P0 item 3 of #86: a point score must not be presented as truth."""

    PARTS = frozenset(evolution_score.NUMERATOR_PARTS) | frozenset(evolution_score.DENOMINATOR_PARTS)

    def actions(self, **kwargs):
        result = evolution_score.evaluate(snapshot(**kwargs), POLICY)
        self.assertTrue(result["recommended_actions"], "fixture produced no recommendations")
        return result

    def test_every_action_declares_provenance_for_every_priority_input(self):
        for action in self.actions()["recommended_actions"]:
            with self.subTest(action=action["id"]):
                self.assertEqual(set(action["priority_input_provenance"]), self.PARTS)
                self.assertTrue(
                    set(action["priority_input_provenance"].values())
                    <= {
                        evolution_score.SNAPSHOT_DERIVED,
                        evolution_score.SNAPSHOT_CONDITIONED_PRIOR,
                        evolution_score.HAND_AUTHORED_PRIOR,
                    }
                )

    def test_point_score_lies_inside_its_own_sensitivity_bounds(self):
        for action in self.actions()["recommended_actions"]:
            low, high = action["priority_bounds"]
            with self.subTest(action=action["id"]):
                self.assertLessEqual(low, action["priority"])
                self.assertLessEqual(action["priority"], high)
                self.assertLess(low, high)

    def test_snapshot_derived_inputs_are_not_perturbed_and_not_listed_as_unevidenced(self):
        actions = {action["id"]: action for action in self.actions()["recommended_actions"]}
        pull_request_actions = [
            action for identifier, action in actions.items() if identifier.endswith("-pr-100")
        ]
        self.assertTrue(pull_request_actions, "fixture produced no pull-request action")
        for action in pull_request_actions:
            with self.subTest(action=action["id"]):
                self.assertEqual(
                    action["priority_input_provenance"]["unlock"],
                    evolution_score.SNAPSHOT_DERIVED,
                )
                self.assertNotIn("unlock", action["unevidenced_priority_inputs"])

    def test_fully_authored_action_reports_every_input_as_unevidenced(self):
        actions = {action["id"]: action for action in self.actions()["recommended_actions"]}
        self.assertIn("protect-main", actions)
        self.assertEqual(
            set(actions["protect-main"]["unevidenced_priority_inputs"]), self.PARTS
        )

    def test_adjacent_recommendations_report_whether_ordering_is_separated(self):
        result = self.actions()
        ranked = result["recommended_actions"]
        self.assertIsNone(ranked[-1]["separated_from_next"])
        for action in ranked[:-1]:
            with self.subTest(action=action["id"]):
                self.assertIsInstance(action["separated_from_next"], bool)
        self.assertEqual(
            result["priority_uncertainty"]["adjacent_pairs_not_separated"],
            sum(1 for action in ranked if action["separated_from_next"] is False),
        )

    def test_the_current_ranking_is_not_separated_by_evidence(self):
        # This is the finding, pinned as a test: under a 25% perturbation of the
        # authored constants, no adjacent pair of recommendations is ordered by
        # evidence. If a future change makes the ranking separable, this test
        # should fail and be updated deliberately rather than silently.
        result = self.actions()
        ranked = result["recommended_actions"]
        self.assertEqual(
            result["priority_uncertainty"]["adjacent_pairs_not_separated"], len(ranked) - 1
        )

    def test_bounds_are_not_advertised_as_a_confidence_interval(self):
        uncertainty = self.actions()["priority_uncertainty"]
        self.assertFalse(uncertainty["bounds_are_a_confidence_interval"])
        self.assertEqual(
            uncertainty["authored_sensitivity_fraction"], evolution_score.AUTHORED_SENSITIVITY
        )

    def test_wider_perturbation_never_narrows_the_bounds(self):
        parts = {
            "value": 0.7, "confidence": 0.8, "unlock": 0.4, "community": 0.5,
            "reversibility": 0.9, "review": 0.3, "complexity": 0.4,
            "coordination": 0.2, "risk": 0.2,
        }
        provenance = dict.fromkeys(parts, evolution_score.HAND_AUTHORED_PRIOR)
        narrow = evolution_score._priority_bounds(parts, provenance)
        original = evolution_score.AUTHORED_SENSITIVITY
        try:
            evolution_score.AUTHORED_SENSITIVITY = original * 2
            wide = evolution_score._priority_bounds(parts, provenance)
        finally:
            evolution_score.AUTHORED_SENSITIVITY = original
        self.assertLessEqual(wide[0], narrow[0])
        self.assertGreaterEqual(wide[1], narrow[1])

    def test_provenance_must_cover_every_part(self):
        parts = {
            "value": 1.0, "confidence": 1.0, "unlock": 1.0, "community": 0.6,
            "reversibility": 0.8, "review": 0.4, "complexity": 0.3,
            "coordination": 0.5, "risk": 0.2,
        }
        incomplete = dict.fromkeys(parts, evolution_score.HAND_AUTHORED_PRIOR)
        del incomplete["risk"]
        with self.assertRaises(ValueError):
            evolution_score._scored(parts, incomplete)
