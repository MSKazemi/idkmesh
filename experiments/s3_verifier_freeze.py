#!/usr/bin/env python3
"""S3 verifier external-validity pre-confirmatory freeze tooling.

This module implements issue #1080 and the v1.1 amendment to the verifier-panel
external-validity preregistration. It has two deliberately non-executing jobs:

* build a calibration-only simulation power plan; and
* bind pre-confirmatory inputs into a content-addressed freeze manifest.

It never executes candidate patches, calls verifier models, or reads a
confirmatory verdict matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

SCHEMA_POWER = "idkmesh.s3-power-plan.v1"
SCHEMA_FREEZE_INPUT = "idkmesh.s3-freeze-input.v1"
SCHEMA_FREEZE = "idkmesh.s3-freeze-manifest.v1"

SEED = 20261011
SIMULATIONS = 10_000
FINAL_BOOTSTRAP_REPLICATES = 10_000
TARGET_POWER = 0.90
DELTA0 = math.log(1.10)
TASK_LADDER = (50, 75, 100, 150, 200, 300, 500)
POWER_INTERVAL_METHOD = (
    "delete-one-cluster jackknife SE with two-sided 95% cluster-t "
    "lower bound at repository and task levels"
)
CLASSES = ("official-pass", "official-fail")
MASK64 = (1 << 64) - 1

REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "analysis_code",
        "power_planning_code",
        "power_plan",
        "calibration_statistics",
        "candidate_inventory",
        "verifier_inventory",
        "stage_assignment",
        "environment_manifest",
    }
)
OPTIONAL_ARTIFACT_ROLES = frozenset({"prompt_bundle", "sandbox_attestation"})
ALLOWED_ARTIFACT_ROLES = REQUIRED_ARTIFACT_ROLES | OPTIONAL_ARTIFACT_ROLES


class S3FreezeError(ValueError):
    """Invalid pre-confirmatory input."""


def _reject_constant(value: str):
    raise S3FreezeError(f"non-finite JSON number is forbidden: {value}")


def _parse_finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise S3FreezeError(f"non-finite JSON number is forbidden: {value}")
    return result


def _no_duplicate_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise S3FreezeError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_constant,
            parse_float=_parse_finite_float,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise S3FreezeError(f"cannot read JSON {path}: {exc}") from exc


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def with_self_digest(payload: dict) -> dict:
    body = dict(payload)
    body.pop("self_sha256", None)
    body["self_sha256"] = sha256_bytes(canonical_bytes(body))
    return body


def verify_self_digest(payload: dict) -> bool:
    claimed = payload.get("self_sha256")
    if not isinstance(claimed, str):
        return False
    body = dict(payload)
    body.pop("self_sha256", None)
    return claimed == sha256_bytes(canonical_bytes(body))


class SplitMix64:
    """Stable PRNG independent of Python's random module implementation."""

    def __init__(self, seed: int):
        self.state = int(seed) & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return (z ^ (z >> 31)) & MASK64

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        bound = (1 << 64) - ((1 << 64) % n)
        while True:
            value = self.next_u64()
            if value < bound:
                return value % n

    def choice(self, values: Sequence):
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self.randbelow(len(values))]

    def sample_without_replacement(self, values: Sequence, k: int) -> list:
        if k < 0 or k > len(values):
            raise ValueError("invalid sample size")
        work = list(values)
        for i in range(k):
            j = i + self.randbelow(len(work) - i)
            work[i], work[j] = work[j], work[i]
        return work[:k]


@dataclass(frozen=True)
class CalibrationRow:
    repository_id: str
    task_id: str
    class_label: str
    delta_logscore: float


@dataclass(frozen=True)
class SimRow:
    repository_id: str
    task_id: str
    class_label: str
    value: float


def load_calibration_jsonl(path: Path) -> list[CalibrationRow]:
    rows: list[CalibrationRow] = []
    allowed = {"stage", "repository_id", "task_id", "class_label", "delta_logscore"}
    seen = set()
    task_owner = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise S3FreezeError(f"cannot read calibration file {path}: {exc}") from exc

    for lineno, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(
                raw,
                object_pairs_hook=_no_duplicate_object,
                parse_constant=_reject_constant,
                parse_float=_parse_finite_float,
            )
        except json.JSONDecodeError as exc:
            raise S3FreezeError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict) or set(obj) != allowed:
            got = sorted(obj) if isinstance(obj, dict) else type(obj).__name__
            raise S3FreezeError(
                f"{path}:{lineno}: expected exactly {sorted(allowed)}, got {got}"
            )
        if obj["stage"] != "calibration":
            raise S3FreezeError(f"{path}:{lineno}: stage must be calibration")

        repo = obj["repository_id"]
        task = obj["task_id"]
        label = obj["class_label"]
        value = obj["delta_logscore"]
        if not isinstance(repo, str) or not repo.strip():
            raise S3FreezeError(f"{path}:{lineno}: repository_id must be non-empty")
        if not isinstance(task, str) or not task.strip():
            raise S3FreezeError(f"{path}:{lineno}: task_id must be non-empty")
        if label not in CLASSES:
            raise S3FreezeError(f"{path}:{lineno}: invalid class_label {label!r}")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise S3FreezeError(f"{path}:{lineno}: delta_logscore must be finite")

        owner = task_owner.setdefault(task, repo)
        if owner != repo:
            raise S3FreezeError(
                f"{path}:{lineno}: task_id {task!r} appears in repositories "
                f"{owner!r} and {repo!r}"
            )
        key = (repo, task, label)
        if key in seen:
            raise S3FreezeError(f"{path}:{lineno}: duplicate task/class row {key!r}")
        seen.add(key)
        rows.append(CalibrationRow(repo, task, label, float(value)))

    if not rows:
        raise S3FreezeError("calibration file is empty")
    return rows


