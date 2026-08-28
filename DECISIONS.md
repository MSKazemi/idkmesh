# IDKMesh Decision Log

## 2026-08-28 — Adopt the name IDKMesh

**Decision:** Use **IDKMesh** as the public project name and `idkmesh` as the repository name.

**Rationale:**

- Preserves the original philosophy of *I Don't Know* without using an extremely generic project name.
- `Mesh` communicates decentralized collaboration among humans, AI agents, knowledge, tasks, and compute nodes.
- The exact GitHub name `idkmesh` was not occupied when checked.
- The phrase supports the project's core idea: uncertainty should be explicit and collective intelligence should emerge through structured collaboration and verification.

**Tagline:** `From uncertainty to collective intelligence.`

**Alternatives considered:**

- `idontknow` / `I Don't Know` — philosophically strong but generic and collision-prone.
- `SwarmForge` — meaningful, but already used in the AI-agent ecosystem.
- Reusing `NovaFabric` — rejected because the existing NovaFabric repository is a different project focused on replayable execution capsules and provenance.

## 2026-08-28 — GitHub is the canonical public project record

**Decision:** Use `https://github.com/MSKazemi/idkmesh` as the canonical public repository for IDKMesh.

**Rationale:**

- Git-based version history is well suited to open research, software, decisions, and proposals.
- GitHub provides issues, pull requests, discussions, CI, contributor workflows, and discoverability.
- Project-related ChatGPT outputs should be reflected in the repository when they materially affect the project.

**Constraint:** Public records must exclude secrets, sensitive personal material, private internal chain-of-thought, and third-party confidential content.

## 2026-08-28 — Treat uncertainty as a first-class system object

**Decision:** IDKMesh should not require a fully specified global goal before collaboration begins.

**Rationale:** The project originated specifically from the problem of coordinating people and AI systems when different participants have incomplete or different understandings of the target.

**Consequence:** The architecture should eventually represent competing goals, assumptions, hypotheses, confidence, evidence, and unresolved questions explicitly.

## 2026-08-28 — Verification must scale with generation

**Decision:** More agents or contributors cannot be assumed to imply higher software quality. IDKMesh must separate proposal generation from verification.

**Rationale:** Ensembles of small models or large contributor populations can amplify correlated errors, duplicated effort, integration overhead, and security risk.

**Consequence:** Testing, review, adversarial evaluation, reproducibility, provenance, and possibly formal methods are core architectural concerns rather than later add-ons.

## 2026-08-28 — Use Work Units as the core execution primitive

**Decision:** IDKMesh should coordinate bounded, independently executable and verifiable **Work Units** rather than initially attempting to coordinate all participating machines as one synchronous computer.

**Rationale:** Internet-connected volunteer laptops are heterogeneous, intermittently available, and constrained by latency and bandwidth. Bounded units of coding, testing, evaluation, simulation, review, inference, fuzzing, benchmarking, and research can tolerate this environment much better than tightly synchronized computation.

**Consequence:** Work Unit schemas should carry goal, context, constraints, resource requirements, expected artifacts, verification rules, provenance, evidence, and confidence/evaluation information.

## 2026-08-28 — Represent evolving intent as a Goal Graph

**Decision:** Explore a persistent Goal Graph that models goals, open questions, assumptions, hypotheses, competing proposals, experiments, evidence, decisions, and unresolved conflicts.

**Rationale:** Different contributors and AI agents may legitimately interpret an ambiguous target differently. IDKMesh should turn disagreement into parallel exploration and experimentation rather than forcing premature consensus.

**Consequence:** Evidence and experiments should be able to increase or decrease confidence in branches of the graph over time.

## 2026-08-28 — Do not start by emulating one giant GPU

**Decision:** The initial distributed-compute architecture should prioritize asynchronous or weakly coupled workloads rather than synchronized large-model training over home Internet connections.

**Rationale:** Heterogeneous hardware, node churn, latency, and bandwidth make synchronized training a significantly harder initial problem.

**Consequence:** Distributed/federated training remains a research stream, while the first implementation focuses on coding attempts, test execution, verification, analysis, inference, benchmarking, simulation, and other independently useful tasks.

## 2026-08-28 — Delay blockchain/token economics

