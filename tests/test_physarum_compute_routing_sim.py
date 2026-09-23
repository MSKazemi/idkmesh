import importlib.util
import sys
from pathlib import Path

SIM_PATH = Path(__file__).parents[1] / "sim" / "physarum_compute_routing_sim.py"
spec = importlib.util.spec_from_file_location(
    "physarum_compute_routing_sim",
    SIM_PATH,
)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_paths_are_simple_and_reach_worker():
    paths = sim.enumerate_paths()
    assert paths
    for path in paths:
        assert path[0] == "coordinator"
        assert path[-1] == "worker"
        assert len(path) == len(set(path))


def test_shortest_path_is_expected_corridor_a():
    paths = sim.enumerate_paths()
    shortest = min(
        paths,
        key=lambda path: (sim.path_length(path), path),
    )
    assert shortest == ("coordinator", "a", "worker")
    assert sim.path_length(shortest) == 2.0


def test_successful_path_reinforces_used_edges():
    config = sim.Config(evaporation=0.10, deposit_gain=1.0)
    conductance = {
        sim.key(edge.a, edge.b): 1.0
        for edge in sim.EDGES
    }
    path = ("coordinator", "a", "worker")
    used = set(sim.path_edges(path))
    sim.update_conductance(
        conductance,
        path,
        True,
        (),
        config,
    )
    assert all(conductance[edge] > 0.9 for edge in used)
    unused = next(edge for edge in conductance if edge not in used)
    assert conductance[unused] == 0.9


def test_failed_edge_is_penalized():
    config = sim.Config()
    conductance = {
        sim.key(edge.a, edge.b): 1.0
        for edge in sim.EDGES
    }
    path = ("coordinator", "a", "worker")
    failed = (sim.key("coordinator", "a"),)
    sim.update_conductance(
        conductance,
        path,
        False,
        failed,
        config,
    )
    assert conductance[failed[0]] < 0.9


def test_same_seed_is_deterministic():
    first = sim.run_strategy(
        "physarum",
        seed=5,
        epochs=20,
        tasks_per_epoch=8,
    )
    second = sim.run_strategy(
        "physarum",
        seed=5,
        epochs=20,
        tasks_per_epoch=8,
    )
    assert first == second


def test_comparison_contains_strong_adaptive_baseline():
    result = sim.compare(
        seed_start=1,
        seeds=2,
        epochs=12,
        tasks_per_epoch=6,
    )
    assert set(result["summary"]) == {
        "shortest-static",
        "reliability-greedy",
        "epsilon-greedy",
        "thompson-path",
        "physarum",
    }


def test_physarum_recovers_better_than_static_after_shift_fixture():
    physarum = sim.run_strategy(
        "physarum",
        seed=3,
        epochs=80,
        tasks_per_epoch=20,
    )
    static = sim.run_strategy(
        "shortest-static",
        seed=3,
        epochs=80,
        tasks_per_epoch=20,
    )
    assert (
        physarum["post_shift_success_rate"]
        > static["post_shift_success_rate"]
    )
    assert physarum["max_path_share"] < static["max_path_share"]
