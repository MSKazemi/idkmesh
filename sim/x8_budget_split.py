#!/usr/bin/env python3
"""X8 -- can the best worker/verifier budget split be predicted from measured dependence?

Program item X8 (issue 981, hypothesis H4, algorithm A6).  H4 says the best way to
divide a fixed budget between worker attempts and verifier reads is predictable from two
measured dependence shapes (worker difficulty from X3, verifier difficulty from X6/X7)
and one cross term, and that the prediction beats fixed splits.

THE REAL-DATA TEST CANNOT BE RUN YET.  It needs, for the same tasks, worker outcomes
*and* verifier verdicts on the candidates those workers produced, with correctness
labels, plus measured per-attempt and per-read costs.  The repository holds no such
matrix: X6 (issue 979) is blocked, X7 (issue 980) is open, and E016/E017/E043 are
partial-oracle, synthetic or program panels.  This module therefore does the part that
can be done honestly and is NOT evidence about real coding agents:

* ``predicted_surface`` / ``fit_model``: the deterministic predictor (A6).  It consumes
  only what a real X3 + X6 pilot would provide, a list of ``TaskObservation`` records.
* a synthetic ``World`` with a known generating process, deliberately *different* in
  form from the predictor's model (atoms at zero worker skill and at total verifier
  blindness; a mean-shift cross term instead of the predictor's Gaussian copula), so the
  predictor is exposed to model misspecification and not only estimation noise.
* a held-out evaluation, preregistered below in code, against the three baselines named
  in the issue (all workers, 50/50, all verifiers) plus two controls.

The pipeline being allocated
----------------------------
An allocation is ``(n, m)``: ``n`` worker attempts on a task, each read by ``m``
independent verifier reads, costing ``n * (c_w + m * c_v)`` with ``c_w = 1``.  A
candidate is accepted when at least ``need(m)`` reads vote accept (strict majority or
unanimity, fixed per scenario).  The task ends with the first accepted candidate; no
accepted candidate means the task is escalated to a human.  Per task, with ``p`` the
chance one attempt is correct and ``d`` the chance one read accepts a wrong candidate
(reads are conditionally independent given ``d``)::

    pc = p * P(Bin(m, 1 - r) >= need)        correct and accepted
    pw = (1 - p) * P(Bin(m, d) >= need)      wrong and accepted
    V = pc / (pc + pw) * (1 - (1 - pc - pw) ** n)     verified-correct
    E = pw / (pc + pw) * (1 - (1 - pc - pw) ** n)     escaped defect
    U = (1 - pc - pw) ** n                            escalated, nothing accepted

``(V, E, U)`` and the two cost components are the outcome *vector* the program asks for;
the full vector (latency, human attention, energy, ...) is not simulated.

Preregistration (frozen here, before any scenario was scored)
-------------------------------------------------------------
* Scenario grid, pilot size, held-out size, replicates and strategies are the module
  constants below.  Nothing was tuned after seeing a result.
* Primary comparison: held-out expected verified value ``V``, paired by replicate,
  predicted split (joint model) against each baseline.
* Per-scenario verdict: ``predicted_wins`` when the paired mean difference to *every*
  baseline exceeds two standard errors; ``baseline_wins`` when any baseline exceeds the
  predicted split by two standard errors; otherwise ``tie``.  The issue's falsifier
  ("a baseline matches or beats the prediction within uncertainty") is the complement of
  ``predicted_wins``.
* Truth for a held-out task set is the exact expectation of ``(V, E, U)`` over the
  candidate and read randomness given each task's true latent ``(p, d)``; a Monte Carlo
  realisation (``simulate_outcome``) is tested to agree with the closed form.

Standard library only; deterministic for a fixed seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Callable, Iterable, Mapping, Sequence

GENERATOR = "idkmesh.sim.x8_budget_split.v1"
DEFAULT_OUT = "experiments/results/X8-budget-split.json"

# ---- frozen design constants -------------------------------------------------------
C_W = 1.0                 # cost of one worker attempt (the unit)
M_MAX = 15                # most reads per candidate the grid considers
PILOT_TASKS = 200         # tasks in the fitting pilot
PILOT_WORKERS = 8         # k_w: attempts per pilot task
PILOT_READS = 4           # k_v: reads per pilot candidate
HELD_OUT_TASKS = 400      # held-out tasks per replicate, disjoint from the pilot
SMALL_PILOT_TASKS = 40    # sensitivity run: a pilot five times smaller
REPLICATES = 16
QUANTILE_SAMPLE = 4000    # draws used to tabulate a fitted Beta's quantile function
GRID_K = 30               # predictor integrates on a K x K grid of normal midpoints
ICC_FLOOR, ICC_CEIL = 0.02, 0.95
CROSS_CLIP = 0.95
Z_DECISIVE = 2.0

# World constants shared by every scenario.
WORLD_BASE = {
    "worker_mean": 0.35,
    "worker_icc": 0.4,
    "lambda_w": 0.08,
    "fa_mean": 0.35,
    "lambda_v": 0.05,
    "false_reject": 0.1,
}
COST_RATIOS = (0.1, 0.5)
BUDGETS = (6.0, 12.0)
CROSS_TERMS = (0.0, 0.6)
VERIFIER_ICCS = (0.1, 0.5)
RULES = ("majority", "unanimity")

STRATEGIES = (
    "oracle",
    "predicted_joint",
    "predicted_independent",
    "all_workers",
    "fifty_fifty",
    "all_verifiers",
    "random_allocation",
    "broken_predictor",
)
BASELINES = ("all_workers", "fifty_fifty", "all_verifiers")

Allocation = tuple[int, int]
Triple = tuple[float, float, float]


# ---- small numeric helpers ---------------------------------------------------------
def clamp(x: float, low: float, high: float) -> float:
    return low if x < low else high if x > high else x


def need_votes(m: int, rule: str) -> int:
    """Reads that must accept for a candidate of ``m`` reads to be accepted."""
    if rule == "majority":
        return m // 2 + 1
    if rule == "unanimity":
        return m
    raise ValueError(f"unknown acceptance rule: {rule!r}")


def binomial_tail(m: int, q: float, need: int) -> float:
    """P(Bin(m, q) >= need), exact."""
    if need <= 0:
        return 1.0
    if need > m:
        return 0.0
    return sum(math.comb(m, k) * q**k * (1.0 - q) ** (m - k) for k in range(need, m + 1))


def beta_shape(mean: float, icc: float) -> tuple[float, float]:
    """Beta(a, b) with the given mean and intra-class correlation 1 / (a + b + 1)."""
    mean = clamp(mean, 1e-3, 1 - 1e-3)
    icc = clamp(icc, ICC_FLOOR, ICC_CEIL)
    scale = (1.0 - icc) / icc
    return mean * scale, (1.0 - mean) * scale


def derive_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


# ---- the synthetic world (ground truth) --------------------------------------------
@dataclass(frozen=True)
class World:
    """Generating process for synthetic tasks; each task has latent ``(p, d)``.

    ``p`` is the chance one worker attempt is correct.  With probability ``lambda_w`` the
    task is worker-blind (``p = 0``).  ``d`` is the chance one verifier read accepts a
    wrong candidate.  With probability ``lambda_v`` the task is verifier-blind
    (``d = 1``).  Otherwise ``d`` is Beta with mean ``fa_mean + cross * (fail - E[fail])``
    where ``fail = 1 - p``: positive ``cross`` means verifiers are fooled on exactly the
    tasks where workers fail, the cross-dependence of the program's formal statement.
    """

    worker_mean: float
    worker_icc: float
    lambda_w: float
    fa_mean: float
    fa_icc: float
    lambda_v: float
    cross: float
    false_reject: float
    rule: str


def draw_tasks(world: World, count: int, rng: random.Random) -> list[tuple[float, float]]:
    a_w, b_w = beta_shape(world.worker_mean, world.worker_icc)
    reference_fail = 1.0 - world.worker_mean
    tasks: list[tuple[float, float]] = []
    for _ in range(count):
        p = 0.0 if rng.random() < world.lambda_w else rng.betavariate(a_w, b_w)
        if rng.random() < world.lambda_v:
            d = 1.0
        else:
            mean_d = clamp(world.fa_mean + world.cross * ((1.0 - p) - reference_fail), 0.02, 0.98)
            a_d, b_d = beta_shape(mean_d, world.fa_icc)
            d = rng.betavariate(a_d, b_d)
        tasks.append((p, d))
    return tasks


# ---- the closed-form pipeline and its Monte Carlo twin -----------------------------
def task_outcome(p: float, d: float, n: int, m: int, rule: str, false_reject: float) -> Triple:
    """Exact ``(V, E, U)`` for one task under allocation ``(n, m)``."""
    need = need_votes(m, rule)
    pc = p * binomial_tail(m, 1.0 - false_reject, need)
    pw = (1.0 - p) * binomial_tail(m, d, need)
    return _combine(pc, pw, n)


def _combine(pc: float, pw: float, n: int) -> Triple:
    s = pc + pw
    if s <= 0.0:
        return 0.0, 0.0, 1.0
    none = (1.0 - s) ** n
    reach = 1.0 - none
    return pc / s * reach, pw / s * reach, none


def simulate_outcome(
    p: float, d: float, n: int, m: int, rule: str, false_reject: float, rng: random.Random
) -> str:
    """One realised run of the pipeline: ``'correct'``, ``'wrong'`` or ``'none'``."""
    need = need_votes(m, rule)
    for _ in range(n):
        is_correct = rng.random() < p
        accept_prob = (1.0 - false_reject) if is_correct else d
        votes = sum(rng.random() < accept_prob for _ in range(m))
        if votes >= need:
            return "correct" if is_correct else "wrong"
    return "none"


def surface(
    points: Sequence[tuple[float, float]],
    allocations: Sequence[Allocation],
    rule: str,
    false_reject: float,
) -> dict[Allocation, Triple]:
    """Mean ``(V, E, U)`` over equally weighted ``(p, d)`` points, for every allocation."""
    by_m: dict[int, list[tuple[float, float]]] = {}
    for m in sorted({m for _, m in allocations}):
        need = need_votes(m, rule)
        accept_correct = binomial_tail(m, 1.0 - false_reject, need)
        by_m[m] = [(p * accept_correct, (1.0 - p) * binomial_tail(m, d, need)) for p, d in points]
    out: dict[Allocation, Triple] = {}
    count = len(points)
    for n, m in allocations:
        v = e = u = 0.0
        for pc, pw in by_m[m]:
            tv, te, tu = _combine(pc, pw, n)
            v += tv
            e += te
            u += tu
        out[(n, m)] = (v / count, e / count, u / count)
    return out


# ---- allocations and baselines -----------------------------------------------------
def enumerate_allocations(budget: float, c_v: float) -> list[Allocation]:
    """Every ``(n, m)`` with ``n >= 1``, ``1 <= m <= M_MAX`` and cost within the budget."""
    out: list[Allocation] = []
    n = 1
    while n * (C_W + c_v) <= budget + 1e-9:
        for m in range(1, M_MAX + 1):
            if n * (C_W + m * c_v) <= budget + 1e-9:
                out.append((n, m))
        n += 1
    return out


def allocation_cost(allocation: Allocation, c_v: float) -> float:
    n, m = allocation
    return n * (C_W + m * c_v)


def baseline_allocations(budget: float, c_v: float) -> dict[str, Allocation]:
    """The three fixed heuristics named in issue 981, as feasible grid points.

    ``all_workers`` spends as much as possible on attempts and keeps one read per attempt
    (zero reads would yield no *verified* work).  ``all_verifiers`` keeps one attempt and
    spends the rest on reads.  ``fifty_fifty`` puts about half the budget on each.
    """
    feasible = set(enumerate_allocations(budget, c_v))
    n_max = max(n for n, _ in feasible)
    all_workers = (n_max, 1)
    m_all = max(m for n, m in feasible if n == 1)
    all_verifiers = (1, m_all)
    n_half = max(1, int(budget / 2 / C_W))
    while True:
        m_half = clamp(int(budget / 2 / (n_half * c_v)), 1, M_MAX)
        if (n_half, int(m_half)) in feasible or n_half == 1:
            break
        n_half -= 1
    fifty = (n_half, int(m_half))
    if fifty not in feasible:
        fifty = (1, max(m for n, m in feasible if n == 1))
    return {"all_workers": all_workers, "fifty_fifty": fifty, "all_verifiers": all_verifiers}


def argbest(values: Mapping[Allocation, float], c_v: float, worst: bool = False) -> Allocation:
    """Best (or worst) allocation by value, ties broken by lower cost, then ``(n, m)``."""
    sign = 1.0 if worst else -1.0
    return min(values, key=lambda a: (sign * values[a], allocation_cost(a, c_v), a))


# ---- pilot observations and the fitted model ---------------------------------------
@dataclass(frozen=True)
class TaskObservation:
    """What one pilot task contributes; the contract a real X3 + X6 matrix must satisfy.

    ``candidates`` attempts were made and ``correct`` of them were correct (hidden-test
    label).  Every candidate was read ``reads_per_candidate`` times by the verifier panel;
    ``wrong_accepts`` counts accept votes on the wrong candidates and ``correct_accepts``
    on the correct ones.
    """

    candidates: int
    correct: int
    reads_per_candidate: int
    wrong_accepts: int
    correct_accepts: int

    @property
    def wrong_reads(self) -> int:
        return (self.candidates - self.correct) * self.reads_per_candidate

    @property
    def correct_reads(self) -> int:
        return self.correct * self.reads_per_candidate


def run_pilot(
    world: World, tasks: Sequence[tuple[float, float]], workers: int, reads: int, rng: random.Random
) -> list[TaskObservation]:
    """Run ``workers`` attempts and ``reads`` reads per candidate on each task."""
    observations: list[TaskObservation] = []
    for p, d in tasks:
        correct = sum(rng.random() < p for _ in range(workers))
        wrong = workers - correct
        wrong_accepts = sum(rng.random() < d for _ in range(wrong * reads))
        correct_accepts = sum(rng.random() < 1.0 - world.false_reject for _ in range(correct * reads))
        observations.append(TaskObservation(workers, correct, reads, wrong_accepts, correct_accepts))
    return observations


@dataclass(frozen=True)
class FittedModel:
    worker_mean: float
    worker_icc: float
    fa_mean: float
    fa_icc: float
    false_reject: float
    cross: float
    tasks: int


def fit_cluster_beta_binomial(sizes: Sequence[int], hits: Sequence[int]) -> tuple[float, float]:
    """Pooled mean and ANOVA intra-class correlation for clustered binary counts.

    The pooled mean weights each cluster by its size, which is the weighting the pipeline
    needs: reads on wrong candidates are weighted by how many wrong candidates a task
    produces.  The ICC is the standard unequal-cluster-size ANOVA estimator, clipped to
    ``[ICC_FLOOR, ICC_CEIL]``.
    """
    clusters = [(s, h) for s, h in zip(sizes, hits) if s >= 2]
    if len(clusters) < 3:
        raise ValueError("need at least 3 clusters of size >= 2 to estimate an intra-class correlation")
    total = sum(s for s, _ in clusters)
    mean = sum(h for _, h in clusters) / total
    count = len(clusters)
    between = sum(s * (h / s - mean) ** 2 for s, h in clusters) / (count - 1)
    within = sum(h * (1.0 - h / s) for s, h in clusters) / (total - count)
    n0 = (total - sum(s * s for s, _ in clusters) / total) / (count - 1)
    denominator = between + (n0 - 1.0) * within
    icc = (between - within) / denominator if denominator > 0 else 0.0
    return clamp(mean, 1e-3, 1 - 1e-3), clamp(icc, ICC_FLOOR, ICC_CEIL)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def _reliability(size: float, icc: float) -> float:
    """Spearman-Brown reliability of an observed rate over ``size`` trials."""
    return size * icc / (1.0 + (size - 1.0) * icc)


def fit_model(observations: Sequence[TaskObservation]) -> FittedModel:
    """Fit the predictor's parameters from a pilot; uses nothing the pilot does not give."""
    if not observations:
        raise ValueError("no observations")
    worker_mean, worker_icc = fit_cluster_beta_binomial(
        [o.candidates for o in observations], [o.correct for o in observations]
    )
    with_wrong = [o for o in observations if o.wrong_reads >= 2]
    fa_mean, fa_icc = fit_cluster_beta_binomial(
        [o.wrong_reads for o in with_wrong], [o.wrong_accepts for o in with_wrong]
    )
    correct_reads = sum(o.correct_reads for o in observations)
    if correct_reads == 0:
        raise ValueError("no correct candidates were read; the false-reject rate is unidentified")
    false_reject = clamp(1.0 - sum(o.correct_accepts for o in observations) / correct_reads, 1e-3, 0.9)
    # cross-dependence: correlation between a task's worker failure rate and its false-accept
    # rate on wrong candidates, corrected for the attenuation both noisy rates carry.
    usable = [o for o in observations if o.wrong_reads >= 1]
    cross = 0.0
    if len(usable) >= 3:
        fail_rate = [1.0 - o.correct / o.candidates for o in usable]
        fa_rate = [o.wrong_accepts / o.wrong_reads for o in usable]
        raw = _pearson(fail_rate, fa_rate)
        mean_candidates = sum(o.candidates for o in usable) / len(usable)
        mean_reads = sum(o.wrong_reads for o in usable) / len(usable)
        reliability = _reliability(mean_candidates, worker_icc) * _reliability(mean_reads, fa_icc)
        cross = clamp(raw / math.sqrt(reliability), -CROSS_CLIP, CROSS_CLIP) if reliability > 0 else 0.0
    return FittedModel(worker_mean, worker_icc, fa_mean, fa_icc, false_reject, cross, len(observations))


