#!/usr/bin/env python3
"""Minimal IDKMesh emergence simulator.

Compares three ways of searching under an initially vague objective:
  * random: unconstrained stochastic exploration plus verification gates;
  * scalar: evolution against one fixed scalar objective;
  * qd: constraint-guided Quality-Diversity archive over multiple plausible goals.

Verification can be perfect (the default) or performed by an imperfect panel with
controllable shared-error correlation and an irreducible shared blind spot. This
is intentionally a small falsifiable model, not evidence that open-ended
collective intelligence will work in production.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple

TRAITS = ("reliability", "adaptability", "efficiency", "simplicity", "security")
BUDGET = 3.2
MIN_RELIABILITY = 0.25
MIN_SECURITY = 0.25

INITIAL_GOAL = (0.30, 0.10, 0.25, 0.20, 0.15)
CHANGED_GOAL = (0.15, 0.35, 0.10, 0.10, 0.30)
PLAUSIBLE_GOALS = (
    INITIAL_GOAL,
    CHANGED_GOAL,
    (0.25, 0.20, 0.15, 0.15, 0.25),
    (0.20, 0.15, 0.30, 0.20, 0.15),
)


@dataclass(frozen=True)
class Candidate:
    traits: Tuple[float, ...]

    @staticmethod
    def random(rng: random.Random) -> "Candidate":
        raw = [rng.expovariate(1.0) for _ in TRAITS]
        total = sum(raw)
        spend = rng.uniform(BUDGET * 0.55, BUDGET)
        vals = [min(1.0, spend * x / total) for x in raw]
        return Candidate(_renormalize_budget(vals))

    def mutate(self, rng: random.Random, sigma: float = 0.12) -> "Candidate":
        vals = [max(0.0, min(1.0, x + rng.gauss(0.0, sigma))) for x in self.traits]
        return Candidate(_renormalize_budget(vals))


@dataclass(frozen=True)
class VerificationConfig:
    """Configuration for an imperfect verifier panel.

    ``accuracy`` is each verifier's probability of matching ground truth.
    ``correlation`` is a mixture weight for a shared correctness shock:
    at 0, verifier correctness is independent; at 1, all verifiers are correct
    or incorrect together. ``quorum`` is the fraction of positive votes that
    must be exceeded for the panel to accept a candidate.

    ``dependence`` selects HOW the verifiers depend on each other:

    ``"shared-shock"``
        The original mixture. Default, so every earlier experiment reproduces.
    ``"item-difficulty"``
        Each work unit draws its own difficulty ``d ~ Beta(alpha, beta)`` and
        every verifier then errs independently with probability ``d``. Takes the
        same two parameters, so the models are directly comparable -- they agree
        exactly at ``correlation`` 0 and 1 and differ only in between.

    E017 measured real verifiers and found the shared-shock shape wrong: it
    assigns near-zero probability to a panel failing *partially*, which is how
    most real panel failures look. See experiments/E017-item-difficulty-and-quorum.md.

    ``blind_spot`` is the irreducible fraction of work units that the *whole*
    panel gets wrong together, whatever its size and whatever the quorum. E020
    measured it on E017's 25 real partial oracles: 4 of 72 defects were missed
    by every single verifier, ``lambda = 0.0556``. Neither two-parameter model
    predicts that floor -- shared-shock puts it 2.13x too high, the plain
    beta-binomial has no floor at all and lands 1.77x too low -- so it is
    carried as its own parameter. Adding it turns the item-difficulty model
    into E020's one-inflated model. See
    experiments/E020-quorum-frontier-under-measured-shape.md.

    ``accuracy`` is the *marginal* accuracy of one verifier over all work units,
    blind-spot units included, so ``blind_spot`` may not exceed ``1 - accuracy``.
    """

    verifiers: int = 1
    accuracy: float = 1.0
    correlation: float = 0.0
    quorum: float = 0.5
    dependence: str = "shared-shock"
    blind_spot: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.blind_spot <= 1.0:
            raise ValueError("blind_spot must be in [0.0, 1.0]")
        if self.blind_spot > 1.0 - self.accuracy + 1e-12:
            raise ValueError(
                "blind_spot must not exceed the marginal error rate 1 - accuracy; "
                "a unit the whole panel misses is already an error for every "
                "verifier on it"
            )

    def as_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "verifiers": self.verifiers,
            "accuracy": self.accuracy,
            "correlation": self.correlation,
            "quorum": self.quorum,
            "dependence": self.dependence,
        }
        # The blind-spot atom was added after several reference artifacts were
        # published. Emitting the key only when the atom is armed keeps every
        # disarmed run's recorded configuration byte-identical to those
        # artifacts -- E024's committed 100-seed sweep among them.
        if self.blind_spot > 0.0:
            payload["blind_spot"] = self.blind_spot
        return payload


@dataclass
class VerificationStats:
    attempts: int = 0
    accepts: int = 0
    true_viable: int = 0
    true_nonviable: int = 0
    false_accepts: int = 0
    false_rejects: int = 0
    disagreement_panels: int = 0
    bootstrap_anchors: int = 0

    def as_metrics(self) -> Dict[str, object]:
        false_accept_rate = self.false_accepts / self.true_nonviable if self.true_nonviable else 0.0
        false_reject_rate = self.false_rejects / self.true_viable if self.true_viable else 0.0
        disagreement_rate = self.disagreement_panels / self.attempts if self.attempts else 0.0
        return {
            "verification_attempts": self.attempts,
            "verification_accepts": self.accepts,
            "false_accepts": self.false_accepts,
            "false_rejects": self.false_rejects,
            "false_accept_rate": round(false_accept_rate, 6),
            "false_reject_rate": round(false_reject_rate, 6),
            "panel_disagreement_rate": round(disagreement_rate, 6),
            "bootstrap_anchors": self.bootstrap_anchors,
        }


def _renormalize_budget(values: Sequence[float]) -> Tuple[float, ...]:
    vals = list(values)
    total = sum(vals)
    if total > BUDGET:
        scale = BUDGET / total
        vals = [x * scale for x in vals]
    return tuple(max(0.0, min(1.0, x)) for x in vals)


def viable(c: Candidate) -> bool:
    return (
        c.traits[0] >= MIN_RELIABILITY
        and c.traits[4] >= MIN_SECURITY
        and sum(c.traits) <= BUDGET + 1e-9
    )


def beta_parameters(accuracy: float, correlation: float):
    """Map (accuracy, correlation) onto Beta(alpha, beta) over task difficulty.

    The mean error rate is ``1 - accuracy`` and the intra-class correlation --
    which is exactly the pairwise error correlation between two verifiers on the
    same task -- is ``correlation``. Returns ``None`` at the degenerate ends,
    where the caller should sample directly instead.
    """
    mu = 1.0 - accuracy
    if correlation <= 0.0 or correlation >= 1.0 or mu <= 0.0 or mu >= 1.0:
        return None
    scale = (1.0 - correlation) / correlation
    return mu * scale, (1.0 - mu) * scale


def reducible_accuracy(accuracy: float, blind_spot: float) -> float:
    """Per-verifier accuracy on the work units outside the panel's blind spot.

    ``accuracy`` is the marginal accuracy over *all* units. A fraction
    ``blind_spot`` of them is missed by every verifier, so the rest must carry
    the remaining error:

        1 - accuracy = blind_spot + (1 - blind_spot) * (1 - reducible)

    This is exactly E020's one-inflated parameterisation. Checked against the
    measured panel: E017's marginal error 0.2044 with lambda 0.0556 gives
    0.1576, which is the reducible-only mean E020 fits directly from the votes.
    """
    if blind_spot <= 0.0:
        return accuracy
    if blind_spot >= 1.0:
        return 0.0
    return 1.0 - (1.0 - accuracy - blind_spot) / (1.0 - blind_spot)


def verify_candidate(c: Candidate, rng: random.Random, config: VerificationConfig, stats: VerificationStats) -> bool:
    """Return the verifier panel's decision and record error statistics.

    Perfect verification takes a fast path and does not consume random numbers,
    which keeps the original reference experiment reproducible.
    """

    truth = viable(c)
    stats.attempts += 1
    if truth:
        stats.true_viable += 1
    else:
        stats.true_nonviable += 1

    if config.accuracy >= 1.0:
        votes = [truth] * config.verifiers
    elif config.blind_spot > 0.0 and rng.random() < config.blind_spot:
        # A shared blind spot, not a correlated shock: every verifier is wrong
        # together and no panel size or quorum reaches past it (E020).
        votes = [not truth] * config.verifiers
    else:
        # Outside the blind spot the panel carries the reducible error only, so
        # the marginal per-verifier accuracy stays exactly `config.accuracy`.
        accuracy = reducible_accuracy(config.accuracy, config.blind_spot)
        if config.dependence == "item-difficulty":
            params = beta_parameters(accuracy, config.correlation)
            if params is None:
                # Degenerate ends: identical to the shared-shock model there.
                if config.correlation >= 1.0:
                    shared_correct = rng.random() < accuracy
                    correctness = [shared_correct] * config.verifiers
                else:
                    correctness = [rng.random() < accuracy
                                   for _ in range(config.verifiers)]
            else:
                difficulty = rng.betavariate(*params)
                correctness = [rng.random() >= difficulty
                               for _ in range(config.verifiers)]
        elif rng.random() < config.correlation:
            shared_correct = rng.random() < accuracy
            correctness = [shared_correct] * config.verifiers
        else:
            correctness = [rng.random() < accuracy for _ in range(config.verifiers)]
        votes = [truth if correct else not truth for correct in correctness]

    positive = sum(1 for vote in votes if vote)
    accepted = (positive / config.verifiers) > config.quorum

    stats.accepts += int(accepted)
    stats.false_accepts += int(accepted and not truth)
    stats.false_rejects += int((not accepted) and truth)
    stats.disagreement_panels += int(any(vote != votes[0] for vote in votes[1:]))
    return accepted


def utility(c: Candidate, weights: Sequence[float]) -> float:
    if not viable(c):
        return 0.0
    interaction = 0.08 * math.sqrt(c.traits[0] * c.traits[4])
    return min(1.0, sum(w * x for w, x in zip(weights, c.traits)) + interaction)


def robust_quality(c: Candidate) -> float:
    if not viable(c):
        return 0.0
    scores = [utility(c, w) for w in PLAUSIBLE_GOALS]
    return 0.75 * mean(scores) + 0.25 * min(scores)


def niche(c: Candidate, bins: int = 8) -> Tuple[int, int]:
    a = min(bins - 1, int(c.traits[1] * bins))
    e = min(bins - 1, int(c.traits[2] * bins))
    return (a, e)


def _goal_at(generation: int, change_at: int) -> Tuple[float, ...]:
    return INITIAL_GOAL if generation < change_at else CHANGED_GOAL


def _best_actual(population: Iterable[Candidate], goal: Sequence[float]) -> float:
    return max((utility(c, goal) for c in population), default=0.0)


def run_random(rng: random.Random, verifier_rng: random.Random, agents: int, generations: int, change_at: int, verification: VerificationConfig) -> Dict[str, object]:
    trace: List[float] = []
    stats = VerificationStats()
    for g in range(generations):
        batch = [Candidate.random(rng) for _ in range(agents)]
        accepted = [c for c in batch if verify_candidate(c, verifier_rng, verification, stats)]
        trace.append(_best_actual(accepted, _goal_at(g, change_at)))
    return _summary("random", trace, stats, archive_size=0, change_at=change_at)


def run_scalar(rng: random.Random, verifier_rng: random.Random, agents: int, generations: int, change_at: int, verification: VerificationConfig) -> Dict[str, object]:
    stats = VerificationStats()
    initial = [Candidate.random(rng) for _ in range(max(8, agents))]
    population = [c for c in initial if verify_candidate(c, verifier_rng, verification, stats)]
    if not population:
        population = [Candidate((0.5, 0.4, 0.7, 0.4, 0.5))]
        stats.bootstrap_anchors += 1

    trace: List[float] = []
    elite_count = max(2, min(32, agents // 4))

    for g in range(generations):
        ranked = sorted(population, key=lambda c: utility(c, INITIAL_GOAL), reverse=True)
        elites = ranked[:elite_count]
        offspring: List[Candidate] = []
        max_attempts = max(agents * 50, 100)
        attempts = 0
        while len(offspring) < agents and attempts < max_attempts:
            attempts += 1
            child = rng.choice(elites).mutate(rng)
            if verify_candidate(child, verifier_rng, verification, stats):
                offspring.append(child)
        population = elites + offspring
        trace.append(_best_actual(population, _goal_at(g, change_at)))
    return _summary("scalar", trace, stats, archive_size=0, change_at=change_at)


def run_qd(rng: random.Random, verifier_rng: random.Random, agents: int, generations: int, change_at: int, verification: VerificationConfig, bins: int = 8) -> Dict[str, object]:
    archive: Dict[Tuple[int, int], Candidate] = {}
    trace: List[float] = []
    stats = VerificationStats()

    def consider(c: Candidate) -> None:
        if not verify_candidate(c, verifier_rng, verification, stats):
            return
        key = niche(c, bins)
        incumbent = archive.get(key)
        if incumbent is None or robust_quality(c) > robust_quality(incumbent):
            archive[key] = c

    for _ in range(max(agents, bins * bins)):
        consider(Candidate.random(rng))

    for g in range(generations):
        parents = list(archive.values())
        for _ in range(agents):
            if parents and rng.random() < 0.85:
                candidate = rng.choice(parents).mutate(rng)
            else:
                candidate = Candidate.random(rng)
            consider(candidate)
        trace.append(_best_actual(archive.values(), _goal_at(g, change_at)))

    return _summary("qd", trace, stats, archive_size=len(archive), change_at=change_at)


def _summary(strategy: str, trace: List[float], stats: VerificationStats, archive_size: int, change_at: int) -> Dict[str, object]:
    pre_index = max(0, min(len(trace) - 1, change_at - 1))
    post_index = max(0, min(len(trace) - 1, change_at))
    final = trace[-1] if trace else 0.0
    pre = trace[pre_index] if trace else 0.0
    post = trace[post_index] if trace else 0.0

    target = 0.95 * final
    recovery = None
    for idx in range(post_index, len(trace)):
        if trace[idx] >= target:
            recovery = idx - post_index
            break

    post_trace = trace[post_index:] if trace else []
    result = {
        "strategy": strategy,
        "pre_change_best": round(pre, 6),
        "post_change_immediate": round(post, 6),
        "post_change_mean": round(mean(post_trace), 6) if post_trace else 0.0,
        "final_best": round(final, 6),
        "recovery_generations": recovery,
        "viable_evaluations": stats.true_viable,
        "archive_size": archive_size,
        "trace": [round(x, 6) for x in trace],
    }
    result.update(stats.as_metrics())
    return result


def run(strategy: str, seed: int, agents: int, generations: int, change_at: int, bins: int, verifiers: int = 1, verifier_accuracy: float = 1.0, verifier_correlation: float = 0.0, verification_quorum: float = 0.5, verifier_dependence: str = "shared-shock", verifier_blind_spot: float = 0.0) -> Dict[str, object]:
    verification = VerificationConfig(
        verifiers=verifiers,
        accuracy=verifier_accuracy,
        correlation=verifier_correlation,
        dependence=verifier_dependence,
        quorum=verification_quorum,
        blind_spot=verifier_blind_spot,
    )
    runners = {
        "random": lambda r, vr: run_random(r, vr, agents, generations, change_at, verification),
        "scalar": lambda r, vr: run_scalar(r, vr, agents, generations, change_at, verification),
        "qd": lambda r, vr: run_qd(r, vr, agents, generations, change_at, verification, bins),
    }
    if strategy == "all":
        results = []
        for offset, name in enumerate(("random", "scalar", "qd")):
            strategy_seed = seed + offset * 100003
            results.append(runners[name](random.Random(strategy_seed), random.Random(strategy_seed ^ 0x5EED5EED)))
        return {
            "experiment": "emergence-from-vague-goals-v1",
            "seed": seed,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "traits": list(TRAITS),
            "budget": BUDGET,
            "verification": verification.as_dict(),
            "results": results,
        }
    return {
        "experiment": "emergence-from-vague-goals-v1",
        "seed": seed,
        "agents": agents,
        "generations": generations,
        "change_at": change_at,
        "traits": list(TRAITS),
        "budget": BUDGET,
        "verification": verification.as_dict(),
        "results": [runners[strategy](random.Random(seed), random.Random(seed ^ 0x5EED5EED))],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=("random", "scalar", "qd", "all"), default="all")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--agents", type=int, default=200)
    parser.add_argument("--generations", type=int, default=120)
    parser.add_argument("--change-at", type=int, default=60)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--verifiers", type=int, default=1)
    parser.add_argument("--verifier-accuracy", type=float, default=1.0)
    parser.add_argument("--verifier-correlation", type=float, default=0.0)
    parser.add_argument("--verifier-dependence", choices=("shared-shock", "item-difficulty"),
                        default="shared-shock",
                        help="how verifiers depend on each other; E017 found "
                             "item-difficulty matches real panels better")
    parser.add_argument("--verifier-blind-spot", type=float, default=0.0,
                        help="irreducible fraction of work units the whole "
                             "panel gets wrong together; E020 measured 0.0556 "
                             "on E017's real 25-verifier panel")
    parser.add_argument("--verification-quorum", type=float, default=0.5)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.agents < 1:
        parser.error("--agents must be >= 1")
    if args.generations < 2:
        parser.error("--generations must be >= 2")
    if not 1 <= args.change_at < args.generations:
        parser.error("--change-at must satisfy 1 <= change-at < generations")
    if args.bins < 2:
        parser.error("--bins must be >= 2")
    if args.verifiers < 1:
        parser.error("--verifiers must be >= 1")
    if not 0.5 <= args.verifier_accuracy <= 1.0:
        parser.error("--verifier-accuracy must be between 0.5 and 1.0")
    if not 0.0 <= args.verifier_correlation <= 1.0:
        parser.error("--verifier-correlation must be between 0.0 and 1.0")
    if not 0.0 <= args.verification_quorum < 1.0:
        parser.error("--verification-quorum must be in [0.0, 1.0)")
    if not 0.0 <= args.verifier_blind_spot <= 1.0 - args.verifier_accuracy + 1e-12:
        parser.error(
            "--verifier-blind-spot must be in [0.0, 1 - verifier-accuracy]"
        )
    return args


def main() -> None:
    args = parse_args()
    result = run(
        args.strategy,
        args.seed,
        args.agents,
        args.generations,
        args.change_at,
        args.bins,
        verifiers=args.verifiers,
        verifier_accuracy=args.verifier_accuracy,
        verifier_correlation=args.verifier_correlation,
        verification_quorum=args.verification_quorum,
        verifier_dependence=args.verifier_dependence,
        verifier_blind_spot=args.verifier_blind_spot,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
