import pytest

from tools.openhands_pilot import PilotError, build_prompt, validate_issue


def issue(*labels: str, state: str = "open", pull_request: bool = False):
    payload = {
        "number": 641,
        "title": "Add a bounded worker",
        "body": "Implement the focused change and run tests.",
        "state": state,
        "labels": [{"name": label} for label in labels],
    }
    if pull_request:
        payload["pull_request"] = {"url": "https://example.invalid/pr"}
    return payload


def test_agent_ready_issue_is_accepted():
    validate_issue(issue("agent-ready", "size:s"))


@pytest.mark.parametrize(
    "label",
    [
        "blocked",
        "do-not-automate",
        "human-required",
        "needs-decomposition",
        "research-evidence",
        "security-sensitive",
    ],
)
def test_veto_labels_fail_closed(label):
    with pytest.raises(PilotError, match="veto"):
        validate_issue(issue("agent-ready", label))


def test_missing_agent_ready_fails_closed():
    with pytest.raises(PilotError, match="agent-ready"):
        validate_issue(issue("size:s"))


def test_closed_issue_is_rejected():
    with pytest.raises(PilotError, match="open"):
        validate_issue(issue("agent-ready", state="closed"))


def test_pull_request_is_rejected():
    with pytest.raises(PilotError, match="pull requests"):
        validate_issue("agent-ready") if False else validate_issue(
            issue("agent-ready", pull_request=True)
        )


def test_prompt_preserves_authority_boundary():
    prompt = build_prompt(issue("agent-ready"), "MSKazemi/idkmesh", "main")
    assert "Issue: #641" in prompt
    assert "Do not merge, approve, close the issue" in prompt
    assert "Do not claim your own output is independent verification" in prompt
    assert "Repository: MSKazemi/idkmesh" in prompt
    assert "Base branch: main" in prompt
