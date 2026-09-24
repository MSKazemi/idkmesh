# Gate Audit v0.1

**Status:** experimental contract, versioned. The meaning of v0.1 will not change
silently; behavior changes get a new version.

`idkmesh gate-audit` is the first installable product surface cut from the
repository's verification research. It answers one question about a review
gate: **how much independent evidence does this panel of verifiers actually
produce?**

A gate that reports "N verifiers approved" implies N independent pieces of
evidence. The repository's retained experiments show that implication fails in
practice and fails in the dangerous direction:

- [E017](../../experiments/E017-item-difficulty-and-quorum.md) measured a real
  25-verifier panel (mean accuracy 0.7956, mean pairwise error correlation
  +0.5873) whose majority vote had the error rate of roughly **one** verifier.
- [E015](../../experiments/E015-verification-phase-diagram.md) falsified the standard
  `N / (1 + (N-1)ρ)` effective-size heuristic: it converges to `1/ρ` regardless
  of verifier accuracy, so it overstates exactly the accurate-verifier panels a
  serious gate would deploy.
- [E016](../../experiments/E016-live-verifier-correlation.md) showed that a
  panel of non-discriminating verifiers produces confident-looking votes whose
  correlation statistics are uninterpretable — so an audit must screen
  discrimination before reporting anything else.

The audit packages those results as a diagnostic. It consumes a **verdict
matrix** and emits a **gate-audit report**. It never runs a gate, never selects
candidates, and never grants acceptance: worker success ≠ acceptance,
verification recommendation ≠ merge authority.

## Input contract: the verdict matrix

A single JSON object supplied by the caller. Collecting verdicts is the
caller's responsibility; the audit deliberately has no opinion about where they
came from (human reviewers, LLM judges, test oracles, CI checks).

```json
{
  "gate_id": "my-repo-pr-gate",
  "evidence_class": "synthetic",
  "quorum": 0.5,
  "candidates": [
    {"id": "c01", "ground_truth": "accept"},
    {"id": "p01", "ground_truth": "reject", "probe": true, "probe_kind": "seeded-defect"}
  ],
  "verifiers": [
    {"id": "reviewer-a", "verdicts": {"c01": "accept", "p01": "accept"}}
  ]
}
```

The document is read as UTF-8. A leading byte-order mark is tolerated, because
Windows editors and PowerShell redirection add one; any other encoding
(UTF-16 included) is refused. Only standard JSON is accepted, because
`provenance.input_digest_sha256` promises a canonicalization another
implementation can recompute: Python's `NaN`, `Infinity` and `-Infinity`
extensions are refused, and so are duplicate keys within one object, on which
implementations disagree (last wins, first wins, or a hard error). A repeated
candidate id inside a `verdicts` object is the case that matters — kept
silently, it rewrites the verifier accuracy the audit is there to measure.

Rules, enforced in code (`idkmesh/gate_audit.py`, `validate_input` — every rule
below, so the function is usable as a pre-flight check):

- `evidence_class` is **mandatory** and must be `synthetic` or `observed`. The
  report copies it verbatim; a report can never upgrade fixture data into an
  observed claim. This is the repository's synthetic-vs-observed boundary
  applied to the product.
- Every candidate carries a `ground_truth` label (`accept`/`reject`). The audit
  measures a panel against known answers; without ground truth there is nothing
  to audit.
- The matrix must be **complete**: every verifier must have a verdict for every
  candidate. A missing verdict is refused, not imputed — every imputation rule
  silently changes the correlation structure the audit exists to measure.
- Probes (`"probe": true`) are **seeded known-bad candidates** and must carry
  `ground_truth: "reject"`. An optional `probe_kind` (for example
  `prompt-injection`, `seeded-defect`) buckets the breach report. `probe_kind`
  without `"probe": true` is refused rather than ignored: as an ordinary
  candidate it would join the headline statistics and leave the breach report
  absent, which reads as "no probes breached".
- At least two non-probe candidates and one verifier are required. Panel
  statistics from fewer are not meaningful.
- `quorum` (default `0.5`) sets the acceptance rule: the panel accepts when
  `accept_votes > quorum × verifiers`. At the default this is strict majority;
  ties reject. It must be a real number in `[0, 1)`; a JSON boolean is refused
  even though `false` would otherwise pass as `0.0`, a rule under which one
  accept vote carries the panel.