def beta_quantile_table(mean: float, icc: float, seed: int = 20261014) -> list[float]:
    """Ascending sample of a Beta, used as its quantile function (deterministic)."""
    a, b = beta_shape(mean, icc)
    rng = random.Random(seed)
    return sorted(rng.betavariate(a, b) for _ in range(QUANTILE_SAMPLE))


def model_points(model: FittedModel, cross: float | None = None) -> list[tuple[float, float]]:
    """Equally weighted ``(p, d)`` points of the fitted joint model (Gaussian copula).

    The failure rank ``u = Phi(z)`` and the false-accept rank ``Phi(rho * z + sqrt(1 -
    rho^2) * e)`` are coupled; ``z`` and ``e`` run over ``GRID_K`` normal midpoints each.
    """
    rho = clamp(model.cross if cross is None else cross, -CROSS_CLIP, CROSS_CLIP)
    p_table = beta_quantile_table(model.worker_mean, model.worker_icc)
    d_table = beta_quantile_table(model.fa_mean, model.fa_icc)
    normal = NormalDist()
    midpoints = [normal.inv_cdf((i + 0.5) / GRID_K) for i in range(GRID_K)]
    root = math.sqrt(1.0 - rho * rho)
    points: list[tuple[float, float]] = []
    top = QUANTILE_SAMPLE - 1
    for z in midpoints:
        fail_rank = normal.cdf(z)
        p = p_table[min(top, int((1.0 - fail_rank) * QUANTILE_SAMPLE))]
        for e in midpoints:
            d = d_table[min(top, int(normal.cdf(rho * z + root * e) * QUANTILE_SAMPLE))]
            points.append((p, d))
    return points


