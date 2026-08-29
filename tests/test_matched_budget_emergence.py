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


PERFECT_PANEL_REPORT_KEYS = {
    "experiment_id",
    "experiment",
    "configuration",
    "aggregate",
    "pairwise_wins",
    "limitations",
}
PERFECT_PANEL_CONFIGURATION_KEYS = {
    "seed_start",
    "seeds",
    "agents",
    "generations",
    "change_at",
    "bins",
    "evaluation_budget_per_strategy_per_seed",
    "verification",
}


def test_default_panel_is_perfect_and_keeps_the_published_report_schema():
    # The committed 100-seed reference was produced by this default. Any key
    # added here, or any random number consumed by the panel, would stop it
    # reproducing byte-for-byte.
    default = benchmark.sim.VerificationConfig()
    assert benchmark.panel_is_perfect(default)
    result = benchmark.sweep(
        seeds=3, seed_start=0, agents=10, generations=10, change_at=5, bins=4
    )
    assert set(result) == PERFECT_PANEL_REPORT_KEYS
    assert set(result["configuration"]) == PERFECT_PANEL_CONFIGURATION_KEYS
    assert result["configuration"]["verification"] == default.as_dict()
    reference = benchmark.json.loads(
        (
            Path(__file__).parents[1]
            / "experiments"
            / "results"
            / "E024-matched-budget-emergence-100-seed-summary.json"
        ).read_text(encoding="utf-8")
    )
    assert set(reference) == set(result)
    assert set(reference["configuration"]) == set(result["configuration"])
    assert reference["configuration"]["verification"] == default.as_dict()
    for strategy in benchmark.STRATEGIES:
        for metric in ("false_accept_rate", "false_reject_rate", "panel_disagreement_rate"):
            assert result["aggregate"][strategy][metric]["max"] == 0.0


def test_measured_panel_parameters_come_from_e017_and_e020():
    panel = benchmark.measured_panel()
    assert panel.verifiers == 25
    assert panel.accuracy == 0.7956
    assert panel.dependence == "item-difficulty"
    assert panel.blind_spot == 0.0556
    # E017's headline rho is the marginal correlation of the whole panel,
    # blind-spot units included. Using it as the base correlation as well would
    # count those shared failures twice, so the base is E020's decomposition.
    assert panel.correlation == 0.4513
    assert benchmark.E017_MEASURED_MARGINAL_CORRELATION == 0.5873
    assert panel.correlation < benchmark.E017_MEASURED_MARGINAL_CORRELATION
    provenance = benchmark.PANEL_PROVENANCE
    assert provenance["source_experiments"] == [
        "experiments/E017-item-difficulty-and-quorum.md",
        "experiments/E020-quorum-frontier-under-measured-shape.md",
    ]
    assert "synthetic" in provenance["evidence_level"]
    assert "shared-shock" in provenance["shape_rejected"]


def test_measured_panel_overrides_only_what_is_named():
    panel = benchmark.measured_panel(correlation=0.0, blind_spot=0.0)
    assert panel.correlation == 0.0
    assert panel.blind_spot == 0.0
    assert panel.verifiers == 25
    assert panel.accuracy == 0.7956


def test_imperfect_panel_produces_real_non_zero_error_rates():
    result = benchmark.run_seed(
        3,
        agents=20,
        generations=12,
        change_at=6,
        bins=4,
        verification=benchmark.measured_panel(),
    )
    for row in result["results"]:
        assert row["false_accept_rate"] > 0.0
        assert row["false_reject_rate"] > 0.0
        assert row["panel_disagreement_rate"] > 0.0


def test_imperfect_panel_keeps_the_budget_matched_across_every_arm():
    panel = benchmark.measured_panel()
    result = benchmark.run_seed(
        5, agents=10, generations=12, change_at=6, bins=4, verification=panel
    )
    contract = result["budget_contract"]
    assert contract["per_strategy"] == 120
    # A bigger panel costs the same for every arm, so it cannot buy one of them
    # more evidence than another.
    assert contract["verifier_votes_per_strategy"] == 120 * panel.verifiers
    for row in result["results"]:
        assert row["verification_attempts"] == 120
        assert row["proposal_attempts"] == 120
        assert row["matched_evaluation_budget"] == 120
        assert row["bootstrap_anchors"] == 0
    perfect = benchmark.run_seed(5, agents=10, generations=12, change_at=6, bins=4)
    assert perfect["budget_contract"]["verifier_votes_per_strategy"] == 120


def test_imperfect_sweep_adds_provenance_catastrophe_counts_and_limitations():
    result = benchmark.sweep(
        seeds=4,
        seed_start=0,
        agents=10,
        generations=12,
        change_at=6,
        bins=4,
        verification=benchmark.measured_panel(),
    )
    assert result["configuration"]["panel_provenance"] == benchmark.PANEL_PROVENANCE
    assert result["configuration"]["verification"]["blind_spot"] == 0.0556
    catastrophes = result["catastrophic_seeds"]
    assert catastrophes["post_change_horizon"] == 6
    assert catastrophes["utility_auc_threshold"] == round(
        benchmark.CATASTROPHE_FRACTION * 6, 6
    )
    assert set(catastrophes["by_strategy"]) == set(benchmark.STRATEGIES)
    for counts in catastrophes["by_strategy"].values():
        assert counts["trials"] == 4
        assert 0 <= counts["seeds"] <= 4
    assert any("blind-spot" in limitation for limitation in result["limitations"])
    assert any("one-sided error" in limitation for limitation in result["limitations"])


def test_committed_imperfect_panel_reference_is_measured_and_honest():
    path = (
        Path(__file__).parents[1]
        / "experiments"
        / "results"
        / "E024-imperfect-panel-100-seed-summary.json"
    )
    result = benchmark.json.loads(path.read_text(encoding="utf-8"))
    assert result["experiment_id"] == "E024"
    assert result["configuration"]["seeds"] == 100
    assert result["configuration"]["verification"] == benchmark.measured_panel().as_dict()
    assert result["configuration"]["panel_provenance"]["measured_verifiers"] == 25
    # The whole point of the artifact: these were structurally zero before.
    for strategy in benchmark.STRATEGIES:
        aggregate = result["aggregate"][strategy]
        assert aggregate["false_accept_rate"]["mean"] > 0.05
        assert aggregate["false_reject_rate"]["mean"] > 0.05
        assert aggregate["panel_disagreement_rate"]["mean"] > 0.05
    assert result["catastrophic_seeds"]["by_strategy"]["qd"]["seeds"] == 0
    assert result["catastrophic_seeds"]["by_strategy"]["majority"]["seeds"] > 0
    assert any("synthetic" in limitation for limitation in result["limitations"])


def test_panel_flags_require_the_imperfect_panel_switch():
    import subprocess

    module = Path(__file__).parents[1] / "sim" / "matched_budget_emergence.py"
    completed = subprocess.run(
        [sys.executable, str(module), "--seeds", "2", "--verifier-accuracy", "0.8"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "--imperfect-panel" in completed.stderr
