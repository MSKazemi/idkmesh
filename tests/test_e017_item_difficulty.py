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


oracles = _load("e017_oracles", "sim/e017_oracles.py")
analyze = _load("e017_analyze", "sim/e017_analyze.py")


def test_input_draws_are_deterministic_for_a_seed():
    a = oracles.draw_inputs("median_of_list", "small", 5, 3)
    b = oracles.draw_inputs("median_of_list", "small", 5, 3)
    assert a == b
    assert len(a) == 5


def test_different_seeds_and_regions_give_different_inputs():
    same_region = oracles.draw_inputs("median_of_list", "small", 5, 1)
    other_seed = oracles.draw_inputs("median_of_list", "small", 5, 2)
    other_region = oracles.draw_inputs("median_of_list", "large", 5, 1)
    assert same_region != other_seed
    assert same_region != other_region


def test_every_problem_has_a_generator():
    corpus = _load("e016_corpus", "sim/e016_corpus.py")
    names = {p[0] for p in corpus.PROBLEMS}
    assert names == set(oracles.GENERATORS)


def test_tiny_region_really_produces_smaller_inputs_than_large():
    """The region label must correspond to a real difference in the inputs, or
    it cannot serve as a declared independence label."""
    tiny = oracles.draw_inputs("running_total", "tiny", 20, 0)
    large = oracles.draw_inputs("running_total", "large", 20, 0)
    mean_tiny = sum(len(a[0]) for a in tiny) / len(tiny)
    mean_large = sum(len(a[0]) for a in large) / len(large)
    assert mean_tiny < mean_large


def test_shared_shock_pmf_is_a_distribution():
    n, acc, rho = 9, 0.8, 0.4
    total = sum(analyze.shared_shock_pmf(k, n, acc, rho) for k in range(n + 1))
    assert abs(total - 1.0) < 1e-9


def test_shared_shock_reduces_to_the_binomial_at_zero_correlation():
    n, acc = 7, 0.75
    for k in range(n + 1):
        binom = math.comb(n, k) * ((1 - acc) ** k) * (acc ** (n - k))
        assert abs(analyze.shared_shock_pmf(k, n, acc, 0.0) - binom) < 1e-12


def test_shared_shock_puts_no_mass_on_partial_disagreement_at_full_correlation():
    """The structural fact E017 turns on: at high correlation the mixture can
    only produce unanimity or an independent-looking spike, never a task that
    splits the panel."""
    n = 25
    for k in range(1, n):
        assert analyze.shared_shock_pmf(k, n, 0.8, 1.0) == 0.0


def test_beta_binomial_pmf_is_a_distribution():
    n = 12
    total = sum(analyze.beta_binomial_pmf(k, n, 0.5, 2.0) for k in range(n + 1))
    assert abs(total - 1.0) < 1e-9


def test_beta_binomial_approaches_the_binomial_as_concentration_grows():
    """As alpha+beta -> infinity the difficulty distribution collapses to a
    point and items stop being correlated."""
    n, mu = 10, 0.3
    scale = 100000.0
    for k in range(n + 1):
        binom = math.comb(n, k) * (mu ** k) * ((1 - mu) ** (n - k))
        got = analyze.beta_binomial_pmf(k, n, mu * scale, (1 - mu) * scale)
        assert abs(got - binom) < 1e-4


def test_fit_recovers_the_mean_error_rate():
    n = 25
    counts = [0] * 40 + [n] * 10 + [5] * 22
    alpha, beta, mu, icc = analyze.fit_beta_binomial(counts, n)
    assert abs(mu - (sum(counts) / len(counts)) / n) < 1e-12
    assert 0.0 < icc < 1.0
    assert alpha > 0 and beta > 0


def test_fit_reports_near_zero_correlation_for_binomial_like_counts():
    """Counts with only binomial variance must not be read as correlated."""
    n = 25
    # Every task splits the panel the same way: variance far below the
    # binomial value, so the fitted correlation is pinned at the floor.
    counts = [5] * 60
    _, _, _, icc = analyze.fit_beta_binomial(counts, n)
    assert icc < 0.01


def test_simulated_flat_model_matches_its_own_analytic_pmf():
    n, acc, rho = 9, 0.8, 0.5
    need = n // 2 + 1
    analytic = sum(analyze.shared_shock_pmf(k, n, acc, rho) for k in range(need, n + 1))
    simulated = analyze.simulate_flat(n, acc, rho, 200000, seed=11)
    assert abs(analytic - simulated) < 0.005
