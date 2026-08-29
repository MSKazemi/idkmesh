import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "matched_budget_emergence.py"
spec = importlib.util.spec_from_file_location("matched_budget_emergence", MODULE_PATH)
benchmark = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmark
assert spec.loader is not None
spec.loader.exec_module(benchmark)


def test_fixed_seed_is_deterministic():
    first = benchmark.run_seed(7, agents=20, generations=16, change_at=8, bins=5)
    second = benchmark.run_seed(7, agents=20, generations=16, change_at=8, bins=5)
    assert first == second


def test_every_strategy_uses_exact_same_budget_without_acceptance_retries():
    result = benchmark.run_seed(9, agents=12, generations=10, change_at=5, bins=4)
    expected = 120
    assert result["budget_contract"]["per_strategy"] == expected
    assert result["budget_contract"]["retry_until_acceptance"] is False
    for row in result["results"]:
        assert row["proposal_attempts"] == expected
        assert row["verification_attempts"] == expected
        assert row["matched_evaluation_budget"] == expected
        assert row["bootstrap_anchors"] == 0


def test_imperfect_verification_does_not_change_budget_contract():
    verification = benchmark.sim.VerificationConfig(
        verifiers=5,
        accuracy=0.75,
        correlation=0.5,
        quorum=0.5,
    )
    result = benchmark.run_seed(
        3,
        agents=10,
        generations=12,
        change_at=6,
        bins=4,
        verification=verification,
    )
    assert result["verification"] == verification.as_dict()
    assert {row["verification_attempts"] for row in result["results"]} == {120}


def test_post_change_auc_and_regret_use_the_fixed_horizon():
    result = benchmark.run_seed(4, agents=10, generations=12, change_at=6, bins=4)
    horizon = 6
    for row in result["results"]:
        assert abs(row["post_change_utility_auc"] + row["post_change_regret_auc"] - horizon) < 1e-6


def test_small_sweep_retains_seed_uncertainty_and_pairwise_counts():
    result = benchmark.sweep(
        seeds=4,
        seed_start=20,
        agents=10,
        generations=12,
        change_at=6,
        bins=4,
    )
    assert result["configuration"]["evaluation_budget_per_strategy_per_seed"] == 120
    assert result["aggregate"]["qd"]["post_change_regret_auc"]["n"] == 4
    for comparison in result["pairwise_wins"].values():
        assert comparison["trials"] == 4
        assert 0 <= comparison["wins"] <= 4


def test_committed_reference_is_explicitly_synthetic_and_budget_matched():
    path = (
        Path(__file__).parents[1]
        / "experiments"
        / "results"
        / "E024-matched-budget-emergence-100-seed-summary.json"
    )
    result = benchmark.json.loads(path.read_text(encoding="utf-8"))
    assert result["experiment_id"] == "E024"
    assert result["experiment"] == "matched-budget-emergence-sweep-v1"
    assert result["configuration"]["seeds"] == 100
    assert result["configuration"]["evaluation_budget_per_strategy_per_seed"] == 2500
    assert all(
        aggregate["post_change_utility_auc"]["n"] == 100
        for aggregate in result["aggregate"].values()
    )
    assert any("synthetic" in limitation for limitation in result["limitations"])
    assert any("not measured compute" in limitation for limitation in result["limitations"])


def test_invalid_budget_shape_fails_closed():
    invalid = [
        {"agents": 1, "generations": 4, "change_at": 2, "bins": 4},
        {"agents": 4, "generations": 1, "change_at": 1, "bins": 4},
        {"agents": 4, "generations": 4, "change_at": 4, "bins": 4},
        {"agents": 4, "generations": 4, "change_at": 2, "bins": 1},
    ]
    for kwargs in invalid:
        try:
            benchmark.run_seed(0, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"invalid configuration accepted: {kwargs}")


def test_issue_22_requires_all_five_baselines():
    # Issue #22 names pure randomness, single-objective evolutionary search, a
    # centralized planner with one fixed objective, and a majority-vote swarm as
    # the comparisons for constraint-guided Quality-Diversity.
    assert set(benchmark.STRATEGIES) == {
        "random",
        "scalar",
        "qd",
        "planner",
        "majority",
    }
    assert set(benchmark.RUNNERS) == set(benchmark.STRATEGIES)


def test_appending_baselines_did_not_disturb_the_published_arms():
    # run_seed derives each arm's seed from its index in STRATEGIES, so a new
    # strategy must be appended rather than inserted. These values were produced
    # by the three-arm implementation published in the E024 reference; if an arm
    # is ever reordered they change and the previously published evidence would
    # silently stop reproducing.
    result = benchmark.run_seed(7, agents=20, generations=16, change_at=8, bins=5)
    rows = {row["strategy"]: row for row in result["results"]}
    assert rows["random"]["final_best"] == 0.708002
    assert rows["scalar"]["final_best"] == 0.631836
    assert rows["qd"]["final_best"] == 0.899031


def test_single_artifact_baselines_keep_no_archive():
    result = benchmark.run_seed(11, agents=12, generations=10, change_at=5, bins=4)
    rows = {row["strategy"]: row for row in result["results"]}
    # The planner holds one central plan and the swarm holds one consensus, so
    # neither retains diversity. Only the QD arm builds an archive.
    assert rows["planner"]["archive_size"] == 0
    assert rows["majority"]["archive_size"] == 0
    assert rows["qd"]["archive_size"] > 0


def test_new_baselines_hold_the_matched_budget_under_imperfect_verification():
    verification = benchmark.sim.VerificationConfig(
        verifiers=5, accuracy=0.7, correlation=0.4, quorum=0.5
    )
    result = benchmark.run_seed(
        5, agents=10, generations=12, change_at=6, bins=4, verification=verification
    )
    rows = {row["strategy"]: row for row in result["results"]}
    for strategy in ("planner", "majority"):
        assert rows[strategy]["verification_attempts"] == 120
        assert rows[strategy]["proposal_attempts"] == 120


def test_sweep_compares_qd_against_every_baseline():
    result = benchmark.sweep(
        seeds=3, seed_start=40, agents=10, generations=10, change_at=5, bins=4
    )
    expected = {
        f"qd_gt_{baseline}_post_change_utility_auc"
        for baseline in benchmark.STRATEGIES
        if baseline != "qd"
    }
    assert set(result["pairwise_wins"]) == expected


def test_committed_reference_reports_all_five_arms():
    path = (
        Path(__file__).parents[1]
        / "experiments"
        / "results"
        / "E024-matched-budget-emergence-100-seed-summary.json"
    )
    result = benchmark.json.loads(path.read_text(encoding="utf-8"))
    assert set(result["aggregate"]) == set(benchmark.STRATEGIES)
    # The majority-vote swarm is bimodal: it either tracks the changed goal or
    # locks onto a stale consensus. Its spread must stay visible in the record
    # rather than be summarised away into a mean.
    majority = result["aggregate"]["majority"]["post_change_utility_auc"]
    qd = result["aggregate"]["qd"]["post_change_utility_auc"]
    assert majority["stdev"] > 10 * qd["stdev"]
    assert majority["min"] < qd["min"]
