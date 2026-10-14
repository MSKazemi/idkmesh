"""E051 -- does the marginal-evidence selector recover the true best verifier?

Issue 693 asks four research questions about ``idkmesh gate-marginal`` and its
held-out benchmark (``idkmesh.marginal_evidence_benchmark``):

1. does the marginal selector beat four simple selectors,
2. when does the marginal signal become too sample-unstable to use,
3. can it stop when every candidate is redundant, and
4. does its ranking survive held-out rows.

Those questions cannot be answered on the repository's data: it holds no
ground-truthed multi-verifier verdict matrix (E016 never measured an AI panel).
This module answers the part that **can** be answered without inventing
evidence. It builds verdict matrices from a *known* generative model, so the
true value of every candidate is computable, and it runs the real, unmodified
``benchmark()`` on them. Everything here is synthetic. It is a validation of the
measurement tool against a known truth, not a statement about real verifiers.

Generative model
----------------
A task has a hidden truth, ``accept`` or ``reject``, with probability one half.
A verifier's verdict equals the truth unless its *error indicator* is set, in
which case the verdict is flipped (errors are symmetric by construction; the
two-sided asymmetric case is **not** modelled). Error indicators come from three
kinds of verifier:

``base``
    errors are i.i.d. Bernoulli(``err``).
``copy``
    with probability ``weight`` the error indicator is copied from a reference
    verifier on the same task, otherwise it is an independent Bernoulli(``err``).
    ``weight = 1`` is an exact duplicate of the reference's verdict vector.
``complementary``
    errs with probability ``err_when_panel_right`` on tasks the current
    panel decides correctly and ``err_when_panel_wrong`` on tasks it decides
    incorrectly, so it is wrong mainly where the panel is right and right where
    the panel is wrong.

Ground truth for a candidate
----------------------------
For each regime one large *population* sample (``ORACLE_ROWS`` tasks, its own
seed stream, never shown to any selector) gives the true panel-error change
``oracle_delta = error(current) - error(current + candidate)`` under the same
tie rule the tool uses (``accept_votes > quorum * panel_size``). The oracle is a
Monte-Carlo estimate with a standard error of about ``0.002``; candidates whose
oracle delta lies within ``ORACLE_TOLERANCE`` of zero are called *redundant*,
which is a labelling convention of this study and not a property of the tool.

What is measured
----------------
For every regime and design-sample size ``n_design`` the unmodified
``benchmark()`` is run ``REPLICATES`` times with independent design and holdout
draws. For each of its five strategies the study records whether it selected a
candidate, the oracle delta of the selection (abstaining counts as ``0``, the
panel is left unchanged), regret against the best candidate, and how often the
selection was harmful (oracle delta below ``-ORACLE_TOLERANCE``) or useless
(``|oracle delta| <= ORACLE_TOLERANCE``).

Nothing here tunes a threshold: the selector's rule is the version already on
``main``. Eight regimes (panel size 3 or 4, shared-blind-spot weight 0.2 or
0.7, pool ``mixed`` or ``redundant_only``) and the grid of design sizes were
fixed before any full result was read, apart from one six-replicate look at a
single cell to time the run. The grid was then extended to larger design sizes
because that cell showed the selector almost never resolving. After the first
eight regimes were read, four more using the ``no_anti_informative`` pool were
added as a sensitivity check (the selector had picked the one worse-than-chance
candidate every time it resolved), and then four more using ``accuracy_trap``,
whose most accurate candidate is largely redundant with the panel, so that the
highest-accuracy baseline is not favoured by construction. All eight are marked
``post_hoc`` in the report.
No claim is made about real verifiers, real error structure or real corpora.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # allow ``python sim/e051_...py`` from the repo root
    sys.path.insert(0, str(ROOT))

from idkmesh import gate_audit  # noqa: E402
from idkmesh import marginal_evidence  # noqa: E402
from idkmesh import marginal_evidence_benchmark as meb  # noqa: E402

SCHEMA_ID = "e051-marginal-selector-sweep-v0.1"
EVIDENCE_CLASS = "synthetic"
AUTHORITY = "diagnostic_only"

ORACLE_ROWS = 40_000
ORACLE_TOLERANCE = 0.01
HOLDOUT_ROWS = 200
REPLICATES = 100
N_DESIGN = (20, 40, 80, 160, 320, 640, 1280)
BOOTSTRAP_REPLICATES = 100
BOOTSTRAP_CONFIDENCE = 0.9
QUORUM = 0.5
MEMBER_ERROR = 0.3

STRATEGIES = meb.STRATEGIES
MARGINAL = meb.STRATEGY_MARGINAL
BASELINES = tuple(name for name in STRATEGIES if name != MARGINAL)

PANEL_SIZES = (3, 4)
SHARED_WEIGHTS = {"low": 0.2, "high": 0.7}
POOLS = ("mixed", "redundant_only", "no_anti_informative", "accuracy_trap")
# Pools added after the first 8 regimes had been run and read. The first run
# showed the selector picking the one candidate that is worse than a coin flip;
# ``no_anti_informative`` removes that candidate to ask whether the pattern is
# an artefact of including it. ``accuracy_trap`` was added after that, because
# the original pools contain no candidate that is both the most accurate and
# largely redundant with the panel, which is the case in which a
# highest-accuracy rule is expected to be weakest; without it the comparison
# against that baseline would be tilted towards the baseline. Both are post-hoc
# sensitivity arms, recorded as such in the report, not preregistered arms.
POST_HOC_POOLS = ("no_anti_informative", "accuracy_trap")

# Candidate recipes. ``weight`` and ``err`` are described in the module docstring.
# The reference of every ``copy`` candidate is the first current member.
_CANDIDATES: dict[str, dict[str, Any]] = {
    "dup": {"kind": "copy", "weight": 1.0, "err": MEMBER_ERROR, "family": "f-ref"},
    "near_dup": {"kind": "copy", "weight": 0.9, "err": MEMBER_ERROR, "family": "f-near"},
    "indep_strong": {"kind": "base", "err": 0.15, "family": "f-strong"},
    "indep_equal": {"kind": "base", "err": MEMBER_ERROR, "family": "f-equal"},
    "indep_weak": {"kind": "base", "err": 0.45, "family": "f-weak"},
    "strong_redundant": {
        "kind": "copy",
        "weight": 0.7,
        "err": 0.02,
        "family": "f-strongred",
    },
    "harmful": {"kind": "base", "err": 0.6, "family": "f-harm"},
    "complementary": {
        "kind": "complementary",
        "err_when_panel_right": 0.3,
        "err_when_panel_wrong": 0.05,
        "family": "f-comp",
    },
}
POOL_MEMBERS = {
    "mixed": (
        "dup",
        "near_dup",
        "indep_strong",
        "indep_equal",
        "indep_weak",
        "harmful",
        "complementary",
    ),
    "redundant_only": ("dup", "near_dup", "indep_weak", "harmful"),
    "no_anti_informative": (
        "dup",
        "near_dup",
        "indep_strong",
        "indep_equal",
        "indep_weak",
        "complementary",
    ),
    "accuracy_trap": ("strong_redundant", "indep_equal", "complementary", "indep_weak"),
}


class SweepInputError(ValueError):
    """Raised when a sweep parameter is outside its documented range."""


def _rng(*parts: object) -> random.Random:
    """A ``random.Random`` seeded from a SHA-256 of the parts (stable across runs)."""
    material = "\x00".join(str(part) for part in parts).encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))


def regime_id(panel_size: int, shared: str, pool: str) -> str:
    return f"k{panel_size}-{shared}-{pool}"


def regimes() -> list[dict[str, Any]]:
    """All regimes, in a fixed order."""
    rows = []
    for panel_size in PANEL_SIZES:
        for shared in SHARED_WEIGHTS:
            for pool in POOLS:
                rows.append(
                    {
                        "id": regime_id(panel_size, shared, pool),
                        "panel_size": panel_size,
                        "member_shared_weight": SHARED_WEIGHTS[shared],
                        "shared": shared,
                        "pool": pool,
                        "post_hoc": pool in POST_HOC_POOLS,
                        "candidates": list(POOL_MEMBERS[pool]),
                    }
                )
    return rows


def current_ids(panel_size: int) -> list[str]:
    return [f"cur-{index + 1}" for index in range(panel_size)]


def candidate_ids(pool: str) -> list[str]:
    return [f"cand-{name}" for name in POOL_MEMBERS[pool]]


def _check_regime(panel_size: int, shared_weight: float, pool: str) -> None:
    if panel_size not in PANEL_SIZES:
        raise SweepInputError(f"panel_size must be one of {PANEL_SIZES}")
    if not (0.0 <= shared_weight <= 1.0):
        raise SweepInputError("member_shared_weight must be in [0, 1]")
    if pool not in POOL_MEMBERS:
        raise SweepInputError(f"pool must be one of {tuple(POOL_MEMBERS)}")


def sample_error_matrix(
    rng: random.Random,
    *,
    rows: int,
    panel_size: int,
    shared_weight: float,
    pool: str,
) -> tuple[list[bool], dict[str, list[bool]]]:
    """Draw ``rows`` tasks. Returns (truth_is_accept, error indicators by verifier id).

    Current members after the first copy the first member's error indicator with
    probability ``shared_weight`` (a shared-blind-spot model), otherwise err
    independently. This is one stylised dependence shape; E018 and the
    repository's dependence notes show real panels need not have it.
    """
    _check_regime(panel_size, shared_weight, pool)
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1:
        raise SweepInputError("rows must be a positive integer")
    truth = [rng.random() < 0.5 for _ in range(rows)]
    errors: dict[str, list[bool]] = {}
    members = current_ids(panel_size)
    first = [rng.random() < MEMBER_ERROR for _ in range(rows)]
    errors[members[0]] = first
    for member in members[1:]:
        errors[member] = [
            first[row] if rng.random() < shared_weight else rng.random() < MEMBER_ERROR
            for row in range(rows)
        ]

    def panel_wrong(row: int) -> bool:
        accepts = 0
        for member in members:
            says_accept = truth[row] != errors[member][row]
            accepts += 1 if says_accept else 0
        decision = accepts > QUORUM * len(members)
        return decision != truth[row]

    wrong = [panel_wrong(row) for row in range(rows)]
    for name in POOL_MEMBERS[pool]:
        recipe = _CANDIDATES[name]
        kind = recipe["kind"]
        if kind == "base":
            vec = [rng.random() < recipe["err"] for _ in range(rows)]
        elif kind == "copy":
            vec = [
                first[row] if rng.random() < recipe["weight"] else rng.random() < recipe["err"]
                for row in range(rows)
            ]
        else:
            vec = [
                rng.random()
                < (recipe["err_when_panel_wrong"] if wrong[row] else recipe["err_when_panel_right"])
                for row in range(rows)
            ]
        errors[f"cand-{name}"] = vec
    return truth, errors


def build_matrix(
    truth: Sequence[bool],
    errors: Mapping[str, Sequence[bool]],
    *,
    gate_id: str,
    prefix: str,
) -> dict[str, Any]:
    """Render a gate-audit verdict matrix (strict ``gate_audit`` input contract)."""
    ids = [f"{prefix}{index + 1:05d}" for index in range(len(truth))]
    verifiers = []
    for verifier_id in errors:
        verdicts = {
            ids[row]: "accept" if (truth[row] != errors[verifier_id][row]) else "reject"
            for row in range(len(truth))
        }
        verifiers.append({"id": verifier_id, "verdicts": verdicts})
    return {
        "gate_id": gate_id,
        "evidence_class": EVIDENCE_CLASS,
        "quorum": QUORUM,
        "candidates": [
            {"id": ids[row], "ground_truth": "accept" if truth[row] else "reject"}
            for row in range(len(truth))
        ],
        "verifiers": verifiers,
    }


def panel_error(
    truth: Sequence[bool],
    errors: Mapping[str, Sequence[bool]],
    verifier_ids: Sequence[str],
) -> float:
    """Fraction of tasks on which the panel's decision differs from the truth."""
    if not verifier_ids:
        raise SweepInputError("a panel needs at least one verifier")
    wrong = 0
    for row, is_accept in enumerate(truth):
        accepts = sum(1 for vid in verifier_ids if (is_accept != errors[vid][row]))
        decision = accepts > QUORUM * len(verifier_ids)
        wrong += 1 if decision != is_accept else 0
    return wrong / len(truth)


