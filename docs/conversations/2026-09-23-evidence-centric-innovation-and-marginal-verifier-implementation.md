# Conversation record — Evidence-centric innovation and marginal verifier implementation

**Date:** 2026-09-23  
**Scope:** competitor differentiation, innovation selection, and the first enterprise-grade implementation slice for evidence-centric verifier routing.

## 1. Project-owner requirements

The project owner asked IDKMesh to identify innovative features that are not merely copies of competitor capabilities, then asked to continue with implementation and explicitly required the result to be:

> "enterprise-level code ... very solid, strong and well done"

The implementation work therefore prioritized bounded contracts, fail-closed behavior, reproducibility, tests, provenance, compatibility, and authority separation over adding broad autonomous behavior quickly.

## 2. Competitive finding

A current ecosystem review showed that several ideas are no longer sufficient as standalone differentiation:

- multi-agent orchestration;
- subagents;
- model/provider routing;
- MCP/tool integration;
- evaluation hooks;
- human-in-the-loop;
- independent/critic verifier agents;
- tracing and observability.

The resulting product thesis was narrowed to:

> **Other platforms orchestrate agents. IDKMesh should orchestrate evidence.**

The strongest candidate capability is an **Adaptive Evidence Portfolio**: choose an additional verifier based on the marginal evidence it contributes to the panel already selected, rather than on nominal reviewer count, standalone accuracy, or provider-family labels alone.

## 3. Alignment with existing IDKMesh research

The repository already had in-flight **Adaptive Verification Ecology (AVE)** work:

- issue #621;
- PR #622.

AVE already covers several adjacent mechanisms:

- verifier-family diversification;
- correlation penalties;
- known-bad/immune-style probes;
- risk-adaptive verifier floors and quorum;
- posterior/Thompson-style routing;
- entropy exploration;
- verification-capacity backpressure.

The new work was deliberately scoped **under** that architecture rather than creating a competing controller.

## 4. Product/research planning artifacts

The innovation program was recorded in:

- `docs/product/INNOVATION_MOAT_2026-09-23.md`;
- issue #693 — **P0 research/product: measure marginal evidence contribution before adding a verifier**;
- PR #694 — product/research positioning and innovation documentation.

The first executable question from #693 is:

> Given one historical ground-truthed verdict matrix, an already-selected verifier panel, one candidate verifier, and the exact gate/quorum rule, what changed when that verifier was added?

The intended quantity is explicitly contextual:

> **marginal panel evidence contribution under gate G on corpus C**

It is not named or treated as an intrinsic verifier "independence score."

## 5. Implementation artifact

Implementation PR:

- **#734 — `feat: measure marginal verifier evidence contribution`**

Primary files:

- `idkmesh/marginal_evidence.py`;
- `idkmesh/cli.py`;
- `idkmesh/gate_audit.py`;
- `schemas/marginal-evidence-report-v0.1.schema.json`;
- `docs/specifications/MARGINAL_EVIDENCE_V0_1.md`;
- `examples/gate-audit/marginal-evidence-report.example.json`;
- `tests/test_marginal_evidence.py`.

The CLI surface is:

```bash
idkmesh gate-marginal panel-votes.json \
  --current reviewer-a \
  --current reviewer-b \
  --candidate reviewer-d \
  --bootstrap \
  --pretty
```

## 6. Enterprise-level implementation properties

### Strict shared input boundary

`gate-marginal` reuses the same verdict-matrix parser as `gate-audit`.

The shared parser:

- rejects duplicate JSON keys;
- rejects non-standard JSON constants;
- validates matrix completeness;
- retains UTF-8/BOM behavior;
- preserves source-qualified error messages.

The refactor was hardened so existing gate-audit bootstrap errors continue to include the input source/path.

### Explicit authority boundary

Every marginal-evidence report carries:

```json
"authority": "diagnostic_only"
```

The implementation does not:

- rank candidates;
- select a verifier;
- dispatch work;
- construct or approve an EvaluatorPlan;
- accept a candidate;
- write canonical repository state;
- merge a pull request.

### Gate-rule-specific measurement

For every candidate verifier, the report separates:

- standalone accuracy;
- current-panel error;
- augmented-panel error;
- panel-error delta;
- current and augmented effective-vote estimates;
- effective-vote delta when mathematically resolvable;
- pairwise error correlations;
- candidate correctness on rows the current panel missed;
- candidate errors on rows the current panel got right;
- actual gate decisions changed to correct;
- actual gate decisions changed to wrong.

This matters because adding one reviewer can change a quorum threshold. A reviewer with good standalone accuracy can still make a specific gate worse.

### Fail-closed unresolved states

The report uses explicit `status` and `unresolved_reasons`.

Examples include:

- insufficient non-probe observations;
- unmeasurable zero-variance error correlation;
- undefined effective votes;
- censored effective-vote estimates.

Censored lower bounds are never subtracted to manufacture a precise delta.

### Probe isolation

Seeded known-bad probes are excluded from:

- ordinary accuracy;
- panel error;
- correlation;
- effective votes;
- bootstrap resampling.

Their breach behavior is reported separately.

### Paired deterministic uncertainty

The optional bootstrap:

- resamples whole candidate rows;
- preserves cross-verifier dependence within a row;
- uses the same sampled row indices for current and augmented panels;
- uses the same seeded row sequence across all candidate verifiers in one analysis;
- counts undefined/censored replicates instead of silently coercing them;
- requires at least five non-probe candidates for inferential output.

### Provenance

Reports bind:

- the exact input matrix by SHA-256;
- the exact analysis question (current panel, candidate set, bootstrap configuration) by a second SHA-256 digest.

Panel/candidate IDs are canonicalized to source-matrix order so semantically identical CLI argument orderings produce the same provenance digest.

### Machine-contract invariants

The JSON Schema rejects contradictory report states, including:

- `status: measured` with unresolved reasons;
- `status: unresolved` without a reason;
- numeric effective-vote deltas when either endpoint is censored or undefined;
- inferential interval data when the report says the sample is insufficient.

### Reproducible fixture

A committed example report is regenerated exactly in tests from the existing gate-audit example matrix. The global example-contract coverage test maps the fixture to its schema.

## 7. Integration discipline

During implementation, `main` advanced with Product Spine, CandidateReference, SEO/topic, and discovery work.

The feature branch was brought onto current `main` using a real two-parent Git commit:

- feature head as first parent;
- current `main` as second parent;
- current-main tree as the base;
- only PR-owned blobs overlaid.

This preserved Git ancestry, avoided copying unrelated changes into the PR diff, and allowed exact-head CI to run against the actual current repository tree.

## 8. Test and CI policy

The PR is required to pass the repository's protected checks, including:

- Python 3.11 gate;
- Python 3.13 gate;
- deterministic Markdown link integrity;
- Phase 0 schema check;
- Gate Audit Action self-test;
- CodeQL;
- repository observability checks.

The feature is not promoted into live AVE/Connector Control Plane routing merely because its unit tests pass.

## 9. Remaining evidence gates

Deliberately not included in the first implementation slice:

- automatic verifier ranking or selection;
- routing-policy promotion;
- matched comparison against all simple selection baselines;
- held-out validation of a selection rule;
- automatic AVE/Connector Control Plane actuation;
- merge/integration authority.

Those remain follow-up work under #693 after the measurement primitive itself is reviewed and validated.

## 10. Community impact

The implementation is intended to make a difficult research idea approachable through:

- one CLI command;
- a strict versioned schema;
- a copyable example;
- explicit terminology;
- fail-closed diagnostics;
- a bounded issue and PR;
- no requirement to understand the full AVE research program before testing or contributing to this slice.

This supports incremental external review and makes it possible for contributors to challenge the statistic, fixtures, bootstrap assumptions, or gate semantics independently.
