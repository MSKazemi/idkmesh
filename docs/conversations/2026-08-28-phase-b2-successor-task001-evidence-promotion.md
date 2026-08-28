# Project Turn: Promote Phase B2 successor Task 001 evidence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## User direction

> https://github.com/MSKazemi/idkmeshcontinue

## Frozen benchmark control

Active scored cohort:

`benchmark/phase-b2-successor-five`

Frozen definition digest:

`sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`

PR #182 froze and merged the definition before outcomes. Tracker #180 later confirmed that this remains the active scored lineage; `phase-b2-successor-v2` is a future mutable scaffold and does not supersede scored evidence for #182.

## Attempt execution

PR #187 ran the first bounded `single-worker-baseline-v1` attempt for successor Task 001.

Successful exact attempt head:

`bcd3ad77cbd4d20339b4236ab2e5d785a63629db`

Workflow run/job:

- run `33196056433`;
- job `98933357141`.

The first run attempt had failed only because the manually constructed seeded-negative VerificationResult ID exceeded the protocol length regex. The repair shortened that evidence-object ID only; candidate logic, frozen WorkUnit, frozen EvaluatorPlan, and seeded-negative behavior were unchanged.

The rerun succeeded through:

- exact frozen source identity;
- baseline opaque-security-evidence bug reproduction;
- bounded candidate generation changing only `tools/benchmark_cohort.py`;
- Python compile and existing cohort self-test;
- frozen EvaluatorPlan v0.4 verification;
- separate behavioral seeded-negative security verification;
- evidence upload.

PR #187 then merged as:

`509c7592341557230cfb2256895075347b00c045`

## Workflow artifact

Artifact:

- ID `9695777042`;
- name `phase-b2-successor-task001-attempt001`;
- ZIP SHA-256 `sha256:ac1c6e1da03af22399ab3769f1cb343cc871904e903581e55697debc5590e6dd`.

The artifact was downloaded and all file/canonical JSON digests were independently recomputed before promotion.

## Canonical promoted evidence

Candidate patch:

`sha256:d20c895d09e2f9521d8c1451cae29f9f859479f2f3401d81ba8b839ec87769eb`

ResultManifest canonical digest:

`sha256:44ae21059a9a36f56a4dce4d5641079e3ecb734c80d38e4d940501232eb10592`

Frozen-plan candidate VerificationResult canonical digest:

`sha256:1f850bb3675ce43a61ceddb38ab9b72d565e87047e65374ccdb7a51413ccc7ab`

Seeded-negative VerificationResult canonical digest:

`sha256:4956d0c335d42c25adb29e81add2c97cd832d6f4ad7de24c426b1ce017577ebe`

Behavioral observation digest:

`sha256:f1b6755c8883c8f48baad34449cd850d01dce73bf7ce433038bff457a7d4ab39`

All exact artifact files are promoted under:

`benchmarks/phase-b2-successor-five/evidence/task-001/attempt-001/`

including patch, stdout/stderr, observation, ResultManifest, candidate VerificationResult, seeded-negative VerificationResult, summary, and artifact provenance.

## Evidence interpretation

The frozen source accepted the seeded invalid case:

- category `security`;
- `evidence_status = verified`;
- `evidence_type = other`;
- digest-valid but semantically unrelated JSON.

The candidate rejects the same case specifically because canonical finding categories now require canonical VerificationResult evidence.

The frozen v0.4 metadata-only evaluator independently reports:

- status `passed`;
- recommendation `accept_candidate`;
- all required WorkUnit checks passed;
- expected added transition substrings matched;
- expected removed unsafe gate matched;
- only `tools/benchmark_cohort.py` changed;
- exact frozen plan digest retained in VerificationResult provenance.

The separate seeded-negative VerificationResult intentionally reports:

- status `failed`;
- recommendation `reject_candidate`;
- category `security`;

because it represents the deliberately invalid opaque-evidence input, not the corrected candidate's acceptance verdict.

## Cohort indexing

Task 001 is changed from `pending` to `verified` with one analyzed attempt:

- attempt ID `attempt-001`;
- structural signature `single-worker-baseline-v1`;
- outcome `support`;
- repository-local ResultManifest and VerificationResult refs;
- verified seeded-negative VerificationResult ref.

Tasks 2–5 remain pending.

The pre-outcome definition digest is not modified. The Benchmark Cohort Contract must still compute and accept:

`sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`

## Authority boundary

Promoting and indexing this evidence does not:

- merge the candidate patch into product code;
- automatically select future candidates;
- grant canonical-write, push, approval, or merge authority to worker/verifier systems;
- complete issue #5;
- convert one deterministic baseline attempt into a claim about collective intelligence.

The next scored step should be Task 002 only if verification/review capacity remains healthy.