def oracle_profile(
    *,
    panel_size: int,
    shared_weight: float,
    pool: str,
    seed: int,
    rows: int = ORACLE_ROWS,
) -> dict[str, dict[str, float | None]]:
    """Population truth per candidate id, from one large never-selected sample.

    ``delta`` is the true ``error(current) - error(current + candidate)``.
    ``delta_effective_votes`` and ``standalone_accuracy`` are what the
    repository's own ``marginal_evidence.analyze`` reports on that same large
    sample with no bootstrap, i.e. the quantity the selector's design estimate
    converges to. Showing them next to ``delta`` is what makes a disagreement
    between the selector's criterion and the true panel-error change visible.
    """
    rng = _rng("e051-oracle", seed, panel_size, shared_weight, pool)
    truth, errors = sample_error_matrix(
        rng, rows=rows, panel_size=panel_size, shared_weight=shared_weight, pool=pool
    )
    members = current_ids(panel_size)
    base = panel_error(truth, errors, members)
    data = build_matrix(truth, errors, gate_id="oracle", prefix="o")
    with memoized_majority_error():
        report = marginal_evidence.analyze(
            data,
            current_verifier_ids=members,
            candidate_verifier_ids=candidate_ids(pool),
        )
    by_id = {row["id"]: row for row in report["candidates"]}
    profile: dict[str, dict[str, float | None]] = {}
    for cid in candidate_ids(pool):
        delta = base - panel_error(truth, errors, members + [cid])
        profile[cid] = {
            "delta": delta,
            "delta_effective_votes": by_id[cid]["delta_effective_votes"],
            "standalone_accuracy": by_id[cid]["standalone_accuracy"],
        }
    return profile


