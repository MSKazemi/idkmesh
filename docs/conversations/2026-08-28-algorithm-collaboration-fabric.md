# Conversation Record — Algorithm Collaboration Fabric

**Date:** 2026-08-28
**Repository:** `MSKazemi/idkmesh`

## User direction

The project owner asked how the many algorithms in IDKMesh should collaborate rather than operate as isolated mechanisms.

## Live repository evidence reviewed

The discussion was based on current repository state, including:

- `IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`;
- `MATHEMATICAL_EVOLUTION_KERNEL.md`;
- `REPOSITORY_MATHEMATICAL_PORTFOLIO.md`;
- `CONJUNCTIVE_EVOLUTION_CONTROL.md`;
- `RESOURCE_COMPUTE_ADMISSION.md`;
- `SEQUENTIAL_EVIDENCE_KERNEL.md`;
- R2 randomized scheduling under churn;
- R3 evolutionary orchestration;
- R4 verified stigmergic routing;
- verification debt / risk-weighted backpressure;
- Phase 0 WorkUnit / ResultManifest / independent-verification contracts;
- the newest uncertainty-aware metric contract;
- the E016 live verifier negative result showing that nominal diversity and near-zero correlation can be meaningless when verifiers do not discriminate;
- the active branch-convergence work in PR #205.

At the time of this record, public GitHub metadata still reported `main` as unprotected, so no stronger autonomous integration authority was added.

## Main architectural decision

Treat IDKMesh as a **federated multi-controller system** with a shared typed blackboard, not as one giant optimizer.

The recommended collaboration chain is:

```text
observe
 -> IDKGraph state
 -> Pareto / graph unlock / UCB / multiplicative-weights attention
 -> verification-backpressure generation limit
 -> resource admission
 -> R2 local scheduling + R4 verified affinity
 -> worker execution / ResultManifest
 -> evaluator-owned independent VerificationResult
 -> sequential / correlation-aware evidence
 -> selective learning updates
 -> branch convergence
 -> external human/GitHub integration decision
 -> observe again
```

## Important division of responsibility

- Pareto/NSGA-II: preserve multi-objective trade-offs.
- UCB: choose the next bounded exploration.
- Multiplicative weights: slower long-horizon experiment-budget allocation.
- Bayesian evolution: historical uncertain health evidence, not causality.
- R3: propose orchestration policies; held-out evidence remains outside the evolutionary selection loop.
- Resource admission: hard zero-cost/capability/trust eligibility.
- R2: local load/churn scheduling with bounded metadata cost.
- R4: task-worker affinity learned only from verified outcomes.
- Verification backpressure: regulate candidate supply according to trust capacity.
- Verifier aggregation: only after discrimination/calibration; nominal diversity is not enough.
- Sequential evidence: optional-stopping-aware nomination of experiment candidates.
- ACE/community algorithms: grow verified descendant lineages, not raw activity.
- Branch planner: integration-review ordering only.
- Human/protected GitHub governance: final integration authority.

## Proposed collaboration primitive

Algorithms should eventually exchange a machine-readable signal envelope containing:

```text
producer/version
scope
signal type
estimate
observation model
evidence mass
uncertainty
assumptions
failure modes
evidence references
exact source revision
freshness/expiry
authority ceiling
```

This would let the system distinguish telemetry, evidence, proposals, capacity signals, and hard guards without allowing a scalar to silently gain authority.

## Key composition proposal: R2 + R4

Use hard resource admission first, then R2 to take a small local capability-aware sample, then R4 to bias the choice within that sample using verified affinity plus explicit exploration.

Conceptually:

```text
eligible set E
 -> small sample S from R2
 -> R4 affinity/exploration inside S
 -> assignment
```

This combines low coordination cost with verified adaptive memory while preserving the rule that learned routing cannot expand the hard eligible-resource set.

## Key control proposal: backpressure regulates generation

Verification debt should constrain candidate fan-out, R3 real-experiment population size, branch/extraction proposal concurrency, and eventually community task-generation rate.

This creates a negative feedback loop:

```text
more unverified risk
 -> lower generation
 -> verifier queue clears
 -> generation may expand later
```

## Key verifier lesson

The E016 negative result is treated as architecture evidence:

```text
diversity of opinions != discrimination
near-zero correlation of noise != useful independence
```

Therefore a verifier panel should pass a discrimination/calibration screen before correlation/effective-sample-size logic is allowed to strengthen evidence.

## Next implementation recommended

Do not add another optimization method yet.

Create an `algorithm-signal-v0.1` contract and validator, then run one end-to-end information-flow experiment across:

```text
IDKGraph
 -> portfolio priority
 -> verification capacity/backpressure
 -> resource admission
 -> R2/R4 routing
 -> ResultManifest
 -> VerificationResult
 -> selective learning signals
 -> branch/governance recommendation
```

The experiment should test authority separation and replayability before trying to prove that the composite optimizer is better than simpler baselines.

## Durable architecture artifact

The full proposal is recorded in:

`docs/architecture/ALGORITHM_COLLABORATION_FABRIC.md`
