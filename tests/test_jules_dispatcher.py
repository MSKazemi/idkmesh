from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from tools import jules_dispatcher as jd


POLICY = {
    "queue_label": "agent-ready",
    "automatic_queue_label": "agent:jules-eligible",
    "trusted_author_associations": ["OWNER", "MEMBER", "COLLABORATOR"],
    "dispatch_label": "agent:jules-dispatched",
    "legacy_dispatch_labels": ["jules"],
    "max_in_flight": 4,
    "max_dispatch_per_sweep": 2,
    "ci_backpressure": {
        "enabled": True,
        "max_queued_runs": 12,
        "max_in_progress_runs": 8,
    },
    "blocked_labels": [
        "blocked",
        "do-not-automate",
        "human-required",
        "needs-decomposition",
        "research-evidence",
        "security-sensitive",
    ],
    "priority_weights": {
        "priority:p0": 300,
        "priority:p1": 200,
        "priority:p2": 100,
    },
    "size_weights": {"size:xs": 40, "size:s": 30, "size:m": 10},
    "bonus_weights": {"bug": 15, "good first issue": 10, "documentation": 5},
    "label_definitions": {
        "agent-ready": {"color": "0E8A16", "description": "ready"},
        "agent:jules-eligible": {"color": "BFDADC", "description": "auto-ready"},
        "agent:jules-dispatched": {"color": "5319E7", "description": "dispatch"},
        "jules": {"color": "EDEDED", "description": "legacy"},
    },
}


def issue(
    number: int,
    *labels: str,
    state: str = "open",
    pull: bool = False,
    author_association: str = "OWNER",
):
    payload = {
        "number": number,
        "state": state,
        "title": f"issue {number}",
        "body": "bounded task body",
        "html_url": f"https://github.com/MSKazemi/idkmesh/issues/{number}",
        "author_association": author_association,
        "labels": [{"name": label} for label in labels],
    }
    if pull:
        payload["pull_request"] = {"url": "https://example.invalid/pr"}
    return payload


class FakeAPI:
    def __init__(
        self,
        *,
        active=None,
        legacy=None,
        queued=None,
        labels=None,
        queued_runs=0,
        in_progress_runs=0,
        fail_actions=False,
    ):
        self.repository = "MSKazemi/idkmesh"
        self.active = list(active or [])
        self.legacy = list(legacy or [])
        self.queued = list(queued or [])
        self.labels = list(labels or [])
        self.queued_runs = queued_runs
        self.in_progress_runs = in_progress_runs
        self.fail_actions = fail_actions
        self.workflow_count_calls = []
        self.added = []
        self.removed = []
        self.comments = []
        self.created = []

    def list_open_issues(self, label: str):
        if label == "agent:jules-dispatched":
            return deepcopy(self.active)
        if label == "jules":
            return deepcopy(self.legacy)
        if label in {"agent-ready", "agent:jules-eligible"}:
            return deepcopy(self.queued)
        return []

    def add_labels(self, issue_number: int, labels: list[str]):
        self.added.append((issue_number, list(labels)))

    def remove_label(self, issue_number: int, label: str):
        self.removed.append((issue_number, label))

    def add_comment(self, issue_number: int, body: str):
        self.comments.append((issue_number, body))

    def list_labels(self):
        return deepcopy(self.labels)

    def create_label(self, name: str, color: str, description: str):
        self.created.append((name, color, description))

    def count_workflow_runs(self, status: str):
        self.workflow_count_calls.append(status)
        if self.fail_actions:
            raise jd.DispatchError("synthetic Actions API failure")
        if status == "queued":
            return self.queued_runs
        if status == "in_progress":
            return self.in_progress_runs
        raise AssertionError(status)


class FakeJules:
    def __init__(self, *, existing=None, create_error=None):
        self.existing = existing
        self.create_error = create_error
        self.resolved = []
        self.created = []

    def resolve_source(self, repository: str):
        self.resolved.append(repository)
        return "sources/github/MSKazemi/idkmesh"

    def find_existing_session(self, title: str):
        return deepcopy(self.existing)

    def create_session(self, **kwargs):
        self.created.append(deepcopy(kwargs))
        if self.create_error:
            raise self.create_error
        return {
            "name": "sessions/123",
            "url": "https://jules.google.com/session/123",
            "state": "QUEUED",
        }


