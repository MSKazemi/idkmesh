import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "e016_analyze.py"
spec = importlib.util.spec_from_file_location("e016_analyze", MODULE_PATH)
e016 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e016
assert spec.loader is not None
spec.loader.exec_module(e016)


def _corpus(n_viable, n_nonviable):
    """Task ids mapped to ground truth, deliberately imbalanced by default."""
    truth = {}
    for i in range(n_viable):
        truth[f"v{i}"] = True
    for i in range(n_nonviable):
        truth[f"n{i}"] = False
    return truth, sorted(truth)


def test_constant_accept_scores_the_base_rate_but_zero_discrimination():
    truth, tasks = _corpus(26, 46)
    verdicts = {t: True for t in tasks}
    accuracy = sum(1 for t in tasks if verdicts[t] == truth[t]) / len(tasks)
    j, se = e016.youden_j(truth, verdicts, tasks)
    # It looks like a 36% verifier, but it discriminates not at all.
    assert abs(accuracy - 26 / 72) < 1e-9
    assert abs(j) < 1e-12
    assert abs(se) < 1e-12


def test_constant_reject_beats_chance_on_accuracy_yet_j_is_still_zero():
    truth, tasks = _corpus(26, 46)
    verdicts = {t: False for t in tasks}
    accuracy = sum(1 for t in tasks if verdicts[t] == truth[t]) / len(tasks)
    j, _ = e016.youden_j(truth, verdicts, tasks)
    # 0.639 accuracy is the trap this metric exists to catch.
    assert accuracy > 0.6
    assert abs(j) < 1e-12


def test_j_is_one_for_a_perfect_verifier_and_minus_one_when_inverted():
    truth, tasks = _corpus(10, 10)
    perfect = {t: truth[t] for t in tasks}
    inverted = {t: not truth[t] for t in tasks}
    assert abs(e016.youden_j(truth, perfect, tasks)[0] - 1.0) < 1e-12
    assert abs(e016.youden_j(truth, inverted, tasks)[0] + 1.0) < 1e-12


def test_j_is_unchanged_by_corpus_imbalance_but_accuracy_is_not():
    """The property that makes J the right screen: it does not move with the
    base rate, so a panel cannot be made to look better by rebalancing."""
    balanced, bal_tasks = _corpus(36, 36)
    skewed, skew_tasks = _corpus(8, 64)

    def half_right(truth, tasks):
        # Correct on every viable task, correct on half the non-viable ones.
        out = {}
        seen = 0
        for t in tasks:
            if truth[t]:
                out[t] = True
            else:
                out[t] = seen % 2 == 1
                seen += 1
        return out

    jb, _ = e016.youden_j(balanced, half_right(balanced, bal_tasks), bal_tasks)
    js, _ = e016.youden_j(skewed, half_right(skewed, skew_tasks), skew_tasks)
    assert abs(jb - js) < 1e-9

    acc_b = sum(1 for t in bal_tasks
                if half_right(balanced, bal_tasks)[t] == balanced[t]) / len(bal_tasks)
    acc_s = sum(1 for t in skew_tasks
                if half_right(skewed, skew_tasks)[t] == skewed[t]) / len(skew_tasks)
    assert abs(acc_b - acc_s) > 0.05


def test_j_is_nan_when_one_truth_class_has_no_parseable_votes():
    truth, tasks = _corpus(5, 5)
    verdicts = {t: None for t in tasks}
    j, se = e016.youden_j(truth, verdicts, tasks)
    assert j != j
    assert se != se


def test_unparseable_votes_do_not_count_as_wrong_answers_in_j():
    """A model that failed to answer must not be scored as if it answered
    incorrectly -- that is a property of the harness, not the verifier."""
    truth, tasks = _corpus(4, 4)
    answered = {t: truth[t] for t in tasks}
    partial = dict(answered)
    partial["v0"] = None
    partial["n0"] = None
    assert abs(e016.youden_j(truth, answered, tasks)[0] - 1.0) < 1e-12
    # Still perfect on what it actually answered.
    assert abs(e016.youden_j(truth, partial, tasks)[0] - 1.0) < 1e-12


def test_standard_error_shrinks_as_the_corpus_grows():
    small, small_tasks = _corpus(10, 10)
    large, large_tasks = _corpus(200, 200)

    def noisy(truth, tasks):
        return {t: (truth[t] if i % 4 else not truth[t])
                for i, t in enumerate(tasks)}

    _, se_small = e016.youden_j(small, noisy(small, small_tasks), small_tasks)
    _, se_large = e016.youden_j(large, noisy(large, large_tasks), large_tasks)
    assert se_large < se_small
