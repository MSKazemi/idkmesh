# E051 — Does the marginal-evidence selector recover the verifier that actually helps? A synthetic validation against a known truth

**Status:** complete. **Evidence level:** synthetic only. Every verdict below is drawn from a stated
generative model; nothing here is a result about real verifiers, real panels or any real corpus.
**Verdict:** negative result for the shipped marginal selector on this model, with the limits listed at
the end. **Generator:** `sim/e051_marginal_selector_sweep.py` ·
**Artifact:** [`results/E051-marginal-selector-sweep.json`](results/E051-marginal-selector-sweep.json) ·
**Issue:** 693 ("measure marginal evidence contribution before adding a verifier") ·
**Related:** issue 621 and the Adaptive Verification Ecology records AVE-0 to AVE-3, which study
verifier-family diversification and routing in simulation; this record does not duplicate them, it
tests the measurement primitive that issue 693 asked for.

## Research question

Issue 693 asks four things of the add-one-verifier primitive that ships as `idkmesh gate-marginal`
and `idkmesh gate-marginal-benchmark`:

1. does the marginal selector beat random choice, highest standalone accuracy, different-family-first
   and minimum mean pairwise error correlation;
2. when is the signal too sample-unstable to use;
3. can it stop when every candidate is redundant;
4. does its choice survive held-out data.

The repository has no ground-truthed multi-verifier verdict matrix (E016 never measured an AI panel), so
none of these can be answered on observed data and this record does not pretend to. It answers the part
that can be answered without inventing evidence: **given a world where the true value of every candidate
is known, does the real, unmodified selector find it?** That is a validation of the tool against a
generative model, not a measurement of any verifier.

## What was run

The study calls `idkmesh.marginal_evidence_benchmark.build_selection_plan`, the same function that
`benchmark()` uses to freeze its five selectors from design rows only. The first eight regimes use
`benchmark()`'s selection-rule version `marginal-selection-interval-dominance-v0.1` unchanged, with
no threshold tuned. Whether skipping the holdout re-analysis changes anything is tested rather than
assumed: a unit test asserts that `build_selection_plan` and the full `benchmark()` freeze identical
selections on the same inputs (the holdout object is not accepted by the plan API by construction).

**Generative model.** A task is truly `accept` or `reject` with probability one half. A verifier's
verdict is the truth unless an error indicator is set (errors are symmetric: one-sided
false-accept/false-reject structure is **not** modelled). The current panel has 3 or 4 members of error
rate 0.30; every member after the first copies the first member's error indicator with probability
`w` (0.2 "low" or 0.7 "high") and is otherwise independent, which is one stylised shared-blind-spot
shape and not a claim about real panels. Candidates are drawn from these recipes:

| candidate | error recipe | accuracy |
| --- | --- | ---: |
| `dup` | exact copy of the first member (declared the same family as the panel) | 0.70 |
| `near_dup` | copies the first member's error 90% of the time (declared a new family) | 0.70 |
| `indep_strong` | independent, error 0.15 | 0.85 |
| `indep_equal` | independent, error 0.30 | 0.70 |
| `indep_weak` | independent, error 0.45 | 0.55 |
| `harmful` | independent, error 0.60 (worse than a coin flip) | 0.40 |
| `complementary` | errs 0.30 where the panel is right, 0.05 where it is wrong | 0.76 |
| `strong_redundant` | copies the first member's error 70% of the time, else error 0.02 | 0.78 |

**Truth.** For each regime a separate population sample of 40,000 tasks, from its own random stream and
shown to no selector, gives each candidate's true panel-error change
`error(current) - error(current + candidate)` under the tool's own rule (`accept_votes > quorum * size`).
It is a Monte-Carlo estimate (standard error about 0.002). A candidate with true change above `+0.01` is
"helpful", below `-0.01` "harmful", otherwise "redundant"; that tolerance is a labelling convention of
this study. The same population sample also gives the tool's own `delta_effective_votes` and standalone
accuracy for every candidate, which is what makes a disagreement visible.

