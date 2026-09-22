import math
from sim.e015_analyze import (
    balanced_error_independent,
    best_quorum,
    effective_n,
    effective_n_balanced,
    effective_n_ceiling,
    effective_n_weighted,
    heuristic_effective_n,
    majority_error_independent,
)


def test_one_verifier_majority_error_reduces_to_individual_error():
    for acc in (0.6, 0.75, 0.9):
        err = majority_error_independent(1, acc, 0.5)
        assert math.isclose(err, 1.0 - acc, abs_tol=1e-12)


def test_majority_error_independent_binomial_tail():
    # 3 verifiers, acc = 0.8, quorum = 0.5 (need = floor(1.5) + 1 = 2)
    # error = P(fewer than 2 correct) = P(0) + P(1) = 0.2^3 + 3 * 0.8^1 * 0.2^2 = 0.008 + 0.096 = 0.104
    err = majority_error_independent(3, 0.8, 0.5)
    assert math.isclose(err, 0.104, abs_tol=1e-12)


def test_balanced_error_independent_coincides_at_simple_majority():
    for n in (1, 3, 5, 7):
        for acc in (0.65, 0.75, 0.85):
            balanced = balanced_error_independent(n, acc, 0.5)
            majority = majority_error_independent(n, acc, 0.5)
            assert math.isclose(balanced, majority, abs_tol=1e-12)


def test_balanced_error_independent_diverges_at_higher_quorum():
    acc = 0.75
    n = 5
    symmetric = balanced_error_independent(n, acc, 0.5)
    high_quorum = balanced_error_independent(n, acc, 0.8)
    assert high_quorum > symmetric


def test_effective_n_handles_non_informative_accuracy():
    assert math.isnan(effective_n(0.2, 0.5, 0.5))
    assert math.isnan(effective_n(0.2, 0.4, 0.5))


def test_effective_n_boundary_clipping():
    acc = 0.75
    # High measured error returns minimum panel size 1.0
    assert math.isclose(effective_n(0.30, acc, 0.5), 1.0)
    # Zero error returns max odd panel size <= nmax (for default nmax=201, this is 199.0)
    assert math.isclose(effective_n(0.0, acc, 0.5, nmax=201), 199.0)


def test_effective_n_weighted_equal_cost_agrees_with_balanced():
    fa, fr, acc = 0.05, 0.15, 0.75
    weighted = effective_n_weighted(fa, fr, acc, false_accept_cost=1.0)
    balanced = effective_n_balanced(fa, fr, acc)
    assert math.isclose(weighted, balanced, abs_tol=1e-12)


def test_heuristic_effective_n_zero_correlation_and_single_verifier():
    # heuristic_effective_n(n, 0) returns n
    for n in (1, 3, 5, 10):
        assert math.isclose(heuristic_effective_n(n, 0.0), float(n))

    # single verifier case remains 1 regardless of correlation
    for corr in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert math.isclose(heuristic_effective_n(1, corr), 1.0)


def test_effective_n_ceiling_zero_correlation_and_accuracy():
    # Zero or negative correlation returns infinity
    assert math.isinf(effective_n_ceiling(0.75, 0.0))
    assert math.isinf(effective_n_ceiling(0.75, -0.2))

    # acc <= 0.5 returns NaN
    assert math.isnan(effective_n_ceiling(0.5, 0.2))
    assert math.isnan(effective_n_ceiling(0.4, 0.2))


def test_best_quorum_ignores_non_matching_cells_and_returns_best():
    cells = [
        # Non-matching verifiers
        {"verifiers": 3, "accuracy": 0.75, "correlation": 0.0, "quorum": 0.5, "false_accept": 0.1, "false_reject": 0.1},
        # Non-matching accuracy
        {"verifiers": 5, "accuracy": 0.80, "correlation": 0.0, "quorum": 0.5, "false_accept": 0.1, "false_reject": 0.1},
        # Non-matching correlation
        {"verifiers": 5, "accuracy": 0.75, "correlation": 0.5, "quorum": 0.5, "false_accept": 0.1, "false_reject": 0.1},
        # Missing false_reject
        {"verifiers": 5, "accuracy": 0.75, "correlation": 0.0, "quorum": 0.6, "false_accept": 0.1, "false_reject": None},
        # Valid candidate 1
        {"verifiers": 5, "accuracy": 0.75, "correlation": 0.0, "quorum": 0.5, "false_accept": 0.10, "false_reject": 0.10},
        # Valid candidate 2 (better score under false_accept_cost=10.0 due to lower false accept)
        {"verifiers": 5, "accuracy": 0.75, "correlation": 0.0, "quorum": 0.7, "false_accept": 0.01, "false_reject": 0.25},
    ]

    best = best_quorum(cells, acc=0.75, corr=0.0, verifiers=5, false_accept_cost=10.0)
    assert best is not None
    assert best[0] == 0.7

    # Non-existent config returns None
    assert best_quorum(cells, acc=0.99, corr=0.0, verifiers=5) is None
