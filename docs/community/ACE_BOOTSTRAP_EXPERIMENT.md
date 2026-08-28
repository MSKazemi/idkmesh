# ACE Bootstrap Experiment — Cohort 1

**Experiment window:** 2026-08-28 through 2026-09-27  
**Status:** Active bootstrap experiment  
**Parent design:** [`COMMUNITY_GROWTH_ENGINE.md`](../../COMMUNITY_GROWTH_ENGINE.md)  
**Public state:** issue #23 (`[ACE] Community Growth Ledger`)

## Question

Can IDKMesh create a small set of bounded, discoverable contribution opportunities that produce verified useful descendants **without increasing maintainer/reviewer load faster than useful output**?

This is the first real test of the ACE hypothesis.

## Cohort 1

The initial cohort deliberately contains only five Growth Seeds:

| Issue | Niche | Seed type | Intended contribution |
| --- | --- | --- | --- |
| #24 | Documentation / community | Onboard | Audit the 15-minute newcomer path |
| #25 | Measurement / data model | Measure | Define parent -> descendant evidence links |
| #26 | Security | Secure | Threat-model the ACE workflow |
| #27 | Coding / modeling | Measure | Build a tiny ACE population simulator |
| #28 | Research / coordination | Onboard | Decompose one research track into five microtasks |

All five use GitHub's standard `good first issue` and `help wanted` discovery labels.

## Why only five?

ACE is explicitly capacity governed. Creating dozens of issues before we know whether anyone can understand, claim, complete, and review them would optimize issue count rather than community reproduction.

Cohort 2 should **not** be spawned merely because time passed.

## Cohort 2 gate

Create the next five Growth Seeds only when at least one of these evidence conditions is true and review capacity is healthy:

1. at least two Cohort-1 seeds produce verified descendant PRs/artifacts; or
2. at least three distinct external contributors meaningfully engage with Cohort-1 seeds and the median first-response/review latency remains below 72 hours; or
3. Cohort 1 produces strong evidence that the seed format itself needs redesign, in which case Cohort 2 becomes a corrected experiment rather than simple expansion.

Do **not** expand if there is a growing unreviewed queue, unresolved conduct/security issue, or the bootstrap maintainer cannot review new work.

## Primary measurements

For each seed record:

- views/engagement if available without invasive tracking;
- whether a contributor claims or discusses it;
- time from issue creation to first external meaningful interaction;
- time from first interaction to candidate PR/artifact;
- whether the candidate is accepted/verified;
- approximate reviewer minutes;
- whether maintainer clarification was required before useful work began;
- whether the contributor makes a second meaningful contribution within 30 days;
- whether the result creates another bounded useful opportunity.

## Reproduction metric

For a window `W`:

```text
R_community(W) = verified descendant contributions / verified parent contributions
```

For this bootstrap, a descendant counts only when it creates an inspectable artifact and passes the applicable review/verification. Comments, stars, raw commits, and issue creation do not count by themselves.

## Efficiency metric

The long-term optimization target is approximately:

```text
verified useful descendants
-----------------------------------------
reviewer minutes + maintainer minutes
```

Compute cost can be added once executable agents/benchmarks are part of the loop.

## Cohort outcome classes

### Reproduce

A seed generates at least one verified descendant and the contributor can begin with little maintainer clarification.

### Learn

A seed does not reproduce, but produces useful evidence about ambiguity, missing documentation, poor scope, or an incorrect growth hypothesis.

### Noise

A seed creates activity but no useful artifact/evidence, or consumes disproportionate review/triage effort. Noise-producing seed strategies should lose future allocation probability.

### Overload

Useful work exists but review capacity becomes the bottleneck. ACE should enter `CONSOLIDATE`, suppress spawning, and prioritize review/mentoring/cleanup.

## Bootstrap strategy allocation

Cohort 1 intentionally samples multiple niches instead of five coding issues. This tests whether IDKMesh can attract and retain different contributor types.

Initial strategy probabilities are therefore treated as uniform priors rather than optimized weights.

After outcomes exist, later cohorts can update strategy weights using a replicator-mutator or contextual-bandit rule while retaining a non-zero exploration probability.

## Safety / anti-Goodhart constraints

- no automatic direct messages;
- no unsolicited mass mentions;
- no auto-merge;
- no issue-generation loop based on stars/comments alone;
- no personal productivity leaderboard;
- no autonomous governance/security-policy changes;
- `pull_request_target` workflows must never execute untrusted contributor code;
- expand only from evidence + available review capacity.

## Review checkpoint

At the end of the experiment window—or earlier if enough evidence arrives—publish a short results note answering:

1. Which seeds produced verified descendants?
2. Which seed types required the least maintainer explanation?
3. What was the reviewer/maintainer cost?
4. Did any first-time contributor return?
5. What should receive more/less probability in Cohort 2?
6. Should ACE remain conservative, expand, or be redesigned?

Negative results are valid results.
