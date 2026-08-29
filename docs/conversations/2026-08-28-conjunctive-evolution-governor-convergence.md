# Conjunctive evolution governor convergence pass

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

Continue strengthening IDKMesh with GitHub-native mathematical/evolutionary mechanisms, open public issues for important actions that cannot be completed directly, and preserve useful chat-derived reasoning/decisions in the repository.

## Starting point

This turn began by inspecting the existing `IDKMesh Evolution Loop` instead of creating a new controller blindly.

The repository then evolved concurrently several times, and the correct architecture changed as stronger work landed:

- **#137 merged** — Mathematical Evolution Kernel + persistent trusted-main Bayesian observer;
- **#143 merged** — live Repository Mathematical Portfolio using dependency graph unlock, Pareto/NSGA attention, entropy/JSD, multiplicative weights, Bayesian health deficits, and UCB exploration;
- **#144 merged** — stateless read-only Repository Evolution Observatory with bounded metadata, anti-Goodhart tests, trusted `pull_request_target`, immutable action pins, and fail-closed `GUARD` behavior on unprotected `main`.

Rather than treating earlier branches as entitled to merge because they were created first, the work was repeatedly reconciled against these new canonical surfaces.

## Superseded exploratory branches

### #139

The first live-observer proposal conflicted with the stronger mathematical core from #137. It was closed unmerged and retained as public provenance.

### #142

A second clean branch correctly preserved #137 and introduced a hard current-state governor, but it became stale as #143/#144 landed. Its unique ideas were ported into the current convergence PR #146 rather than forcing stale ancestry.

## Final responsibility separation

The converged design is:

```text
#137 persistent Bayesian history
        +
#146 hard recomputed current-state governor
        +
#143 live Pareto/UCB attention portfolio
        |
        v
bounded recommendation
        |
        v
independent verification + external GitHub governance
```

PR #144's stateless scorer remains on `main` as an **offline comparison/falsification baseline**. It is valuable because disagreement between stateless and persistent/current-guarded reasoning can expose stale priors or weak proxies; it is not wired as an additional autonomous controller.

## Why the hard live governor still adds value

Persistent Bayesian state answers historical/uncertainty questions. Pareto/UCB answers where attention may be informative. Neither should be able to compensate for a failed current hard condition.

The live governor recomputes:

- actual default-branch protection;
- live review-ready/draft pressure;
- recoverable ACE-style carrying capacity;
- independent-review coverage;
- starter-task supply;
- external public witness/participant signal;
- immutable-SHA workflow pin ratio;
- branch-count coordination pressure;
- open-work Shannon diversity;
- project chat-memory archive/rule surfaces.

Hard rule:

```text
main_protected = false => GUARD
```

Historical Bayesian fitness, Pareto rank, UCB focus, stars, forks, reactions, comments, or commit counts cannot override it.

## Checkpoint integration bug discovered

After #144 merged, the live Evolution Loop published artifacts named:

```text
evolution-observation-*
```

while the #143 portfolio expected:

```text
evolution-checkpoint-*
  containing state/evolution-state.json
```

That meant the portfolio's Bayesian-health input could silently fall back to the repository seed instead of consuming the trusted persistent Bayesian checkpoint.

PR #146 restores the persistent checkpoint contract while also publishing the live hard-governor evidence in the same trusted observation artifact.

## GitHub Actions trust-boundary correction

A security subtlety was explicitly handled: ordinary `pull_request` workflow YAML is proposed code, so live API/checkpoint authority must not run from that PR-controlled definition.

The converged workflows separate contexts:

### Trusted live observation

- `pull_request_target` for PR metadata observation;
- workflow definition comes from the default branch;
- explicit default-branch checkout;
- no PR-head code execution;
- read-only job-scoped token permissions;
- persisted checkout credentials disabled;
- external actions pinned by immutable SHA.

### Proposed-code verification

- ordinary `pull_request`;
- PR-head checkout;
- `contents: read` only;
- deterministic compile/unit/invariant tests;
- no trusted checkpoint restore;
- no live GitHub API observer execution;
- no repository secrets explicitly exported.

## Artifact-state concurrency

Trusted artifact-backed observers use repository-level latest-state concurrency with `cancel-in-progress: true` so concurrent event bursts do not restore the same checkpoint and publish forked successor observer state.

This makes the checkpoint a **latest-state observer**, not an immutable raw event ledger.

## Supply-chain hardening

Core mathematical workflows use reviewed immutable commits for:

- `actions/checkout` v7.0.1;
- `actions/setup-python` v7.0.0;
- `actions/upload-artifact` v7.0.1;
- `actions/download-artifact` v8.0.1.

The hard governor independently measures repository-wide SHA-pin coverage so these local fixes cannot be mistaken for proof that every workflow is already fully pinned.

## Privacy/evidence-minimization finding

The #143 portfolio needs issue/PR text ephemerally for deterministic classification and reference extraction. Its original workflow copied the raw snapshot — including issue/PR bodies — into the retained replay artifact.

That was unnecessary retained data.

PR #146 changes the boundary to:

```text
raw issue/PR bodies -> ephemeral /tmp snapshot
                  -> deterministic portfolio calculation
                  -> not copied into retained artifact
```

The retained portfolio checkpoint now contains only derived portfolio state/output, policy, and Markdown. A workflow assertion verifies that `repository-snapshot.json` is absent from the retained checkpoint directory.

## Clean branch reconstruction

PR #146 initially inherited conflicting/stale history even though its recorded base matched current `main`.

The branch was professionally reconstructed as one clean commit on exact current `main` using exactly the intended convergence file blobs. Unrelated benchmark/IDKGraph changes from `main` were inherited directly rather than copied or overwritten.

All pre-reconstruction CI was intentionally considered stale and must be rerun on the new exact head.

## Anti-Goodhart rule

Live hard-governor fitness excludes:

- stars;
- forks;
- reactions;
- raw comments;
- raw commit count.

The broader interpretation is:

```text
Bayesian posterior != causality
Pareto front        != correctness
UCB focus           != approval
activity volume     != improvement
popularity          != trust
```

## Chat-to-repository propagation

The existing `PROJECT_RULES.md` mandatory preservation rule remains canonical.

Substantive project turns should continue to use two layers:

```text
docs/conversations/ structured public record
+
promotion into canonical code/docs/issues when the turn changes the project
```

The live snapshot can observe that the rule/archive surfaces exist. It cannot prove completeness for a conversation that was never committed.

## External blockers surfaced publicly

### #35 — protect `main`

Public GitHub metadata still reports `main` unprotected. The issue remains the canonical administrative hard gate. Repository workflows cannot substitute for this external enforcement.

### #138 — independent human review for PR #91

Automation cannot manufacture a genuinely independent human witness. A bounded expert-review issue was opened instead of self-approving the canonical node.

## Remaining completion path for #146

1. require fresh exact-head PR-head CI after the clean reconstruction and privacy/doc corrections;
2. verify the PR is mergeable and contains only the intended convergence files;
3. verify the live/PR trust separation and minimum permissions from the actual diff;
4. open a bounded independent-review issue for #146;
5. close #142 unmerged as superseded once #146 is demonstrably clean/green;
6. do **not** self-merge #146.

## Scientific next step

After the control-plane convergence, the next strong mathematical step should be calibration from delayed outcomes rather than adding a fourth controller. Historical observations can be joined to regressions/reverts, verifier disagreement, review latency, benchmark movement, newcomer completion, external contributor retention, security findings, and time-to-verified-useful-work, then compared with held-out Brier/log-loss/calibration/ranking-regret metrics.

Negative results remain first-class evidence.
