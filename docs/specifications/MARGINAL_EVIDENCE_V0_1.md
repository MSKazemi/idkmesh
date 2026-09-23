# Marginal Evidence Analysis v0.1

**Status:** experimental, versioned diagnostic contract.  
**Issue:** [#693](https://github.com/MSKazemi/idkmesh/issues/693)  
**Authority:** diagnostic only.

The `idkmesh gate-marginal` command asks a narrower question than
`gate-audit`:

> Given a fixed ground-truthed verdict matrix, a current verifier panel, and
> one possible additional verifier, what changed under the exact same gate
> rule?

It is an **add-one historical analysis**. It does not claim that a verifier has
an intrinsic independence score, does not rank candidates, and does not select
or dispatch a verifier.

## Why this exists

A routing policy that chooses the highest-accuracy verifier can add almost no
new information when that verifier repeats the current panel's failure pattern.

A routing policy that chooses a different provider/model family can also be
wrong: family labels are structural proxies, not observed evidence of
independence.

The v0.1 diagnostic therefore reports several separate facts instead of
collapsing them into one trust score:

- standalone verifier accuracy;
- current-panel and augmented-panel error;
- change in measured effective votes when resolvable;
- observed pairwise error correlation with each current reviewer;
- candidate correctness on rows the current panel missed;
- candidate errors on rows the current panel got right;
- actual gate decisions changed to correct vs. changed to wrong;
- seeded known-bad probe effects, reported separately;
- optional paired candidate-row bootstrap intervals.

These quantities describe **marginal panel evidence contribution under one
declared gate rule and corpus**. They are not permanent properties of the
verifier.

## Input

The input JSON is exactly the strict verdict-matrix contract documented in
[Gate Audit v0.1](GATE_AUDIT_V0_1.md).

The same parser is shared by both tools. Therefore the following behavior is
identical:

- UTF-8 input, with an optional BOM;
- standard JSON only;
- duplicate JSON keys refused;
- `NaN`, `Infinity`, and `-Infinity` refused;
- complete verifier-by-candidate matrix required;
- every candidate requires ground truth;
- seeded probes must be known-bad;
- at least two non-probe candidates;
- the gate accepts only when `accept_votes > quorum * panel_size`.

The caller additionally supplies:

- one or more `--current VERIFIER_ID` values;
- zero or more `--candidate VERIFIER_ID` values.

When `--candidate` is omitted, every verifier in the matrix that is not
already in the current panel is analyzed.

A verifier cannot be both current and candidate. Unknown or duplicate IDs are
refused.

## CLI

Point-estimate analysis:

```bash
idkmesh gate-marginal examples/gate-audit/panel-votes.example.json \
  --current reviewer-a \
  --current reviewer-b \
  --candidate reviewer-d \
  --pretty
```

Analyze every remaining verifier:

```bash
idkmesh gate-marginal examples/gate-audit/panel-votes.example.json \
  --current reviewer-a \
  --current reviewer-b
```

Add paired finite-sample resampling:

```bash
idkmesh gate-marginal examples/gate-audit/panel-votes.example.json \
  --current reviewer-a \
  --current reviewer-b \
  --candidate reviewer-d \
  --bootstrap \
  --bootstrap-replicates 2000 \
  --bootstrap-seed 0 \
  --bootstrap-confidence-level 0.95 \
  --pretty
```

Bootstrap tuning flags without `--bootstrap` are refused rather than silently
ignored.

## Output

The machine-readable report validates against:

- `schemas/marginal-evidence-report-v0.1.schema.json`

Top-level authority is always:

```json
"authority": "diagnostic_only"
```

There is no selected verifier or ranking field in v0.1.

### Current panel

`current_panel` records:

- nominal verifier count;
- measured panel error;
- mean verifier accuracy;
- mean pairwise error correlation;
- measured effective votes;
- whether the effective-vote value is censored at the comparison-table
  resolution limit.

### Candidate row

Each candidate verifier has:

| Field | Meaning |
| --- | --- |
| `standalone_accuracy` | Accuracy of this verifier over non-probe candidates. |
| `current_panel_error` | Error before adding the verifier. |
| `augmented_panel_error` | Error after adding the verifier under the same quorum. |
| `panel_error_delta` | `current_error - augmented_error`; positive means the augmented panel made fewer errors on this corpus. |
| `current_effective_votes` | Gate-audit effective-vote estimate for the current panel. |
| `augmented_effective_votes` | Same estimate after adding this verifier. |
| `delta_effective_votes` | `augmented - current` only when both estimates are resolved and uncensored. |
| `mean_error_correlation_with_current_panel` | Mean measurable phi correlation between the candidate's error vector and current-panel error vectors. |
| `pairwise_error_correlations` | Per-current-verifier values; `null` when either error vector has zero variance. |
| `transition_counts` | Candidate correctness on current misses and actual gate decisions changed to correct/wrong. |
| `probe_effect` | Separate seeded-probe breach comparison; never mixed into headline statistics. |
| `uncertainty` | Optional paired bootstrap intervals. |
| `status` / `unresolved_reasons` | Explicit resolution state. |

### Why censored values are not subtracted

Gate-audit's effective-vote comparison table currently resolves up to 199
independent votes. A value at that boundary means **at least 199**, not exactly
199.

Therefore this tool deliberately refuses to compute:

```text
augmented_effective_votes - current_effective_votes
```

when either side is censored. Subtracting two lower bounds would produce a
precise-looking number with no valid interpretation.

The report instead sets `delta_effective_votes: null` and records explicit
reason codes such as:

- `current_effective_votes_censored`;
- `augmented_effective_votes_censored`;
- `current_effective_votes_undefined`;
- `augmented_effective_votes_undefined`.

## Error correlation and zero-variance rows

Pairwise dependence uses the same phi coefficient as gate-audit.

If either verifier is always correct or always wrong on the audited non-probe
set, its binary error vector has zero variance and correlation is mathematically
undefined. The report uses `null`, never zero.

When no candidate/current pair has measurable variance, the candidate row is
marked unresolved for dependence measurement:

```text
candidate_error_correlation_unmeasurable
```

This does **not** mean the verifier is independent. It means the sample contains
no information with which to measure that dependence.

## Gate-rule transitions matter

Adding one verifier can change the numeric quorum threshold.

At the default strict-majority rule:

- 3 reviewers require 2 accepts;
- 4 reviewers require 3 accepts;
- 5 reviewers require 3 accepts.

Therefore a fourth reviewer can make a panel worse even when its standalone
accuracy looks good: a prior 2-1 accept becomes a 2-2 tie, and ties reject.

The report records actual decision changes, including:

- changed to correct;
- changed to wrong.

This is why v0.1 measures the candidate **under the real gate rule** rather than
using pairwise correlation as a standalone routing score.

## Seeded probes

Probes are never part of:

- standalone accuracy;
- panel error;
- effective votes;
- error correlation;
- bootstrap resampling.

They are reported only in `probe_effect`:

- current breached probes;
- augmented breached probes;
- breaches prevented.

A negative `breaches_prevented` means the added verifier caused more known-bad
probes to pass under the declared gate.

## Paired finite-sample bootstrap

The bootstrap is opt-in.

It resamples entire **non-probe candidate rows** with replacement. The same
sampled row indices are used for the current and augmented panels in each
replicate.

This pairing is load-bearing: independently resampling the two panels would add
Monte Carlo noise unrelated to the verifier addition and would destroy the
row-level comparison.

The report includes percentile intervals for:

- `panel_error_delta`;
- `effective_votes_delta`.

Rules:

- minimum 100 replicates;
- minimum 5 non-probe candidates for inferential output;
- deterministic PRNG seed;
- confidence level strictly in `(0, 1)`;
- effective-vote deltas omitted for replicates where either panel is
  non-discriminating or the estimate reaches the table-resolution censoring
  boundary;
- every omitted replicate is counted.

The interval is conditional on the audited candidate set being an exchangeable
sample from the population the claim is meant to cover. The tool cannot infer
that assumption from the matrix.

A narrow bootstrap interval is evidence of **resampling stability**, not proof
that the candidate corpus is representative and not proof that verifiers are
independent.

## Provenance

The report carries two SHA-256 bindings:

- `input_digest_sha256` binds the exact verdict matrix;
- `analysis_digest_sha256` binds the current-panel IDs, candidate IDs, and
  bootstrap parameters.

The report therefore changes when the analysis question changes even if the
underlying matrix is unchanged.

## Security and authority boundary

This diagnostic:

- makes no model/provider network call;
- executes no candidate code;
- materializes no secrets;
- dispatches no connector;
- writes no GitHub state;
- creates no EvaluatorPlan;
- grants no verification or merge authority;
- selects no "winner."

A later AVE/Connector Control Plane integration may consume this report only
after separate held-out evidence supports a routing policy. That integration is
outside v0.1.

## Known limitations

v0.1 deliberately does not:

- estimate causal benefit of a verifier;
- infer independence from provider/model labels;
- rank candidates;
- learn a global verifier score;
- compare review cost or latency;
- perform held-out model selection;
- mutate routing policy.

Those are separate experiments because mixing them into the first measurement
primitive would make it difficult to determine what actually produced any
observed gain.

## Test requirements

The implementation is covered for:

- duplicate/unknown/overlapping verifier IDs;
- source-order determinism;
- perfectly redundant error vectors;
- zero-variance correlation;
- helpful and harmful gate transitions;
- a verifier that worsens panel error;
- probe isolation;
- effective-vote censoring;
- fewer than five non-probe rows;
- paired deterministic bootstrap;
- bootstrap parameter rejection;
- strict JSON parsing;
- provenance binding;
- schema validation;
- CLI output and destructive-output-path refusal.

These tests are intended to make the first implementation fail closed before
any future routing integration is considered.
