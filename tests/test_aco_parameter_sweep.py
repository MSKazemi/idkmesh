import importlib.util
import sys
from pathlib import Path

SIM_PATH = Path(__file__).parents[1] / "sim" / "aco_stigmergy_sim.py"
sim_spec = importlib.util.spec_from_file_location("aco_stigmergy_sim", SIM_PATH)
sim = importlib.util.module_from_spec(sim_spec)
sys.modules[sim_spec.name] = sim
assert sim_spec.loader is not None
sim_spec.loader.exec_module(sim)

SWEEP_PATH = Path(__file__).parents[1] / "sim" / "run_aco_parameter_sweep.py"
sweep_spec = importlib.util.spec_from_file_location("run_aco_parameter_sweep", SWEEP_PATH)
sweep = importlib.util.module_from_spec(sweep_spec)
sys.modules[sweep_spec.name] = sweep
assert sweep_spec.loader is not None
sweep_spec.loader.exec_module(sweep)


def test_dominance_prefers_more_utility_coverage_and_less_duplication_concentration():
    better = {
        "verified_utility_per_cost": 0.7,
        "duplicate_rate": 0.1,
        "task_coverage": 8.0,
        "max_selection_share": 0.2,
    }
    worse = {
        "verified_utility_per_cost": 0.6,
        "duplicate_rate": 0.2,
        "task_coverage": 7.0,
        "max_selection_share": 0.3,
    }
    assert sweep.dominates(better, worse)
    assert not sweep.dominates(worse, better)


def test_tradeoff_points_can_both_be_pareto_optimal():
    high_utility = {
        "parameters": {"name": "u"},
        "mean": {
            "verified_utility_per_cost": 0.9,
            "duplicate_rate": 0.4,
            "task_coverage": 6.0,
            "max_selection_share": 0.4,
        },
    }
    high_diversity = {
        "parameters": {"name": "d"},
        "mean": {
            "verified_utility_per_cost": 0.6,
            "duplicate_rate": 0.1,
            "task_coverage": 8.0,
            "max_selection_share": 0.2,
        },
    }
    front = sweep.pareto_front([high_utility, high_diversity])
    assert len(front) == 2


def test_small_parameter_sweep_is_deterministic():
    kwargs = dict(
        seed_start=2,
        seeds=2,
        workers=8,
        epochs=4,
        alphas=[0.3, 0.7],
        betas=[1.5],
        rhos=[0.1],
        explorations=[0.05],
    )
    first = sweep.run_parameter_sweep(**kwargs)
    second = sweep.run_parameter_sweep(**kwargs)
    assert first == second
    assert first["configurations_tested"] == 2
    assert 1 <= len(first["pareto_configurations"]) <= 2
