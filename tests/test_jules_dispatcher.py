from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path

import pytest

from tools import jules_dispatcher as jd


POLICY = {
    "queue_label": "agent-ready",
    "automatic_queue_label": "agent:jules-eligible",
    "trusted_author_associations": ["OWNER", "MEMBER", "COLLABORATOR"],
    "dispatch_label": "agent:jules-dispatched",
    "legacy_dispatch_labels": ["jules"],
    "attention_label": "agent:jules-needs-attention",
    "attention_session_states": [
        "FAILED",
        "AWAITING_PLAN_APPROVAL",
        "AWAITING_USER_FEEDBACK",
        "PAUSED",
        "STATE_UNSPECIFIED",
    ],
    "stale_session_minutes": {
        "QUEUED": 120,
        "PLANNING": 180,
        "IN_PROGRESS": 360,
    },
    "stale_missing_session_minutes": 60,
    "session_scan_max_pages": 10,
    "max_in_flight": 4,
    "provider_concurrency": {
        "max_concurrent_tasks": 3,
        "plan": "Jules",
        "source": "https://jules.google/docs/usage-limits",
        "terminal_session_states": ["COMPLETED", "FAILED"],
        "session_state_source": "https://jules.google/docs/api/reference/types/",
        "checked_at": "2026-09-23",
    },
    "max_dispatch_per_sweep": 2,
    "blocked_labels": [
        "blocked",
        "do-not-automate",
        "human-required",
        "needs-decomposition",
        "research-evidence",
        "security-sensitive",
        "agent:jules-needs-attention",
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
        "agent:jules-needs-attention": {
            "color": "D93F0B",
            "description": "attention",
        },
        "jules": {"color": "EDEDED", "description": "legacy"},
    },
}


def issue(
    number: int,
    *labels: str,
    state: str = "open",
    pull: bool = False,
    author_association: str = "OWNER",
    updated_at: str = "2026-09-23T12:00:00Z",
):
    payload = {
        "number": number,
        "state": state,
        "title": f"issue {number}",
        "body": "bounded task body",
        "html_url": f"https://github.com/MSKazemi/idkmesh/issues/{number}",
        "author_association": author_association,
        "updated_at": updated_at,
        "labels": [{"name": label} for label in labels],
    }
    if pull:
        payload["pull_request"] = {"url": "https://example.invalid/pr"}
    return payload


class FakeAPI:
    def __init__(self, *, issues=None, labels=None):
        self.repository = "MSKazemi/idkmesh"
        self.issues = deepcopy(list(issues or []))
        self.labels = list(labels or [])
        self.list_open_issues_calls = []
        self.added = []
        self.removed = []
        self.comments = []
        self.created = []

    def list_open_issues(self, label: str | None = None):
        self.list_open_issues_calls.append(label)
        rows = [
            item
            for item in self.issues
            if item.get("state") == "open"
            and (
                label is None
                or label.casefold() in jd.label_names(item)
            )
        ]
        return deepcopy(rows)

    def add_labels(self, issue_number: int, labels: list[str]):
        self.added.append((issue_number, list(labels)))
        for item in self.issues:
            if int(item["number"]) == issue_number:
                existing = jd.label_names(item)
                for label in labels:
                    if label.casefold() not in existing:
                        item["labels"].append({"name": label})

    def remove_label(self, issue_number: int, label: str):
        self.removed.append((issue_number, label))
        for item in self.issues:
            if int(item["number"]) == issue_number:
                item["labels"] = [
                    value
                    for value in item.get("labels", [])
                    if str(value.get("name", "")).casefold() != label.casefold()
                ]

    def add_comment(self, issue_number: int, body: str):
        self.comments.append((issue_number, body))

    def list_labels(self):
        return deepcopy(self.labels)

    def create_label(self, name: str, color: str, description: str):
        self.created.append((name, color, description))


