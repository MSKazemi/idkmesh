"""Issue #596: bootstrap owner steps remain manual and reproducible."""
import pytest
from idkmesh.github_bootstrap import (
    build_github_bootstrap_plan,
    render_owner_action_checklist,
)


def test_owner_checklist_is_complete_and_deterministic():
    plan = build_github_bootstrap_plan(idkmesh_ref="a" * 40)
    output = render_owner_action_checklist(plan)
    assert output == render_owner_action_checklist(plan)
    assert output.endswith("\n")
    for action in plan.owner_actions:
        assert output.count(f"- [ ] {action.code}:") == 1
        assert action.reason in output
        assert action.requires_repository_owner and not action.automatic
    assert "a" * 40 in output
    assert "Do not paste secret values" in output
    assert "configure-preview-scope" in output
    assert "verify-pinned-runtime" in output
    assert "unavailable phases must stay fail-closed" in output
    assert "not implemented on current main" not in output


def test_owner_checklist_rejects_non_plan_input():
    with pytest.raises(TypeError, match="GitHubBootstrapPlan"):
        render_owner_action_checklist({"owner_actions": []})