**Grid.** 16 regimes = panel size (3, 4) x shared weight (0.2, 0.7) x four candidate pools, and seven
design sizes (20, 40, 80, 160, 320, 640, 1,280 rows), 100 independent replicates per cell
(each with a fresh design draw): 16 x 7 x 100 = **11,200 frozen selections per strategy** in total. Bootstrap: 100 replicates, 90% intervals, the tool's minimum.
A strategy that does not select counts as value 0 (the panel is left as it is).

**What was and was not fixed in advance (Registration: none).** The eight regimes using pools `mixed`
and `redundant_only` and the grid were fixed before any full result was read, with one exception that
is disclosed: a six-replicate look at a single cell (3-member panel, low sharing, `mixed`, 160 rows) to
time the run, which showed the selector abstaining, after which the grid was extended from 320 to 1,280
rows. The first full run then showed the selector picking only the two least accurate candidates, so
eight further regimes were added **post hoc** (marked `post_hoc` in the artifact):
`no_anti_informative` (removes the worse-than-chance candidate, to ask whether the pattern depends on
including it) and `accuracy_trap` (adds a candidate that is both the most accurate and largely
redundant with the panel, because without one the comparison would be tilted towards the
highest-accuracy baseline). Results are reported for both groups separately below.

## Result 1 — the selector almost never selects, and when it does it does not pick a helpful candidate

Over all 16 regimes and all 7 sample sizes (11,200 replicates):

| strategy | selected | selected a helpful candidate | redundant | harmful | mean true panel-error change (abstain = 0) |
| --- | ---: | ---: | ---: | ---: | ---: |
| marginal effective votes | 1,548 | **1** | 1,136 | 411 | -0.0008 |
| random eligible | 11,200 | 4,109 | 4,305 | 2,786 | +0.0051 |
| highest standalone accuracy | 11,200 | 7,270 | 2,742 | 1,188 | +0.0231 |
| different family first | 11,200 | 7,300 | 3,127 | 773 | +0.0237 |
| min mean pairwise error correlation | 11,154 | 8,169 | 1,379 | 1,606 | +0.0217 |

Split by registration: in the eight pre-specified regimes the marginal selector made 915 selections,
none helpful, 504 redundant and 411 harmful, and the three informed baselines averaged +0.015, +0.016
and +0.007; in the eight post-hoc regimes it made 633 selections, one helpful and 632 redundant, against
+0.031, +0.032 and +0.036. The only candidates it ever chose were `harmful` (915 times), `indep_weak`
(632 times) and `complementary` (once); it never chose `dup` or `near_dup`.

**Why, on the population sample.** The selector ranks candidates by `delta_effective_votes`, and the tool
reports that quantity alongside the true panel-error change, which this study can compare. The
effective-vote count compares the measured panel error to an independent panel *of the same mean
accuracy*; adding a low-accuracy verifier lowers the mean accuracy and therefore raises the effective
vote count even while it raises the panel's error. In the 3-member, high-sharing `mixed` regime the
population values are:

| candidate | true panel-error change | population `delta_effective_votes` | accuracy |
| --- | ---: | ---: | ---: |
| `indep_strong` | +0.035 | -0.07 | 0.853 |
| `complementary` | +0.030 | 0.28 | 0.770 |
| `indep_weak` | -0.001 | 1.07 | 0.546 |
| `harmful` | -0.017 | **2.13** | 0.401 |

Across the 16 regimes the Spearman correlation between the true change and the effective-vote delta
ranges from -0.8 to +0.8 with no consistent sign (4 to 7 candidates each, so descriptive only), whereas
the correlation with standalone accuracy is positive in 14 of 16. This is a mechanism that fits the
population numbers; it is not proven beyond these regimes. The report keeps panel-error change and
effective-vote change in separate columns, which is what the specification says to do, so nothing here
is a hidden defect of the report. What the result shows is that the *selection rule* is keyed to the
column that disagrees with the true change.

## Result 2 — sample instability: the selector needs about 640 or more rows before it resolves at all