class FakeJules:
    def __init__(self, *, sessions=None, create_error=None):
        self.sessions = deepcopy(list(sessions or []))
        self.create_error = create_error
        self.resolved = []
        self.created = []
        self.list_calls = 0

    def resolve_source(self, repository: str):
        self.resolved.append(repository)
        return "sources/github/MSKazemi/idkmesh"

    def list_sessions(self, *, max_pages: int = 3):
        self.list_calls += 1
        return deepcopy(self.sessions)

    def create_session(self, **kwargs):
        self.created.append(deepcopy(kwargs))
        if self.create_error:
            raise self.create_error
        session = {
            "name": f"sessions/{len(self.created)}",
            "url": f"https://jules.google.com/session/{len(self.created)}",
            "title": kwargs["title"],
            "state": "QUEUED",
            "createTime": "2026-09-23T18:00:00Z",
            "updateTime": "2026-09-23T18:00:00Z",
        }
        self.sessions.append(deepcopy(session))
        return session


def test_dispatchability_supports_manual_and_trusted_automatic_queues():
    assert jd.is_dispatchable(issue(1, "agent-ready", author_association="NONE"), POLICY)
    assert jd.is_dispatchable(issue(2, "agent:jules-eligible"), POLICY)
    assert not jd.is_dispatchable(
        issue(3, "agent:jules-eligible", author_association="NONE"),
        POLICY,
    )
    assert not jd.is_dispatchable(issue(4, "good first issue"), POLICY)
    assert not jd.is_dispatchable(
        issue(5, "agent:jules-eligible", "agent:jules-needs-attention"),
        POLICY,
    )
    assert not jd.is_dispatchable(
        issue(6, "agent-ready", "agent:jules-dispatched"),
        POLICY,
    )
    assert not jd.is_dispatchable(issue(7, "agent-ready", state="closed"), POLICY)
    assert not jd.is_dispatchable(issue(8, "agent-ready", pull=True), POLICY)


def test_selection_prefers_event_issue_then_priority_and_small_size():
    queued = [
        issue(10, "agent-ready", "priority:p0", "size:m"),
        issue(11, "agent:jules-eligible", "priority:p1", "size:xs"),
        issue(12, "agent:jules-eligible", "priority:p2", "size:s"),
    ]
    selected = jd.select_candidates(
        queued,
        POLICY,
        slots=3,
        event_issue_number=12,
        max_dispatch=3,
    )
    assert [item["number"] for item in selected] == [12, 10, 11]


def test_dispatch_uses_one_issue_snapshot_and_one_session_snapshot():
    issues = [
        issue(100, "agent:jules-dispatched"),
        issue(101, "jules"),
        issue(1, "agent:jules-eligible", "priority:p0"),
        issue(2, "agent-ready", "priority:p1"),
    ]
    api = FakeAPI(issues=issues)
    jules = FakeJules()

    dispatched = jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    )

    # The provider cap is three; two existing dispatch labels leave one slot.
    assert dispatched == [1]
    assert api.list_open_issues_calls == [None]
    assert jules.list_calls == 1
    assert api.added == [
        (1, ["agent:jules-dispatched"]),
    ]
    assert len(jules.created) == 1


def test_dispatch_fails_closed_when_capacity_is_full():
    api = FakeAPI(
        issues=[
            issue(number, "agent:jules-dispatched")
            for number in range(100, 104)
        ]
        + [issue(1, "agent:jules-eligible")]
    )

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=FakeJules(),
        starting_branch="main",
    ) == []
    assert api.added == []


def test_existing_api_session_is_reused_instead_of_duplicated():
    queued = issue(7, "agent-ready")
    existing = {
        "name": "sessions/existing",
        "url": "https://jules.google.com/session/existing",
        "title": jd.session_title("MSKazemi/idkmesh", queued),
        "state": "IN_PROGRESS",
    }
    api = FakeAPI(issues=[queued])
    jules = FakeJules(sessions=[existing])

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    ) == [7]
    assert jules.created == []
    assert "existing" in api.comments[0][1]


def test_newest_matching_session_wins_over_old_failed_history():
    queued = issue(72, "agent-ready")
    marker = jd.session_marker("MSKazemi/idkmesh", queued)
    sessions = [
        {
            "name": "sessions/old-failed",
            "title": f"{marker} old title",
            "state": "FAILED",
            "updateTime": "2026-09-23T14:00:00Z",
        },
        {
            "name": "sessions/new-active",
            "title": f"{marker} new title",
            "state": "IN_PROGRESS",
            "updateTime": "2026-09-23T17:00:00Z",
        },
    ]

    assert jd.find_issue_session("MSKazemi/idkmesh", queued, sessions)["name"] == (
        "sessions/new-active"
    )


