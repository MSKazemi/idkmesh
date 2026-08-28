# IDKMesh Constitution — v0.1

IDKMesh intentionally allows goals, hypotheses, algorithms, contributors, AI agents, and implementation details to evolve. That flexibility requires a smaller set of rules that are harder to change than ordinary project state.

This document defines candidate **constitutional invariants** for experiments and early implementations. It is not a claim that these rules are complete. Amendments should require explicit rationale, evidence, review, and a migration/rollback plan.

The central design principle is:

> **The destination may be uncertain; the laws governing exploration must not be.**

A nature-inspired system should use randomness for variation and evidence for propagation.

---

## Law 1 — Proposal is not proof

No human, AI agent, model, contributor, vote, reputation score, or popularity signal can make a claim correct merely by asserting it.

A proposal may gain status through reproducible evidence, independent verification, formal constraints where appropriate, and explicit human judgment for value-laden decisions.

**Implication:** generation and verification must remain distinguishable roles.

---

## Law 2 — Randomness creates variation, never authority

Random mutation, sampling, novelty search, stochastic scheduling, evolutionary search, and exploratory agents may create candidate ideas or implementations.

Randomness alone must never authorize:

- integration into protected code;
- security-sensitive execution;
- irreversible state change;
- policy amendment;
- resource escalation;
- release/deployment.

**Implication:** `random candidate -> evidence -> verification -> possible promotion`, never `random candidate -> trust`.

---

## Law 3 — Hard invariants precede soft objectives

The project may optimize many uncertain or changing objectives, but hard constraints are evaluated first.

Examples include:

- sandbox boundaries;
- secrets isolation;
- resource ceilings;
- required tests;
- provenance requirements;
- protected interfaces;
- privacy constraints;
- license constraints;
- explicit human-control boundaries.

A candidate that violates a hard invariant is not rescued by a high optimization score.

---

## Law 4 — Preserve uncertainty explicitly

IDKMesh must be able to represent:

- unknowns;
- confidence;
- competing hypotheses;
- contradictory evidence;
- unresolved requirements;
- alternative architectures;
- assumptions;
- risks.

The system should not manufacture false consensus merely to simplify coordination.

**Implication:** use Goal Graph state rather than forcing all uncertainty into one roadmap or scalar objective.

---

## Law 5 — Preserve useful diversity while uncertainty is high

A single currently successful strategy must not automatically consume all resources.

The system should maintain protected exploration capacity for sufficiently different viable approaches, especially when:

- goals are changing;
- evidence is weak;
- errors are correlated;
- the search landscape is deceptive;
- architectural lock-in would be expensive.

Diversity must still satisfy viability and safety constraints; random noise is not automatically useful diversity.

---

## Law 6 — More agents do not imply more truth

Raw contributor count, model count, task count, votes, stars, tokens, or compute hours are not quality measures.

Aggregation should account for:

- competence;
- calibration;
- independence;
- correlated failure;
- specialization;
- reproducibility;
- adversarial behavior.

Where possible, verify claims by methods that fail differently from the generator.

---

## Law 7 — Workers do not trust jobs; coordinators do not trust workers

Every Work Unit is potentially hostile to the executing node, and every returned result is potentially incorrect or malicious.

Early implementations should default toward:

- least privilege;
- sandboxing;
- no ambient secrets;
- explicit network policy;
- content hashing;
- reproducible environments;
- independent verification;
- signed/attributed provenance where practical;
- redundant execution for high-risk claims.

Trust may reduce verification cost but should not erase verification for critical operations.

---

## Law 8 — Evidence and lineage are shared memory

The mesh must remember more than winners.

Preserve, where useful and lawful:

- failed experiments;
- negative results;
- rejected designs;
- benchmark configurations;
- random seeds;
- environment information;
- test evidence;
- artifact hashes;
- decisions and their rationale;
- superseded assumptions.

This prevents the network from repeatedly paying to rediscover known failures and enables future agents to challenge old conclusions.

---

## Law 9 — Prefer reversible evolution

Changes with uncertain consequences should be staged, observable, and reversible wherever feasible.

Mechanisms include:

- feature flags;
- canaries;
- branches;
- isolated experiments;
- versioned protocols;
- migration plans;
- rollback points;
- bounded blast radius.

Self-modification must not remove the mechanisms needed to inspect, stop, reproduce, or roll back the modification itself.

---

## Law 10 — Self-improvement has stronger gates than ordinary work

IDKMesh may eventually propose changes to its own schedulers, verifiers, reputation rules, governance, or constitutional processes.

Such changes require stronger review than ordinary Work Units because they alter the mechanism that judges future work.

