# Marginal Evidence Held-Out Benchmark v0.1

**Status:** experimental, versioned diagnostic benchmark.  
**Issue:** [#693](https://github.com/MSKazemi/idkmesh/issues/693)  
**Related research:** [#621](https://github.com/MSKazemi/idkmesh/issues/621), PR #622.  
**Authority:** diagnostic only.

This contract extends
[Marginal Evidence Analysis v0.1](MARGINAL_EVIDENCE_V0_1.md) with a bounded
held-out benchmark.

The benchmark asks:

> If candidate-verifier selection is frozen using one design corpus, how does
> that selection behave on a disjoint holdout corpus compared with four simpler
> selectors?

It does **not** ask which selector should be deployed in production, and it does
not mutate the Connector Control Plane or Adaptive Verification Ecology (AVE).

## 1. Why this is a separate contract

The first `gate-marginal` slice measures every candidate on one fixed corpus.
That is necessary but insufficient for a routing policy: choosing the candidate
that looks best on the same rows used to invent or tune the selection rule can
overfit those rows.

The benchmark therefore separates two phases:

```text
design verdict matrix
        |
        v
frozen selection plan
        |
        |  SHA-256 bound
        v
disjoint holdout verdict matrix
        |
        v
side-by-side evaluation only
```

The holdout object is not accepted by the selection-plan API. This is a code
boundary, not only a documentation convention.

## 2. CLI

```bash
idkmesh gate-marginal-benchmark \
  examples/gate-audit/marginal-evidence-benchmark-config.example.json \
  --pretty
```

Optional output:

```bash
idkmesh gate-marginal-benchmark benchmark-config.json \
  --out benchmark-report.json \
  --pretty
```

The command refuses to write the report over:

- the benchmark config;
- the design verdict matrix;
- the holdout verdict matrix.

## 3. Versioned config

Schema:

- `schemas/marginal-evidence-benchmark-config-v0.1.schema.json`

Example:

- `examples/gate-audit/marginal-evidence-benchmark-config.example.json`

Required fields:

| Field | Meaning |
| --- | --- |
| `benchmark_id` | Stable benchmark identity. |
| `design_matrix` | Relative path to the design verdict matrix. |
| `holdout_matrix` | Relative path to the holdout verdict matrix. |
| `current_verifier_ids` | Already-selected panel. |
| `candidate_verifier_ids` | Eligible add-one candidates. |
| `verifier_families` | Structural family metadata used only by the family baseline. |
| `random_seed` | Seed material for the deterministic random baseline. |
| `bootstrap` | Finite-sample uncertainty configuration used by design and holdout diagnostics. |

Matrix paths must be relative to the config directory and must not escape that
directory after path resolution.

The family map must exactly cover the current and candidate verifier IDs. Extra
or missing family metadata is refused instead of ignored.

## 4. Split-integrity requirements

Both matrices must independently satisfy the strict gate-audit verdict-matrix
contract.

The benchmark additionally requires:

- the same `gate_id`;
- the same evidence class;
- the same quorum;
- every requested current/candidate verifier to exist in both matrices;
- **no candidate ID overlap at all** between design and holdout matrices.

The last condition includes probe IDs. Reusing a row identity across the two
splits is treated as evidence leakage and is refused.

## 5. Preregistered selectors

v0.1 always evaluates exactly five strategies. Their definitions are part of
the contract; they are not tuned from holdout outcomes.

### 5.1 Marginal effective votes

Strategy ID:

`marginal_effective_votes`

Selection uses the design `gate-marginal` report with bootstrap enabled.

The strategy is resolved only when:

1. every candidate has a numeric, finite, uncensored
   `delta_effective_votes`;
2. every candidate has a sufficient bootstrap result;
3. every candidate has a finite effective-vote-delta interval;
4. the largest point estimate is unique;
5. the top candidate's interval lower bound is **strictly greater** than every
   other candidate's interval upper bound.

A candidate can still have an unrelated diagnostic status such as
unmeasurable error correlation. That does not block this selector when the
effective-vote estimand itself is fully resolved. The correlation baseline has
its own separate fail-closed rule.

If any requirement fails, the strategy is `unresolved`.

There is deliberately **no fallback** to panel-error delta, standalone accuracy,
family metadata, or correlation. A fallback would silently change the
preregistered estimand after seeing inconvenient evidence.

The interval-separation rule is intentionally conservative. It is a stability
gate, not a claim that non-overlapping percentile intervals are an optimal
statistical test.

Rule version:

`marginal-selection-interval-dominance-v0.1`

### 5.2 Random eligible

Strategy ID:

`random_eligible`

The candidate is chosen from canonical source-matrix candidate order using:

```text
SHA256(random_seed || NUL || candidate_id_1 || NUL || ... || candidate_id_n)
```

The digest integer modulo candidate count selects the index.

This avoids Python-version PRNG drift. It is a reproducible random-style
baseline, not a security primitive.

### 5.3 Highest standalone accuracy

Strategy ID:

`highest_standalone_accuracy`

Choose the largest design-corpus standalone accuracy.

Tie break:

1. canonical source-matrix order.

### 5.4 Different family first

Strategy ID:

`different_family_first`

1. Prefer candidates whose declared family is absent from the current panel.
2. Within that pool, choose highest design standalone accuracy.
3. Break remaining ties by canonical source-matrix order.
4. If no family is novel, apply highest standalone accuracy to all candidates.

Family is structural metadata only. The benchmark does not interpret different
family labels as proof of independence.

### 5.5 Minimum mean pairwise error correlation

Strategy ID:

`minimum_mean_pairwise_error_correlation`

Every candidate must have measurable mean error correlation against the current
panel. If any candidate is unmeasurable, the strategy is unresolved because the
unknown candidate could be the minimum.

Otherwise:

1. choose minimum mean design error correlation;
2. tie-break by higher design standalone accuracy;
3. then canonical source-matrix order.

## 6. Frozen selection plan

The design-only plan records:

- rule version;
- SHA-256 digest of the exact design verdict matrix;
- canonical current IDs;
- canonical candidate IDs;
- all five selector states;
- selected verifier IDs or unresolved reason codes;
- design score used by each selector;
- SHA-256 digest of the complete plan.

The digest is copied into report provenance.

The holdout matrix is not an argument to `build_selection_plan()`.

Tests also mutate every non-probe holdout verdict and require the selection plan
to remain byte-equivalent as a Python object.

## 7. Holdout evaluation

Only after selection is frozen does the benchmark evaluate each selected
candidate on the holdout matrix.

For each strategy it reports:

- selected verifier ID;
- whether design selection was resolved;
- holdout marginal-evidence status;
- holdout panel-error delta;
- holdout effective-vote delta when resolvable;
- holdout standalone accuracy;
- holdout mean error correlation;
- holdout bootstrap uncertainty;
- separate seeded-probe effect;
- warnings.

If a strategy was unresolved on design evidence, it is marked
`not_evaluated`.

The benchmark does **not** inspect holdout outcomes and then choose a fallback.

## 8. No winner field

Schema:

- `schemas/marginal-evidence-benchmark-report-v0.1.schema.json`

The report intentionally contains no:

- `winner`;
- `best_strategy`;
- production routing recommendation;
- `selected_connection_id`;
- EvaluatorPlan;
- acceptance verdict;
- merge decision.

The five outcomes are presented side by side.

A later research synthesis may compare them across multiple preregistered
benchmarks. One fixture is not enough to promote a policy.

## 9. Evidence class

The committed example uses:

`"evidence_class": "synthetic"`

It proves:

- parser behavior;
- selector determinism;
- split isolation;
- schema validity;
- reproducible bootstrap plumbing;
- authority boundaries.

It does **not** establish that one selector is better for real software review.

Observed evidence must remain labeled `observed` and should come from a
preregistered corpus that was not used to design the selection rule.

## 10. Relationship to AVE

Issue #621 and PR #622 study Adaptive Verification Ecology, including:

- family diversification;
- risk-adaptive quorum;
- posterior routing;
- exploration;
- review backpressure;
- known-bad probes.

This benchmark does not duplicate those controllers.

Its narrower role is to answer one reusable question before any AVE/Connector
Control Plane integration:

> Does the marginal-evidence selector retain useful behavior on rows it did not
> use to choose the candidate, and how does that compare with simpler
> selectors?

Until a broader held-out corpus supports promotion, this module remains
diagnostic.

## 11. Security and authority boundary

The benchmark:

- performs no live provider/model call;
- executes no candidate code;
- reads only the config and two local verdict matrices;
- resolves matrix paths inside the config directory;
- materializes no secrets;
- dispatches no work;
- modifies no routing state;
- creates no EvaluatorPlan;
- accepts no candidate;
- grants no merge authority.

## 12. Provenance

The report binds:

- normalized benchmark config by SHA-256;
- design matrix by SHA-256;
- holdout matrix by SHA-256;
- frozen design-only selection plan by SHA-256;
- tool version.

The design and holdout digests are separate so a changed evaluation corpus
cannot masquerade as the same benchmark.

## 13. Known limitations

v0.1 does not:

- estimate causal reviewer value;
- optimize reviewer cost or latency;
- aggregate results across multiple benchmark cohorts;
- correct for multiple comparisons;
- infer family membership;
- learn a threshold from observed outcomes;
- declare a production winner;
- actuate routing.

The interval-separation rule is deliberately conservative and should be changed
only through a new explicit selection-rule version.

## 14. Acceptance contribution to #693

This slice directly addresses:

- comparison with random eligible addition;
- comparison with highest standalone accuracy;
- comparison with different-family-first;
- comparison with minimum mean pairwise error correlation;
- held-out evaluation separated from statistic/threshold design;
- fail-closed unresolved state for unstable evidence;
- explicit relationship to #621 / PR #622;
- diagnostic-only authority.

Remaining #693 work after this slice is evidence collection/synthesis across a
broader preregistered cohort before considering any dry-run Connector Control
Plane or AVE integration.