def predicted_surface(
    model: FittedModel, allocations: Sequence[Allocation], rule: str, cross: float | None = None
) -> dict[Allocation, Triple]:
    """A6: predicted ``(V, E, U)`` for every allocation from the fitted model."""
    return surface(model_points(model, cross), allocations, rule, model.false_reject)


def choose_split(
    model: FittedModel, budget: float, c_v: float, rule: str, cross: float | None = None
) -> Allocation:
    """The allocator: the feasible allocation with the highest predicted verified value."""
    allocations = enumerate_allocations(budget, c_v)
    predicted = predicted_surface(model, allocations, rule, cross)
    return argbest({a: v[0] for a, v in predicted.items()}, c_v)


# ---- scenarios and replicates ------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    cost_ratio: float
    budget: float
    cross: float
    verifier_icc: float
    rule: str

    @property
    def scenario_id(self) -> str:
        return f"cv{self.cost_ratio:g}-B{self.budget:g}-x{self.cross:g}-vi{self.verifier_icc:g}-{self.rule}"

    def world(self) -> World:
        return World(
            worker_mean=WORLD_BASE["worker_mean"],
            worker_icc=WORLD_BASE["worker_icc"],
            lambda_w=WORLD_BASE["lambda_w"],
            fa_mean=WORLD_BASE["fa_mean"],
            fa_icc=self.verifier_icc,
            lambda_v=WORLD_BASE["lambda_v"],
            cross=self.cross,
            false_reject=WORLD_BASE["false_reject"],
            rule=self.rule,
        )