def oracle_deltas(**kwargs: Any) -> dict[str, float]:
    """``oracle_profile`` reduced to the true panel-error change per candidate."""
    return {cid: row["delta"] for cid, row in oracle_profile(**kwargs).items()}  # type: ignore[misc]


def classify(delta: float) -> str:
    if delta > ORACLE_TOLERANCE:
        return "helpful"
    if delta < -ORACLE_TOLERANCE:
        return "harmful"
    return "redundant"


def families_for(panel_size: int, pool: str) -> dict[str, str]:
    """Declared families. All current members share ``f-ref``.

    The exact duplicate is *declared* ``f-ref`` too, so a family heuristic
    flags it correctly. The near-duplicate and every other candidate declare a
    fresh family, so a family heuristic cannot see that ``near_dup`` is
    redundant: that is the failure mode the issue says family labels have.
    """
    families = {member: "f-ref" for member in current_ids(panel_size)}
    for name in POOL_MEMBERS[pool]:
        families[f"cand-{name}"] = _CANDIDATES[name]["family"]
    return families


@contextlib.contextmanager
def memoized_majority_error() -> Iterator[None]:
    """Memoize ``gate_audit.majority_error_independent`` for the duration.

    ``gate_audit.effective_n`` rebuilds a 101-entry table of binomial tail sums
    on every call and the bootstrap calls it thousands of times with a few
    hundred distinct accuracies. The memo returns the identical float the
    original returns for the same arguments, so reports are bit-for-bit
    unchanged (``tests/test_e051_marginal_selector_sweep.py`` checks this); it
    only removes repeated work. The original function is always restored.
    """
    original = gate_audit.majority_error_independent
    cached = functools.lru_cache(maxsize=None)(original)
    gate_audit.majority_error_independent = cached  # type: ignore[assignment]
    try:
        yield
    finally:
        gate_audit.majority_error_independent = original  # type: ignore[assignment]


