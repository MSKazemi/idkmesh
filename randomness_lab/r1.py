from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import random
from statistics import mean, stdev
from typing import Sequence

from .model import (
    CorrelatedBernoulliEnvironment,
    ItemDifficultyEnvironment,
    Worker,
)
from .policies import History, ThompsonSamplingPolicy


@dataclass(frozen=True)
class CandidateProfile:
    worker: Worker
    hidden_test_pass_probability: float = 0.95
    regression_probability: float = 0.03
    security_failure_probability: float = 0.01
    diversity_label: str = "same-structure"

    def __post_init__(self) -> None:
        for name, value in (
            ("hidden_test_pass_probability", self.hidden_test_pass_probability),
            ("regression_probability", self.regression_probability),
            ("security_failure_probability", self.security_failure_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class Verifier:
    name: str
    sensitivity: float = 0.97
    false_positive_rate: float = 0.03
    attention_cost: float = 0.10

    def __post_init__(self) -> None:
        if not 0.0 <= self.sensitivity <= 1.0:
            raise ValueError("sensitivity must be in [0, 1]")
        if not 0.0 <= self.false_positive_rate <= 1.0:
            raise ValueError("false_positive_rate must be in [0, 1]")
        if self.attention_cost < 0.0:
            raise ValueError("attention_cost must be non-negative")


WORKER_DEPENDENCE_SHAPES = {
    "shared_shock": CorrelatedBernoulliEnvironment,
    "item_difficulty": ItemDifficultyEnvironment,
}
PANEL_ATTENTION_BILLING_MODES = {"per_verifier", "per_candidate"}


PANEL_DEPENDENCE_SHAPES = ("shared_shock", "item_difficulty")


@dataclass(frozen=True)
class R1Condition:
    name: str
    profiles: tuple[CandidateProfile, ...]
    attempts_per_task: int
    worker_error_correlation: float
    scheduler: str = "first-k"
    verifier_assignment: str = "fixed"
    verifiers: tuple[Verifier, ...] = (Verifier("verifier-1"),)
    verifier_error_correlation: float = 0.50
    # Panel of distinct verifiers reading each candidate. `panel_size = 1` is
    # the single-verifier behaviour every committed R1 artifact was generated
    # under, and is reproduced draw-for-draw, not merely equivalently.
    #
    # `verifier_error_correlation` above is NOT dependence between panellists:
    # `shared_draws` is keyed per verifier name and drawn once per task, so it
    # couples one verifier's decisions across candidates within a task -- a
    # within-task strictness shock. E041 records two readings that went wrong by
    # assuming otherwise. Inter-panellist dependence, when it arrives, takes a
    # deliberately distinct name so the two can never be conflated.
    panel_size: int = 1
    # Fraction of the panel that must accept, in the sense
    # `sim/e018_dependence_models.py` uses: `need = floor(quorum * k) + 1`.
    # 0.5 is the symmetric majority, and is the only value E018 sweeps, so
    # keeping it as the default is what makes these numbers comparable to
    # E017/E018 at all. Sweeping it moves `need` across the whole `[1, k]`
    # range, which matters: at least one prior result here survives only on a
    # sub-range of `need` and dissolves once the full range is opened.
    panel_quorum: float = 0.5
    # Dependence BETWEEN panellists, which is what hypothesis 2's "independent
    # verification" half is about. Distinct from `verifier_error_correlation`
    # above on purpose -- that one is a within-task strictness shock on a single
    # verifier, and reusing its name here would rebuild the trap E041 records.
    #
    # 0.0 is independence and is the default, so every arm reproduces the
    # single-verifier and independent-panel behaviour draw for draw.
    panel_dependence_correlation: float = 0.0
    # `shared_shock` puts the mass on unanimity; `item_difficulty` is the
    # beta-binomial, which spreads it across partial panel failures. Both are
    # `sim/e018_dependence_models.py`'s, and they agree exactly at correlation
    # 0 and 1, so any difference between them is attributable to shape alone.
    panel_dependence_shape: str = "shared_shock"
    # The default bills every actual panel read. `per_candidate` is the explicit
    # counterfactual required by #380: one average-equivalent verifier read per
    # candidate, so heterogeneous verifier costs do not make the accounting
    # depend on panel ordering. Billing is accounting only and consumes no RNG.
    panel_attention_billing: str = "per_verifier"
    # Shape of the worker joint-failure distribution. "shared_shock" is the
    # historical behaviour and stays the default so every committed artifact
    # keeps reproducing; "item_difficulty" is the beta-binomial E017 measured
    # and E018 recomputed, matched to the same marginal and correlation.
    worker_dependence_shape: str = "shared_shock"

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("profiles must not be empty")
        if not 1 <= self.attempts_per_task <= len(self.profiles):
            raise ValueError("attempts_per_task must be between 1 and profile count")
        if not 0.0 <= self.worker_error_correlation <= 1.0:
            raise ValueError("worker_error_correlation must be in [0, 1]")
        if self.scheduler not in {"first-k", "thompson"}:
            raise ValueError("scheduler must be 'first-k' or 'thompson'")
        if self.verifier_assignment not in {"fixed", "random"}:
            raise ValueError("verifier_assignment must be 'fixed' or 'random'")
        if not self.verifiers:
            raise ValueError("verifiers must not be empty")
        verifier_names = [verifier.name for verifier in self.verifiers]
        if len(set(verifier_names)) != len(verifier_names):
            raise ValueError("verifier names must be unique within a panel pool")
        if not 0.0 <= self.verifier_error_correlation <= 1.0:
            raise ValueError("verifier_error_correlation must be in [0, 1]")
        if (
            isinstance(self.panel_size, bool)
            or not isinstance(self.panel_size, int)
            or self.panel_size < 1
        ):
            raise ValueError("panel_size must be a positive integer")
        if self.panel_size > len(self.verifiers):
            raise ValueError("panel_size must not exceed the verifier pool size")
        if not 0.0 <= self.panel_quorum < 1.0:
            raise ValueError("panel_quorum must be in [0, 1)")
        if not 0.0 <= self.panel_dependence_correlation <= 1.0:
            raise ValueError("panel_dependence_correlation must be in [0, 1]")
        if self.panel_dependence_shape not in PANEL_DEPENDENCE_SHAPES:
            raise ValueError(
                "panel_dependence_shape must be one of "
                f"{sorted(PANEL_DEPENDENCE_SHAPES)}"
            )
        if self.panel_attention_billing not in PANEL_ATTENTION_BILLING_MODES:
            raise ValueError(
                "panel_attention_billing must be one of "
                f"{sorted(PANEL_ATTENTION_BILLING_MODES)}"
            )
        if self.worker_dependence_shape not in WORKER_DEPENDENCE_SHAPES:
            raise ValueError(
                "worker_dependence_shape must be one of "
                f"{sorted(WORKER_DEPENDENCE_SHAPES)}"
            )


@dataclass(frozen=True)
class R1ExperimentConfig:
    tasks_per_trial: int = 500
    trials: int = 30
    swarm_size: int = 5
    base_seed: int = 42
    base_worker_success_probability: float = 0.68
    hidden_test_pass_probability: float = 0.94
    regression_probability: float = 0.03
    security_failure_probability: float = 0.01
    seed_only_error_correlation: float = 0.75
    structural_error_correlation: float = 0.25
    verifier_error_correlation: float = 0.60
    verifier_sensitivity: float = 0.97
    verifier_false_positive_rate: float = 0.03
    verifier_attention_cost: float = 0.10
    retain_task_records: bool = True

    def __post_init__(self) -> None:
        if self.tasks_per_trial < 1:
            raise ValueError("tasks_per_trial must be >= 1")
        if self.trials < 2:
            raise ValueError("trials must be >= 2 so uncertainty can be reported")
        if self.swarm_size < 2:
            raise ValueError("swarm_size must be >= 2")
        for name, value in (
            ("base_worker_success_probability", self.base_worker_success_probability),
            ("hidden_test_pass_probability", self.hidden_test_pass_probability),
            ("regression_probability", self.regression_probability),
            ("security_failure_probability", self.security_failure_probability),
            ("seed_only_error_correlation", self.seed_only_error_correlation),
            ("structural_error_correlation", self.structural_error_correlation),
            ("verifier_error_correlation", self.verifier_error_correlation),
            ("verifier_sensitivity", self.verifier_sensitivity),
            ("verifier_false_positive_rate", self.verifier_false_positive_rate),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.verifier_attention_cost < 0.0:
            raise ValueError("verifier_attention_cost must be non-negative")


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _make_profile(
    name: str,
    success_probability: float,
    config: R1ExperimentConfig,
    *,
    diversity_label: str,
) -> CandidateProfile:
    return CandidateProfile(
        worker=Worker(name, _clip_probability(success_probability)),
        hidden_test_pass_probability=config.hidden_test_pass_probability,
        regression_probability=config.regression_probability,
        security_failure_probability=config.security_failure_probability,
        diversity_label=diversity_label,
    )


def build_r1_conditions(config: R1ExperimentConfig) -> list[R1Condition]:
    n = config.swarm_size
    base = config.base_worker_success_probability
    fixed_verifier = Verifier(
        "verifier-1",
        sensitivity=config.verifier_sensitivity,
        false_positive_rate=config.verifier_false_positive_rate,
        attention_cost=config.verifier_attention_cost,
    )
    verifier_pool = tuple(
        Verifier(
            f"verifier-{index + 1}",
            sensitivity=config.verifier_sensitivity,
            false_positive_rate=config.verifier_false_positive_rate,
            attention_cost=config.verifier_attention_cost,
        )
        for index in range(max(3, min(n, 5)))
    )

    single = (
        _make_profile("worker-1", base, config, diversity_label="same-structure"),
    )
    identical = tuple(
        _make_profile(
            f"clone-{index + 1}",
            base,
            config,
            diversity_label="same-structure",
        )
        for index in range(n)
    )
    structural = tuple(
        _make_profile(
            f"role-{index + 1}",
            base,
            config,
            diversity_label=f"structure-{index + 1}",
        )
        for index in range(n)
    )

    bandit_pool_size = max(n * 2, n + 2)
    bandit_pool = []
    offsets = (-0.06, -0.03, 0.0, 0.03, 0.06)
    for index in range(bandit_pool_size):
        offset = offsets[index % len(offsets)]
        bandit_pool.append(
            _make_profile(
                f"adaptive-{index + 1}",
                base + offset,
                config,
                diversity_label=f"structure-{index + 1}",
            )
        )

    common_verifier_args = {
        "verifier_error_correlation": config.verifier_error_correlation,
    }
    return [
        R1Condition(
            name="single_deterministic",
            profiles=single,
            attempts_per_task=1,
            worker_error_correlation=0.0,
            verifiers=(fixed_verifier,),
            **common_verifier_args,
        ),
        R1Condition(
            name="identical_replication",
            profiles=identical,
            attempts_per_task=n,
            worker_error_correlation=1.0,
            verifiers=(fixed_verifier,),
            **common_verifier_args,
        ),
        R1Condition(
            name="seed_only",
            profiles=identical,
            attempts_per_task=n,
            worker_error_correlation=config.seed_only_error_correlation,
            verifiers=(fixed_verifier,),
            **common_verifier_args,
        ),
        R1Condition(
            name="structural_diversity",
            profiles=structural,
            attempts_per_task=n,
            worker_error_correlation=config.structural_error_correlation,
            verifiers=(fixed_verifier,),
            **common_verifier_args,
        ),
        R1Condition(
            name="bandit_selected",
            profiles=tuple(bandit_pool),
            attempts_per_task=n,
            worker_error_correlation=config.structural_error_correlation,
            scheduler="thompson",
            verifiers=(fixed_verifier,),
            **common_verifier_args,
        ),
        R1Condition(
            name="diverse_random_verifiers",
            profiles=structural,
            attempts_per_task=n,
            worker_error_correlation=config.structural_error_correlation,
            verifier_assignment="random",
            verifiers=verifier_pool,
            **common_verifier_args,
        ),
    ]


def _pearson_binary(xs: Sequence[int], ys: Sequence[int]) -> float | None:
    if len(xs) != len(ys) or not xs:
        return None
    mx = mean(xs)
    my = mean(ys)
    dx = [value - mx for value in xs]
    dy = [value - my for value in ys]
    denominator = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denominator == 0.0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / denominator


def _mean_pairwise_error_correlation(
    profiles: Sequence[CandidateProfile],
    latent_outcomes: dict[str, list[int]],
) -> float | None:
    correlations: list[float] = []
    for index, left in enumerate(profiles):
        left_errors = [1 - value for value in latent_outcomes[left.worker.name]]
        for right in profiles[index + 1 :]:
            right_errors = [1 - value for value in latent_outcomes[right.worker.name]]
            correlation = _pearson_binary(left_errors, right_errors)
            if correlation is not None:
                correlations.append(correlation)
    return mean(correlations) if correlations else None


def _select_profiles(
    condition: R1Condition,
    history: History,
    policy: ThompsonSamplingPolicy,
    rng: random.Random,
) -> list[CandidateProfile]:
    if condition.scheduler == "first-k":
        return list(condition.profiles[: condition.attempts_per_task])

    remaining = list(condition.profiles)
    selected: list[CandidateProfile] = []
    for _ in range(condition.attempts_per_task):
        chosen_worker = policy.select(
            [profile.worker for profile in remaining],
            history,
            rng,
        )
        chosen_index = next(
            index
            for index, profile in enumerate(remaining)
            if profile.worker.name == chosen_worker.name
        )
        selected.append(remaining.pop(chosen_index))
    return selected


def _verifier_accepts(
    is_good: bool,
    verifier: Verifier,
    rng: random.Random,
    shared_draw: float,
    correlation: float,
) -> bool:
    draw = shared_draw if rng.random() < correlation else rng.random()
    threshold = verifier.sensitivity if is_good else verifier.false_positive_rate
    return draw < threshold


def _verifier_accuracy(verifier: Verifier, is_good: bool) -> float:
    """Probability this verifier judges this candidate *correctly*.

    E018's models carry one ``accuracy``; ``_verifier_accepts`` carries two
    thresholds. Correct means accept for a good candidate and reject for a bad
    one, so panel dependence must be applied to the **error** event. Applying
    it to the accept event instead inverts the shape for bad candidates, which
    is the one way this can look right and be wrong.
    """

    return verifier.sensitivity if is_good else 1.0 - verifier.false_positive_rate


def _dependent_panel_votes(
    is_good: bool,
    panel: Sequence[Verifier],
    rng: random.Random,
    correlation: float,
    shape: str,
) -> list[bool]:
    """Accept/reject votes whose *errors* co-occur with ``correlation``.

    Reproduces `sim/e018_dependence_models.py` by construction, verified
    against its closed form rather than assumed: see
    ``tests/test_r1_panel_dependence.py``.
    """

    accuracies = [_verifier_accuracy(verifier, is_good) for verifier in panel]

    # Degenerate accuracies first: a Beta with a zero parameter is undefined,
    # and `rng.betavariate` raises from inside `gammavariate` rather than
    # saying so. A verifier that is never wrong, or always wrong, has no
    # dependence structure to model.
    if min(accuracies) <= 0.0 or max(accuracies) >= 1.0:
        correct = [rng.random() < accuracy for accuracy in accuracies]
    # The two endpoints are ONE implementation shared by both shapes, not two
    # that happen to coincide. At rho 0 and rho 1 the shapes are the same
    # distribution, so they should also consume the same RNG and return the
    # same vector for a seed -- otherwise "the shapes agree at the endpoints"
    # is only true on average, and cannot be asserted exactly.
    #
    # Sharing them also removes a whole class of edge case: `item_difficulty`
    # computes `(1 - rho) / rho`, which divides by zero at rho = 0, and its
    # rho = 1 branch was a separate special case that could drift from the
    # shared-shock one.
    elif correlation <= 0.0:
        correct = [rng.random() < accuracy for accuracy in accuracies]
    elif correlation >= 1.0:
        draw = rng.random()
        correct = [draw < accuracy for accuracy in accuracies]
    elif shape == "shared_shock":
        # With probability `correlation` the panel is judged on one draw.
        if rng.random() < correlation:
            draw = rng.random()
            correct = [draw < accuracy for accuracy in accuracies]
        else:
            correct = [rng.random() < accuracy for accuracy in accuracies]
    else:
        # Item difficulty: the candidate draws a difficulty, then panellists err
        # independently at that rate. Beta(mu*s, (1-mu)*s) with s = (1-rho)/rho
        # has mean mu and intra-class correlation 1/(alpha+beta+1) = rho, so the
        # parameter means what it says.
        #
        # E018's beta-binomial carries a single accuracy. A heterogeneous panel
        # would need a copula to keep each marginal correct, and guessing one
        # here would produce a plausible number with no stated meaning -- so
        # refuse instead. `shared_shock` has no such restriction: a shared draw
        # compared against each verifier's own threshold is well defined.
        if len(set(accuracies)) > 1:
            raise ValueError(
                "panel_dependence_shape='item_difficulty' needs an identically "
                "parameterised panel; this panel has accuracies "
                f"{sorted(set(accuracies))}. Use 'shared_shock' for a "
                "heterogeneous panel."
            )
        mu = 1.0 - accuracies[0]
        scale = (1.0 - correlation) / correlation
        difficulty = rng.betavariate(mu * scale, (1.0 - mu) * scale)
        correct = [rng.random() >= difficulty for _ in panel]

    # A correct vote accepts a good candidate and rejects a bad one.
    return [vote if is_good else not vote for vote in correct]


def _select_panel(
    condition: R1Condition, rng: random.Random
) -> tuple[Verifier, ...]:
    """Choose distinct verifiers that read one candidate.

    At ``panel_size == 1`` this makes exactly the draws the historical
    single-verifier implementation made -- none under ``fixed``, one
    ``rng.choice`` under ``random``. Multi-verifier random panels sample without
    replacement so repeating one verifier cannot be mistaken for evidence about
    dependence between distinct panellists.
    """

    if condition.verifier_assignment == "fixed":
        return condition.verifiers[: condition.panel_size]
    if condition.panel_size == 1:
        return (rng.choice(condition.verifiers),)
    return tuple(rng.sample(condition.verifiers, condition.panel_size))


def _panel_accepts(votes: Sequence[bool], quorum: float) -> bool:
    """Aggregate panel votes, using E018's ``need = floor(quorum * k) + 1``."""

    need = math.floor(quorum * len(votes)) + 1
    return sum(1 for vote in votes if vote) >= need


def _panel_attention_cost(
    panel: Sequence[Verifier], billing: str
) -> float:
    """Return panel attention under the explicit #380 billing counterfactual.

    ``per_verifier`` charges every actual read. ``per_candidate`` charges one
    average-equivalent verifier read for the candidate, which is order-invariant
    when verifier attention costs differ. The helper is deterministic and must
    not consume RNG state.
    """

    total = sum(verifier.attention_cost for verifier in panel)
    if billing == "per_candidate":
        return total / len(panel)
    return total


def run_r1_condition(
    condition: R1Condition,
    *,
    tasks: int,
    seed: int,
    retain_task_records: bool = True,
) -> dict[str, object]:
    if tasks < 1:
        raise ValueError("tasks must be >= 1")

    rng = random.Random(seed)
    history = History()
    policy = ThompsonSamplingPolicy()
    environment = WORKER_DEPENDENCE_SHAPES[condition.worker_dependence_shape](
        condition.worker_error_correlation
    )
    workers = [profile.worker for profile in condition.profiles]
    profile_by_name = {profile.worker.name: profile for profile in condition.profiles}
    latent_outcomes = {worker.name: [] for worker in workers}

    totals = {
        "verified_successes": 0,
        "candidate_any_good": 0,
        "selected_hidden_test_pass": 0,
        "selected_regressions": 0,
        "selected_security_failures": 0,
        "false_acceptances": 0,
        "abstentions": 0,
        "missed_good_candidates": 0,
        "compute": 0.0,
        "parallel_latency": 0.0,
        "human_attention": 0.0,
        "structural_diversity": 0.0,
    }
    task_records: list[dict[str, object]] = []

    for task_index in range(tasks):
        base_outcomes = environment.sample(workers, rng)
        for worker in workers:
            latent_outcomes[worker.name].append(int(base_outcomes[worker.name]))

        selected_profiles = _select_profiles(condition, history, policy, rng)
        candidate_records: list[dict[str, object]] = []
        for profile in selected_profiles:
            base_success = bool(base_outcomes[profile.worker.name])
            hidden_test_pass = bool(
                base_success and rng.random() < profile.hidden_test_pass_probability
            )
            regression = rng.random() < profile.regression_probability
            security_failure = rng.random() < profile.security_failure_probability
            is_good = bool(
                base_success
                and hidden_test_pass
                and not regression
                and not security_failure
            )
            candidate_records.append(
                {
                    "worker": profile.worker.name,
                    "diversity_label": profile.diversity_label,
                    "base_success": base_success,
                    "hidden_test_pass": hidden_test_pass,
                    "regression": regression,
                    "security_failure": security_failure,
                    "is_good": is_good,
                }
            )
            history.record(profile.worker, is_good)

        shared_draws = {verifier.name: rng.random() for verifier in condition.verifiers}
        for candidate in candidate_records:
            panel = _select_panel(condition, rng)
            if condition.panel_dependence_correlation <= 0.0:
                # Independent panellists: the original path, draw for draw.
                votes = [
                    _verifier_accepts(
                        bool(candidate["is_good"]),
                        verifier,
                        rng,
                        shared_draws[verifier.name],
                        condition.verifier_error_correlation,
                    )
                    for verifier in panel
                ]
            else:
                votes = _dependent_panel_votes(
                    bool(candidate["is_good"]),
                    panel,
                    rng,
                    condition.panel_dependence_correlation,
                    condition.panel_dependence_shape,
                )
            accepted = _panel_accepts(votes, condition.panel_quorum)
            candidate["verifier"] = panel[0].name
            candidate["accepted"] = accepted
            if len(panel) > 1:
                # Only emitted for a real panel, so single-verifier payloads
                # stay byte-identical to the committed artifacts.
                candidate["verifier_panel"] = [verifier.name for verifier in panel]
                candidate["verifier_votes"] = votes
            totals["human_attention"] += _panel_attention_cost(
                panel, condition.panel_attention_billing
            )

        accepted_candidates = [
            candidate for candidate in candidate_records if bool(candidate["accepted"])
        ]
        integrated = accepted_candidates[0] if accepted_candidates else None
        any_good = any(bool(candidate["is_good"]) for candidate in candidate_records)

        totals["candidate_any_good"] += int(any_good)
        totals["compute"] += sum(profile.worker.compute_cost for profile in selected_profiles)
        totals["parallel_latency"] += max(
            profile.worker.latency for profile in selected_profiles
        )
        totals["structural_diversity"] += len(
            {profile.diversity_label for profile in selected_profiles}
        ) / len(selected_profiles)

        if integrated is None:
            totals["abstentions"] += 1
            totals["missed_good_candidates"] += int(any_good)
        else:
            is_good = bool(integrated["is_good"])
            totals["verified_successes"] += int(is_good)
            totals["false_acceptances"] += int(not is_good)
            totals["selected_hidden_test_pass"] += int(
                bool(integrated["hidden_test_pass"])
            )
            totals["selected_regressions"] += int(bool(integrated["regression"]))
            totals["selected_security_failures"] += int(
                bool(integrated["security_failure"])
            )

        if retain_task_records:
            task_records.append(
                {
                    "task_index": task_index,
                    "selected_workers": [profile.worker.name for profile in selected_profiles],
                    "candidates": candidate_records,
                    "integrated_worker": integrated["worker"] if integrated else None,
                    "verified_success": bool(integrated and integrated["is_good"]),
                }
            )

    resource_cost = float(totals["compute"]) + float(totals["human_attention"])
    metrics = {
        "verified_successes": totals["verified_successes"],
        "verified_success_rate": totals["verified_successes"] / tasks,
        "candidate_any_good_rate": totals["candidate_any_good"] / tasks,
        "selected_hidden_test_pass_rate": totals["selected_hidden_test_pass"] / tasks,
        "selected_regression_rate": totals["selected_regressions"] / tasks,
        "selected_security_failure_rate": totals["selected_security_failures"] / tasks,
        "false_acceptance_rate": totals["false_acceptances"] / tasks,
        "abstention_rate": totals["abstentions"] / tasks,
        "missed_good_candidate_rate": totals["missed_good_candidates"] / tasks,
        "total_compute": totals["compute"],
        "mean_compute_per_task": totals["compute"] / tasks,
        "mean_parallel_latency_per_task": totals["parallel_latency"] / tasks,
        "total_human_attention_proxy": totals["human_attention"],
        "mean_human_attention_proxy_per_task": totals["human_attention"] / tasks,
        "mean_structural_diversity": totals["structural_diversity"] / tasks,
        "mean_pairwise_base_error_correlation": _mean_pairwise_error_correlation(
            condition.profiles, latent_outcomes
        ),
        "verified_utility_per_unit_cost": (
            totals["verified_successes"] / resource_cost if resource_cost else None
        ),
    }

    condition_record: dict[str, object] = {
        "name": condition.name,
        "attempts_per_task": condition.attempts_per_task,
        "worker_error_correlation": condition.worker_error_correlation,
        "scheduler": condition.scheduler,
        "verifier_assignment": condition.verifier_assignment,
        "verifier_error_correlation": condition.verifier_error_correlation,
        "worker_dependence_shape": condition.worker_dependence_shape,
        "profiles": [asdict(profile) for profile in condition.profiles],
        "verifiers": [asdict(verifier) for verifier in condition.verifiers],
    }
    if (
        condition.panel_size != 1
        or condition.panel_quorum != 0.5
        or condition.panel_attention_billing != "per_verifier"
    ):
        condition_record.update(
            {
                "panel_size": condition.panel_size,
                "panel_quorum": condition.panel_quorum,
                "panel_attention_billing": condition.panel_attention_billing,
            }
        )

    return {
        "schema_version": 1,
        "experiment": "R1-swarm-diversity",
        "condition": condition_record,
        "tasks": tasks,
        "seed": seed,
        "metrics": metrics,
        "task_records": task_records,
    }


def _normal_95_interval(values: Sequence[float]) -> list[float]:
    center = mean(values)
    standard_error = stdev(values) / math.sqrt(len(values))
    margin = 1.96 * standard_error
    return [center - margin, center + margin]


def _summarize_trials(trials: Sequence[dict[str, object]]) -> dict[str, object]:
    metric_names = (
        "verified_success_rate",
        "candidate_any_good_rate",
        "selected_hidden_test_pass_rate",
        "selected_regression_rate",
        "selected_security_failure_rate",
        "false_acceptance_rate",
        "abstention_rate",
        "missed_good_candidate_rate",
        "mean_compute_per_task",
        "mean_parallel_latency_per_task",
        "mean_human_attention_proxy_per_task",
        "mean_structural_diversity",
        "verified_utility_per_unit_cost",
    )
    summary: dict[str, object] = {}
    for metric_name in metric_names:
        values = [float(trial["metrics"][metric_name]) for trial in trials]
        summary[metric_name] = {
            "mean": mean(values),
            "sample_std": stdev(values),
            "normal_approx_95_ci": _normal_95_interval(values),
            "min": min(values),
            "max": max(values),
        }

    correlations = [
        trial["metrics"]["mean_pairwise_base_error_correlation"] for trial in trials
    ]
    defined = [float(value) for value in correlations if value is not None]
    summary["mean_pairwise_base_error_correlation"] = {
        "mean": mean(defined) if defined else None,
        "sample_std": stdev(defined) if len(defined) > 1 else 0.0 if defined else None,
        "normal_approx_95_ci": _normal_95_interval(defined) if len(defined) > 1 else None,
        "min": min(defined) if defined else None,
        "max": max(defined) if defined else None,
    }
    return summary


def run_r1_experiment(config: R1ExperimentConfig) -> dict[str, object]:
    condition_results: dict[str, object] = {}
    conditions = build_r1_conditions(config)

    for condition in conditions:
        trials = [
            run_r1_condition(
                condition,
                tasks=config.tasks_per_trial,
                seed=config.base_seed + trial_index,
                retain_task_records=config.retain_task_records,
            )
            for trial_index in range(config.trials)
        ]
        condition_results[condition.name] = {
            "configured_worker_error_correlation": condition.worker_error_correlation,
            "raw_trials": trials,
            "summary": _summarize_trials(trials),
        }

    baseline = condition_results["identical_replication"]["summary"]
    comparisons: dict[str, object] = {}
    for condition in conditions:
        if condition.name == "identical_replication":
            continue
        summary = condition_results[condition.name]["summary"]
        delta_success = (
            summary["verified_success_rate"]["mean"]
            - baseline["verified_success_rate"]["mean"]
        )
        delta_utility = (
            summary["verified_utility_per_unit_cost"]["mean"]
            - baseline["verified_utility_per_unit_cost"]["mean"]
        )
        comparisons[condition.name] = {
            "baseline": "identical_replication",
            "delta_mean_verified_success_rate": delta_success,
            "delta_mean_verified_utility_per_unit_cost": delta_utility,
            "lower_success_than_replication": delta_success < 0.0,
            "lower_utility_than_replication": delta_utility < 0.0,
        }

    return {
        "schema_version": 1,
        "experiment": "R1-swarm-diversity",
        "config": asdict(config),
        "conditions": condition_results,
        "comparisons": comparisons,
        "interpretation_guardrail": (
            "This is a synthetic controlled experiment. Negative results are retained. "
            "Do not infer that more agents or biological/stochastic diversity improves real coding work "
            "without validation on independent real task benchmarks."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1",
        description="Run the IDKMesh R1 synthetic swarm-diversity experiment.",
    )
    parser.add_argument("--tasks", type=int, default=500)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--swarm-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--worker-success", type=float, default=0.68)
    parser.add_argument("--seed-only-correlation", type=float, default=0.75)
    parser.add_argument("--structural-correlation", type=float, default=0.25)
    parser.add_argument("--no-task-records", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r1_experiment(
        R1ExperimentConfig(
            tasks_per_trial=args.tasks,
            trials=args.trials,
            swarm_size=args.swarm_size,
            base_seed=args.seed,
            base_worker_success_probability=args.worker_success,
            seed_only_error_correlation=args.seed_only_correlation,
            structural_error_correlation=args.structural_correlation,
            retain_task_records=not args.no_task_records,
        )
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