def scenario_grid() -> list[Scenario]:
    return [
        Scenario(c, b, x, vi, rule)
        for c in COST_RATIOS
        for b in BUDGETS
        for x in CROSS_TERMS
        for vi in VERIFIER_ICCS
        for rule in RULES
    ]


def choose_for_strategy(
    name: str,
    truth: Mapping[Allocation, Triple],
    model: FittedModel,
    scenario: Scenario,
    permutation_seed: int,
) -> Allocation:
    """Allocation each non-oracle strategy picks.  Only ``oracle`` sees the truth."""
    c_v = scenario.cost_ratio
    allocations = list(truth)
    if name == "oracle":
        return argbest({a: v[0] for a, v in truth.items()}, c_v)
    if name in BASELINES:
        return baseline_allocations(scenario.budget, c_v)[name]
    if name == "predicted_joint":
        return choose_split(model, scenario.budget, c_v, scenario.rule)
    if name == "predicted_independent":
        return choose_split(model, scenario.budget, c_v, scenario.rule, cross=0.0)
    if name == "broken_predictor":
        # Control: the same fitted predictions, read upside down.  A harness that cannot
        # tell this from the real predictor would be measuring nothing.
        predicted = predicted_surface(model, allocations, scenario.rule)
        return argbest({a: v[0] for a, v in predicted.items()}, c_v, worst=True)
    raise ValueError(name)


