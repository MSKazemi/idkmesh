# Current-main conjunctive evolution convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

Continue strengthening the mathematical and algorithmic foundation through GitHub-native mechanisms; when an important action cannot be completed directly, expose it as a public issue; and preserve useful chat-derived reasoning, decisions, and results in the repository rather than leaving them only in private conversation context.

## What happened concurrently

This pass first established:

- #137 — persistent Bayesian Mathematical Evolution Kernel;
- #143 — live Repository Mathematical Portfolio with Pareto/NSGA, graph unlock, entropy/JSD, multiplicative attention, and UCB;
- #144 — stateless/recomputed Repository Evolution Observatory with a trusted PR event boundary, carrying capacity, graph/reference signals, Shannon diversity, control-energy deficits, replicator-mutator response, hard `GUARD`, Anti-Goodhart exclusions, and immutable Action pins.

The first canonical portfolio run consumed a trusted Bayesian checkpoint and surfaced parallel evolution-observer PRs as high review-attention candidates. That created a real self-convergence test: improve the existing layers instead of preserving competing controllers because they were opened first.

A stale intermediate convergence PR (#146) was closed rather than forced across the semantic collision created by #144.

## Current-main composition in PR #148

The reduced convergence keeps #144 intact and restores/composes only what is missing:

```text
persistent Bayesian history (#137)
 + current Repository Evolution Observatory (#144)
 + live Pareto/UCB Repository Mathematical Portfolio (#143)
 -> conjunctive bounded recommendation (#148)
 -> independent verification / GitHub governance
```

The layers answer different questions:

- Bayesian history: what uncertain evidence accumulated over trusted iterations?
- live observatory: what are the current recoverable constraints and blockers?
- portfolio: where is attention/experimentation most informative under multiple objectives?
- conjunctive controller: are historical confidence and current hard guards jointly healthy enough to consider a stronger **non-integrating** experiment?

None grants merge or approval authority.

## New conjunctive controller

`scripts/conjunctive_evolution_control.py` combines conservative Bayesian confidence bounds with live observatory blockers/capacity.

A stronger bounded non-integrating experiment is a candidate only when:

- the live observer has no blockers and is not in `GUARD`;
- the verification posterior lower bound exceeds the existing homeostatic target minus scale;
- the risk-debt posterior upper bound is below the existing target plus scale;
- live review capacity exceeds the live policy minimum;
- the live mode is `EXPLORE`, `ONBOARD`, or `INTEGRATE`.

No integration, approval, merge, branch mutation, spending, or constitutional authority is created.

Hard non-compensation rule:

```text
live hard blocker => stronger experiment candidate = false
```

Therefore perfect historical Bayesian confidence cannot override `main_unprotected -> GUARD`.

## Bayesian persistence restored beside the live observatory

After #144, the Evolution Loop published stateless `evolution-observation-*` artifacts while #143's portfolio expected persistent `evolution-checkpoint-*` history containing `state/evolution-state.json`.

That mismatch could make portfolio Bayesian-health silently fall back to the repository seed.

PR #148 restores the trusted Bayesian checkpoint contract **without removing #144's live observatory**. The trusted workflow now:

1. searches recent successful default-branch runs;
2. selects the newest run that actually retains an unexpired `evolution-checkpoint-*` artifact;
3. restores the Bayesian state/ledger when available;
4. updates persistent history;
5. recomputes the current live observatory from fresh bounded metadata;
6. evaluates the conjunctive controller;
7. retains historical, live, and conjunctive evidence in the next checkpoint.

The lookup is constrained to successful default-branch runs so PR-generated artifacts cannot become trusted history.

## GitHub Actions trust boundary

The Repository Mathematical Portfolio is hardened to mirror the live observatory pattern.

### Trusted live observation

- `pull_request_target` for PR metadata;
- workflow definition comes from the default branch;
- explicit default-branch checkout;
- no PR-head code execution with live observer token scopes;
- job-local read permissions only;
- persisted checkout credentials disabled;
- immutable Action pins.

### Ordinary `pull_request`

- PR-head code receives only `contents: read`;
- compile/unit/invariant tests only;
- no trusted checkpoint restore;
- no live GitHub API observation;
- no repository secrets explicitly exported.

Artifact-backed trusted observers use one latest-state concurrency lineage with `cancel-in-progress: true` so event storms do not create forked successor checkpoint histories.

## Supply-chain hardening

Core mathematical workflows use reviewed immutable commit SHAs for checkout, Python setup, artifact upload, and artifact download. The live observatory separately measures repository-wide workflow pin coverage, so local hardening is not misrepresented as proof that every workflow is already pinned.

## Artifact privacy / evidence minimization finding

During review of #148, the Repository Mathematical Portfolio was found to copy its transient `/tmp/repository-snapshot.json` into the retained checkpoint. That snapshot contains issue/PR bodies needed only ephemerally for deterministic classification/reference extraction.

Retaining the raw bodies added no value to replayable portfolio evidence.

The workflow was patched directly on #148:

```text
raw issue/PR text
 -> ephemeral /tmp snapshot
 -> deterministic portfolio calculation
 -> NOT copied into uploaded checkpoint
```

The retained portfolio artifact now contains only derived portfolio state/output, policy, and Markdown. A shell assertion requires `repository-snapshot.json` to be absent from the checkpoint directory before upload.

The separate #144 live-observatory snapshot already retains no issue/PR/comment bodies.

## Anti-Goodhart rule

```text
stars           != correctness
forks           != correctness
raw comments    != correctness
raw commits     != improvement
Bayesian score  != causality
Pareto rank     != approval
UCB focus       != trust
replicator mass != integration authority
```

Historical belief and current mathematical opportunity may guide attention, but current hard guards and independent verification remain binding.

## Chat-to-repository propagation

`PROJECT_RULES.md` remains the canonical mandatory preservation rule.

For substantive turns, the project should continue to use two layers:

```text
docs/conversations/ structured public record
+
promotion into code/docs/issues when the discussion changes the project
```

A repository observer can confirm that archive/rule surfaces exist, but it cannot detect a conversation that was never committed. The behavioral rule remains necessary.

This turn itself is represented by this record plus the implementation/docs/issues it changed.

## External actions surfaced as public work

### #35 — protect `main`

GitHub still reports `main` unprotected. The live observatory must truthfully remain in `GUARD`, and the conjunctive controller must refuse stronger experiment escalation until that external branch/ruleset boundary is actually configured.

### #138 — separate human review for PR #91

Automation cannot manufacture the genuinely separate human witness required for the canonical node. The blocker is public and claimable rather than being silently bypassed.

## Remaining path for PR #148

- require fresh exact-head PR-head CI after the artifact-minimization correction;
- confirm the PR is mergeable against current `main` and contains only the intended convergence files;
- inspect actual workflow permissions/pins/trusted-default-branch behavior;
- open a bounded independent-review task for #148 once exact-head CI is green;
- close older #142 unmerged as superseded when #148 is demonstrably clean/reviewable;
- do not self-merge the repository-wide control-plane change.

## Scientific next step

After controller convergence, the next strong mathematical improvement should be calibration from delayed outcomes rather than another hand-authored controller.

Join retained observations to outcomes such as regressions/reverts, verifier disagreement, review latency/burden, benchmark movement, issue reopen rate, newcomer completion, contributor retention, security findings, and time-to-verified-useful-work. Compare predictive variants on held-out Brier score, log loss, calibration error, ranking regret, and uncertainty coverage.

Negative results remain first-class evidence.
