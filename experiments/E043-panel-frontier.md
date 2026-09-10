# E043 — A verifier panel does not pay for itself, and its one advantage needs real independence

**Status:** complete. **Generator:** `randomness_lab.r1_panel_frontier.v1`.
**Artifact:** [`results/experiments/r1/panel-frontier-seeds42-65.json.gz`](../results/experiments/r1/panel-frontier-seeds42-65.json.gz)
· [report](../results/experiments/r1/panel-frontier-seeds42-65.md)

## The question, and why it had to be split

[Issue #13](https://github.com/MSKazemi/idkmesh/issues/13)'s hypothesis 2 is one
sentence carrying two claims:

> Heterogeneous teams **with independent verification** outperform homogeneous
> teams at equal inference/compute budget on at least some software-engineering
> workloads.

[E041](E041-verifier-strictness-shock.md) established that the R1 lab could test
the first half and not the second: `run_r1_condition` read every candidate with
exactly one verifier, so there was no panel for verifiers to be independent
*within*. A panel, its aggregation, and two dependence shapes were added for
this experiment.

**This document reports the two halves separately and does not combine them into
a verdict on the sentence.** That is not stylistic caution. The sweep shows the
combined statistic cancelling: at correlation 0.5875 the mean difference between
the two dependence shapes is **-0.0008**, indistinguishable from zero, while the
underlying cells are **8 positive and 8 negative**. A single number for this
sentence would be an average of effects that point in opposite directions, and
here it would land on almost exactly nothing.

## Setup

Swarm size 5, 250 tasks, 24 seeds (42–65), 162 cells. Every figure below is
read from the committed artifact, not from a side run; a test asserts the
artifact was generated at the documented sample size, because an earlier version
of it was not. Panel sizes 1, 3, 5;
`need` swept across its whole `[1, k]` range; correlations 0, 0.25, 0.5875, 0.75,
1.0; both dependence shapes; both attention billings.

`need` is swept rather than pinned at the majority because at least one prior
result in this repository survives only on a sub-range of it. Both billings are
run because `human_attention` feeds `resource_cost`, which feeds
`verified_utility_per_unit_cost` — the equal-budget metric the hypothesis is
stated in.

## Result 1 — the verification half, at equal budget

**Billed per verifier read, a panel never beats a single verifier. 0 of 80
cells.** No panel size, no quorum, no dependence shape and no correlation in this
grid recovers the cost of charging `k` reads for a `k`-panel.

This is the robust finding. It holds at every sample size tested and is asserted
against the committed payload, so it fails loudly if it ever stops being true.

## Result 2 — and it is fragile

With panellists unbilled (`per_candidate`), a decisive advantage exists in
exactly three configurations: `k = 5` at `need` 1, 2 and 3, **all at correlation
0**, margin `+0.0188 ± 0.0089`.

Every one requires *genuinely independent* verifiers. At correlation 0.25 and
above the decisive advantage is gone, and the remaining decisive `per_candidate`
cells are negative.

**It also does not survive a smaller sample.** At 120 tasks instead of 250, zero
cells separate decisively. This result is at the edge of detectability and is
deliberately **not** asserted by any test.

So the "independent verification" clause is load-bearing in the strongest sense
available here: the only regime where a panel helps at all is the one where the
independence is real, and even there it helps only when nobody is charged for it.

## What had to be fixed before these numbers meant anything

The headline statistic was **wrong, not merely under-sampled**. Counting how many
cells reverse their verdict between billings is a count of binary outcomes, so
any cell near a tie flips on noise. It never converged:

| seeds × tasks | raw reversals of 80 |
| --- | ---: |
| 2 × 60 | 68 (85%) |
| 4 × 60 | 50 (62%) |
| 8 × 120 | 47 (59%) |
| 16 × 250 | 36 (45%) |
| 24 × 250 | 36 (45%) |
| 32 × 250 | 42 (52%) |

Every cell now carries its across-seed standard error and a reversal counts only
when both sides clear two standard errors of their difference. Under
`per_verifier` all 80 cells separate decisively; under `per_candidate` only about
19 do. **The raw reversal count should not be quoted** — most of it is
tie-flipping. The sensitivity table above is recorded in the module and asserted
by a test, so a small run cannot be reported as a finding.

## Scope

The R1 lab is a simulator. Worker quality, verifier sensitivity, both
correlations and the attention costs are invented parameters. A cell here is
evidence about the model, not about real coding agents. In particular, "a panel
does not pay" is a statement about this cost model, and the cost model is the
part most obviously not measured from anything real.

## Relationship to earlier findings

- [E040](E040-diversity-correlation-threshold.md)'s decision item 3 asked for a
  beta-binomial reshape of the verifier joint-failure distribution.
  [E041](E041-verifier-strictness-shock.md) closed it as *not executable*
  because no joint distribution over verifiers existed. **It is now
  executable and executed**: `item_difficulty` is that reshape, validated
  against `sim/e018_dependence_models.py` to Monte-Carlo error.
- E041's structural premise is superseded, deliberately and explicitly; see the
  dated supersession section in that document.
- The two shapes agree to 12 decimal places at correlation 0 and 1, which is the
  acceptance criterion of
  [issue #380](https://github.com/MSKazemi/idkmesh/issues/380) measured rather
  than asserted.