def draw_split(
    scenario: Scenario, replicate: int, pilot_tasks: int = PILOT_TASKS
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], random.Random]:
    """Pilot tasks and held-out tasks (consecutive fresh draws), plus the stream that follows."""
    world = scenario.world()
    rng = random.Random(derive_seed("x8", scenario.scenario_id, replicate, pilot_tasks))
    pilot = draw_tasks(world, pilot_tasks, rng)
    held_out = draw_tasks(world, HELD_OUT_TASKS, rng)
    return pilot, held_out, rng


def run_replicate(scenario: Scenario, replicate: int, pilot_tasks: int = PILOT_TASKS) -> dict:
    """One pilot-fit-then-held-out trial.  Every random choice derives from the ids."""
    world = scenario.world()
    pilot_draws, held_out, rng = draw_split(scenario, replicate, pilot_tasks)
    observations = run_pilot(world, pilot_draws, PILOT_WORKERS, PILOT_READS, rng)
    model = fit_model(observations)
    allocations = enumerate_allocations(scenario.budget, scenario.cost_ratio)
    truth = surface(held_out, allocations, scenario.rule, world.false_reject)
    predicted = predicted_surface(model, allocations, scenario.rule)
    picks: dict[str, dict] = {}
    for name in STRATEGIES:
        if name == "random_allocation":
            v = sum(t[0] for t in truth.values()) / len(truth)
            e = sum(t[1] for t in truth.values()) / len(truth)
            u = sum(t[2] for t in truth.values()) / len(truth)
            cost = sum(allocation_cost(a, scenario.cost_ratio) for a in truth) / len(truth)
            picks[name] = {"allocation": None, "V": v, "E": e, "U": u, "cost": cost}
            continue
        alloc = choose_for_strategy(name, truth, model, scenario, replicate)
        v, e, u = truth[alloc]
        picks[name] = {
            "allocation": list(alloc),
            "V": v,
            "E": e,
            "U": u,
            "cost": allocation_cost(alloc, scenario.cost_ratio),
        }
    oracle_v = picks["oracle"]["V"]
    for pick in picks.values():
        pick["regret"] = oracle_v - pick["V"]
    errors = [abs(predicted[a][0] - truth[a][0]) for a in truth]
    ranked = sorted(truth, key=lambda a: (-truth[a][0], a))
    chosen = tuple(picks["predicted_joint"]["allocation"])
    return {
        "scenario": scenario.scenario_id,
        "replicate": replicate,
        "strategies": picks,
        "surface_mae": sum(errors) / len(errors),
        "surface_bias": sum(predicted[a][0] - truth[a][0] for a in truth) / len(truth),
        "allocations": len(truth),
        "rank_of_predicted_pick": ranked.index(chosen) + 1,
        "fitted": asdict(model),
    }


