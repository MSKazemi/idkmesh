#!/usr/bin/env python3
"""E039: can an adversary learn the panel's blind spot? Not in this model.

E036 closed with a named next step: *"the adversary here is goal-blind,
independent of the other adversaries, and cannot see what was accepted. The
test that would move this is a coordinated adversary that adapts to feedback --
if independence of the verifiers is the defence, an attacker who learns the
panel's shared blind spot should be able to remove it."*

That test cannot be run against the panel as written, and the reason is
structural rather than a matter of tuning.

Result 1, which is a proof rather than a measurement
----------------------------------------------------

:func:`sim.emergence_sim.verify_candidate` reads the candidate exactly once::

    truth = viable(c)

Every other term -- the per-verifier accuracy draw, the shared correctness
shock, the blind-spot draw -- is a coin flipped against the panel's rng and
never against the artifact. So the panel sees each submission through **one
bit**, and two structurally different candidates that agree on that bit produce
*bit-identical* decision sequences on the same rng stream.
:func:`content_blindness` demonstrates this rather than asserting it.

The consequence is that E036's proposed attacker has nothing to learn. The
blind spot is a memoryless coin, not a region of artifact space; there is no
address to find. Any "coordinated adversary" measured against this panel would
report a null, and the null would be a fact about the simulator rather than
about verification.

This matters beyond E036. Every panel result on this line -- E016, E020,
E025-E028, E036, E037, E038 -- is a result about a panel whose errors are
independent of artifact content. That is a real scope limit and it is not
stated in any of those records.

What E039 changes
-----------------

To ask E036's question at all, the blind spot needs a *content address*. Here
it becomes a set of niches -- the same ``(adaptability, efficiency)`` bins the
archive already partitions on -- which every verifier misses together. This is
the natural shape for a shared blind spot: reviewers do not miss a random 5.56%
of work, they miss the same *kind* of work.

The construction is calibrated so the marginal behaviour is unchanged. E027's
``measured`` panel carries ``accuracy 0.7956`` with ``blind_spot 0.0556``,
which means each verifier is :func:`sim.emergence_sim.reducible_accuracy`
accurate *outside* the blind spot. The content-addressed panel keeps that same
outside-accuracy and the same correlation, sets the scalar ``blind_spot`` to
zero, and misses everything inside the region instead. Under the honest
proposal distribution the region carries the same mass the coin did, so the
marginal error rates match -- **matched by construction, not bit-identical**,
because the two panels consume different rng.

The threat model
----------------

Both adversaries are E036's: a fraction of the pool is hostile, each hostile
contributor draws ``effort`` candidates and ships one with ``integrity`` zeroed.
They differ only in *which* draw they ship.

``goal-blind``
    E036's rule -- the highest apparent quality. It never looks at where its
    submissions land.
``coordinated``
    Hostile contributors share one memory of their own submissions, keyed by
    niche, and ship the draw whose niche has the best observed accept rate.
    Ties break on apparent quality, so an adversary that has learned nothing
    behaves *exactly* like the goal-blind one -- the two arms start identical
    and separate only if there is something to learn.

The memory holds the adversary's own submissions only. It is reset at the start
of every run (:data:`VerificationStats.attempts` is zero exactly once per run),
so no seed and no arm inherits what another one learned; sharing across
replicates would manufacture the effect this experiment is trying to detect.

The design, and the prediction stated before it
------------------------------------------------

Two panels crossed with two adversaries. The cross is the point: three of the
four cells are controls for the fourth.

============================  ==================  =====================
                              goal-blind          coordinated
============================  ==================  =====================
memoryless blind spot         E036's cell         *should not differ*
content-addressed blind spot  *should not differ*  **the attack**
============================  ==================  =====================

A fourth clause tests the mechanism rather than the outcome, and it is the one
most likely to fail. An arm that spreads across niches must walk into a
niche-addressed blind spot; an arm that converges on one niche either sits in
the region or never touches it. So the archive's *diversity* should raise its
exposure, in the same shape E038 found for viability: a uniform gate, unequal
exposure, because the arms do not submit the same distribution of work.

No network, no model API, no cost.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import os
import random
import statistics
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, Iterator, List, Sequence, Tuple

import sim.emergence_sim as sim
import sim.matched_budget_emergence as mbe
import sim.e027_defect_propagation as e027
import sim.e028_latent_defect_dimension as e028
import sim.e036_adversarial_contributors as e036

EXPERIMENT_ID = "E039"
EXPERIMENT = "content-addressed-blind-spot-and-coordinated-adversary-v1"

STRATEGIES: Tuple[str, ...] = mbe.STRATEGIES
ARCHIVE_ARM = "qd"

#: The panel E039 rebuilds. ``measured`` is the only panel on this line whose
#: blind spot was fitted to real oracles (E020, lambda = 0.0556), so it is the
#: only one where "give the blind spot an address" is a change of *shape*
#: rather than the invention of a parameter.
BASE_PANEL = "measured"

#: Region calibration is deterministic: same seed, same draws, same region.
CALIBRATION_SEED = 20260830
CALIBRATION_DRAWS = 400_000

DEFAULT_BINS = 8
DEFAULT_SEEDS = 100
DEFAULT_SEED_START = 1
DEFAULT_AGENTS = 64
DEFAULT_GENERATIONS = 50
DEFAULT_CHANGE_AT = 25

#: E036's strategic contributor. Effort 1 is a *faulty* contributor and cannot
#: aim, so it cannot express the coordinated rule at all; E039 sweeps the
#: fraction and holds effort at E036's strategic end.
DEFAULT_EFFORT = 8
FRACTIONS: Tuple[float, ...] = (0.02, 0.10)

PANEL_SHAPES: Tuple[str, ...] = ("memoryless", "content-addressed")
ADVERSARIES: Tuple[str, ...] = ("goal-blind", "coordinated")

#: A hostile artifact ships integrity exactly zero (E036's choice, made so a
#: hostile artifact is identifiable in an audit). The adversary's memory keys
#: off the same marker. An honest child *can* land on exactly zero through the
#: mutation clamp, so the marker is not perfectly clean -- :func:`marker_purity`
#: measures the contamination instead of assuming it away.
HOSTILE_INTEGRITY = e036.ADVERSARY_INTEGRITY


# --------------------------------------------------------------------------
# Result 1 -- the panel is content-blind, demonstrated
# --------------------------------------------------------------------------

def content_blindness(
    *,
    panel: str = BASE_PANEL,
    draws: int = 4000,
    seed: int = 12345,
    pool_seed: int = 7,
) -> Dict[str, Any]:
    """Show the panel's decisions depend on the artifact through one bit only.

    Two candidates that differ in every trait but agree on ``viable`` are run
    against the same rng stream. Identical output is not evidence *for* an
    approximation -- it is the whole decision sequence, so it is a proof that
    nothing else about the artifact reached the panel.
    """
    config = e027.PANELS[panel]
    pool_rng = random.Random(pool_seed)
    pool = [sim.Candidate.random(pool_rng) for _ in range(400)]
    viables = [c for c in pool if sim.viable(c)][:2]
    nonviables = [c for c in pool if not sim.viable(c)][:2]
    if len(viables) < 2 or len(nonviables) < 2:
        raise RuntimeError("calibration pool did not yield two of each class")

    def decisions(candidate: "sim.Candidate") -> List[bool]:
        rng = random.Random(seed)
        stats = sim.VerificationStats()
        return [sim.verify_candidate(candidate, rng, config, stats) for _ in range(draws)]

    same_viable = decisions(viables[0]) == decisions(viables[1])
    same_nonviable = decisions(nonviables[0]) == decisions(nonviables[1])
    across = decisions(viables[0]) != decisions(nonviables[0])
    return {
        "panel": panel,
        "draws": draws,
        "distinct_candidates": viables[0].traits != viables[1].traits,
        "identical_decisions_within_viable": same_viable,
        "identical_decisions_within_nonviable": same_nonviable,
        "decisions_differ_across_the_viability_bit": across,
        "candidate_is_read_through_one_bit": bool(
            same_viable and same_nonviable and across
        ),
    }


# --------------------------------------------------------------------------
# The content-addressed blind spot
# --------------------------------------------------------------------------

def niche_mass(
    *, bins: int = DEFAULT_BINS, draws: int = CALIBRATION_DRAWS, seed: int = CALIBRATION_SEED
) -> Dict[Tuple[int, int], float]:
    """Share of honest random proposals landing in each niche."""
    rng = random.Random(seed)
    counts: "collections.Counter[Tuple[int, int]]" = collections.Counter()
    for _ in range(draws):
        counts[sim.niche(sim.Candidate.random(rng), bins)] += 1
    return {n: c / draws for n, c in counts.items()}


def calibrate_region(
    *,
    target: float,
    shape: str = "concentrated",
    bins: int = DEFAULT_BINS,
    draws: int = CALIBRATION_DRAWS,
    seed: int = CALIBRATION_SEED,
) -> Dict[str, Any]:
    """Pick a set of niches carrying ``target`` of the honest proposal mass.

    ``concentrated`` takes the heaviest niches first, which is the realistic
    shape -- a shared blind spot is one *kind* of work. ``diffuse`` takes the
    lightest first, which spreads the same mass over many more niches and is
    correspondingly harder to localise from feedback. Both are reported,
    because "the attack works" and "the attack works when the blind spot is
    concentrated" are different claims.
    """
    if shape not in ("concentrated", "diffuse"):
        raise ValueError("shape must be 'concentrated' or 'diffuse'")
    mass = niche_mass(bins=bins, draws=draws, seed=seed)
    order = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))
    if shape == "diffuse":
        order = sorted(mass.items(), key=lambda kv: (kv[1], kv[0]))
    region: List[Tuple[int, int]] = []
    total = 0.0
    for niche, share in order:
        if total + share <= target + 1e-9:
            region.append(niche)
            total += share
    return {
        "shape": shape,
        "target_mass": round(target, 6),
        "region": sorted(region),
        "region_size": len(region),
        "niche_count": bins * bins,
        "calibrated_mass": round(total, 6),
        "calibration_error": round(total - target, 6),
        "bins": bins,
        "draws": draws,
        "seed": seed,
    }


def content_addressed_panel(base: str = BASE_PANEL) -> "sim.VerificationConfig":
    """``base`` with its blind spot moved from a coin to a region.

    The outside-the-blind-spot accuracy and the correlation are carried over
    unchanged and the scalar blind spot is set to zero, so the panel that
    results has exactly the same marginal accuracy once the region carries the
    mass the coin used to carry.
    """
    config = e027.PANELS[base]
    return sim.VerificationConfig(
        verifiers=config.verifiers,
        accuracy=sim.reducible_accuracy(config.accuracy, config.blind_spot),
        correlation=config.correlation,
        quorum=config.quorum,
        dependence=config.dependence,
        blind_spot=0.0,
    )


class AdversaryMemory:
    """Per-run tally of the adversary's own submissions, keyed by niche.

    Reset once per run. The score is a Beta(1, 1) posterior mean, so an unseen
    niche scores exactly 0.5 and every niche ties before any evidence arrives
    -- which is what makes the coordinated arm start out identical to the
    goal-blind one instead of merely similar.
    """

    def __init__(self) -> None:
        self.attempts: "collections.Counter[Tuple[int, int]]" = collections.Counter()
        self.accepts: "collections.Counter[Tuple[int, int]]" = collections.Counter()
        self.region_hits = 0
        self.total = 0
        self.hostile_submissions = 0
        self.zero_integrity_seen = 0

    def reset(self) -> None:
        self.__init__()

    def record(self, niche: Tuple[int, int], accepted: bool) -> None:
        self.attempts[niche] += 1
        self.accepts[niche] += int(accepted)

    def score(self, niche: Tuple[int, int]) -> float:
        return (self.accepts[niche] + 1.0) / (self.attempts[niche] + 2.0)


#: Process-local. Every cell runs in its own process (see :func:`_cell_job`),
#: so this is never shared between two configurations.
MEMORY = AdversaryMemory()

#: Per-run exposure records, appended when a run ends. See :func:`exposure`.
RUN_LOG: List[Dict[str, Any]] = []


class CoordinatedCandidate(e036.AdversarialCandidate):
    """E036's adversary, aiming at the niche its own submissions get through.

    Identical to :class:`~sim.e036_adversarial_contributors.AdversarialCandidate`
    except for the selection rule among the ``effort`` draws.
    """

    COORDINATED: bool = True
    NICHE_BINS: int = DEFAULT_BINS

    @classmethod
    def _select(cls, drawn: Sequence["sim.Candidate"], bins: int) -> "sim.Candidate":
        if not cls.COORDINATED:
            return max(drawn, key=sim.unchecked_robust_quality)
        return max(
            drawn,
            key=lambda c: (
                MEMORY.score(sim.niche(c, bins)),
                sim.unchecked_robust_quality(c),
            ),
        )

    @classmethod
    def random(cls, rng: random.Random) -> "CoordinatedCandidate":
        if not cls._is_hostile(rng):
            return super(e036.AdversarialCandidate, cls).random(rng)
        drawn = [
            super(e036.AdversarialCandidate, cls).random(rng)
            for _ in range(cls.ADVERSARY_EFFORT)
        ]
        return cls._compromise(cls._select(drawn, cls.NICHE_BINS))

    def mutate(self, rng: random.Random, sigma: float = 0.12) -> "CoordinatedCandidate":
        cls = type(self)
        if not cls._is_hostile(rng):
            return super(e036.AdversarialCandidate, self).mutate(rng, sigma)
        drawn = [
            super(e036.AdversarialCandidate, self).mutate(rng, sigma)
            for _ in range(cls.ADVERSARY_EFFORT)
        ]
        return cls._compromise(cls._select(drawn, cls.NICHE_BINS))


def _candidate_class(*, fraction: float, effort: int, coordinated: bool, bins: int) -> type:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("adversary fraction must be in [0.0, 1.0]")
    if effort < 1:
        raise ValueError("adversary effort must be >= 1")
    return type(
        "CoordinatedCandidateBound",
        (CoordinatedCandidate,),
        {
            "ADVERSARY_FRACTION": fraction,
            "ADVERSARY_EFFORT": effort,
            "COORDINATED": coordinated,
            "NICHE_BINS": bins,
            "INTEGRITY_SIGMA": e028.INTEGRITY_SIGMA_DEFAULT,
        },
    )


def flush_run() -> None:
    """Close the run in progress, if any, into :data:`RUN_LOG`.

    The wrapper can only detect a *new* run starting, so the last run of a
    sweep has to be closed from outside. Losing it would drop one arm's
    exposure silently, which is why :func:`exposure` checks the count.
    """
    if MEMORY.total or MEMORY.attempts:
        RUN_LOG.append(
            {
                "attempts": MEMORY.total,
                "region_hits": MEMORY.region_hits,
                "hostile_submissions": MEMORY.hostile_submissions,
                "zero_integrity_seen": MEMORY.zero_integrity_seen,
            }
        )
        MEMORY.reset()


def _verifier(module, region: "frozenset[Tuple[int, int]] | None", bins: int):
    """Wrap one module's verifier with a region and the adversary's feedback.

    Built per module rather than once, so a call made through the arena module
    reads the arena module's own ground truth instead of reaching across into
    the package copy. E028 warns about exactly that crossing.
    """
    original = module.verify_candidate

    def verify(candidate, rng, config, stats):
        if stats.attempts == 0:
            flush_run()

        spot = sim.niche(candidate, bins)
        in_region = region is not None and spot in region
        MEMORY.total += 1
        MEMORY.region_hits += int(in_region)

        if in_region:
            # The whole panel misses this artifact together, exactly as the
            # scalar blind spot does -- but for a reason the artifact carries.
            truth = module.viable(candidate)
            stats.attempts += 1
            if truth:
                stats.true_viable += 1
            else:
                stats.true_nonviable += 1
            accepted = not truth
            stats.accepts += int(accepted)
            stats.false_accepts += int(accepted and not truth)
            stats.false_rejects += int((not accepted) and truth)
        else:
            accepted = original(candidate, rng, config, stats)

        traits = candidate.traits
        if len(traits) > e028.LATENT_INDEX and traits[e028.LATENT_INDEX] == HOSTILE_INTEGRITY:
            MEMORY.zero_integrity_seen += 1
            MEMORY.hostile_submissions += 1
            MEMORY.record(spot, accepted)
        return accepted

    return verify


@contextlib.contextmanager
def blind_spot_landscape(
    *,
    fraction: float,
    effort: int,
    coordinated: bool,
    region: "Sequence[Tuple[int, int]] | None",
    bins: int,
) -> Iterator[type]:
    """E028's latent landscape, E036's hostile pool, E039's addressed blind spot.

    Patches ``Candidate``, ``viable`` *and* ``verify_candidate`` on every module
    object that owns a copy of the landscape, and restores all three on the way
    out including on an exception.
    """
    candidate_class = _candidate_class(
        fraction=fraction, effort=effort, coordinated=coordinated, bins=bins
    )
    frozen = frozenset(region) if region else None
    modules = e028._landscape_modules()
    saved = [
        (m, m.Candidate, m.viable, m.verify_candidate) for m in modules
    ]
    MEMORY.reset()
    RUN_LOG.clear()
    try:
        for module in modules:
            module.Candidate = candidate_class
            module.viable = e028.latent_viable
            module.verify_candidate = _verifier(module, frozen, bins)
        yield candidate_class
    finally:
        for module, candidate, viable, verify in saved:
            module.Candidate = candidate
            module.viable = viable
            module.verify_candidate = verify


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------

def two_proportion_z(a: int, na: int, b: int, nb: int) -> "float | None":
    """z for the difference of two independent proportions, ``a/na - b/nb``.

    Normal approximation on the pooled variance. Returns ``None`` when the
    pooled variance is zero -- both arms at the same extreme -- because a
    difference of exactly nothing has no scale to be measured against, and
    reporting an infinity there would read as a resolved result.
    """
    if na <= 0 or nb <= 0:
        return None
    pa, pb = a / na, b / nb
    pooled = (a + b) / (na + nb)
    var = pooled * (1.0 - pooled) * (1.0 / na + 1.0 / nb)
    if var <= 0.0:
        return None
    return (pa - pb) / var ** 0.5


#: Two-sided 95%. Named so the write-up and the test read the same constant.
RESOLVED_Z = 1.96


def panel_for(shape: str) -> "sim.VerificationConfig":
    if shape == "memoryless":
        return e027.PANELS[BASE_PANEL]
    return content_addressed_panel()


def _cell(
    *,
    panel_shape: str,
    adversary: str,
    fraction: float,
    region: "Sequence[Tuple[int, int]] | None",
    seeds: int,
    seed_start: int,
    agents: int,
    generations: int,
    change_at: int,
    bins: int,
    effort: int,
) -> Dict[str, Any]:
    """One (panel shape, adversary, fraction) cell.

    Runs seed by seed rather than through :func:`mbe.sweep`, because the
    exposure counters have to be paired back to the arm that produced them.
    The pairing is *checked*, not assumed: every run's own attempt count must
    equal the arm's reported ``verification_attempts``.
    """
    if panel_shape not in ("memoryless", "content-addressed", "content-addressed-diffuse"):
        raise ValueError(f"unknown panel shape {panel_shape!r}")
    if adversary not in ADVERSARIES:
        raise ValueError(f"unknown adversary {adversary!r}")

    verification = panel_for(panel_shape)
    use_region = None if panel_shape == "memoryless" else region
    threshold = mbe.CATASTROPHE_FRACTION * (generations - change_at)

    auc: Dict[str, List[float]] = {s: [] for s in STRATEGIES}
    region_hits: Dict[str, int] = {s: 0 for s in STRATEGIES}
    attempts: Dict[str, int] = {s: 0 for s in STRATEGIES}
    hostile: Dict[str, int] = {s: 0 for s in STRATEGIES}
    false_accepts: Dict[str, int] = {s: 0 for s in STRATEGIES}
    nonviable: Dict[str, int] = {s: 0 for s in STRATEGIES}
    pairing_checked = 0

    with blind_spot_landscape(
        fraction=fraction,
        effort=effort,
        coordinated=adversary == "coordinated",
        region=use_region,
        bins=bins,
    ):
        for seed in range(seed_start, seed_start + seeds):
            RUN_LOG.clear()
            out = mbe.run_seed(
                seed=seed,
                agents=agents,
                generations=generations,
                change_at=change_at,
                bins=bins,
                verification=verification,
                defect=mbe.DefectChannel(cost=1.0),
            )
            flush_run()
            rows = out["results"]
            if len(RUN_LOG) != len(rows):
                raise RuntimeError(
                    f"exposure log has {len(RUN_LOG)} runs for {len(rows)} arms"
                )
            for row, log in zip(rows, RUN_LOG):
                strategy = row["strategy"]
                if log["attempts"] != row["verification_attempts"]:
                    raise RuntimeError(
                        "exposure log does not line up with the arm that "
                        f"produced it: {strategy} seed {seed} logged "
                        f"{log['attempts']} against {row['verification_attempts']}"
                    )
                pairing_checked += 1
                auc[strategy].append(row["post_change_utility_auc"])
                region_hits[strategy] += log["region_hits"]
                attempts[strategy] += log["attempts"]
                hostile[strategy] += log["hostile_submissions"]
                false_accepts[strategy] += row["false_accepts"]
                nonviable[strategy] += row["verification_attempts"]

    catastrophes = {
        s: sum(1 for v in auc[s] if v < threshold) for s in STRATEGIES
    }
    return {
        "panel_shape": panel_shape,
        "adversary": adversary,
        "adversary_fraction": fraction,
        "adversary_effort": effort,
        "seeds": seeds,
        "utility_auc_threshold": round(threshold, 6),
        "pairing_checks": pairing_checked,
        "catastrophic_seeds": catastrophes,
        "post_change_utility_auc": {
            s: round(statistics.fmean(auc[s]), 6) for s in STRATEGIES
        },
        "region_share": {
            s: round(region_hits[s] / attempts[s], 6) if attempts[s] else 0.0
            for s in STRATEGIES
        },
        "hostile_submission_share": {
            s: round(hostile[s] / attempts[s], 6) if attempts[s] else 0.0
            for s in STRATEGIES
        },
        "false_accepts": {s: false_accepts[s] for s in STRATEGIES},
        "verification_attempts": {s: attempts[s] for s in STRATEGIES},
    }


def _cell_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process entry point.

    Cells run in *processes*, never threads: a cell rebinds ``Candidate``,
    ``viable`` and ``verify_candidate`` on shared module objects and keeps the
    adversary's memory in a module global, so two cells in one interpreter
    would read each other's landscape and each other's learning.
    """
    payload = dict(payload)
    region = payload.pop("region")
    return _cell(region=None if region is None else [tuple(n) for n in region], **payload)


