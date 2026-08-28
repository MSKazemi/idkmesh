# Project Turn: Strong Evolution Action and Chat Propagation

**Date:** 2026-08-28

## Project-owner direction

The project owner asked IDKMesh to continue repository work, open an issue whenever an important action cannot be completed directly, build a much stronger GitHub Action grounded in the mathematical/biological/social/physics-inspired algorithms discussed throughout the project, and continue preserving the useful parts of substantive project chats in the public repository.

## Repository inspection

The current repository was re-read before proposing another controller.

Important observations:

1. `PROJECT_RULES.md` already makes same-turn chat-to-repository preservation a standing public rule.
2. The canonical `IDKMesh Evolution Loop` already exists and should be upgraded rather than duplicated.
3. The old loop applied event priors to `state/evolution-state.json` inside the ephemeral runner, but did not persist that modified state back to the repository. The next run therefore began again from the checked-in baseline.
4. The project already learned through ACE that cumulative historical activity is a poor proxy for current carrying capacity; live/recoverable state is preferable.
5. Public GitHub branch metadata still reports `main` as unprotected. Issue #35 remains the external administrative safety gate.
6. The repository has continued to advance: real multi-attempt node/evaluator/report/replay evidence now exists, while PR #91 still intentionally requires a genuinely separate human reviewer.

## Decision

Upgrade the existing evolution loop into a **read-only Repository Evolution Observatory v1** rather than creating another write-capable self-evolution controller.

The observer recomputes current repository state every run and produces inspectable recommendation artifacts.

No automatic merge, branch mutation, issue creation, governance modification, or execution of untrusted GitHub text is introduced.

## Algorithms integrated

### Ecological carrying capacity

Reuse ACE `live-open-work-v1` and its logistic carrying-capacity governor.

### Information theory

Use normalized Shannon entropy as a bounded work-mix diversity signal.

### Graph theory

Use deduplicated same-repository issue/PR references as a coordination/dependency graph. Reference centrality is treated only as an unblock proxy, never correctness evidence.

### Evolutionary dynamics

Use one deterministic replicator-mutator response over `protect / verify / consolidate / integrate / onboard / explore / maintain`, preserving a mutation/exploration floor.

This is a current-state response, not a claim of learned historical fitness.

### Feedback control

Aggregate normalized safety/capacity/review/community/supply-chain deficits into a weighted squared control-energy proxy. This is explicitly not a Lyapunov proof.

### Multi-objective scheduling

Rank bounded recommendations by expected value, evidence confidence, dependency unlock, community leverage, reversibility, reviewer attention, complexity, coordination cost, and risk.

Hard invariants always override the scalar ranking.

## Anti-Goodhart decision

The repository evolution fitness deliberately excludes:

- stars;
- forks;
- reactions;
- raw comment volume;
- raw commit volume.

High activity may be useful discovery evidence but does not establish correctness, community reproduction, or verified improvement.

## Security design

Pull-request metadata observation uses `pull_request_target`, so both the live workflow definition and checked-out observer implementation come from the trusted default branch; no PR-head code is executed there.

The live collector receives only `contents: read`, `issues: read`, and `pull-requests: read`, and stores no issue/PR/comment bodies. Natural-language GitHub text remains untrusted.

A separate ordinary `pull_request` job runs deterministic PR-head tests with only contents-read authority, persisted checkout credentials disabled, and no repository token/secrets explicitly exported to the test process. The live API observer is disabled in that PR-controlled execution context.

The workflow's own dependencies are pinned to immutable reviewed SHAs. The new observer also measures pinning coverage across the rest of the repository workflows so supply-chain hardening becomes visible debt.

## GitHub-event / resource design

Rapid event storms should not create a backlog of obsolete evolution observations.

The trusted live observer uses one `evolution-observer` concurrency group with `cancel-in-progress: true`: current state wins over stale intermediate snapshots. PR-head checks use a separate per-PR concurrency group so proposed-code tests and trusted observation cannot cancel each other.

A quiet daily scheduled snapshot remains available for drift detection.

## Chat propagation decision

The project keeps the existing mandatory preservation rule.

For substantive turns, preserve useful material in two layers:

```text
conversation record under docs/conversations/
+
promotion into canonical architecture/planning/code/issues where the turn changes the project
```

The evolution observer can measure whether the rule/archive surfaces exist, but it must not claim it can detect an omitted chat that never reached the repository.

## Blocked/external actions

### Main protection

The connected repository tools cannot configure the required GitHub branch/ruleset administration safely in this turn. Do not pretend repository files substitute for external enforcement.

Continue using issue #35 as the canonical admin gate rather than creating a duplicate issue.

### Separate human witness for PR #91

Automation cannot manufacture a genuinely independent human review. PR #91 should remain draft/blocked until another eligible person inspects its exact-head evidence.

The evolution observer should surface this as a bounded review recommendation, not self-approve it.

## Implementation artifacts

This turn proposes/implements:

- `.github/workflows/evolution-loop.yml` — trusted-default-branch live observer + token-minimal PR-head policy tests;
- `scripts/evolution_snapshot.py` — bounded GitHub/repository evidence collector;
- `scripts/evolution_score.py` — deterministic multi-algorithm scorer/recommender;
- `config/evolution-policy-v1.json` — inspectable bootstrap parameters;
- `tests/test_evolution_observer.py` — invariants and anti-Goodhart regression tests;
- `docs/architecture/REPOSITORY_EVOLUTION_OBSERVATORY.md` — normative design, formulas, security and falsification path;
- this public conversation record;
- a small planning-document link so the canonical improvement loop points at the executable observer.

## Verification performed before publication

The implementation was syntax-checked and the deterministic unit suite passed for:

- capacity recovery when open work decreases;
- GUARD mode when canonical integration is unprotected;
- normalized replicator weights with nonzero mutation floor;
- stronger consolidation pressure under high load;
- invariance to huge star/fork/comment-count changes;
- deduplication of repeated dependency references;
- detection of floating vs SHA-pinned GitHub Action dependencies;
- independent-review coverage calculation;
- lower control-energy proxy when guardrails/capacity/review/community/supply-chain state improves.

Repository-level CI remains the authoritative verification surface for the proposed branch/PR.

## Community impact

This change creates a public, falsifiable way for contributors to ask not merely “what should we build?” but:

> **What does the current evidence say is the highest-leverage bounded intervention, and which formula/proxy produced that recommendation?**

That makes the self-evolution logic challengeable and forkable rather than private or mystical.
