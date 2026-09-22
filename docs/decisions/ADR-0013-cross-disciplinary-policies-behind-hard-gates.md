# ADR-0013 — Cross-disciplinary algorithms remain optional policies behind hard gates

**Status:** Proposed  
**Date:** 2026-09-22

## Context

IDKMesh intentionally studies mechanisms from biology, ecology, economics, physics, control theory, and complex systems.

Examples already include:

- ACO/stigmergic routing;
- homeostatic regulation;
- Quality-Diversity;
- verification backpressure;
- Adaptive Verification Ecology;
- Physarum-inspired adaptive compute routing;
- ACE evolutionary/community controllers.

These mechanisms can improve exploration, adaptation, resource allocation, resilience, or diversity. They can also create herding, reward hacking, over-exploration, excess review cost, unstable feedback, or opaque policy behavior.

The scientific origin of a mechanism is not evidence that it is correct for software-development coordination.

IDKMesh also has hard authority and safety boundaries that must not become tunable outputs of an adaptive controller.

## Decision

Cross-disciplinary algorithms are **optional policy layers operating inside a feasible set defined by hard gates**.

Conceptually:

```text
constitutional / repository constraints
        |
        v
hard feasibility and authority gates
        |
        v
eligible action set
        |
        v
optional learned / nature-inspired policy
        |
        v
recommendation or bounded action
        |
        v
verification / evidence
        |
        v
explicit integration authority
```

An adaptive mechanism may rank, sample, allocate, or recommend among already eligible choices.

It may not create eligibility.

## Hard constraints outside adaptive authority

At minimum, adaptive algorithms cannot relax:

- WorkUnit scope, permissions, or source binding;
- repository compute-spend policy;
- resource/compute admission;
- secret boundaries;
- minimum trust/security requirements;
- required validator coverage;
- EvaluatorPlan ownership and content binding;
- worker/verifier identity-separation requirements;
- branch protection;
- explicit human/governance merge/integration authority.

If the eligible set is empty, the correct outcome is no route/no action, not policy relaxation.

## Evidence rule

Every adaptive mechanism must progress through explicit maturity stages documented in:

`docs/algorithms/NATURE_INSPIRED_ALGORITHM_REGISTRY.md`

Promotion requires stronger evidence at each stage.

For the N2 -> N3 transition, adaptive mechanisms should use the common shadow-evidence contract from PR #637 / issue #636 so recommendations are frozen before outcomes, exact-revision/input-bound, and retrospectively joined without inventing the unexecuted counterfactual.

A mechanism must be removable if a simpler baseline matches its result.

## Interpretability rule

Each decision-support mechanism must expose enough state to answer:

- what hard constraints filtered the action set?
- what policy selected among the remaining choices?
- which evidence/state influenced the policy?
- what uncertainty or exploration was present?
- what resource cost did the policy trade for its benefit?
- what would have happened under a named baseline where feasible?

Opaque composite "swarm intelligence" scores are discouraged.

## No trust-by-identity rule

Provider, model, agent, organization, popularity, or family labels may be routing features, but they are not correctness evidence.

In particular:

```text
different family label != independent evidence
many reviewers          != many independent reviewers
popular route           != correct route
high probe score         != safe live verifier
```

Observed verified outcomes and measured failure dependence are preferred where available.

## Economic terminology rule

Internal shadow prices, utility, budgets, auctions, or market-like mechanisms do not grant financial authority.

Repository monetary policy remains a hard external constraint.

## Consequences

Positive:

- research can remain innovative without weakening safety/governance boundaries;
- algorithms can be compared and removed independently;
- negative results become actionable simplifications;
- subsystem ownership remains understandable;
- real deployment can begin in dry-run/explain mode.

Costs:

- some adaptive mechanisms will appear less powerful because they cannot alter hard constraints;
- experiments need stronger baselines and cost accounting;
- several policies may coexist rather than one global optimizer;
- promotion to live use is slower.

These costs are intentional.

## Related

- `SCIENTIFIC_FOUNDATIONS.md`
- `docs/algorithms/NATURE_INSPIRED_ALGORITHM_REGISTRY.md`
- ADR-0006 zero-project-spend compute
- ADR-0007 verification-debt backpressure
- ADR-0009 evaluator sovereignty
- PR #622 Adaptive Verification Ecology
- issue #621 AVE ablation
- PR #631 Physarum compute routing
- issue #630 Physarum stress testing
- PR #637 adaptive policy shadow contract
- issue #636 N3 real shadow cohort
