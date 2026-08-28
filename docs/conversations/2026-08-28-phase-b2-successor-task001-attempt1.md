# Project Turn: Phase B2 successor Task 001 first bounded attempt

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

Continue maintaining IDKMesh directly in the public repository.

## Preconditions completed before this attempt

The fresh successor cohort was merged by PR #182 as:

`d331d635718bef5561ba815e76675b434e7c2bea`

Frozen cohort:

`benchmark/phase-b2-successor-five`

Frozen definition digest:

`sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`

Every successor task still had `evidence.status = pending` at merge. No outcome was used to tune the definition.

## Scope of this execution

Only successor Task 001 was executed:

`benchmark/phase-b2-successor/001-negative-evidence-type-boundary`

Frozen source:

`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`

Frozen WorkUnit digest:

`sha256:04258ad63d36368ae6780b351f5e3729fe5f7a12de66aee16d1bc475a8b69096`

Frozen EvaluatorPlan v0.4 digest:

`sha256:1abee7b4886e8c4626af8714cfad72c04cac6e93a42920af8dddf598a2236ddc`

Structural signature:

`single-worker-baseline-v1`

## Seeded bug

On the frozen source, `_validate_negative_case()` first checks the JSON digest and only applies semantic VerificationResult validation when `evidence_type == verification_result`.

Therefore a seeded negative declaring canonical category `security` could use `evidence_type = other` and a digest-valid but semantically unrelated JSON object, and validation accepted it.

The attempt harness proved this baseline behavior before modifying the isolated source.

## Candidate transform

The bounded deterministic baseline edited only:

`tools/benchmark_cohort.py`

The candidate changed the trust boundary to:

1. require `evidence_type == verification_result` whenever `expected_category` is one of the canonical finding categories;
2. return early for non-VerificationResult evidence only after that category-aware gate;
3. preserve canonical VerificationResult schema/recommendation/category validation.

## Independent evidence channels

### Frozen metadata-only evaluator

The canonical EvaluatorPlan v0.4 checked the committed transition:

- add category-aware canonical-negative validation;
- add the VerificationResult requirement;
- remove the old evidence-type-only `if` gate.

The verifier remained metadata-only and did not execute candidate code.

### Behavioral seeded negative

The harness independently created the same schema-valid cohort negative before and after the candidate using:

- `expected_category = security`;
- `evidence_status = verified`;
- `evidence_type = other`;
- a real existing JSON file with its correct canonical digest.

Observed result:

```text
frozen source -> accepted the opaque security evidence
candidate     -> rejected it because canonical categories require VerificationResult evidence
```

A separate schema-valid VerificationResult was emitted for this deliberately invalid security negative with `recommendation = reject_candidate` and a `security` finding. This seeded-negative object is not the candidate acceptance verdict.

## Exact execution result

PR #187 exact head:

`bcd3ad77cbd4d20339b4236ab2e5d785a63629db`

Workflow:

- run `33196056433` — success;
- job `98933357141` — success.

Candidate evidence:

- ResultManifest digest `sha256:44ae21059a9a36f56a4dce4d5641079e3ecb734c80d38e4d940501232eb10592`;
- candidate patch digest `sha256:d20c895d09e2f9521d8c1451cae29f9f859479f2f3401d81ba8b839ec87769eb`;
- VerificationResult digest `sha256:1f850bb3675ce43a61ceddb38ab9b72d565e87047e65374ccdb7a51413ccc7ab`;
- candidate verification `passed`;
- recommendation `accept_candidate`;
- changed path only `tools/benchmark_cohort.py`;
- metadata verifier adapter `0.3.0`;
- artifact/log/scope/added-transition/removed-transition checks passed;
- candidate code was not executed by the metadata-only verifier.

Seeded-negative evidence:

- baseline opaque security negative accepted;
- candidate opaque security negative rejected;
- seeded-negative VerificationResult digest `sha256:4956d0c335d42c25adb29e81add2c97cd832d6f4ad7de24c426b1ce017577ebe`;
- category `security`;
- recommendation `reject_candidate`.

Temporary GitHub Actions artifact:

- artifact `9695777042`;
- archive digest `sha256:ac1c6e1da03af22399ab3769f1cb343cc871904e903581e55697debc5590e6dd`;
- expiry `2026-09-11T17:44:25Z`.

A durable machine-readable receipt is stored at:

`docs/evidence/phase-b2-successor-task001-attempt001.json`

## Authority boundary

This attempt did not:

- edit `benchmarks/phase-b2-successor-five/cohort.json`;
- edit any frozen EvaluatorPlan;
- auto-select the candidate;
- write canonical benchmark state from CI;
- push or merge code;
- approve a pull request;
- grant the worker or verifier integration authority.

The worker self-report and verifier recommendation remain decision evidence only.

## Lifecycle decision

PR #187 is attempt-specific evidence instrumentation. Its useful result is the exact evidence bundle and reproducibility record, not a permanent Task-001 workflow on `main`.

After preserving this record and the machine-readable receipt, the PR should be closed unmerged. The frozen cohort definition remains unchanged.
