# Conversation record — executable ACO continuation

**Date:** 2026-08-28

## Trigger

After adding the biology-inspired ACO stigmergic task-routing proposal, the project owner asked to continue.

## Initial decision

Do not connect ACO directly to live GitHub task assignment. First convert the biological analogy into deterministic, falsifiable experiments with simple baselines and CI.

## Phase 1 — fixed ACO implementation

Added:

- `sim/aco_stigmergy_sim.py`
  - synthetic heterogeneous tasks and workers;
  - random, greedy, capability-only, and ACO routing;
  - evidence-backed pheromone deposits;
  - evaporation and bounded pheromone state;
  - congestion and correlated-attempt penalties;
  - explicit exploration floor;
  - JSON output and reproducible seeds.
- `sim/run_aco_sweep.py`
  - repeated-seed comparison using the same generated worker population per strategy/replicate.
- `tests/test_aco_stigmergy_sim.py`
  - mechanics, determinism, probability normalization, evaporation, bounds, reinforcement, and anti-congestion tests.
- `experiments/E014-aco-stigmergic-task-routing.md`
  - predeclared question, baselines, metrics, rejection conditions, and evidence ladder.

## Phase 2 — first synthetic result

A 40-seed reference comparison produced a mixed result:

```text
strategy        utility/cost   duplicate   coverage   concentration
random             0.3997        0.2266      8.000       0.1391
greedy             1.1322        0.8333      1.000       1.0000
capability         0.8690        0.4281      4.825       0.3833
fixed ACO          0.5584        0.1551      8.000       0.1944
```

ACO reduced duplication and concentration and preserved full task coverage, but it did not beat capability-only or greedy routing on immediate utility per cost.

Decision: preserve the mixed result rather than tuning it away.

Results:

- `experiments/results/E014-reference-sweep.json`
- `experiments/results/E014-reference-sweep.md`

## Phase 3 — parameter/Pareto sensitivity

Added `sim/run_aco_parameter_sweep.py` and tests.

A sweep of 24 ACO parameter configurations over 12 seeds produced 11 non-dominated Pareto points. The best-efficiency tested ACO point reached approximately:

```text
utility/cost       0.6071
duplicate rate     0.1833
coverage           8/8
concentration      0.2108
```

The result confirmed a stable tradeoff rather than one universally best setting: stronger exploitation improved efficiency while consuming diversity/congestion margin.

Results:

- `experiments/results/E014-parameter-pareto.json`
- `experiments/results/E014-parameter-pareto.md`

## Phase 4 — Homeostatic Stigmergic Routing

The mixed ACO evidence motivated a synthesis rather than blind parameter optimization.

**Homeostatic Stigmergic Routing (HSR)** combines:

1. capability matching for exploitation;
2. evidence-backed stigmergic memory;
3. density-dependent negative feedback that increases diversity/congestion pressure only when crowding exceeds healthy targets.

Core form:

```text
Score(a,j,t) = CapabilityValue(a,j)
               * tau_j(t)^alpha
               * [Diversity(a,j,t) * Congestion(j,t)]^lambda(t)
```

with feedback:

```text
lambda(t+1) = clip(
    lambda(t)
    + k_d * (DuplicateRate(t) - D_target)
    + k_s * (Concentration(t) - S_target)
    - r * (lambda(t) - lambda_min),
    lambda_min,
    lambda_max
)
```

Added:

- `sim/homeostatic_stigmergy_sim.py`
- `tests/test_homeostatic_stigmergy_sim.py`
- `docs/algorithms/HOMEOSTATIC_STIGMERGY_ROUTING.md`

A 40-seed comparison produced:

```text
strategy             utility/cost   duplicate   coverage   concentration
fixed ACO               0.5584        0.1551      8.000       0.1944
capability              0.8690        0.4281      4.825       0.3833
homeostatic hybrid      0.6754        0.2796      7.850       0.2515
```

HSR is a promising intermediate Pareto operating point, not a universal winner. It moves toward capability efficiency while retaining much lower duplication/concentration and near-full coverage.

Results:

- `experiments/results/E014-homeostatic-hybrid.json`
- `experiments/results/E014-homeostatic-hybrid.md`

## Phase 5 — historical replay interface

Synthetic evidence is not enough for live use. The next gate is read-only historical/shadow replay.

Added:

- `schemas/routing-replay-v0.schema.json`
  - separates routing-time inputs from retrospective outcomes;
  - records feature/profile provenance and annotation policy;
  - makes hindsight leakage an explicit dataset concern.
- `sim/replay_task_routing.py`
  - performs deterministic capability, fixed-ACO, and HSR recommendations from frozen snapshots;
  - never calls GitHub or changes repository state;
  - applies only evidence known at the snapshot time;
  - evaluates held-out retrospective outcomes only after recommendations are fixed.
- `tests/test_replay_task_routing.py`
  - includes an anti-hindsight test: arbitrarily changing future outcomes must not change recommendations.
- `examples/routing-replay.example.json`
  - illustrative IDKMesh-shaped example only; all annotations/outcomes are clearly marked synthetic and are not Level-2 evidence.

The legitimate next dataset must freeze real source timestamps and annotation rules before evaluation.

## Evidence ladder

The research must advance only through explicit stages:

1. **unit/mechanics tests** — implemented and passing;
2. **repeated synthetic simulation** — active; mixed results preserved;
3. **historical repository replay** — interface implemented; real frozen dataset still required;
4. **advisory shadow mode** — not authorized yet;
5. **bounded live experiment** — not authorized yet.

A favorable synthetic result is **not** permission for autonomous production routing.

## Safety / anti-Goodhart constraints

- Pheromone is routing memory, not truth, reputation, or authority.
- Unverified popularity/activity must not create strong reinforcement.
- Routing never grants permissions, approves work, merges work, or bypasses verification.
- Evaporation, lower/upper bounds, explicit exploration, congestion penalties, and correlation discounts preserve alternatives and reduce herding.
- Homeostatic regulation is bounded and explicit rather than hidden tuning.
- Retrospective outcomes must remain held out from historical routing inputs.
- Negative and mixed experimental results are durable project evidence and may justify rejecting ACO/HSR.

## Current research conclusion

The most useful biological insight from this iteration is broader than Ant Colony Optimization itself:

> **Exploit strongly while capacity is healthy; when density, duplication, correlation, or reviewer pressure rises, increase negative feedback and diversify effort; relax the inhibition again when the system returns to a healthy region.**

This principle may later apply to task routing, Growth Seed generation, verifier allocation, compute scheduling, experiment portfolios, and repository self-evolution, but each application requires its own evidence and safety gates.
