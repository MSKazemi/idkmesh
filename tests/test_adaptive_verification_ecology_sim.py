import importlib.util
import sys
from pathlib import Path

SIM_PATH = Path(__file__).parents[1] / "sim" / "adaptive_verification_ecology_sim.py"
spec = importlib.util.spec_from_file_location("adaptive_verification_ecology_sim", SIM_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_softmax_normalizes():
    probs = sim.softmax([-2.0, -1.0, 0.0], 0.5)
    assert all(probability > 0 for probability in probs)
    assert abs(sum(probs) - 1.0) < 1e-12


def test_shadow_price_increases_under_overload():
    config = sim.Config()
    assert sim.update_price(0.4, 1.2, config) > 0.4
    assert sim.update_price(0.4, 0.2, config) < 0.4


def test_temperature_cools_with_review_price():
    config = sim.Config()
    posteriors = {("family", "task"): [2.0, 2.0]}
    warm = sim.route_temperature(posteriors, 0.0, config)
    cool = sim.route_temperature(posteriors, 2.0, config)
    assert config.temp_min <= cool < warm <= config.temp_max


def test_high_risk_task_has_three_verifier_floor():
    task = next(task for task in sim.TASKS if task.name == "security")
    assert sim.verifier_floor(task, 0.1) == 3


def test_verifier_selection_spreads_families():
    rng = sim.random.Random(3)
    verifiers = sim.make_verifiers(9, rng)
    posteriors = {verifier.name: [3.0, 1.0] for verifier in verifiers}
    loads = {verifier.name: 0 for verifier in verifiers}
    chosen = sim.select_verifiers(
        verifiers,
        posteriors,
        loads,
        3,
        0.0,
        sim.Config(),
    )
    assert len({verifier.family for verifier in chosen}) == 3


def test_probe_updates_memory():
    rng = sim.random.Random(9)
    verifiers = sim.make_verifiers(6, rng)
    posteriors = {verifier.name: [3.0, 1.0] for verifier in verifiers}
    before = {name: sum(values) for name, values in posteriors.items()}
    breaches, probes, cost = sim.probe(verifiers, posteriors, rng, sim.Config())
    assert 0 <= breaches <= probes == len(verifiers)
    assert cost > 0
    assert all(sum(posteriors[name]) == before[name] + 1 for name in posteriors)


def test_same_seed_is_deterministic():
    first = sim.run("ave", seed=12, workers=10, epochs=6, verifier_count=6)
    second = sim.run("ave", seed=12, workers=10, epochs=6, verifier_count=6)
    assert first == second


def test_comparison_reports_tradeoff_metrics():
    result = sim.compare(
        seed_start=1,
        seeds=2,
        workers=8,
        epochs=4,
        verifier_count=6,
    )
    assert set(result["summary"]) == set(sim.STRATEGIES)
    for row in result["summary"].values():
        assert row["verified_utility_per_cost"] >= 0
        assert 0 <= row["escaped_defect_rate"] <= 1
        assert 0 <= row["false_reject_rate"] <= 1
        assert 0 <= row["duplicate_rate"] <= 1
        assert 0 <= row["task_coverage"] <= len(sim.TASKS)
        assert 0 <= row["verifier_family_concentration"] <= 1
