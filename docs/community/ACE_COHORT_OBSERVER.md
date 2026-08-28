# ACE Cohort Observer v0

**Status:** Experimental, metadata-only observability.

This document specifies the first automatic observer for the ACE Bootstrap Cohort.

The observer exists because the project must distinguish **activity** from **community reproduction evidence**. Stars, comments, issue closures, and even merged pull requests are not automatically proof that a Growth Seed produced a useful descendant.

For this first community-growth cohort, reproduction metrics intentionally exclude the bootstrap repository owner and GitHub bot accounts. Their activity may still be operationally useful, but it must not make a community-growth experiment appear successful by itself.

## State funnel

For each issue labelled `growth-seed` in Bootstrap Cohort 1, the observer tracks:

```text
visible seed
  -> external interest
  -> claim
  -> candidate PR
  -> merged candidate
  -> explicitly verified descendant
```

### External interest

A non-owner, non-bot contributor comment or contribution signal associated with the seed.

Interest is useful diagnostic evidence, but it is not a claim or descendant.

### Claim

A seed is considered claimed when at least one of these occurs from an external non-bot contributor:

- the contributor is assigned;
- the contributor comments `/claim`;
- the contributor authors a pull request that GitHub cross-references from the seed.

The `/claim` convention is intentionally lightweight. It does not grant repository permissions or exclusive ownership.

### Candidate PR

A pull request authored by an external non-bot contributor that GitHub cross-references from the Growth Seed.

A candidate PR is not automatically a descendant because it may be incomplete, incorrect, abandoned, or only loosely related.

### Verified descendant

A candidate pull request counts as verified ACE evidence only when:

1. it is merged; and
2. it has the label `ace:verified-descendant`.

The label is an explicit evidence gate. It should only be applied after the applicable review/tests/reproduction evidence support treating the contribution as a useful descendant of the seed.

## Cohort metric

Until ACE has a full parent→descendant lineage schema, the observer reports a deliberately narrower quantity:

```text
SeedReproductionRatio = verified external descendant PRs / Growth Seeds
```

This is **not** the full `R_community`.

The eventual community reproduction number remains:

```text
R_community(W) = verified descendant contributions / verified parent contributions
```

That requires explicit lineage across generations, which is the subject of Growth Seed #25.

## Capacity-aware expansion recommendation

The observer may report one of two advisory states:

- `HOLD_COHORT_1`
- `EVALUATE_COHORT_2`

`EVALUATE_COHORT_2` currently requires all of:

- at least 2 verified external descendant PRs;
- at least 2 claimed seeds;
- no more than 3 open external candidate PRs;
- ACE capacity at or above 0.60, when the Growth Ledger capacity can be read.

This threshold is a bootstrap hypothesis, not a permanent policy.

The observer **never creates Cohort 2**. Expansion remains a human/community decision until evidence supports a higher autonomy level.

## Public status surface

The workflow maintains one issue titled:

`[ACE] Bootstrap Cohort Observatory`

Its body contains:

- a human-readable cohort table;
- aggregate counts;
- current capacity signal from ACE Growth Ledger #23 where available;
- the advisory expansion state;
- a machine-readable `ACE_COHORT_STATE` block.

Keeping one status issue avoids producing a comment for every event.

## Security boundary

The workflow listens to issue/comment metadata and `pull_request_target` metadata.

It must never:

- check out pull-request code;
- execute pull-request code;
- import code or configuration from the pull-request branch;
- expose repository secrets to candidate code;
- auto-merge a contribution;
- apply `ace:verified-descendant` automatically from raw activity;
- create the next cohort automatically.

This keeps observation and evidence accounting separate from execution and acceptance.

## Anti-Goodhart rule

The observer should make gaming inconvenient rather than rewarding volume.

It therefore distinguishes:

```text
comment != claim
claim != candidate
candidate != merge
merge != verified descendant
verified descendant != durable retained contributor
owner/bot activity != external community reproduction
```

Future versions should add reviewer-time accounting, contributor return/retention, descendant durability, and explicit parent lineage rather than simply adding more event counters.

## Related

- `COMMUNITY_GROWTH_ENGINE.md`
- `docs/community/ACE_BOOTSTRAP_EXPERIMENT.md`
- `.github/workflows/ace-community-growth.yml`
- `.github/workflows/ace-cohort-observer.yml`
- issue #23 — ACE Growth Ledger
- issue #25 — parent→descendant lineage evidence
