import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


e018 = _load("e018_dependence_models", "sim/e018_dependence_models.py")
sim = _load("emergence_sim", "sim/emergence_sim.py")


def test_the_two_models_agree_exactly_at_zero_correlation():
    """Any difference between the models must come from shape alone, so they
    have to coincide where dependence vanishes."""
    for n in (3, 9, 21):
        for acc in (0.6, 0.75, 0.95):
            a = e018.shared_shock_error(n, acc, 0.0)
            b = e018.item_difficulty_error(n, acc, 0.0)
            assert abs(a - b) < 1e-12


def test_the_two_models_agree_exactly_at_full_correlation():
    for n in (3, 9, 21):
        for acc in (0.6, 0.75, 0.95):
            a = e018.shared_shock_error(n, acc, 1.0)
            b = e018.item_difficulty_error(n, acc, 1.0)
            assert abs(a - b) < 1e-12
            assert abs(a - (1 - acc)) < 1e-12


def test_independent_error_matches_the_binomial_tail():
    n, acc = 9, 0.8
    need = n // 2 + 1
    expected = sum(math.comb(n, k) * acc ** k * (1 - acc) ** (n - k)
                   for k in range(0, need))
    assert abs(e018.independent_error(n, acc) - expected) < 1e-12


def test_item_difficulty_predicts_more_error_than_shared_shock():
    """The direction E017 measured: shared-shock is optimistic in between."""
    worse = 0
    total = 0
    for n in (5, 11, 21):
        for acc in (0.65, 0.75, 0.85):
            for rho in (0.125, 0.25, 0.5, 0.75):
                total += 1
                if e018.item_difficulty_error(n, acc, rho) > \
                        e018.shared_shock_error(n, acc, rho):
                    worse += 1
    assert worse == total


def test_more_verifiers_never_increase_error_under_either_model():
    for model in (e018.shared_shock_error, e018.item_difficulty_error):
        for acc in (0.7, 0.9):
            for rho in (0.125, 0.5):
                errs = [model(n, acc, rho) for n in (3, 5, 7, 9, 11, 15, 21)]
                for a, b in zip(errs, errs[1:]):
                    assert b <= a + 1e-12


def test_effective_size_is_never_larger_than_the_nominal_panel():
    for n in (3, 9, 21):
        for acc in (0.7, 0.9):
            for rho in (0.125, 0.5):
                eff = e018.effective_n(e018.item_difficulty_error(n, acc, rho), acc)
                assert eff <= n + 1e-9


def test_heuristic_overstates_independence_everywhere_under_item_difficulty():
    """E015 found the N_eff heuristic optimistic only for accurate verifiers.
    Under the measured shape it is optimistic across the whole grid."""
    for n in (5, 11, 21):
        for acc in (0.6, 0.75, 0.9):
            for rho in (0.125, 0.25, 0.5):
                eff = e018.effective_n(e018.item_difficulty_error(n, acc, rho), acc)
                assert e018.heuristic_effective_n(n, rho) > eff


def test_beta_parameters_recover_the_requested_mean_and_correlation():
    acc, rho = 0.8, 0.35
    params = sim.beta_parameters(acc, rho)
    assert params is not None
    alpha, beta = params
    assert abs(alpha / (alpha + beta) - (1 - acc)) < 1e-12
    assert abs(1.0 / (alpha + beta + 1) - rho) < 1e-12


def test_beta_parameters_declines_the_degenerate_ends():
    assert sim.beta_parameters(0.8, 0.0) is None
    assert sim.beta_parameters(0.8, 1.0) is None
    assert sim.beta_parameters(1.0, 0.5) is None


def test_simulator_default_is_still_shared_shock():
    """Every earlier experiment must keep reproducing."""
    assert sim.VerificationConfig().dependence == "shared-shock"


def test_selecting_item_difficulty_changes_the_simulated_panel():
    base = dict(strategy="all", seed=5, agents=30, generations=12, change_at=6,
                bins=6, verifiers=9, verifier_accuracy=0.75,
                verifier_correlation=0.5, verification_quorum=0.5)
    shock = sim.run(**base, verifier_dependence="shared-shock")
    item = sim.run(**base, verifier_dependence="item-difficulty")
    assert shock["verification"]["dependence"] == "shared-shock"
    assert item["verification"]["dependence"] == "item-difficulty"
    shock_rates = [r["false_accept_rate"] for r in shock["results"]]
    item_rates = [r["false_accept_rate"] for r in item["results"]]
    assert shock_rates != item_rates


def test_simulated_item_difficulty_tracks_its_closed_form():
    """The sampler and the analytic model must describe the same process."""
    import random
    n, acc, rho = 11, 0.75, 0.4
    cfg = sim.VerificationConfig(verifiers=n, accuracy=acc, correlation=rho,
                                 quorum=0.5, dependence="item-difficulty")
    rng = random.Random(3)
    params = sim.beta_parameters(acc, rho)
    need = n // 2 + 1
    wrong = 0
    trials = 40000
    for _ in range(trials):
        d = rng.betavariate(*params)
        correct = sum(1 for _ in range(n) if rng.random() >= d)
        if correct < need:
            wrong += 1
    assert abs(wrong / trials - e018.item_difficulty_error(n, acc, rho)) < 0.01
