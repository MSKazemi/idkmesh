# IDKMesh Roadmap

**Status:** evidence-gated roadmap from the current repository state.

IDKMesh should **earn scale**. A mechanism demonstrated in a schema test, simulation, GitHub workflow, or one controlled machine must not be advertised as proven at Internet scale.

The project optimizes for **verified useful work under scarce human attention and compute**, not raw task count, model tokens, CPU-hours, commits, issues, or contributor count.

## 0. Where the project is now

The original roadmap began when most of the experimental kernel was still hypothetical. That is no longer true.

Already implemented on `main`:

- WorkUnit v0.1/v0.2 and related machine-readable contracts;
- ResultManifest, EvaluatorPlan, VerificationResult, experiment, CI, decomposition, compute, and graph schemas;
- Phase 0 schema/cross-object validation;
- deterministic simulation and experiment code;
- independent verification/evidence machinery;
- replay/non-selecting reporting research;
- WorkUnit decomposition benchmark infrastructure;
- protocol-neutral adapter boundary and A2A/MCP interop bindings;
- zero-project-spend compute routing/admission experiments;
- IDKGraph repository observability and link-integrity tooling;
- repository mathematical/evolution control experiments;
- ACE community-growth observation/control experiments;
- protected `main` with stable Python 3.11/3.13 PR gates.

Therefore the current bottleneck is **not “define the first JSON schemas”**. The bottleneck is converting the existing foundation into independently reviewed, real, comparable execution evidence and a coherent user-facing runner.

## 1. Primary success model

A useful headline quantity is:

```text
Verified Useful Work
---------------------------------------------
Human Attention + Compute/Resource Cost + Risk
```

Keep a Pareto view rather than collapsing everything into one permanent scalar.

Supporting measurements include:

- correctness and hidden-test success;
- post-integration defects/regressions;
- independent reproducibility;
- security findings;
- human reviewer minutes;
- verification latency/debt;
- wall-clock and resource use;
- error correlation and independence;
- merge/integration conflict;
- provenance completeness;
- contributor onboarding/return/review capacity;
- structural maintenance burden.

## 2. Scientific operating loop

Every significant mechanism should follow:

```text
Question
 -> falsifiable hypothesis
 -> baseline / comparator
 -> bounded implementation or experiment
 -> independent checks
 -> retained evidence
 -> scoped decision
 -> delayed outcome observation where relevant
```

Repository artifacts must distinguish:

- implemented mechanism;
- synthetic fixture/simulation evidence;
- observed real-run evidence;
- accepted conclusion;
- unresolved uncertainty.

## 3. Current priority gates

### Gate A — coherent Verified Swarm Runner path

**Goal:** make the existing contracts and verifier/orchestration work usable as one understandable local product path.

Required outcomes:

- one current, independently reviewed real worker/execution adapter;
- at least one additional heterogeneous adapter through the same coordinator-facing interface;
- multiple isolated attempts from one bounded WorkUnit;
- canonical ResultManifest per completed attempt;
- verifier-owned EvaluatorPlan and independent VerificationResult;
- peer failure isolation;
- non-selecting evidence/reporting and replay;
- explicit human integration outside worker/verifier authority;
- newcomer-facing run/inspect/replay instructions.

Do not count historical worker prototypes as current integration merely because their bytes or behavior were previously tested. Exact current candidate evidence and review gates still matter.

### Gate B — real WorkUnit decomposition evidence

The five-arm decomposition benchmark infrastructure exists. The research question remains open.

Required outcomes before claiming a preferred decomposition strategy:

- controlled independently assigned worker runs across the benchmark arms;
- bounded and comparable context/resource budgets;
- shared hidden evaluation criteria;
- measured rework/integration/context/verification costs;
- retained raw evidence and uncertainty;
- no assumption that formal decomposition must win.

This is the remaining empirical boundary tracked by issue #15.

### Gate C — interoperability beyond faithful mocks