def test_existing_session_match_survives_issue_title_edit():
    queued = issue(70, "agent-ready")
    old_title = deepcopy(queued)
    old_title["title"] = "old issue title"
    existing = {
        "name": "sessions/existing-old-title",
        "url": "https://jules.google.com/session/existing-old-title",
        "title": jd.session_title("MSKazemi/idkmesh", old_title),
        "state": "IN_PROGRESS",
    }
    queued["title"] = "new issue title after dispatch"
    api = FakeAPI(issues=[queued])
    jules = FakeJules(sessions=[existing])

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    ) == [70]
    assert jules.created == []
    assert "existing-old-title" in api.comments[0][1]


def test_reconcile_session_match_survives_issue_title_edit():
    active = issue(71, "agent:jules-dispatched")
    original = deepcopy(active)
    original["title"] = "title at dispatch time"
    session = {
        "name": "sessions/title-edit",
        "title": jd.session_title("MSKazemi/idkmesh", original),
        "state": "IN_PROGRESS",
        "updateTime": "2026-09-23T17:59:00Z",
    }
    active["title"] = "later edited title"
    api = FakeAPI(issues=[active])

    assert jd.reconcile_active_sessions(
        api,
        POLICY,
        jules_api=FakeJules(sessions=[session]),
        now=NOW,
    ) == []
    assert api.added == []
    assert api.removed == []


def test_failed_existing_session_does_not_block_explicit_retry():
    queued = issue(8, "agent-ready")
    failed = {
        "name": "sessions/failed",
        "url": "https://jules.google.com/session/failed",
        "title": jd.session_title("MSKazemi/idkmesh", queued),
        "state": "FAILED",
    }
    api = FakeAPI(issues=[queued])
    jules = FakeJules(sessions=[failed])

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    ) == [8]
    assert len(jules.created) == 1


def test_client_error_rolls_back_status_for_safe_retry():
    api = FakeAPI(issues=[issue(9, "agent-ready")])
    jules = FakeJules(
        create_error=jd.JulesAPIError("bad request", status_code=400)
    )

    with pytest.raises(jd.JulesAPIError):
        jd.dispatch(
            api,
            POLICY,
            jules_api=jules,
            starting_branch="main",
        )

    assert api.removed == [(9, "agent:jules-dispatched")]


def test_ambiguous_provider_error_keeps_status_to_prevent_duplicate():
    api = FakeAPI(issues=[issue(10, "agent-ready")])
    jules = FakeJules(create_error=jd.JulesAPIError("connection reset"))

    with pytest.raises(jd.JulesAPIError):
        jd.dispatch(
            api,
            POLICY,
            jules_api=jules,
            starting_branch="main",
        )

    assert api.removed == []
    assert "prevent an automatic duplicate session" in api.comments[0][1]


NOW = datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc)


def test_reconcile_failed_session_blocks_retry_and_frees_capacity():
    active = issue(50, "agent:jules-dispatched")
    session = {
        "name": "sessions/failed",
        "url": "https://jules.google.com/session/failed",
        "title": jd.session_title("MSKazemi/idkmesh", active),
        "state": "FAILED",
        "updateTime": "2026-09-23T17:59:00Z",
    }
    api = FakeAPI(issues=[active])

    attention = jd.reconcile_active_sessions(
        api,
        POLICY,
        jules_api=FakeJules(sessions=[session]),
        now=NOW,
    )

    assert attention == [50]
    assert api.added == [(50, ["agent:jules-needs-attention"])]
    assert api.removed == [(50, "agent:jules-dispatched")]
    assert "FAILED" in api.comments[0][1]


