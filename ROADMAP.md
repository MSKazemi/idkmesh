# IDKMesh Roadmap

This roadmap converts the project vision into a sequence of falsifiable research and engineering milestones. The rule is to **earn scale**: do not claim that an algorithm works for one million nodes until simulation and progressively larger deployments support the claim.

The intended progression is approximately:

`1 -> 10 -> 100 -> 10,000 -> 1,000,000`

The project should optimize for **verified useful work**, not raw task count, raw model tokens, raw CPU-hours, or raw contributor count.

---

# 0. Primary success metric

The first headline metric should be:

`Verified Useful Work / (Human Attention + Compute Cost)`

Supporting metrics:

- accepted useful artifacts;
- post-acceptance defect rate;
- test pass rate and test quality;
- independent reproducibility;
- security findings;
- time to verified result;
- CPU/GPU-hours per accepted result;
- energy per accepted result where measurable;
- human review minutes per accepted result;
- duplicate-work ratio;
- agent error correlation;
- disagreement/calibration quality;
- node failure recovery time;
- bandwidth per verified result.

No single metric should become a permanent master objective. Maintain a Pareto view.

---

# 1. Scientific operating loop

Every significant idea follows:

`Question -> Hypothesis -> Formal model -> Baseline -> Experiment -> Evidence -> Decision -> Implementation -> Re-test`

Repository artifacts should preserve:

- positive results;
- negative results;
- uncertainty;
- assumptions;
- datasets/workloads;
- benchmark configurations;
- random seeds when relevant;
- hardware/software environment;
- result provenance.

---

# Phase 0 — Define the experimental kernel

## Goal

Build the minimum local framework needed to test IDKMesh ideas on one computer without prematurely building a distributed platform.

## Deliverables

### A. Work Unit schema

Define a machine-readable `WorkUnit` containing at least:

- `id`;
- parent goal/task;
- inputs and content hashes;
- resource requirements;
- required capabilities;
- execution constraints;
- expected artifact types;
- verification policy;
- replication policy;
- timeout/deadline hints;
- privacy/trust class;
- provenance requirements;
- reward/priority metadata;
- dependency IDs.

### B. Result / Evidence schema

Define a `ResultManifest`:

- Work Unit ID;
- produced artifact hashes;
- worker identity/key;
- environment/build information;
- logs/metrics references;
- self-reported confidence;
- signature;
- verifier results;
- reproducibility status.

### C. Goal Graph schema

Initial node types:

- Goal;
- Question;
- Assumption;
- Hypothesis;
- Requirement;
- Proposal;
- WorkUnit;
- Artifact;
- Test;
- Evidence;
- Decision;
- Risk;
- Contributor/Agent.

Initial edge types:

- `depends_on`;
- `supports`;
- `contradicts`;
- `implements`;
- `verifies`;
- `derived_from`;
- `supersedes`;
- `blocks`;
- `produced_by`.

### D. Simulator

Create a discrete-event simulator able to generate virtual workers with different:

- CPU/GPU capacity;
- latency/bandwidth;
- reliability;
- availability/churn;
- task skills;
- model quality;
- error correlation;
- malicious behavior probability.

### E. Metrics harness

Every algorithm comparison should write a common metrics format.

## Exit criterion

At least two scheduling/aggregation algorithms can run on the same synthetic workload and produce directly comparable metrics.

---

# Phase 1 — Single-machine multi-agent scientific prototype

## Goal

Test the central collective-intelligence hypothesis before networking laptops.

Run multiple AI roles on one machine or controlled environment:

1. proposer;
2. alternative proposer;
3. critic;
4. test author;
5. adversarial tester;
6. integrator;
7. verifier.

## First experiment

Compare:

- **Baseline A:** one capable coding agent;
- **Baseline B:** N copies of the same agent + majority/selection;
- **IDKMesh C:** diverse roles/models/prompts + independent tests + correlation-aware verification.

Keep task set and compute budget as comparable as practical.

## Key measurements

