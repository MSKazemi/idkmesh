# IDKMesh: The 20 Most Important Questions

These questions should drive the project before implementation complexity outruns understanding. They are ordered roughly by dependency: later questions are harder to answer well if earlier ones remain vague.

## 1. What is the atomic unit of value?
Is IDKMesh producing code, verified patches, experiments, proofs, datasets, decisions, deployments, or a more general "validated artifact"? The platform needs a small unit that can be created, verified, composed, attributed, and rolled back.

## 2. What does "better with scale" mean?
What measurable property must improve as humans, agents, and compute nodes increase? Candidate metrics include validated-value throughput, defect rate, security findings, time-to-solution, cost per verified artifact, robustness, and information gain.

## 3. How do we decompose an ambiguous goal without freezing the wrong interpretation?
The task graph must support competing interpretations, hypotheses, architectures, and experiments before convergence. Decomposition itself should be reviewable and revisable.

## 4. How do we represent uncertainty explicitly?
Requirements, beliefs, confidence, assumptions, contradictions, open questions, and alternative branches should be first-class objects rather than hidden in chat history.

## 5. What is the smallest independently verifiable task?
A task should be small enough to parallelize but large enough that its output can be tested against an explicit contract. This granularity strongly controls coordination cost.

## 6. How are tasks matched to humans, AI agents, and compute?
Scheduling should consider capability, trust, cost, latency, data locality, energy, privacy, specialization, historical reliability, and expected information gain rather than only CPU/GPU availability.

## 7. How do we measure useful diversity and correlated error?
Ten agents using the same model, prompt, retrieval source, and assumptions may behave more like one agent than ten. IDKMesh needs diversity and correlation metrics so redundancy is real rather than cosmetic.

## 8. How much independent verification is enough?
Verification depth should depend on risk. Low-risk work may need one checker; security-critical or irreversible work may require heterogeneous redundant execution, adversarial review, formal methods, or human approval.

## 9. What is the threat model?
Which nodes are trusted, semi-trusted, unreliable, compromised, malicious, or Sybil identities? Different trust domains need different protocols. The system cannot choose consensus, sandboxing, reputation, or replication intelligently without an explicit adversary model.

## 10. Which state requires strong consistency, and which state can be eventually consistent?
Global consensus should be rare. Collaborative notes, presence, caches, and many task-state updates can often use CRDT/eventual-consistency approaches; irreversible permissions, release signatures, financial actions, and some governance decisions may need stronger guarantees.

## 11. How do we avoid all-to-all communication?
Any design whose hot path requires every participant to know about every other participant will fail long before millions of nodes. The network must use bounded peer sets, locality, hierarchy, federation, gossip, partitioning, and summaries.

## 12. How do we avoid a global scheduler bottleneck?
A single queue or scheduler becomes both a scalability ceiling and a failure domain. Scheduling must become hierarchical or federated: local schedulers make most decisions; higher layers exchange only aggregate demand, capability, and overflow information.

## 13. What moves: data, code, models, or tasks?
Moving terabytes to idle compute may be worse than moving a small task to where data already lives. The system needs explicit locality and placement rules, content-addressed artifacts, caching, replication, and cost-aware movement.

## 14. How does the system behave under churn, partitions, and offline operation?
Nodes will disappear mid-task. Networks will partition. Laptops will sleep. Every task and protocol should define timeout, retry, checkpoint, idempotency, duplicate handling, reconciliation, and eventual recovery semantics.

## 15. How do we safely execute untrusted work while protecting data and users?
The design needs sandboxing, capability-scoped credentials, secret isolation, provenance, software-supply-chain verification, resource quotas, network policy, privacy boundaries, and data-sovereignty constraints.

## 16. How do we reward contribution without making the system easy to game?
Reputation, recognition, reciprocal compute, access, money, or tokens can all create unintended incentives. The mechanism should reward verified marginal value rather than volume, popularity, or raw activity, and must resist Sybil and collusion attacks.

## 17. Which decisions are local, delegated, experimental, or global?
The governance model should minimize global decisions. Cells and subsystems should have autonomy within explicit contracts, while a small constitutional layer defines interoperability, safety, identity, and release rules.

## 18. How can the protocols evolve without slowing the project down?
Schemas, APIs, schedulers, validators, and governance mechanisms must be versioned and replaceable. IDKMesh should support shadow implementations, canaries, feature flags, contract tests, compatibility windows, and rapid rollback.

## 19. How do we observe, debug, and explain a system with millions of participants?
Raw centralized telemetry will not scale. The system needs hierarchical metrics, sampling, trace summaries, provenance graphs, local debugging, privacy-preserving aggregation, and clear failure-domain boundaries.

## 20. What evidence would falsify the project thesis?
IDKMesh should define stopping conditions. For example: if quality does not improve after controlling for compute budget; if coordination cost grows faster than validated value; or if trust/security overhead makes open participation uneconomic. A serious research project must be able to discover that some parts of its hypothesis are wrong.

# Priority grouping

## P0 — must answer before architecture hardens
1, 2, 3, 5, 7, 8, 10, 11, 12, 20.

## P1 — required before open multi-party deployment
6, 9, 13, 14, 15, 19.

## P2 — required before large community scale
4, 16, 17, 18.

# Recommended north-star metric

A useful candidate is **Validated Value Throughput (VVT)**:

`VVT = verified useful artifacts / (wall-clock time * normalized cost)`

This should be accompanied by quality and safety guardrails, because maximizing throughput alone would reward low-value or low-risk work.

Suggested guardrails:

- escaped-defect rate;
- verification failure rate;
- rollback rate;
- security incident rate;
- median and p95 task latency;
- human-review burden;
- coordination messages or bytes per verified artifact;
- cross-cell traffic per artifact;
- effective diversity / error correlation;
- contributor onboarding time;
- recovery time after node/cell failure.

The important question is not "how many agents can we run?" It is "how much independently verified useful value does each additional unit of coordination and compute create?"
