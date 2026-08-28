# IDKMesh Randomness Research Roadmap

**Status:** Actionable research and implementation plan

**Companion:** [`../../RANDOMNESS_AND_BIOINSPIRED_ALGORITHMS.md`](../../RANDOMNESS_AND_BIOINSPIRED_ALGORITHMS.md)

This document converts the randomness / biological-algorithm research into concrete engineering steps for IDKMesh.

## Core finding

IDKMesh should use **bounded randomness**.

Randomness is most useful when it chooses what to explore, who attempts work, which alternative gets compute, which independent verifier evaluates a result, or how non-critical information propagates. It should not decide what becomes canonical.

The governing pattern is:

```text
safe constraints
    + stochastic exploration
    + heterogeneous independent attempts
    + independent verification
    + evidence-backed selection
    + persistent memory
    -> adaptive collective search
```

### Constitutional rule

> IDKMesh MAY use randomness to decide what to explore, who attempts work, which hypotheses receive experiments, and how decentralized information moves. IDKMesh MUST NOT use randomness as a substitute for evidence, authorization, provenance, safety policy, or verification when deciding what becomes canonical.

## Findings to treat as hypotheses, not dogma

1. **More agents are not automatically more intelligence.** Error correlation matters more than raw swarm size.
2. **Exploration should scale with uncertainty.** High unresolved uncertainty should increase diversity/temperature; strong evidence should reduce it.
3. **Randomness without selection is noise.** Variation becomes useful only when coupled to reproducible evaluation and memory.
4. **Randomness without diversity may be fake diversity.** Different seeds on the same model/prompt/toolchain can remain strongly correlated.
5. **Local stochastic rules can scale better than global optimization.** Examples include power-of-two load balancing and randomized gossip.
6. **Biological algorithms are inspirations, not proof of superiority.** Every bio-inspired policy must be benchmarked against simple conventional baselines.
7. **Fitness must represent verified durable value.** Optimizing activity, stars, commits, output count, or benchmark score alone risks Goodhart-style failure.
8. **The system should preserve some minority strategies.** A small exploration floor or diversity archive reduces permanent lock-in.
9. **Random choices should be auditable.** Record policy version, random seed where safe, inputs, selected candidates, and evaluation evidence.
10. **Security-sensitive randomness needs cryptographic randomness.** Scientific reproducibility seeds and security secrets have different requirements.

## Candidate stochastic control law

For candidate action `i`, define:

\[
S_i = \hat U_i - \lambda C_i - \rho R_i + \beta E_i + \gamma N_i + \delta D_i
\]

where:

- `U_i`: expected verified utility;
- `C_i`: expected compute/time/human-attention cost;
- `R_i`: risk;
- `E_i`: exploration value from uncertainty;
- `N_i`: novelty;
- `D_i`: diversity contribution.

Sample rather than always taking the argmax:

\[
P(i)=\frac{\exp(S_i/T)}{\sum_j\exp(S_j/T)}.
\]

Let temperature depend on uncertainty:

\[
T_t = clip(T_{min} + k H_t, T_{min}, T_{max})
\]

with entropy

\[
H_t=-\sum_k p_k\log p_k.
\]

Interpretation:

```text
high uncertainty -> higher T -> more alternatives
strong evidence  -> lower T  -> more convergence
```

This is an experimentable policy, not yet a protocol requirement.

---

# Phase 0 — Measurement contract

Before implementing clever algorithms, define a shared result schema so every policy can be compared fairly.

Minimum run metrics:

- task / task family;
- worker strategy and version;
- verifier strategy and version;
- random seed or randomness provenance where safe;
- success/failure;
- hidden-test or independent-verification score;
- security failures/regressions;
- compute consumed;
- wall-clock latency;
- human review/attention required;
- pairwise error correlation across attempts;
- novelty/diversity metrics;
- information gain where applicable;
- reproducibility result;
- post-integration defect rate when observable.

Primary candidate objective:

\[
Q_{swarm}=VerifiedUtility-\lambda Compute-\mu HumanAttention-\nu ErrorCorrelation.
\]

Do not freeze the coefficients prematurely; preserve the raw metrics.

### Done when

A deterministic baseline and a stochastic policy can emit exactly the same experiment/result schema.

---

# Phase 1 — `randomness-lab` simulator

Build a small policy simulator before wiring stochastic behavior deeply into the Verified Swarm Runner.

Suggested structure:

```text
randomness-lab/
  policies/
    greedy.py
    epsilon_greedy.py
    softmax.py
    ucb.py
    thompson.py
    power_of_two.py
  environments/
    worker_selection.py
    load_balancing.py
    correlated_workers.py
  metrics/
    utility.py
    diversity.py
    correlation.py
    information_gain.py
  experiments/
    r1_swarm_diversity.py
    r2_scheduler.py
    r3_evolution.py
```

Names are illustrative; follow repository conventions when implementation begins.

Requirements:

- seeded reproducibility;
- interchangeable policies;
- configurable worker-quality distributions;
- controllable error correlations;
- worker churn/failure;
- configurable compute and attention costs;
- machine-readable result output;
- plots/tables generated from saved experiment data, not manually entered results.

### Done when

At least two selection policies and one deterministic baseline can be compared over many seeded trials with confidence intervals or equivalent uncertainty reporting.

---

# Phase 2 — Experiment R1: controlled randomness in a coding swarm