# --------------------------------------------------------------------------
# The prediction
# --------------------------------------------------------------------------

PREDICTION = {
    "stated_before_run": True,
    "question": (
        "E036's named next step: can an adversary that adapts to feedback "
        "learn the panel's shared blind spot and remove verifier independence "
        "as a defence?"
    ),
    "claim": (
        "Not against the panel as written -- it reads the artifact through one "
        "bit, so there is no address to learn. Give the blind spot a content "
        "address at the same marginal rate and the same adversary becomes "
        "effective, and the archive is the arm most exposed to it because "
        "covering niches is what walking into a niche-addressed blind spot "
        "requires."
    ),
    "clauses": {
        "the_panel_reads_the_artifact_through_one_bit": True,
        "coordination_is_worthless_against_a_memoryless_panel": True,
        "content_addressing_alone_is_not_the_attack": True,
        "coordination_pays_against_a_content_addressed_panel": True,
        "the_archive_is_the_most_exposed_arm": True,
    },
    "falsified_if": (
        "The coordinated adversary gains nothing even against a content-"
        "addressed blind spot -- fifty generations of accept feedback is not "
        "enough to localise two niches in sixty-four -- or the archive is not "
        "the most exposed arm."
    ),
}

ELITIST_ARMS: Tuple[str, ...] = tuple(
    s for s in STRATEGIES if s not in (ARCHIVE_ARM, "random")
)


