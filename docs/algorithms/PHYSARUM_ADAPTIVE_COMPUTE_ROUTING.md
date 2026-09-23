# Physarum-Inspired Adaptive Compute Routing

**Status:** experimental algorithm proposal  
**Date:** 2026-09-22  
**Scope:** adaptive routing inside a future admitted multi-node/federated compute fabric.

## 1. Why this mechanism

IDKMesh already has:

- hard zero-project-spend compute admission;
- provider-neutral compute offers;
- deterministic offer selection;
- work-unit capability/security filters;
- experimental task-to-worker routing.

What it does **not** yet have is an adaptive multi-path routing layer for a future compute mesh where:

- several already-authorized nodes/regions can carry work;
- link/node quality changes over time;
- one path may be cheap/fast but fragile;
- another may be slower but more reliable;
- a static best path can become wrong after churn or an outage.

The slime mold *Physarum polycephalum* is relevant because its transport network adapts tube conductance according to flow. Tero et al. showed a mathematical abstraction balancing transport efficiency, cost, and fault tolerance in adaptive networks (Science 327, 2010, DOI: 10.1126/science.1177894).

The engineering hypothesis is:

> A conductance-based adaptive routing rule can retain useful alternative compute paths and recover from changing node/link quality faster than static single-path selection, without bypassing IDKMesh admission or trust policy.

## 2. Critical authority boundary

Physarum routing is **after admission**, never before it.

```text
Resource evidence
  -> local authorization
  -> concrete compute offers
  -> Resource -> Compute Admission
  -> hard WorkUnit feasibility/security/cost filter
  -> admitted zero-project-cost graph
  -> Physarum-inspired adaptive route recommendation
  -> bounded execution
  -> ResultManifest
  -> independent VerificationResult
  -> human/governance integration
```

The adaptive algorithm MUST NOT:

- turn an unavailable provider into an available one;
- relax the repository's $0 project-spend ceiling;
- invent capabilities;
- weaken worker trust requirements;
- grant repository-write or merge authority;
- treat path popularity as correctness evidence.

If no eligible admitted path exists, the result remains `no_eligible_offer` / no dispatch.

## 3. Biological mechanism -> engineering mechanism

In the classical flow-conductivity abstraction:

```text
Q_ij = (D_ij / L_ij) * (p_i - p_j)
```

where:

- `Q_ij` = flow;
- `D_ij` = tube conductivity;
- `L_ij` = path/edge length or cost;
- `p_i - p_j` = pressure difference.

Conductivity changes with observed flow and decays without reinforcement.

For the first IDKMesh experiment, use a simpler path-level equivalent-resistance approximation:

```text
R(path) = sum_e L_e / D_e

Conductance(path) = 1 / R(path)
```

Then combine that with observed reliability:

```text
RouteValue(path) =
    Conductance(path)
  * EstimatedReliability(path)
  * Efficiency(path)
```

with:

```text
Efficiency(path) = 1 / PathLength(path)
```

Selection remains stochastic with a small exploration floor.

## 4. Conductance update

For edge `e` after one routed WorkUnit:

```text
D_e(t+1) =
  clip(
    (1-rho) * D_e(t)
    + alpha * VerifiedRouteReward * I[e used]
    - penalty * I[e observed failed],
    D_min,
    D_max
  )
```

where:

- `rho` = evaporation / forgetting;
- `alpha` = reinforcement gain;
- verified route reward is larger for successful low-burden paths;
- observed failed edges are explicitly penalized;
- `D_min > 0` prevents total extinction of alternative paths.

This is deliberately similar in spirit to biological tube adaptation but is not a claim that compute networks are literal slime molds.

## 5. Reliability learning

Each admitted edge keeps a simple Beta posterior:

```text
reliability_e ~ Beta(a_e, b_e)
```

Observed success:

```text
a_e += 1
```

Observed failure:

```text
b_e += 1
```

Path reliability is initially approximated as the product of posterior means across its edges.

This is a research simplification. Real deployment would need to distinguish:

- transport failure;
- worker failure;
- provider outage;
- timeout;
- artifact-transfer failure;
- verifier rejection.

