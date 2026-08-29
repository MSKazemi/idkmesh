import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "aco_stigmergy_sim.py"
spec = importlib.util.spec_from_file_location("aco_stigmergy_sim", MODULE_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_same_seed_is_deterministic():
    a = sim.run("all", seed=17, workers=18, epochs=12)
    b = sim.run("all", seed=17, workers=18, epochs=12)
    assert a == b


def test_aco_probabilities_are_normalized_and_positive():
    rng = sim.random.Random(3)
    worker = sim.make_workers(1, rng)[0]
    config = sim.ACOConfig()
    pheromone = {task.name: 1.0 for task in sim.TASKS}
    attempts = {task.name: 0 for task in sim.TASKS}
    groups = {}

    probabilities = sim.aco_probabilities(
        worker, sim.TASKS, pheromone, attempts, groups, config
    )

    assert len(probabilities) == len(sim.TASKS)
    assert all(probability > 0.0 for probability in probabilities)
    assert abs(sum(probabilities) - 1.0) < 1e-12


def test_pheromone_evaporates_without_evidence():
    config = sim.ACOConfig(rho=0.20, tau_min=0.1, tau_max=4.0)
    updated = sim.update_pheromone(1.0, deposit=0.0, penalty=0.0, config=config)
    assert abs(updated - 0.8) < 1e-12


def test_verified_deposit_can_increase_pheromone():
    config = sim.ACOConfig(rho=0.10, tau_min=0.1, tau_max=4.0)
    updated = sim.update_pheromone(1.0, deposit=0.5, penalty=0.0, config=config)
    assert updated > 1.0


def test_pheromone_bounds_prevent_starvation_and_runaway():
    config = sim.ACOConfig(rho=0.50, tau_min=0.2, tau_max=2.0)
    assert sim.update_pheromone(0.2, 0.0, 100.0, config) == 0.2
    assert sim.update_pheromone(2.0, 100.0, 0.0, config) == 2.0


def test_congestion_and_correlation_reduce_local_desirability():
    rng = sim.random.Random(9)
    worker = sim.make_workers(1, rng)[0]
    task = sim.TASKS[0]
    config = sim.ACOConfig()

    clear = sim.heuristic(worker, task, attempt_count=0, same_group_attempts=0, config=config)
    crowded = sim.heuristic(worker, task, attempt_count=5, same_group_attempts=2, config=config)

    assert crowded < clear


def test_all_strategies_return_bounded_metrics():
    result = sim.run("all", seed=7, workers=12, epochs=8)
    names = {row["strategy"] for row in result["results"]}
    assert names == {"random", "greedy", "capability", "aco"}

    for row in result["results"]:
        assert row["attempts"] == 96
        assert 0 <= row["verified_count"] <= row["attempts"]
        assert 0.0 <= row["duplicate_rate"] <= 1.0
        assert 0.0 <= row["max_selection_share"] <= 1.0
        assert 0 <= row["task_coverage"] <= len(sim.TASKS)
        assert row["review_cost"] > 0.0
        assert row["compute_cost"] > 0.0
