# Repository Evolution Observatory v1

**Status:** proposed canonical upgrade of the existing `IDKMesh Evolution Loop`  
**Date:** 2026-08-28

## Purpose

IDKMesh needs one repository-level feedback loop that can answer a practical question after GitHub activity:

> **Given the current observable state, what bounded intervention is most likely to improve verified useful work without outrunning review, safety, or community capacity?**

This is an **observer and recommender**, not an autonomous integrator.

It upgrades the existing `.github/workflows/evolution-loop.yml` instead of introducing a second self-evolution controller.

## Why the old event-delta state is insufficient

The previous loop loaded `state/evolution-state.json`, applied a small prior delta for the triggering event, and wrote the result inside the ephemeral Actions runner. The next run checked out the repository baseline again, so those runner-local state changes were not durable repository memory.

More importantly, cumulative event scoring can confuse **history** with **current condition**. IDKMesh already corrected the same structural problem in ACE carrying capacity: review pressure should recover when open work disappears.

Evolution Observatory v1 therefore uses a different rule:

```text
current GitHub/repository snapshot
 -> deterministic measurements
 -> bounded mathematical response
 -> recommendation artifact
```

Every run recomputes the state from observable evidence. Historical learning, when introduced, must use explicit outcome/lineage evidence rather than hidden runner-local memory.

## Evidence collected

The collector uses public/repository metadata only:

- whether the default branch is protected;
- open issues and pull requests;
- draft vs review-ready PR state;
- presence of independent reviewers/approvers on open PRs;
- bounded same-repository `#N` dependency references;
- issue/PR labels;
- distinct non-owner/non-bot public participants observed in the bounded snapshot;
- recent merged-PR count;
- branch count;
- GitHub Actions dependency pinning in checked-in workflows;
- presence/count of public conversation records and the chat-preservation project rule.

Natural-language bodies are **not stored** in the observation artifact. They are treated as untrusted text. The collector extracts only bounded numeric same-repository references and labels as coordination signals.

The project-memory signal is deliberately modest: it can observe archive structure/rules, but it **cannot prove that every ChatGPT turn was preserved**. That remains a behavioral/project-governance responsibility.

## Algorithm stack

The observer combines several inspirations discussed in the project. These are engineering hypotheses, not claims that a software repository literally obeys biological or physical laws.

### 1. Ecological carrying capacity

Reuse the accepted ACE `live-open-work-v1` review-pressure model:

```text
L =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_issues, 20)

Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

Bootstrap values remain `K = 8`, `tau = 2` until empirical reviewer-latency data justifies calibration.

Important property:

```text
open work falls -> L falls -> capacity recovers
```

### 2. Shannon diversity

Open work is mapped into coarse, inspectable categories such as verification, community, research, maintenance, governance, product, and other.

Normalized Shannon entropy is used as a **work-mix diversity proxy**:

```text
H = -sum(p_i * ln(p_i)) / ln(k)
```

This does not claim that higher diversity is always better. It is one signal for whether the current work surface has collapsed into one category.

### 3. Bounded dependency graph

For open issues/PRs, same-repository `#N` references create a coordination graph:

```text
open item -> referenced open item
```

Incoming references are a capped **dependency-unlock proxy**, not correctness evidence. Repeated references from one source are deduplicated so simple repetition cannot multiply the signal.

### 4. Replicator-mutator response

The observer maps current deficits/pressures onto a small strategy set:

- `protect`
- `verify`
- `consolidate`
- `integrate`
- `onboard`
- `explore`
- `maintain`

A one-step response uses:

```text
w_i* = w_i * exp(eta * (f_i - mean_fitness))
w_i' = (1 - mu) * normalize(w_i*) + mu / n
```

`mu > 0` preserves a non-zero exploration floor.

This is **not historical learning** yet. It is a deterministic allocation response to the current snapshot. Historical adaptation must later be driven by explicit verified outcomes.

### 5. Feedback-control / energy proxy

The observer computes deficits for:

- branch protection;
- review carrying capacity;
- independent-review coverage;
- newcomer task supply;
- external witness/participant presence;
- workflow SHA pinning;
- branch-pressure coordination debt.

It then reports a weighted squared proxy:

```text
V_proxy = sum_j alpha_j * deficit_j^2
```

Lower is directionally better under the configured targets.

This is **not a Lyapunov stability proof**. It is an inspectable control-error aggregate that should be tested against real outcomes.

### 6. Multi-objective bounded action priority

Candidate recommendations reuse the repository improvement-loop shape:

