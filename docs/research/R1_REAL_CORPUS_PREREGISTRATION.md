# R1 real-corpus preregistration (committed copy)

**Issues:** 30, 70 (refs only; both stay open)

**Evidence status:** a committed copy of a preregistration that exists only as
GitHub issue comments. No real R1 outcome exists. Nothing on this page is a
result, and nothing here changes any rule.

## Why this page exists

The first real R1 decision gate was written as a comment on issue 70 and is
therefore editable, easy to miss, and absent from the repository tree. The
hypothesis, the `helps` / `hurts` / `uncertain` decision rule, the primary
confounder, the 20-work-unit target and the rule for scaling to 3 to 5 workers
all live only there. This page commits that text next to the readiness gate that
enforces part of it, so a reader of the repository can find the gate without the
issue tracker.

**This page is a copy, not a new registration.** The authoritative timestamp is
the comment's own, **2026-08-28T16:34:42Z**. Committing a copy later adds no
preregistration value of its own; it only makes the existing text durable and
linkable. The comments below were fetched with the GitHub REST API on
2026-10-14 and none had been edited (each comment's `updated_at` equals its
`created_at`). Issue bodies were last updated 2026-09-23, so the body text cited
here is as read on 2026-10-14.

The comment was posted from the repository owner's account. The comment does not
record whether a human or owner-controlled tooling wrote it, so treat it as
owner-controlled either way. It is not an independent review.

## Provenance