def test_reconcile_marks_stale_queued_session_but_not_fresh_session():
    stale = issue(51, "agent:jules-dispatched")
    fresh = issue(52, "agent:jules-dispatched")
    sessions = [
        {
            "name": "sessions/stale",
            "title": jd.session_title("MSKazemi/idkmesh", stale),
            "state": "QUEUED",
            "updateTime": "2026-09-23T15:00:00Z",
        },
        {
            "name": "sessions/fresh",
            "title": jd.session_title("MSKazemi/idkmesh", fresh),
            "state": "QUEUED",
            "updateTime": "2026-09-23T17:30:00Z",
        },
    ]
    api = FakeAPI(issues=[stale, fresh])

    attention = jd.reconcile_active_sessions(
        api,
        POLICY,
        jules_api=FakeJules(sessions=sessions),
        now=NOW,
    )

    assert attention == [51]
    assert api.removed == [(51, "agent:jules-dispatched")]


def test_reconcile_marks_missing_session_after_grace_period():
    active = issue(
        53,
        "agent:jules-dispatched",
        updated_at="2026-09-23T16:00:00Z",
    )
    api = FakeAPI(issues=[active])

    assert jd.reconcile_active_sessions(
        api,
        POLICY,
        jules_api=FakeJules(),
        now=NOW,
    ) == [53]
    assert "no matching Jules session" in api.comments[0][1]


def test_reconcile_then_dispatch_backfills_freed_slot_in_same_snapshot():
    failed = issue(60, "agent:jules-dispatched")
    open_issues = [
        failed,
        issue(61, "agent:jules-dispatched", updated_at="2026-09-23T17:30:00Z"),
        issue(62, "agent:jules-dispatched", updated_at="2026-09-23T17:30:00Z"),
        issue(1, "agent:jules-eligible", "priority:p0"),
    ]
    failed_session = {
        "name": "sessions/failed",
        "title": jd.session_title("MSKazemi/idkmesh", failed),
        "state": "FAILED",
        "updateTime": "2026-09-23T17:50:00Z",
    }
    api = FakeAPI(issues=open_issues)
    jules = FakeJules(sessions=[failed_session])
    snapshot = deepcopy(open_issues)
    sessions = jules.list_sessions()

    assert jd.reconcile_active_sessions(
        api,
        POLICY,
        jules_api=jules,
        open_issues=snapshot,
        sessions=sessions,
        now=NOW,
    ) == [60]
    assert jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
        open_issues=snapshot,
        sessions=sessions,
    ) == [1]


def test_ensure_labels_creates_new_queue_and_attention_labels():
    api = FakeAPI(labels=[{"name": "agent-ready"}, {"name": "jules"}])

    created = jd.ensure_labels(api, POLICY)

    assert set(created) == {
        "agent:jules-eligible",
        "agent:jules-dispatched",
        "agent:jules-needs-attention",
    }


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_policy_keeps_speed_and_hard_vetoes_explicit():
    policy = jd.load_policy(REPO_ROOT / "config" / "jules-dispatch.json")

    assert policy["automatic_queue_label"] == "agent:jules-eligible"
    assert policy["trusted_author_associations"] == [
        "OWNER",
        "MEMBER",
        "COLLABORATOR",
    ]
    assert policy["attention_label"] == "agent:jules-needs-attention"
    assert policy["stale_session_minutes"]["QUEUED"] == 120
    assert policy["session_scan_max_pages"] == 10
    assert policy["max_in_flight"] == 4
    assert policy["provider_concurrency"]["max_concurrent_tasks"] == 3
    assert policy["provider_concurrency"]["plan"] == "Jules"
    assert policy["provider_concurrency"]["source"] == "https://jules.google/docs/usage-limits"
    assert policy["provider_concurrency"]["terminal_session_states"] == [
        "COMPLETED",
        "FAILED",
    ]
    assert (
        policy["provider_concurrency"]["session_state_source"]
        == "https://jules.google/docs/api/reference/types/"
    )
    assert jd.effective_in_flight_limit(policy) == 3
    assert policy["max_dispatch_per_sweep"] == 2
    assert "agent:jules-needs-attention" in policy["blocked_labels"]


