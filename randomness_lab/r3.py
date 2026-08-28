from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean, pstdev
from typing import Iterable, Sequence


@dataclass(frozen=True)
class OrchestrationGenome:
    """Compact synthetic orchestration policy searched by R3."""

    worker_count: int
    diversity_mix: float
    decomposition_depth: int
    replication_factor: int
    verifier_depth: int
    exploration_temperature: float
    timeout_budget: int
    escalation_threshold: float

    def __post_init__(self) -> None:
        if not 1 <= self.worker_count <= 8:
            raise ValueError("worker_count must be in [1, 8]")
        if not 0.0 <= self.diversity_mix <= 1.0:
            raise ValueError("diversity_mix must be in [0, 1]")
        if not 1 <= self.decomposition_depth <= 4:
            raise ValueError("decomposition_depth must be in [1, 4]")
        if not 1 <= self.replication_factor <= 4:
            raise ValueError("replication_factor must be in [1, 4]")
        if not 1 <= self.verifier_depth <= 4:
            raise ValueError("verifier_depth must be in [1, 4]")
        if not 0.0 <= self.exploration_temperature <= 1.5:
            raise ValueError("exploration_temperature must be in [0, 1.5]")
        if not 1 <= self.timeout_budget <= 10:
            raise ValueError("timeout_budget must be in [1, 10]")
        if not 0.0 <= self.escalation_threshold <= 1.0:
            raise ValueError("escalation_threshold must be in [0, 1]")

    @property
    def id(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return "g-" + hashlib.sha256(encoded).hexdigest()[:12]


@dataclass(frozen=True)
class SyntheticTaskFamily:
    name: str
    difficulty: float
    ideal_decomposition_depth: int
    diversity_value: float
    verification_need: float
    correlation_pressure: float
    security_pressure: float
    latency_pressure: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("task family name must not be empty")
        for field_name, value in (
            ("difficulty", self.difficulty),
            ("diversity_value", self.diversity_value),
            ("verification_need", self.verification_need),
            ("correlation_pressure", self.correlation_pressure),
            ("security_pressure", self.security_pressure),
            ("latency_pressure", self.latency_pressure),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be in [0, 1]")
        if not 1 <= self.ideal_decomposition_depth <= 4:
            raise ValueError("ideal_decomposition_depth must be in [1, 4]")


TRAIN_FAMILIES = (
    SyntheticTaskFamily("train-routine-fix", 0.35, 1, 0.15, 0.25, 0.25, 0.15, 0.25),
    SyntheticTaskFamily("train-cross-file-refactor", 0.60, 3, 0.45, 0.45, 0.45, 0.25, 0.40),
    SyntheticTaskFamily("train-api-change", 0.55, 2, 0.30, 0.50, 0.35, 0.30, 0.35),
    SyntheticTaskFamily("train-test-generation", 0.45, 2, 0.35, 0.35, 0.30, 0.15, 0.30),
    SyntheticTaskFamily("train-security-sensitive", 0.70, 3, 0.55, 0.90, 0.60, 0.95, 0.50),
)

HELDOUT_FAMILIES = (
    SyntheticTaskFamily("heldout-ambiguous-cross-module", 0.78, 4, 0.75, 0.65, 0.75, 0.45, 0.50),
    SyntheticTaskFamily("heldout-performance-constrained", 0.67, 2, 0.25, 0.45, 0.40, 0.25, 0.95),
    SyntheticTaskFamily("heldout-adversarial-regression", 0.82, 3, 0.65, 0.95, 0.85, 0.90, 0.65),
)

BASELINE_GENOME = OrchestrationGenome(
    worker_count=3,
    diversity_mix=0.25,
    decomposition_depth=2,
    replication_factor=1,
    verifier_depth=2,
    exploration_temperature=0.20,
    timeout_budget=5,
    escalation_threshold=0.50,
)


@dataclass(frozen=True)
class R3Config:
    population_size: int = 24
    generations: int = 12
    trials_per_family: int = 80
    seed: int = 42
    mutation_rate: float = 0.35
    crossover_rate: float = 0.70
    exploration_floor: float = 0.10
    archive_size: int = 40
    archive_novelty_threshold: float = 0.18
    overfit_gap_threshold: float = 0.10

    def __post_init__(self) -> None:
        if self.population_size < 4:
            raise ValueError("population_size must be >= 4")
        if self.generations < 1:
            raise ValueError("generations must be >= 1")
        if self.trials_per_family < 2:
            raise ValueError("trials_per_family must be >= 2")
        for name, value in (
            ("mutation_rate", self.mutation_rate),
            ("crossover_rate", self.crossover_rate),
            ("exploration_floor", self.exploration_floor),
            ("archive_novelty_threshold", self.archive_novelty_threshold),
            ("overfit_gap_threshold", self.overfit_gap_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.archive_size < 1:
            raise ValueError("archive_size must be >= 1")


def _clip(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _logistic(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def validate_family_split(
    train_families: Sequence[SyntheticTaskFamily],
    heldout_families: Sequence[SyntheticTaskFamily],
) -> None:
    train_names = {family.name for family in train_families}
    heldout_names = {family.name for family in heldout_families}
    overlap = sorted(train_names & heldout_names)
    if overlap:
        raise ValueError(f"train/heldout family leakage: {', '.join(overlap)}")


def family_split_digest(
    train_families: Sequence[SyntheticTaskFamily],
    heldout_families: Sequence[SyntheticTaskFamily],
) -> str:
    validate_family_split(train_families, heldout_families)
    payload = {
        "train": [asdict(family) for family in train_families],
        "heldout": [asdict(family) for family in heldout_families],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _seed_for(*parts: object) -> int:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def _family_distribution(
    families: Sequence[SyntheticTaskFamily], seed: int, generation: int | None
) -> dict[str, float]:
    """Return shared family weights for one evaluation context.

    During evolution the weights change by generation. Final train-reference and
    heldout evaluations pass ``generation=None`` and therefore use uniform
    weights. Every genome in a generation sees the same distribution.
    """

    if generation is None:
        return {family.name: 1.0 / len(families) for family in families}

    rng = random.Random(_seed_for(seed, "family-distribution", generation))
    raw = [0.35 + rng.random() for _ in families]
    total = sum(raw)
    return {family.name: weight / total for family, weight in zip(families, raw)}


def _genome_complexity(genome: OrchestrationGenome) -> float:
    return (
        genome.worker_count / 8.0
        + genome.decomposition_depth / 4.0
        + genome.replication_factor / 4.0
        + genome.verifier_depth / 4.0
        + genome.diversity_mix
        + genome.exploration_temperature / 1.5
    ) / 6.0


def _family_probabilities(
    genome: OrchestrationGenome, family: SyntheticTaskFamily
) -> dict[str, float]:
    decomposition_match = 1.0 - abs(
        genome.decomposition_depth - family.ideal_decomposition_depth
    ) / 3.0
    decomposition_match = _clip(decomposition_match, 0.0, 1.0)

    error_correlation = _clip(
        0.82
        - 0.56 * genome.diversity_mix
        + 0.18 * family.correlation_pressure
        - 0.05 * genome.exploration_temperature,
        0.04,
        0.97,
    )

    coordination_penalty = 0.055 * max(0, genome.worker_count - 1) + 0.035 * max(
        0, genome.decomposition_depth - 1
    )
    timeout_fit = 1.0 - abs(genome.timeout_budget - (3.0 + 6.0 * family.difficulty)) / 9.0
    timeout_fit = _clip(timeout_fit, 0.0, 1.0)

    latent = (
        -1.05
        - 1.25 * family.difficulty
        + 0.28 * math.log2(genome.worker_count + 1.0)
        + 0.70 * decomposition_match
        + 0.68 * family.diversity_value * genome.diversity_mix
        + 0.22 * genome.exploration_temperature * family.diversity_value
        + 0.25 * timeout_fit
        - coordination_penalty
    )
    base_attempt_success = _clip(_logistic(latent), 0.02, 0.97)

    effective_replication = 1.0 + (genome.replication_factor - 1.0) * (
        1.0 - error_correlation
    )
    candidate_success = 1.0 - (1.0 - base_attempt_success) ** effective_replication

    verifier_strength = _clip(
        0.52
        + 0.105 * genome.verifier_depth
        + 0.12 * genome.diversity_mix
        - 0.10 * family.verification_need,
        0.50,
        0.995,
    )
    false_reject = _clip(0.075 - 0.010 * genome.verifier_depth, 0.015, 0.08)
    false_accept = _clip(
        (1.0 - verifier_strength)
        * (0.35 + 0.65 * family.verification_need),
        0.002,
        0.45,
    )

    escalation_probability = _clip(
        genome.escalation_threshold
        * (0.25 + 0.55 * family.difficulty + 0.20 * family.verification_need),
        0.0,
        0.95,
    )

    return {
        "candidate_success": candidate_success,
        "false_reject": false_reject,
        "false_accept": false_accept,
        "error_correlation": error_correlation,
        "escalation_probability": escalation_probability,
    }


def _resource_metrics(
    genome: OrchestrationGenome, family: SyntheticTaskFamily
) -> dict[str, float]:
    compute = (
        genome.worker_count
        * genome.replication_factor
        * (1.0 + 0.12 * genome.decomposition_depth)
        * (0.75 + family.difficulty)
    )
    parallelism = 1.0 + 0.50 * math.log2(genome.worker_count + 1.0)
    latency = (
        (3.0 + 8.0 * family.difficulty) / parallelism
        + 0.45 * genome.decomposition_depth
        + 0.55 * genome.verifier_depth
        + 0.15 * genome.replication_factor
        + 0.18 * genome.exploration_temperature
    ) * (1.0 + 0.35 * family.latency_pressure)
    attention = (
        0.04 * genome.verifier_depth
        + 0.06 * genome.escalation_threshold
        + 0.02 * max(0, genome.worker_count - 1)
    ) * (1.0 + family.verification_need)
    return {
        "compute": compute,
        "latency": latency,
        "human_attention": attention,
    }


def evaluate_genome(
    genome: OrchestrationGenome,
    families: Sequence[SyntheticTaskFamily],
    *,
    trials_per_family: int,
    seed: int,
    context: str,
    generation: int | None = None,
) -> dict[str, object]:
    if not families:
        raise ValueError("families must not be empty")
    if trials_per_family < 1:
        raise ValueError("trials_per_family must be >= 1")

    weights = _family_distribution(families, seed, generation)
    family_results = []

    for family in families:
        probabilities = _family_probabilities(genome, family)
        resources = _resource_metrics(genome, family)
        rng = random.Random(
            _seed_for(seed, context, generation, genome.id, family.name)
        )
        verified_successes = 0
        false_acceptances = 0
        security_failures = 0
        regressions = 0
        escalations = 0

        for _ in range(trials_per_family):
            candidate_good = rng.random() < probabilities["candidate_success"]
            if candidate_good:
                accepted = rng.random() >= probabilities["false_reject"]
            else:
                accepted = rng.random() < probabilities["false_accept"]

            verified_successes += int(candidate_good and accepted)
            false_accept = bool(not candidate_good and accepted)
            false_acceptances += int(false_accept)
            if false_accept:
                security_failures += int(
                    rng.random()
                    < family.security_pressure * (0.35 + 0.45 * family.difficulty)
                )
                regressions += int(
                    rng.random() < 0.25 + 0.55 * family.difficulty
                )
            escalations += int(
                rng.random() < probabilities["escalation_probability"]
            )

        family_results.append(
            {
                "family": family.name,
                "weight": weights[family.name],
                "verified_success_rate": verified_successes / trials_per_family,
                "false_acceptance_rate": false_acceptances / trials_per_family,
                "security_failure_rate": security_failures / trials_per_family,
                "regression_rate": regressions / trials_per_family,
                "escalation_rate": escalations / trials_per_family,
                "error_correlation": probabilities["error_correlation"],
                "compute_per_task": resources["compute"],
                "latency_per_task": resources["latency"],
                "human_attention_per_task": resources["human_attention"],
            }
        )

    def weighted(metric: str) -> float:
        return sum(
            float(result[metric]) * float(result["weight"])
            for result in family_results
        )

    family_successes = [float(result["verified_success_rate"]) for result in family_results]
    complexity = _genome_complexity(genome)
    return {
        "genome_id": genome.id,
        "genome": asdict(genome),
        "context": context,
        "generation": generation,
        "family_distribution": weights,
        "metrics": {
            "verified_success_rate": weighted("verified_success_rate"),
            "worst_family_success_rate": min(family_successes),
            "family_success_std": pstdev(family_successes),
            "false_acceptance_rate": weighted("false_acceptance_rate"),
            "security_failure_rate": weighted("security_failure_rate"),
            "regression_rate": weighted("regression_rate"),
            "error_correlation": weighted("error_correlation"),
            "compute_per_task": weighted("compute_per_task"),
            "latency_per_task": weighted("latency_per_task"),
            "human_attention_per_task": weighted("human_attention_per_task"),
            "escalation_rate": weighted("escalation_rate"),
            "complexity": complexity,
        },
        "families": family_results,
    }


# True means maximize. False means minimize.
OBJECTIVES = {
    "verified_success_rate": True,
    "worst_family_success_rate": True,
    "security_failure_rate": False,
    "regression_rate": False,
    "error_correlation": False,
    "compute_per_task": False,
    "latency_per_task": False,
    "human_attention_per_task": False,
    "complexity": False,
}


def dominates(left: dict[str, object], right: dict[str, object]) -> bool:
    left_metrics = left["metrics"]
    right_metrics = right["metrics"]
    at_least_as_good = True
    strictly_better = False
    for metric, maximize in OBJECTIVES.items():
        left_value = float(left_metrics[metric])
        right_value = float(right_metrics[metric])
        if maximize:
            if left_value < right_value:
                at_least_as_good = False
                break
            if left_value > right_value:
                strictly_better = True
        else:
            if left_value > right_value:
                at_least_as_good = False
                break
            if left_value < right_value:
                strictly_better = True
    return at_least_as_good and strictly_better


def nondominated_front(evaluations: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return [
        candidate
        for candidate in evaluations
        if not any(
            other is not candidate and dominates(other, candidate)
            for other in evaluations
        )
    ]


def nondominated_layers(
    evaluations: Sequence[dict[str, object]],
) -> list[list[dict[str, object]]]:
    remaining = list(evaluations)
    layers = []
    while remaining:
        front = nondominated_front(remaining)
        layers.append(front)
        front_ids = {id(item) for item in front}
        remaining = [item for item in remaining if id(item) not in front_ids]
    return layers


def genome_distance(left: OrchestrationGenome, right: OrchestrationGenome) -> float:
    components = (
        abs(left.worker_count - right.worker_count) / 7.0,
        abs(left.diversity_mix - right.diversity_mix),
        abs(left.decomposition_depth - right.decomposition_depth) / 3.0,
        abs(left.replication_factor - right.replication_factor) / 3.0,
        abs(left.verifier_depth - right.verifier_depth) / 3.0,
        abs(left.exploration_temperature - right.exploration_temperature) / 1.5,
        abs(left.timeout_budget - right.timeout_budget) / 9.0,
        abs(left.escalation_threshold - right.escalation_threshold),
    )
    return sum(components) / len(components)


def novelty_score(
    genome: OrchestrationGenome, references: Sequence[OrchestrationGenome]
) -> float:
    others = [reference for reference in references if reference.id != genome.id]
    if not others:
        return 1.0
    distances = sorted(genome_distance(genome, reference) for reference in others)
    nearest = distances[: min(5, len(distances))]
    return mean(nearest)


def random_genome(rng: random.Random) -> OrchestrationGenome:
    return OrchestrationGenome(
        worker_count=rng.randint(1, 8),
        diversity_mix=round(rng.random(), 4),
        decomposition_depth=rng.randint(1, 4),
        replication_factor=rng.randint(1, 4),
        verifier_depth=rng.randint(1, 4),
        exploration_temperature=round(rng.random() * 1.5, 4),
        timeout_budget=rng.randint(1, 10),
        escalation_threshold=round(rng.random(), 4),
    )


def mutate_genome(genome: OrchestrationGenome, rng: random.Random) -> OrchestrationGenome:
    field = rng.choice(
        (
            "worker_count",
            "diversity_mix",
            "decomposition_depth",
            "replication_factor",
            "verifier_depth",
            "exploration_temperature",
            "timeout_budget",
            "escalation_threshold",
        )
    )
    if field == "worker_count":
        return replace(genome, worker_count=int(_clip(genome.worker_count + rng.choice((-1, 1)), 1, 8)))
    if field == "diversity_mix":
        return replace(genome, diversity_mix=round(_clip(genome.diversity_mix + rng.gauss(0.0, 0.15), 0.0, 1.0), 4))
    if field == "decomposition_depth":
        return replace(genome, decomposition_depth=int(_clip(genome.decomposition_depth + rng.choice((-1, 1)), 1, 4)))
    if field == "replication_factor":
        return replace(genome, replication_factor=int(_clip(genome.replication_factor + rng.choice((-1, 1)), 1, 4)))
    if field == "verifier_depth":
        return replace(genome, verifier_depth=int(_clip(genome.verifier_depth + rng.choice((-1, 1)), 1, 4)))
    if field == "exploration_temperature":
        return replace(genome, exploration_temperature=round(_clip(genome.exploration_temperature + rng.gauss(0.0, 0.20), 0.0, 1.5), 4))
    if field == "timeout_budget":
        return replace(genome, timeout_budget=int(_clip(genome.timeout_budget + rng.choice((-1, 1)), 1, 10)))
    return replace(genome, escalation_threshold=round(_clip(genome.escalation_threshold + rng.gauss(0.0, 0.15), 0.0, 1.0), 4))


def crossover_genomes(
    left: OrchestrationGenome, right: OrchestrationGenome, rng: random.Random
) -> OrchestrationGenome:
    left_data = asdict(left)
    right_data = asdict(right)
    child = {
        key: left_data[key] if rng.random() < 0.5 else right_data[key]
        for key in left_data
    }
    return OrchestrationGenome(**child)


def _select_survivors(
    evaluations: Sequence[dict[str, object]], count: int
) -> list[OrchestrationGenome]:
    layers = nondominated_layers(evaluations)
    all_genomes = [OrchestrationGenome(**evaluation["genome"]) for evaluation in evaluations]
    survivors: list[OrchestrationGenome] = []
    for layer in layers:
        if len(survivors) + len(layer) <= count:
            survivors.extend(OrchestrationGenome(**evaluation["genome"]) for evaluation in layer)
            continue
        needed = count - len(survivors)
        ranked = sorted(
            layer,
            key=lambda evaluation: (
                novelty_score(OrchestrationGenome(**evaluation["genome"]), all_genomes),
                float(evaluation["metrics"]["worst_family_success_rate"]),
                float(evaluation["metrics"]["verified_success_rate"]),
            ),
            reverse=True,
        )
        survivors.extend(
            OrchestrationGenome(**evaluation["genome"])
            for evaluation in ranked[:needed]
        )
        break
    return survivors


def _update_diversity_archive(
    archive: Sequence[OrchestrationGenome],
    candidates: Sequence[OrchestrationGenome],
    *,
    threshold: float,
    max_size: int,
) -> list[OrchestrationGenome]:
    output = list(archive)
    existing_ids = {genome.id for genome in output}
    for candidate in candidates:
        if candidate.id in existing_ids:
            continue
        score = novelty_score(candidate, output) if output else 1.0
        if score >= threshold or not output:
            output.append(candidate)
            existing_ids.add(candidate.id)
    if len(output) <= max_size:
        return output
    ranked = sorted(
        output,
        key=lambda genome: novelty_score(genome, output),
        reverse=True,
    )
    return ranked[:max_size]


def _unique_population(
    genomes: Iterable[OrchestrationGenome],
) -> list[OrchestrationGenome]:
    by_id: dict[str, OrchestrationGenome] = {}
    for genome in genomes:
        by_id.setdefault(genome.id, genome)
    return list(by_id.values())


def _breed_population(
    survivors: Sequence[OrchestrationGenome],
    archive: Sequence[OrchestrationGenome],
    config: R3Config,
    rng: random.Random,
) -> list[OrchestrationGenome]:
    target = config.population_size
    immigrant_count = max(1, math.ceil(target * config.exploration_floor))
    next_population = list(survivors)
    parent_pool = _unique_population(list(survivors) + list(archive)) or [BASELINE_GENOME]

    attempts = 0
    while len(_unique_population(next_population)) < target - immigrant_count:
        attempts += 1
        if attempts > target * 100:
            break
        left = rng.choice(parent_pool)
        child = left
        if len(parent_pool) > 1 and rng.random() < config.crossover_rate:
            right = rng.choice(parent_pool)
            child = crossover_genomes(left, right, rng)
        if rng.random() < config.mutation_rate:
            child = mutate_genome(child, rng)
        next_population.append(child)
        next_population = _unique_population(next_population)

    while len(_unique_population(next_population)) < target:
        next_population.append(random_genome(rng))
        next_population = _unique_population(next_population)

    return next_population[:target]


def _choose_preheldout_champion(
    train_evaluations: Sequence[dict[str, object]],
) -> dict[str, object]:
    front = nondominated_front(train_evaluations)
    return max(
        front,
        key=lambda evaluation: (
            float(evaluation["metrics"]["worst_family_success_rate"]),
            float(evaluation["metrics"]["verified_success_rate"]),
            -float(evaluation["metrics"]["security_failure_rate"]),
            -float(evaluation["metrics"]["compute_per_task"]),
            -float(evaluation["metrics"]["complexity"]),
            evaluation["genome_id"],
        ),
    )


def _promotion_evidence(
    champion_train: dict[str, object],
    champion_heldout: dict[str, object],
    baseline_heldout: dict[str, object],
    config: R3Config,
) -> dict[str, object]:
    train_success = float(champion_train["metrics"]["verified_success_rate"])
    heldout_success = float(champion_heldout["metrics"]["verified_success_rate"])
    gap = train_success - heldout_success
    heldout_delta = heldout_success - float(
        baseline_heldout["metrics"]["verified_success_rate"]
    )
    security_delta = float(champion_heldout["metrics"]["security_failure_rate"]) - float(
        baseline_heldout["metrics"]["security_failure_rate"]
    )
    compute_ratio = float(champion_heldout["metrics"]["compute_per_task"]) / float(
        baseline_heldout["metrics"]["compute_per_task"]
    )
    overfit = gap > config.overfit_gap_threshold
    evidence_supports_consideration = (
        not overfit
        and heldout_delta >= 0.0
        and security_delta <= 0.0
    )
    return {
        "autonomous_promotion": False,
        "status": "human_review_required",
        "champion_selected_before_heldout": True,
        "heldout_used_for_evolutionary_selection": False,
        "train_to_heldout_success_gap": gap,
        "overfit_gap_threshold": config.overfit_gap_threshold,
        "overfit_flag": overfit,
        "heldout_success_delta_vs_fixed_baseline": heldout_delta,
        "heldout_security_failure_delta_vs_fixed_baseline": security_delta,
        "heldout_compute_ratio_vs_fixed_baseline": compute_ratio,
        "evidence_supports_consideration": evidence_supports_consideration,
        "decision": (
            "consider_for_separate human-reviewed experiment"
            if evidence_supports_consideration
            else "do not promote from this evidence"
        ),
        "guardrail": (
            "R3 never modifies production policy. A positive synthetic heldout result only "
            "supports a separate human-reviewed experiment on independent real tasks."
        ),
    }


def run_r3_experiment(
    config: R3Config,
    *,
    train_families: Sequence[SyntheticTaskFamily] = TRAIN_FAMILIES,
    heldout_families: Sequence[SyntheticTaskFamily] = HELDOUT_FAMILIES,
) -> dict[str, object]:
    validate_family_split(train_families, heldout_families)
    split_digest = family_split_digest(train_families, heldout_families)
    rng = random.Random(config.seed)

    population = [BASELINE_GENOME]
    while len(population) < config.population_size:
        candidate = random_genome(rng)
        if candidate.id not in {genome.id for genome in population}:
            population.append(candidate)

    archive: list[OrchestrationGenome] = []
    history = []

    for generation in range(config.generations):
        evaluations = [
            evaluate_genome(
                genome,
                train_families,
                trials_per_family=config.trials_per_family,
                seed=config.seed,
                context="evolution-train",
                generation=generation,
            )
            for genome in population
        ]
        front = nondominated_front(evaluations)
        front_genomes = [OrchestrationGenome(**evaluation["genome"]) for evaluation in front]
        archive = _update_diversity_archive(
            archive,
            front_genomes,
            threshold=config.archive_novelty_threshold,
            max_size=config.archive_size,
        )
        survivor_count = max(2, config.population_size // 2)
        survivors = _select_survivors(evaluations, survivor_count)

        history.append(
            {
                "generation": generation,
                "family_distribution": evaluations[0]["family_distribution"],
                "population_size": len(population),
                "pareto_front_ids": sorted(item["genome_id"] for item in front),
                "survivor_ids": sorted(genome.id for genome in survivors),
                "archive_ids": sorted(genome.id for genome in archive),
                "evaluations": evaluations,
                "heldout_family_names": [],
            }
        )
        population = _breed_population(survivors, archive, config, rng)

    final_candidates = _unique_population(population + archive + [BASELINE_GENOME])
    final_train = [
        evaluate_genome(
            genome,
            train_families,
            trials_per_family=config.trials_per_family,
            seed=config.seed,
            context="final-train-reference",
            generation=None,
        )
        for genome in final_candidates
    ]
    final_train_front = nondominated_front(final_train)
    champion_train = _choose_preheldout_champion(final_train)
    champion = OrchestrationGenome(**champion_train["genome"])

    # The heldout split is first touched only after evolution and champion
    # selection have ended. Its results never feed mutation/selection.
    heldout_evaluations = [
        evaluate_genome(
            OrchestrationGenome(**evaluation["genome"]),
            heldout_families,
            trials_per_family=config.trials_per_family,
            seed=config.seed,
            context="heldout-final-only",
            generation=None,
        )
        for evaluation in final_train_front
    ]
    heldout_by_id = {evaluation["genome_id"]: evaluation for evaluation in heldout_evaluations}
    if champion.id not in heldout_by_id:
        champion_heldout = evaluate_genome(
            champion,
            heldout_families,
            trials_per_family=config.trials_per_family,
            seed=config.seed,
            context="heldout-final-only",
            generation=None,
        )
        heldout_evaluations.append(champion_heldout)
    else:
        champion_heldout = heldout_by_id[champion.id]

    baseline_train = evaluate_genome(
        BASELINE_GENOME,
        train_families,
        trials_per_family=config.trials_per_family,
        seed=config.seed,
        context="fixed-baseline-train",
        generation=None,
    )
    baseline_heldout = evaluate_genome(
        BASELINE_GENOME,
        heldout_families,
        trials_per_family=config.trials_per_family,
        seed=config.seed,
        context="fixed-baseline-heldout",
        generation=None,
    )

    heldout_analysis = []
    train_by_id = {evaluation["genome_id"]: evaluation for evaluation in final_train}
    for heldout in heldout_evaluations:
        train = train_by_id[heldout["genome_id"]]
        gap = float(train["metrics"]["verified_success_rate"]) - float(
            heldout["metrics"]["verified_success_rate"]
        )
        heldout_analysis.append(
            {
                "genome_id": heldout["genome_id"],
                "train_verified_success_rate": train["metrics"]["verified_success_rate"],
                "heldout_verified_success_rate": heldout["metrics"]["verified_success_rate"],
                "generalization_gap": gap,
                "overfit_flag": gap > config.overfit_gap_threshold,
                "heldout_success_delta_vs_baseline": float(
                    heldout["metrics"]["verified_success_rate"]
                )
                - float(baseline_heldout["metrics"]["verified_success_rate"]),
                "heldout_security_delta_vs_baseline": float(
                    heldout["metrics"]["security_failure_rate"]
                )
                - float(baseline_heldout["metrics"]["security_failure_rate"]),
            }
        )

    return {
        "schema_version": 1,
        "experiment": "R3-evolutionary-orchestration",
        "config": asdict(config),
        "split": {
            "digest": split_digest,
            "train_families": [asdict(family) for family in train_families],
            "heldout_families": [asdict(family) for family in heldout_families],
            "heldout_used_for_evolutionary_selection": False,
            "heldout_burned_after_final_evaluation": True,
        },
        "objective_directions": OBJECTIVES,
        "fixed_baseline": {
            "genome": asdict(BASELINE_GENOME),
            "train": baseline_train,
            "heldout": baseline_heldout,
        },
        "evolution_history": history,
        "diversity_archive": [asdict(genome) for genome in archive],
        "final_train_reference": final_train,
        "final_train_pareto_front_ids": sorted(
            evaluation["genome_id"] for evaluation in final_train_front
        ),
        "preheldout_champion_id": champion.id,
        "heldout_evaluations": heldout_evaluations,
        "heldout_analysis": heldout_analysis,
        "promotion_evidence": _promotion_evidence(
            champion_train, champion_heldout, baseline_heldout, config
        ),
        "research_guardrail": (
            "All metrics are synthetic mechanism-test outputs. Heldout families are not used "
            "during evolutionary selection, and no evolved genome can autonomously become a "
            "production orchestration policy."
        ),
    }


def render_r3_report(result: dict[str, object]) -> str:
    promotion = result["promotion_evidence"]
    baseline = result["fixed_baseline"]["heldout"]["metrics"]
    champion_id = result["preheldout_champion_id"]
    champion_heldout = next(
        evaluation
        for evaluation in result["heldout_evaluations"]
        if evaluation["genome_id"] == champion_id
    )
    champion_metrics = champion_heldout["metrics"]
    overfit_count = sum(int(item["overfit_flag"]) for item in result["heldout_analysis"])

    lines = [
        "# R3 Evolutionary Orchestration Evidence Report",
        "",
        "**Status:** Synthetic mechanism experiment. Human review required; no autonomous promotion.",
        "",
        f"Split digest: `{result['split']['digest']}`",
        f"Pre-heldout champion: `{champion_id}`",
        "",
        "## Held-out comparison",
        "",
        "| Metric | Fixed baseline | Pre-heldout champion |",
        "| --- | ---: | ---: |",
        f"| Verified success | {baseline['verified_success_rate']:.4f} | {champion_metrics['verified_success_rate']:.4f} |",
        f"| Security failure | {baseline['security_failure_rate']:.4f} | {champion_metrics['security_failure_rate']:.4f} |",
        f"| Regression | {baseline['regression_rate']:.4f} | {champion_metrics['regression_rate']:.4f} |",
        f"| Compute/task | {baseline['compute_per_task']:.4f} | {champion_metrics['compute_per_task']:.4f} |",
        f"| Latency/task | {baseline['latency_per_task']:.4f} | {champion_metrics['latency_per_task']:.4f} |",
        f"| Human attention/task | {baseline['human_attention_per_task']:.4f} | {champion_metrics['human_attention_per_task']:.4f} |",
        "",
        "## Generalization / safeguards",
        "",
        f"- Final train-Pareto genomes evaluated on heldout: {len(result['heldout_analysis'])}.",
        f"- Overfit flags: {overfit_count}.",
        f"- Champion train→heldout success gap: {promotion['train_to_heldout_success_gap']:.4f}.",
        f"- Heldout success delta vs baseline: {promotion['heldout_success_delta_vs_fixed_baseline']:.4f}.",
        f"- Heldout security delta vs baseline: {promotion['heldout_security_failure_delta_vs_fixed_baseline']:.4f}.",
        f"- Evidence supports consideration: {promotion['evidence_supports_consideration']}.",
        f"- Decision: **{promotion['decision']}**.",
        "",
        "Heldout families were not used for mutation, Pareto selection, survivor selection, or champion selection. This heldout split is considered burned after this report.",
        "",
        "A favorable result can only motivate a separate human-reviewed experiment on independent real tasks; it cannot promote a policy into production.",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r3",
        description="Evolve synthetic IDKMesh orchestration genomes with Pareto selection and heldout evaluation.",
    )
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--trials", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mutation-rate", type=float, default=0.35)
    parser.add_argument("--crossover-rate", type=float, default=0.70)
    parser.add_argument("--exploration-floor", type=float, default=0.10)
    parser.add_argument("--archive-size", type=int, default=40)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_r3_experiment(
        R3Config(
            population_size=args.population,
            generations=args.generations,
            trials_per_family=args.trials,
            seed=args.seed,
            mutation_rate=args.mutation_rate,
            crossover_rate=args.crossover_rate,
            exploration_floor=args.exploration_floor,
            archive_size=args.archive_size,
        )
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_r3_report(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