**Decision:** Do not make blockchain, cryptocurrency, or token rewards a prerequisite for the first IDKMesh implementation.

**Rationale:** These mechanisms introduce a second large problem involving incentives, regulation, Sybil attacks, speculation, and economic design before the system has demonstrated useful coordinated work.

**Consequence:** Begin with contribution history, provenance, reproducibility, reputation, and non-monetary credits. Revisit economic mechanisms only when a demonstrated coordination problem requires them.

## 2026-08-28 — First empirical milestone is a 10–20 laptop self-improvement experiment

**Decision:** The first major research experiment should test whether 10–20 ordinary laptops running diverse AI coding agents can improve the IDKMesh codebase itself while producing better independently verified results than a single-agent baseline.

**Rationale:** This experiment is small enough to implement but directly tests the central thesis: distributed diversity plus verification can create more reliable software-development output than one agent working alone.

**Primary measurement direction:** **Verified useful work per unit of human attention and compute.**

**Candidate metrics:** accepted contributions, post-merge defects, reproducibility, compute cost per accepted artifact, reviewer time, evaluator disagreement, duplicated effort, security findings, and time from idea to verified implementation.

## 2026-08-28 — Design for mutual distrust between workers and coordinators

**Decision:** Workers should not trust arbitrary incoming jobs, and coordinators should not trust arbitrary returned results.

**Rationale:** A volunteer software-development compute network creates both remote-code-execution risk on participant machines and fraudulent/incorrect result risk for the network.

**Consequence:** Sandboxing, least privilege, reproducible environments, provenance, content-addressed artifacts, independent verification, redundant execution for sensitive claims, and supply-chain controls are foundational requirements.

## 2026-08-28 — Use a three-network abstraction

**Decision:** Model IDKMesh initially as three interacting networks:

1. **Intelligence network** — humans and AI agents that propose, criticize, test, and select ideas.
2. **Work/knowledge network** — goals, questions, hypotheses, tasks, code, evidence, tests, dependencies, decisions, and provenance.
3. **Compute network** — heterogeneous laptops, GPUs, servers, and other resources that execute work.

**Rationale:** Reasoning/coordination, knowledge/dependency structure, and physical execution have different mathematical constraints and should not be conflated into one protocol.

## 2026-08-28 — Treat collective intelligence as diversity-aware, not count-based

**Decision:** Raw agent count is not a quality metric.

**Rationale:** Majority or ensemble gains depend on competence and sufficiently independent errors. Large populations of similar agents can have strongly correlated failure modes.

**Consequence:** IDKMesh should explicitly measure correctness, calibration, novelty, redundancy, error correlation, specialization, and independent verification.

A working research relationship is:

`collective value = f(competence, diversity, independence, verification, specialization, coordination)`.

## 2026-08-28 — Use multi-objective optimization rather than one master score

**Decision:** Model system design as a multi-objective optimization problem and study Pareto trade-offs.

**Candidate objectives:** correctness, usefulness, diversity, robustness, security, latency, compute/energy cost, bandwidth, privacy, fairness, and contributor satisfaction.

**Rationale:** Collapsing all values into one permanent scalar objective too early creates brittle optimization and Goodhart risks.

## 2026-08-28 — P0 mathematical foundations

**Decision:** Prioritize the following mathematical families for early research and prototypes:

1. graph/DAG algorithms and spectral graph theory;
2. multi-objective and combinatorial optimization;
3. Bayesian inference, calibration, robust statistics, and information theory;
4. multi-armed bandits and Monte Carlo tree search;
5. matching, network flow, queueing, and work stealing;
6. redundant execution and Byzantine-resistant validation;
7. gossip, CRDTs, and appropriately scoped consensus;
8. game theory, proper scoring, contribution valuation, and evolutionary mechanism selection.

**Later research:** distributed/federated learning, coding theory, secure aggregation, formal verification, and deeper statistical-physics or quantum-inspired techniques when concrete experiments justify them.

## 2026-08-28 — Physics analogies are hypotheses, not evidence

**Decision:** Ideas from simulated annealing, free-energy models, spin systems, percolation, synchronization, particle/gas models, or quantum-inspired algorithms may generate useful hypotheses but must not be described as engineering advantages without empirical evidence.

