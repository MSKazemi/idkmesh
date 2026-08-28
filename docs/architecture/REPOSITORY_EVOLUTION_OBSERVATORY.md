# Repository Evolution Observatory v1

**Status:** proposed canonical upgrade of the existing `IDKMesh Evolution Loop`  
**Date:** 2026-08-28

## Purpose

IDKMesh needs one repository-level feedback loop that can answer:

> **Given the current observable state, what bounded intervention is most likely to improve verified useful work without outrunning review, safety, or community capacity?**

The Observatory is an **observer and recommender**, not an autonomous integrator.

It upgrades `.github/workflows/evolution-loop.yml`; it does not introduce a second write-capable self-evolution controller.

## Core rule

The previous loop accumulated soft event evidence in a checkpointed state. That model remains useful as a mathematical/evidence experiment, but cumulative event state can be mistaken for current repository condition.

Repository Observatory v1 therefore evaluates a fresh bounded snapshot:

```text
current GitHub/repository snapshot
 -> deterministic measurements
 -> bounded mathematical response
 -> recommendation artifact
```

Every live observation recomputes current condition. Historical learning, when added, must be bound to explicit outcomes/lineage rather than hidden runner-local memory.

## Compatibility boundary: two models, two scorer modules

The repository deliberately keeps two different mathematical surfaces instead of overloading one CLI:

- `scripts/evolution_score.py` remains the **legacy Bayesian event/checkpoint scorer** used by the Mathematical Evolution Kernel and its existing reproducibility evidence;
- `scripts/repository_evolution_score.py` is the **stateless repository-snapshot scorer** used by Observatory v1;
- `scripts/evolution_snapshot.py` collects the bounded live snapshot consumed by the repository scorer.

This separation is intentional. A new repository-control model must not silently break the older mathematical evidence path, and the legacy event scorer must not be mistaken for current-state observation.

## Evidence collected

The live collector uses bounded repository/public metadata:

- whether the default branch is protected;
- open issues and pull requests;
- draft vs review-ready PR state;
- independent reviewer/approver counts on open PRs;
- bounded same-repository `#N` references;
- labels;
- distinct non-owner/non-bot public participants seen in the bounded observation windows;
- recent merged-PR count;
- branch count;
- immutable-SHA pin coverage in checked-in GitHub Actions workflows;
- public conversation-record count and presence of the chat-preservation project rule.

Natural-language bodies/comments are **not stored** in the artifact and are not executed or sent to an LLM. PR/issue body text is reduced only to deduplicated numeric same-repository references, capped at 32 per item.

The collector is also bounded by page/review caps. Truncation is retained as evidence rather than silently interpreted as completeness.

## Algorithm stack

These are inspectable engineering hypotheses, not claims that software repositories literally obey biological or physical laws.

### 1. Ecological carrying capacity

Reuse the ACE `live-open-work-v1` pressure model:

```text
L =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_issues, 20)

Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

Bootstrap values remain `K = 8`, `tau = 2` until real reviewer-latency/backlog data justifies calibration.

Important property:

```text
open work falls -> L falls -> capacity recovers
```

### 2. Shannon work-mix diversity

Open work is mapped to coarse public categories. Normalized Shannon entropy is an inspectable diversity proxy:

```text
H = -sum(p_i * ln(p_i)) / ln(k)
```

Higher entropy is not automatically better; it is only evidence about concentration of the work surface.

### 3. Bounded dependency graph

Same-repository `#N` references between open items create a structural coordination graph:

```text
open item -> referenced open item
```

Incoming references are a capped **unlock/dependency proxy**, never correctness evidence. Repetition from one source is deduplicated.

### 4. Replicator-mutator response

The current strategy set is:

- `protect`
- `verify`
- `consolidate`
- `integrate`
- `onboard`
- `explore`
- `maintain`

A one-step allocation response uses:

```text
w_i* = w_i * exp(eta * (f_i - mean_fitness))
w_i' = (1 - mu) * normalize(w_i*) + mu / n
```

`mu > 0` preserves a non-zero exploration floor. This is a current-state response, not historical learning.

### 5. Feedback-control deficit proxy

The observer computes deficits for:

- branch protection;
- review carrying capacity;
- independent-review coverage;
- starter-task supply;
- external witness/participant presence;
- workflow SHA pinning;
- branch-pressure coordination debt.

It reports:

```text
V_proxy = sum_j alpha_j * deficit_j^2
```

Lower is directionally better under configured targets. **This is not a Lyapunov stability proof.**

### 6. Multi-objective bounded action priority

Candidate recommendations use an inspectable priority shape:

```text
Priority(a) ~
  value * confidence * unlock * community_leverage * reversibility
  ----------------------------------------------------------------
  1 + review + complexity + coordination + risk
```

Hard invariants outrank this scalar.

