# IDKMesh Randomness / Bio-Inspired Experiment Status

**Updated:** 2026-08-29
**Program rule:** Randomness controls exploration, not acceptance.

This page is a compact status map for the executable research program derived from `RANDOMNESS_AND_BIOINSPIRED_ALGORITHMS.md` and `docs/research/RANDOMNESS_ROADMAP.md`.

The purpose is to keep contributors from having to reconstruct the experiment graph from many issues and pull requests.

## Governing architecture

```text
safe / deterministic envelope
          +
stochastic exploration and diversity
          +
independent verification
          +
evidence-backed selection
          +
persistent memory
          ->
adaptive collective search
```

Randomness may decide:

- what to explore;
- who attempts work;
- which local candidates receive resources;
- which independent verifier is assigned;
- how non-critical information propagates;
- how experimental policy variants are generated.

Randomness must not substitute for:

- authorization;
- provenance;
- safety gates;
- independent verification;
- canonical acceptance.

---

# Current experiment graph

```text
#29 randomness-lab foundation                    COMPLETE
      |
      +-- #30 R1 swarm diversity                MECHANISM COMPLETE / REAL EVIDENCE OPEN
      |      |
      |      +-- #70 real R1 coding corpus      OPEN
      |
      +-- #31 R2 randomized scheduling          COMPLETE
      |      |
      |      +-- #84 stronger R2 evidence       OPEN
      |
      +-- #32 R3 evolutionary orchestration     SYNTHETIC COMPLETE
      |      |
      |      +-- #96 real-task R3 phase         OPEN
      |
      +-- #97 R4 verified stigmergic routing    SYNTHETIC COMPLETE
```

---

# R0 — randomness-lab foundation

**Issue:** #29 — completed  
**Core PR:** #39

Implemented reusable dependency-free experimental infrastructure:

- deterministic seeded simulation;
- pluggable outcome environments;
- greedy baseline;
- epsilon-greedy;
- softmax/Boltzmann selection;
- UCB;
- Thompson sampling;
- power-of-d least-loaded primitive;
- repeated trials;
- raw machine-readable metrics;
- descriptive uncertainty summaries;
- Python 3.11–3.13 CI.

This remains the common substrate for the randomness experiments.

---

# R1 — diversity, error correlation, and verification

**Issue:** #30 — mechanism implemented; open pending real corpus  
**Implementation PRs:** #54, #58, #67  
**Real evidence:** #70

## Question

When does stochastic/structural diversity improve verified coding outcomes compared with repeated copies of the same worker?

## Implemented

### Six-condition synthetic harness

- one deterministic worker;
- identical replication;
- seed-only variation;
- structural diversity;
- Thompson-selected workers;
- structural diversity + randomized verifier assignment.

### Help/hurt map

The parameter sweep explicitly reports:

```text
helps
hurts
uncertain
```

instead of tuning only for positive diversity results.

Variables include:

- worker error correlation;
- verifier correlation;
- swarm size;
- structural-worker quality penalty.

### Real-result replay adapter

`randomness_lab.r1_replay` consumes the existing Phase 0:

- `ResultManifest v0.1`;
- independently verified `VerificationResult v0.1`.

Worker self-report alone never establishes truth.

The replay compares equal candidate budgets and can measure actual structural-signature failure correlation.

### Real-corpus readiness gate

`randomness_lab.r1_readiness` now fails closed before a BenchmarkCohort is
interpreted as real R1 evidence. It checks held-out/frozen status, the
prospective 20-work-unit target, exact per-signature candidate budgets,
conclusive independent verification, replay/cohort signature agreement,
independent tests, retained seeded negatives, complete cost measurements, and
non-selecting authority. The committed current-state audit is blocked at zero
eligible work units; it is explicitly contract-state evidence, not a coding
outcome.

## Evidence boundary

The repository does not yet contain a sufficient real multi-worker corpus.

#70 therefore blocks a real empirical answer. It requires held-out coding work, multiple baseline replicas, multiple structural signatures, independent verification, retained negative results, and public reproducible evidence.

---

# R2 — randomized scheduling under churn

**Issue:** #31 — completed  
**Implementation PRs:** #77, #80  
**Reference evidence PR:** #83  
**Stronger follow-up:** #84 — synthetic Phase A/B/C completed

## Question

Can bounded local random choices produce useful scheduling quality without maintaining globally current state?

## Policies

- one random choice;
- power-of-two;
- power-of-three;
- capability-aware power-of-two;
- global least-loaded high-information oracle.

## Model

