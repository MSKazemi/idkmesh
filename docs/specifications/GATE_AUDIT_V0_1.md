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

Rules, enforced in code (`idkmesh/gate_audit.py`, `validate_input`):

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
  `prompt-injection`, `seeded-defect`) buckets the breach report.
- At least two non-probe candidates and one verifier are required. Panel
  statistics from less are not meaningful.
- `quorum` (default `0.5`) sets the acceptance rule: the panel accepts when
  `accept_votes > quorum × verifiers`. At the default this is strict majority;
  ties reject.

## What is computed

Headline statistics use **only non-probe candidates**, so the probe set cannot
inflate or deflate the accuracy/correlation it is supposed to stress-test.

| Report field | Meaning |
|---|---|
| `verifiers[].accuracy` | Per-verifier accuracy against ground truth. Verifiers at or below 0.5 are flagged: their votes add no evidence (the E016 screen). |
| `panel.mean_pairwise_error_correlation` | Mean pairwise φ (phi coefficient) of verifier error vectors. Pairs where a verifier made zero or all errors are skipped and counted in `skipped_correlation_pairs`. |
| `panel.error`, `panel.false_accept_rate`, `panel.false_reject_rate` | Measured panel performance under the quorum rule. |
| `panel.effective_votes` | The smallest **independent** panel size that reproduces the measured panel error at the measured mean accuracy — the number the gate's "N approvals" claim should be compared against. `null` when the panel does not discriminate. |
| `panel.effective_votes_ceiling` | The largest effective size *any* panel at this accuracy/correlation can reach. Under shared-shock dependence, panel error floors at `ρ(1−acc)` however many verifiers are added; if the ceiling is below your target, adding reviewers is wasted spend and the only moves are raising accuracy or lowering correlation. |
| `panel.heuristic_n_eff` | The classic `N/(1+(N-1)ρ)` value, reported **only for contrast** with a warning when it exceeds the ceiling. |
| `probes` | Breach accounting: how many seeded known-bad candidates the panel accepted, in total and per `probe_kind`. |

The mathematical definitions are identical to the research record:
`effective_n`, `effective_n_ceiling` and `heuristic_effective_n` follow
`sim/e015_analyze.py`; `phi` follows `sim/e016_analyze.py`.
`tests/test_gate_audit.py` asserts numerical parity with those modules so the
packaged copies cannot drift from the published results.

## Output contract

The JSON report validates against
[`schemas/gate-audit-report-v0.1.schema.json`](../../schemas/gate-audit-report-v0.1.schema.json).
A committed example pair lives in
[`examples/gate-audit/`](../../examples/gate-audit/): the report example is
regenerated from the input example by the test suite, so the two cannot drift
apart.

`provenance.input_digest_sha256` binds every report to the exact canonicalized
input it was computed from. The report contains no timestamp by design: the
same input must produce byte-identical output.

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

Exit codes: `0` success, `2` contract violation or unreadable input (with the
violation named on stderr).

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
