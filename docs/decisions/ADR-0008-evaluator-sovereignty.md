# ADR-0008: Evaluator Sovereignty

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related:** #5, #14, #16, PR #72

## Context

PR #72 established the first zero-cost executable local verifier. It correctly keeps its verifier-owned policy outside the candidate root and never executes candidate-controlled code.

The next trust problem is not candidate evaluation itself; it is **binding the evaluator control plane to the exact work being evaluated**. A verifier policy file that is merely located elsewhere can still become stale, point at the wrong revision, omit a required validator, or be substituted accidentally.

## Decision

Adopt **Evaluator Sovereignty** as an IDKMesh invariant.

A verifier-owned `EvaluatorPlan` must be a separate machine-readable object that:

1. binds the exact WorkUnit id, document version, canonical SHA-256 digest, and expected source revision;
2. declares exactly which required WorkUnit validator IDs it implements;
3. identifies the verifier implementation/version expected to execute it;
4. may be public or hidden from the worker;
5. remains outside the candidate workspace;
6. requires VerificationResult output to remain outside the candidate workspace;
7. requires verifier identity to differ from worker identity when independent verification is requested;
8. is itself canonically hashed and recorded as `VerificationResult.provenance.verifier_config_digest`;
9. remains decision support only and grants no integration or merge authority.

The first implementation is `schemas/evaluator-plan-v0.1.schema.json` plus `experiments/evaluator_plan_runner.py`. It wraps the existing `experiments/local_verifier.py`; it is deliberately not a competing verifier implementation.

## Binding invariant

Let:

```text
W = canonical_json(WorkUnit)
H_W = SHA256(W)
H_E = SHA256(canonical_json(EvaluatorPlan))
V_W = RequiredValidatorIDs(WorkUnit)
V_E = EvaluatorPlan.required_validator_ids
```

Before candidate evaluation, require:

```text
EvaluatorPlan.binding.work_unit_id      = WorkUnit.id
EvaluatorPlan.binding.work_unit_version = WorkUnit.version
EvaluatorPlan.binding.work_unit_digest  = H_W
EvaluatorPlan.binding.source_revision   = ResultManifest.provenance.source_revision
V_E                                      = V_W
EvaluatorPlan.verifier.id               != ResultManifest.worker.id
EvaluatorPlan.path                      not-in CandidateRoot
VerificationResult.output               not-in CandidateRoot
```

After evaluation, require:

```text
VerificationResult.provenance.verifier_config_digest = H_E
```

Any mismatch fails closed before a candidate can receive positive decision support.

## Rationale

A candidate should not control the evaluator that judges it, but evaluator independence is stronger than filesystem separation. The evaluation specification must also be content-addressed and bound to the exact WorkUnit/revision.

This creates a four-object trust model:

```text
WorkUnit          -> public requirements / authority
ResultManifest    -> untrusted worker self-report
EvaluatorPlan     -> verifier-owned bound control plane
VerificationResult-> independent evidence / recommendation
```

The model makes evaluator drift, substitution, and missing-check errors observable and reproducible.

## Consequences

### Positive

- stale or substituted evaluator policy is detectable;
- a WorkUnit cannot silently lose a required validator during evaluation;
- verifier identity/version is pinned before execution;
- hidden evaluator plans can exist without changing the public WorkUnit contract;
- later sandboxed hidden tests have a stable control-plane object to bind to;
- verifier configuration becomes content-addressed provenance.

### Costs

- another versioned protocol object must be maintained;
- WorkUnit changes require corresponding EvaluatorPlan updates;
- v0.1 currently supports only the three deterministic validator IDs implemented by the local verifier MVP;
- this does not replace the Docker/sandbox gate or prove semantic correctness for arbitrary code.

## Alternatives considered

### Keep an untyped policy JSON only

Rejected as the durable design. Location outside the candidate root is useful but does not prove that policy belongs to this WorkUnit/revision or covers all required validators.

### Put hidden evaluator implementation directly in WorkUnit

Rejected. WorkUnit should expose acceptance requirements, while verifier implementation/control may need to remain independently owned or hidden.

### Let verifier success authorize merge

Rejected. Verification evidence and integration authority remain separate.

## Follow-up

After the controlled Docker gate in issue #37 is satisfied, extend EvaluatorPlan with a sandboxed execution backend where verifier-owned hidden tests are mounted read-only and candidate code runs with explicit network, filesystem, resource, and time limits.
