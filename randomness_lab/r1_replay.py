from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import random
from statistics import mean, stdev
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ReplayConfig:
    swarm_size: int = 2
    bootstrap_trials: int = 200
    seed: int = 42
    baseline_signature: str | None = None
    human_minute_cost_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.swarm_size < 2:
            raise ValueError("swarm_size must be >= 2")
        if self.bootstrap_trials < 2:
            raise ValueError("bootstrap_trials must be >= 2")
        if self.human_minute_cost_weight < 0.0:
            raise ValueError("human_minute_cost_weight must be non-negative")


@dataclass(frozen=True)
class ReplayCandidate:
    result_manifest_id: str
    work_unit_id: str
    attempt: int
    worker_id: str
    structural_signature: str
    structural_signature_source: str
    verified_good: bool
    independent_test_pass: bool | None
    regression_finding: bool
    security_finding: bool
    compute_units: float | None
    human_minutes: float | None
    observed_wall_seconds: float
    verifier_signatures: tuple[str, ...]


def _require_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _structural_signature(result: dict[str, object]) -> tuple[str, str]:
    extensions = result.get("extensions")
    if isinstance(extensions, dict):
        override = extensions.get("r1_structural_signature")
        if isinstance(override, str) and override.strip():
            return override.strip(), "result.extensions.r1_structural_signature"

    worker = _require_mapping(result.get("worker"), "result.worker")
    parts = [
        str(worker.get("type", "unknown")),
        str(worker.get("adapter", "unknown")),
    ]
    model = worker.get("model")
    if isinstance(model, dict):
        parts.extend(
            [
                str(model.get("provider", "unknown-provider")),
                str(model.get("name", "unknown-model")),
                str(model.get("version", "unknown-version")),
            ]
        )
    else:
        parts.extend(["no-model", "no-model", "no-model"])
    return "|".join(parts), "result.worker metadata"


def _verifier_signature(verification: dict[str, object]) -> str:
    verifier = _require_mapping(verification.get("verifier"), "verification.verifier")
    parts = [
        str(verifier.get("type", "unknown")),
        str(verifier.get("adapter", "unknown")),
    ]
    model = verifier.get("model")
    if isinstance(model, dict):
        parts.extend(
            [
                str(model.get("provider", "unknown-provider")),
                str(model.get("name", "unknown-model")),
                str(model.get("version", "unknown-version")),
            ]
        )
    return "|".join(parts)


def _independent_verifications(
    verifications: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    independent = []
    for verification in verifications:
        independence = verification.get("independence")
        if isinstance(independence, dict) and independence.get("independent_from_worker") is True:
            independent.append(verification)
    return independent


def _verification_verdict(
    result: dict[str, object],
    verifications: Sequence[dict[str, object]],
) -> tuple[bool | None, str]:
    if not verifications:
        return None, "no_independent_verification"

    reject_signal = False
    all_accept = True
    for verification in verifications:
        status = verification.get("status")
        decision_support = verification.get("decision_support")
        recommendation = (
            decision_support.get("recommendation")
            if isinstance(decision_support, dict)
            else None
        )
        checks = verification.get("checks")
        required_failure = False
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict) or check.get("required") is not True:
                    continue
                if check.get("status") in {"failed", "error"}:
                    required_failure = True
                    break

        if status == "failed" or recommendation == "reject_candidate" or required_failure:
            reject_signal = True
        if status != "passed" or recommendation != "accept_candidate" or required_failure:
            all_accept = False

    if reject_signal:
        return False, "independent_rejection"
    if all_accept and result.get("status") == "succeeded":
        return True, "independent_acceptance"
    return None, "inconclusive_or_conflicting_verification"


def _independent_test_pass(
    verifications: Sequence[dict[str, object]],
) -> bool | None:
    statuses: list[str] = []
    for verification in verifications:
        checks = verification.get("checks")
        if not isinstance(checks, list):
            continue
        for check in checks:
            if isinstance(check, dict) and check.get("type") == "test":
                status = check.get("status")
                if isinstance(status, str):
                    statuses.append(status)
    if not statuses:
        return None
    if any(status in {"failed", "error"} for status in statuses):
        return False
    if all(status == "passed" for status in statuses):
        return True
    return None


def _finding_flag(
    verifications: Sequence[dict[str, object]],
    category: str,
) -> bool:
    for verification in verifications:
        findings = verification.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            if finding.get("category") != category:
                continue
            if finding.get("severity") in {"low", "medium", "high", "critical"}:
                return True
    return False