Recommendations include protecting `main` through #35, obtaining independent review, inspecting reviewed work for integration, pinning floating workflow actions, improving starter-task supply, or converging stale branches. The workflow executes none of them.

## Modes

The deterministic repository scorer can emit:

```text
GUARD
CONSOLIDATE
VERIFY
ONBOARD
INTEGRATE
EXPLORE
```

Examples:

- unprotected canonical branch -> `GUARD`;
- low review capacity / oversized ready queue -> `CONSOLIDATE`;
- ready PRs lacking independent review -> `VERIFY`;
- healthy capacity with insufficient newcomer/external-witness surface -> `ONBOARD`;
- healthy reviewed queue -> `INTEGRATE`;
- otherwise -> `EXPLORE`.

No mode grants write or merge authority.

## Anti-Goodhart boundary

These are explicitly excluded from fitness:

- stars;
- forks;
- reactions;
- raw comments;
- raw commit count.

They may be discovery/attention context elsewhere, but they do not establish correctness or verified improvement.

## Workflow security model

### Trusted live observation

Live observation is triggered by bounded issue lifecycle, PR metadata, review, `main` push, manual dispatch, and daily schedule events. **There is deliberately no per-comment trigger**: comments may contribute to the bounded 30-day external-participant observation when another observation runs, but comment spam cannot directly amplify API/Actions execution.

Pull-request metadata observation uses `pull_request_target` so the workflow definition comes from the trusted default branch. The live job explicitly checks out the **default branch**, never PR-head code.

Job-scoped permissions are only:

```text
contents: read
issues: read
pull-requests: read
```

Checkout credentials are not persisted. The live collector receives the ephemeral token only for bounded GitHub metadata reads. It has no secrets, contents-write, issue-write, PR-write, Actions-write, approval, branch-mutation, or merge authority.

### PR-head verification

A separate ordinary `pull_request` job runs deterministic compile/unit tests against proposed code with `contents: read` only. It does not invoke the live API collector.

The observer tests explicitly require that:

- extracted structural references are deduplicated and capped;
- the PR author and bots cannot count as independent reviewers;
- popularity fields do not change the decision;
- unprotected `main` forces `GUARD`;
- strategy weights normalize and retain an exploration floor;
- no `issue_comment` trigger exists.

### Supply chain

The Observatory workflow's third-party actions are pinned to reviewed immutable SHAs. The live observer also measures pin coverage in the rest of `.github/workflows/` and may recommend hardening; it does not silently rewrite other workflows.

## Event storms and compute budget

The trusted observer uses one concurrency group with `cancel-in-progress: true`:

```text
many rapid events -> cancel stale observation -> compute newest snapshot
```

PR-head tests use a separate per-PR group, so proposed-code verification cannot cancel the trusted observer or vice versa.

A daily scheduled observation provides quiet drift detection.

## Output

Each successful live run retains for 30 days:

```text
results/evolution/repository-snapshot.json
results/evolution/evolution-decision.json
results/evolution/EVOLUTION_REPORT.md
```

The job summary publishes the human-readable report. These outputs are decision-support evidence, not canonical-state mutations.

## Hard external gates

The Observatory must remain fail-closed around capabilities it cannot enforce itself:

- if GitHub reports `main` unprotected, `GUARD` remains active and #35 stays the external admin gate;
- automation cannot manufacture the independent human witness required for frozen runtime PR #91;
- any future write actuator must satisfy branch/ruleset protection, independent-review requirements, the external ACE activation gate, rate limits, deduplication, and no-self-approval/no-self-merge rules.

## Relationship to ACE, IDKGraph, and verification

The Observatory is a consumer/recommender, not a replacement controller:

- ACE owns community reproduction/lineage/capacity policy;
- the branch-convergence audit owns branch lifecycle classification;
- IDKGraph owns repository/document/relationship observability layers;
- verification/evaluator workflows own candidate correctness evidence;
- the repository observer combines bounded signals to recommend the next repository-level intervention.

Long-term direction remains a guarded composition of repository, collaboration, and evidence graphs—not parallel competing sources of truth.

## Falsification and calibration

Treat the model as wrong or incomplete if, for example:

- lower `V_proxy` does not correlate with lower review/coordination burden;
- the priority rule repeatedly recommends low-value work;
- work-mix entropy predicts nothing useful;
- reference centrality is gamed or does not predict unblock value;
- capacity parameters do not track reviewer latency/backlog;
- strategy weights oscillate without measurable benefit.

When enough outcome data exists, replace hand-authored pressures with calibrated estimates and retain negative results.

## Community impact

A strong repository action should make the project more inspectable, not more mysterious. The Observatory therefore publishes its inputs/proxies, formulas, blockers, strategy weights, recommendations, authority limits, and scientific caveats so contributors can challenge individual assumptions without access to a hidden autonomous agent.