Refusals name the offending key and, where an `id` is absent, the candidate's
or verifier's position in the list.

## What is computed

Headline statistics use **only non-probe candidates**, so the probe set cannot
inflate or deflate the accuracy/correlation it is supposed to stress-test.

| Report field | Meaning |
|---|---|
| `verifiers[].accuracy` | Per-verifier accuracy against ground truth. Verifiers at or below 0.5 are flagged: their votes add no evidence (the E016 screen). |
| `panel.mean_pairwise_error_correlation` | Mean pairwise φ (phi coefficient) of verifier error vectors. Pairs where a verifier made zero or all errors are skipped and counted in `skipped_correlation_pairs`. |
| `panel.error`, `panel.false_accept_rate`, `panel.false_reject_rate` | Measured panel performance under the quorum rule. |
| `panel.effective_votes` | The smallest **independent** panel size that reproduces the measured panel error at the measured mean accuracy — the number the gate's "N approvals" claim should be compared against. `null` when the panel does not discriminate. Reported raw: this is a property of the measured error rate, not of the head-count, so it may exceed `panel.nominal_votes` (see below). |
| `panel.effective_votes_ceiling` | The largest effective size *any* panel at this accuracy/correlation can reach. Under shared-shock dependence, panel error floors at `ρ(1−acc)` however many verifiers are added; if the ceiling is below your target, adding reviewers is wasted spend and the only moves are raising accuracy or lowering correlation. The string `"unbounded"` when measured correlation is at or below zero, and `null` when the panel does not discriminate (mean accuracy ≤ 0.5) or correlation was unmeasurable — the same undefined case as `effective_votes`. |
| `panel.heuristic_n_eff` | The classic `N/(1+(N-1)ρ)` value, reported **only for contrast** with a warning when it exceeds the ceiling. |
| `probes` | Breach accounting: how many seeded known-bad candidates the panel accepted, in total and per `probe_kind`. |

### Resolution limits: censoring, not a cap

`effective_votes` is obtained by comparing measured panel error against a table
of independent panel sizes up to **199**. A measured error at or below what 199
independent verifiers achieve is therefore **censored**: the comparison has run
out of resolution and the value is a *lower bound*, not a resolved measurement.
An accurate, genuinely uncorrelated panel that made no errors on the audited set
reaches this quickly — it is the regime the research is trying to get gates
into, not a pathological input.

Two consequences, and neither is repaired by changing the number:

- **A value at the table maximum means "at least 199".** It is reported raw in
  the JSON, the condition is named in `warnings`, and the Markdown summary
  renders it as a bound — `**50 verifiers ≈ ≥199 effective independent votes on
  this candidate set.**` — so a censored result does not read as a precise one.
- **The value may exceed `nominal_votes`, and that is not an error.** The
  estimand is the independent-panel size whose *expected* error matches the
  error actually measured; on a finite candidate set a panel can outperform the
  expectation for an equal-size independent panel, so an equivalent size above
  the head-count is possible. Clamping it to `nominal_votes` would substitute a
  different statistic for a published v0.1 field, and would turn a censored
  bound into an apparently exact `50.00`. A capped display quantity, if one is
  ever wanted, belongs in a deliberately named and versioned field rather than
  in this one.

`effective_votes_ceiling` saturates at the same table edge for a small positive
correlation. It too is uncapped, and for a further reason: it describes what any
panel in this accuracy/correlation regime could reach, which is a property of
the regime and not of the audited head-count.

The mathematical definitions are identical to the research record:
`effective_n`, `effective_n_ceiling` and `heuristic_effective_n` follow
`sim/e015_analyze.py`; `phi` follows `sim/e016_analyze.py`.
`tests/test_gate_audit.py` asserts numerical parity with those modules so the
packaged copies cannot drift from the published results.

## Finite-sample uncertainty (opt-in, `gate-audit-report-v0.2`)

**Status:** additive and opt-in. Nothing above this section changes: the
default report stays byte-identical `gate-audit-report-v0.1`, and this
section only activates with `--bootstrap`.