The repository has a protocol-neutral worker boundary plus A2A/MCP mappings and conformance helpers.

Next evidence should show:

- official/current SDK/type conformance where feasible;
- the same logical WorkUnit round-tripping without semantic loss;
- at least one external/heterogeneous lifecycle normalized to canonical ResultManifest evidence;
- transport completion remaining distinct from acceptance;
- identity/provenance and artifact normalization surviving the boundary.

See issue #17 and the interoperability docs.

### Gate D — independent review capacity

Several important subsystems deliberately require genuinely separate review. Automation must not manufacture this evidence.

Continue to measure:

- time to first independent review;
- reviewer minutes per bounded decision;
- disagreement/uncertainty;
- concentration of approvals in one maintainer;
- whether documentation reduces review/onboarding cost.

### Gate E — documentation and product coherence

The repository now contains much more implementation/evidence than a newcomer should read directly.

Maintain progressive disclosure:

1. README: identity, current truth, how to start;
2. contributor docs: workflow and live work;
3. architecture/specification indexes: current subsystem truth;
4. research/audit/history: evidence and provenance.

Historical records should remain inspectable without silently becoming current architecture.

## 4. Near-term engineering sequence

### R0 — Keep the foundation green

- protect `main`;
- require stable PR gates;
- preserve deterministic link/schema checks;
- keep untrusted PR text/data out of privileged execution paths;
- keep project compute spend at the declared repository policy ceiling;
- fix documentation drift when implementations or gates change.

### R1 — Finish one real local product loop

Target experience:

```text
bounded repository task
 -> WorkUnit
 -> two or more isolated attempts
 -> canonical candidate bundles
 -> independent verification
 -> evidence report
 -> exact replay
 -> human decision
```

The result should be runnable and explainable without reading research-history documents.

### R2 — Demonstrate heterogeneous worker interchangeability

Route at least two materially different worker implementations through the same coordinator-facing contract without coordinator-core rewrites.

Measure semantic equivalence, adapter-specific failures, evidence/provenance quality, and integration cost.

### R3 — Execute the first controlled comparative benchmark cohort

Use the existing decomposition/benchmark contracts with real bounded attempts.

Publish negative results and uncertainty. Do not optimize only for task success; record verification/reviewer/resource costs.

### R4 — Package the first reproducible release

A release should contain or point to:

- install/run instructions;
- exact contract versions;
- a small reproducible example;
- saved result/evidence bundle;
- replay instructions;
- known limitations/security boundaries;
- benchmark/evidence provenance.

### R5 — Small multi-machine experiment

Only after the local loop is coherent, test 3–10 real machines/resources.

Study:

- churn and retries;
- stragglers;
- heterogeneous environments;
- artifact transfer;
- coordinator restart;
- resource admission;
- corrupted/malicious results;
- sandbox boundaries;
- end-to-end provenance.

### R6 — Community-scale experiment

With real external participants, measure whether the system reduces or increases human coordination burden.

The social system is part of the distributed system: a technically scalable mesh that requires one human bottleneck is not scalable.

## 5. Medium-term research phases

### Phase M1 — Stronger execution isolation and provenance

Progressively add or test, when threat models require them:

- stronger container isolation;
- gVisor/microVM/WASI-style backends where appropriate;
- immutable source/environment identifiers;
- signed manifests/attestations;
- transparency/audit logs;
- independent monitors.

Do not add blockchain merely because provenance matters.

### Phase M2 — Verification-market/backpressure research

Study how verification capacity should be allocated under generation pressure:

- risk-aware verification;
- adaptive fan-out;
- verifier diversity/correlation;
- sequential/anytime evidence;
- overload/criticality signals;
- human escalation by information value.

### Phase M3 — Locality and federated scheduling

Test the fractal scaling hypothesis:

```text
node -> cell -> region/fabric -> federation
```

Measure what summaries can be coarse-grained without losing important scheduling, verification, or governance decisions.

### Phase M4 — Decentralized state only where needed

