# Constitutional Evolutionary Mesh (CEM)

**Status:** research protocol / architecture hypothesis

CEM is the current IDKMesh hypothesis for building coherent systems from vague or evolving goals without surrendering quality, safety, or auditability.

It combines:

- explicit uncertainty in the Goal Graph;
- stochastic and human/AI proposal generation;
- constitutional viability gates;
- multiple competing solution niches;
- bounded Work Units;
- independent verification;
- provenance and failure memory;
- diversity-aware resource allocation;
- staged, reversible self-improvement.

The constitution is defined in [`../../CONSTITUTION.md`](../../CONSTITUTION.md).

## Control loop

At iteration `t`, maintain:

- `G_t`: current Goal Graph;
- `A_t`: archive of viable candidate approaches;
- `E_t`: accumulated evidence and failures;
- `R_t`: available human/compute resources;
- `L`: constitutional laws / hard invariants.

A simplified loop is:

```text
1. Observe unresolved/high-value regions of G_t.
2. Allocate bounded exploration/verification budget from R_t.
3. Generate candidate proposals using humans, agents, mutation, search, or recombination.
4. Reject candidates that fail constitutional viability gates L.
5. Place surviving candidates into behavior/architecture niches in A_t.
6. Emit bounded Work Units for experiments, implementation, tests, benchmarks, and attacks.
7. Execute Work Units on capability-matched workers.
8. Independently verify returned Result Manifests.
9. Add positive and negative evidence to E_t and the Goal Graph.
10. Update confidence, risks, and open questions in G_t.
11. Replace a niche incumbent only when the challenger has stronger verified evidence.
12. Reallocate resources using value, information gain, uncertainty, novelty, risk, and redundancy.
13. Integrate only through normal project/release gates.
14. Repeat.
```

## Mathematical sketch

Let candidate `x` have multi-objective measurements:

`M(x) = [Q, S, R, A, N, I, C]`

where for example:

- `Q`: verified quality/usefulness;
- `S`: safety/security;
- `R`: robustness/reproducibility;
- `A`: adaptability;
- `N`: useful novelty;
- `I`: expected information gain;
- `C`: human + compute cost.

Hard viability is separate:

```text
V(x, L) = 1  if all required constitutional constraints are satisfied
          0  otherwise
```

Only `V(x,L)=1` candidates may enter the viable archive.

Do not permanently collapse `M(x)` into one score. Use Pareto dominance, niches, task-specific scalarizations, or temporary policies that remain inspectable and revisable.

A candidate research-allocation score might be:

`Priority(x) = a*ExpectedValue + b*InformationGain + c*Novelty + d*RiskReduction - e*Cost - f*Redundancy`

with an explicit protected exploration budget so the currently popular branch cannot monopolize all resources.

## Niche archive

A niche is not necessarily a product category. It can be defined by behavior or architecture descriptors such as:

- centralized <-> decentralized;
- low-resource <-> high-performance;
- synchronous <-> asynchronous;
- maximum-security <-> maximum-throughput;
- human-heavy <-> autonomous;
- local-first <-> federated;
- simple <-> feature-rich.

The descriptors themselves are research parameters and may evolve.

The archive should retain the strongest *verified* candidate per region rather than the most popular candidate.

## Stigmergic memory

Direct all-to-all communication does not scale to large populations. Agents should coordinate indirectly through durable traces:

- Goal Graph nodes/edges;
- Work Unit status;
- test and benchmark results;
- failure signatures;
- artifact provenance;
- resource prices/queues;
- review outcomes;
- confidence and uncertainty;
- open risks;
- niche occupancy.

A worker can act on the current environment without knowing every other worker. The environment becomes collective memory.

## Positive and negative feedback

Positive feedback is useful:

- verified success -> more resource;
- reliable worker -> higher-value tasks;
- high-information experiment -> more investigation.

But every positive loop needs damping:

- correlation penalty;
- novelty/exploration budget;
- replication by independent methods;
- resource ceilings;
- queue/backpressure limits;
- reputation decay/uncertainty;
- challenger allocation;
- human escalation for high-risk unresolved disagreement.

Without negative feedback, the mesh can converge prematurely or amplify a wrong belief.

## Self-modification levels

CEM should evolve itself gradually.

### Level 0 — search state

Goals, tasks, priorities, proposals, and experiments can change freely within ordinary project rules.

### Level 1 — operational policies

Scheduler weights, exploration temperature, replication factors, and queue limits may change automatically inside bounded ranges and with metrics/rollback.

### Level 2 — protocol mechanisms

Schedulers, aggregation rules, verifier strategies, and reputation formulas may compete experimentally. Promotion requires benchmark evidence and compatibility review.

### Level 3 — governance/constitutional mechanisms

Changes to the rules that judge future changes require the strongest gates, public rationale, adversarial analysis, and explicit human governance.

The system must never allow a self-improving mechanism to make itself successful merely by weakening its own evaluation criteria.

## What CEM is not

CEM is not:

- an argument that evolution produces perfection;
- a license for arbitrary autonomous code changes;
- a claim that random agents become intelligent at sufficient scale;
- a substitute for software architecture or human judgment;
- one fixed Quality-Diversity algorithm;
- a requirement for blockchain or tokens;
- proof that nature-inspired metaphors transfer directly to engineering.

Every mechanism remains a falsifiable hypothesis.

## First executable model

See:

- [`../../sim/emergence_sim.py`](../../sim/emergence_sim.py)
- [`../../tests/test_emergence_sim.py`](../../tests/test_emergence_sim.py)
- [`../../experiments/E011-emergence-vague-goals.md`](../../experiments/E011-emergence-vague-goals.md)
- [`../../experiments/results/E011-reference-seed7.json`](../../experiments/results/E011-reference-seed7.json)

The model is intentionally small. Its value is that IDKMesh now has a concrete mechanism that can be attacked, compared, improved, or disproved.
