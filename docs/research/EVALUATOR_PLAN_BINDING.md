# Evaluator Plan Binding

## Purpose

The executable local verifier merged in PR #72 establishes that IDKMesh can independently reject a self-consistent but incorrect candidate without trusting worker claims.

This follow-up strengthens the **verifier control plane**. It adds a schema-validated EvaluatorPlan that is bound to the exact WorkUnit and source revision before the existing local verifier is allowed to evaluate a candidate.

## Why another object?

A verifier policy that merely lives outside a candidate directory can still be wrong in several ways:

- it may have been written for another WorkUnit;
- it may target a stale repository revision;
- it may omit a newly required validator;
- its verifier implementation/version may have changed;
- its output might accidentally be written into worker-controlled state;
- a replay may not know exactly which complete evaluator configuration produced a result.

The EvaluatorPlan makes those failure modes machine-checkable.

## Protocol chain

```text
WorkUnit v0.2
    |
    +--> ResultManifest v0.1        (worker-owned claim)
    |
    +--> EvaluatorPlan v0.1         (verifier-owned control)
              |
              v
       existing local verifier
              |
              v
      VerificationResult v0.1      (evidence / decision support)
```

`experiments/evaluator_plan_runner.py` is a guard around `experiments/local_verifier.py`; it does not reimplement candidate evaluation.

## Content binding

Canonical JSON uses sorted keys and compact separators, matching existing IDKMesh provenance hashing.

For WorkUnit `W` and EvaluatorPlan `E`:

```text
H_W = SHA256(canonical_json(W))
H_E = SHA256(canonical_json(E))
```

The pre-evaluation gate requires:

```text
E.binding.work_unit_digest = H_W
E.binding.work_unit_id = W.id
E.binding.work_unit_version = W.version
E.binding.source_revision = ResultManifest.provenance.source_revision
```

If the WorkUnit itself declares a source revision, that revision must also equal the plan binding.

## Validator coverage invariant

Let:

```text
V_W = {v.id | v in WorkUnit.validators and v.required = true}
V_E = set(EvaluatorPlan.required_validator_ids)
```

v0.1 requires exact equality:

```text
V_E = V_W
```

Exact equality is intentionally stricter than subset coverage. It makes an evaluator-plan review explicitly acknowledge changes in the WorkUnit's required verification surface.

The current deterministic verifier MVP implements exactly:

```text
artifact-digest
candidate-scope
independent-acceptance
```

A different validator set must fail closed until a compatible evaluator backend is implemented rather than silently pretending coverage.

## Independence boundaries

When the plan policy requires independence:

```text
EvaluatorPlan.verifier.id != ResultManifest.worker.id
EvaluatorPlan.path not-in CandidateRoot
VerificationResult.output_path not-in CandidateRoot
```

The plan may be marked `public` or `hidden`. Visibility describes whether workers can inspect evaluator control data; it does not weaken any binding or independence rule.

## Verifier provenance

The underlying local verifier already records `verifier_config_digest`. The guarded runner replaces that field with the digest of the **complete EvaluatorPlan**:

```text
VerificationResult.provenance.verifier_config_digest = H_E
```

It also records the plan id, digest, visibility, execution mode, and guard-runner version in namespaced extensions.

This means a VerificationResult can be traced not merely to a small operational policy fragment, but to the complete bound evaluator-control object.

## Deterministic negative tests

`python experiments/evaluator_plan_runner.py self-test` first proves that the existing known-good and known-bad PR #72 candidates retain their expected verdicts. It then mutates the control plane and requires every case below to fail closed:

1. wrong WorkUnit digest;
2. wrong source revision;
3. missing required validator ID;
4. verifier identity colliding with worker identity;
5. evaluator plan placed inside a copied candidate workspace;
6. proposed VerificationResult output inside candidate workspace.

The test also asserts that the successful VerificationResult records the SHA-256 digest of the full EvaluatorPlan.

## Security scope

This remains a metadata-only verifier layer.

It does not:

- execute candidate code;
- run candidate-supplied commands;
- add network access;
- mount secrets;
- grant merge authority;
- authorize project-paid compute;
- satisfy the controlled Docker runtime gate in issue #37.

## Relationship to hidden tests

EvaluatorPlan is intended to become the stable control object for hidden/regression/security checks after a sandbox backend exists.

A future plan may describe a trusted evaluator bundle such that:

```text
trusted evaluator bundle (read-only)
             +
untrusted candidate workspace
             |
             v
      disposable sandbox
             |
             v
normalized evidence + provenance
```

The evaluator bundle should be bound by digest just as the current WorkUnit and plan are bound. A worker should not be able to alter the hidden tests used to judge its own candidate.

## Success criteria for this increment

This increment is useful if:

- current PR #72 verifier behavior remains unchanged for its good/bad fixtures;
- binding drift fails before positive decision support;
- required validator coverage cannot silently shrink;
- verifier configuration is content-addressed in VerificationResult provenance;
- evaluator control/output cannot live in the candidate root;
- all tests run in public zero-cost CI without executing candidate code.

## Next step

Do not build a second verifier. After issue #37 provides a controlled Docker execution gate, extend the existing verifier path with a sandboxed evaluator backend and use EvaluatorPlan to bind real repository regression/hidden checks to fixed source snapshots.
