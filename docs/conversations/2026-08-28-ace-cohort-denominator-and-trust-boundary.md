# Conversation Record — ACE Cohort Denominator and Trust Boundary

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner asked the assistant to continue improving the repository under the standing rule that GitHub activity should increase verified capability, knowledge, safety, or community leverage rather than raw activity alone.

## Context

The ACE stack had become more concrete:

```text
#40 cohort observer
#48 causal lineage contract
#44 offline population simulator
#68 shadow generational controller
#51 consolidated safety / protected-main gate
```

PR #48 now defines a tested `ACE_LINEAGE` contract. That made part of PR #40's original documentation stale: it described causal lineage as a future schema and risked making its bootstrap label-based ratio look closer to the full community reproduction number than it really is.

## Architectural clarification

The layers now have distinct responsibilities.

### PR #40 — cohort/exposure observer

Owns:

- deliberate Bootstrap Cohort inventory;
- external interest;
- claim state;
- candidate PRs;
- merged candidates;
- bootstrap `ace:verified-descendant` acceptance signal;
- review-capacity context;
- a narrow seed-exposure ratio.

It does **not** own cross-generation causal proof.

### PR #48 — lineage contract

Owns:

```text
parent -> seed -> descendant -> verification evidence
```

including machine validation and duplicate-causal-credit protection.

### Full community reproduction

The full quantity must combine an independent denominator with causal verified lineages:

```text
R_community(W,t)
  = verified causal descendants
    / eligible matured verified parents
```

A Growth Seed exposure denominator is useful for the bootstrap cohort but is not automatically identical to the future set of eligible verified parents. Therefore PR #40 explicitly reports:

```text
metric_scope = bootstrap_growth_seed_exposure
full_r_community_ready = false
```

This prevents a temporary experimental ratio from becoming an accidental canonical success metric.

## Security hardening added

The cohort observer also received its own trust boundary rather than depending on another PR landing first.

Changes include:

- pin `actions/github-script` to immutable reviewed SHA `f28e40c7f34bde8b3046d885e986cb6290c5673b`;
- require trusted repository `author_association` in addition to `growth-seed` + `cohort=bootstrap-1` for cohort admission;
- add workflow-owned observatory identity label `ace:cohort-observer`;
- adopt a legacy observatory by title only when it also contains `ACE_COHORT_STATE`;
- prefer the workflow-owned `ace:ledger` identity for capacity input, with legacy #23 fallback while the safety consolidation remains under review;
- keep capacity unknown rather than manufacturing default state when the ledger cannot be read;
- retain the invariant that raw activity never auto-applies the verified-descendant label;
- never create Cohort 2 automatically.

## Executable observer contract

Added:

- `tests/test_ace_cohort_observer_contract.py`;
- `.github/workflows/ace-cohort-contract.yml`.

The contract checks that the privileged observer:

- contains no checkout or shell `run:` execution in the `pull_request_target` workflow;
- pins its external action dependency;
- requires trusted bootstrap-seed provenance;
- owns its observatory identity by label rather than title;
- explicitly marks the snapshot as not ready to claim full `R_community`;
- observes rather than auto-applies the verification label;
- does not auto-create Cohort 2;
- has no `contents: write` permission.

## Community impact

This clarification makes the experiment easier to interpret and harder to game. Contributors can see exactly what a claim, candidate, merge, bootstrap verification signal, and causal lineage receipt mean. Reviewers no longer need to infer whether two ACE workflows are measuring the same thing.

## Next step

1. Run the cohort contract CI.
2. Review #40 as the bootstrap denominator/funnel layer rather than a full reproduction controller.
3. Review the tested #48 causal lineage contract.
4. Once those evidence layers are accepted, adapt #68 to consume validated lineage receipts plus an independent matured-parent inventory.
5. Keep Phase-B public actuation disabled until the consolidated safety/protection gate and real descendant evidence are in place.