def test_dispatchability_requires_explicit_queue_label_and_respects_vetoes():
    assert jd.is_dispatchable(issue(1, "agent-ready"), POLICY)
    assert jd.is_dispatchable(issue(2, "agent:jules-eligible"), POLICY)
    assert not jd.is_dispatchable(
        issue(3, "agent:jules-eligible", author_association="NONE"), POLICY
    )
    assert jd.is_dispatchable(
        issue(30, "agent-ready", author_association="NONE"), POLICY
    )
    assert not jd.is_dispatchable(issue(4, "good first issue"), POLICY)
    assert not jd.is_dispatchable(
        issue(5, "agent-ready", "agent:jules-dispatched"), POLICY
    )
    assert not jd.is_dispatchable(issue(6, "agent-ready", "jules"), POLICY)
    assert not jd.is_dispatchable(issue(7, "agent-ready", "human-required"), POLICY)
    assert not jd.is_dispatchable(issue(8, "agent-ready", "security-sensitive"), POLICY)
    assert not jd.is_dispatchable(issue(9, "agent-ready", state="closed"), POLICY)
    assert not jd.is_dispatchable(issue(10, "agent-ready", pull=True), POLICY)


def test_selection_prefers_event_issue_then_priority_and_small_size():
    queued = [
        issue(10, "agent-ready", "priority:p0", "size:m"),
        issue(11, "agent-ready", "priority:p1", "size:xs"),
        issue(12, "agent-ready", "priority:p2", "size:s"),
    ]

    selected = jd.select_candidates(
        queued,
        POLICY,
        slots=3,
        event_issue_number=12,
        max_dispatch=3,
    )

    assert [item["number"] for item in selected] == [12, 10, 11]


def test_selection_is_bounded_by_slots_and_sweep_limit():
    queued = [
        issue(1, "agent-ready", "priority:p0"),
        issue(2, "agent-ready", "priority:p1"),
        issue(3, "agent-ready", "priority:p2"),
    ]

    assert len(jd.select_candidates(queued, POLICY, slots=1)) == 1
    assert len(jd.select_candidates(queued, POLICY, slots=4)) == 2


def test_dispatch_does_not_exceed_open_jules_capacity():
    api = FakeAPI(
        active=[
            issue(100, "agent:jules-dispatched"),
            issue(101, "agent:jules-dispatched"),
        ],
        legacy=[issue(102, "jules")],
        queued=[
            issue(1, "agent-ready", "priority:p0"),
            issue(2, "agent-ready", "priority:p1"),
        ],
    )
    jules = FakeJules()

    dispatched = jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    )

    assert dispatched == [1]
    assert api.added == [(1, ["agent:jules-dispatched"])]
    assert len(jules.created) == 1
    assert jules.created[0]["source"] == "sources/github/MSKazemi/idkmesh"
    assert jules.created[0]["starting_branch"] == "main"
    assert "approved GitHub issue #1" in jules.created[0]["prompt"]
    assert "official Jules REST API" in api.comments[0][1]

    reused_api = FakeAPI(queued=[issue(7, "agent-ready")])
    reused_jules = FakeJules(
        existing={
            "name": "sessions/existing",
            "url": "https://jules.google.com/session/existing",
            "state": "IN_PROGRESS",
        }
    )
    assert jd.dispatch(
        reused_api,
        POLICY,
        jules_api=reused_jules,
        starting_branch="main",
    ) == [7]
    assert reused_jules.created == []
    assert reused_api.added == [(7, ["agent:jules-dispatched"])]

    retry_api = FakeAPI(queued=[issue(8, "agent-ready")])
    retry_jules = FakeJules(
        create_error=jd.JulesAPIError("bad request", status_code=400)
    )
    with pytest.raises(jd.JulesAPIError):
        jd.dispatch(
            retry_api,
            POLICY,
            jules_api=retry_jules,
            starting_branch="main",
        )
    assert retry_api.removed == [(8, "agent:jules-dispatched")]

def test_dispatch_fails_closed_when_capacity_is_full():
    api = FakeAPI(
        active=[issue(number, "jules") for number in range(100, 104)],
        queued=[issue(1, "agent-ready", "priority:p0")],
    )

    assert jd.dispatch(api, POLICY, jules_api=None, starting_branch="main") == []
    assert api.added == []

    idle = FakeAPI()
    assert jd.dispatch(idle, POLICY, jules_api=None, starting_branch="main") == []
    assert idle.added == []


def test_dispatch_pauses_when_actions_queue_exceeds_policy():
    api = FakeAPI(
        queued=[issue(1, "agent-ready", "priority:p0")],
        queued_runs=13,
        in_progress_runs=1,
    )

    assert jd.dispatch(api, POLICY, jules_api=FakeJules(), starting_branch="main") == []
    assert api.added == []
    assert api.workflow_count_calls == ["queued", "in_progress"]


def test_dispatch_pauses_when_actions_in_progress_exceeds_policy():
    api = FakeAPI(
        queued=[issue(1, "agent-ready", "priority:p0")],
        queued_runs=1,
        in_progress_runs=9,
    )

    assert jd.dispatch(api, POLICY, jules_api=FakeJules(), starting_branch="main") == []
    assert api.added == []


