from __future__ import annotations

from copy import deepcopy

from tools import jules_dispatcher as jd


POLICY = {
    "queue_label": "agent-ready",
    "dispatch_label": "jules",
    "max_in_flight": 4,
    "max_dispatch_per_sweep": 2,
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
        "jules": {"color": "EDEDED", "description": "dispatch"},
    },
}


def issue(number: int, *labels: str, state: str = "open", pull: bool = False):
    payload = {
        "number": number,
        "state": state,
        "labels": [{"name": label} for label in labels],
    }
    if pull:
        payload["pull_request"] = {"url": "https://example.invalid/pr"}
    return payload


class FakeAPI:
    def __init__(self, *, active=None, queued=None, labels=None):
        self.active = list(active or [])
        self.queued = list(queued or [])
        self.labels = list(labels or [])
        self.added = []
        self.created = []

    def list_open_issues(self, label: str):
        if label == "jules":
            return deepcopy(self.active)
        if label == "agent-ready":
            return deepcopy(self.queued)
        return []

    def add_labels(self, issue_number: int, labels: list[str]):
        self.added.append((issue_number, list(labels)))

    def list_labels(self):
        return deepcopy(self.labels)

    def create_label(self, name: str, color: str, description: str):
        self.created.append((name, color, description))


def test_dispatchability_requires_explicit_queue_label_and_respects_vetoes():
    assert jd.is_dispatchable(issue(1, "agent-ready"), POLICY)
    assert not jd.is_dispatchable(issue(2, "good first issue"), POLICY)
    assert not jd.is_dispatchable(issue(3, "agent-ready", "jules"), POLICY)
    assert not jd.is_dispatchable(issue(4, "agent-ready", "human-required"), POLICY)
    assert not jd.is_dispatchable(issue(5, "agent-ready", "security-sensitive"), POLICY)
    assert not jd.is_dispatchable(issue(6, "agent-ready", state="closed"), POLICY)
    assert not jd.is_dispatchable(issue(7, "agent-ready", pull=True), POLICY)


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
            issue(100, "jules"),
            issue(101, "jules"),
            issue(102, "jules"),
        ],
        queued=[
            issue(1, "agent-ready", "priority:p0"),
            issue(2, "agent-ready", "priority:p1"),
        ],
    )

    dispatched = jd.dispatch(api, POLICY)

    assert dispatched == [1]
    assert api.added == [(1, ["jules"])]


def test_dispatch_fails_closed_when_capacity_is_full():
    api = FakeAPI(
        active=[issue(number, "jules") for number in range(100, 104)],
        queued=[issue(1, "agent-ready", "priority:p0")],
    )

    assert jd.dispatch(api, POLICY) == []
    assert api.added == []


def test_ensure_labels_creates_only_missing_policy_labels():
    api = FakeAPI(labels=[{"name": "agent-ready"}])

    created = jd.ensure_labels(api, POLICY)

    assert created == ["jules"]
    assert api.created == [("jules", "EDEDED", "dispatch")]