| source | where | timestamp (UTC) |
|---|---|---|
| Preregistration comment (primary) | [issue 70 comment 5455112557](https://github.com/MSKazemi/idkmesh/issues/70#issuecomment-5455112557) | 2026-08-28T16:34:42Z |
| Identical re-post of the same comment | [issue 70 comment 5455128410](https://github.com/MSKazemi/idkmesh/issues/70#issuecomment-5455128410) | 2026-08-28T16:36:01Z |
| Corpus-integrity update (first-five pilot not eligible) | [issue 70 comment 5455386108](https://github.com/MSKazemi/idkmesh/issues/70#issuecomment-5455386108) | 2026-08-28T17:02:18Z |
| Reusable-infrastructure update (BenchmarkCohort) | [issue 70 comment 5454746056](https://github.com/MSKazemi/idkmesh/issues/70#issuecomment-5454746056) | 2026-08-28T15:59:45Z |
| Readiness-gate intent | [issue 70 comment 5459306168](https://github.com/MSKazemi/idkmesh/issues/70#issuecomment-5459306168) | 2026-08-29T00:52:59Z |
| Readiness-gate delivery report | [issue 30 comment 5459348518](https://github.com/MSKazemi/idkmesh/issues/30#issuecomment-5459348518) | 2026-08-29T01:01:25Z |
| Research question, conditions, evidence gate | [issue 30 body](https://github.com/MSKazemi/idkmesh/issues/30) | created 2026-08-28T14:10:54Z |
| Minimum first corpus, procedure, acceptance criteria | [issue 70 body](https://github.com/MSKazemi/idkmesh/issues/70) | created 2026-08-28T14:41:01Z |

The primary comment was posted twice with identical text, 79 seconds apart. This
page treats the first as the registration and the second as a duplicate. Issue 30
also carries two earlier comments (5453886612, 5453954401) summarizing the
synthetic E012 and E013 results; they are context, not part of the gate.

## The preregistered text

Quoted verbatim from the primary comment. The only differences are layout: the
comment's top-level heading ("Bounded research outcome") is omitted, its
sub-headings sit outside the quotation, and the H1 statement is a nested
quotation. A line-by-line comparison against the fetched comment text (each line
compared after stripping blockquote markers) found no line of the comment
missing from this page apart from that omitted heading. No rule, number or
threshold was altered.

> Verified live evidence now changes the interpretation of this issue.
>
> From merged PR #117's successful exact-head workflow (`Real Two-Attempt Evidence E2E`, run `33187051319`), the two normal real attempts were both independently supported, but they produced the **same candidate patch digest**:
>
> `sha256:8383a0dd5217e9472e5f55eb658248620e539394cb96012dc61c24a3cc33f6cf`
>
> The same run also preserved one verified peer when the other real worker invocation failed (`worker_error`, exit code 2). Therefore the current real evidence establishes **orchestration/replay/fault-isolation reliability**, but it does **not** establish useful candidate diversity or reduced error correlation.

### Falsifiable hypothesis for the first real R1 corpus

> For the first frozen corpus with `swarm_size = 2` and equal attempt budgets:
>
> > **H1:** two prospectively declared structural signatures produce a higher independently verified task-success rate than two replication-baseline attempts from one fixed structural signature.
>
> Primary comparison must use the already-merged `randomness_lab.r1_replay` unchanged. The primary decision statistic is its paired bootstrap classification for independently verified success:
>
> - `helps` only if the paired 95% interval for `success_diverse - success_replication` is entirely above 0;
> - `hurts` only if entirely below 0;
> - otherwise `uncertain`.

### Baseline

> For each eligible held-out work unit:
>
> - **replication arm:** 2 attempts from one frozen `r1_structural_signature`;
> - **diversity arm:** 2 attempts from 2 distinct, prospectively declared structural signatures;
> - same WorkUnit/source revision and equal total attempt count;
> - every included candidate independently verified with retained negative/failed outcomes.
>
> The current #117 same-patch pair is useful as a **control-plane replication example**, but must not be counted as evidence for H1 because it is one smoke task and does not compare structural signatures.

### Primary confounder to freeze before execution

> **Structural quality vs structural diversity.** A different signature may simply be a stronger or weaker worker rather than useful diversity. Record each signature before hidden/final outcomes and report per-signature marginal success alongside pairwise failure correlation. Do not redefine signatures after seeing benchmark results.
>
> Secondary confounders to retain in the corpus: verifier/model-family overlap, task difficulty, missing cost fields, inconclusive verification, and unequal hidden-test coverage.

### Measurement / active decision

> Use the existing target of **at least 20 eligible real work units** for the first bounded result. Publish:
>
> 1. the unchanged `r1_replay` success classification;
> 2. measured pairwise failure correlation for overlapping signatures;
> 3. coverage/exclusion counts;
> 4. negative/inconclusive candidates;
> 5. utility-per-normalized-cost only where compute + human-attention fields are complete.
>
> **Decision rule for the next worker-scaling experiment:** do not treat 3–5 worker fan-out as evidence-improving merely because two-worker execution is reliable. A diversity-motivated scale-up should wait for this frozen N=2 corpus to show `helps`, or remain explicitly exploratory if the result is `uncertain`; if it shows `hurts`, keep the replication baseline and investigate the measured confounders before increasing diversity.
>
> This narrows the uncertainty without adding a new controller, queue, schema, or analysis rule. It preserves the possibility that real diversity does not help.

## The same rules, as a checklist

A tight restatement for scanning. The quotation above is the authority; if the two
ever differ, the quotation wins.

| element | rule | where it comes from |
|---|---|---|
| Hypothesis H1 | Two prospectively declared structural signatures beat two replication attempts from one fixed signature on independently verified success. | primary comment |
| Setting | `swarm_size = 2`, equal attempt budgets, same WorkUnit and source revision per task. | primary comment |
| Decision statistic | Paired bootstrap on `success_diverse - success_replication` from the unchanged `randomness_lab.r1_replay`. | primary comment |
| `helps` | Paired 95% interval entirely above 0. | primary comment |
| `hurts` | Paired 95% interval entirely below 0. | primary comment |
| `uncertain` | Otherwise. | primary comment |
| Primary confounder | Structural quality versus structural diversity: report per-signature marginal success next to pairwise failure correlation; never redefine signatures after outcomes. | primary comment |
| Secondary confounders | Verifier and model-family overlap, task difficulty, missing cost fields, inconclusive verification, unequal hidden-test coverage. | primary comment |
| Size target | At least 20 eligible real work units for the first bounded result. | primary comment; issue 70 body calls it "an experiment target, not a claim that 20 tasks provides universal statistical power" |
| 3 to 5 worker scale-up | Do not scale on reliability alone; wait for `helps`; stay exploratory on `uncertain`; keep the replication baseline and investigate confounders on `hurts`. | primary comment |
| Not evidence for H1 | The same-patch smoke pair from the merged two-attempt end-to-end run. | primary comment |
| Not eligible | The original Phase B2 first-five pilot (burned; its outcomes are excluded from benchmark claims). | issue 70 comment 5455386108 |

Two requirements from the issue bodies shape what counts as eligible, and the
readiness gate checks them: every analyzed candidate needs conclusive independent
verification, and negative candidates must be retained. See the issue 70 body for
the full minimum-corpus list.

## What the comments leave ambiguous

These are gaps in the text as posted, not choices made here. Nothing below was
resolved by this page, and none of it may be resolved after outcomes are seen.

1. **Bootstrap parameters are not in the comment.** The comment names the
   statistic but not the number of bootstrap trials or the seed. At the base
   commit of this page, `randomness_lab.r1_replay` defaults to 200 trials and
   seed 42 and takes the 2.5th and 97.5th percentiles of the paired success
   deltas. Those are facts about the code, not part of the registration. A
   freeze should record the exact values used.
2. **Per-signature marginal success has no producer.** The comment requires it
   alongside pairwise failure correlation. At the base commit the replay report
   contains arm-level `verified_success_rate` for the replication and diversity
   arms and `signature_failure_correlations` (first-attempt failure correlation
   per overlapping signature pair), and a search of `r1_replay.py` finds no
   per-signature marginal success field. Whether a post-processor should
   produce it, or whether it counts as part of the unchanged replay, is not
   stated. This page builds nothing for it.
3. **"Scale-up" is not defined beyond "3 to 5 workers".** The comment does not say
   what exactly is gated (a new experiment, a default configuration, or a claim),
   nor what "remain explicitly exploratory" permits when the result is
   `uncertain`.
4. **"Wait for `helps`" has no stated corpus condition.** The text says the
   frozen N=2 corpus must show `helps` but does not say whether that requires
   the full 20 eligible units or any smaller `helps` classification.
5. **Task difficulty and budget definitions are deferred.** "Equal attempt
   budgets" is stated; equal compute, tokens or human attention are not, and the
   cost-based utility metric is published "only where compute + human-attention
   fields are complete".
6. **Verifier independence is a retained confounder, not a gate.** Verifier and
   model-family overlap is listed as a secondary confounder to retain. The
   comment does not say what overlap would make a task ineligible; the issue 70
   body requires recording `independent_from_worker` truthfully.
7. **The 20-unit figure is a target.** It is called the "existing target", not a
   power calculation. A result at 20 is bounded by the sample.

## Current state

The readiness gate currently reports **blocked**. Run read-only on 2026-10-14
from the base commit of this page, writing nothing into `results/`:

```bash
python -m randomness_lab.r1_readiness \
  --cohort benchmarks/phase-b2-successor-v2/cohort.json \
  --baseline-signature single-worker-baseline-v2 \
  --diversity-signature single-worker-baseline-v2 \
  --diversity-signature role-specialized-two-attempts-v2
```

It exits 0 (a blocked report is valid output unless `--require-ready` is passed)
and prints `status: blocked`, `evidence_class:
repository_contract_state_not_coding_outcome` and `supports_empirical_r1_claim:
false`. Observed values:

| quantity | observed | required |
|---|---:|---:|
| cohort tasks | 5 | at least 20 prospectively |
| eligible work units | 0 | 20 |
| conclusive candidates after normalization | 0 | every analyzed candidate |
| cohort state | `scaffold` | `frozen` or `burned` |
| committed definition digest | none | present before analyzed outcomes |

Every one of the five tasks is ineligible. The reported blockers on each are
`cost_metrics_not_predeclared`, `evidence_not_verified`, `not_held_out`,
`seeded_negative_not_verified` and `unequal_or_unexpected_signature_budget`; one
task also reports `analysis_signatures_not_predeclared`. These are collection
blockers, not experimental outcomes.

So there is no real R1 outcome, no `helps`, `hurts` or `uncertain` classification
on real data, and nothing here licenses scaling to 3 to 5 workers. The
[readiness gate](R1_CORPUS_READINESS.md) describes the checks, and its committed
[current-state report](https://github.com/MSKazemi/idkmesh/blob/main/results/experiments/r1/real-corpus-readiness-current.json)
is the repository's own record of this state.

## What this page does not do

- It does not add, remove or reinterpret a rule from the comments.
- It does not claim H1, or any part of issue 30 or issue 70, is satisfied.
- It does not build the per-signature marginal-success post-processor.
- It does not treat the synthetic harness, the help/hurt sweep or E040 to E043 as
  evidence for H1; those are labelled synthetic in the
  [results ledger](RESULTS_LEDGER.md).
- It is not independent review of the preregistration.