**Rationale:** Attractive cross-disciplinary analogies can inspire algorithms, but they can also mislead if treated as proof.

## 2026-08-28 — Incremental scaling discipline

**Decision:** Study scalability progressively, approximately across scales such as:

`1 -> 10 -> 100 -> 10,000 -> 1,000,000` participants/nodes.

**Rationale:** Large-scale claims should be supported by simulation, benchmarks, and progressively larger deployments rather than extrapolated casually from small prototypes.

## 2026-08-28 — Research mechanisms must be falsifiable

**Decision:** Major algorithms, aggregation rules, scheduling methods, and governance mechanisms should be connected to explicit hypotheses, baselines, metrics, and experiments.

**Rationale:** IDKMesh is both a software project and an open scientific experiment. Negative results and rejected mechanisms are valuable project output.

## 2026-08-28 — Use physics as a multiscale model library

**Decision:** Treat statistical mechanics, diffusion, percolation, synchronization, transport, control theory, renormalization, and thermodynamics of information as a library of candidate models for specific IDKMesh behaviors rather than as one unified physical theory of the platform.

**Rationale:** These fields address different real properties of a large heterogeneous mesh: exploration, propagation, connectivity, cadence, congestion, feedback stability, scale, and energy.

**Consequence:** Each physical model must identify its IDKMesh variables, baseline, measurable prediction, and falsification experiment before affecting production architecture. See `SCIENTIFIC_FOUNDATIONS.md`.

## 2026-08-28 — Prefer partial/local coordination over global synchronization

**Decision:** Do not require global barriers or full synchronization across arbitrary volunteer workers.

**Rationale:** Heterogeneous Internet-connected machines have different latency, availability, and natural operating cadence. Full synchronization converts slow or disconnected nodes into global bottlenecks.

**Consequence:** Study asynchronous execution, local synchronization, compute islands, eventual consistency, and bounded integration checkpoints. Kuramoto-style synchronization models may be used as research tools, not as the runtime protocol.

## 2026-08-28 — Quantum methods are optional backends, not the project foundation

**Decision:** Ordinary IDKMesh laptops are classical computers and should not be described as a quantum computer. Quantum ideas enter through testable quantum-inspired formulations or optional future hardware integrations.

**Rationale:** Classical distribution does not create superposition, entanglement, or quantum speedup.

**Consequence:** QUBO formulations may be compared across classical heuristics and future quantum annealers. Tensor-network or other quantum-inspired techniques remain later research until a concrete bottleneck justifies them.

## 2026-08-28 — Cryptographic provenance precedes blockchain

**Decision:** Implement artifact hashing, signatures, signed attestations, and an append-only transparency log before considering blockchain as core infrastructure.

**Rationale:** IDKMesh needs provenance and auditability early, but those properties do not inherently require cryptocurrency or general-purpose blockchain consensus. Transparency-log systems demonstrate a simpler verifiable approach for software-supply-chain metadata.

**Consequence:** The initial provenance path is:

`content hash -> signature -> attestation -> transparency log -> independent monitoring`.

Blockchain becomes a decision point only when multiple independent operators need a shared ledger or economic settlement that simpler mechanisms cannot satisfy. See `BLOCKCHAIN_STRATEGY.md`.

## 2026-08-28 — Blockchain is not a correctness oracle

**Decision:** Never treat an on-chain record or smart contract as proof that an AI result, code contribution, test, or scientific claim is correct.

**Rationale:** Ledgers can preserve signed claims and settlement history, but truth about external computation requires tests, independent reproduction, trusted measurement, or other verification mechanisms.

**Consequence:** Verification remains a more fundamental subsystem than blockchain. Any future smart-contract reward mechanism must consume externally produced verification evidence.

## 2026-08-28 — Earn scale through staged experiments

**Decision:** Use `ROADMAP.md` as the current staged research direction: experimental kernel -> single-machine multi-agent tests -> 3–10-node local mesh -> 10–20-laptop verification swarm -> decentralized/churn tests -> adversarial security -> hierarchical 100+ node mesh -> optional distributed learning -> cross-organization federation -> optional economy -> Internet-scale research.