def _optional_resource(resources: dict[str, object], name: str) -> float | None:
    value = resources.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _sum_optional(values: Sequence[float | None]) -> float | None:
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None)


def normalize_replay_candidates(
    result_manifests: Sequence[dict[str, object]],
    verification_results: Sequence[dict[str, object]],
) -> tuple[list[ReplayCandidate], dict[str, object]]:
    results_by_id: dict[str, dict[str, object]] = {}
    for result in result_manifests:
        if result.get("schema_version") != "0.1":
            raise ValueError("R1 replay currently accepts ResultManifest schema_version 0.1")
        result_id = result.get("id")
        if not isinstance(result_id, str) or not result_id:
            raise ValueError("every ResultManifest requires a non-empty id")
        if result_id in results_by_id:
            raise ValueError(f"duplicate ResultManifest id: {result_id}")
        results_by_id[result_id] = result

    verification_by_result: dict[str, list[dict[str, object]]] = {}
    unknown_verification_refs = 0
    for verification in verification_results:
        if verification.get("schema_version") != "0.1":
            raise ValueError("R1 replay currently accepts VerificationResult schema_version 0.1")
        result_id = verification.get("result_manifest_id")
        if not isinstance(result_id, str) or not result_id:
            raise ValueError("every VerificationResult requires result_manifest_id")
        if result_id not in results_by_id:
            unknown_verification_refs += 1
            continue
        verification_by_result.setdefault(result_id, []).append(verification)

    candidates: list[ReplayCandidate] = []
    excluded = {
        "no_independent_verification": 0,
        "inconclusive_or_conflicting_verification": 0,
    }

    for result_id, result in results_by_id.items():
        all_verifications = verification_by_result.get(result_id, [])
        independent = _independent_verifications(all_verifications)
        verdict, reason = _verification_verdict(result, independent)
        if verdict is None:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue

        work_unit_id = result.get("work_unit_id")
        attempt = result.get("attempt")
        worker = _require_mapping(result.get("worker"), "result.worker")
        worker_id = worker.get("id")
        if not isinstance(work_unit_id, str) or not work_unit_id:
            raise ValueError(f"ResultManifest {result_id} requires work_unit_id")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError(f"ResultManifest {result_id} requires integer attempt >= 1")
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError(f"ResultManifest {result_id} requires worker.id")

        signature, signature_source = _structural_signature(result)
        result_resources = _require_mapping(result.get("resources"), "result.resources")
        result_wall = _optional_resource(result_resources, "wall_seconds")
        if result_wall is None:
            raise ValueError(f"ResultManifest {result_id} requires numeric resources.wall_seconds")

        verification_walls: list[float] = []
        human_values: list[float | None] = [_optional_resource(result_resources, "human_minutes")]
        verifier_signatures = []
        for verification in independent:
            resources = _require_mapping(
                verification.get("resources"), "verification.resources"
            )
            wall = _optional_resource(resources, "wall_seconds")
            if wall is None:
                raise ValueError("VerificationResult requires numeric resources.wall_seconds")
            verification_walls.append(wall)
            human_values.append(_optional_resource(resources, "human_minutes"))
            verifier_signatures.append(_verifier_signature(verification))

        candidates.append(
            ReplayCandidate(
                result_manifest_id=result_id,
                work_unit_id=work_unit_id,
                attempt=attempt,
                worker_id=worker_id,
                structural_signature=signature,
                structural_signature_source=signature_source,
                verified_good=bool(verdict),
                independent_test_pass=_independent_test_pass(independent),
                regression_finding=_finding_flag(independent, "regression"),
                security_finding=_finding_flag(independent, "security"),
                compute_units=_optional_resource(result_resources, "compute_units"),
                human_minutes=_sum_optional(human_values),
                observed_wall_seconds=result_wall + sum(verification_walls),
                verifier_signatures=tuple(sorted(set(verifier_signatures))),
            )
        )

    diagnostics = {
        "input_result_manifests": len(result_manifests),
        "input_verification_results": len(verification_results),
        "conclusive_candidates": len(candidates),
        "excluded": excluded,
        "unknown_verification_result_references": unknown_verification_refs,
    }
    return candidates, diagnostics


def _load_json_file(path: Path) -> list[dict[str, object]]:
    if path.suffix.lower() == ".jsonl":
        objects = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            objects.append(value)
        return objects

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return list(value)
    raise ValueError(f"{path} must contain an object, an array of objects, or JSONL")