The panel statistics above are point estimates from one fixed candidate
sample. A small or unrepresentative sample can make them unstable even though
each number prints to four decimal places. `--bootstrap` adds a deterministic
finite-sample uncertainty interval for `panel.error`,
`panel.mean_verifier_accuracy`, `panel.mean_pairwise_error_correlation` and
`panel.effective_votes` — the concrete scope of
[issue #520](https://github.com/MSKazemi/idkmesh/issues/520) — and switches
the emitted `schema` to `gate-audit-report-v0.2`, validated against
[`schemas/gate-audit-report-v0.2.schema.json`](../../schemas/gate-audit-report-v0.2.schema.json).
A committed example pair regenerated by the test suite lives at
[`examples/gate-audit/gate-audit-report-v0.2.example.json`](../../examples/gate-audit/gate-audit-report-v0.2.example.json).

**Method: candidate-level nonparametric bootstrap.** Each replicate resamples
whole *non-probe candidate rows* with replacement — never individual verifier
cells — so every replicate keeps the real cross-verifier dependence structure
for whichever candidates it happened to draw. Resampling cells independently
would destroy exactly the dependence the audit exists to measure and
manufacture a false independence result. Intervals are percentile intervals
using linear interpolation between order statistics (NumPy's `"linear"`
method, R's type 7). Probes are never part of the resampled population, the
same boundary the headline statistics already observe.

A fixed seed reproduces the identical interval on a fixed Python
interpreter. Across interpreter versions the correlation interval's bound can
differ in the last representable bit, because it is computed through `phi()`
(unchanged v0.1 code, thousands of calls per audit), whose float summation
inherits whatever `sum()` does on that interpreter — and `sum()`'s algorithm
for floats changed in Python 3.12 (compensated summation replaced naive
addition). This module's own averaging uses `math.fsum`, which has been
stable across versions, so the effect is small and confined to
`mean_pairwise_error_correlation`; it is not a claim that resampling itself
is version-dependent.

**What the interval is conditional on.** It describes resampling stability of
the *observed* candidate set only. It is a valid inferential interval solely
under the assumption that the audited candidates are exchangeable draws from
the population the report's claim is about; a set curated by difficulty,
topic, recency, or any other selection rule does not satisfy that, and the
matrix alone cannot tell the tool whether it does. A narrow interval is
evidence that the panel numbers are stable under resampling — **never**
evidence that the verifiers are independent, and never evidence that the
candidate set is representative of anything beyond itself.

**Failure modes, defined rather than left to numeric accident:**

| Condition | Behavior |
|---|---|
| Fewer than 5 non-probe candidates | Bootstrap skipped outright: `sufficient_for_inference: false`, every metric section `null`. Too few distinct resamples exist for a percentile interval to mean anything. |
| A replicate's mean verifier accuracy does not exceed chance | That replicate's `effective_votes` contribution is undefined — excluded from the interval, counted in `replicates_undefined`, never coerced to a number. |
| No verifier pair has variance in both error vectors in a replicate | Same treatment for that replicate's correlation contribution. |
| Every replicate is undefined for a metric | That metric's interval is `null` and a warning names it — never silently omitted. |
| A replicate's `effective_votes` reaches the table-resolution ceiling `is_saturated` already defines for the point estimate | If the interval's upper bound lands there, `effective_votes.ci_high_censored` is `true`: a resolution limit, not a resolved bound. This can happen even when the point estimate itself is not saturated — a real property of the upper tail on a small candidate set, not a bug. |

`uncertainty.method`, `.sampling_unit`, `.confidence_level`, `.replicates`
and `.seed` record exactly what was run. Each of `panel_error`,
`mean_verifier_accuracy`, `mean_pairwise_error_correlation` and
`effective_votes` carries `point` (mirrored from `panel`), `ci_low`,
`ci_high`, `replicates_used` and `replicates_undefined`;
`effective_votes` additionally carries `ci_high_censored`.
`provenance.input_digest_sha256` is unaffected: it binds the verdict-matrix
input, not the bootstrap parameters run against it.

```bash
idkmesh gate-audit examples/gate-audit/panel-votes.example.json \
  --bootstrap --bootstrap-replicates 2000 --bootstrap-seed 0 \
  --bootstrap-confidence-level 0.95 --pretty
```

`--bootstrap-replicates` (default 2000, minimum 100 — fewer cannot resolve a
percentile interval), `--bootstrap-seed` (default 0) and
`--bootstrap-confidence-level` (default 0.95) all require `--bootstrap`;
passing any of them without it is refused rather than silently ignored, the
same fail-closed rule the rest of the CLI follows. Runtime is
`O(replicates × candidates × verifiers²)`, dominated by the pairwise
correlation term; reduce `--bootstrap-replicates` for very large panels.

Not yet done, deliberately: the composite GitHub Action
(`actions/gate-audit/action.yml`) does not expose `--bootstrap` as an input.
The CLI supports it today; wiring the action is separate follow-on scope, not
bundled into a change whose point was the statistics.

## Output contract

The JSON report validates against
[`schemas/gate-audit-report-v0.1.schema.json`](../../schemas/gate-audit-report-v0.1.schema.json).
A committed example pair lives in
[`examples/gate-audit/`](../../examples/gate-audit/): the report example is
regenerated from the input example by the test suite, so the two cannot drift
apart.

`provenance.input_digest_sha256` binds every report to the exact canonicalized
input it was computed from. The report contains no timestamp by design: the
same input must produce byte-identical output. A byte-order mark on the input
does not change the digest.

The report is always standard JSON: a non-finite number is a serialization
failure, never a bare `NaN` token that only Python can read back.

`--markdown` additionally renders a human summary whose headline is the number
the audit exists to surface:

> **5 verifiers ≈ 1.69 effective independent votes.**

## Usage

From an installed package:

```bash
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

From the repository without installing:

```bash
PYTHONPATH=. python -m idkmesh.cli gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

`--out` and `--markdown` must name different paths, and neither may name the
input file; both are refused before the audit runs rather than silently
overwriting evidence.

Exit codes: `0` success, `2` anything else — a contract violation, an input
that cannot be read or decoded, an output that cannot be written, or a usage
error from the argument parser. The reason is always named on stderr, on one
line, without a traceback. On success the command writes nothing to stderr,
and nothing to stdout either when `--out` is given.

### As a GitHub Action

The composite action at [`actions/gate-audit/`](../../actions/gate-audit/action.yml)
wraps the CLI for CI use: it installs the package from the action's own
repository checkout, runs the audit, and appends the Markdown summary to the
job summary page.

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

Inputs: `votes-file` (required), `report-file`, `markdown-file`, `job-summary`,
`python-version` (defaults `gate-audit-report.json`, `gate-audit-report.md`,
`true`, `3.12`). The workflow
[`gate-audit-action-selftest.yml`](../../.github/workflows/gate-audit-action-selftest.yml)
runs the action on the committed example on every relevant change and asserts
the output is byte-identical to the committed report example.

## Authority boundary

The report is decision support about the **review layer itself**. It does not
accept or reject any candidate, does not gate any merge, and its warnings are
observations, not policy. Whether a measured breach rate or effective-vote
count is acceptable is a human/governance decision outside this tool.

## Non-goals for v0.1

- Collecting verdicts (running reviewers, calling models, driving CI). The
  audit stays a pure function of the supplied matrix.
- Estimating effective votes without ground truth.
- Signing/attesting reports. Binding a report to a signed provenance chain is
  planned to reuse existing attestation standards rather than invent one.
- Prescribing panel composition. The report says what a panel is worth, not
  what to buy.
- Failing a build on a threshold. There is deliberately no `--max-breach-rate`
  or `--min-effective-votes`: whether a measured number is acceptable is the
  governance decision named under **Authority boundary**, and an exit code
  would move it into the tool.
- Reading the verdict matrix from stdin. The audit takes a path so the report
  can name the file it rejected.

## Related: per-pair dependence evidence

`gate-audit-report-v0.1` reports only the panel's *mean* pairwise error
correlation, on purpose: a future adaptive verifier-allocation revision must
not reconstruct or invent each pair's own dependence from that mean, or from
provider/model/family identity. `idkmesh gate-audit-dependence` (issue #654)
reads the same verdict-matrix input and emits a separate, optional
`gate-audit-dependence-v0.1` report with every verifier pair's own measured
phi error-correlation, bound to the identical `provenance.input_digest_sha256`
so the two reports are provably about the same audited panel. It is
diagnostic only — see
[`idkmesh/gate_audit_dependence.py`](../../idkmesh/gate_audit_dependence.py)
and [`schemas/gate-audit-dependence-v0.1.schema.json`](../../schemas/gate-audit-dependence-v0.1.schema.json).
