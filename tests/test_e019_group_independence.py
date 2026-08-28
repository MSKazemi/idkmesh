import importlib.util
import random
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "verification_aggregation_sim.py"
spec = importlib.util.spec_from_file_location("verification_aggregation_sim", MODULE_PATH)
agg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agg
assert spec.loader is not None
spec.loader.exec_module(agg)

GROUPS = (7, 1, 1, 1, 1)
ACCURACY = 0.75


def _error_rates(correlation, dependence, cross_group, trials=40000, seed=5):
    rng = random.Random(seed)
    naive = balanced = 0
    for _ in range(trials):
        truth = rng.random() < 0.5
        groups = agg.sample_panel(truth, GROUPS, ACCURACY, correlation, rng,
                                  dependence=dependence, cross_group=cross_group)
        naive += agg.naive_majority(groups) != truth
        balanced += agg.group_balanced_majority(groups) != truth
    return naive / trials, balanced / trials


def test_default_dependence_is_shared_shock():
    """E013 must keep reproducing byte-for-byte."""
    rng_a = random.Random(1)
    rng_b = random.Random(1)
    a = agg.sample_panel(True, GROUPS, ACCURACY, 0.5, rng_a)
    b = agg.sample_panel(True, GROUPS, ACCURACY, 0.5, rng_b,
                         dependence="shared-shock")
    assert a == b


def test_beta_parameters_match_requested_mean_and_correlation():
    alpha, beta = agg.beta_parameters(0.75, 0.4)
    assert abs(alpha / (alpha + beta) - 0.25) < 1e-12
    assert abs(1.0 / (alpha + beta + 1) - 0.4) < 1e-12


def test_beta_parameters_declines_degenerate_ends():
    assert agg.beta_parameters(0.75, 0.0) is None
    assert agg.beta_parameters(0.75, 1.0) is None
    assert agg.beta_parameters(1.0, 0.5) is None


def test_perfect_accuracy_still_short_circuits_under_item_difficulty():
    rng = random.Random(0)
    groups = agg.sample_panel(False, GROUPS, 1.0, 0.5, rng,
                              dependence="item-difficulty")
    assert all(vote is False for group in groups for vote in group)


def test_group_balancing_wins_at_high_correlation_when_groups_are_independent():
    """E013's headline, and it survives the shape change."""
    for dependence in ("shared-shock", "item-difficulty"):
        naive, balanced = _error_rates(0.75, dependence, cross_group=False)
        assert balanced < naive


def test_naive_wins_at_zero_correlation_under_both_models():
    for dependence in ("shared-shock", "item-difficulty"):
        naive, balanced = _error_rates(0.0, dependence, cross_group=False)
        assert naive < balanced


def test_group_balancing_loses_its_advantage_when_groups_share_difficulty():
    """The E019 result: balancing needs the declared groups to carry
    independent evidence. When every group errs on the same hard tasks, there
    is nothing left to balance and naive is no worse."""
    for correlation in (0.25, 0.5, 0.75):
        naive, balanced = _error_rates(correlation, "item-difficulty",
                                       cross_group=True)
        assert balanced >= naive - 1e-3


def test_shared_difficulty_collapses_the_panel_to_one_verifier_at_full_correlation():
    naive, balanced = _error_rates(1.0, "item-difficulty", cross_group=True)
    for rate in (naive, balanced):
        assert abs(rate - (1 - ACCURACY)) < 0.02


def test_cross_group_never_reduces_error_below_independent_groups():
    """Sharing difficulty across groups can only destroy evidence."""
    for correlation in (0.25, 0.5, 0.75):
        _, indep = _error_rates(correlation, "item-difficulty", cross_group=False)
        _, shared = _error_rates(correlation, "item-difficulty", cross_group=True)
        assert shared >= indep - 1e-3