Only failures actually attributable to a path/link should update transport reliability.

## 6. Why this is different from ACO already in IDKMesh

ACO/stigmergy currently addresses **which task/worker path deserves attention** based on verified useful outcomes.

Physarum routing addresses a different layer:

```text
ACO / AVE:
Which worker/task/verifier strategy should receive work?

Physarum compute routing:
Through which already-admitted compute/federation path should the bounded work travel?
```

The state variable is edge/path conductance, not task pheromone.

The mechanism should not create a second task scheduler.

## 7. Baselines

The first simulator compares:

1. **shortest-static**
   - always use the initially shortest path;
   - no learning.

2. **reliability-greedy**
   - choose current estimated reliability / path length;
   - no explicit exploration.

3. **epsilon-greedy**
   - same as reliability greedy with random exploration.

4. **Thompson path**
   - Bayesian path-level success posterior;
   - samples a route under uncertainty.

5. **Physarum**
   - edge-level reliability posteriors;
   - adaptive conductance;
   - evaporation;
   - failure penalty;
   - bounded exploration.

The Physarum mechanism only earns further development if it competes with the stronger adaptive baselines, not merely the static shortest path.

## 8. Dynamic environment

The first fixture intentionally changes during the run.

Before the shift:

- path A is shortest and highly reliable;
- path B is longer but usable;
- path C is longest and highly reliable.

After the shift:

- path A degrades sharply;
- path B improves;
- path C remains stable.

This tests whether the router can:

- exploit a good short path initially;
- retain enough alternate-path knowledge;
- recover after the old route becomes bad;
- avoid paying unnecessary route burden forever.

## 9. Metrics

Report a Pareto vector:

- overall completion rate;
- pre-shift completion rate;
- post-shift completion rate;
- mean latency/path length on successful tasks;
- mean routing burden;
- path entropy;
- maximum path-selection share;
- adaptation/recovery time;
- optional future energy/donor burden;
- optional future verifier-independence value.

A higher success rate that doubles donor/network burden is not automatically better.

## 10. Product integration target

If the synthetic mechanism survives baselines and later real-node evidence, integrate as a **dry-run planner** beside the existing compute router.

Possible future interface:

```text
admitted_graph = compute_admission(...)

plan = adaptive_path_router(
    work_unit,
    admitted_graph,
    observed_path_state,
)

explain(plan)
```

The initial integration should only explain:

- selected route;
- alternative routes kept alive;
- conductance/reliability state;
- why a path was penalized;
- whether route scarcity caused no dispatch.

It should not execute automatically.

## 11. Real-node evidence gate

Do not claim an advantage from simulation alone.

A real experiment should use 3-10 controlled nodes or containers and inject:

- latency changes;
- transient node loss;
- one degraded relay/provider;
- bandwidth limits;
- coordinator restart;
- artifact transfer failure.

Compare against:

- deterministic shortest/lowest-wait routing;
- reliability-aware greedy;
- Thompson/contextual-bandit routing.

Retain exact route decisions and failure attribution.

## 12. Falsification criteria

Reject or simplify the mechanism if:

- Thompson/bandit routing adapts equally well with less state;
- the conductance model adds latency/burden without improving resilience;
- it becomes unstable under noisy reliability observations;
- it over-reinforces early lucky paths;
- `D_min` exploration produces excessive donor/network cost;
- path failures cannot be attributed accurately enough for safe updates.

## 13. External research basis

- Tero et al., **Rules for biologically inspired adaptive network design**, Science 327 (2010), DOI `10.1126/science.1177894`.
- Le Verge-Serandour & Alim, **Physarum polycephalum: Smart Network Adaptation**, Annual Review of Condensed Matter Physics 15 (2024), DOI `10.1146/annurev-conmatphys-040821-115312`.
- Gao et al., review of Physarum-based computational models, Physics of Life Reviews 29 (2019), DOI `10.1016/j.plrev.2018.05.002`.

The papers motivate the adaptive-network mechanism. They do not establish that the mechanism is better for IDKMesh; that remains an experimental question.
