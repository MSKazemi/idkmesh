import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "emergence_sim.py"
spec = importlib.util.spec_from_file_location("emergence_sim", MODULE_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_random_candidate_respects_bounds_and_budget():
    rng = sim.random.Random(11)
    for _ in range(1000):
        c = sim.Candidate.random(rng)
        assert all(0.0 <= x <= 1.0 for x in c.traits)
        assert sum(c.traits) <= sim.BUDGET + 1e-9


def test_same_seed_is_deterministic():
    a = sim.run("all", seed=5, agents=50, generations=30, change_at=15, bins=6)
    b = sim.run("all", seed=5, agents=50, generations=30, change_at=15, bins=6)
    assert a == b


def test_qd_maintains_multiple_niches():
    result = sim.run("qd", seed=7, agents=80, generations=40, change_at=20, bins=6)
    qd = result["results"][0]
    assert qd["archive_size"] >= 10


def test_qd_beats_fixed_scalar_after_goal_change_for_reference_seed():
    result = sim.run("all", seed=7, agents=120, generations=70, change_at=35, bins=8)
    rows = {r["strategy"]: r for r in result["results"]}
    assert rows["qd"]["post_change_mean"] > rows["scalar"]["post_change_mean"]


def test_perfect_verifier_matches_ground_truth():
    config = sim.VerificationConfig(verifiers=5, accuracy=1.0, correlation=1.0, quorum=0.5)
    stats = sim.VerificationStats()
    rng = sim.random.Random(1)
    good = sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5))
    bad = sim.Candidate((0.1, 0.8, 0.8, 0.8, 0.7))

    assert sim.viable(good)
    assert not sim.viable(bad)
    assert sim.verify_candidate(good, rng, config, stats)
    assert not sim.verify_candidate(bad, rng, config, stats)
    assert stats.false_accepts == 0
    assert stats.false_rejects == 0
    assert stats.disagreement_panels == 0


def test_full_correlation_eliminates_within_panel_disagreement():
    config = sim.VerificationConfig(verifiers=7, accuracy=0.75, correlation=1.0, quorum=0.5)
    stats = sim.VerificationStats()
    rng = sim.random.Random(123)
    candidates = [
        sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5)),
        sim.Candidate((0.1, 0.8, 0.8, 0.8, 0.7)),
    ]

    for i in range(400):
        sim.verify_candidate(candidates[i % 2], rng, config, stats)

    assert stats.disagreement_panels == 0
    assert stats.false_accepts + stats.false_rejects > 0


def test_independent_imperfect_verifiers_can_disagree():
    config = sim.VerificationConfig(verifiers=7, accuracy=0.75, correlation=0.0, quorum=0.5)
    stats = sim.VerificationStats()
    rng = sim.random.Random(123)
    candidate = sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5))

    for _ in range(200):
        sim.verify_candidate(candidate, rng, config, stats)

    assert stats.disagreement_panels > 0


def test_imperfect_verifier_run_reports_error_metrics():
    result = sim.run(
        "all",
        seed=7,
        agents=40,
        generations=20,
        change_at=10,
        bins=5,
        verifiers=5,
        verifier_accuracy=0.75,
        verifier_correlation=0.8,
        verification_quorum=0.5,
    )
    assert result["verification"]["verifiers"] == 5
    for row in result["results"]:
        assert row["verification_attempts"] > 0
        assert 0.0 <= row["false_accept_rate"] <= 1.0
        assert 0.0 <= row["false_reject_rate"] <= 1.0
        assert 0.0 <= row["panel_disagreement_rate"] <= 1.0