def test_dispatch_allows_counts_exactly_at_backpressure_ceilings():
    api = FakeAPI(
        queued=[issue(1, "agent-ready", "priority:p0")],
        queued_runs=12,
        in_progress_runs=8,
    )

    assert jd.dispatch(api, POLICY, jules_api=FakeJules(), starting_branch="main") == [1]
    assert api.added == [(1, ["agent:jules-dispatched"])]


def test_disabled_ci_backpressure_preserves_previous_behavior():
    policy = deepcopy(POLICY)
    policy["ci_backpressure"]["enabled"] = False
    api = FakeAPI(
        queued=[issue(1, "agent-ready", "priority:p0")],
        queued_runs=999,
        in_progress_runs=999,
    )

    assert jd.dispatch(api, policy, jules_api=FakeJules(), starting_branch="main") == [1]
    assert api.workflow_count_calls == []


def test_actions_capacity_signal_failure_fails_closed_before_label_mutation():
    api = FakeAPI(
        queued=[issue(1, "agent-ready", "priority:p0")],
        fail_actions=True,
    )

    try:
        jd.dispatch(api, POLICY, jules_api=FakeJules(), starting_branch="main")
    except jd.DispatchError as exc:
        assert "Actions API" in str(exc)
    else:
        raise AssertionError("dispatch must fail closed when Actions state is unknown")

    assert api.added == []


def test_ensure_labels_creates_only_missing_policy_labels(monkeypatch):
    api = FakeAPI(labels=[{"name": "agent-ready"}, {"name": "jules"}])

    created = jd.ensure_labels(api, POLICY)

    assert created == ["agent:jules-eligible", "agent:jules-dispatched"]
    assert api.created == [
        ("agent:jules-eligible", "BFDADC", "auto-ready"),
        ("agent:jules-dispatched", "5319E7", "dispatch"),
    ]

    client = jd.JulesAPI("secret")
    monkeypatch.setattr(
        client,
        "list_sources",
        lambda: [
            {
                "name": "sources/github/MSKazemi/idkmesh",
                "githubRepo": {"owner": "MSKazemi", "repo": "idkmesh"},
            }
        ],
    )
    assert client.resolve_source("MSKazemi/idkmesh") == (
        "sources/github/MSKazemi/idkmesh"
    )

    captured = {}

    def fake_request(method, path, payload=None):
        captured.update(
            {"method": method, "path": path, "payload": deepcopy(payload)}
        )
        return {"name": "sessions/abc", "state": "QUEUED"}

    monkeypatch.setattr(client, "request", fake_request)
    client.create_session(
        source="sources/github/MSKazemi/idkmesh",
        starting_branch="main",
        title="task title",
        prompt="task prompt",
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/sessions"
    assert captured["payload"]["automationMode"] == "AUTO_CREATE_PR"
    assert captured["payload"]["requirePlanApproval"] is False


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_policy_keeps_speed_and_hard_vetoes_explicit():
    policy = jd.load_policy(REPO_ROOT / "config" / "jules-dispatch.json")

    assert policy["automatic_queue_label"] == "agent:jules-eligible"
    assert policy["trusted_author_associations"] == ["OWNER", "MEMBER", "COLLABORATOR"]
    assert policy["dispatch_label"] == "agent:jules-dispatched"
    assert policy["legacy_dispatch_labels"] == ["jules"]
    assert policy["max_in_flight"] == 4
    assert policy["max_dispatch_per_sweep"] == 2
    assert policy["ci_backpressure"] == {
        "enabled": True,
        "max_queued_runs": 96,
        "max_in_progress_runs": 24,
    }
    assert {
        "human-required",
        "research-evidence",
        "security-sensitive",
        "needs-decomposition",
        "do-not-automate",
    }.issubset(set(policy["blocked_labels"]))


def test_workflow_preserves_dispatch_trust_boundary_and_fast_recovery():
    workflow = (REPO_ROOT / ".github" / "workflows" / "jules-dispatch.yml").read_text(
        encoding="utf-8"
    )

    assert "types: [opened, edited, reopened, labeled, closed]" in workflow
    assert "cron: '17,47 * * * *'" in workflow
    assert "actions: read" in workflow
    assert "JULES_API_KEY: ${{ secrets.JULES_API_KEY }}" in workflow
    assert (
        "GITHUB_DEFAULT_BRANCH: "
        "${{ github.event.repository.default_branch }}" in workflow
    )
    assert "contents: read" in workflow
    assert "issues: write" in workflow
    assert "actions: write" not in workflow
    assert "contents: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "pull_request_target:" not in workflow
    assert "pull_request:" not in workflow
    assert "ref: ${{ github.event.repository.default_branch }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "github.event.issue.body" not in workflow
    assert "github.event.issue.title" not in workflow
