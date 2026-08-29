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


def test_regulation_increases_under_overload():
    config = hybrid.HomeostaticConfig()
    updated = hybrid.update_regulation(
        value=0.4,
        duplicate_rate=0.60,
        concentration=0.70,
        config=config,
    )
    assert updated > 0.4


def test_regulation_relaxes_when_system_is_below_targets():
    config = hybrid.HomeostaticConfig()
    updated = hybrid.update_regulation(
        value=1.0,
        duplicate_rate=0.02,
        concentration=0.15,
        config=config,
    )
    assert config.lambda_min <= updated < 1.0


def test_hybrid_probabilities_are_normalized():
    rng = sim.random.Random(4)
    worker = sim.make_workers(1, rng)[0]
    config = hybrid.HomeostaticConfig()
    pheromone = {task.name: 1.0 for task in sim.TASKS}
    attempts = {task.name: 0 for task in sim.TASKS}
    probs = hybrid.probabilities(
        worker,
        sim.TASKS,
        pheromone,
        attempts,
        {},
        regulation=config.lambda_initial,
        config=config,
    )
    assert all(p > 0.0 for p in probs)
    assert abs(sum(probs) - 1.0) < 1e-12


def test_same_seed_is_deterministic():
    first = hybrid.run_hybrid(seed=12, workers=10, epochs=6)
    second = hybrid.run_hybrid(seed=12, workers=10, epochs=6)
    assert first == second


def test_comparison_reports_all_three_strategies():
    result = hybrid.run_comparison(seed_start=1, seeds=2, workers=8, epochs=4)
    assert set(result["summary"]) == {"capability", "aco", "homeostatic-hybrid"}
    for row in result["summary"].values():
        assert row["verified_utility_per_cost"] >= 0.0
        assert 0.0 <= row["duplicate_rate"] <= 1.0
        assert 0.0 <= row["max_selection_share"] <= 1.0
        assert 0.0 <= row["task_coverage"] <= len(sim.TASKS)
