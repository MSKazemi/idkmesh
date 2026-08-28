import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "verification_aggregation_sim.py"
spec = importlib.util.spec_from_file_location("verification_aggregation_sim", MODULE_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_parse_group_sizes():
    assert sim.parse_group_sizes("7,1,1,1,1") == (7, 1, 1, 1, 1)


def test_same_seed_is_deterministic():
    a = sim.run_seed(7, 200, (7, 1, 1, 1, 1), 0.75, 0.5)
    b = sim.run_seed(7, 200, (7, 1, 1, 1, 1), 0.75, 0.5)
    assert a == b


def test_full_correlation_makes_large_group_unanimous():
    rng = sim.random.Random(3)
    for _ in range(100):
        votes = sim.sample_group_votes(True, 7, 0.75, 1.0, rng)
        assert all(vote == votes[0] for vote in votes)


def test_group_balancing_is_not_universally_better():
    out = sim.sweep(
        correlations=[0.0, 1.0],
        seeds=8,
        seed_start=0,
        trials=500,
        group_sizes=(7, 1, 1, 1, 1),
        accuracy=0.75,
    )
    independent = out["levels"][0]
    correlated = out["levels"][1]

    assert independent["aggregate"]["naive_majority"]["error_rate"]["mean"] < independent["aggregate"]["group_balanced"]["error_rate"]["mean"]
    assert correlated["aggregate"]["group_balanced"]["error_rate"]["mean"] < correlated["aggregate"]["naive_majority"]["error_rate"]["mean"]


def test_matched_panel_can_produce_different_aggregation_decisions():
    groups = [
        [False, False, False, False, False, False, False],
        [True],
        [True],
        [True],
        [True],
    ]
    assert sim.naive_majority(groups) is False
    assert sim.group_balanced_majority(groups) is True
