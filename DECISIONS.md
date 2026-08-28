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