def test_provider_capacity_is_independent_from_repository_reservations():
    provider_full = FakeAPI(
        issues=[
            issue(1, "agent:jules-dispatched"),
            issue(4, "agent:jules-eligible"),
        ]
    )
    active_sessions = [
        {"name": "sessions/a", "title": "other task a", "state": "QUEUED"},
        {"name": "sessions/b", "title": "other task b", "state": "PLANNING"},
        {"name": "sessions/c", "title": "other task c", "state": "IN_PROGRESS"},
    ]
    active_jules = FakeJules(sessions=active_sessions)

    assert jd.effective_in_flight_limit(POLICY) == 3
    assert jd.provider_active_session_count(POLICY, active_sessions) == 3
    assert jd.dispatch(
        provider_full,
        POLICY,
        jules_api=active_jules,
        starting_branch="main",
    ) == []
    assert provider_full.added == []
    assert active_jules.created == []

    completed_reservations = FakeAPI(
        issues=[
            issue(1, "agent:jules-dispatched"),
            issue(2, "agent:jules-dispatched"),
            issue(3, "agent:jules-dispatched"),
            issue(4, "agent:jules-eligible"),
        ]
    )
    terminal_sessions = [
        {"name": "sessions/1", "title": "old task 1", "state": "COMPLETED"},
        {"name": "sessions/2", "title": "old task 2", "state": "COMPLETED"},
        {"name": "sessions/3", "title": "old task 3", "state": "FAILED"},
    ]
    terminal_jules = FakeJules(sessions=terminal_sessions)

    assert jd.provider_active_session_count(POLICY, terminal_sessions) == 0
    assert jd.dispatch(
        completed_reservations,
        POLICY,
        jules_api=terminal_jules,
        starting_branch="main",
    ) == [4]
    assert completed_reservations.added == [(4, ["agent:jules-dispatched"])]
    assert len(terminal_jules.created) == 1


def test_provider_failed_precondition_defers_without_failing():
    api = FakeAPI(issues=[issue(1, "agent:jules-eligible")])
    jules = FakeJules(
        create_error=jd.JulesAPIError(
            "provider concurrency full",
            status_code=400,
            api_status="FAILED_PRECONDITION",
        )
    )

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=jules,
        starting_branch="main",
    ) == []
    assert api.added == [(1, ["agent:jules-dispatched"])]
    assert api.removed == [(1, "agent:jules-dispatched")]
    assert api.comments == []


def test_jules_http_error_preserves_provider_status(monkeypatch):
    payload = io.BytesIO(
        b'{"error":{"code":400,"message":"Precondition check failed.",'
        b'"status":"FAILED_PRECONDITION"}}'
    )
    error = jd.urllib.error.HTTPError(
        "https://jules.googleapis.com/v1alpha/sessions",
        400,
        "Bad Request",
        {},
        payload,
    )

    def fail_request(*args, **kwargs):
        raise error

    monkeypatch.setattr(jd.urllib.request, "urlopen", fail_request)

    with pytest.raises(jd.JulesAPIError) as captured:
        jd.JulesAPI("secret").request("POST", "/sessions", {})

    assert captured.value.status_code == 400
    assert captured.value.api_status == "FAILED_PRECONDITION"
    assert jd.is_provider_backpressure(captured.value)


def test_model_routing_policy_uses_dispatcher_label_contract():
    dispatch_policy = jd.load_policy(REPO_ROOT / "config" / "jules-dispatch.json")
    routing_policy = json.loads(
        (REPO_ROOT / "config" / "llm-routing-policy.json").read_text(
            encoding="utf-8"
        )
    )
    jules = routing_policy["provider_examples"]["jules"]

    assert jules["queue_label"] == dispatch_policy["automatic_queue_label"]
    assert jules["execution_status_label"] == dispatch_policy["dispatch_label"]
    assert jules["attention_label"] == dispatch_policy["attention_label"]
    assert jules["manual_fallback_label"] == "jules"


