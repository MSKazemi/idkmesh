import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:  # Broad unittest CI intentionally installs no extras.
    jsonschema = None

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "e025_learned_verifiers", ROOT / "sim" / "e025_learned_verifiers.py"
)
sim = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sim
assert SPEC.loader is not None
SPEC.loader.exec_module(sim)


def test_deterministic_replay_and_disjoint_streams():
    verifiers = sim.panel(sim.BASE_ACCURACY)
    first = sim.generate_stream(verifiers, .7, "item-difficulty", 200, 123)
    assert first == sim.generate_stream(verifiers, .7, "item-difficulty", 200, 123)
    assert first != sim.generate_stream(verifiers, .7, "item-difficulty", 200, 124)
    assert sim.stream_digest(first) == sim.stream_digest(first)


def test_heldout_is_independent_of_history_length_and_prediction_cannot_see_truth():
    scenario = sim.SCENARIOS[1]
    heldout_a = sim.generate_stream(sim.panel(scenario.evaluation_accuracy), .7,
                                    "item-difficulty", 200, 2_000_003)
    # The evaluation namespace does not involve history length or calibration RNG.
    sim.generate_stream(sim.panel(scenario.calibration_accuracy), .7,
                        "item-difficulty", 40, 1_000_003)
    heldout_b = sim.generate_stream(sim.panel(scenario.evaluation_accuracy), .7,
                                    "item-difficulty", 200, 2_000_003)
    assert heldout_a == heldout_b
    assert tuple(inspect.signature(sim.predict_probabilities).parameters) == ("votes", "model")


def test_calibration_learns_high_dependence_and_reports_uncertainty():
    verifiers = sim.panel(sim.BASE_ACCURACY)
    history = sim.generate_stream(verifiers, .7, "item-difficulty", 2000, 99)
    model = sim.calibrate(verifiers, history)
    cluster = next(c for c in model.inferred_clusters if 0 in c)
    assert set(range(7)).issubset(cluster)
    assert all(low < value < high for low, value, high in zip(
        model.accuracy_ci_low, model.accuracy_mean, model.accuracy_ci_high
    ))


def test_all_required_baselines_share_one_vote_vector():
    verifiers = sim.panel(sim.BASE_ACCURACY)
    history = sim.generate_stream(verifiers, .7, "shared-shock", 400, 17)
    model = sim.calibrate(verifiers, history)
    probabilities = sim.predict_probabilities((True,) * len(verifiers), model)
    assert tuple(probabilities) == sim.METHODS
    assert all(0 <= value <= 1 for value in probabilities.values())


def test_empirical_effective_size_compares_error_on_both_sides():
    assert sim.independent_error(1, .75) == .25
    assert sim.independent_error(3, .75) == .15625
    assert sim.empirical_neff(.75, .75, 3) == 1
    assert sim.empirical_neff(.84375, .75, 3) == 3
    assert math.isclose(
        sim.empirical_neff(.80, .75, 3),
        sim.e015_effective_n(.20, .75, .5, nmax=5),
    )
    assert 1 < sim.empirical_neff(.80, .75, 3) < 3
    assert sim.empirical_neff(.70, .49, 3) == 1


def test_experiment_preserves_both_improvement_and_harm_regimes():
    result = sim.run_experiment((200,), heldout_trials=600, seeds=8)
    assert result["findings"]["improvement_observed"] is True
    assert result["findings"]["harm_observed"] is True
    stable = next(c for c in result["cells"] if c["scenario"] == "stable_item_difficulty")
    shifted = next(c for c in result["cells"] if c["scenario"] == "reliability_shift")
    emerged = next(c for c in result["cells"] if c["scenario"] == "dependence_emerges")
    assert stable["metrics"]["combined_reliability_dependence"]["error_rate"]["mean"] < \
        stable["metrics"]["naive_majority"]["error_rate"]["mean"]
    assert shifted["metrics"]["combined_reliability_dependence"]["error_rate"]["mean"] > \
        shifted["metrics"]["naive_majority"]["error_rate"]["mean"]
    assert emerged["heldout_correlation_misspecification"][
        "overestimated_independence_pair_rate"
    ]["mean"] > .3


def test_machine_result_has_uncertainty_false_confidence_and_model_shape_warning():
    result = sim.run_experiment((40,), heldout_trials=100, seeds=2,
                                scenarios=(sim.SCENARIOS[1],))
    cell = result["cells"][0]
    assert "ci95_low" in cell["metrics"]["naive_majority"]["error_rate"]
    assert "high_confidence_error_rate" in cell["metrics"]["bayesian_reliability"]
    assert "overestimated_independence_pair_rate" in cell["correlation_estimation"]
    assert any("E018" in limitation for limitation in result["limitations"])
    schema = json.loads((ROOT / "schemas" / "e025-learned-verifier-result.schema.json").read_text())
    if jsonschema is not None:
        jsonschema.Draft202012Validator(schema).validate(result)
    else:
        assert set(schema["required"]).issubset(result)


def test_committed_artifact_validates_and_reproduces_exactly():
    artifact = ROOT / "experiments" / "results" / "E025-learned-verifier-results.json"
    committed = json.loads(artifact.read_text())
    schema = json.loads((ROOT / "schemas" / "e025-learned-verifier-result.schema.json").read_text())
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(committed)
        malformed_metric = json.loads(json.dumps(committed))
        del malformed_metric["cells"][0]["metrics"]["naive_majority"]["error_rate"]["ci95_low"]
        assert list(validator.iter_errors(malformed_metric))
        malformed_uncertainty = json.loads(json.dumps(committed))
        malformed_uncertainty["cells"][0]["model_uncertainty"][
            "mean_accuracy_ci95_width"
        ]["n"] = "twenty"
        assert list(validator.iter_errors(malformed_uncertainty))
    else:
        assert set(schema["required"]).issubset(committed)
    config = committed["configuration"]
    reproduced = sim.run_experiment(
        tuple(config["history_trials"]), config["heldout_trials"],
        config["seeds"], config["seed_start"],
    )
    assert reproduced == committed