At minimum, self-modifying policy experiments should have:

- an isolated evaluation environment;
- comparison against the incumbent mechanism;
- explicit adversarial tests;
- measurable success criteria;
- rollback;
- independent review;
- protection against changing the metric merely to make itself appear better.

---

## Law 11 — No permanent single master objective

IDKMesh should generally treat design as multi-objective optimization.

Relevant objectives may include:

- correctness;
- usefulness;
- safety/security;
- robustness;
- adaptability;
- privacy;
- cost;
- latency;
- energy;
- bandwidth;
- fairness;
- contributor experience;
- human attention.

Pareto trade-offs should remain visible. If a scalar score is used operationally, its weights and limitations should be explicit and revisable.

---

## Law 12 — Human values cannot be inferred from technical fitness alone

Tests and benchmarks can verify technical properties. They do not automatically determine what people should want.

For decisions involving social values, acceptable risk, rights, governance, community norms, or public impact, technical optimization must remain subordinate to explicit human governance and applicable law.

---

## Law 13 — Local comprehension, global composition

No single participant should be required to understand the entire future mesh.

Instead, the system should aim for:

> **Globally complex behavior assembled from locally bounded, inspectable, composable, and verifiable pieces.**

Interfaces, contracts, provenance, tests, and graph relationships are the tools that make this possible.

---

## Law 14 — Minimize required global coordination

Do not require every node to know every state or wait for every participant.

Prefer:

- asynchronous Work Units;
- local decisions;
- eventual consistency where valid;
- hierarchical summaries;
- compute islands;
- scoped consensus only where authoritative ordering is necessary.

This is both a scalability rule and a resilience rule.

---

## Law 15 — Resource allocation must retain exploration

Successful branches may receive more compute and attention, but resource allocation should protect some budget for:

- challengers;
- replication;
- novelty;
- high-information experiments;
- underexplored niches;
- independent verification.

This prevents a positive-feedback loop from turning an early local optimum into permanent monoculture.

---

## Law 16 — Optimize verified useful work, not activity

The network should not reward activity for its own sake.

Primary direction:

`Verified Useful Work / (Human Attention + Compute Cost)`

Supporting metrics should include reliability, post-integration defects, reproducibility, security findings, information gain, diversity, energy, latency, and uncertainty.

No metric is immune to Goodhart's Law. Important metrics must be periodically challenged.

---

## Law 17 — Scale claims must be earned

A mechanism validated on one laptop is not proven at one million nodes.

Use staged evidence:

`1 -> 10 -> 100 -> 10,000 -> 1,000,000`

At larger claimed scales, report assumptions about node count, churn, bandwidth, latency, failure domains, workload distributions, control-plane overhead, adversaries, and simulation-versus-real deployment.

---

## Law 18 — Negative results are first-class output

A failed algorithm, rejected analogy, scaling bottleneck, security flaw, or experiment showing no benefit is useful project knowledge.

IDKMesh should prefer an honest negative result over a flattering but irreproducible narrative.

---

# Constitutional layers

Not every rule needs the same permanence. A future governance model should distinguish:

1. **Constitutional invariants** — rare changes, strongest review.
2. **Protocol rules** — versioned and experimentally replaceable.
3. **Operational policies** — tunable based on current load/risk.
4. **Search state** — rapidly changing goals, tasks, hypotheses, priorities, and candidates.

This separation is analogous to giving an evolving system stable physics while allowing its organisms and behaviors to change.

---

# Candidate amendment process

Until governance is more mature, a constitutional amendment proposal should include:

1. the exact rule being changed;
2. motivation;
3. failure mode in the current rule;
4. alternatives considered;
5. threat/safety analysis;
6. experiments or evidence;
7. compatibility consequences;
8. rollback/migration plan;
9. public review period;
10. explicit maintainer approval.

Future IDKMesh governance may make this more distributed, but constitutional mutation should always be slower and more evidence-heavy than ordinary project mutation.

---

# Relationship to the Constitutional Evolutionary Mesh

The working architecture can now be stated compactly:

```text
uncertain needs
      |
      v
Goal Graph <------------------------------+
      |                                   |
      v                                   |
variation / proposals                     |
      |                                   |
      v                                   |
CONSTITUTIONAL VIABILITY GATES             |
      |                                   |
      v                                   |
competing viable niches                   |
      |                                   |
      v                                   |
work execution -> independent verification|
      |                                   |
      v                                   |
evidence / failures / provenance ----------+
      |
      v
resource reallocation + new questions
      |
      +------------> repeat
```

The system is allowed to say **"I don't know"** about the final architecture while remaining strict about how new knowledge earns trust.
