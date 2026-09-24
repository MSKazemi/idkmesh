import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("router", ROOT / "scripts" / "issue_model_router.py")
router = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = router
SPEC.loader.exec_module(router)

POLICY = json.loads((ROOT / "config" / "llm-routing-policy.json").read_text())
OVERRIDES = json.loads((ROOT / "config" / "issue-model-routing-overrides.json").read_text())
DISPATCH_POLICY = json.loads((ROOT / "config" / "jules-dispatch.json").read_text())


def route(number, title, body=""):
    return router.classify_issue(
        {"number": number, "title": title, "body": body, "labels": []},
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )


def test_current_good_first_issue_routes_to_small_and_jules_eligible():
    value = route(563, "good first issue: add direct tests for sim/e017_oracles.py")
    assert value.tier == "T1"
    assert value.authority == "agent"
    queue_label = POLICY["provider_examples"]["jules"]["queue_label"]
    assert queue_label in value.labels

    blocked_override = router.classify_issue(
        {
            "number": 563,
            "title": "good first issue: add direct tests for sim/e017_oracles.py",
            "body": "",
            "labels": ["needs-decomposition"],
        },
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert queue_label not in blocked_override.labels
    assert "model:t1-small" in blocked_override.labels
    assert "authority:agent-candidate" in blocked_override.labels
    assert any("Jules hard veto labels" in reason for reason in blocked_override.reasons)


def test_current_benchmark_generator_task_routes_to_standard():
    value = route(564, "good first issue: add per-family coverage to benchmark publication")
    assert value.tier == "T2"
    assert value.recommended_lane == "jules-or-equivalent"


def test_current_statistical_research_routes_to_peak():
    value = route(520, "research: quantify finite-sample uncertainty in gate-audit effective-vote estimates")
    assert value.tier == "T4"
    assert value.authority == "agent"


def test_independent_review_is_human_even_if_models_are_capable():
    value = route(138, "Independent review: inspect PR #159 canonical-node evidence")
    assert value.tier is None
    assert value.authority == "human_required"
    assert "model:none" in value.labels


def test_new_bounded_test_defaults_to_small_or_standard():
    value = router.classify_issue(
        {
            "number": 9999,
            "title": "Add focused tests for parser helper",
            "body": "Add tests for one helper. Run focused regression tests. No schema or workflow changes.",
            "labels": ["good first issue"],
        },
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert value.tier in {"T1", "T2"}
    assert value.authority == "agent"


def test_new_security_work_cannot_route_below_strong():
    value = router.classify_issue(
        {
            "number": 9998,
            "title": "Tighten GitHub workflow permissions",
            "body": "Review security and permissions for the release workflow.",
            "labels": [],
        },
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert router.TIER_ORDER[value.tier] >= router.TIER_ORDER["T3"]


def test_new_human_evidence_task_is_not_agent_routed():
    value = router.classify_issue(
        {
            "number": 9997,
            "title": "Run on another person's machine",
            "body": "We need an external tester to report first-run friction.",
            "labels": [],
        },
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert value.authority == "human_required"
    assert value.tier is None


def test_route_serialization_carries_current_labels_for_api_free_diffing():
    issue = {
        "number": 9996,
        "title": "Add focused docs test",
        "body": "Documentation-only bounded task.",
        "labels": [{"name": "enhancement"}, {"name": "priority:p2"}],
    }
    value = router.classify_issue(issue, POLICY, OVERRIDES)
    payload = router._route_dict(value, issue)

    assert payload["current_labels"] == ["enhancement", "priority:p2"]

    queue_label = POLICY["provider_examples"]["jules"]["queue_label"]
    for veto in ("needs-decomposition", "agent:jules-completed"):
        blocked_issue = {
            "number": 9996,
            "title": "Add focused docs test",
            "body": "Documentation-only bounded task.",
            "labels": [{"name": "enhancement"}, {"name": veto}],
        }
        blocked_route = router.classify_issue(
            blocked_issue,
            POLICY,
            OVERRIDES,
            DISPATCH_POLICY,
        )
        assert queue_label not in blocked_route.labels
        assert blocked_route.tier in {"T1", "T2"}
        assert blocked_route.authority == "agent"

    unblocked_issue = {
        "number": 9996,
        "title": "Add focused docs test",
        "body": "Documentation-only bounded task.",
        "labels": [{"name": "enhancement"}],
    }
    unblocked_route = router.classify_issue(
        unblocked_issue,
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert queue_label in unblocked_route.labels


def test_never_scope_does_not_escalate_sensitive_phrase():
    value = router.classify_issue(
        {
            "number": 9995,
            "title": "Document bounded read-only behavior",
            "body": "This helper never grants merge authority. Add a focused documentation test.",
            "labels": [],
        },
        POLICY,
        OVERRIDES,
        DISPATCH_POLICY,
    )
    assert router.TIER_ORDER[value.tier] <= router.TIER_ORDER["T2"]


def test_router_workflow_keeps_hot_path_api_budget_bounded():
    workflow = (ROOT / ".github" / "workflows" / "issue-model-router.yml").read_text(
        encoding="utf-8"
    )

    assert "cron: '7 */6 * * *'" in workflow
    assert "gh issue view" not in workflow
    assert "Validate router syntax" in workflow
    assert "Validate Jules control-plane contract" in workflow
    assert "python tools/check_jules_contract.py" in workflow
    assert "--dispatch-policy config/jules-dispatch.json" in workflow
    assert "python -m pytest" not in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.bootstrap_labels" in workflow
    assert "uses: ./.github/workflows/jules-dispatch.yml" in workflow
    assert "issue_number: ${{ needs.route.outputs.routed_issue_number }}" in workflow
    assert "secrets: inherit" in workflow
    assert "gh workflow run jules-dispatch.yml" not in workflow
    assert "bootstrap_labels: true" in workflow
    assert "fill_capacity: true" in workflow
    assert "actions: write" not in workflow
