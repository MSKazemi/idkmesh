import importlib.util
import json
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



def test_sparse_and_dense_topologies_are_distinct_and_replayable():
    sparse = stress.topology_by_name("sparse")
    dense = stress.topology_by_name("dense")
    sparse_paths = stress.topology_paths(sparse, max_hops=5)
    dense_paths = stress.topology_paths(dense, max_hops=5)

    assert len(sparse_paths) == 3
    assert len(dense_paths) > len(sparse_paths)

    environment = stress.environment_by_name("abrupt-shift")
    first = stress.run_strategy(
        "physarum",
        environment,
        seed=11,
        epochs=16,
        tasks_per_epoch=6,
        topology=sparse,
    )
    second = stress.run_strategy(
        "physarum",
        environment,
        seed=11,
        epochs=16,
        tasks_per_epoch=6,
        topology=sparse,
    )
    assert first == second
    assert first["topology"] == "sparse"


def test_topology_sweep_covers_both_graph_shapes():
    result = stress.compare_topologies(
        seed_start=1,
        seeds=1,
        epochs=10,
        tasks_per_epoch=4,
        environment_names=["stationary"],
    )
    assert set(result["topologies"]) == {"sparse", "dense"}
    for summary in result["topologies"].values():
        assert set(summary["stationary"]) == set(stress.STRATEGIES)


def test_parameter_sweep_varies_only_declared_physarum_controls():
    result = stress.parameter_sweep(
        seed_start=1,
        seeds=1,
        epochs=10,
        tasks_per_epoch=4,
    )
    rows = result["parameters"]
    assert {
        "baseline",
        "conductance-floor-low",
        "conductance-floor-high",
        "evaporation-low",
        "evaporation-high",
        "exploration-low",
        "exploration-high",
    } == set(rows)

    baseline = rows["baseline"]["config"]
    assert rows["conductance-floor-low"]["config"]["d_min"] != baseline["d_min"]
    assert rows["evaporation-high"]["config"]["evaporation"] != baseline["evaporation"]
    assert rows["exploration-low"]["config"]["exploration"] != baseline["exploration"]
    for row in rows.values():
        assert 0.0 <= row["summary"]["success_rate"] <= 1.0


def test_unknown_topology_fails_closed():
    try:
        stress.topology_by_name("invented")
    except ValueError as exc:
        assert "unknown topology" in str(exc)
    else:
        raise AssertionError("unknown topology must fail closed")


def test_parameter_sweep_rejects_non_positive_sample_counts():
    try:
        stress.parameter_sweep(seeds=0)
    except ValueError as exc:
        assert "seeds must be positive" in str(exc)
    else:
        raise AssertionError("non-positive sample counts must fail closed")


def test_retained_completion_artifact_marks_synthetic_scope():
    result_path = (
        Path(__file__).parents[1]
        / "experiments"
        / "results"
        / "PHY-1-completion-sweep.json"
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["recommendation"] == "reject-promotion"
    assert "Synthetic" in payload["model_warning"]
    assert payload["seeds"] == 6
    assert payload["epochs"] == 50
    assert payload["tasks_per_epoch"] == 10
    assert set(payload["topology_summary"]) == {"sparse", "dense"}
    assert set(payload["parameter_sweep"]) == {
        "baseline",
        "conductance-floor-low",
        "conductance-floor-high",
        "evaporation-low",
        "evaporation-high",
        "exploration-low",
        "exploration-high",
    }