def calibration_summary(rows: Sequence[CalibrationRow]) -> dict:
    repos = sorted({row.repository_id for row in rows})
    tasks = sorted({(row.repository_id, row.task_id) for row in rows})
    return {
        "repositories": len(repos),
        "tasks": len(tasks),
        "class_rows": {
            label: sum(row.class_label == label for row in rows)
            for label in CLASSES
        },
    }


def _center(rows: Sequence[CalibrationRow]) -> list[CalibrationRow]:
    means = {}
    for label in CLASSES:
        values = [row.delta_logscore for row in rows if row.class_label == label]
        if not values:
            raise S3FreezeError(f"calibration lacks {label} rows")
        means[label] = sum(values) / len(values)
    return [
        CalibrationRow(
            row.repository_id,
            row.task_id,
            row.class_label,
            row.delta_logscore - means[row.class_label],
        )
        for row in rows
    ]


def _profiles(rows: Sequence[CalibrationRow]):
    grouped = {}
    for row in rows:
        grouped.setdefault(row.repository_id, {}).setdefault(row.task_id, []).append(row)
    return {
        repo: tuple(
            (task, tuple(entries)) for task, entries in sorted(tasks.items())
        )
        for repo, tasks in sorted(grouped.items())
    }


def _macro_mean(rows: Sequence[SimRow]) -> float | None:
    class_means = {}
    for label in CLASSES:
        values = [row.value for row in rows if row.class_label == label]
        if not values:
            return None
        class_means[label] = sum(values) / len(values)
    return 0.5 * (
        class_means["official-pass"] + class_means["official-fail"]
    )


def _simulate_cohort(
    centered: Sequence[CalibrationRow],
    task_count: int,
    eligible_repository_count: int,
    delta0: float,
    rng: SplitMix64,
) -> list[SimRow]:
    profiles = _profiles(centered)
    repo_ids = sorted(profiles)
    if len(repo_ids) < 8:
        raise S3FreezeError("at least 8 calibration repositories are required")
    if task_count < 8 or eligible_repository_count < 8:
        raise S3FreezeError(
            "task and eligible repository counts must each be at least 8"
        )

    # Never simulate more independent repository clusters than the eligible
    # confirmatory universe actually contains.
    target_repositories = min(task_count, eligible_repository_count)
    selected_profiles = list(
        rng.sample_without_replacement(repo_ids, min(8, target_repositories))
    )
    while len(selected_profiles) < target_repositories:
        selected_profiles.append(rng.choice(repo_ids))

    out: list[SimRow] = []
    task_ordinals = [0] * target_repositories

    def append_task(sim_repo_index: int) -> None:
        profile = profiles[selected_profiles[sim_repo_index]]
        _task, entries = rng.choice(profile)
        sim_repo = f"simrepo-{sim_repo_index:05d}"
        sim_task = (
            f"{sim_repo}/task-{task_ordinals[sim_repo_index]:05d}"
        )
        task_ordinals[sim_repo_index] += 1
        for row in entries:
            out.append(
                SimRow(
                    sim_repo,
                    sim_task,
                    row.class_label,
                    row.delta_logscore + delta0,
                )
            )

    # Give each eligible repository cluster one task first.
    for repo_index in range(target_repositories):
        append_task(repo_index)

    # Allocate remaining tasks in proportion to the empirical profile sizes.
    tickets = []
    for repo_index, profile_name in enumerate(selected_profiles):
        tickets.extend([repo_index] * len(profiles[profile_name]))
    for _ in range(task_count - target_repositories):
        append_task(rng.choice(tickets))

    return out


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile of empty values")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must lie in [0,1]")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


_T975 = {
    7: 2.364624, 8: 2.306004, 9: 2.262157, 10: 2.228139,
    11: 2.200985, 12: 2.178813, 13: 2.160369, 14: 2.144787,
    15: 2.131450, 16: 2.119905, 17: 2.109816, 18: 2.100922,
    19: 2.093024, 20: 2.085963, 21: 2.079614, 22: 2.073873,
    23: 2.068658, 24: 2.063899, 25: 2.059539, 26: 2.055529,
    27: 2.051831, 28: 2.048407, 29: 2.045230, 30: 2.042272,
}