def test_workflow_and_router_share_the_same_dispatch_contract():
    workflow = (REPO_ROOT / ".github" / "workflows" / "jules-dispatch.yml").read_text(
        encoding="utf-8"
    )
    router = (
        REPO_ROOT / ".github" / "workflows" / "issue-model-router.yml"
    ).read_text(encoding="utf-8")
    pr_gate = (REPO_ROOT / ".github" / "workflows" / "pr-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_call:" in workflow
    assert workflow.count("issue_number:") >= 2
    assert "inputs.issue_number" in workflow
    assert "agent:jules-eligible" in workflow
    assert "--reconcile" in workflow
    assert "inputs.bootstrap_labels" in workflow
    assert "uses: ./.github/workflows/jules-dispatch.yml" in router
    assert "issue_number: ${{ needs.route.outputs.routed_issue_number }}" in router
    assert "secrets: inherit" in router
    assert "gh workflow run jules-dispatch.yml" not in router
    assert "actions: write" not in router
    assert 'dispatch_policy["automatic_queue_label"]' in router
    assert "python tools/check_jules_contract.py" in pr_gate
    assert "python tools/check_jules_contract.py" in router
    assert "python tools/check_jules_contract.py" in workflow
    assert "dispatch-after-control-plane-change:" in router
    assert "bootstrap_labels: true" in router
    assert "\n  push:\n" not in workflow
    assert "contents: read" in workflow
    assert "issues: write" in workflow
    assert "pull-requests: write" not in workflow
    assert "pull_request_target:" not in workflow
    assert "persist-credentials: false" in workflow
    assert "github.event.issue.body" not in workflow
    assert "github.event.issue.title" not in workflow


def test_prompt_preserves_issue_context_and_safety_boundary():
    payload = issue(42, "agent-ready")
    payload["title"] = "add tests"
    payload["body"] = "Only touch tests/foo.py"

    prompt = jd.build_jules_prompt("MSKazemi/idkmesh", payload)

    assert "GitHub issue #42" in prompt
    assert "Only touch tests/foo.py" in prompt
    assert "AGENTS.md" in prompt
    assert "human-only evidence" in prompt


def test_dispatch_requires_api_client_for_live_work():
    api = FakeAPI(issues=[issue(1, "agent-ready")])

    with pytest.raises(jd.DispatchError, match="JULES_API_KEY"):
        jd.dispatch(
            api,
            POLICY,
            jules_api=None,
            starting_branch="main",
        )


def test_dry_run_does_not_require_api_key_or_mutate():
    api = FakeAPI(issues=[issue(1, "agent-ready")])

    assert jd.dispatch(
        api,
        POLICY,
        jules_api=None,
        starting_branch="main",
        dry_run=True,
    ) == [1]
    assert api.added == []


def test_create_session_uses_auto_create_pr_and_no_plan_gate(monkeypatch):
    client = jd.JulesAPI("secret")
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


def test_resolve_source_matches_connected_github_repository(monkeypatch):
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
    assert (
        client.resolve_source("MSKazemi/idkmesh")
        == "sources/github/MSKazemi/idkmesh"
    )


def test_list_sessions_paginates_until_complete(monkeypatch):
    client = jd.JulesAPI("secret")
    calls = []

    def fake_request(method, path, payload=None):
        calls.append(path)
        if "pageToken=" not in path:
            return {
                "sessions": [{"name": "sessions/1"}],
                "nextPageToken": "next",
            }
        return {"sessions": [{"name": "sessions/2"}]}

    monkeypatch.setattr(client, "request", fake_request)

    assert [item["name"] for item in client.list_sessions(max_pages=2)] == [
        "sessions/1",
        "sessions/2",
    ]
    assert len(calls) == 2


def test_list_sessions_fails_closed_if_history_scan_is_incomplete(monkeypatch):
    client = jd.JulesAPI("secret")

    monkeypatch.setattr(
        client,
        "request",
        lambda method, path, payload=None: {
            "sessions": [{"name": "sessions/1"}],
            "nextPageToken": "still-more",
        },
    )

    with pytest.raises(jd.JulesAPIError, match="safe pagination scan"):
        client.list_sessions(max_pages=1)


def test_resolve_source_fails_closed_when_repo_is_not_connected(monkeypatch):
    client = jd.JulesAPI("secret")
    monkeypatch.setattr(client, "list_sources", lambda: [])

    with pytest.raises(jd.JulesAPIError, match="connect the repository"):
        client.resolve_source("MSKazemi/idkmesh")
