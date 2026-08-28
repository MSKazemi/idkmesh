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


e020 = _load("e020_quorum_frontier", "sim/e020_quorum_frontier.py")


def _binomial(n, mu):
    return [math.comb(n, k) * mu ** k * (1 - mu) ** (n - k) for k in range(n + 1)]


def test_every_distribution_is_normalised():
    for n in (3, 7, 25):
        for pmf in (e020.shared_shock_pmf(n, 0.2, 0.5),
                    e020.beta_binomial_pmf(n, 0.2, 0.5),
                    e020.one_inflated_pmf(n, 0.2, 0.5, 0.1)):
            assert abs(sum(pmf) - 1.0) < 1e-9
            assert len(pmf) == n + 1
            assert all(p >= -1e-12 for p in pmf)


def test_both_models_reduce_to_the_binomial_when_independent():
    """At zero correlation neither model may add anything to independence."""
    for n in (3, 9):
        exact = _binomial(n, 0.25)
        shock = e020.shared_shock_pmf(n, 0.25, 0.0)
        item = e020.beta_binomial_pmf(n, 0.25, 0.0)
        for k in range(n + 1):
            assert abs(shock[k] - exact[k]) < 1e-12
            assert abs(item[k] - exact[k]) < 1e-12


def test_both_models_collapse_to_one_verifier_when_fully_correlated():
    for n in (3, 9):
        for pmf in (e020.shared_shock_pmf(n, 0.3, 1.0),
                    e020.beta_binomial_pmf(n, 0.3, 1.0)):
            assert abs(pmf[n] - 0.3) < 1e-9
            assert abs(pmf[0] - 0.7) < 1e-9
            assert all(abs(pmf[k]) < 1e-12 for k in range(1, n))


def test_beta_parameters_round_trip_mean_and_correlation():
    for mu in (0.1, 0.2044, 0.4):
        for icc in (0.1, 0.5713, 0.9):
            a, b = e020.beta_parameters(mu, icc)
            assert abs(a / (a + b) - mu) < 1e-12
            assert abs(1.0 / (a + b + 1.0) - icc) < 1e-12


def test_beta_parameters_rejects_degenerate_input():
    for mu, icc in ((0.0, 0.5), (1.0, 0.5), (0.2, 0.0), (0.2, 1.0)):
        assert e020.beta_parameters(mu, icc) is None


def test_tail_is_a_survival_function():
    pmf = e020.beta_binomial_pmf(5, 0.2, 0.5)
    assert abs(e020.tail(pmf, 0) - 1.0) < 1e-12
    assert abs(e020.tail(pmf, 5) - pmf[5]) < 1e-12
    assert e020.tail(pmf, 6) == 0.0
    for lo in range(6):
        assert e020.tail(pmf, lo) >= e020.tail(pmf, lo + 1) - 1e-15


def test_shared_shock_unanimity_error_has_a_floor_at_rho_times_mu():
    """The floor is what makes the shared-shock model say a high quorum is
    pointless; it must not decay away with panel size."""
    mu, rho = 0.2044, 0.58
    floor = mu * rho
    for n in (25, 100, 1000):
        assert e020.shared_shock_pmf(n, mu, rho)[n] >= floor
    # The excess over the floor is the independent term, which vanishes.
    assert abs(e020.shared_shock_pmf(2000, mu, rho)[2000] - floor) < 1e-12
    assert e020.shared_shock_pmf(5, mu, rho)[5] > floor


def test_beta_binomial_unanimity_error_has_no_floor():
    """The competing model decays polynomially instead, which is the whole
    disagreement at high quorum."""
    mu, icc = 0.2044, 0.58
    values = [e020.beta_binomial_pmf(n, mu, icc)[n] for n in (25, 100, 1000, 10000)]
    for a, b in zip(values, values[1:]):
        assert b < a
    assert values[-1] < mu * icc / 10


def test_unanimity_decay_exponent_matches_the_measured_decade_ratio():
    """P(all wrong) ~ n^-beta.  Checked against the actual ratio, not asserted."""
    mu, icc = 0.2044, 0.5713
    beta = e020.unanimity_decay_exponent(mu, icc)
    assert abs(beta - (1 - mu) * (1 - icc) / icc) < 1e-12
    hi = e020.beta_binomial_pmf(10 ** 6, mu, icc)[10 ** 6]
    lo = e020.beta_binomial_pmf(10 ** 5, mu, icc)[10 ** 5]
    assert abs(hi / lo - 10 ** -beta) < 1e-3


