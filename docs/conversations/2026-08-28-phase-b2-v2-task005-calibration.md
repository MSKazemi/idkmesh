# Continuation: first Phase B2 successor per-task calibration — 2026-08-28

## User direction

Continue improving `https://github.com/MSKazemi/idkmesh` and keep substantive project work in the public repository.

## Convergence before new work

The active benchmark-definition branches were refreshed first.

PR #186 had become the scientifically stronger successor process: five tasks fixed before outcomes, `stage=scaffold`, no stored definition digest, zero outcomes, and mandatory per-task evaluator calibration before any freeze.

Its cohort index initially violated Benchmark Cohort v0.1 schema details, so only the index/workflow layer was repaired:

- required title added;
- `taxonomy_frozen_before_outcomes=true` retained as the schema requires;
- stage remained `scaffold`;
- no `definition_digest` was added;
- provisional evaluator calibration remained pending;
- schema-invalid family/category labels were mapped to existing cohort enums without changing task objectives;
- task-level calibration metadata was moved into the allowed top-level extension.

Exact repaired head `391b2905ff55885def2a4930281d148682d012a6` passed:

- Phase B2 successor v2 scaffold `33195886824`;
- IDKMesh Evolution Loop `33195886904`;
- idkgraph-observatory `33195887216`.

PR #186 was merged as:

`1986b8cace7ab3ccfa4f8df1902f9805bc962a42`

Our competing #185 freeze was then closed as premature. Its useful source-precondition invariant was retained for later calibration/freeze, but its proposed digest is design provenance only and not a canonical benchmark commitment.

Issue #180 was updated so the only legitimate path to freeze is now:

```text
scaffold
 -> per-task straightforward calibration
 -> per-task inert/Goodhart near-miss
 -> behavioral evidence where practical
 -> all five green
 -> freeze + definition digest
 -> scored candidate outcomes
```

The E015 CI-coverage PR #184 had already merged concurrently, so no duplicate work was created there.

## First calibration selected

Task 005 was selected first because it is safety-relevant and behaviorally testable without external services:

`benchmark/phase-b2-v2/005-local-offer-output-boundary`

Frozen source:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

Target:

`experiments/local_compute_offer.py`

The tool claims discovery-only/no-canonical-write authority, but the frozen implementation accepts arbitrary `--output` paths through:

```python
output = Path(args.output)
```

The provisional EvaluatorPlan v0.4 requires:

```text
added:   results/
removed: output = Path(args.output)
```

## Calibration design

### Straightforward transition

A repository/results-bounded path resolver replaces the direct assignment. It rejects:

- absolute paths;
- `..` traversal;
- non-`results/` repository paths;
- a `results/` root that resolves outside the repository;
- a requested path that resolves outside the results root.

Existing stdout behavior and existing write code are otherwise retained.

### Inert near-miss

The decoy only appends a harmless comment/string containing `results/` and leaves the vulnerable `output = Path(args.output)` line untouched.

This deliberately proves that the added lexical signal alone is insufficient. Canonical v0.4 must reject the decoy because the required removal is absent.

## Separate behavioral evidence

The metadata-only verifier never executes candidate code.

A separate evaluator-owned behavior matrix runs each calibration transform in the disposable frozen-source checkout:

1. no `--output` -> valid JSON on stdout;
2. output under `results/` -> valid file created;
3. `README.md` -> straightforward must reject without modification; decoy remains vulnerable;
4. absolute path -> straightforward must reject/no file; decoy remains vulnerable;
5. traversal -> straightforward must reject/no outside file; decoy remains vulnerable.

Each case resets the source checkout and reapplies the candidate transform so one unsafe decoy write cannot contaminate another observation.

## Authority boundary

Calibration objects are not scored benchmark outcomes.

The workflow has `contents: read`, no persisted checkout credentials, no secrets, no project-paid compute, no canonical write/push/approval/merge authority, and no automatic candidate selection.

A successful Task 005 calibration would retire only **one of five** #180 calibration gates. The successor cohort must remain unfrozen until all five are calibrated.
