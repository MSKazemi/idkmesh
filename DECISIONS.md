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