- accepted tasks;
- hidden-test success;
- post-integration regressions;
- review effort;
- duplicate reasoning;
- error correlation;
- total token/compute use;
- calibration of confidence;
- time to verified artifact.

## Mathematical experiments

- majority vote versus weighted Bayesian aggregation;
- random diversification versus measured diversity;
- UCB/Thompson task allocation versus uniform allocation;
- greedy selection versus annealing/evolutionary search;
- one verifier versus quorum/redundant verification.

## Exit criterion

Demonstrate at least one reproducible workload where a structured diverse swarm produces a better verification-adjusted result than a single-agent baseline, or document a negative result explaining why it does not.

---

# Phase 2 — Local mesh: 3–10 real machines

## Goal

Create the first actual compute mesh.

## Components

1. **Coordinator prototype** — receives goals and emits Work Units.
2. **Worker daemon** — advertises capabilities and executes sandboxed Work Units.
3. **Artifact store** — content-addressed result storage.
4. **Scheduler** — capability-aware assignment.
5. **Verifier service** — runs tests/quorum checks.
6. **Provenance service** — hashes and signs artifacts/results.
7. **Metrics collector** — stores benchmark events.
8. **CLI** — joins a worker and submits/observes jobs.

## Scheduling baselines

Compare:

- central FIFO;
- capability matching;
- shortest expected processing time;
- work stealing;
- multi-objective scheduler.

## Failure tests

- worker disappears mid-task;
- slow/straggler worker;
- duplicate result;
- corrupted result;
- network partition;
- coordinator restart;
- incompatible environment.

## Exit criterion

A job graph can finish correctly despite planned worker failures, with reproducible artifacts and end-to-end provenance.

---

# Phase 3 — Verification-first swarm: 10–20 laptops

## Goal

Run the first headline experiment already identified in the decision log: can ordinary laptops with diverse AI coding agents improve IDKMesh itself better than a single-agent baseline?

## Work types

- implementation;
- test generation;
- fuzzing;
- static analysis;
- benchmark execution;
- documentation verification;
- architecture critique;
- dependency/security review;
- reproducibility checks.

## Verification policies

Experiment with:

- deterministic tests;
- independent test generation;
- redundant execution;
- majority/quorum;
- trimmed/median aggregation;
- model-family diversity;
- adversarial verifier;
- human escalation for unresolved high-risk disagreement.

## Key scientific question

How does verification cost scale as generation fan-out increases?

The system should seek an operating point where marginal generation still produces positive verified value.

## Exit criterion

Publish a reproducible benchmark report with raw data, failures, compute cost, and uncertainty intervals.

---

# Phase 4 — Decentralized state and churn

## Goal

Reduce dependence on a single always-available coordinator.

## Research tracks

### Gossip

Use randomized gossip for selected distributed summaries such as load estimates or liveness information.

### CRDTs

Use CRDTs for state that can tolerate eventual consistency.

### Consensus

Use consensus only for state that actually needs one ordered authoritative decision.

### Graph partitioning / islands

Create local clusters of workers based on latency, trust, capability, organization, or workload affinity.

## Physics/science experiments

- graph Laplacian/spectral monitoring of fragmentation;
- percolation simulations under churn and targeted failures;
- load diffusion/backpressure;
- partial synchronization versus fully asynchronous operation;
- epidemic-style propagation analysis for compromised updates.

## Exit criterion

The mesh continues useful operation through partitions/churn and reconciles allowed state after reconnection without global corruption.

---

# Phase 5 — Security and adversarial network

## Goal

Assume both workers and coordinators can be hostile.

## Required work

- least-privilege sandbox;
- network/filesystem policy;
- reproducible execution environments;
- signed Work Units;
- signed result manifests;
- content-addressed artifacts;
- software supply-chain controls;
- verifier separation;
- Byzantine result tests;
- replay protection;
- rate limits;
- identity/reputation experimentation;
- secrets isolation;
- incident/audit logs.

## Adversarial simulations

