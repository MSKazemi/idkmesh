import importlib.util
import sys
from pathlib import Path

SIM_DIR = Path(__file__).parents[1] / "sim"

BASE_PATH = SIM_DIR / "adaptive_verification_ecology_sim.py"
base_spec = importlib.util.spec_from_file_location(
    "adaptive_verification_ecology_sim",
    BASE_PATH,
)
base = importlib.util.module_from_spec(base_spec)
sys.modules[base_spec.name] = base
assert base_spec.loader is not None
base_spec.loader.exec_module(base)

ABLATION_PATH = SIM_DIR / "adaptive_verification_ecology_ablation.py"
ablation_spec = importlib.util.spec_from_file_location(
    "adaptive_verification_ecology_ablation",
    ABLATION_PATH,
)
ablation = importlib.util.module_from_spec(ablation_spec)
sys.modules[ablation_spec.name] = ablation
assert ablation_spec.loader is not None
ablation_spec.loader.exec_module(ablation)


def test_policy_ladder_is_cumulative():
    previous = None
    for policy in ablation.POLICIES:
        active = {
            name
            for name in (
                "niche",
                "posterior_routing",
                "temperature",
                "verifier_diversity",
                "probe_memory",
                "risk_adaptive",
                "shadow_backpressure",
                "price_aware_routing",
            )
            if getattr(policy, name)
        }
        if previous is not None:
            assert previous <= active
        previous = active


def test_matched_budget_ceiling_is_never_exceeded():
    result = ablation.run_policy(
        ablation.policy_by_name("full-ave"),
        ablation.environment_by_name("scarce-review"),
        seed=4,
        workers=10,
        epochs=6,
        verifier_count=6,
    )
    assert result["review_cost"] <= result["review_budget"] + 1e-6
    assert result["compute_cost"] <= result["compute_budget"] + 1e-6
    assert 0 <= result["review_budget_utilization"] <= 1.000001
    assert 0 <= result["compute_budget_utilization"] <= 1.000001


def test_two_sided_environment_can_false_reject():
    result = ablation.run_policy(
        ablation.policy_by_name("capability-only"),
        ablation.environment_by_name("two-sided-medium"),
        seed=8,
        workers=16,
        epochs=12,
        verifier_count=6,
    )
    assert result["false_reject_rate"] > 0.0


def test_shadow_price_activates_when_review_is_scarce():
    result = ablation.run_policy(
        ablation.policy_by_name("full-ave"),
        ablation.environment_by_name("scarce-review"),
        seed=9,
        workers=16,
        epochs=12,
        verifier_count=8,
    )
    assert result["review_price_mean"] > 0.0


def test_misleading_probe_environment_runs_deterministically():
    policy = ablation.policy_by_name("plus-probe-memory")
    environment = ablation.environment_by_name("misleading-probes")
    first = ablation.run_policy(
        policy,
        environment,
        seed=11,
        workers=10,
        epochs=8,
        verifier_count=6,
    )
    second = ablation.run_policy(
        policy,
        environment,
        seed=11,
        workers=10,
        epochs=8,
        verifier_count=6,
    )
    assert first == second


def test_task_family_concentration_is_bounded():
    counts = {
        ("a", "f1"): 3,
        ("a", "f2"): 1,
        ("b", "f1"): 2,
        ("b", "f2"): 2,
    }
    value = ablation.task_family_concentration(counts)
    assert 0.0 <= value <= 1.0


def test_sweep_reports_requested_policy_and_environment():
    result = ablation.sweep(
        seed_start=1,
        seeds=2,
        workers=8,
        epochs=4,
        verifier_count=6,
        environment_names=[
            "one-sided-medium",
            "high-correlation",
        ],
        policy_names=[
            "capability-only",
            "full-ave",
        ],
    )
    assert set(result["summary"]) == {
        "one-sided-medium",
        "high-correlation",
    }
    for environment in result["summary"].values():
        assert set(environment) == {
            "capability-only",
            "full-ave",
        }
        for row in environment.values():
            assert 0.0 <= row["escaped_defect_rate"] <= 1.0
            assert 0.0 <= row["false_reject_rate"] <= 1.0
            assert 0.0 <= row["duplicate_rate"] <= 1.0


def test_extended_environment_matrix_is_exposed():
    names = {environment.name for environment in ablation.ENVIRONMENTS}
    assert {
        "dominant-worker-family",
        "workload-shift",
        "worker-family-outage",
        "verifier-family-outage",
        "selective-adversarial-verifier",
    }.issubset(names)


def test_outage_and_adversarial_scenarios_execute_under_budget():
    for name in (
        "worker-family-outage",
        "verifier-family-outage",
        "selective-adversarial-verifier",
    ):
        result = ablation.run_policy(
            ablation.policy_by_name("full-ave"),
            ablation.environment_by_name(name),
            seed=5,
            workers=12,
            epochs=8,
            verifier_count=8,
        )
        assert result["review_cost"] <= result["review_budget"] + 1e-6
        assert result["compute_cost"] <= result["compute_budget"] + 1e-6
        assert 0.0 <= result["escaped_defect_rate"] <= 1.0