Share of the 1,600 replicates per design size in which the marginal selector chose a candidate:
n=20 **0**; n=40 14; n=80 25; n=160 82; n=320 216; n=640 467; n=1,280 744 (0%, 0.9%, 1.6%, 5%, 13.5%,
29%, 46.5%). Below 80 rows it essentially always returns unresolved. The reason changes with size: at n=20 and
n=40 the leading code is `unresolved_design_effective_vote_metrics` (1,529 and 688 of the abstentions: the
bootstrap could not produce a finite effective-vote interval); at n=80 `marginal_ordering_not_interval_separated`
(745) overtakes `marginal_gain_not_positive_with_interval_support` (687); from n=160 up the ordering code
dominates (1,054 of 1,518 abstentions at n=160, 812 of 856 at n=1,280). The stop rule is behaving as designed. But the number of times it resolves *to the wrong candidate* grows with n: in the 3-member
high-sharing `mixed` regime it picks `harmful` in 0, 1, 3, 12, 24, 57 and 94 of 100 replicates as n
rises, so more data makes it more confidently wrong, not less. The correlation baseline also abstained
on 46 of 1,600 replicates at n=20 (no measurable pairwise correlation) and never above that.

## Result 3 — the stop rule: abstaining does not track redundancy

In the three regimes in which no candidate is helpful (3-member panel, both sharing levels, and the
4-member high-sharing panel, all `redundant_only`), the marginal selector abstained in 1,656 of 2,100
replicates (78.9%), with mean true change -0.0022 against -0.0100 to -0.0194 for the four baselines,
which are forced to add something. That is a genuine benefit of being able to say "no": it is the one place where the
marginal selector beats the baselines on average (+0.021 to +0.049 against them in the 3-member
low-sharing `redundant_only` regime at n=1,280).
But in the 13 regimes where at least one candidate *is* helpful it abstained in 87.9% of replicates, so
it abstained *more* when a helpful verifier existed. It is closer to "almost never add" than to "add
when redundant, stop when redundant". Also, among the 444 selections it did make in the no-helpful
regimes, 186 were harmful.

## Result 4 — the baselines, including where they fail

Highest standalone accuracy and different-family-first are near-identical here (the only declared-family
overlap is the exact duplicate), so they are not independent evidence of two separate heuristics. In the
`accuracy_trap` pool the highest-accuracy rule picks `strong_redundant` (true change +0.001 to +0.019)
instead of `complementary` (+0.015 to +0.069) in 54 to 92 of 100 replicates at n=320 and n=1,280, and
**the minimum-correlation rule picks `complementary` in 98 to 100 of 100 replicates** at both sizes in all four
`accuracy_trap` regimes, with a higher mean true change than the accuracy and family rules there (for example
+0.069 against +0.024 at the 4-member low-sharing panel, n=1,280). So the complementarity-aware rule wins exactly where the
complementarity story predicts it should, and that is evidence for the idea behind the issue; it is not
evidence for the *effective-vote ranking* that the tool currently uses to operationalise it. The
minimum-correlation rule is not uniformly good: at 4-member low-sharing `redundant_only`, n=1,280 it picked a
harmful candidate in 57 of 100 replicates (accuracy rule 50, family rule 0), and in 3-member low-sharing `mixed`
at n=20 in 30 of 95. Random choice has the lowest overall mean true change of the four baselines (+0.0051), as it should.

## What this does and does not show

* It shows that, **on this generative model**, the shipped marginal-effective-vote selector (rule
  `marginal-selection-interval-dominance-v0.1`) should not be promoted: across 11,200 frozen selections
  it chose a helpful candidate once, and its choices were the two lowest-accuracy candidates.
* It does **not** show that "marginal evidence contribution" is a bad idea. The report's
  `panel_error_delta` column has the right sign on this model; it is the effective-vote ranking that
  does not. No alternative rule (for example ranking on the interval-supported panel-error delta) was
  tried or tuned here, and none should be adopted on the strength of this record without a
  pre-specified comparison.
