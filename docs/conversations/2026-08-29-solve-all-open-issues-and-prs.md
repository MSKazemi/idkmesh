# Conversation record — solve the open issues and pull requests

**Date:** 2026-08-29
**Repository:** `MSKazemi/idkmesh`

## Project owner request

> solve all the issues and PRs and merge to the main branch with high quality and
> professional way. You can do in parallel if it is doable.

## Live repository audit

State observed before any change, at `origin/main` `649df7b7`:

- **0 open pull requests**, so the pull-request half of the request was already satisfied;
- 21 open issues;
- the local branch `audit/issue-152-warning-debt` was already squash-merged as PR #315 and
  had drifted **behind** `main`; merging it would have reverted 747 lines across 7 files,
  including `tools/closing_keyword_guard.py` and ADR-0011;
- **`main` was red.** The PR Gate push run on `649df7b7` (`33271165430`) failed.

## Defect found: a red default branch

PR #320 added `docs/conversations/2026-08-29-resolve-discovery-surface-gate.md` without
indexing it in `docs/conversations/README.md`. That is exactly the drift the guard added in
PR #315 exists to catch.

The guard worked. Both PR-Gate matrix legs of the #320 head failed (`gate (3.11)`,
`gate (3.13)`, run `33271151151`) and the pull request was merged anyway.

Root cause of the escape, stated precisely: the PR Gate runs on
`github.event.pull_request.head.sha` — the branch head, not a merge-with-`main` result —
and merging is not blocked on its conclusion. A red gate was **visible but not enforced**.

## Changes integrated

Two single-concern pull requests, in dependency order:

1. **PR #322** — restore the conversation index (`146 -> 147`). Returns `main` to green.
2. **PR #323** — #152 Phase 2: resolve the one live
   `accepted_decision_without_document_link` warning on ADR-0011.

On #323 the graph edge was not the real defect. `docs/PAGES_SETUP.md` never recorded
ADR-0011's decision, so a reader following the post-activation checks could not tell that
pinning the welcome discussion is optional. The decision was recorded in the runbook
**first**; only then was the now-true `implements` relation declared. Declaring the edge
against a document that did not reflect the decision would have manufactured traceability
to clear a warning — the failure mode #152 prohibits.

Evidence: `accepted_decision_without_document_link` 1 -> 0, `orphan_document_candidate`
27 -> 26, deterministic hard errors 0 -> 0, `implements` edges 11 -> 12.

## Boundaries preserved

This pass does **not**:

- close any issue whose acceptance criteria require an external human witness;
- supply the independent review required by #167, #151, or #138;
- close a workflow-maintained observatory issue (#23, #109);
- claim or manufacture external community participation for #9;
- activate ACE actuation or any hosted-agent lane;
- change branch-protection or repository settings;
- use a closing keyword on any issue reference. Both pull requests used `Refs:` only,
  verified with `tools/closing_keyword_guard.py` (0 violations). #152 remains open.

## Research contribution: the two missing E024 baselines

Issue #22 names five comparison arms; `sim/matched_budget_emergence.py`
implemented three, and E024 recorded the gap as an explicit limitation. Both
missing arms were implemented (PR #324): a centralized planner with one fixed
objective, and a majority-vote swarm.

The majority-vote arm **partly falsifies E024's hypothesis as it was written**.
Over 100 matched-budget seeds, Quality-Diversity wins 100/100 paired seeds
against random, fixed-scalar, and the planner — but only **51/100** against the
swarm, whose mean utility AUC (18.576) is indistinguishable from random search
(18.468).

The distribution carries the real finding:

| Arm | mean | stdev | min | seeds below AUC 16 |
| --- | ---: | ---: | ---: | ---: |
| Majority-vote swarm | 18.576 | 4.052 | 13.202 | 44/100 |
| Quality-Diversity | 22.061 | 0.271 | 21.221 | 0/100 |

Majority voting collapses the swarm onto a single consensus artifact, so its
belief spread stops functioning as retained diversity and becomes a bet settled
early in the run. Issue #22 asks whether a population can *reliably* evolve
toward a coherent system; under that reading the archive's advantage is the
removal of the failure mode, not a higher mean. E024's Decision section was
rewritten to state the claim that way.

Prior evidence was preserved: new arms are appended to `STRATEGIES` because
`run_seed` derives each arm's seed from its index, and a regression test pins
the published random/scalar/qd values.

## Issue triage — why the remaining issues did not close

All 21 open issues were audited against merged repository evidence rather than
against their issue text. **None was closeable on evidence.** The blockers are
structural, and most are deliberate.

| Blocker | Issues | Representative evidence |
| --- | --- | --- |
| Needs a genuinely external human witness | #167, #151, #138, #11 | #167: *"do not assume it is correct because it was merged"*; #151's own audit self-declares *"AI-assisted independent review; it does not claim human or organizational independence"*; PR #91 and PR #159 are both closed-and-unmerged drafts with no approving review |
| Workflow-maintained dashboards | #23, #109 | Bodies are rewritten by `ace-community-growth.yml` / `ace-cohort-observer.yml`, which look the ledger up by `state: 'open', labels: 'ace:ledger'`. Closing #23 would make the workflow create a duplicate |
| Needs real external participants | #9, #10, #57, #86 | Measured on `main`: 197 merged PRs all authored by `MSKazemi`; 492 commits all by the owner; exactly one comment from one external account. Every observatory reports `distinct external participants = 0` |
| Needs real or paid compute | #1, #2, #13, #30, #70, #96 | `results/experiments/r1/real-corpus-readiness-current.json` reports `"status": "blocked"`, `"eligible_work_units": 0` against a required 20. No coding-agent LLM inference has ever been executed in this repository |
| Needs an outward-facing activation decision | #12 | Stage A requires the owner to create a third-party API key and store it as a repository secret |
| Gated on the above | #4, #16, #22, #57 | #4 and #16 are gated on the canonical-node human review; #22's remaining scope is population scale and a learned Goal Graph |

Two issues are candidates for a **scope split** rather than closure, and that is
a maintainer decision rather than an automated one:

- **#57** — every Phase A acceptance criterion is met on `main`
  (`scripts/ace_generation_controller.py`, 18 tests, fail-closed activation
  gate). Only Phase B is blocked, by the issue's own explicit gate.
- **#86** — P0 items 1, 2, 3 and 5-as-defined are landed; the falsifiable-target
  answers need real contributor cohorts.

## Process finding requiring an owner decision

PR #320 was merged while both required PR-Gate legs were failing. The gate runs
on `github.event.pull_request.head.sha` — the branch head, not a merge-with-main
result — and merging is not blocked on its conclusion, so a red gate is visible
but not enforced.

Two settings would close this, and both are governance decisions outside the
scope of a content pull request:

1. make the PR Gate a **required** status check on `main`;
2. require branches to be **up to date** before merging, since the gate tests the
   branch head rather than the merge result.

## Open questions

- Should #57 and #86 be split so their completed mechanism layers can be
  retired separately from their blocked phases?
- Issue #138 reviews a candidate that no longer exists as an open pull request.
  Should it be rescoped, or retired? Its subject, PR #159, ended unmerged.

  (Both bullets are deliberately phrased to keep a closing keyword away from an
  issue reference. `tools/closing_keyword_guard.py` flagged the first draft of
  this section twice — once for the questions themselves, and once for the note
  explaining the first fix, which reintroduced the hazard by quoting the
  offending words next to the same numbers. The guard is worth running on prose,
  not just on pull request bodies.)
- Does the project want a social-preview image (#10 P1) and automated benchmark
  result publication (#10 P2), the two owner-fixable items in that issue?