def load_json_objects(path: Path) -> list[dict[str, object]]:
    if path.is_file():
        return _load_json_file(path)
    if not path.is_dir():
        raise ValueError(f"input path does not exist: {path}")
    files = sorted(
        file
        for file in path.rglob("*")
        if file.is_file() and file.suffix.lower() in {".json", ".jsonl"}
    )
    objects: list[dict[str, object]] = []
    for file in files:
        objects.extend(_load_json_file(file))
    return objects


def _group_candidates(
    candidates: Sequence[ReplayCandidate],
) -> dict[str, dict[str, list[ReplayCandidate]]]:
    grouped: dict[str, dict[str, list[ReplayCandidate]]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.work_unit_id, {}).setdefault(
            candidate.structural_signature, []
        ).append(candidate)
    for signature_pools in grouped.values():
        for pool in signature_pools.values():
            pool.sort(key=lambda item: (item.attempt, item.result_manifest_id))
    return grouped


def _choose_baseline_signature(
    grouped: dict[str, dict[str, list[ReplayCandidate]]],
    swarm_size: int,
    requested: str | None,
) -> str | None:
    signatures = sorted(
        {signature for pools in grouped.values() for signature in pools}
    )
    if requested is not None:
        return requested if requested in signatures else None
    if not signatures:
        return None

    scores = []
    for signature in signatures:
        eligible_tasks = sum(
            1 for pools in grouped.values() if len(pools.get(signature, [])) >= swarm_size
        )
        total_candidates = sum(len(pools.get(signature, [])) for pools in grouped.values())
        scores.append((eligible_tasks, total_candidates, signature))
    best_eligible = max(score[0] for score in scores)
    best_total = max(score[1] for score in scores if score[0] == best_eligible)
    return min(
        score[2]
        for score in scores
        if score[0] == best_eligible and score[1] == best_total
    )


def _pearson_binary(xs: Sequence[int], ys: Sequence[int]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = mean(xs)
    my = mean(ys)
    dx = [value - mx for value in xs]
    dy = [value - my for value in ys]
    denominator = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if denominator == 0.0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / denominator


def _signature_failure_correlations(
    grouped: dict[str, dict[str, list[ReplayCandidate]]],
) -> list[dict[str, object]]:
    signatures = sorted(
        {signature for pools in grouped.values() for signature in pools}
    )
    rows = []
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index + 1 :]:
            left_failures = []
            right_failures = []
            for pools in grouped.values():
                left_pool = pools.get(left)
                right_pool = pools.get(right)
                if not left_pool or not right_pool:
                    continue
                left_failures.append(int(not left_pool[0].verified_good))
                right_failures.append(int(not right_pool[0].verified_good))
            correlation = _pearson_binary(left_failures, right_failures)
            rows.append(
                {
                    "left_signature": left,
                    "right_signature": right,
                    "overlap_tasks": len(left_failures),
                    "first_attempt_failure_correlation": correlation,
                }
            )
    return rows


def _candidate_set_metrics(
    candidates: Sequence[ReplayCandidate],
    human_minute_cost_weight: float,
) -> dict[str, object]:
    success = any(candidate.verified_good for candidate in candidates)
    independent_test_pass = any(
        candidate.independent_test_pass is True for candidate in candidates
    )
    regression_finding = any(candidate.regression_finding for candidate in candidates)
    security_finding = any(candidate.security_finding for candidate in candidates)
    compute_values = [candidate.compute_units for candidate in candidates]
    human_values = [candidate.human_minutes for candidate in candidates]
    compute = _sum_optional(compute_values)
    human = _sum_optional(human_values)
    normalized_cost = (
        compute + human_minute_cost_weight * human
        if compute is not None and human is not None
        else None
    )
    return {
        "success": success,
        "independent_test_pass": independent_test_pass,
        "regression_finding": regression_finding,
        "security_finding": security_finding,
        "compute_units": compute,
        "human_minutes": human,
        "normalized_cost": normalized_cost,
        "parallel_observed_wall_seconds": max(
            candidate.observed_wall_seconds for candidate in candidates
        ),
    }