* The model has symmetric errors, one dependence shape, panels of 3 or 4, 0.5 base rate, and no
  candidate-level heterogeneity across tasks. A worse-than-chance verifier (`harmful`, accuracy 0.40) is
  extreme; it drives the first result but the `no_anti_informative` regimes, which exclude it, show the
  selector then picking `indep_weak` (accuracy 0.55, true change zero or slightly negative), so the pattern is not only
  due to that one candidate.
* The oracle is a Monte-Carlo estimate; the "redundant" band of +-0.01 is a labelling choice.
* Replicate SEs on paired differences are in the artifact and are descriptive only; **no significance
  test was run, no p-values are quoted and no multiple-comparison correction applies** because no
  confirmatory claim is made. The 16 regimes are not independent samples of anything.
* It does not touch observed data. The issue's remaining gate, a broader preregistered *observed*
  cohort, is untouched and remains human/data-gated: the repository still has no ground-truthed
  multi-verifier verdict matrix, and held-out real splits belong to issue 973. This record is not
  promotion evidence for AVE or the Connector Control Plane integration in either direction; the
  specification's integration boundary stands (diagnostic only, no routing, EvaluatorPlan, acceptance
  or merge authority).

## Reproduction

```bash
PYTHONPATH=. python sim/e051_marginal_selector_sweep.py \
  --workers 4 --pretty --output experiments/results/E051-marginal-selector-sweep.json
```

Tens of minutes with four workers on a loaded 12-core machine (not carefully timed); the report is
independent of `--workers`. To avoid rebuilding a 101-entry binomial table on every call, the sweep
memoises `gate_audit.majority_error_independent` for the duration of the run; the memo is a pure cache
that returns the identical float, a unit test checks bit-identity and restoration, and the repository
function is not modified. `tests/test_e051_marginal_selector_sweep.py` is fast (small samples, internal
consistency of the committed artifact). `tests/test_e051_committed_artifact.py` (marked `sim`, about 20
seconds) re-derives the oracle and the smallest-design-size cell of two regimes. `results/` is
gitignored, so the artifact is committed with `git add -f`, as its neighbours are.

**Interpreter reproducibility (measured, not assumed).** The artifact was generated on CPython 3.12.3.
Re-deriving it on 3.11.16 reproduces the oracle, the marginal selector and the accuracy and family
baselines **exactly**, but not the minimum-mean-pairwise-error-correlation baseline: that rule's argmin
sits on near-ties and the repository's correlation arithmetic is float-summation sensitive, so a different
interpreter flips a few picks. Across all 16 regimes at the smallest design size this was 30 differing
values, all inside that one baseline, in 4 regimes, with a largest difference of 0.00084 in a mean regret
and 2 of 100 replicates in a selection count. The committed-artifact test therefore compares that baseline
within a stated tolerance (0.002 for floats, 3 for counts) and everything else exactly, and a control test
checks the tolerance rejects a real change. Result 4's statements about the minimum-correlation rule are
quoted from the 3.12 run; differences of this size do not change them, but they are not bit-reproducible
across CPython versions. The shipped library code that causes this is not modified here.

## Controls the unit tests pin

* An **exact duplicate** of an admitted verifier is never scored as a gain: its true panel-error change
  is `<= 0` in both panel sizes, and an independent informative verifier scores more than +0.02.
* A **panel-mimic** (a verifier equal to the 4-panel's decision on every task) changes no decision and
  scores exactly 0.0 panel-error change when added to make a 5-panel.
* The tool's `delta_effective_votes` for the `harmful` candidate exceeds the exact duplicate's, pinning
  the disagreement that Result 1 describes so a change in the metric is noticed.

What these controls expose beyond the issue's wording: an exact duplicate does not score "about zero"
under panel error. Adding one extra vote for an existing member changes the quorum arithmetic (here an
odd to even step with ties rejecting), so its change was -0.026 and -0.004 at 3 members and -0.020 and
-0.008 at 4, in the low and high sharing regimes. A true zero requires a verifier that cannot flip a
decision, which is what the panel-mimic is.
