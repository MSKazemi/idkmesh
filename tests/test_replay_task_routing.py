import copy
import importlib.util
import sys
from pathlib import Path

SIM_PATH = Path(__file__).parents[1] / "sim" / "aco_stigmergy_sim.py"
sim_spec = importlib.util.spec_from_file_location("aco_stigmergy_sim", SIM_PATH)
sim = importlib.util.module_from_spec(sim_spec)
sys.modules[sim_spec.name] = sim
assert sim_spec.loader is not None
sim_spec.loader.exec_module(sim)

HYBRID_PATH = Path(__file__).parents[1] / "sim" / "homeostatic_stigmergy_sim.py"
hybrid_spec = importlib.util.spec_from_file_location("homeostatic_stigmergy_sim", HYBRID_PATH)
hybrid = importlib.util.module_from_spec(hybrid_spec)
sys.modules[hybrid_spec.name] = hybrid
assert hybrid_spec.loader is not None
hybrid_spec.loader.exec_module(hybrid)

REPLAY_PATH = Path(__file__).parents[1] / "sim" / "replay_task_routing.py"
replay_spec = importlib.util.spec_from_file_location("replay_task_routing", REPLAY_PATH)
replay = importlib.util.module_from_spec(replay_spec)
sys.modules[replay_spec.name] = replay
assert replay_spec.loader is not None
replay_spec.loader.exec_module(replay)


def dataset():
    return {
        "schema_version": "0.1.0",
        "dataset_id": "test-replay",
        "repository": {"full_name": "example/repo"},
        "annotation_policy": {
            "method": "test fixture",
            "hindsight_rule": "outcomes unavailable to routing inputs",
        },
        "tasks": [
            {
                "id": "task-a",
                "source_ref": "issue:1",
                "skill": "code",
                "impact": 0.9,
                "information_gain": 0.7,
                "review_cost": 0.2,
                "compute_cost": 0.2,
                "risk": 0.2,
                "accessibility": 0.7,
            },
            {
                "id": "task-b",
                "source_ref": "issue:2",
                "skill": "docs",
                "impact": 0.6,
                "information_gain": 0.8,
                "review_cost": 0.1,
                "compute_cost": 0.05,
                "risk": 0.05,
                "accessibility": 1.0,
            },
        ],
        "workers": [
            {
                "id": "worker-1",
                "group": "family-a",
                "skills": {"code": 0.9, "docs": 0.4},
            }
        ],
        "snapshots": [
            {
                "id": "s1",
                "observed_at": "2026-01-01T00:00:00Z",
                "available_task_ids": ["task-a", "task-b"],
                "available_worker_ids": ["worker-1"],
                "active_attempts": [],
                "evidence": [],
                "observed_duplicate_rate": 0.1,
                "observed_concentration": 0.2,
                "retrospective_outcomes": {
                    "task-a": {"verified_utility": 1.0, "eventual_verified": True},
                    "task-b": {"verified_utility": 0.2, "eventual_verified": True},
                },
            },
            {
                "id": "s2",
                "observed_at": "2026-01-02T00:00:00Z",
                "available_task_ids": ["task-a", "task-b"],
                "available_worker_ids": ["worker-1"],
                "active_attempts": [
                    {"task_id": "task-a", "worker_group": "family-a"}
                ],
                "evidence": [
                    {
                        "task_id": "task-b",
                        "verified": True,
                        "quality": 0.8,
                        "verification_strength": 0.9,
                        "diversity": 1.0,
                        "descendant_value": 0.8,
                        "human_review_cost": 0.1,
                        "compute_cost": 0.05,
                        "penalty": 0.0,
                    }
                ],
                "observed_duplicate_rate": 0.4,
                "observed_concentration": 0.6,
                "retrospective_outcomes": {
                    "task-a": {"verified_utility": 0.4, "eventual_verified": True},
                    "task-b": {"verified_utility": 0.9, "eventual_verified": True},
                },
            },
        ],
        "limitations": ["test fixture only"],
    }


def recommendations(result):
    return [
        snapshot["workers"][0]["recommendations"]
        for snapshot in result["snapshots"]
    ]


def test_replay_is_deterministic():
    first = replay.replay(dataset())
    second = replay.replay(dataset())
    assert first == second


def test_retrospective_outcomes_cannot_change_recommendations():
    original = dataset()
    changed = copy.deepcopy(original)
    for snapshot in changed["snapshots"]:
        for outcome in snapshot["retrospective_outcomes"].values():
            outcome["verified_utility"] = 999.0 - float(outcome["verified_utility"])
            outcome["eventual_verified"] = not outcome["eventual_verified"]

    assert recommendations(replay.replay(original)) == recommendations(replay.replay(changed))


def test_known_verified_evidence_reinforces_pheromone():
    result = replay.replay(dataset())
    first = result["snapshots"][0]["pheromone"]
    second = result["snapshots"][1]["pheromone"]
    # Both paths evaporate, but task-b receives a verified deposit at s2.
    assert second["task-b"] > second["task-a"]
    assert first["task-a"] == first["task-b"]


def test_homeostatic_regulation_responds_to_observed_pressure():
    result = replay.replay(dataset())
    first = result["snapshots"][0]
    second = result["snapshots"][1]
    assert first["homeostatic_regulation_after"] < first["homeostatic_regulation_before"]
    assert second["homeostatic_regulation_after"] > second["homeostatic_regulation_before"]


def test_replay_reports_heldout_evaluation_after_decisions():
    result = replay.replay(dataset())
    assert result["decisions"] == 2
    assert set(result["mean_heldout_verified_utility_of_top_recommendation"]) == {
        "capability",
        "aco",
        "homeostatic",
    }
    assert "retrospective_outcomes are read only after" in result["anti_hindsight_invariant"]
