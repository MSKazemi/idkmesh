# Conversation record: how IDKMesh should improve its repository

**Date:** 2026-08-28

## Prompt

Clarify how the repository itself should be improved over time.

## Repository state inspected

The repository already contains:

- a community-first README and contribution path;
- a staged roadmap and evolution strategy;
- executable evolution scoring and state/event artifacts;
- ACE community-growth experiments and a public Growth Ledger;
- a canonical local-node integration path under PR #34;
- an independent Evidence Report proposal under PR #42;
- a proposal-first Repository Homeostasis Engine under PR #36;
- a GitHub Reflex Observatory under PR #43;
- multiple research/simulation branches;
- a current-priorities document that already identifies the dominant integration bottlenecks.

## Main conclusion

IDKMesh is no longer primarily constrained by a shortage of ideas. The dominant risk is proliferation: adding new algorithms, documents, protocols, and automation faster than existing work is integrated, independently verified, measured, and made usable by external contributors.

The improvement strategy should therefore be **convergence before expansion**.

A repository iteration is defined as:

```text
observe
 -> identify dominant bottleneck
 -> choose bounded intervention
 -> implement as reviewable proposal
 -> verify
 -> integrate or reject
 -> measure outcome
 -> update project memory/priorities
```

A GitHub event by itself is not improvement.

## Working definition of improvement

Evaluate repository changes across multiple dimensions:

- verified useful capability;
- verification strength;
- safety;
- reproducibility;
- community accessibility;
- maintainability;
- interoperability;
- evidence quality;
- review scalability;
- community reproduction;
- research value.

Penalize added complexity, reviewer attention, operational cost, coordination risk, protocol duplication, security risk, and irreversibility.

Working north star:

```text
verified useful improvement
---------------------------------------
human attention + compute + complexity
```

Hard safety/governance constraints take precedence over this heuristic.

## Immediate repository direction

The current sequence should remain approximately:

1. protect canonical `main` integration (#35);
2. synchronize, runtime-test, review, and integrate canonical local node PR #34 / #37;
3. retire or split obsolete competing node/protocol work (#21);
4. complete independent verifier/evidence separation (#5, PR #42);
5. complete the local multi-worker Verified Swarm Runner (#4, #16);
6. merge deterministic observability before self-writing (#36/#20 and related GitHub observatory work);
7. unify repository, GitHub collaboration, verification, and community-capacity evidence into one guarded evolution state (#46 direction);
8. make ACE learn from verified parent -> descendant lineage (#25/#26) rather than raw activity;
9. publish one reproducible diversity + verification flagship experiment (#2/#30);
10. use measured results to justify future scheduling, randomness, autonomy, federation, and scale work.

## Durable artifact created

`docs/planning/REPOSITORY_IMPROVEMENT_LOOP.md` now defines the repeatable operating contract for future IDKMesh repository iterations.

It is intentionally linked from `docs/planning/CURRENT_PRIORITIES.md` rather than replacing the live backlog.