The simulator has replayable task/outage traces with:

- heterogeneous capacity;
- heterogeneous capabilities;
- bursty arrivals;
- stale availability;
- stale load observations;
- worker outages/churn;
- capability mismatch;
- locality mismatch;
- requeue/recovery;
- uncheckpointed lost work.

The oracle is charged for full capability-pool metadata scans.

## Published reference scale

`results/experiments/r2/reference-scale-seed42.json`  
`results/experiments/r2/reference-scale-seed42.md`

Scales:

```text
1
10
100
1,000
10,000
100,000 workers
```

Regimes:

```text
fresh
moderate
stale
```

## First single-seed observations

These are reference observations, not universal conclusions.

- All published cells completed all tasks within the configured drain horizon.
- Capability-aware power-of-two generally stayed close to oracle p95 response while using roughly 2 metadata probes per routing attempt.
- The oracle metadata scan grew from roughly 5 probes/attempt at 10 workers to roughly 4.4k probes/attempt at 10k workers.
- At 100k workers the full oracle was intentionally skipped; bounded local policies remained executable.
- Capability-oblivious policies produced many more failed assignments, especially at large scale.
- Some small moderate/stale cells triggered the explicit `loses_badly` diagnostic, proving the harness can expose local-routing failure regimes.

## Stronger evidence completed

#84 now retains:

- a five-seed full scale ladder;
- factor-isolated capability-rarity sweeps;
- independent availability/load staleness sweeps;
- matched independent and regional failure shapes;
- workload saturation separate from fleet-size scaling;
- deterministic communication, directory, and state-cost proxies;
- an explicitly host-specific scheduler CPU/peak-memory profile.

The result is a regime map, not a universal power-of-two claim. Real network
and fleet measurements remain outside this synthetic evidence boundary.

---

# R3 — evolutionary orchestration

**Issue:** #32 — synthetic mechanism experiment completed  
**Implementation PR:** #93  
**Frozen evidence PR:** #95  
**Real-task phase:** #96

## Question

Can evolutionary search discover useful orchestration policies without using held-out results during selection, collapsing into one monoculture, or autonomously promoting itself?

## Genome

- worker count;
- structural diversity mix;
- decomposition depth;
- replication factor;
- verifier depth;
- exploration temperature;
- timeout budget;
- escalation threshold.

## Search

- changing training distributions;
- Pareto multi-objective selection;
- novelty-aware tie-breaking;
- bounded diversity archive;
- mutation;
- crossover;
- random-immigrant exploration floor;
- fixed baseline;
- fixed final training reference;
- pre-heldout champion selection;
- held-out evaluation only after search ends.

## Objectives

Maximize:

- verified success;
- worst-family success.

Minimize:

- security failures;
- regressions;
- error correlation;
- compute;
- latency;
- human attention;
- complexity.

Raw output volume/activity is not a fitness objective.

## Frozen seed-42 evidence

`results/experiments/r3/reference-seed42.json`  
`results/experiments/r3/reference-seed42.md`

Split digest:

`sha256:261e1edd128ee0492fd5b740a1576a0eeb1c5ef4cfb6ccbdf90989fac3f610f5`

Pre-heldout champion:

`g-7d18f6c8917d`

Held-out reference result:

| Metric | Fixed baseline | Pre-heldout champion |
| --- | ---: | ---: |
| Verified success | 0.2917 | 0.6417 |
| Security failure | 0.0583 | 0.0208 |
| Regression | 0.0792 | 0.0542 |
| Compute/task | 5.6048 | 8.1963 |
| Latency/task | 8.3435 | 10.6808 |
| Human attention/task | 0.2525 | 0.0833 |

Important mixed evidence:

- 47 final train-Pareto genomes reached held-out evaluation;
- 12 triggered the configured overfit flag;
- champion train→heldout success gap = 0.0733;
- champion held-out success delta vs baseline = +0.3500;
- champion security-failure delta vs baseline = -0.0375;
- champion costs more compute and latency;
- the strongest recommendation is only `consider_for_separate human-reviewed experiment`;
- autonomous promotion is always false.

The synthetic held-out split is now burned for confirmatory tuning.

#96 requires a new real-task train/held-out split and actual Verified Swarm Runner controls/outcomes.

---

# R4 — verified stigmergic routing

**Issue:** #97 — synthetic mechanism and frozen reference complete

## Question

Can ant-colony-like traces learn task→worker affinities from verified outcomes, adapt when capabilities change, and still give newcomers enough opportunities to demonstrate value?

Candidate rule:

