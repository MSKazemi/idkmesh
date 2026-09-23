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

TARGET_PATH = SIM_DIR / "adaptive_verification_ecology_targeted.py"
target_spec = importlib.util.spec_from_file_location(
    "adaptive_verification_ecology_targeted",
    TARGET_PATH,
)
target = importlib.util.module_from_spec(target_spec)
sys.modules[target_spec.name] = target
assert target_spec.loader is not None
target_spec.loader.exec_module(target)


def test_ave_core_excludes_probe_memory_from_routing():
    core = next(
        policy
        for policy in target.TARGETED_POLICIES
        if policy.name == "ave-core"
    )
    assert core.verifier_diversity
    assert core.risk_adaptive
    assert core.shadow_backpressure
    assert core.price_aware_routing
    assert not core.probe_memory


def test_targeted_study_keeps_full_ave_comparator():
    assert {
        policy.name for policy in target.TARGETED_POLICIES
    } == {
        "plus-verifier-diversity",
        "diversity-risk-no-probes",
        "ave-core",
        "full-ave",
    }


def test_targeted_study_is_deterministic():
    first = target.run_targeted(
        seed_start=1,
        seeds=2,
        workers=8,
        epochs=4,
        verifier_count=6,
        environment_names=["one-sided-medium"],
    )
    second = target.run_targeted(
        seed_start=1,
        seeds=2,
        workers=8,
        epochs=4,
        verifier_count=6,
        environment_names=["one-sided-medium"],
    )
    assert first == second


def test_targeted_study_reports_all_policies():
    result = target.run_targeted(
        seed_start=3,
        seeds=1,
        workers=8,
        epochs=4,
        verifier_count=6,
        environment_names=["scarce-review"],
    )
    assert set(result["summary"]["scarce-review"]) == {
        "plus-verifier-diversity",
        "diversity-risk-no-probes",
        "ave-core",
        "full-ave",
    }
