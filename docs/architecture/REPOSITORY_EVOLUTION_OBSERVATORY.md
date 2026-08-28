# Repository Evolution Observatory — Persistent Kernel + Live Governor

**Status:** proposed convergence architecture  
**Date:** 2026-08-28  
**Authority:** observe / recommend only

## Purpose

IDKMesh now has a strong mathematical evolution core on `main` from PR #137: persistent trusted-main Bayesian checkpoints, correlation-aware verification evidence, Pareto/NSGA diversity preservation, UCB and multiplicative-weights experiment allocation, graph unlock value, entropy/JSD diversity, and Lyapunov-style homeostasis.

The remaining repository-level problem is different:

> Historical evidence must not override current hard constraints.

A repository can have an improving Bayesian posterior while `main` is still unprotected, independent review is missing, or the review queue is saturated. The canonical evolution loop therefore needs two complementary state layers:

```text
persistent historical evidence kernel
        +
recomputed current repository governor
        |
        v
conjunctive recommendation / guard surface
```

The live governor does **not** replace the mathematical kernel. It constrains it.

## Why two state layers

### Persistent kernel

The merged Mathematical Evolution Kernel is appropriate for questions such as:

- what evidence has accumulated over iterations?;
- how uncertain are our beliefs?;
- how correlated are verification signals?;
- which experiments preserve Pareto diversity?;
- how should exploration/exploitation evolve?;
- did a proposed update improve a Lyapunov-style homeostatic potential?

### Live governor

The live governor answers questions that must be recomputed from the current repository:

- is the canonical branch actually protected now?;
- how many review-ready vs draft PRs exist now?;
- how much reviewer capacity is currently available?;
- do review-ready PRs have independent reviewers?;
- is there a bounded newcomer task surface?;
- is there an external public witness/participant signal?;
- are checked-in GitHub Actions dependencies pinned to immutable SHAs?;
- is branch proliferation creating coordination pressure?

These signals are intentionally recoverable. When open work decreases, pressure must decrease.

## Live evidence collector

`scripts/evolution_snapshot.py` collects bounded public/repository metadata and emits `results/evolution/repository-snapshot.json`.

It records:

- default-branch protection boolean;
- open issues and PRs;
- PR draft state;
- independent reviewer/approver counts;
- labels;
- bounded/deduplicated same-repository `#N` references;
- distinct non-owner/non-bot participants observed in open work, recent merged work, reviews, and a bounded recent comment window;
- branch count;
- workflow dependency pinning;
- project conversation-record count and the presence of the mandatory chat-preservation rule.

### Untrusted text rule

Issue, PR, and comment natural language is **not retained** in the generated snapshot. Bodies are treated as untrusted input. Only bounded numeric references and structural metadata are extracted.

The project-memory check makes a deliberately weak claim: it can confirm that repository archive/rule surfaces exist, but it cannot prove that a conversation which was never committed does not exist. Same-turn preservation remains a project behavior/governance responsibility.

## Ecological carrying capacity

Reuse the accepted ACE live-open-work model:

```text
L =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_issues, 20)

Capacity(L) = 1 / (1 + exp((L-K)/tau))
```

Bootstrap parameters remain `K=8`, `tau=2` until reviewer-latency/backlog evidence justifies recalibration.

The required invariant is:

```text
open work falls -> L falls -> Capacity(L) recovers
```

## Current-state Shannon diversity

The persistent kernel already measures event/actor diversity. The live governor measures a different quantity: **the current mix of open work**.

Open items are mapped to coarse inspectable classes such as verification, community, research, maintenance, governance, product, and other. The governor reuses the canonical `normalized_entropy()` primitive from `scripts/evolution_math.py`.

This is a diagnostic signal, not a target saying more diversity is always better.

## Live homeostatic potential

The governor reuses the canonical `homeostatic_potential()` primitive from the Mathematical Evolution Kernel.

Current signals include:

```text
main_protection
review_capacity
independent_review_coverage
starter_task_supply
external_witness
workflow_pin_ratio
branch_health
```

A weighted normalized squared distance from configured healthy targets produces a live potential. Lower is directionally healthier under the current bootstrap policy.

This remains a control proxy, not a proof of repository stability.

## Conjunctive modes

The live governor can emit:

```text
GUARD
CONSOLIDATE
VERIFY
ONBOARD
INTEGRATE
EXPLORE
```

