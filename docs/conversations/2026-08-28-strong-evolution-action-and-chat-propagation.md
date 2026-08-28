# Project Turn: Strong Evolution Action, Convergence, and Chat Propagation

**Date:** 2026-08-28

## Project-owner direction

Continue professional repository work; if an important action cannot be completed directly, make the blocker public as an issue; strengthen the GitHub-native evolution system using the mathematical/biological/social/physics-inspired algorithms discussed throughout IDKMesh; and keep preserving useful chat-derived decisions/results in the public repository.

## Initial repository finding

The existing `IDKMesh Evolution Loop` was inspected before creating another controller.

At the beginning of the turn its checked-in event scorer mutated `state/evolution-state.json` only inside an Actions runner. That original form did not persist the mutation back to durable repository memory, so it motivated a live-state redesign.

A first review branch/PR (#139) was prepared around a recomputed repository snapshot, ecological carrying capacity, Shannon work diversity, graph references, a replicator-mutator response, and a feedback-control deficit proxy.

## Important concurrency / convergence event

While #139 was being prepared, `main` advanced through PR #137: **Mathematical Evolution Kernel + persistent Bayesian observer**.

That merged change solved a large part of the original weakness and did so with a stronger mathematical core:

- trusted-main persistent checkpoint artifacts;
- Bayesian soft-evidence beliefs and explicit uncertainty;
- correlation-aware verifier aggregation;
- Pareto / NSGA diversity preservation;
- UCB and multiplicative-weights experiment allocation;
- graph unlock value;
- entropy/JSD primitives;
- Lyapunov-style homeostatic potential.

The correct response was **not** to overwrite #137 with another scorer.

The project therefore changed course and rebuilt the work on a clean current-`main` branch as a complement to #137.

## Converged architecture

The canonical direction is now:

```text
persistent mathematical evolution kernel (#137)
        +
recomputed live repository governor
        |
        v
conjunctive guarded recommendation surface
```

The persistent kernel answers historical/uncertainty/allocation questions. The live governor answers current-state questions that should recover or change immediately with repository state.

## Live current-state signals

The new bounded collector/governor observes:

- actual default-branch protection state;
- live review-ready vs draft PR pressure;
- ACE-compatible carrying capacity;
- independent review coverage;
- bounded newcomer task supply;
- distinct non-owner/non-bot public participant/witness presence;
- current open-work Shannon diversity;
- GitHub Action immutable-SHA pin coverage;
- branch-count coordination pressure;
- project conversation archive/rule surfaces.

Issue/PR/comment bodies are not retained. Natural-language GitHub text remains untrusted; only labels and bounded same-repository numeric references are extracted as structural signals.

## Conjunctive safety decision

A historical Bayesian posterior cannot compensate for a current hard guard.

Examples:

```text
main unprotected -> GUARD
review capacity saturated -> CONSOLIDATE
review-ready work lacks independent review -> VERIFY
```

This prevents a high historical/evolution score from being interpreted as permission.

## Anti-Goodhart decision

The live governor deliberately ignores stars, forks, reactions, raw comment volume, and raw commit volume as fitness inputs. They may help discovery but do not establish correctness, independent verification, or verified community reproduction.

## Workflow security improvement

A subtle trust-boundary problem was identified during the turn: on an ordinary `pull_request` event, proposed workflow YAML can control the workflow execution. For that reason, the live observer must not receive its API/checkpoint token in a PR-controlled workflow definition.

The converged design separates contexts:

- `pull_request_target` -> trusted default-branch workflow definition + trusted default-branch observer code, metadata only, never PR-head execution;
- `pull_request` -> proposed-code deterministic tests only, minimal contents-read authority, persisted checkout credentials disabled, no live API observer.

The persistent checkpoint requires `actions: read`; the live collector additionally uses `contents: read`, `issues: read`, and `pull-requests: read`. There are no repository-write, issue-write, PR-write, settings-write, approval, or merge permissions.

## Supply-chain hardening

The evolution workflows' external action dependencies are moved to immutable current SHAs rather than floating major-version tags. The live collector also measures repository-wide workflow pinning so remaining supply-chain debt is visible.

## Event backpressure

Trusted live observations use a shared `evolution-observer` concurrency group with `cancel-in-progress: true`. Rapid event storms therefore converge to the newest state instead of spending compute retaining obsolete intermediate observations.

PR-head tests use a different per-PR concurrency group.

## Chat-to-repository propagation

The existing `PROJECT_RULES.md` mandatory preservation rule remains canonical.

Useful substantive turns should be preserved in two layers:

```text
docs/conversations/ structured turn record
+
promotion into canonical code/docs/issues when the turn changes the project
```

The live collector can confirm the archive/rule surface exists, but it cannot prove completeness for a chat that was never committed.

## External actions made public

### `main` protection

Public GitHub metadata still reports `main` unprotected. Existing issue #35 remains the canonical admin gate; it was updated during this turn instead of creating a duplicate.

### Independent human review for PR #91

Automation cannot manufacture the separate human witness required by the frozen canonical-node candidate. A bounded expert-review task was therefore opened as issue #138, pointing reviewers to exact-head CI, the controlled Docker matrix, retained negative evidence, and real evaluator evidence.

## Implementation artifacts on the converged branch

- `.github/workflows/evolution-loop.yml` — persistent Bayesian checkpoint + trusted live snapshot/governor + PR-head separation;
- `.github/workflows/mathematical-evolution-kernel.yml` — immutable dependency pins and reduced token permissions;
- `scripts/evolution_snapshot.py` — bounded public/repository metadata collector;
- `scripts/evolution_live_governor.py` — live carrying-capacity/homeostasis/guard layer reusing canonical `evolution_math` primitives;
- `state/evolution-live-policy.json` — inspectable bootstrap live-policy parameters;
- `tests/test_evolution_live_governor.py` — current-state, anti-Goodhart, capacity, review, pinning, and reference invariants;
- `docs/architecture/REPOSITORY_EVOLUTION_OBSERVATORY.md` — normative convergence architecture;
- this public turn record.

## Verification before repository CI

A local dependency-free test harness exercised the live governor against the same canonical `normalized_entropy()` and `homeostatic_potential()` semantics and passed seven invariants:

1. capacity recovers when open work decreases;
2. unprotected canonical integration is a hard `GUARD`;
3. independent-review coverage is measured live;
4. arbitrary popularity/activity counters cannot change the live decision;
5. homeostatic potential improves when protection/capacity/review/community/supply-chain guardrails improve;
6. workflow pin scanning distinguishes immutable SHA pins from floating refs;
7. repeated same-repository references are deduplicated.

Repository CI remains authoritative.

## Professional PR convergence decision

PR #139 should not be merged in its original form because it conflicts with and would partially replace the stronger mathematical core already merged in #137.

The clean replacement branch preserves #137 and contributes only complementary live-state/security/supply-chain behavior. Once the replacement PR exists and its diff/CI are verified, #139 should be closed as superseded with the convergence reasoning retained publicly.

## Community impact

The combined system is more useful to contributors than either a hidden autonomous agent or a single scalar score:

- historical evidence and uncertainty are explicit;
- current hard constraints are explicit;
- the formulas are public and testable;
- negative evidence is preserved;
- blocked actions become claimable public issues;
- no controller can declare itself authorized merely because its own metrics improved.