def _t975(df: int) -> float:
    """Two-sided 95% t critical value without a scipy dependency.

    Repository-level inference uses the exact tabulated values over the range
    where the small-cluster correction materially differs from Normal. For
    larger df, a Cornish-Fisher expansion around z=.975 is accurate enough for
    power planning; the *confirmatory* analysis still uses the preregistered
    10,000-replicate percentile cluster bootstrap.
    """
    if df < 1:
        raise ValueError("degrees of freedom must be positive")
    if df in _T975:
        return _T975[df]
    z = 1.959963984540054
    inv = 1.0 / df
    return (
        z
        + (z**3 + z) * inv / 4.0
        + (5.0 * z**5 + 16.0 * z**3 + 3.0 * z) * inv**2 / 96.0
    )


def _cluster_jackknife_lower(
    rows: Sequence[SimRow],
    level: str,
) -> float | None:
    """Fast cluster-t lower bound used only for sample-size planning.

    This avoids an infeasible nested 10k x 10k bootstrap.  It is deliberately
    not the final confirmatory interval; the final analysis retains the frozen
    repository- and task-cluster percentile bootstraps with 10,000 resamples.
    """
    if level == "repository":
        key_fn = lambda row: row.repository_id
    elif level == "task":
        key_fn = lambda row: (row.repository_id, row.task_id)
    else:
        raise ValueError("level must be repository or task")

    estimate = _macro_mean(rows)
    if estimate is None:
        return None

    total_sum = {label: 0.0 for label in CLASSES}
    total_n = {label: 0 for label in CLASSES}
    clusters = {}
    for row in rows:
        total_sum[row.class_label] += row.value
        total_n[row.class_label] += 1
        bucket = clusters.setdefault(
            key_fn(row),
            {
                "sum": {label: 0.0 for label in CLASSES},
                "n": {label: 0 for label in CLASSES},
            },
        )
        bucket["sum"][row.class_label] += row.value
        bucket["n"][row.class_label] += 1

    keys = sorted(clusters, key=lambda item: str(item))
    if level == "repository" and len(keys) < 8:
        return None
    if len(keys) < 2:
        return None

    deleted = []
    for key in keys:
        bucket = clusters[key]
        means = {}
        for label in CLASSES:
            count = total_n[label] - bucket["n"][label]
            if count <= 0:
                return None
            means[label] = (
                total_sum[label] - bucket["sum"][label]
            ) / count
        deleted.append(
            0.5 * (means["official-pass"] + means["official-fail"])
        )

    jack_mean = sum(deleted) / len(deleted)
    variance = (
        (len(deleted) - 1)
        / len(deleted)
        * sum((value - jack_mean) ** 2 for value in deleted)
    )
    se = math.sqrt(max(0.0, variance))
    return estimate - _t975(len(deleted) - 1) * se


def _seed_for(base: int, task_count: int, simulation: int, channel: int) -> int:
    payload = f"{base}:{task_count}:{simulation}:{channel}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _candidate_counts(eligible_tasks: int) -> list[int]:
    values = [n for n in TASK_LADDER if n <= eligible_tasks]
    if eligible_tasks not in values:
        values.append(eligible_tasks)
    return sorted(set(values))