**Rationale:** This sequence tests the central hypotheses at the smallest useful scale while preserving a path to the long-term vision.

**Consequence:** The immediate engineering backlog begins with Work Unit, Result Manifest, and Goal Graph schemas, a discrete-event simulator, a metrics harness, and baseline scheduling/aggregation algorithms rather than a large production network.

## 2026-08-28 — Prefer a constitution over a complete specification

**Decision:** IDKMesh may begin without a precise final product specification, but it must operate inside explicit slow-changing constitutional constraints and minimum viability criteria.

**Rationale:** Natural self-organizing and evolutionary systems demonstrate that global complexity can emerge without a central blueprint, but not without rules, constraints, feedback, resource limits, and selection. Randomness provides variation; it does not provide correctness.

**Consequence:** Define hard or slow-changing rules for sandboxing, provenance, reproducibility, independent verification, resource budgets, rollback, critical invariants, and safe self-modification. Allow product goals, architectures, and strategies to remain mutable inside that envelope.

## 2026-08-28 — Co-evolve goals and solutions

**Decision:** Treat the Goal Graph itself as an adaptive system. Solutions may modify confidence in existing goals, reveal new goals, invalidate assumptions, or create new product directions.

**Rationale:** With genuinely vague objectives, a fixed objective function can encode the wrong problem. IDKMesh should learn what is worth optimizing while also learning how to optimize it.

**Consequence:** Model goal state as evidence-conditioned and versioned rather than as one immutable scalar fitness function. Preserve historical goals and the evidence that caused transitions.

## 2026-08-28 — Preserve niches with Quality-Diversity mechanisms

**Decision:** During high uncertainty, preserve multiple viable, high-quality behavioral/design niches instead of selecting one global winner prematurely.

**Rationale:** Novelty Search and Quality-Diversity research show why divergent exploration can outperform aggressive convergence when objectives are deceptive or incomplete. Natural evolution also diversifies across ecological niches rather than converging toward one organism.

**Consequence:** Experiment with MAP-Elites/Quality-Diversity archives, Pareto selection, novelty metrics, local competition, and diversity quotas for architectures, agents, workflows, and goal interpretations.

## 2026-08-28 — Randomness generates proposals, never acceptance

**Decision:** Stochasticity is an exploration mechanism only. Random or mutated artifacts must pass viability, independent verification, and evidence gates before integration or propagation.

**Rationale:** Randomness can escape local optima and generate novelty, but unfiltered randomness creates noise and failure rather than useful emergence.

**Consequence:** Every generative loop must be paired with negative feedback, verification, resource caps, correlation penalties, rollback, and measurable stopping/selection conditions.

## 2026-08-28 — Evaluator sovereignty: bind verifier control to exact work

**Decision:** A worker must not control the evaluator used to judge its own candidate. Verifier control must be represented by a separate, content-addressed `EvaluatorPlan` bound to the exact WorkUnit and source revision.

**Rationale:** Keeping verifier policy outside the candidate workspace is necessary but insufficient. A stale, substituted, or incomplete evaluator can still judge the wrong work, omit a required validator, or make a replay unable to prove which evaluator configuration produced the result.

Let:

`H_W = SHA256(canonical_json(WorkUnit))`

`H_E = SHA256(canonical_json(EvaluatorPlan))`

`V_W = RequiredValidatorIDs(WorkUnit)`

`V_E = EvaluatorPlan.required_validator_ids`

The pre-verification invariant is:

`EvaluatorPlan.work_unit_digest = H_W`

`EvaluatorPlan.source_revision = ResultManifest.source_revision`

`V_E = V_W`

`EvaluatorPlan.verifier.id != ResultManifest.worker.id`

and evaluator control/output remain outside the candidate workspace. The resulting `VerificationResult` records `H_E` as verifier-configuration provenance.

**Consequence:** Evaluator drift and validator-coverage loss fail closed before positive decision support. The current implementation wraps the existing metadata-only local verifier; it does not execute candidate code, satisfy Docker gate #37, or grant merge authority. See `docs/decisions/ADR-0009-evaluator-sovereignty.md` and `docs/research/EVALUATOR_PLAN_BINDING.md`.
