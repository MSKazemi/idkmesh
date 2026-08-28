import importlib.util
import sys
from math import comb
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "e015_analyze.py"
spec = importlib.util.spec_from_file_location("e015_analyze", MODULE_PATH)
e015 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e015
assert spec.loader is not None
spec.loader.exec_module(e015)


def test_majority_error_matches_binomial_tail():
    # 5 verifiers, 75% accurate, simple majority: accept needs 3 of 5.
    expected = sum(comb(5, k) * 0.75**k * 0.25 ** (5 - k) for k in range(3))
    assert abs(e015.majority_error_independent(5, 0.75, 0.5) - expected) < 1e-12


def test_single_verifier_error_is_one_minus_accuracy():
    assert abs(e015.majority_error_independent(1, 0.75, 0.5) - 0.25) < 1e-12


def test_majority_error_decreases_with_panel_size():
    errs = [e015.majority_error_independent(n, 0.75, 0.5) for n in (1, 3, 5, 7, 9)]
    assert errs == sorted(errs, reverse=True)


def test_effective_n_recovers_independent_panel_size():
    # An independent panel must be worth exactly its nominal size.
    for n in (1, 3, 5, 7, 9, 11):
        err = e015.majority_error_independent(n, 0.75, 0.5)
        assert abs(e015.effective_n(err, 0.75, 0.5) - n) < 0.05


def test_fully_correlated_panel_is_worth_one_verifier():
    # At rho = 1 the panel error collapses to a single verifier's error.
    assert abs(e015.effective_n(0.25, 0.75, 0.5) - 1.0) < 0.05


def test_effective_n_is_monotone_in_measured_error():
    # Worse measured error must never imply more effective evidence.
    prev = None
    for err in (0.10, 0.14, 0.17, 0.21, 0.25):
        cur = e015.effective_n(err, 0.75, 0.5)
        if prev is not None:
            assert cur <= prev + 1e-9
        prev = cur


def test_effective_n_undefined_for_useless_verifiers():
    # A verifier at or below chance carries no evidence; n_eff is not defined.
    assert e015.effective_n(0.5, 0.5, 0.5) != e015.effective_n(0.5, 0.5, 0.5)


def test_balanced_error_equals_one_sided_at_simple_majority():
    # At quorum 0.5 the two error types are symmetric, so the balanced error
    # must coincide with the one-sided tail.
    for n in (3, 5, 11, 21):
        for p in (0.6, 0.75, 0.9):
            assert abs(
                e015.balanced_error_independent(n, p, 0.5)
                - e015.majority_error_independent(n, p, 0.5)
            ) < 1e-12


def test_raising_quorum_diverges_the_two_error_types():
    # A strict quorum suppresses false accepts by inflating false rejects.
    # The balanced error must therefore get worse, not better.
    lax = e015.balanced_error_independent(11, 0.75, 0.5)
    strict = e015.balanced_error_independent(11, 0.75, 0.7)
    assert strict > lax


def test_balanced_effective_n_is_not_inflated_by_a_strict_quorum():
    # The defect this metric exists to fix: an 11-panel at quorum 0.7 has a
    # tiny false-accept rate, which the one-sided metric reads as a panel of
    # ~199 verifiers. The balanced metric must stay near or below the real size.
    need = 8  # floor(0.7 * 11) + 1
    fa = sum(
        e015.comb(11, k) * (0.25**k) * (0.75 ** (11 - k)) for k in range(need, 12)
    )
    fr = e015.majority_error_independent(11, 0.75, 0.7)
    one_sided = e015.effective_n(fa, 0.75, 0.7)
    balanced = e015.effective_n_balanced(fa, fr, 0.75)
    assert one_sided > 100          # the defect is real
    assert balanced < 11            # the fix bounds it by the actual panel size


def test_balanced_effective_n_still_recovers_independent_majority_panels():
    # The fix must not break the calibrated case.
    for n in (3, 5, 7, 9, 11):
        err = e015.majority_error_independent(n, 0.75, 0.5)
        assert abs(e015.effective_n_balanced(err, err, 0.75) - n) < 0.05