def _trial_metrics(
    sampled_tasks: Sequence[str],
    grouped: dict[str, dict[str, list[ReplayCandidate]]],
    baseline_signature: str,
    config: ReplayConfig,
    rng: random.Random,
) -> tuple[dict[str, object], dict[str, object]]:
    aggregates = {
        "replication": {
            "successes": 0,
            "independent_tests": 0,
            "regressions": 0,
            "security": 0,
            "compute": 0.0,
            "human": 0.0,
            "cost": 0.0,
            "cost_complete": True,
            "wall": 0.0,
        },
        "diversity": {
            "successes": 0,
            "independent_tests": 0,
            "regressions": 0,
            "security": 0,
            "compute": 0.0,
            "human": 0.0,
            "cost": 0.0,
            "cost_complete": True,
            "wall": 0.0,
        },
    }

    for task_id in sampled_tasks:
        pools = grouped[task_id]
        replication_candidates = rng.sample(
            pools[baseline_signature], k=config.swarm_size
        )
        signatures = sorted(pools)
        chosen_signatures = rng.sample(signatures, k=config.swarm_size)
        diversity_candidates = [rng.choice(pools[signature]) for signature in chosen_signatures]

        for name, selected in (
            ("replication", replication_candidates),
            ("diversity", diversity_candidates),
        ):
            metrics = _candidate_set_metrics(selected, config.human_minute_cost_weight)
            aggregate = aggregates[name]
            aggregate["successes"] += int(bool(metrics["success"]))
            aggregate["independent_tests"] += int(bool(metrics["independent_test_pass"]))
            aggregate["regressions"] += int(bool(metrics["regression_finding"]))
            aggregate["security"] += int(bool(metrics["security_finding"]))
            aggregate["wall"] += float(metrics["parallel_observed_wall_seconds"])
            if metrics["normalized_cost"] is None:
                aggregate["cost_complete"] = False
            else:
                aggregate["compute"] += float(metrics["compute_units"])
                aggregate["human"] += float(metrics["human_minutes"])
                aggregate["cost"] += float(metrics["normalized_cost"])

    task_count = len(sampled_tasks)
    output = {}
    for name, aggregate in aggregates.items():
        cost_complete = bool(aggregate["cost_complete"])
        total_cost = float(aggregate["cost"]) if cost_complete else None
        output[name] = {
            "verified_success_rate": aggregate["successes"] / task_count,
            "independent_test_coverage_rate": aggregate["independent_tests"] / task_count,
            "candidate_regression_finding_rate": aggregate["regressions"] / task_count,
            "candidate_security_finding_rate": aggregate["security"] / task_count,
            "mean_parallel_observed_wall_seconds": aggregate["wall"] / task_count,
            "total_compute_units": float(aggregate["compute"]) if cost_complete else None,
            "total_human_minutes": float(aggregate["human"]) if cost_complete else None,
            "normalized_total_cost": total_cost,
            "verified_utility_per_normalized_cost": (
                aggregate["successes"] / total_cost
                if total_cost is not None and total_cost > 0.0
                else None
            ),
            "resource_cost_complete": cost_complete,
        }
    return output["replication"], output["diversity"]


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _bootstrap_delta_summary(values: Sequence[float]) -> dict[str, object]:
    if len(values) < 2:
        return {
            "status": "insufficient_data",
            "sample_count": len(values),
            "classification": "insufficient-data",
        }
    interval = [_percentile(values, 0.025), _percentile(values, 0.975)]
    if interval[0] > 0.0:
        classification = "helps"
    elif interval[1] < 0.0:
        classification = "hurts"
    else:
        classification = "uncertain"
    return {
        "status": "ok",
        "sample_count": len(values),
        "mean_delta": mean(values),
        "sample_std": stdev(values),
        "bootstrap_percentile_95_interval": interval,
        "min_delta": min(values),
        "max_delta": max(values),
        "classification": classification,
    }