def test_one_inflated_model_cannot_go_below_its_atom():
    lam = 0.0556
    for n in (25, 500):
        pmf = e020.one_inflated_pmf(n, 0.1576, 0.4513, lam)
        assert pmf[n] >= lam
        assert e020.tail(pmf, n) >= lam


def test_panel_costs_are_symmetric_at_majority_for_a_symmetric_panel():
    n, need = 5, 3
    pmf = e020.beta_binomial_pmf(n, 0.2, 0.5)
    fa, fr, cost = e020.panel_costs(pmf, n, need, base_rate=0.5)
    assert abs(fa - fr) < 1e-12
    assert abs(cost - fa) < 1e-12


def test_lowering_the_quorum_trades_false_rejects_for_false_accepts():
    n = 9
    pmf = e020.beta_binomial_pmf(n, 0.25, 0.4)
    prev_fa, prev_fr = None, None
    for need in range(1, n + 1):
        fa, fr, _ = e020.panel_costs(pmf, n, need, base_rate=0.5)
        if prev_fa is not None:
            assert fa <= prev_fa + 1e-15
            assert fr >= prev_fr - 1e-15
        prev_fa, prev_fr = fa, fr


def test_optimal_quorum_breaks_ties_toward_the_lower_requirement():
    """A flat cost curve must not be reported as demanding a high quorum."""
    n = 5
    flat = [0.0] * (n + 1)
    flat[0] = 1.0
    need, cost = e020.optimal_quorum(flat, n, base_rate=0.5)
    assert need == 1
    assert abs(cost) < 1e-12


def test_making_false_accepts_costlier_never_lowers_the_optimal_quorum():
    n = 11
    pmf = e020.beta_binomial_pmf(n, 0.2, 0.4)
    last = 0
    for cost_fa in (1, 2, 5, 10, 50):
        need, _ = e020.optimal_quorum(pmf, n, base_rate=0.5, cost_fa=cost_fa)
        assert need >= last
        last = need


def test_fit_moments_recovers_the_parameters_it_was_given():
    """Draw the exact beta-binomial pmf as weighted counts and refit it."""
    n, mu, icc = 20, 0.3, 0.4
    pmf = e020.beta_binomial_pmf(n, mu, icc)
    total = 2000000
    counts = []
    for k in range(n + 1):
        counts.extend([k] * round(pmf[k] * total))
    got_mu, got_icc = e020.fit_moments(counts, n)
    assert abs(got_mu - mu) < 1e-3
    assert abs(got_icc - icc) < 1e-3


def test_the_shape_choice_moves_the_optimal_quorum_much_further_than_rho_does():
    """E020's headline, as a regression test: at n=25 the shared-shock optimum
    barely leaves majority while the item-difficulty optimum spans the range."""
    n, mu = 25, 0.2044
    shock, item = [], []
    for rho in (0.25, 0.58, 0.8):
        for base in (0.639, 0.1):
            for cost_fa in (1, 10):
                shock.append(e020.optimal_quorum(
                    e020.shared_shock_pmf(n, mu, rho), n, base, cost_fa)[0])
                item.append(e020.optimal_quorum(
                    e020.beta_binomial_pmf(n, mu, rho), n, base, cost_fa)[0])
    assert max(shock) - min(shock) <= 3
    assert max(item) - min(item) >= 20


def test_empirical_curve_matches_a_hand_worked_panel():
    agents = ["a", "b", "c"]
    tasks = ["good", "bad"]
    truth = {"good": True, "bad": False}
    votes = {
        "a": {"good": True, "bad": True},
        "b": {"good": True, "bad": True},
        "c": {"good": True, "bad": False},
    }
    curve = e020.empirical_curve(agents, tasks, truth, votes)
    # need=1: both accepted -> 'bad' is wrong          -> 1/2
    # need=2: 'good' 3 yes ok, 'bad' 2 yes accepted    -> 1/2
    # need=3: 'good' accepted, 'bad' 2 yes rejected    -> 0/2
    assert curve == [0.5, 0.5, 0.0]