```text
tau[a,i](t+1) = (1-rho) * tau[a,i](t) + verified_deposit[a,i](t)
```

Critical constraints:

- activity does not produce pheromone;
- verified durable outcome does;
- old evidence evaporates;
- newcomer/exploration floor remains non-zero;
- canonical acceptance remains independent from routing weight;
- no direct conversion of pheromone into governance power.

Implemented baselines:

- uniform random;
- greedy empirical success;
- Thompson sampling;
- stigmergy without evaporation;
- stigmergy with evaporation;
- stigmergy + evaporation + exploration/newcomer floor.

Implemented stressors:

- specialization;
- capability shift;
- newcomer arrival;
- misleading early success;
- churn;
- lock-in.

## Frozen reference evidence

- `results/experiments/r4/reference-default.json` — full 800-step routing
  traces, metrics, and pheromone snapshots;
- `results/experiments/r4/reference-lockin.json` — full 500-step adversarial
  lock-in traces, metrics, and snapshots;
- `results/experiments/r4/reference-summary.md` — commands, digests, comparison,
  limitations, and interpretation.

The adaptive stigmergic policy avoided the catastrophic permanent-pheromone
lock-in and explored both strong and weak newcomers. Thompson sampling still
slightly led realized success in the default trace and decisively won the
lock-in trap. The biological analogy therefore does not establish superiority.

Every stigmergic reference run records exactly zero pheromone increase from
unverified activity. A deterministic regression test verifies both artifact
hashes, preserves cross-runtime replay invariants and the negative regime, and
requires byte identity on the recorded Python 3.12 runtime family.

---

# Next-order biological tracks

These remain hypotheses rather than implementation commitments.

## Honeybee-style cross-inhibition

Use competing evidence accumulation plus explicit counter-evidence to test whether architecture/proposal decisions avoid deadlock and premature consensus better than majority voting.

## Quorum sensing

Test local thresholds for activating expensive collective actions, for example:

- starting large integration work;
- spawning an autonomous cell;
- escalating verification;
- promoting an experimental protocol to a broader trial.

A quorum is a coordination threshold, not proof of correctness.

## Physarum-style adaptive topology

Strengthen communication/task routes carrying verified useful flow and decay weak routes while preserving redundancy.

Candidate use: evolve `node -> cell -> region -> federation` connectivity under cost/latency/fault-tolerance objectives.

## Artificial immune mechanisms

Use distributed detector memory as an experimental security/anomaly layer, benchmarked against conventional anomaly-detection baselines rather than assuming biological inspiration is superior.

---

# What we have learned so far

## 1. Diversity is not agent count

The useful variable is closer to:

```text
independent useful attempts
- correlated failure
- compute cost
- human attention
```

than raw worker count.

## 2. Information has a scalability cost

R2 shows why scheduler quality must be reported together with the amount of global state consulted.

A bounded capability index + tiny candidate sample is currently a more interesting IDKMesh hypothesis than either uniform random assignment or a globally current full scan.

## 3. Search needs a test it cannot rewrite

R3 makes the held-out boundary operational. Evolution can search aggressively, but its candidate must be chosen before confirmatory evidence is opened.

## 4. Negative results are part of the product

The experiment APIs explicitly preserve:

- harmful diversity cells;
- local scheduling regimes that lose to the oracle;
- overfit evolved genomes;
- failed/security/regression evidence.

A research system that deletes those outcomes cannot reliably self-improve.

## 5. Memory needs forgetting

The next R4 question makes this explicit. Permanent historical advantage creates lock-in; zero memory wastes evidence. Controlled evaporation/decay is likely to be a core parameter across routing, reputation, topology, and community systems.

## 6. Community algorithms need stronger abuse resistance than routing algorithms

A pheromone value that routes a synthetic task is low risk. A score that influences contributor authority or resource ownership is much more dangerous.

Do not reuse experimental routing metrics as governance power without separate work on:

- Sybil resistance;
- collusion;
- newcomer fairness;
- capture;
- metric gaming;
- appeals;
- transparent decay;
- human governance.

---

# Immediate contributor path

If you want to contribute to this program now:

1. **Real coding evidence:** #70 (R1).
2. **R2 real-fleet validation:** open a bounded follow-up from completed #84 evidence.
3. **Real evolutionary orchestration evidence:** #96 (R3).
4. **New bio-inspired algorithm implementation:** #97 (R4 stigmergy).

The experiments are intentionally separable. A contributor should not need to understand all of IDKMesh before improving one policy, environment, metric, or evidence pipeline.
