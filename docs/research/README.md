# Research Index

This directory contains executable research plans, experiment interpretations,
and calibration evidence. Results are evidence for bounded claims, not automatic
policy changes or merge decisions.

## Program and Measurement

- [First Research Program](FIRST_RESEARCH_PROGRAM.md) — staged path from
  deterministic foundations to held-out real-task evidence.
- [Top 20 Questions](TOP_20_QUESTIONS.md) — prioritized open questions about
  scaling, verification, governance, and community growth.
- [Metric Uncertainty v0.1](METRIC_UNCERTAINTY_V0_1.md) — uncertainty and
  reporting rules for repository metrics.
- [Collaboration Observables v0.1](COLLABORATION_OBSERVABLES_V0_1.md) —
  deterministic latency, concentration, recurrence, queue, CI, and debt
  measurements plus the preregistered E023 community analysis.
- [Preregistration v1: First-Review Latency and Contributor Recurrence](PREREG_FIRST_REVIEW_LATENCY_V1.md) —
  the specification, the randomized design it would take to earn a causal
  claim, and the threats to validity, registered against zero observations.
- [Phase 0: Executable Research Foundation](PHASE_0_SPEC.md) — schemas,
  fixtures, and replay requirements beneath later experiments.
- [Randomness Research Roadmap](RANDOMNESS_ROADMAP.md) and
  [experiment status](RANDOMNESS_EXPERIMENT_STATUS.md) — sequence and current
  state of the bio-inspired scheduling program.

## Routing and Orchestration Experiments

- [R1 Swarm Diversity vs Replication](R1_SWARM_DIVERSITY_EXPERIMENT.md),
  [help/hurt sweep](R1_HELP_HURT_SWEEP.md), and
  [real-result replay](R1_REAL_RESULT_REPLAY.md) — identify and replay regimes
  where diverse attempts help or hurt.
- [R1 Collective-Capability Scaling](R1_COLLECTIVE_SCALING.md) — synthetic
  mechanism extension for issue #13: verified-success increment, compute, and
  verifier attention as N moves through 1, 2, 5, and 10 under controlled task
  difficulty, plus budget-matched flat, role-specialized, and task-DAG
  coordination topologies and their fitted scaling exponents. Not real
  coding-agent performance.
- [R1 Real-Corpus Readiness Gate](R1_CORPUS_READINESS.md) — the contract that
  must hold before `randomness_lab.r1_replay` may be run on a real held-out
  corpus. Readiness tooling only; no real R1 outcome. Issues #30 and #70.
- [R2 Randomized Scheduling Under Churn](R2_SCHEDULING_CHURN_EXPERIMENT.md) and
  [scale/regime sweep](R2_SCALE_REGIME_SWEEP.md), plus the
  [capability-rarity sweep](R2_CAPABILITY_RARITY_SWEEP.md) — measure capability,
  staleness, failure, and scale effects.
- [R3 Evolutionary Orchestration](R3_EVOLUTIONARY_ORCHESTRATION.md) — evolve
  policies on training tasks and confirm on held-out work.
- [R4 Verified Stigmergic Routing](R4_STIGMERGIC_ROUTING.md) — route from
  verified outcomes with evaporation and newcomer exploration.

- [Work Unit Research Track — protocol status map](WORK_UNIT_RESEARCH_TRACK_COMPLETION.md)
  — maps the formal Work Unit research questions onto current executable
  contracts and separates the converged protocol-definition foundation from the
  empirical acceptance work that keeps issue #15 open.

## Verification Research

- [Coordination Criticality and Finite-Difference Response](CRITICALITY_AND_FLUCTUATION_RESPONSE.md)
  — matched small-load probes compared with utilization and backlog baselines.
- [Evaluator Plan Binding](EVALUATOR_PLAN_BINDING.md) — binds verifier-owned
  evaluation intent to exact task evidence.
- [Executable Independent Verifier MVP](EXECUTABLE_VERIFIER_MVP.md) — defines
  the first executable authority-separated verifier.
- [Verification Debt and Risk-Weighted Backpressure](VERIFICATION_DEBT_AND_BACKPRESSURE.md)
  — controller model for limiting unverified work.
- [Verification Backpressure Temporal Benchmark](VERIFICATION_BACKPRESSURE_BENCHMARK.md)
  — multi-window benchmark for that controller.
- [E022 Seven-Mode Verification Scaling Matrix](../../experiments/E022-verification-scaling-matrix.md)
  — matched comparison of every verification condition required by issue #14.
- [E024 Matched-Budget Emergence](../../experiments/E024-matched-budget-emergence.md)
  — equal-evaluation comparison of random, fixed-scalar, and Quality-Diversity search.
- [E026 Imperfect Verifier Panel](../../experiments/E026-imperfect-verifier-panel.md)
  — E024 rerun with E017/E020's measured correlated panel and blind-spot floor.
- [E027 Defect Propagation](../../experiments/E027-defect-propagation.md)
  — gives an accepted defect a cost, so verifier error can reach the outcome
  metric, and sweeps the cost knob across its whole range.
- [E028 Latent Defect Dimension](../../experiments/E028-latent-defect-dimension.md)
  — removes E027's confound by moving viability into a dimension the goals cannot
  see; the archive's survival holds in 18 of 20 cells and breaks only under the
  stress panel at full defect cost.
- [E029 First Real Model Attempts](../../experiments/E029-first-real-model-attempts.md)
  — 60 sandboxed attempts by a pinned 0.5B open-weight producer on the frozen
  benchmark: 0 accepted, 56 of 60 failing the diff protocol before any
  repository content was consulted.
- [E030 Supplied-Goal Membership](../../experiments/E030-supplied-goal-membership.md)
  — removes E024's supplied-oracle confound by switching the environment to a
  parity-matched goal the arms do not hold; the archive keeps all but 1.6-4.4%
  of its lead and stays 0/100 catastrophic, while the majority-vote swarm loses
  its whole lead in every panel.
- [E025 Learned Verifier Reliability](../../experiments/E025-learned-verifier-reliability.md)
  — calibration/held-out evidence for reliability and dependence-aware aggregation.
- [IDKGraph P1 Independent Review Protocol](IDKGRAPH_P1_INDEPENDENT_REVIEW_PROTOCOL.md)
  — frozen-cohort human review and attention measurement for issue #152.

## Benchmark Calibration Evidence

- [Canonical Task 001 v0.4 calibration](TASK001_REAL_V04_CALIBRATION.md) — real
  transition-proxy calibration retained from the active benchmark lineage.
- Successor-v2 pre-freeze calibrations:
  [Task 001](PHASE_B2_V2_TASK001_SYMLINK_CALIBRATION.md),
  [Task 002](PHASE_B2_V2_TASK002_NONFINITE_ROUTER_CALIBRATION.md),
  [Task 003](PHASE_B2_V2_TASK003_UNOBSERVED_HEAD_CALIBRATION.md),
  [Task 004](PHASE_B2_V2_TASK004_NONFINITE_RWVB_CALIBRATION.md), and
  [Task 005](PHASE_B2_V2_TASK005_OUTPUT_CALIBRATION.md).

- [Successor-v2 pre-freeze novelty audit](PHASE_B2_V2_PRE_FREEZE_NOVELTY_AUDIT.md)
  — records why the calibrated scaffold must remain unscored and unfrozen.

Calibration candidates are not scored benchmark outcomes. Preserve exact
source revisions, digests, and lifecycle status when citing these records.