## Question

Does controlled stochastic diversity improve verified outcomes compared with simple replication?

## Conditions

1. one deterministic worker;
2. `N` identical deterministic workers;
3. `N` workers with only random seed variation;
4. `N` workers with role/prompt/model/tool diversity;
5. bandit-selected workers;
6. diverse workers + independent randomized verifier assignment.

## Critical variable

Explicitly manipulate pairwise error correlation. This is central to the IDKMesh thesis.

## Measurements

- verified task success;
- hidden-test pass rate;
- regression rate;
- security defects;
- pairwise error correlation;
- compute;
- latency;
- human attention;
- verified utility per unit cost.

## Expected useful result

Not "randomness is good." The useful result is a map of **when diversity + stochastic exploration beats replication and when it does not**.

---

# Phase 3 — Experiment R2: power-of-two scheduling under churn

## Question

Can local randomized routing approach useful load balance without maintaining expensive global state?

Simulate heterogeneous workers at scales such as:

```text
1
10
100
1,000
10,000
100,000
```

Compare:

- one random choice;
- power-of-two choices;
- power-of-three choices;
- capability-aware power-of-two;
- global least-loaded oracle as an upper-cost reference.

Inject:

- bursty arrivals;
- heterogeneous task sizes;
- worker churn;
- stale load observations;
- network partitions / unreachable workers where appropriate.

Measure:

- maximum and percentile queue depth;
- task waiting time;
- failed assignments;
- scheduler metadata traffic;
- fairness;
- utilization;
- locality/capability mismatch.

---

# Phase 4 — Experiment R3: evolutionary orchestration

Represent an orchestration policy as a genome, for example:

```text
worker_count
worker_mix
diversity_weight
decomposition_depth
replication_factor
verification_mix
exploration_temperature
timeout
escalation_threshold
```

Run:

```text
variation
 -> isolated benchmark trials
 -> independent verification
 -> multi-objective scoring
 -> selection
 -> mutation/crossover
 -> diversity archive
```

Use a Pareto front rather than collapsing every objective into one scalar whenever practical.

Required safeguards:

- hold-out tasks;
- changing task families;
- benchmark leakage checks;
- complexity penalties;
- reproducibility;
- no autonomous promotion into production;
- human-readable evidence report for any promoted policy.

Goal: discover robust orchestration policies, not benchmark-specialized tricks.

---

# Phase 5 — Stigmergic routing

After IDKMesh has enough real experiment history, prototype pheromone-style task/worker and task/verifier edges:

\[
\tau_{ij}(t+1)=(1-\rho)\tau_{ij}(t)+\Delta\tau_{ij}(t).
\]

Rules:

- deposits are proportional to **verified useful outcomes**, not activity;
- stale history evaporates;
- new workers receive an exploration prior;
- reputation cannot bypass verification;
- anti-monopoly caps or sublinear reinforcement should be tested.

Potential edge types:

```text
task-class -> worker-strategy
task-class -> verifier
contributor-skill -> starter-task
failure-mode -> detector
```

---

# Phase 6 — Distributed stochastic mechanisms

Only when central discovery/scheduling becomes a measured bottleneck, prototype:

- randomized gossip for non-critical summaries;
- small-world cross-cell links;
- Physarum-inspired adaptive communication topology;
- quorum-sensing-like activation thresholds for forming cells or launching expensive collective work.

These should not be prerequisites for the first Verified Swarm Runner.

---

# Community-growth experiments

Randomness can also help the repository community if used carefully.

Candidate mechanisms:

1. randomly rotate a subset of "good first investigation" issues so the same visible issues do not monopolize attention;
2. probabilistically surface newcomer contributions for review while preserving risk gates;
3. create stochastic cross-domain issue recommendations to connect contributors from different specialties;
4. use bandits to learn which onboarding paths produce retained contributors;
5. decay old routing signals so historical popularity does not permanently dominate.

Do **not** optimize community algorithms directly for stars, comments, or issue volume. Candidate community fitness should include retained contributors, verified contributions, review latency, newcomer success, diversity, and maintainer attention.

---

# Relationship to existing IDKMesh work

This roadmap complements the existing broad experiment on whether coherent systems can emerge from vague goals (GitHub issue #22). That experiment asks the larger emergence question. The randomness track supplies concrete mechanisms and controlled sub-experiments that can feed evidence into it.

The randomness track should also integrate with:

- Goal/Evidence Graph;
- Work Contract;
- Verified Swarm Runner;
- experiment/metrics layer;
- contributor/community evolution work;
- future fractal cell scheduling.

---

# Immediate next steps

1. Define the shared stochastic experiment/result schema.
2. Build the minimal `randomness-lab` simulator.
3. Implement deterministic, epsilon-greedy, softmax, UCB, and Thompson baselines.
4. Add explicit correlated-error simulation.
5. Run R1 and publish raw results plus analysis.
6. Add power-of-two scheduling and run R2 under heterogeneous churn.
7. Add a minimal evolutionary policy genome and run R3 on held-out task families.
8. Only after empirical results, propose which mechanisms belong in IDKMesh core through the normal design/IDKIP process.

## Decision gate

No stochastic mechanism becomes a default IDKMesh production policy merely because it is elegant or biologically inspired. Promotion requires evidence that it improves the relevant objective under reproducible conditions, with documented failure modes and a deterministic or simpler baseline for comparison.
