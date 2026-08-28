# ACE Cohort Observer v0

**Status:** Experimental, metadata-only observability.

This observer exists because IDKMesh must distinguish **activity**, **cohort exposure**, **candidate work**, and **causal verified-descendant evidence**.

Its role in the ACE stack is intentionally narrow:

```text
ACE Cohort Observer (#40)
  -> trusted Bootstrap Cohort inventory
  -> external-interest / claim / candidate funnel
  -> bootstrap exposure denominator + review-capacity context

ACE Lineage Protocol (#48 / #25)
  -> parent -> seed -> descendant causal receipt
  -> verification evidence

ACE generational controller (#68 / #57)
  -> consumes validated evidence
  -> learns bounded community strategy in shadow mode
```

The observer must not duplicate the lineage parser or claim the full community reproduction number from labels alone.

## State funnel

For each trusted issue labelled `growth-seed` in Bootstrap Cohort 1, the observer tracks:

```text
trusted visible seed
  -> external interest
  -> claim
  -> candidate PR
  -> merged candidate
  -> bootstrap verified-descendant signal
```

Cohort admission requires all of:

- `growth-seed` label;
- explicit `cohort=bootstrap-1` marker;
- trusted repository author association (`OWNER`, `MEMBER`, or `COLLABORATOR`).

This prevents untrusted marker text from manufacturing cohort membership even before the broader ACE workflow-hardening PR is integrated.

### External interest

A non-owner, non-bot contributor comment or contribution signal associated with the seed. Interest is diagnostic evidence, not a descendant.

### Claim

A seed is considered claimed when an external non-bot contributor is assigned, comments `/claim`, or authors a PR that GitHub cross-references from the seed. `/claim` grants no repository permission or exclusive ownership.

### Candidate PR

An external-human-authored PR cross-referenced from the Growth Seed. A candidate is not automatically useful or verified.

### Bootstrap verified-descendant signal

A candidate PR enters the observer's bootstrap verified set only when it is merged and carries `ace:verified-descendant`.

This label is an explicit trusted acceptance signal. It is **not** equivalent to the full ACE lineage record. After the lineage protocol is accepted, a real causal claim should be represented by a validated `ACE_LINEAGE` receipt with verification evidence. The label can support that receipt; it cannot replace it.

## Metric scope

The observer reports:

```text
SeedReproductionRatio
  = bootstrap verified descendant PRs
    / trusted Bootstrap Cohort Growth Seeds
```

This is a **bootstrap exposure metric**, not the full `R_community`.

The full quantity remains conceptually:

```text
R_community(W, t)
  = verified causal descendants
    / eligible matured verified parents
```

Computing it requires two independent inputs:

1. a denominator inventory that keeps zero-descendant eligible parents visible and handles right-censoring;
2. validated causal lineage receipts from the ACE lineage contract.

The cohort observer contributes useful denominator/exposure evidence for the bootstrap experiment, but its Growth Seeds are not automatically identical to all future verified parents. It therefore sets `full_r_community_ready: false` in its snapshot and must not overclaim causal reproduction.

## Capacity-aware expansion recommendation

The observer may report `HOLD_COHORT_1` or `EVALUATE_COHORT_2`.

`EVALUATE_COHORT_2` currently requires at least two bootstrap verified descendant PRs, at least two claimed seeds, no more than three open external candidate PRs, and ACE capacity >= 0.60 when capacity evidence is available.

These are bootstrap hypotheses. The observer **never creates Cohort 2**. Expansion remains a human/community decision until the evidence and security gates justify a higher authority tier.

## Public status identity

The workflow maintains one observatory issue using workflow-owned label:

`ace:cohort-observer`

The title `[ACE] Bootstrap Cohort Observatory` is for humans, not authority. During migration, an old title-matching issue is adopted only when it already contains an `ACE_COHORT_STATE` block.

The machine snapshot includes:

- `metric_scope: bootstrap_growth_seed_exposure`;
- `full_r_community_ready: false`;
- trusted seed numbers;
- claim/candidate/merge counts;
- bootstrap verified descendant PR numbers;
- participant count;
- seed reproduction ratio;
- capacity/review-load evidence when available;
- advisory recommendation.

## Security boundary

This workflow uses `pull_request_target` metadata with issue-write capability, so the critical boundary is explicit:

> **Never check out, import, build, install, evaluate, or execute PR-controlled code in this privileged workflow.**

Additional guards:

- `actions/github-script` is pinned to immutable reviewed commit `f28e40c7f34bde8b3046d885e986cb6290c5673b`;
- bootstrap seed membership requires trusted author association;
- observatory identity is label-owned rather than title-owned;
- ACE ledger state is read only as advisory capacity evidence;
- no auto-merge;
- no automatic application of verification from raw activity;
- no automatic Cohort-2 creation.

## Anti-Goodhart rule

```text
comment != claim
claim != candidate
candidate != merge
merge != verified causal descendant
bootstrap verified label != complete lineage proof
verified descendant != durable retained contributor
owner/bot activity != external community reproduction
```

Future versions should add reviewer-time accounting, contributor return/retention, matured parent inventories, and validated lineage integration rather than simply adding event counters.

## Related

- `COMMUNITY_GROWTH_ENGINE.md`
- `docs/community/ACE_BOOTSTRAP_EXPERIMENT.md`
- `.github/workflows/ace-community-growth.yml`
- `.github/workflows/ace-cohort-observer.yml`
- issue #23 — ACE Growth Ledger
- issue #25 / PR #48 — ACE lineage evidence
- issue #57 / PR #68 — generational controller
