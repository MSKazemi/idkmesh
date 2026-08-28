# Conversation Record — GitHub-Constrained Self-Improving Community

**Date:** 2026-08-28

## Project-owner direction

The project owner emphasized that IDKMesh should not merely have community-growth documentation. The community itself should become **self-improving**, using formulas inspired by biology, politics, adversarial/war strategy, mathematics, physics, statistical physics, and carefully bounded quantum-inspired ideas.

A practical constraint was also made explicit: the implementation currently lives inside GitHub and is therefore limited by GitHub Actions, comments/notifications, permissions, event semantics, and API/platform restrictions.

## Working conclusion

The correct architecture is not an unrestricted recursive automation loop such as:

```text
event -> comment -> event -> comment -> ...
```

Instead, ACE should operate in **generations**:

```text
many GitHub events
    -> one quiet evidence/state ledger
    -> periodic generation evaluation
    -> choose mode and strategy
    -> at most a very small number of public actions
    -> observe verified descendants
    -> update strategy fitness
    -> next generation
```

This makes GitHub's constraints part of the system model rather than an obstacle to be ignored.

## Mathematical synthesis

### Biology/ecology

Use a community reproduction number:

```text
R_c(W) = verified descendants / verified parents
```

combined with a carrying-capacity gate:

```text
C(L) = 1 / (1 + exp((L-K)/tau))
```

so growth pressure falls when review/verification capacity becomes saturated.

### Evolution

Maintain multiple community-growth strategies with weights `w_i` and update those weights from measured descendant fitness:

```text
w_i* = w_i * exp(eta * (f_i - mean_fitness))
```

then normalize and add mutation/exploration:

```text
w_i' = (1-mu) * normalize(w_i*) + mu/n
```

The fitness target is verified descendant value per scarce reviewer/maintainer attention, with penalties for added latency and noise.

This is the mechanism by which the community algorithm can improve itself rather than merely execute fixed rules forever.

### Statistical physics

Use an exploration temperature `T` and softmax strategy selection:

```text
P(i) = exp(f_i/T) / sum_j exp(f_j/T)
```

Higher uncertainty can justify higher temperature and more diverse experiments. Higher evidence or review pressure can justify lower temperature and more consolidation.

### Information theory

Growth Seeds should be prioritized by expected useful information gain and downstream impact relative to human attention and friction.

### Political science

Use two independent gates for amplification:

1. evidence/verification gate;
2. community-capacity/governance gate.

Popularity alone should never satisfy either gate. Future cells/subprojects may use polycentric local governance while sharing constitutional security/provenance rules.

### Adversarial / Red Queen / OODA inspiration

Successful capabilities should periodically generate bounded challenge, reproduction, security-review, or regression-test opportunities. The useful military-style inspiration is the evidence loop:

```text
Observe -> Orient -> Decide -> Act -> Observe
```

not conflict between contributors.

### Quantum-inspired ideas

GitHub Actions are classical computation. IDKMesh should make no claim of quantum computation.

The useful analogy is to keep multiple policy hypotheses alive until evidence justifies convergence. This can be implemented honestly as a classical probability distribution with entropy/Bayesian or multiplicative-weights updates.

## GitHub constraints incorporated

Current GitHub documentation reviewed for the design states that:

- ordinary repository `GITHUB_TOKEN` REST requests are limited to 1,000 requests/hour/repository;
- secondary API limits include content-generation controls, documented in general around 80 content-generating requests/minute and 500/hour, with some endpoints lower and limits subject to change;
- most events caused by `GITHUB_TOKEN` do not recursively create new workflow runs, with documented exceptions/special cases;
- `pull_request_target` is privileged and must never be used to check out or execute untrusted PR code;
- comments create notifications and are therefore a poor primitive for event-by-event state updates;
- public repositories currently receive standard GitHub-hosted Actions usage without minute charges, but usage/platform limits still apply.

Therefore ACE should use **many observations but few public writes**.

## Durable design decision

The recommended next ACE version is a **generational controller** rather than a recursive event amplifier.

The controller should:

1. maintain compact state in the Growth Ledger;
2. measure real parent -> seed -> verified descendant links;
3. estimate `R_c`, review capacity, uncertainty, and strategy fitness;
4. update strategy weights with mutation/exploration;
5. choose among DORMANT / EXPLORE / GROW / CONSOLIDATE modes;
6. spend a strict automation/public-write budget;
7. create at most a small number of bounded public actions per generation;
8. treat "do nothing" as a valid output;
9. preserve human/security gates for high-impact actions.

## Repository changes from this conversation

Added:

- `docs/community/ACE_GITHUB_CONSTRAINED_EVOLUTION.md` — detailed constraint-aware mathematical design and implementation direction.

The active community-engine issue should reference this design as the next ACE direction.

## Immediate next step

Do not create a new large batch of Growth Seeds. The current bootstrap cohort already exists. First complete/validate the parent -> seed -> descendant evidence-link mechanism so ACE can learn from real outcomes rather than proxy activity credit.
