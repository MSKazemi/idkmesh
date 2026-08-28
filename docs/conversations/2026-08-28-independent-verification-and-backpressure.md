# Conversation record: independent verification and backpressure

Date: 2026-08-28

## User direction

The project owner asked IDKMesh to continue by doing three concrete things in the public repository:

1. solve one important problem;
2. add one important idea;
3. add one important algorithm.

Repository: `https://github.com/MSKazemi/idkmesh`

## Repository state considered

Issue #3 (WorkUnit/ResultManifest foundational contract) had just been completed. That unblocked the next verification/orchestration layer. Issues #5 and #14 remained especially relevant:

- #5: independent validator and benchmark task set;
- #14: make verification scale with generation.

The existing protocol sequence had a gap:

```text
WorkUnit -> worker ResultManifest -> ??? -> integration decision
```

The repository explicitly treated ResultManifest as worker self-report, so using it as verifier evidence would collapse the trust boundary.

## Important problem solved: independent VerificationResult contract

PR #47 added:

- `schemas/verification-result-v0.1.schema.json`;
- `examples/results/phase0-smoke.verification-result.json`;
- `examples/results/invalid-non-independent.verification-result.json`;
- harness validation for the new protocol object.

The resulting chain is:

```text
WorkUnit
 -> worker attempt
 -> ResultManifest
 -> independent verifier
 -> VerificationResult
 -> integration/human decision
```

Cross-object validation now checks:

- exact ResultManifest/WorkUnit/attempt binding;
- evidence reference integrity;
- required WorkUnit validator coverage;
- requested-validator coverage;
- worker/verifier identity separation when independence is required;
- consistency between required checks, verification status, and `accept_candidate` recommendations.

A VerificationResult is decision support and does not authorize an automated merge.

## Important idea added: verification debt

The project now explicitly models **verification debt**: pending unverified work weighted by risk, uncertainty, impact, estimated verification cost, and lack of independent/diverse evidence.

The motivation is that queue length alone is misleading. One security-sensitive patch can create more trust burden than many trivial changes.

Research/design note:

`docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`

Decision record:

`docs/decisions/ADR-0007-verification-debt-backpressure.md`

## Important algorithm added: Risk-Weighted Verification Backpressure (RWVB)

Executable reference implementation:

`experiments/verification_backpressure.py`

RWVB has two coupled controls:

1. allocate scarce verifier capacity by risk-clearing pressure per estimated verification cost, including uncertainty, impact, evidence-diversity deficit, age, and starvation protection;
2. adjust generator fan-out using verification-debt load relative to verifier capacity.

High verification debt suppresses new candidate fan-out; safely low debt allows fan-out to expand.

The algorithm is inspired by MaxWeight/backpressure queueing/network-control methods. IDKMesh does not claim that classical throughput-optimality proofs transfer to this heuristic risk/verification transformation.

## Validation evidence

PR #47 changed eight files and triggered the `Phase 0 schema check` workflow.

The workflow completed successfully, including:

- schema and fixture validation;
- VerificationResult cross-object checks;
- RWVB deterministic self-tests;
- existing zero-cost compute routing self-test;
- safe built-in smoke experiment.

PR #47 was squash-merged to `main` as:

`bd03c6c79b4929a46549fd4e844bc84f0cdcf5d1`

## Issue updates

- Issue #5 received a progress record: the independent verification protocol prerequisite is now implemented, while the hidden evaluator and 20–50 task benchmark remain open.
- Issue #14 received the RWVB baseline and next comparison plan: FIFO vs highest-risk-first vs cheapest-first vs RWVB under seeded defects and increasing generation fan-out.

## Recommended next implementation

The next high-leverage work remains #4/#5 integration:

```text
bounded WorkUnit
 -> 2+ isolated worker adapters
 -> ResultManifests
 -> independent validator execution
 -> VerificationResults
 -> Evidence Report
 -> human integration decision
```

The immediate useful slice is to implement a deterministic local validator runner that consumes ResultManifest + WorkUnit, runs bounded checks in an isolated candidate workspace, and emits the new VerificationResult contract.
