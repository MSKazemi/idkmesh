import json
from io import BytesIO

import pytest

from tools.openhands_pilot import (
    PilotError,
    build_prompt,
    conversation_identity,
    create_conversation,
    get_conversation,
    validate_issue,
)


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


def test_veto_labels_fail_closed():
    for label in [
        "blocked",
        "do-not-automate",
        "human-required",
        "needs-decomposition",
        "research-evidence",
        "security-sensitive",
    ]:
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
        validate_issue(issue("agent-ready", pull_request=True))


def test_prompt_preserves_authority_boundary():
    prompt = build_prompt(issue("agent-ready"), "MSKazemi/idkmesh", "main")
    assert "Issue: #641" in prompt
    assert "Do not merge, approve, close the issue" in prompt
    assert "Do not claim your own output is independent verification" in prompt
    assert "Repository: MSKazemi/idkmesh" in prompt
    assert "Base branch: main" in prompt


def test_conversation_identity_requires_id():
    with pytest.raises(PilotError, match="conversation id"):
        conversation_identity({"status": "RUNNING"})


def test_create_conversation_sends_bounded_repository_context(monkeypatch):
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"conversation_id": "conv-1", "status": "RUNNING"}
            ).encode()

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["body"] = json.loads(request.data.decode())
        observed["api_key"] = request.headers["X-session-api-key"]
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = create_conversation(
        "secret-value",
        "https://app.all-hands.dev",
        "bounded prompt",
        "MSKazemi/idkmesh",
        "main",
    )

    assert response["conversation_id"] == "conv-1"
    assert observed["url"] == "https://app.all-hands.dev/api/conversations"
    assert observed["body"] == {
        "initial_user_msg": "bounded prompt",
        "repository": "MSKazemi/idkmesh",
        "selected_branch": "main",
    }
    assert observed["api_key"] == "secret-value"
    assert observed["timeout"] == 30


def test_get_conversation_uses_session_api_key(monkeypatch):
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"conversation_id": "conv-1", "status": "STOPPED"}
            ).encode()

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["api_key"] = request.headers["X-session-api-key"]
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = get_conversation(
        "secret-value", "https://app.all-hands.dev", "conv-1"
    )

    assert response["status"] == "STOPPED"
    assert observed["url"] == (
        "https://app.all-hands.dev/api/conversations/conv-1"
    )
    assert observed["api_key"] == "secret-value"
    assert observed["timeout"] == 30
