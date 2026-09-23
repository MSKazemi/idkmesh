import importlib.util
import sys
from pathlib import Path

SIM_DIR = Path(__file__).parents[1] / "sim"

for module_name in (
    "adaptive_verification_ecology_sim",
    "adaptive_verification_ecology_ablation",
):
    path = SIM_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)

STRESS_PATH = SIM_DIR / "adaptive_verification_ecology_stress.py"
stress_spec = importlib.util.spec_from_file_location(
    "adaptive_verification_ecology_stress",
    STRESS_PATH,
)
stress = importlib.util.module_from_spec(stress_spec)
sys.modules[stress_spec.name] = stress
assert stress_spec.loader is not None
stress_spec.loader.exec_module(stress)


def test_correlation_grids_hold_other_axis_fixed():
    low = stress.environment_by_name("verifier-corr-low")
    med = stress.environment_by_name("verifier-corr-medium")
    high = stress.environment_by_name("verifier-corr-high")
    assert low.worker_shock_rate == med.worker_shock_rate == high.worker_shock_rate
    assert low.verifier_corr_scale < med.verifier_corr_scale < high.verifier_corr_scale

    wlow = stress.environment_by_name("worker-corr-low")
    wmed = stress.environment_by_name("worker-corr-medium")
    whigh = stress.environment_by_name("worker-corr-high")
    assert wlow.verifier_corr_scale == wmed.verifier_corr_scale == whigh.verifier_corr_scale
    assert wlow.worker_shock_rate < wmed.worker_shock_rate < whigh.worker_shock_rate


def test_capacity_grid_is_ordered():
    scarce = stress.environment_by_name("review-scarce")
    medium = stress.environment_by_name("review-medium")
    abundant = stress.environment_by_name("review-abundant")
    assert scarce.review_capacity_scale < medium.review_capacity_scale < abundant.review_capacity_scale


def test_dominant_provider_changes_family_quality():
    import adaptive_verification_ecology_ablation as ablation
    import adaptive_verification_ecology_sim as ave

    rng = ave.random.Random(4)
    workers = ave.make_workers(12, rng)
    changed = ablation.apply_worker_quality_imbalance(workers, 0.18)
    family0_before = [
        sum(worker.skills.values())
        for worker in workers
        if worker.family == "worker-family-0"
    ]
    family0_after = [
        sum(worker.skills.values())
        for worker in changed
        if worker.family == "worker-family-0"
    ]
    assert sum(family0_after) > sum(family0_before)


def test_workload_shift_flips_demand():
    import adaptive_verification_ecology_ablation as ablation

    environment = stress.environment_by_name("workload-shift")
    before = ablation.workload_weights(1, 10, environment)
    after = ablation.workload_weights(9, 10, environment)
    assert before["docs"] > after["docs"]
    assert before["security"] < after["security"]


def test_outage_and_adversary_environments_execute():
    for name in (
        "provider-outage",
        "verifier-outage",
        "selective-adversarial-verifier",
    ):
        result = stress.run_stress(
            seed_start=1,
            seeds=1,
            workers=8,
            epochs=4,
            verifier_count=6,
            environment_names=[name],
        )
        assert name in result["summary"]
        assert set(result["summary"][name]) == {
            "capability-only",
            "plus-verifier-diversity",
            "ave-core",
            "full-ave",
        }
