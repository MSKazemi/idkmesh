# IDKMesh Architecture — Working Draft

This document is intentionally provisional. IDKMesh is still exploring its product and research boundaries.

## Core abstraction

Represent the project as interacting graphs rather than a single queue of tasks.

### Goal / knowledge graph
Nodes may represent goals, requirements, hypotheses, assumptions, evidence, questions, decisions, artifacts, tests, failures, and unresolved conflicts.

### Work graph
Nodes represent tasks such as decomposition, implementation, review, verification, benchmarking, documentation, integration, and deployment. Edges encode dependencies and information flow.

### Participant / capability graph
Humans, AI agents, tools, and compute nodes expose capabilities, trust signals, availability, cost, latency, and resource limits.

## Candidate control loop

`uncertain goal -> competing decompositions -> task market/scheduler -> execution -> independent verification -> evidence update -> integration/rejection -> new questions`

## Candidate layers

1. **Identity & capability** — participant identity, model/tool identity, hardware capabilities, permissions, reputation.
2. **Knowledge & provenance** — goals, hypotheses, evidence, decisions, lineage, uncertainty.
3. **Task graph** — decomposed work, dependencies, priorities, verification requirements.
4. **Matching & scheduling** — assign work by capability, cost, diversity, information value, reliability, and locality.
5. **Execution mesh** — laptops, servers, clusters, cloud, edge, volunteer resources.
6. **Verification** — tests, reviews, adversarial agents, reproducibility, formal checks where feasible.
7. **Integration** — version control, CI/CD, release engineering, rollback, observability, supply-chain security.
8. **Governance & incentives** — decision processes, reputation, conflict resolution, anti-Sybil controls, contribution accounting.

## Scaling principle

Do not assume every participant communicates with every other participant. Hierarchical, federated, gossip, sharded, and locality-aware structures will likely be necessary to keep communication complexity bounded.

## Quality principle

Generation and verification must be separate roles. A proposal should not gain trust merely because many correlated agents repeat it. Verification should preferentially use independent methods, diverse models, different prompts/toolchains, reproducible tests, and evidence.

## First prototype target

Start with a single-machine simulation containing many logical agents and a task/evidence graph. Prove useful coordination and verification rules before attempting wide-area distributed execution.