Hard/current rules have priority:

- unprotected canonical branch -> `GUARD`;
- exhausted capacity / excessive review-ready queue -> `CONSOLIDATE`;
- review-ready work without adequate independent review -> `VERIFY`;
- healthy capacity but insufficient newcomer/external witness surface -> `ONBOARD`;
- healthy reviewed queue -> `INTEGRATE`;
- otherwise -> `EXPLORE`.

The governing rule is:

> Persistent Bayesian/evolutionary evidence may inform recommendations, but a current hard guard cannot be compensated by historical fitness.

No mode is merge authority.

## Anti-Goodhart boundary

The live governor ignores the following as fitness inputs:

- stars;
- forks;
- reactions;
- raw comments;
- raw commits.

They can be useful discovery context elsewhere, but they do not establish correctness, verified improvement, or independent community reproduction.

## GitHub Actions trust boundary

### Trusted live observation

Pull-request metadata observation uses `pull_request_target` so the workflow definition comes from the default branch. The job then explicitly checks out the default branch and never checks out or executes PR-head code.

The live job has only:

```text
contents: read
issues: read
pull-requests: read
actions: read
```

`actions: read` exists only because the persistent kernel restores the previous trusted-main checkpoint artifact. There are no contents/issue/PR/settings write permissions.

### Proposed-code verification

A separate ordinary `pull_request` execution tests the proposed PR head with only `contents: read`; checkout credentials are not persisted and no repository token/secrets are explicitly exported to the test process. The live API observation job is disabled in this PR-controlled context.

### Immutable workflow dependencies

The evolution workflows pin external actions to immutable commit SHAs. The live collector also measures pinning coverage across all checked-in workflows so broader supply-chain debt becomes visible rather than silently rewritten.

## Persistent checkpoint + current snapshot

Each trusted observation run:

1. restores the latest successful trusted-main Bayesian checkpoint when available;
2. applies the normalized event as soft evidence through the existing scorer;
3. independently collects the current repository snapshot;
4. evaluates the live governor;
5. publishes both historical and current-state evidence in one checkpoint artifact.

The artifact includes:

```text
EVOLUTION_REPORT.md
state/evolution-state.json
state/evolution-events.jsonl
state/evolution-math-policy.json
state/evolution-live-policy.json
results/evolution/repository-snapshot.json
results/evolution/live-governor.json
results/evolution/LIVE_GOVERNOR_REPORT.md
```

The workflow remains read-only with respect to repository content.

## Event backpressure

Trusted live observations share `evolution-observer` with `cancel-in-progress: true`:

```text
many rapid events -> discard stale observation run -> compute newest state
```

PR-head tests use a separate per-PR concurrency group, so proposed-code verification cannot cancel trusted observation and vice versa.

A daily scheduled run supplies a quiet drift baseline.

## Relationship to IDKGraph / ACE

This is not another community controller.

- the Mathematical Evolution Kernel owns persistent uncertain evidence and allocation primitives;
- ACE owns community reproduction/lineage policy;
- branch convergence owns detailed branch lifecycle classification;
- verifier/evaluator workflows own correctness evidence;
- the live governor supplies current repository constraints to the repository-level evolution loop.

The long-term direction remains issue #46:

```text
RepositoryGraph U GitHubCollaborationGraph U EvidenceGraph
 -> guarded evolution policy
```

Any future actuator still requires external GitHub protection (#35), explicit activation gates, deduplication/rate limits, and a prohibition on self-approval/self-merge.

## Falsification and calibration

Treat the live policy as wrong or incomplete when evidence shows, for example:

- carrying capacity does not predict review latency/backlog;
- the live potential falls while coordination burden worsens;
- open-work entropy provides no useful diagnostic value;
- branch pressure is poorly calibrated;
- participant/starter signals do not predict community return or verified descendants;
- pin ratio is already covered better by another canonical security metric.

Negative results should be retained. Parameters should move from bootstrap hypotheses to empirically calibrated values only after outcome evidence exists.

## Community impact

The combined observer is designed to make self-evolution understandable:

- historical beliefs remain explicit and uncertain;
- current guards are recomputed from public state;
- formulas and parameters are versioned;
- authority limits are explicit;
- every recommendation can be challenged by changing a metric, test, calibration, or evidence source rather than trusting a hidden agent.