Evaluate gossip, CRDTs, ordered consensus, and partitioned/federated state according to the semantics of each state class.

Do not create one global real-time database for every worker simply because the long-term vision is distributed.

### Phase M5 — Cross-organization trust

When multiple real operators exist, compare:

1. signed/federated databases;
2. Merkle/transparency logs;
3. Byzantine replicated state machines;
4. permissioned ledgers.

Choose the cheapest mechanism that satisfies the demonstrated threat model.

### Phase M6 — Optional economic mechanisms

Only after IDKMesh produces demonstrated useful work, study credits, grants, conventional payments, reputation, auctions, scoring rules, or other incentives.

A token is not a prerequisite and should not be introduced without a concrete need for transferable permissionless settlement or equivalent functionality.

## 6. Internet-scale research

Claims about 10,000–1,000,000 participants should begin in simulation and progressively larger observed deployments.

Any scale claim should report at least:

- real vs simulated node count;
- task/event rate;
- workload distribution;
- coordinator/federation count;
- state size;
- bandwidth;
- latency distribution;
- failure/churn assumptions;
- trust/adversary assumptions;
- resource and verification cost;
- human governance/review load.

Relevant research areas include hierarchical control, locality-aware scheduling, network-of-networks failure, privacy-preserving aggregation, protocol evolution, heterogeneous accelerators, disaster recovery, and global-vs-local governance.

## 7. Current repository structure

The repository has evolved beyond the old proposed `src/coordinator`, `src/worker`, and three-schema sketch. Current top-level responsibility is distributed roughly as follows:

```text
.github/workflows/   GitHub-native checks, observers, experiments, and gates
benchmarks/          benchmark cohorts/fixtures
config/              repository policies
examples/            machine-readable examples and fixtures
docs/                architecture, specs, research, audits, evidence, history
experiments/         executable experiment and validation tooling
idkips/              improvement proposals
interop/             protocol-neutral adapters and A2A/MCP interoperability
schemas/             versioned machine-readable contracts
scripts/             repository/community/evolution control and analysis code
sim/                 deterministic research simulations/analysis
tests/               repository-wide regression and contract tests
tools/               repository observatory/link/maintenance tooling
state/               bounded machine-readable evolution state/history
```

Do not reorganize this tree merely to match an old roadmap diagram. Structural changes should reduce a demonstrated maintenance/navigation problem and preserve provenance.

## 8. Research program examples

Current and planned experiment families include:

- diversity vs duplication under matched budgets;
- correlated-error and verifier-independence effects;
- quorum/dependence model shape;
- verification scaling/backpressure;
- adaptive allocation and scheduling;
- coordination criticality;
- WorkUnit decomposition strategies;
- learned verifier reliability;
- community reproduction and reviewer load;
- repository evolution/control quality.

The purpose is not to prove the preferred architecture. The purpose is to find where it works, where it fails, and what boundary conditions matter.

## 9. Deliberate non-goals for the current stage

Do not prematurely build or claim:

- a custom cryptocurrency/token;
- a public blockchain dependency;
- a custom generic agent transport replacing A2A/MCP;
- a one-million-node production network;
- synchronized giant-model training over arbitrary home Internet;
- one universal reputation score;
- one permanent global objective function;
- autonomous self-approval or merge;
- production-grade hostile multi-tenant guarantees without the required isolation evidence;
- superiority of swarm/decomposition strategies before controlled results exist.

## 10. Definition of progress

The roadmap advances when evidence removes a gate, not when a document accumulates more future features.

A useful transition should leave an inspectable chain:

```text
baseline
 -> bounded action/experiment
 -> exact artifacts
 -> independent checks
 -> scoped decision
 -> observed outcome
 -> updated next gate
```

See [`ITERATION_MODEL.md`](ITERATION_MODEL.md), [`EVOLUTION.md`](EVOLUTION.md), [`schemas/README.md`](schemas/README.md), and the curated [`docs/`](docs/README.md) indexes for the current contracts behind this roadmap.