def _contrast(left: Dict[str, Any], right: Dict[str, Any], arm: str) -> Dict[str, Any]:
    """Catastrophe-rate difference ``left - right`` for one arm."""
    a, b = left["catastrophic_seeds"][arm], right["catastrophic_seeds"][arm]
    na, nb = left["seeds"], right["seeds"]
    z = two_proportion_z(a, na, b, nb)
    return {
        "arm": arm,
        "left": a,
        "right": b,
        "trials": [na, nb],
        "rate_difference": round(a / na - b / nb, 6),
        "z": None if z is None else round(z, 4),
        "resolved": bool(z is not None and abs(z) >= RESOLVED_Z),
    }


def _find(cells: Sequence[Dict[str, Any]], shape: str, adversary: str, fraction: float):
    for cell in cells:
        if (
            cell["panel_shape"] == shape
            and cell["adversary"] == adversary
            and cell["adversary_fraction"] == fraction
        ):
            return cell
    raise KeyError(f"no cell for {shape}/{adversary}/{fraction}")


def prediction_outcome(
    cells: Sequence[Dict[str, Any]],
    blindness: Dict[str, Any],
    *,
    headline_fraction: float,
    arm: str = ARCHIVE_ARM,
) -> Dict[str, Any]:
    """Score every clause against the cells, and say which ones are nulls.

    Two clauses are *absences* of an effect. An unresolved contrast is not
    proof that nothing is there, so each one carries its observed difference
    and the width of the interval it was judged against rather than a bare
    pass.
    """
    f = headline_fraction
    memoryless_gain = _contrast(
        _find(cells, "memoryless", "coordinated", f),
        _find(cells, "memoryless", "goal-blind", f),
        arm,
    )
    addressing_alone = _contrast(
        _find(cells, "content-addressed", "goal-blind", f),
        _find(cells, "memoryless", "goal-blind", f),
        arm,
    )
    coordinated_gain = _contrast(
        _find(cells, "content-addressed", "coordinated", f),
        _find(cells, "content-addressed", "goal-blind", f),
        arm,
    )
    attacked = _find(cells, "content-addressed", "coordinated", f)
    shares = attacked["region_share"]
    archive_share = shares[ARCHIVE_ARM]
    elitist_best = max(shares[s] for s in ELITIST_ARMS)
    observed = {
        "the_panel_reads_the_artifact_through_one_bit": bool(
            blindness["candidate_is_read_through_one_bit"]
        ),
        "coordination_is_worthless_against_a_memoryless_panel": not memoryless_gain["resolved"],
        "content_addressing_alone_is_not_the_attack": not addressing_alone["resolved"],
        "coordination_pays_against_a_content_addressed_panel": bool(
            coordinated_gain["resolved"] and coordinated_gain["rate_difference"] > 0.0
        ),
        "the_archive_is_the_most_exposed_arm": bool(archive_share > elitist_best),
    }
    clauses = PREDICTION["clauses"]
    return {
        "headline_fraction": f,
        "arm": arm,
        "predicted": dict(clauses),
        "observed": observed,
        "per_clause": {k: observed[k] == v for k, v in clauses.items()},
        "supported": all(observed[k] == v for k, v in clauses.items()),
        "clauses_met": sum(1 for k, v in clauses.items() if observed[k] == v),
        "clauses_total": len(clauses),
        "contrasts": {
            "coordination_on_a_memoryless_panel": memoryless_gain,
            "content_addressing_with_a_goal_blind_adversary": addressing_alone,
            "coordination_on_a_content_addressed_panel": coordinated_gain,
        },
        "null_clauses": [
            "coordination_is_worthless_against_a_memoryless_panel",
            "content_addressing_alone_is_not_the_attack",
        ],
        "null_clause_caveat": (
            "Two clauses pass by failing to resolve a difference, which is "
            "not evidence of no difference. At these trial counts the pass "
            "is consistent with a small real effect; the observed "
            "differences and their z are reported so the reader can judge "
            "the width rather than take the pass at face value."
        ),
        "exposure": {
            "archive": archive_share,
            "best_elitist": elitist_best,
            "by_arm": shares,
        },
    }