def _benchmark_config(
    *, panel_size: int, pool: str, gate: str, n_design: int, replicate: int
) -> dict[str, Any]:
    return {
        "schema": meb.CONFIG_SCHEMA_ID,
        "benchmark_id": f"e051-{gate}-n{n_design}-r{replicate}",
        "design_matrix": "design.json",
        "holdout_matrix": "holdout.json",
        "current_verifier_ids": current_ids(panel_size),
        "candidate_verifier_ids": candidate_ids(pool),
        "verifier_families": families_for(panel_size, pool),
        "random_seed": replicate,
        "bootstrap": {
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": replicate + 1,
            "confidence_level": BOOTSTRAP_CONFIDENCE,
        },
    }


def draw_cell_matrices(
    *,
    panel_size: int,
    shared_weight: float,
    pool: str,
    n_design: int,
    replicate: int,
    seed: int,
    holdout_rows: int = HOLDOUT_ROWS,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Independent design and holdout verdict matrices for one replicate."""
    key = (seed, panel_size, shared_weight, pool, n_design, replicate)
    design_rng = _rng("e051-design", *key)
    holdout_rng = _rng("e051-holdout", *key)
    d_truth, d_err = sample_error_matrix(
        design_rng,
        rows=n_design,
        panel_size=panel_size,
        shared_weight=shared_weight,
        pool=pool,
    )
    h_truth, h_err = sample_error_matrix(
        holdout_rng,
        rows=holdout_rows,
        panel_size=panel_size,
        shared_weight=shared_weight,
        pool=pool,
    )
    gate = regime_id(panel_size, "w%g" % shared_weight, pool)
    return (
        build_matrix(d_truth, d_err, gate_id=gate, prefix="d"),
        build_matrix(h_truth, h_err, gate_id=gate, prefix="h"),
        gate,
    )


def _selections(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        selector["strategy"]: {
            "selected": selector["selected_verifier_id"],
            "reason_code": selector["reason_code"],
        }
        for selector in plan["selectors"]
    }


def run_cell(
    *,
    panel_size: int,
    shared_weight: float,
    pool: str,
    n_design: int,
    replicate: int,
    seed: int,
    full_benchmark: bool = False,
) -> dict[str, Any]:
    """One replicate. Selection is design-only, so by default only the plan runs.

    ``full_benchmark=True`` runs the whole held-out ``benchmark()`` and returns
    the same selections; the test suite asserts the two agree. The default skips
    the five holdout re-analyses because the study scores selections against the
    population oracle, not against a finite holdout.
    """
    design, holdout, gate = draw_cell_matrices(
        panel_size=panel_size,
        shared_weight=shared_weight,
        pool=pool,
        n_design=n_design,
        replicate=replicate,
        seed=seed,
    )
    config = _benchmark_config(
        panel_size=panel_size, pool=pool, gate=gate, n_design=n_design, replicate=replicate
    )
    if full_benchmark:
        report = meb.benchmark(design, holdout, config=config)
        plan = report["selection_plan"]
    else:
        plan = meb.build_selection_plan(design, config=config)
    return {"selections": _selections(plan)}


def summarize_cell(
    results: Sequence[Mapping[str, Any]], oracle: Mapping[str, float]
) -> dict[str, Any]:
    """Aggregate the replicates of one (regime, n_design) cell against the oracle.

    A strategy that does not select counts as value ``0`` (the panel is left
    as it is). ``regret`` is measured against the best candidate in the pool.
    """
    if not results:
        raise SweepInputError("no replicates to summarize")
    best = max(oracle.values())
    helpful_exists = any(classify(value) == "helpful" for value in oracle.values())
    out: dict[str, Any] = {}
    for strategy in STRATEGIES:
        values: list[float] = []
        counts: dict[str, int] = {}
        reasons: dict[str, int] = {}
        resolved = harmful = redundant = helpful = near_best = 0
        for result in results:
            entry = result["selections"][strategy]
            chosen = entry["selected"]
            if chosen is None:
                values.append(0.0)
                reasons[entry["reason_code"]] = reasons.get(entry["reason_code"], 0) + 1
                continue
            resolved += 1
            value = oracle[chosen]
            values.append(value)
            counts[chosen] = counts.get(chosen, 0) + 1
            label = classify(value)
            harmful += label == "harmful"
            redundant += label == "redundant"
            helpful += label == "helpful"
            near_best += value >= best - ORACLE_TOLERANCE
        n = len(values)
        mean = math.fsum(values) / n
        out[strategy] = {
            "replicates": n,
            "selected": resolved,
            "abstained": n - resolved,
            "selected_helpful": helpful,
            "selected_redundant": redundant,
            "selected_harmful": harmful,
            "selected_near_best": near_best,
            "mean_oracle_delta_abstain_as_zero": mean,
            "mean_regret_abstain_as_zero": best - mean,
            "selected_counts": dict(sorted(counts.items())),
            "abstain_reason_counts": dict(sorted(reasons.items())),
        }
    return {
        "replicates": len(results),
        "any_helpful_candidate": helpful_exists,
        "strategies": out,
        "marginal_vs_baselines": {
            baseline: paired_difference(results, oracle, MARGINAL, baseline)
            for baseline in BASELINES
        },
    }


def paired_difference(
    results: Sequence[Mapping[str, Any]],
    oracle: Mapping[str, float],
    a: str,
    b: str,
) -> dict[str, float]:
    """Paired mean of ``oracle value(a) - oracle value(b)`` across replicates.

    The replicates are independent draws, so ``se`` is the usual standard error
    of a mean of independent differences. It is descriptive; no p-value or
    significance claim is derived from it.
    """
    diffs = []
    for result in results:
        va = result["selections"][a]["selected"]
        vb = result["selections"][b]["selected"]
        diffs.append((oracle[va] if va else 0.0) - (oracle[vb] if vb else 0.0))
    n = len(diffs)
    mean = math.fsum(diffs) / n
    var = math.fsum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
    return {"mean": mean, "se": math.sqrt(var / n), "n": n}


def _job(payload: dict[str, Any]) -> dict[str, Any]:
    """All replicates of one (regime, n_design) cell, in one process."""
    with memoized_majority_error():
        results = [
            run_cell(
                panel_size=payload["panel_size"],
                shared_weight=payload["shared_weight"],
                pool=payload["pool"],
                n_design=payload["n_design"],
                replicate=replicate,
                seed=payload["seed"],
            )
            for replicate in range(payload["replicates"])
        ]
    return {
        "regime": payload["regime"],
        "n_design": payload["n_design"],
        "results": results,
    }


def _canonical_digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sweep(
    *,
    seed: int = 1,
    replicates: int = REPLICATES,
    n_design: Sequence[int] = N_DESIGN,
    regime_ids: Sequence[str] | None = None,
    workers: int = 1,
    oracle_rows: int = ORACLE_ROWS,
) -> dict[str, Any]:
    """Run the study and return a deterministic report (independent of ``workers``)."""
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1:
        raise SweepInputError("replicates must be a positive integer")
    if workers < 1:
        raise SweepInputError("workers must be >= 1")
    if isinstance(oracle_rows, bool) or not isinstance(oracle_rows, int) or oracle_rows < 100:
        raise SweepInputError("oracle_rows must be an integer >= 100")
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 5 for n in n_design):
        raise SweepInputError("every n_design must be an integer >= 5")
    selected = [r for r in regimes() if regime_ids is None or r["id"] in regime_ids]
    if regime_ids is not None and len(selected) != len(set(regime_ids)):
        raise SweepInputError("unknown regime id requested")
    profile_by_regime = {
        r["id"]: oracle_profile(
            panel_size=r["panel_size"],
            shared_weight=r["member_shared_weight"],
            pool=r["pool"],
            seed=seed,
            rows=oracle_rows,
        )
        for r in selected
    }
    oracle_by_regime = {
        regime: {cid: row["delta"] for cid, row in profile.items()}
        for regime, profile in profile_by_regime.items()
    }
    payloads = [
        {
            "regime": r["id"],
            "panel_size": r["panel_size"],
            "shared_weight": r["member_shared_weight"],
            "pool": r["pool"],
            "n_design": n,
            "seed": seed,
            "replicates": replicates,
        }
        for r in selected
        for n in n_design
    ]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs = list(pool.map(_job, payloads))
    else:
        jobs = [_job(payload) for payload in payloads]

    regime_reports = []
    for r in selected:
        oracle = oracle_by_regime[r["id"]]
        cells = []
        for job in jobs:
            if job["regime"] != r["id"]:
                continue
            cells.append(
                {
                    "n_design": job["n_design"],
                    **summarize_cell(job["results"], oracle),
                }
            )
        regime_reports.append(
            {
                **r,
                "oracle": {
                    cid: {**profile_by_regime[r["id"]][cid], "label": classify(value)}
                    for cid, value in oracle.items()
                },
                "cells": cells,
            }
        )
    body = {
        "schema": SCHEMA_ID,
        "evidence_class": EVIDENCE_CLASS,
        "authority": AUTHORITY,
        "selection_rule_version": meb.SELECTION_RULE_VERSION,
        "config": {
            "seed": seed,
            "replicates": replicates,
            "n_design": list(n_design),
            "holdout_rows": HOLDOUT_ROWS,
            "oracle_rows": oracle_rows,
            "oracle_tolerance": ORACLE_TOLERANCE,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_confidence_level": BOOTSTRAP_CONFIDENCE,
            "quorum": QUORUM,
            "member_error": MEMBER_ERROR,
            "candidate_recipes": _CANDIDATES,
        },
        "regimes": regime_reports,
        "limitations": [
            "synthetic: every verdict is drawn from the stated generative model",
            "symmetric errors only; one-sided (false-accept vs false-reject) error "
            "structure is not modelled",
            "one dependence shape (copy-the-first-member); real dependence differs",
            "the oracle is a Monte-Carlo estimate, not an analytic value",
            "descriptive only: no significance claim, no threshold was tuned, and "
            "nothing here supports promoting the selector",
        ],
    }
    return {**body, "digest_sha256": _canonical_digest(body)}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--n-design", type=int, nargs="+", default=list(N_DESIGN))
    parser.add_argument("--regime", action="append", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--oracle-rows", type=int, default=ORACLE_ROWS)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = sweep(
            seed=args.seed,
            replicates=args.replicates,
            n_design=args.n_design,
            regime_ids=args.regime,
            workers=args.workers,
            oracle_rows=args.oracle_rows,
        )
    except SweepInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
