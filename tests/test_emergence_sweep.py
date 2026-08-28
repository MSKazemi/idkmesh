import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "run_emergence_sweep.py"
spec = importlib.util.spec_from_file_location("run_emergence_sweep", MODULE_PATH)
sweep_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sweep_mod
assert spec.loader is not None
spec.loader.exec_module(sweep_mod)


def test_stats_shape():
    s = sweep_mod.stats([1.0, 2.0, 3.0])
    assert s["n"] == 3
    assert s["mean"] == 2.0
    assert s["ci95_low"] < s["mean"] < s["ci95_high"]


def test_small_sweep_counts_trials():
    out = sweep_mod.sweep(seeds=3, seed_start=0, agents=10, generations=12, change_at=6, bins=4)
    assert out["configuration"]["seeds"] == 3
    assert out["pairwise_wins"]["qd_gt_scalar_post_change_mean"]["trials"] == 3
    assert out["aggregate"]["qd"]["post_change_mean"]["n"] == 3


def test_sweep_propagates_verifier_configuration_and_metrics():
    out = sweep_mod.sweep(
        seeds=3,
        seed_start=10,
        agents=10,
        generations=12,
        change_at=6,
        bins=4,
        verifiers=5,
        verifier_accuracy=0.8,
        verifier_correlation=0.6,
        verification_quorum=0.5,
    )
    assert out["configuration"]["verifiers"] == 5
    assert out["configuration"]["verifier_accuracy"] == 0.8
    assert out["configuration"]["verifier_correlation"] == 0.6
    assert out["aggregate"]["qd"]["false_accept_rate"]["n"] == 3
    assert out["aggregate"]["scalar"]["panel_disagreement_rate"]["n"] == 3