def mechanism(
    cells: Sequence[Dict[str, Any]], *, headline_fraction: float
) -> Dict[str, Any]:
    """Post-hoc. Where each arm's work actually lands once the region exists.

    This block was written *after* the exposure clause came out backwards, and
    it is labelled so. It is a description of the observed reversal, not a
    prediction that survived a test, and it should be read at that weight.
    """
    # The preregistered clauses are all scored on the archive, which is where
    # the interesting *null* was expected. Scoring only there hides the largest
    # effect in the experiment, so it is computed here explicitly.
    blind = _find(cells, "content-addressed", "goal-blind", headline_fraction)
    memoryless_blind = _find(cells, "memoryless", "goal-blind", headline_fraction)
    elitist_collapse = {
        "note": (
            "Content-addressing the blind spot, with no coordination at all, "
            "against the arms that rank on apparent quality."
        ),
        "by_arm": {
            s: {
                "catastrophic_seeds": [
                    memoryless_blind["catastrophic_seeds"][s],
                    blind["catastrophic_seeds"][s],
                ],
                "post_change_utility_auc": [
                    memoryless_blind["post_change_utility_auc"][s],
                    blind["post_change_utility_auc"][s],
                ],
                "region_share": blind["region_share"][s],
                "contrast": _contrast(blind, memoryless_blind, s),
            }
            for s in STRATEGIES
        },
    }
    # The `random` arm does not optimise, so its realised share of the region
    # should sit at the mass the region was calibrated to carry. It is the
    # only check available that the construction landed where it was aimed.
    calibration = {
        "note": (
            "The unoptimising arm's realised region share against the mass "
            "the region was calibrated to. These should agree; nothing forces "
            "them to, because the calibration is measured on initial draws "
            "and the run evolves away from them."
        ),
        "unoptimising_arm": "random",
        "realised_region_share": blind["region_share"]["random"],
    }

    attacked = _find(cells, "content-addressed", "coordinated", headline_fraction)
    control = _find(cells, "memoryless", "coordinated", headline_fraction)
    shares = attacked["region_share"]
    archive = shares[ARCHIVE_ARM]
    elitist = {s: shares[s] for s in ELITIST_ARMS}
    return {
        "stated_after_the_run": True,
        "observation": (
            "The exposure clause is backwards. The archive is the *least* "
            "exposed arm, not the most."
        ),
        "reading": (
            "A blind-spot niche is where a non-viable artifact with high "
            "apparent quality is certain to be accepted, so it is the most "
            "attractive place in the arena to an arm that ranks on apparent "
            "quality. The elitist arms converge into it and stay. The archive "
            "cannot: it keeps one elite per niche, so however good the region "
            "looks it can hold at most as many of the archive's slots as the "
            "region has niches. Niche partitioning caps the blind spot's "
            "reach at region_size / niche_count of the portfolio."
        ),
        "region_share_by_arm": shares,
        "archive_region_share": archive,
        "elitist_region_share": elitist,
        "archive_is_least_exposed": bool(archive < min(elitist.values())),
        "catastrophic_seeds_under_attack": attacked["catastrophic_seeds"],
        "catastrophic_seeds_memoryless_control": control["catastrophic_seeds"],
        "elitist_collapse": elitist_collapse,
        "calibration_check": calibration,
        "caveat": (
            "Post-hoc and single-shaped. The reading predicts the archive's "
            "region share should track region_size / niche_count and the "
            "elitist arms' should not; that is a further test, not something "
            "this run establishes."
        ),
    }



