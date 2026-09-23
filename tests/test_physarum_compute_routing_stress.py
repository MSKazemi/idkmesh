import importlib.util
import sys
from pathlib import Path

SIM_DIR = Path(__file__).parents[1] / "sim"

BASE_PATH = SIM_DIR / "physarum_compute_routing_sim.py"
base_spec = importlib.util.spec_from_file_location(
    "physarum_compute_routing_sim",
    BASE_PATH,
)
base = importlib.util.module_from_spec(base_spec)
sys.modules[base_spec.name] = base
assert base_spec.loader is not None
base_spec.loader.exec_module(base)

STRESS_PATH = SIM_DIR / "physarum_compute_routing_stress.py"
stress_spec = importlib.util.spec_from_file_location(
    "physarum_compute_routing_stress",
    STRESS_PATH,
)
stress = importlib.util.module_from_spec(stress_spec)
sys.modules[stress_spec.name] = stress
assert stress_spec.loader is not None
stress_spec.loader.exec_module(stress)


def test_stress_matrix_contains_falsification_environments():
    names = {environment.name for environment in stress.ENVIRONMENTS}
    assert {
        "stationary",
        "gradual-shift",
        "transient-a-outage",
        "permanent-a-node-loss",
        "correlated-ab-region-shocks",
        "donor-burden-asymmetry",
        "noisy-failure-attribution",
    }.issubset(names)


def test_stationary_environment_does_not_invent_shift():
    environment = stress.environment_by_name("stationary")
    edge_key = base.key("coordinator", "a")
    first = stress.reliability_for(edge_key, 0, 80, environment)
    last = stress.reliability_for(edge_key, 79, 80, environment)
    assert first == last == base.EDGE_BY_KEY[edge_key].reliability_before


def test_permanent_node_loss_disables_a_corridor_after_event():
    environment = stress.environment_by_name("permanent-a-node-loss")
    edge_key = base.key("coordinator", "a")
    before = stress.reliability_for(edge_key, 0, 80, environment)
    after = stress.reliability_for(edge_key, 60, 80, environment)
    assert before > 0.9
    assert after <= 0.001


def test_donor_burden_penalizes_c_paths():
    environment = stress.environment_by_name("donor-burden-asymmetry")
    a_path = ("coordinator", "a", "worker")
    c_path = ("coordinator", "c", "worker")
    assert (
        stress.path_burden(c_path, environment)
        > stress.path_burden(a_path, environment)
    )


def test_noisy_attribution_stays_on_used_path():
    environment = stress.environment_by_name("noisy-failure-attribution")
    path = ("coordinator", "a", "worker")
    failed = (base.key("coordinator", "a"),)
    rng = base.random.Random(3)
    attributed = stress.attributed_failures(
        path,
        failed,
        environment,
        rng,
    )
    assert set(attributed).issubset(set(base.path_edges(path)))


def test_stress_run_is_deterministic():
    environment = stress.environment_by_name("gradual-shift")
    first = stress.run_strategy(
        "physarum",
        environment,
        seed=4,
        epochs=20,
        tasks_per_epoch=8,
    )
    second = stress.run_strategy(
        "physarum",
        environment,
        seed=4,
        epochs=20,
        tasks_per_epoch=8,
    )
    assert first == second


def test_explicit_failover_reports_retries():
    result = stress.run_strategy(
        "multipath-failover",
        stress.environment_by_name("transient-a-outage"),
        seed=5,
        epochs=24,
        tasks_per_epoch=10,
    )
    assert result["route_attempts"] >= result["attempts"]
    assert result["retry_rate"] > 0.0


def test_small_matrix_reports_all_strong_baselines():
    result = stress.compare(
        seed_start=1,
        seeds=2,
        epochs=12,
        tasks_per_epoch=5,
        environment_names=["stationary", "permanent-a-node-loss"],
    )
    for environment in result["summary"].values():
        assert set(environment) == set(stress.STRATEGIES)
        for row in environment.values():
            assert 0.0 <= row["success_rate"] <= 1.0
            assert row["mean_route_burden_per_task"] > 0.0