- worker fabricates success;
- worker returns poisoned artifact;
- verifier colludes with worker;
- coordinator sends malicious code;
- compromised high-reputation node;
- Sybil population;
- correlated model attack;
- artifact-history rewrite attempt.

## Provenance implementation order

`hashes -> signatures -> attestations -> transparency log -> independent monitors`

Do not require blockchain at this stage.

## Exit criterion

Publish a threat model and show that selected attacks are detected, contained, or explicitly documented as unresolved.

---

# Phase 6 — 100+ node hierarchical mesh

## Goal

Test the architecture beyond a laboratory cluster.

## Architecture hypothesis

`worker -> local swarm -> compute island -> regional/federated coordinator -> global goal graph`

The hierarchy should aggregate summaries rather than pushing all worker state globally.

## Multiscale / renormalization question

Determine what information can be coarse-grained at each level without losing important scheduling or verification decisions.

## Metrics

- control-plane messages per worker;
- data-plane bandwidth;
- scheduling regret;
- stale task rate;
- island imbalance;
- fault containment;
- convergence after partition;
- spectral connectivity;
- energy per verified result.

## Exit criterion

Show sublinear or bounded-per-node control overhead for the tested workload and explain any central bottlenecks.

---

# Phase 7 — Distributed/federated model learning experiments

## Goal

Only after the work mesh is stable, test whether the same infrastructure can support distributed model learning.

## Candidate methods

- FedAvg/FedProx-style methods;
- asynchronous federated optimization;
- local-SGD/island methods;
- DiLoCo-like low-communication training;
- gradient compression;
- secure aggregation;
- robust aggregation;
- gradient/coded computation for stragglers.

## Constraint

Do not assume synchronized large-model pretraining across home Internet connections is a suitable first workload.

## Exit criterion

For a selected model/workload, beat a clearly defined centralized or naive-distributed baseline on a Pareto dimension such as cost, privacy, communication, resilience, or utilization without unacceptable quality loss.

---

# Phase 8 — Cross-organization federation

## Goal

Allow independent organizations to run infrastructure while sharing selected goals, tasks, artifacts, and provenance.

## Research questions

- federated identity;
- policy boundaries;
- trust domains;
- data locality;
- organizational reputation;
- replicated provenance;
- permissioned consensus where necessary;
- dispute resolution.

## Blockchain decision point

At this stage compare:

1. signed central/federated database;
2. replicated Merkle transparency logs;
3. Byzantine replicated state machine;
4. permissioned blockchain/ledger.

Adopt blockchain only if the threat model and benchmark justify the cost.

---

# Phase 9 — Optional open compute economy

## Goal

Only after IDKMesh produces demonstrated useful work, investigate economic incentives.

## Start without a token

Test:

- public contribution scores;
- reputation;
- compute credits;
- grants/bounties;
- sponsorship;
- conventional payments.

## Economic experiments

- proper scoring rules for probabilistic claims;
- Shapley-style marginal contribution estimates;
- auction-based scarce-resource allocation;
- Nash bargaining for shared resource allocation;
- peer prediction where ground truth is delayed;
- Sybil-resistance mechanisms.

## Blockchain/token gate

A token should be considered only if transferability, permissionless settlement, or programmable economic coordination is demonstrably necessary.

---

# Phase 10 — Internet-scale research

## Goal

Study rather than assume operation at 10,000–1,000,000 participants.

Much of this phase begins in simulation before real deployment.

## Required areas

- hierarchical control;
- locality-aware scheduling;
- failure domains;
- network-of-networks percolation;
- economic/adversarial simulation;
- observability sampling;
- privacy-preserving aggregation;
- global-versus-local governance;
- protocol evolution;
- heterogeneous accelerators;
- energy/carbon accounting;
- disaster recovery.

## Scaling rule

Any claim of scale should report:

- node count;
- task rate;
- bandwidth;
- state size;
- coordinator count;
- failure assumptions;
- latency distribution;
- workload distribution;
- simulation versus real-node percentage.

---

# 2. Immediate implementation backlog

These are the recommended next concrete artifacts, in order:

1. `schemas/work-unit.schema.json`
2. `schemas/result-manifest.schema.json`
3. `schemas/goal-graph.schema.json`
4. `sim/` discrete-event simulator
5. `metrics/` common benchmark schema
6. baseline FIFO scheduler
7. capability-aware scheduler
8. work-stealing scheduler
9. baseline majority aggregator
10. Bayesian/weighted aggregator
11. correlation/diversity estimator
12. redundant verifier/quorum module
13. content-addressed artifact store
14. signing/attestation module
15. local worker daemon
16. coordinator prototype
17. reproducible sandbox executor
18. first multi-agent coding benchmark
19. first 3–10-node fault/churn benchmark
20. first 10–20-laptop self-improvement experiment

---

# 3. Proposed repository structure

```text
idkmesh/
  README.md
  VISION.md
  ARCHITECTURE.md
  MATHEMATICAL_FOUNDATIONS.md
  SCIENTIFIC_FOUNDATIONS.md
  BLOCKCHAIN_STRATEGY.md
  RESEARCH_QUESTIONS.md
  ROADMAP.md
  DECISIONS.md
  GOVERNANCE.md
  CONTRIBUTING.md
  PROJECT_RULES.md

  schemas/
    work-unit.schema.json
    result-manifest.schema.json
    goal-graph.schema.json

  src/
    coordinator/
    worker/
    scheduler/
    verifier/
    provenance/
    graph/
    reputation/

  sim/
    worker_model/
    network_model/
    adversary_model/

  experiments/
    manifests/
    results/
    analysis/

  benchmarks/
    coding/
    scheduling/
    churn/
    byzantine/

  docs/
    conversations/
    findings/
    protocols/
    threat-models/
```

This structure should evolve only when implementation produces evidence for a better organization.

---

# 4. First experiment suite

## E001 — Does diversity beat duplication?

Compare same-model replication versus model/role diversity under a fixed compute budget.

## E002 — Does independent verification improve scaling?

Increase generation fan-out and measure marginal verified value with and without independent verification.

## E003 — How harmful is correlated error?

Artificially vary error correlation in simulation and compare majority, weighted voting, Bayesian aggregation, and robust methods.

## E004 — Which scheduler works under heterogeneous churn?

Compare FIFO, capability matching, work stealing, and multi-objective scheduling.

## E005 — What replication factor is economically optimal?

Vary redundant execution versus worker reliability and task risk.

## E006 — Can bandits allocate research compute better?

Compare uniform allocation with UCB/Thompson allocation across competing approaches.

## E007 — Can annealing/evolution escape architecture local optima?

Compare greedy, random, simulated annealing, genetic, and bandit/tree-search approaches on synthetic architecture/configuration problems.

## E008 — Where is the network failure transition?

Use percolation/churn simulations for random and targeted failures across the three-network model.

## E009 — Does hierarchical coarse-graining preserve decisions?

Compare flat global scheduling with island summaries at increasing network sizes.

## E010 — Transparency log versus blockchain

When multiple operators exist, benchmark signed database, Merkle transparency log, BFT replication, and permissioned ledger for provenance.

---

# 5. What we should deliberately NOT build yet

Avoid premature complexity:

- custom cryptocurrency/token;
- public blockchain dependency;
- one-million-node deployment;
- synchronized giant-model training over arbitrary home Internet;
- custom consensus protocol without a formal need;
- global real-time state for every node;
- one universal reputation score;
- one permanent global objective function;
- unverified autonomous code merging;
- physics/quantum claims without benchmark evidence.

---

# 6. Near-term definition of success

IDKMesh does **not** need to prove the million-laptop vision immediately.

A convincing first success is much smaller:

> A reproducible open-source system in which a heterogeneous group of AI agents and a small number of ordinary computers can decompose useful software work, execute it safely, independently verify results, preserve provenance, survive worker failures, and demonstrate better verification-adjusted productivity than a well-defined single-agent baseline.

If that cannot be demonstrated, the failure is scientifically valuable and should guide the next architecture.