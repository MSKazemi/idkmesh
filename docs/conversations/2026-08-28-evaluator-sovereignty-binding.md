# Conversation record: evaluator sovereignty and bound verification control

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`  
**Primary issues:** #5, #14, #16, #37

## User direction

The project owner asked IDKMesh to continue autonomously from the previous verification/backpressure work and keep the substantive project output in the public repository.

## Starting point

The immediately preceding work had added:

- WorkUnit v0.2 and ResultManifest contracts;
- independent VerificationResult v0.1;
- verification debt and risk-weighted verification backpressure;
- a clear next step toward an executable independent validator.

## Repository coordination discovery

While an independent-validator implementation was being prepared, the repository was changing concurrently.

A first branch/PR (`#73`) attempted to add a local metadata-only validator. During that work, **PR #72 — Build zero-cost executable independent verifier MVP** merged into `main` and solved the same core gap with:

- `experiments/local_verifier.py`;
- verifier-owned policy outside candidate roots;
- artifact-digest checks;
- isolated candidate-scope checks;
- an independent deterministic acceptance check;
- VerificationResult output and provenance integrity;
- positive/negative fixtures and CI.

Rather than keep two competing verifier implementations, PR #73 was explicitly closed as superseded.

This is an important collaboration rule for IDKMesh itself: when parallel branches converge on the same subsystem, prefer reconciliation and incremental differentiation over duplicating architecture.

## New gap selected

PR #72 separated verifier policy from the candidate workspace, but the policy object itself was still a small untyped control file. The remaining trust gap was **evaluator-control binding**:

- Is this evaluator policy intended for this exact WorkUnit?
- Is it intended for this exact source revision?
- Does it cover every currently required WorkUnit validator?
- Is the verifier implementation/version the expected one?
- Can the candidate accidentally own evaluator control or verifier output?
- Can a replay prove exactly which full evaluator configuration produced a VerificationResult?

## Decision: Evaluator Sovereignty

IDKMesh adopted **Evaluator Sovereignty** as ADR-0009.

The core principle is:

> A worker must not control the evaluator used to judge its own candidate, and evaluator independence must be content-bound rather than inferred only from filesystem location.

The trust chain is now:

```text
WorkUnit          -> public requirements and authority
ResultManifest    -> untrusted worker self-report
EvaluatorPlan     -> verifier-owned, content-bound control plane
VerificationResult-> independent evidence and recommendation
integration       -> separate later policy/human authority
```

## EvaluatorPlan v0.1

Added:

- `schemas/evaluator-plan-v0.1.schema.json`
- `verification/fixtures/verifier-smoke-evaluator-plan.json`

The plan binds:

- WorkUnit id;
- WorkUnit version;
- canonical WorkUnit SHA-256;
- expected source revision;
- exact required validator IDs;
- expected verifier id/adapter/version;
- public/hidden visibility;
- current metadata-only operational policy;
- candidate/evaluator/output separation invariants.

## Mathematical/content-addressed invariant

Let:

```text
H_W = SHA256(canonical_json(WorkUnit))
H_E = SHA256(canonical_json(EvaluatorPlan))
V_W = RequiredValidatorIDs(WorkUnit)
V_E = EvaluatorPlan.required_validator_ids
```

Before evaluation:

```text
Plan.work_unit_id      = WorkUnit.id
Plan.work_unit_version = WorkUnit.version
Plan.work_unit_digest  = H_W
Plan.source_revision   = ResultManifest.source_revision
V_E                    = V_W
Plan.verifier.id       != ResultManifest.worker.id
Plan.path              not-in CandidateRoot
VerificationOutput     not-in CandidateRoot
```

After evaluation:

```text
VerificationResult.provenance.verifier_config_digest = H_E
```

Mismatch means fail closed before positive decision support.

## Guard implementation

Added `experiments/evaluator_plan_runner.py`.

It is intentionally a **guard/wrapper**, not a second verifier. It delegates candidate evaluation to the already merged `experiments/local_verifier.py` from PR #72.

The guard:

- validates EvaluatorPlan schema;
- recomputes the canonical WorkUnit hash;
- enforces WorkUnit/source-revision binding;
- requires exact required-validator coverage;
- requires the current local verifier's supported validator set;
- requires the worker's verification request to include required validators;
- rejects worker/verifier identity collision;
- rejects evaluator plans inside candidate roots;
- rejects verifier outputs inside candidate roots;
- checks the actual underlying verifier identity/version against the plan;
- replaces verifier configuration provenance with the SHA-256 of the complete EvaluatorPlan;
- re-validates VerificationResult and cross-object provenance integrity.

## Fail-closed self-tests

The evaluator-plan self-test first confirms the existing PR #72 known-good candidate still passes and known-bad self-consistent candidate still fails.

It then requires rejection of:

1. a wrong WorkUnit digest binding;
2. a wrong source revision;
3. missing required validator coverage;
4. a worker/verifier identity collision;
5. an EvaluatorPlan placed inside a copied candidate workspace;
6. a proposed VerificationResult output inside the candidate workspace.

It also confirms that the successful VerificationResult contains the SHA-256 of the complete EvaluatorPlan.

## CI evidence

Added `.github/workflows/evaluator-plan-binding.yml`.

The workflow runs only metadata/deterministic checks and does not execute candidate code.

For PR #81, all triggered workflows completed successfully. The dedicated `Evaluator plan binding` job explicitly passed:

- base local verifier fixtures;
- evaluator sovereignty and binding self-tests.

## Merge

**PR #81 — Bind verifier control to exact WorkUnit with EvaluatorPlan** was squash-merged into `main`.

Merge commit:

`403658833ed484fbd71b4c9140176a4de7d1e542`

Issue #5 was updated with the completion evidence and remains open.

## Important non-claim

This work does **not** claim that repository-level hidden tests are safely executable yet.

It does not:

- execute candidate code;
- satisfy Docker acceptance gate #37;
- add sandboxed regression/security/fuzz execution;
- complete the real benchmark corpus;
- grant automatic merge authority.

## Next dependency

The next high-value verifier step is gated by **issue #37**: run the canonical `idkmesh-node` smoke on a controlled Docker host and bind evidence to the exact tested commit.

After that gate is satisfied, extend the existing verifier with a disposable sandbox backend where:

```text
verifier-owned hidden evaluator/test bundle (read-only, digest-bound)
                    +
          untrusted candidate workspace
                    |
                    v
              disposable sandbox
                    |
                    v
       normalized VerificationResult evidence
```

EvaluatorPlan should become the content-addressed control object for those hidden/regression/security checks rather than inventing another parallel verifier protocol.
