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


def _panel_error_rate(config, trials: int = 4000, seed: int = 20240829) -> float:
    """Fraction of panel decisions that disagree with ground truth.

    Alternating one viable and one non-viable candidate keeps both error
    directions in the estimate, which is what an effective-panel-size claim
    needs.
    """
    stats = sim.VerificationStats()
    rng = sim.random.Random(seed)
    candidates = (
        sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5)),
        sim.Candidate((0.1, 0.8, 0.8, 0.8, 0.7)),
    )
    for index in range(trials):
        sim.verify_candidate(candidates[index % 2], rng, config, stats)
    return (stats.false_accepts + stats.false_rejects) / stats.attempts


def test_reducible_accuracy_reproduces_the_e020_one_inflated_fit():
    # E020 fits E017's votes twice: over every task (mu=0.2044) and over the
    # tasks outside the panel's blind spot (mu=0.1576, lambda=0.0556). The
    # reparameterisation used here must land on the same reducible mean, or the
    # marginal accuracy this module advertises would not be the measured one.
    reducible = sim.reducible_accuracy(0.7956, 0.0556)
    assert abs((1.0 - reducible) - 0.1576) < 5e-4


def test_blind_spot_may_not_exceed_the_marginal_error_rate():
    for accuracy, blind_spot in ((0.9, 0.2), (1.0, 0.05)):
        try:
            sim.VerificationConfig(accuracy=accuracy, blind_spot=blind_spot)
        except ValueError:
            continue
        raise AssertionError(
            f"accepted incoherent panel accuracy={accuracy} blind_spot={blind_spot}"
        )


def test_disarmed_blind_spot_is_absent_from_the_recorded_configuration():
    # Reference artifacts published before the atom existed record five keys.
    # Emitting a sixth would make them stop reproducing.
    assert set(sim.VerificationConfig().as_dict()) == {
        "verifiers",
        "accuracy",
        "correlation",
        "quorum",
        "dependence",
    }
    armed = sim.VerificationConfig(accuracy=0.8, blind_spot=0.05).as_dict()
    assert armed["blind_spot"] == 0.05


def test_disarmed_blind_spot_leaves_the_random_stream_untouched():
    # The atom is drawn before the dependence model, so a disarmed atom must
    # short-circuit rather than burn a draw and shift every later sample. These
    # counts were produced by the implementation that predates the atom; if the
    # disarmed path ever consumes a random number they all change, and every
    # artifact published with a perfect or atom-free panel stops reproducing.
    published = {
        "shared-shock": (258, 44, 36, 249),
        "item-difficulty": (256, 52, 46, 263),
    }
    candidates = (
        sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5)),
        sim.Candidate((0.1, 0.8, 0.8, 0.8, 0.7)),
    )
    for dependence, expected in published.items():
        config = sim.VerificationConfig(
            verifiers=7, accuracy=0.75, correlation=0.4, dependence=dependence
        )
        rng = sim.random.Random(4)
        stats = sim.VerificationStats()
        for index in range(500):
            sim.verify_candidate(candidates[index % 2], rng, config, stats)
        assert (
            stats.accepts,
            stats.false_accepts,
            stats.false_rejects,
            stats.disagreement_panels,
        ) == expected, dependence


def test_arming_the_blind_spot_does_change_the_panel():
    # The mirror of the test above: the atom must not be a no-op either.
    candidate = sim.Candidate((0.5, 0.4, 0.7, 0.4, 0.5))
    disarmed = sim.VerificationConfig(verifiers=7, accuracy=0.75, correlation=0.0)
    armed = sim.VerificationConfig(
        verifiers=7, accuracy=0.75, correlation=0.0, blind_spot=0.2
    )
    errors = []
    for config in (disarmed, armed):
        rng = sim.random.Random(9)
        stats = sim.VerificationStats()
        for _ in range(2000):
            sim.verify_candidate(candidate, rng, config, stats)
        errors.append(stats.false_rejects / stats.attempts)
    assert errors[1] > errors[0] + 0.1


def test_correlation_collapses_the_effective_panel_size():
    # 25 verifiers at E017's measured marginal accuracy. Independent errors let
    # the majority vote average them away; correlated errors do not, which is
    # the mechanism behind E017's "25 verifiers are worth 1".
    single = _panel_error_rate(
        sim.VerificationConfig(verifiers=1, accuracy=0.7956, correlation=0.0)
    )
    independent = _panel_error_rate(
        sim.VerificationConfig(
            verifiers=25, accuracy=0.7956, correlation=0.0,
            dependence="item-difficulty",
        )
    )
    correlated = _panel_error_rate(
        sim.VerificationConfig(
            verifiers=25, accuracy=0.7956, correlation=0.9,
            dependence="item-difficulty",
        )
    )
    assert 0.15 < single < 0.25
    assert independent < 0.01
    assert independent < correlated
    # Effective panel size, read as the error reduction the panel actually buys.
    assert single / independent > 20.0
    assert single / correlated < 2.0


def test_blind_spot_floor_is_not_escapable_by_growing_the_panel():
    # A shared blind spot is not a correlated shock: you escape a shock by
    # decorrelating and by adding verifiers, but nothing reaches past lambda.
    floor = 0.2
    errors = [
        _panel_error_rate(
            sim.VerificationConfig(
                verifiers=size, accuracy=0.6, correlation=0.0,
                blind_spot=floor, dependence="item-difficulty",
            )
        )
        for size in (3, 25, 201)
    ]
    for size, error in zip((3, 25, 201), errors):
        assert error > 0.8 * floor, f"panel of {size} fell below the floor: {error}"
    # Without the atom the same reducible accuracy is averaged away entirely,
    # so the floor and not the panel size is what stops the improvement.
    without_atom = _panel_error_rate(
        sim.VerificationConfig(
            verifiers=201, accuracy=0.75, correlation=0.0,
            dependence="item-difficulty",
        )
    )
    assert without_atom < 0.01
    assert errors[-1] > 20 * without_atom