def build_power_plan(
    rows: Sequence[CalibrationRow],
    *,
    calibration_sha256: str,
    eligible_task_count: int,
    eligible_repository_count: int,
    eligible_pass_items: int,
    eligible_fail_items: int,
    simulations: int = SIMULATIONS,
    seed: int = SEED,
    delta0: float = DELTA0,
    target_power: float = TARGET_POWER,
) -> dict:
    if simulations <= 0:
        raise S3FreezeError("simulation count must be positive")
    if not 0.0 < target_power < 1.0:
        raise S3FreezeError("target_power must lie in (0,1)")
    if not math.isfinite(delta0) or delta0 <= 0:
        raise S3FreezeError("delta0 must be a positive finite number")

    for name, value in (
        ("eligible_task_count", eligible_task_count),
        ("eligible_repository_count", eligible_repository_count),
        ("eligible_pass_items", eligible_pass_items),
        ("eligible_fail_items", eligible_fail_items),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise S3FreezeError(f"{name} must be a non-negative integer")

    _validate_sha256(calibration_sha256, "calibration_sha256")
    summary = calibration_summary(rows)
    canonical = (
        simulations == SIMULATIONS
        and seed == SEED
        and abs(delta0 - DELTA0) <= 1e-15
        and abs(target_power - TARGET_POWER) <= 1e-15
    )
    plan = {
        "schema_version": SCHEMA_POWER,
        "canonical": canonical,
        "calibration_sha256": calibration_sha256,
        "design": {
            "seed": seed,
            "smallest_effect_logscore_nats": delta0,
            "smallest_effect_geometric_likelihood_ratio": math.exp(delta0),
            "target_power": target_power,
            "simulated_cohorts": simulations,
            "power_interval_method": POWER_INTERVAL_METHOD,
            "final_confirmatory_bootstrap_replicates_per_level": (
                FINAL_BOOTSTRAP_REPLICATES
            ),
            "power_decision": (
                "both repository- and task-cluster jackknife/cluster-t "
                "95% lower bounds are > 0"
            ),
            "final_confirmatory_decision": (
                "both repository- and task-cluster 10,000-resample percentile "
                "95% intervals have lower bound > 0"
            ),
            "class_estimand": (
                "macro-average of official-pass and official-fail mean "
                "delta_logscore"
            ),
            "centering": (
                "subtract calibration mean within each class before injecting "
                "the smallest effect"
            ),
        },
        "calibration": summary,
        "eligible_universe": {
            "tasks": eligible_task_count,
            "repositories": eligible_repository_count,
            "official_pass_items": eligible_pass_items,
            "official_fail_items": eligible_fail_items,
        },
        "candidates": [],
        "decision": {},
    }

    reasons = []
    if summary["repositories"] < 8:
        reasons.append("calibration_has_fewer_than_8_repositories")
    if (
        summary["class_rows"]["official-pass"] == 0
        or summary["class_rows"]["official-fail"] == 0
    ):
        reasons.append("calibration_missing_pass_or_fail_class")
    if eligible_repository_count < 8:
        reasons.append("eligible_universe_has_fewer_than_8_repositories")
    if eligible_task_count < 8:
        reasons.append("eligible_universe_has_fewer_than_8_tasks")
    if eligible_pass_items == 0 or eligible_fail_items == 0:
        reasons.append("eligible_universe_missing_pass_or_fail_class")

    if reasons:
        plan["decision"] = {
            "status": "infeasible",
            "reasons": reasons,
            "selected_task_count": None,
        }
        return with_self_digest(plan)

    centered = _center(rows)
    selected = None
    for task_count in _candidate_counts(eligible_task_count):
        successes = 0
        valid_repository_intervals = 0
        valid_task_intervals = 0

        for simulation in range(simulations):
            cohort = _simulate_cohort(
                centered,
                task_count,
                eligible_repository_count,
                delta0,
                SplitMix64(_seed_for(seed, task_count, simulation, 0)),
            )
            repo_lower = _cluster_jackknife_lower(
                cohort, "repository"
            )
            task_lower = _cluster_jackknife_lower(cohort, "task")
            if repo_lower is not None:
                valid_repository_intervals += 1
            if task_lower is not None:
                valid_task_intervals += 1
            if (
                repo_lower is not None
                and task_lower is not None
                and repo_lower > 0.0
                and task_lower > 0.0
            ):
                successes += 1

        power = successes / simulations
        plan["candidates"].append(
            {
                "task_count": task_count,
                "estimated_power": power,
                "successful_cohorts": successes,
                "valid_repository_intervals": valid_repository_intervals,
                "valid_task_intervals": valid_task_intervals,
                "simulated_cohorts": simulations,
            }
        )
        if selected is None and power >= target_power:
            selected = task_count
            break

    if selected is not None:
        plan["decision"] = {
            "status": "powered",
            "selected_task_count": selected,
            "target_power": target_power,
        }
    else:
        plan["decision"] = {
            "status": "underpowered_full_universe",
            "selected_task_count": eligible_task_count,
            "target_power": target_power,
            "observed_power_at_full_universe": (
                plan["candidates"][-1]["estimated_power"]
                if plan["candidates"]
                else 0.0
            ),
        }
    return with_self_digest(plan)


def _validate_sha256(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise S3FreezeError(f"{field} must be a string")
    raw = value[7:] if value.startswith("sha256:") else value
    if len(raw) != 64 or any(
        ch not in "0123456789abcdef" for ch in raw.lower()
    ):
        raise S3FreezeError(f"{field} must be a SHA-256 digest")
    return raw.lower()


def _relative_regular_file(root: Path, raw_path: str, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise S3FreezeError(f"{field} must be a non-empty relative path")
    posix = PurePosixPath(raw_path)
    if posix.is_absolute() or ".." in posix.parts:
        raise S3FreezeError(f"{field} must stay inside the freeze root")

    candidate = root
    for component in posix.parts:
        candidate = candidate / component
        if candidate.is_symlink():
            raise S3FreezeError(
                f"{field} must not traverse a symlink: {raw_path}"
            )
    resolved_root = root.resolve()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise S3FreezeError(f"{field} does not exist: {raw_path}") from exc

    if os.path.commonpath([str(resolved_root), str(resolved)]) != str(resolved_root):
        raise S3FreezeError(f"{field} escapes the freeze root")
    if not resolved.is_file():
        raise S3FreezeError(f"{field} must be a regular file")
    return resolved


FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "verdict",
        "verdicts",
        "vote",
        "votes",
        "verdict_matrix",
        "confirmatory_verdict_matrix",
        "confirmatory_outcome",
        "confirmatory_outcomes",
        "judge_output",
        "judge_outputs",
        "model_output",
        "model_outputs",
    }
)


def _walk_forbidden_outcome_keys(value, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_OUTCOME_KEYS:
                raise S3FreezeError(
                    f"pre-confirmatory metadata contains forbidden outcome key "
                    f"{key!r} at {location}"
                )
            _walk_forbidden_outcome_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _walk_forbidden_outcome_keys(child, f"{location}[{idx}]")


def _load_metadata_for_outcome_scan(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix == ".jsonl":
        values = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise S3FreezeError(f"cannot read metadata {path}: {exc}") from exc
        for lineno, raw in enumerate(lines, 1):
            if not raw.strip():
                continue
            try:
                values.append(
                    json.loads(
                        raw,
                        object_pairs_hook=_no_duplicate_object,
                        parse_constant=_reject_constant,
                        parse_float=_parse_finite_float,
                    )
                )
            except json.JSONDecodeError as exc:
                raise S3FreezeError(
                    f"{path}:{lineno}: invalid JSONL metadata: {exc}"
                ) from exc
        return values
    raise S3FreezeError(
        f"pre-confirmatory metadata must be JSON or JSONL: {path}"
    )


def _validate_power_plan_file(path: Path) -> dict:
    plan = load_json(path)
    if not isinstance(plan, dict):
        raise S3FreezeError("power_plan must be a JSON object")
    if plan.get("schema_version") != SCHEMA_POWER:
        raise S3FreezeError("power_plan has the wrong schema_version")
    if plan.get("canonical") is not True:
        raise S3FreezeError(
            "freeze manifest requires a canonical=true power_plan"
        )
    if not verify_self_digest(plan):
        raise S3FreezeError("power_plan self_sha256 is invalid")

    design = plan.get("design")
    if not isinstance(design, dict):
        raise S3FreezeError("power_plan is missing design")
    expected = {
        "seed": SEED,
        "simulated_cohorts": SIMULATIONS,
        "final_confirmatory_bootstrap_replicates_per_level": (
            FINAL_BOOTSTRAP_REPLICATES
        ),
        "target_power": TARGET_POWER,
        "power_interval_method": POWER_INTERVAL_METHOD,
    }
    for key, value in expected.items():
        if design.get(key) != value:
            raise S3FreezeError(
                f"power_plan design {key} must equal frozen value {value!r}"
            )
    effect_size = design.get("smallest_effect_logscore_nats")
    if (
        isinstance(effect_size, bool)
        or not isinstance(effect_size, (int, float))
        or not math.isfinite(effect_size)
        or abs(effect_size - DELTA0) > 1e-15
    ):
        raise S3FreezeError(
            "power_plan smallest effect must be finite log(1.10)"
        )

    decision = plan.get("decision")
    if not isinstance(decision, dict):
        raise S3FreezeError("power_plan is missing decision")
    status = decision.get("status")
    if status not in {"powered", "underpowered_full_universe"}:
        raise S3FreezeError(
            "an infeasible/unknown power plan cannot authorize an experiment freeze"
        )
    return {
        "self_sha256": plan["self_sha256"],
        "status": status,
        "selected_task_count": decision.get("selected_task_count"),
        "calibration_sha256": _validate_sha256(
            plan.get("calibration_sha256"),
            "power_plan.calibration_sha256",
        ),
    }


def _validate_preconfirmatory_artifact(path: Path, role: str):
    if role in {"analysis_code", "power_planning_code"}:
        if path.suffix.lower() != ".py":
            raise S3FreezeError(f"{role} must bind a Python source file")
        return None
    if role == "power_plan":
        return _validate_power_plan_file(path)

    metadata = _load_metadata_for_outcome_scan(path)
    _walk_forbidden_outcome_keys(metadata)
    return None


def build_freeze_manifest(spec: dict, root: Path) -> dict:
    allowed_top = {
        "schema_version",
        "experiment_id",
        "repository_commit",
        "protocol_document",
        "artifacts",
        "upstream",
        "models",
        "seeds",
        "execution_boundary",
        "container_image_digest",
    }
    if not isinstance(spec, dict) or set(spec) != allowed_top:
        raise S3FreezeError(
            f"freeze input must contain exactly {sorted(allowed_top)}"
        )
    if spec["schema_version"] != SCHEMA_FREEZE_INPUT:
        raise S3FreezeError(
            f"schema_version must be {SCHEMA_FREEZE_INPUT}"
        )

    experiment_id = spec["experiment_id"]
    if experiment_id not in {"X6", "X7", "X10"}:
        raise S3FreezeError("experiment_id must be X6, X7, or X10")

    commit = spec["repository_commit"]
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(ch not in "0123456789abcdef" for ch in commit.lower())
    ):
        raise S3FreezeError("repository_commit must be a 40-hex commit SHA")

    protocol = spec["protocol_document"]
    if not isinstance(protocol, str) or not protocol:
        raise S3FreezeError("protocol_document must be non-empty")

    artifacts = spec["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise S3FreezeError("artifacts must be a non-empty list")

    seen_roles = set()
    bound_artifacts = []
    for idx, item in enumerate(artifacts):
        if not isinstance(item, dict) or set(item) != {"role", "path"}:
            raise S3FreezeError(
                f"artifacts[{idx}] must contain role and path"
            )
        role = item["role"]
        if role not in ALLOWED_ARTIFACT_ROLES:
            raise S3FreezeError(
                f"artifacts[{idx}] has forbidden/unknown role {role!r}"
            )
        if role in seen_roles:
            raise S3FreezeError(f"duplicate artifact role: {role}")
        seen_roles.add(role)

        resolved = _relative_regular_file(
            root, item["path"], f"artifacts[{idx}].path"
        )
        validation = _validate_preconfirmatory_artifact(resolved, role)
        bound = {
            "role": role,
            "path": item["path"],
            "sha256": file_sha256(resolved),
            "bytes": resolved.stat().st_size,
        }
        if validation is not None:
            bound["validation"] = validation
        bound_artifacts.append(bound)

    missing = sorted(REQUIRED_ARTIFACT_ROLES - seen_roles)
    if missing:
        raise S3FreezeError(f"missing required artifact roles: {missing}")

    bound_by_role = {item["role"]: item for item in bound_artifacts}
    power_validation = bound_by_role["power_plan"].get("validation")
    if not isinstance(power_validation, dict):
        raise S3FreezeError("power_plan validation metadata is missing")
    if (
        power_validation["calibration_sha256"]
        != bound_by_role["calibration_statistics"]["sha256"]
    ):
        raise S3FreezeError(
            "calibration_statistics digest does not match power_plan calibration_sha256"
        )

    if experiment_id == "X7" and "prompt_bundle" not in seen_roles:
        raise S3FreezeError("X7 requires a prompt_bundle artifact")

    seeds = spec["seeds"]
    if (
        not isinstance(seeds, dict)
        or set(seeds)
        != {"bootstrap", "permutation", "stage_assignment"}
    ):
        raise S3FreezeError(
            "seeds must contain bootstrap, permutation, stage_assignment"
        )
    if seeds["bootstrap"] != SEED or seeds["permutation"] != SEED:
        raise S3FreezeError(
            f"bootstrap and permutation seeds must both be {SEED}"
        )
    if (
        isinstance(seeds["stage_assignment"], bool)
        or not isinstance(seeds["stage_assignment"], int)
    ):
        raise S3FreezeError("stage_assignment seed must be an integer")

    execution = spec["execution_boundary"]
    expected_execution = {
        "untrusted_patch_execution",
        "sandbox_required",
        "sandbox_issue",
    }
    if not isinstance(execution, dict) or set(execution) != expected_execution:
        raise S3FreezeError(
            "execution_boundary must contain untrusted_patch_execution, "
            "sandbox_required, sandbox_issue"
        )
    if (
        not isinstance(execution["untrusted_patch_execution"], bool)
        or not isinstance(execution["sandbox_required"], bool)
    ):
        raise S3FreezeError("execution boundary flags must be booleans")
    if execution["sandbox_issue"] != 804:
        raise S3FreezeError("sandbox_issue must remain #804")
    if (
        execution["untrusted_patch_execution"]
        and not execution["sandbox_required"]
    ):
        raise S3FreezeError("untrusted patch execution requires the sandbox")

    upstream = spec["upstream"]
    if (
        not isinstance(upstream, dict)
        or set(upstream) != {"name", "commit", "artifacts"}
    ):
        raise S3FreezeError("upstream must contain name, commit, artifacts")
    if not isinstance(upstream["name"], str) or not upstream["name"]:
        raise S3FreezeError("upstream.name must be non-empty")
    if not isinstance(upstream["commit"], str) or not upstream["commit"]:
        raise S3FreezeError("upstream.commit must be non-empty")

    upstream_artifacts = upstream["artifacts"]
    if not isinstance(upstream_artifacts, list) or not upstream_artifacts:
        raise S3FreezeError("upstream.artifacts must be non-empty")

    frozen_upstream = []
    names = set()
    for idx, item in enumerate(upstream_artifacts):
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "sha256"}
        ):
            raise S3FreezeError(
                f"upstream.artifacts[{idx}] must contain name and sha256"
            )
        name = item["name"]
        if not isinstance(name, str) or not name or name in names:
            raise S3FreezeError(
                f"invalid/duplicate upstream artifact name: {name!r}"
            )
        names.add(name)
        frozen_upstream.append(
            {
                "name": name,
                "sha256": _validate_sha256(
                    item["sha256"],
                    f"upstream.artifacts[{idx}].sha256",
                ),
            }
        )

    models = spec["models"]
    if not isinstance(models, list):
        raise S3FreezeError("models must be a list")

    model_keys = {
        "lineage",
        "checkpoint",
        "digest",
        "release_date",
        "training_cutoff",
        "benchmark_contamination",
        "benchmark_specific_finetuning",
    }
    frozen_models = []
    seen_checkpoints = set()
    for idx, model in enumerate(models):
        if not isinstance(model, dict) or set(model) != model_keys:
            raise S3FreezeError(f"models[{idx}] has the wrong fields")
        if model["benchmark_contamination"] not in {
            "ruled_out",
            "known_possible",
            "unknown",
        }:
            raise S3FreezeError(
                f"models[{idx}] has invalid benchmark_contamination"
            )
        if not isinstance(model["benchmark_specific_finetuning"], bool):
            raise S3FreezeError(
                f"models[{idx}].benchmark_specific_finetuning must be boolean"
            )
        if model["benchmark_specific_finetuning"]:
            raise S3FreezeError(
                f"models[{idx}] is benchmark-specifically fine-tuned and "
                "is ineligible for the primary independent-family panel"
            )
        for key in (
            "lineage",
            "checkpoint",
            "release_date",
            "training_cutoff",
        ):
            if model[key] is not None and not isinstance(model[key], str):
                raise S3FreezeError(
                    f"models[{idx}].{key} must be string or null"
                )

        checkpoint = model["checkpoint"]
        if not checkpoint or checkpoint in seen_checkpoints:
            raise S3FreezeError(
                f"models[{idx}] checkpoint must be unique and non-empty"
            )
        seen_checkpoints.add(checkpoint)
        frozen = dict(model)
        frozen["digest"] = _validate_sha256(
            model["digest"], f"models[{idx}].digest"
        )
        frozen_models.append(frozen)

    if experiment_id == "X7":
        if not frozen_models:
            raise S3FreezeError("X7 requires model metadata")
        lineages = {
            model["lineage"]
            for model in frozen_models
            if model["lineage"]
        }
        if len(lineages) < 3:
            raise S3FreezeError(
                "X7 freeze input must declare at least 3 model lineages"
            )

    container_digest = spec["container_image_digest"]
    if container_digest is not None:
        container_digest = _validate_sha256(
            container_digest, "container_image_digest"
        )

    protocol_path = _relative_regular_file(
        root, protocol, "protocol_document"
    )
    manifest = {
        "schema_version": SCHEMA_FREEZE,
        "experiment_id": experiment_id,
        "repository_commit": commit.lower(),
        "protocol": {
            "path": protocol,
            "sha256": file_sha256(protocol_path),
        },
        "artifacts": sorted(
            bound_artifacts, key=lambda item: item["role"]
        ),
        "upstream": {
            "name": upstream["name"],
            "commit": upstream["commit"],
            "artifacts": sorted(
                frozen_upstream, key=lambda item: item["name"]
            ),
        },
        "models": sorted(
            frozen_models,
            key=lambda item: (
                item["lineage"] or "",
                item["checkpoint"],
            ),
        ),
        "seeds": dict(seeds),
        "execution_boundary": dict(execution),
        "container_image_digest": container_digest,
        "claims": {
            "contains_confirmatory_outcomes": False,
            "executes_untrusted_code": False,
            "grants_acceptance_authority": False,
        },
    }
    return with_self_digest(manifest)



def validate_freeze_manifest(manifest: dict, root: Path) -> None:
    """Reconstruct the complete frozen artifact manifest from current bytes.

    A self-digest authenticates only the *description*, not the files it names.
    Comparing to a fresh build rechecks paths, artifact types, outcome exclusion,
    power-plan defaults, calibration binding, model metadata, and SHA-256 bytes.
    This is a local preflight, not a signature, provenance attestation, or
    immunity to external files changing after the check.
    """
    expected_fields = {
        "schema_version", "experiment_id", "repository_commit",
        "protocol", "artifacts", "upstream", "models", "seeds",
        "execution_boundary", "container_image_digest", "claims",
        "self_sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise S3FreezeError("freeze manifest has unexpected or missing fields")
    if manifest["schema_version"] != SCHEMA_FREEZE:
        raise S3FreezeError("freeze manifest has the wrong schema_version")
    if not verify_self_digest(manifest):
        raise S3FreezeError("freeze manifest self_sha256 is invalid")
    if manifest["claims"] != {
        "contains_confirmatory_outcomes": False,
        "executes_untrusted_code": False,
        "grants_acceptance_authority": False,
    }:
        raise S3FreezeError("freeze manifest asserts forbidden authority/outcomes")

    protocol = manifest["protocol"]
    artifacts = manifest["artifacts"]
    if (
        not isinstance(protocol, dict)
        or set(protocol) != {"path", "sha256"}
        or not isinstance(artifacts, list)
    ):
        raise S3FreezeError("freeze manifest has malformed protocol/artifacts")
    artifact_specs = []
    for idx, item in enumerate(artifacts):
        if (
            not isinstance(item, dict)
            or not {"role", "path", "sha256", "bytes"}.issubset(item)
            or set(item) - {"role", "path", "sha256", "bytes", "validation"}
        ):
            raise S3FreezeError(f"freeze manifest artifact {idx} is malformed")
        artifact_specs.append({"role": item["role"], "path": item["path"]})

    spec = {
        "schema_version": SCHEMA_FREEZE_INPUT,
        "experiment_id": manifest["experiment_id"],
        "repository_commit": manifest["repository_commit"],
        "protocol_document": protocol["path"],
        "artifacts": artifact_specs,
        "upstream": manifest["upstream"],
        "models": manifest["models"],
        "seeds": manifest["seeds"],
        "execution_boundary": manifest["execution_boundary"],
        "container_image_digest": manifest["container_image_digest"],
    }
    try:
        rebuilt = build_freeze_manifest(spec, root)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise S3FreezeError("freeze manifest has malformed bound metadata") from exc
    if rebuilt != manifest:
        raise S3FreezeError(
            "freeze manifest differs from current bound files or canonical schema"
        )


def _write_new_json(path: Path, payload: dict) -> None:
    if path.exists():
        raise S3FreezeError(
            f"refusing to overwrite existing freeze artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _cmd_power(args) -> int:
    calibration_path = Path(args.calibration)
    rows = load_calibration_jsonl(calibration_path)
    plan = build_power_plan(
        rows,
        calibration_sha256=file_sha256(calibration_path),
        eligible_task_count=args.eligible_task_count,
        eligible_repository_count=args.eligible_repository_count,
        eligible_pass_items=args.eligible_pass_items,
        eligible_fail_items=args.eligible_fail_items,
        simulations=args.simulations,
        seed=args.seed,
        delta0=args.delta0,
        target_power=args.target_power,
    )
    _write_new_json(Path(args.out), plan)
    print(
        json.dumps(
            {
                "status": plan["decision"]["status"],
                "canonical": plan["canonical"],
                "out": args.out,
                "self_sha256": plan["self_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_manifest(args) -> int:
    spec = load_json(Path(args.spec))
    manifest = build_freeze_manifest(spec, Path(args.root))
    _write_new_json(Path(args.out), manifest)
    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "out": args.out,
                "self_sha256": manifest["self_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_validate(args) -> int:
    payload = load_json(Path(args.manifest))
    if not isinstance(payload, dict) or payload.get("schema_version") not in {
        SCHEMA_POWER,
        SCHEMA_FREEZE,
    }:
        raise S3FreezeError("unsupported manifest schema")
    if not verify_self_digest(payload):
        raise S3FreezeError(
            "self_sha256 does not match canonical manifest content"
        )

    if payload["schema_version"] == SCHEMA_FREEZE:
        if args.root is None:
            raise S3FreezeError(
                "--root is required to validate freeze-bound artifact contents"
            )
        validate_freeze_manifest(payload, Path(args.root))
        verification_scope = "bound_artifacts_and_self_digest"
        artifact_bindings_verified = True
    else:
        # A standalone plan is evidence of the plan document's integrity,
        # not evidence that source files or a confirmatory study were frozen.
        verification_scope = "power_plan_self_digest_only"
        artifact_bindings_verified = False
        if payload.get("canonical") is True and (
            isinstance(payload.get("decision"), dict)
            and payload["decision"].get("status")
            in {"powered", "underpowered_full_universe"}
        ):
            _validate_power_plan_file(Path(args.manifest))
            verification_scope = "canonical_power_plan_structure"

    print(
        json.dumps(
            {
                "valid": True,
                "schema_version": payload["schema_version"],
                "self_sha256": payload["self_sha256"],
                "verification_scope": verification_scope,
                "artifact_bindings_verified": artifact_bindings_verified,
                "authorizes_confirmatory_execution": False,
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    power = sub.add_parser(
        "power-plan",
        help="build calibration-only S3 power_plan.json",
    )
    power.add_argument(
        "calibration",
        help="JSONL with calibration task/class log-score differences",
    )
    power.add_argument(
        "--eligible-task-count",
        type=int,
        required=True,
    )
    power.add_argument(
        "--eligible-repository-count",
        type=int,
        required=True,
    )
    power.add_argument(
        "--eligible-pass-items",
        type=int,
        required=True,
    )
    power.add_argument(
        "--eligible-fail-items",
        type=int,
        required=True,
    )
    power.add_argument(
        "--simulations",
        type=int,
        default=SIMULATIONS,
        help="non-default values create canonical=false development plans",
    )
    power.add_argument("--seed", type=int, default=SEED)
    power.add_argument("--delta0", type=float, default=DELTA0)
    power.add_argument(
        "--target-power",
        type=float,
        default=TARGET_POWER,
    )
    power.add_argument("--out", required=True)
    power.set_defaults(func=_cmd_power)

    freeze = sub.add_parser(
        "freeze-manifest",
        help="bind pre-confirmatory inputs by SHA-256",
    )
    freeze.add_argument(
        "spec",
        help=f"{SCHEMA_FREEZE_INPUT} JSON input",
    )
    freeze.add_argument(
        "--root",
        default=".",
        help="repository/freeze root",
    )
    freeze.add_argument("--out", required=True)
    freeze.set_defaults(func=_cmd_manifest)

    validate = sub.add_parser(
        "validate",
        help="validate a power-plan digest or rehash a freeze's bound artifacts",
    )
    validate.add_argument("manifest")
    validate.add_argument(
        "--root",
        help="freeze artifact root (required for a freeze manifest)",
    )
    validate.set_defaults(func=_cmd_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except S3FreezeError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