```text
Priority(a) ~
  value * confidence * unlock * community_leverage * reversibility
  ----------------------------------------------------------------
  1 + review + complexity + coordination + risk
```

Hard invariants outrank this scalar.

The current action classes are recommendations such as:

- protect `main` via the existing admin gate (#35);
- obtain independent review for a PR;
- inspect an already-reviewed PR for integration;
- pin floating GitHub Actions dependencies;
- improve the bounded starter-task surface;
- converge stale branches through the existing branch audit (#127).

The workflow does **not execute these actions**.

## Modes

The current deterministic controller can emit:

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
- low review capacity / large ready queue -> `CONSOLIDATE`;
- ready PRs lacking independent review -> `VERIFY`;
- healthy capacity but insufficient newcomer surface -> `ONBOARD`;
- healthy reviewed queue -> `INTEGRATE`;
- otherwise -> `EXPLORE`.

No mode grants write/merge authority.

## Anti-Goodhart boundary

The observer explicitly excludes these from fitness:

- stars;
- forks;
- reactions;
- raw comments;
- raw commit count.

They may be useful discovery/attention context elsewhere, but they do not prove correctness or verified improvement.

## Workflow security model

### Trusted observer execution

On issue/review/comment/push/scheduled events, the observation job runs from the trusted default-branch workflow. Pull-request metadata observation uses `pull_request_target` specifically so the workflow definition also comes from the trusted default branch. The live observer explicitly checks out the repository **default branch**, never PR-head code.

Permissions are read-only and job-scoped:

```text
contents: read
issues: read
pull-requests: read
```

The live collector receives the ephemeral GitHub token only in the bounded metadata-collection step. It has no secrets, contents-write, issue-write, PR-write, or Actions-write authority.

### PR-head policy verification

A separate ordinary `pull_request` execution runs only deterministic compile/unit tests against proposed code. Checkout credentials are not persisted and the test process receives no explicitly exported repository token or secrets. The live metadata observer is disabled in this PR-controlled execution context.

### Dependency pinning

The workflow's own third-party actions are pinned to reviewed immutable SHAs. The observer also measures SHA-pinning across the rest of `.github/workflows/` and can recommend a repository-wide hardening task without silently changing every workflow in the same PR.

## Event storms / compute budget

The trusted live-observer job uses one `evolution-observer` concurrency group with `cancel-in-progress: true`. PR-head checks use a separate per-PR concurrency group.

For live observation this implements **latest-state** semantics:

```text
many rapid events -> cancel stale observation -> compute newest snapshot
```

A PR-head test can therefore never cancel the trusted live observer, or vice versa. This avoids spending GitHub-hosted public CI time preserving obsolete intermediate snapshots while keeping proposed-code verification independent.

A daily scheduled observation provides a quiet baseline even when no event fires.

## Output

Each run emits a 30-day artifact containing:

```text
results/evolution/repository-snapshot.json
results/evolution/evolution-decision.json
results/evolution/EVOLUTION_REPORT.md
```

The job summary surfaces the same human-readable report.

Artifacts are evidence snapshots, not canonical state mutations.

## Relationship to ACE and IDKGraph

This observer should not become a parallel community controller.

- ACE owns community reproduction/lineage/capacity policy.
- The branch-convergence audit owns detailed branch lifecycle classification.
- Verification/evaluator workflows own candidate correctness evidence.
- The repository evolution observer consumes bounded signals and recommends the next repository-level intervention.

The long-term direction remains issue #46:

```text
RepositoryGraph
 U GitHubCollaborationGraph
 U EvidenceGraph
 -> one guarded evolution policy
```

Any future Level-2 actuator must satisfy issue #35 and the external ACE activation gate first, remain rate-limited, deduplicate equivalent work, and never approve/merge itself.

## Falsification / calibration path

The model should be considered wrong or incomplete if, for example:

- lower `V_proxy` does not correlate with lower review/coordination burden;
- the priority rule repeatedly recommends work that produces little verified value;
- Shannon work-mix diversity predicts nothing useful;
- dependency-reference centrality is easily gamed or does not predict unblock value;
- the capacity parameters do not track real reviewer latency/backlog;
- strategy weights oscillate without measurable benefit.

When enough outcome data exists, replace hand-authored pressures with calibrated estimates. Negative results should be retained.

## Community impact

A strong repository action should make the project easier to understand, not more mysterious.

The observer therefore publishes:

- inputs/proxies;
- formulas;
- blockers;
- strategy weights;
- bounded recommended actions;
- authority limits;
- scientific caveats.

A contributor can challenge one metric, calibration, graph rule, test, or recommendation policy without needing private project context or access to a hidden autonomous agent.