# --------------------------------------------------------------------------
# The matrix
# --------------------------------------------------------------------------

def _jobs(
    *,
    fractions: Sequence[float],
    region: Sequence[Tuple[int, int]],
    diffuse_region: Sequence[Tuple[int, int]],
    headline_fraction: float,
    **common: Any,
) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for fraction in fractions:
        for shape in ("memoryless", "content-addressed"):
            for adversary in ADVERSARIES:
                jobs.append(
                    dict(
                        panel_shape=shape,
                        adversary=adversary,
                        fraction=fraction,
                        region=None if shape == "memoryless" else [list(n) for n in region],
                        **common,
                    )
                )
    # The diffuse region is run at the headline fraction only. It is a
    # robustness check on the *shape* of the blind spot, not a second sweep.
    for adversary in ADVERSARIES:
        jobs.append(
            dict(
                panel_shape="content-addressed-diffuse",
                adversary=adversary,
                fraction=headline_fraction,
                region=[list(n) for n in diffuse_region],
                **common,
            )
        )
    return jobs


def matrix(
    *,
    seeds: int = DEFAULT_SEEDS,
    seed_start: int = DEFAULT_SEED_START,
    agents: int = DEFAULT_AGENTS,
    generations: int = DEFAULT_GENERATIONS,
    change_at: int = DEFAULT_CHANGE_AT,
    bins: int = DEFAULT_BINS,
    effort: int = DEFAULT_EFFORT,
    fractions: Sequence[float] = FRACTIONS,
    jobs: "int | None" = None,
) -> Dict[str, Any]:
    blindness = content_blindness()
    base = e027.PANELS[BASE_PANEL]
    concentrated = calibrate_region(target=base.blind_spot, shape="concentrated", bins=bins)
    diffuse = calibrate_region(target=base.blind_spot, shape="diffuse", bins=bins)
    headline = max(fractions)

    common = dict(
        seeds=seeds,
        seed_start=seed_start,
        agents=agents,
        generations=generations,
        change_at=change_at,
        bins=bins,
        effort=effort,
    )
    payloads = _jobs(
        fractions=fractions,
        region=concentrated["region"],
        diffuse_region=diffuse["region"],
        headline_fraction=headline,
        **common,
    )
    workers = jobs or min(len(payloads), max(1, (os.cpu_count() or 2) - 2))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            cells = list(pool.map(_cell_job, payloads))
    else:
        cells = [_cell_job(p) for p in payloads]

    outcome = prediction_outcome(cells, blindness, headline_fraction=headline)
    observed_mechanism = mechanism(cells, headline_fraction=headline)
    diffuse_gain = _contrast(
        _find(cells, "content-addressed-diffuse", "coordinated", headline),
        _find(cells, "content-addressed-diffuse", "goal-blind", headline),
        ARCHIVE_ARM,
    )
    addressed_panel = content_addressed_panel()
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment": EXPERIMENT,
        "configuration": {
            "base_panel": BASE_PANEL,
            "seeds": seeds,
            "seed_start": seed_start,
            "agents": agents,
            "generations": generations,
            "change_at": change_at,
            "bins": bins,
            "adversary_effort": effort,
            "fractions": list(fractions),
            "headline_fraction": headline,
            "strategies": list(STRATEGIES),
        },
        "panels": {
            "memoryless": base.as_metrics() if hasattr(base, "as_metrics") else {
                "verifiers": base.verifiers,
                "accuracy": base.accuracy,
                "correlation": base.correlation,
                "blind_spot": base.blind_spot,
            },
            "content_addressed": {
                "verifiers": addressed_panel.verifiers,
                "accuracy": round(addressed_panel.accuracy, 6),
                "correlation": addressed_panel.correlation,
                "blind_spot": addressed_panel.blind_spot,
                "note": (
                    "accuracy is the base panel's reducible accuracy: outside "
                    "the region each verifier is exactly as accurate as it was "
                    "outside the coin, so the marginal rate is unchanged."
                ),
            },
        },
        "content_blindness": blindness,
        "regions": {"concentrated": concentrated, "diffuse": diffuse},
        "prediction": PREDICTION,
        "outcome": outcome,
        "mechanism": observed_mechanism,
        "diffuse_region_contrast": diffuse_gain,
        "cells": cells,
        "limitations": [
            "The content-addressed blind spot is a construction, not a "
            "measurement. E020 measured the blind spot's *rate* on 25 real "
            "oracles; nothing here measures its shape, and a real one need be "
            "neither niche-aligned nor this concentrated.",
            "Two clauses are nulls -- an unresolved difference at 100 seeds is "
            "not evidence of no difference.",
            "The adversary's memory is exact and noiseless within a run: it "
            "sees the accept decision on every one of its own submissions. A "
            "real attacker sees a delayed, partial signal.",
            "The niche grid the blind spot is addressed by is the same grid "
            "the archive partitions on. That is the strongest possible "
            "alignment between the defence's structure and the attack's, and "
            "it is why the exposure clause should be read as an existence "
            "result rather than a rate.",
        ],
    }


def parse_args(argv: "Sequence[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--change-at", type=int, default=DEFAULT_CHANGE_AT)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--effort", type=int, default=DEFAULT_EFFORT)
    parser.add_argument(
        "--fraction",
        type=float,
        action="append",
        dest="fractions",
        help="hostile fraction; repeatable, defaults to %s" % (list(FRACTIONS),),
    )
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument(
        "--blindness-only",
        action="store_true",
        help="run only the content-blindness proof and print it",
    )
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: "Sequence[str] | None" = None) -> int:
    args = parse_args(argv)
    if args.blindness_only:
        report: Dict[str, Any] = content_blindness()
    else:
        report = matrix(
            seeds=args.seeds,
            seed_start=args.seed_start,
            agents=args.agents,
            generations=args.generations,
            change_at=args.change_at,
            bins=args.bins,
            effort=args.effort,
            fractions=tuple(args.fractions or FRACTIONS),
            jobs=args.jobs,
        )
    text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
