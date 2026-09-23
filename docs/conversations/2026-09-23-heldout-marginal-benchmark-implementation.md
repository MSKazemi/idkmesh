# Conversation record — Held-out marginal evidence benchmark implementation

**Date:** 2026-09-23  
**Scope:** continuation of issue #693 after the first `gate-marginal` measurement primitive merged via PR #734.

## Project-owner requirement

The project owner asked to continue implementation and reiterated that the code
must be solid, strong, well done, and enterprise-level.

The next acceptance gap in #693 was selected:

- compare marginal evidence selection with four simpler baselines;
- keep selection/statistic design separate from held-out evaluation;
- fail closed when finite-sample evidence cannot support a stable ordering;
- preserve diagnostic-only authority.

## Repository state

The first marginal-evidence implementation had already merged into `main`
through PR #734.

Related AVE research remains in:

- issue #621;
- PR #622.

This continuation does not merge or copy AVE controller logic into the benchmark.

## Design decision

A new diagnostic command is being implemented:

`idkmesh gate-marginal-benchmark`

It consumes a versioned benchmark config that references two strict verdict
matrices:

1. design split;
2. disjoint holdout split.

The design/holdout row identities must not overlap.

## Preregistered selectors

Exactly five design-only selectors are frozen in v0.1:

1. marginal effective-vote contribution;
2. deterministic random eligible addition;
3. highest standalone accuracy;
4. different-family-first;
5. minimum mean pairwise error correlation.

The holdout matrix is not accepted by the selection-plan function.

## Marginal-selector stability gate

The marginal strategy is resolved only if:

- every candidate has measured, uncensored effective-vote delta;
- every candidate has sufficient bootstrap uncertainty;
- the top point estimate is unique;
- the top interval lower bound is strictly above every alternative interval
  upper bound.

Otherwise it reports `unresolved`.

There is no fallback to another metric.

## Deterministic random baseline

The random baseline is derived from SHA-256 over the configured seed and
canonical candidate order rather than Python PRNG state, reducing
cross-interpreter reproducibility risk.

## Family and correlation baselines

The family selector treats family labels only as structural metadata, not proof
of independence.

The correlation selector fails closed if any candidate correlation is
unmeasurable, because an unknown candidate could be the true minimum.

## Machine contracts

Added:

- `schemas/marginal-evidence-benchmark-config-v0.1.schema.json`;
- `schemas/marginal-evidence-benchmark-report-v0.1.schema.json`;
- `docs/specifications/MARGINAL_EVIDENCE_BENCHMARK_V0_1.md`.

The report contains no winner or production routing recommendation.

## Implementation artifacts

Primary code:

- `idkmesh/marginal_evidence_benchmark.py`;
- `idkmesh/cli.py`.

Tests:

- `tests/test_marginal_evidence_benchmark.py`;
- `tests/test_example_contract_coverage.py`.

Synthetic fixtures:

- `examples/gate-audit/marginal-benchmark-design.example.json`;
- `examples/gate-audit/marginal-benchmark-holdout.example.json`;
- `examples/gate-audit/marginal-evidence-benchmark-config.example.json`.

The fixtures test infrastructure and contract behavior only. They are not
scientific evidence that any selector is superior.

## Test focus

The new tests cover:

- strict config structure;
- exact family-map coverage;
- current/candidate overlap rejection;
- duplicate JSON key rejection;
- matrix path escape rejection;
- design/holdout row overlap rejection;
- matching gate/quorum requirements;
- holdout-verdict mutation cannot change the frozen selection plan;
- marginal interval-separation behavior;
- no marginal fallback from unresolved candidates;
- correlation fail-closed behavior;
- deterministic random baseline;
- family-first tie semantics;
- five-strategy end-to-end report shape;
- small-sample marginal unresolved state;
- selection-plan provenance binding;
- relative matrix loading;
- CLI report output;
- refusal to overwrite benchmark evidence;
- JSON Schema validation.

## Product documentation

`docs/product/INNOVATION_MOAT_2026-09-23.md` is advanced from the first
measurement slice to the explicit progression:

```text
measure marginal contribution
        |
compare against simple baselines
        |
require held-out stability
        |
only then consider AVE / Connector Control Plane dry-run integration
```

## Authority boundary

The benchmark:

- makes no live model/provider call;
- executes no candidate code;
- dispatches no work;
- creates no EvaluatorPlan;
- modifies no routing state;
- accepts no candidate;
- grants no merge authority.

## Remaining work after this slice

After the implementation passes protected CI, issue #693 still needs a broader
preregistered observed/held-out corpus and synthesis before any dry-run routing
integration should be proposed.

A single synthetic fixture is not a promotion gate.