def run_replay_analysis(
    candidates: Sequence[ReplayCandidate],
    config: ReplayConfig,
    *,
    normalization_diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    grouped = _group_candidates(candidates)
    baseline_signature = _choose_baseline_signature(
        grouped, config.swarm_size, config.baseline_signature
    )

    if baseline_signature is None:
        return {
            "schema_version": 1,
            "experiment": "R1-real-result-replay",
            "status": "insufficient_data",
            "reason": "no baseline structural signature available",
            "config": asdict(config),
            "normalization": normalization_diagnostics or {},
        }

    eligible_tasks = []
    for task_id, pools in grouped.items():
        if len(pools.get(baseline_signature, [])) < config.swarm_size:
            continue
        if len([signature for signature, pool in pools.items() if pool]) < config.swarm_size:
            continue
        eligible_tasks.append(task_id)
    eligible_tasks.sort()

    coverage = {
        "conclusive_candidates": len(candidates),
        "work_units_with_conclusive_candidates": len(grouped),
        "eligible_work_units": len(eligible_tasks),
        "baseline_signature": baseline_signature,
        "swarm_size": config.swarm_size,
    }
    if not eligible_tasks:
        return {
            "schema_version": 1,
            "experiment": "R1-real-result-replay",
            "status": "insufficient_data",
            "reason": (
                "no work unit has both enough baseline replicas and enough distinct "
                "structural signatures for a fixed-budget comparison"
            ),
            "config": asdict(config),
            "coverage": coverage,
            "normalization": normalization_diagnostics or {},
            "signature_failure_correlations": _signature_failure_correlations(grouped),
        }

    rng = random.Random(config.seed)
    raw_trials = []
    success_deltas = []
    utility_deltas = []
    for trial_index in range(config.bootstrap_trials):
        sampled_tasks = [rng.choice(eligible_tasks) for _ in range(len(eligible_tasks))]
        replication, diversity = _trial_metrics(
            sampled_tasks, grouped, baseline_signature, config, rng
        )
        success_delta = (
            float(diversity["verified_success_rate"])
            - float(replication["verified_success_rate"])
        )
        success_deltas.append(success_delta)
        replication_utility = replication["verified_utility_per_normalized_cost"]
        diversity_utility = diversity["verified_utility_per_normalized_cost"]
        utility_delta = None
        if replication_utility is not None and diversity_utility is not None:
            utility_delta = float(diversity_utility) - float(replication_utility)
            utility_deltas.append(utility_delta)

        raw_trials.append(
            {
                "trial_index": trial_index,
                "replication": replication,
                "structural_diversity": diversity,
                "delta": {
                    "verified_success_rate": success_delta,
                    "verified_utility_per_normalized_cost": utility_delta,
                },
            }
        )

    return {
        "schema_version": 1,
        "experiment": "R1-real-result-replay",
        "status": "ok",
        "config": asdict(config),
        "input_schemas": {
            "result_manifest": "IDKMesh Worker Result Manifest v0.1",
            "verification_result": "IDKMesh Independent Verification Result v0.1",
        },
        "coverage": coverage,
        "normalization": normalization_diagnostics or {},
        "success_delta": _bootstrap_delta_summary(success_deltas),
        "utility_delta": _bootstrap_delta_summary(utility_deltas),
        "signature_failure_correlations": _signature_failure_correlations(grouped),
        "raw_bootstrap_trials": raw_trials,
        "candidate_index": [
            {
                "result_manifest_id": candidate.result_manifest_id,
                "work_unit_id": candidate.work_unit_id,
                "attempt": candidate.attempt,
                "worker_id": candidate.worker_id,
                "structural_signature": candidate.structural_signature,
                "structural_signature_source": candidate.structural_signature_source,
                "verified_good": candidate.verified_good,
                "independent_test_pass": candidate.independent_test_pass,
                "regression_finding": candidate.regression_finding,
                "security_finding": candidate.security_finding,
                "compute_units": candidate.compute_units,
                "human_minutes": candidate.human_minutes,
                "observed_wall_seconds": candidate.observed_wall_seconds,
                "verifier_signatures": list(candidate.verifier_signatures),
            }
            for candidate in candidates
        ],
        "interpretation_guardrail": (
            "This is an observational replay of independently verified results. It can measure "
            "coverage and failure correlation in the supplied data, but it does not randomize "
            "real worker assignment and can still be confounded by task selection and worker quality."
        ),
    }


def run_replay_from_paths(
    results_path: Path,
    verifications_path: Path,
    config: ReplayConfig,
) -> dict[str, object]:
    result_manifests = load_json_objects(results_path)
    verification_results = load_json_objects(verifications_path)
    candidates, diagnostics = normalize_replay_candidates(
        result_manifests, verification_results
    )
    return run_replay_analysis(
        candidates,
        config,
        normalization_diagnostics=diagnostics,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m randomness_lab.r1_replay",
        description=(
            "Replay real IDKMesh ResultManifest + VerificationResult data through the R1 "
            "fixed-budget replication-vs-diversity analysis."
        ),
    )
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--verifications", type=Path, required=True)
    parser.add_argument("--swarm-size", type=int, default=2)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--baseline-signature")
    parser.add_argument("--human-minute-cost-weight", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_replay_from_paths(
        args.results,
        args.verifications,
        ReplayConfig(
            swarm_size=args.swarm_size,
            bootstrap_trials=args.trials,
            seed=args.seed,
            baseline_signature=args.baseline_signature,
            human_minute_cost_weight=args.human_minute_cost_weight,
        ),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