# ---- aggregation and verdicts ------------------------------------------------------
def mean_and_se(values: Sequence[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def paired_difference(replicates: Sequence[Mapping], left: str, right: str) -> dict:
    diffs = [r["strategies"][left]["V"] - r["strategies"][right]["V"] for r in replicates]
    mean, se = mean_and_se(diffs)
    return {"mean": mean, "se": se, "z": (mean / se) if se > 0 else (math.copysign(math.inf, mean) if mean else 0.0)}


def scenario_verdict(replicates: Sequence[Mapping]) -> dict:
    """Apply the preregistered rule to one scenario's replicates."""
    versus = {b: paired_difference(replicates, "predicted_joint", b) for b in BASELINES}
    wins = all(d["z"] > Z_DECISIVE for d in versus.values())
    loses = any(d["z"] < -Z_DECISIVE for d in versus.values())
    label = "predicted_wins" if wins else "baseline_wins" if loses else "tie"
    return {"verdict": label, "versus_baseline": versus}


def summarise_scenario(scenario: Scenario, replicates: Sequence[Mapping]) -> dict:
    strategies: dict[str, dict] = {}
    for name in STRATEGIES:
        row: dict[str, float] = {}
        for key in ("V", "E", "U", "cost", "regret"):
            row[key], row[key + "_se"] = mean_and_se([r["strategies"][name][key] for r in replicates])
        strategies[name] = row
    verdict = scenario_verdict(replicates)
    independent = paired_difference(replicates, "predicted_joint", "predicted_independent")
    return {
        "scenario": scenario.scenario_id,
        "parameters": asdict(scenario),
        "strategies": strategies,
        **verdict,
        "joint_minus_independent": independent,
        "surface_mae": mean_and_se([r["surface_mae"] for r in replicates])[0],
        "surface_bias": mean_and_se([r["surface_bias"] for r in replicates])[0],
        "allocations": replicates[0]["allocations"],
        "mean_rank_of_predicted_pick": mean_and_se([r["rank_of_predicted_pick"] for r in replicates])[0],
        "baseline_allocations": {k: list(v) for k, v in baseline_allocations(scenario.budget, scenario.cost_ratio).items()},
        "replicate_regrets": {
            name: [round(r["strategies"][name]["regret"], 9) for r in replicates] for name in STRATEGIES
        },
        "replicate_picks": [r["strategies"]["predicted_joint"]["allocation"] for r in replicates],
    }


def run_study(
    scenarios: Iterable[Scenario] | None = None,
    replicates: int = REPLICATES,
    progress: Callable[[str], None] | None = None,
    pilot_tasks: int = PILOT_TASKS,
) -> dict:
    scenarios = list(scenarios) if scenarios is not None else scenario_grid()
    rows = []
    for scenario in scenarios:
        runs = [run_replicate(scenario, r, pilot_tasks) for r in range(replicates)]
        rows.append(summarise_scenario(scenario, runs))
        if progress:
            progress(scenario.scenario_id)
    verdicts = [row["verdict"] for row in rows]
    totals = {label: verdicts.count(label) for label in ("predicted_wins", "tie", "baseline_wins")}
    best_baseline_regret = [min(row["strategies"][b]["regret"] for b in BASELINES) for row in rows]
    return {
        "generator": GENERATOR,
        "evidence_class": "synthetic",
        "scope": (
            "Synthetic ground truth with an invented generating process, invented costs and a "
            "fixed acceptance rule.  Evidence about the predictor's behaviour on that model, not "
            "about real coding agents or verifiers; the real-data test of H4 is blocked on X6."
        ),
        "design": {
            "pilot_tasks": pilot_tasks,
            "pilot_workers": PILOT_WORKERS,
            "pilot_reads": PILOT_READS,
            "held_out_tasks": HELD_OUT_TASKS,
            "replicates": replicates,
            "grid_k": GRID_K,
            "m_max": M_MAX,
            "z_decisive": Z_DECISIVE,
            "world_base": WORLD_BASE,
        },
        "totals": totals,
        "scenarios_run": len(rows),
        "mean_regret": {
            name: sum(row["strategies"][name]["regret"] for row in rows) / len(rows) for name in STRATEGIES
        },
        "mean_best_baseline_regret": sum(best_baseline_regret) / len(rows),
        "mean_surface_mae": sum(row["surface_mae"] for row in rows) / len(rows),
        "scenarios": rows,
    }


def canonical_digest(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=DEFAULT_OUT, help="where to write the JSON result")
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    progress = None if args.quiet else (lambda s: print(f"done {s}", file=sys.stderr))
    result = run_study(replicates=args.replicates, progress=progress)
    small = run_study(replicates=args.replicates, progress=progress, pilot_tasks=SMALL_PILOT_TASKS)
    result["small_pilot"] = {
        key: small[key]
        for key in ("design", "totals", "mean_regret", "mean_best_baseline_regret", "mean_surface_mae")
    }
    result["small_pilot"]["scenarios"] = [
        {
            "scenario": row["scenario"],
            "verdict": row["verdict"],
            "V": {name: row["strategies"][name]["V"] for name in STRATEGIES},
            "surface_mae": row["surface_mae"],
            "surface_bias": row["surface_bias"],
        }
        for row in small["scenarios"]
    ]
    result["digest"] = canonical_digest({k: v for k, v in result.items() if k != "digest"})
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(path), "totals": result["totals"], "digest": result["digest"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
