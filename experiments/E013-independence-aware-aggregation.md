# E013 — Independence-Aware Verifier Aggregation

## Research question

At the same nominal review cost and using exactly the same verifier votes, when should IDKMesh discount a large correlated verifier cluster instead of counting every vote equally?

This follows E012, which showed that verifier unanimity becomes misleading when errors are correlated.

## Hypothesis

A transparent independence-aware rule should help when a large verifier cluster shares failure modes, but it should **not** be assumed to help when reviewers are genuinely independent.

The purpose of this experiment is therefore not to prove that group weighting is universally superior. It is to identify the regime where it becomes useful and preserve the negative result where it hurts.

## Two aggregation rules

Both rules consume exactly the same sampled verifier panel.

### 1. Naive majority

Every verifier receives one equal vote:

`decision = majority(all verifier votes)`

### 2. Group-balanced majority

Verifiers are partitioned into declared independence groups. First compute a majority decision inside each group, then give each group one equal vote:

`decision = majority( majority(group_1), ..., majority(group_k) )`

This is intentionally simple. It is a transparent baseline for measuring the value and cost of independence information, not a proposed final IDKMesh trust algorithm.

## Reference panel

```text
group sizes = [7, 1, 1, 1, 1]
nominal verifier count = 11
independence groups = 5
individual verifier accuracy = 0.75
truth prevalence = 50/50
trials per seed = 2,000
seeds = 50
within-group correlation = [0, 0.25, 0.5, 0.75, 1]
```

The large 7-verifier group models many reviewers sharing a model family, provider, prompt template, retrieval source, test generator, organization, or other correlated failure source. The four singleton groups model independent evidence sources.

Within each group, correlation uses the same controlled shared-correctness mixture introduced in E012. Different groups are sampled independently.

## Reproduce

```bash
python sim/verification_aggregation_sim.py --pretty
```

Machine-readable reference result:

`experiments/results/E013-independence-aware-aggregation-50-seed-summary.json`

## Result

Mean overall classification error across 50 seeds:

| Within-group correlation | Naive majority | Group-balanced | Better rule | Group-balanced seed wins |
| ---: | ---: | ---: | --- | ---: |
| 0.00 | **0.033710** | 0.064990 | naive | 0 / 50 |
| 0.25 | 0.089040 | **0.075180** | group-balanced | 50 / 50 |
| 0.50 | 0.142940 | **0.083930** | group-balanced | 50 / 50 |
| 0.75 | 0.196620 | **0.094330** | group-balanced | 50 / 50 |
| 1.00 | 0.245520 | **0.102700** | group-balanced | 50 / 50 |

The first tested crossover occurs at correlation `0.25` for this panel geometry and accuracy. This is **not** a universal threshold; it depends on group sizes, verifier accuracy, quorum, and the dependence model.

## Interpretation

### Negative result: independence-aware weighting can hurt

When `rho = 0`, all 11 verifier errors are independent. Naive majority correctly uses eleven independent signals and reaches about 3.37% error. Group-balanced voting throws away information by compressing seven independent votes into one group vote, increasing error to about 6.50%.

Therefore:

> **Do not discount reviewers merely because they share a declared category if their errors are actually independent.**

### Positive result: correlated clusters can dominate naive voting

As within-group error correlation increases, seven nominal votes increasingly behave like one shared error source. Naive majority continues counting all seven separately, so the large group can dominate the panel.

At full correlation, naive majority reaches about 24.55% error—close to the cluster's individual 25% error rate—while group-balanced voting is about 10.27% because the large cluster receives one group vote among five independent group decisions.

Therefore:

> **Reviewer count should not be confused with independent evidence count.**

### Design implication

IDKMesh should not use a permanent rule such as `one account = one vote` or `one model call = one vote` for high-stakes verification.

It should eventually estimate an evidence weight from factors such as:

- historical pairwise error correlation;
- shared model/provider family;
- shared prompt/reasoning template;
- test origin;
- retrieval/data source;
- toolchain and execution environment;
- organizational/trust domain;
- shared dependencies;
- specialization by defect type.

But E013 also warns against blindly using metadata-based diversity weights: independence should ideally be **measured from outcomes**, not only declared.

## Mathematical connection

For a group with nominal size `N` and average correlation `rho`, the existing IDKMesh heuristic is:

`N_eff ~= N / (1 + (N-1) rho)`

For the 7-member cluster:

- `rho = 0` -> `N_eff ~= 7`
- `rho = 0.25` -> `N_eff ~= 2.8`
- `rho = 0.5` -> `N_eff ~= 1.75`
- `rho = 1` -> `N_eff = 1`

Group-balanced voting is a coarse approximation to the `rho = 1` case. A better future method should continuously discount evidence based on estimated dependence rather than collapsing every declared group to exactly one vote.

## What this does NOT show

- Declared independence groups are assumed correct.
- All verifiers have the same marginal accuracy.
- The dependence model is synthetic.
- The task is binary classification, not real code review.
- No strategic collusion or adversarial identity creation is modeled.
- No uncertainty exists about the group labels themselves.
- The observed `0.25` crossover is specific to this experiment configuration.

## Next falsifiable step

E014 should remove the known-correlation oracle:

1. generate verifier histories with heterogeneous accuracy and dependence;
2. estimate reliability and pairwise correlation from past outcomes;
3. compare naive majority, declared-group balancing, estimated effective-sample-size weighting, and Bayesian/log-odds weighting;
4. evaluate calibration and false acceptance under distribution shift;
5. then move the mechanism onto bounded real software tasks with independent hidden tests.

## Decision direction

The evidence supports a conditional principle, not a fixed algorithm:

> **Weight verification by estimated independent information, while preserving the raw evidence and uncertainty about the estimate.**

Related issue: #71.
