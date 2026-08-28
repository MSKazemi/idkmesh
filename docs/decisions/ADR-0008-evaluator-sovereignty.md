# ADR-0008: Evaluator Sovereignty

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related:** #5, #14, #16; `schemas/evaluator-plan-v0.1.schema.json`; `experiments/local_validator.py`

## Context

IDKMesh now has separate WorkUnit, worker ResultManifest, and independent VerificationResult contracts. The remaining trust problem is control of the evaluator itself.

If a candidate worker can modify the tests, verification policy, baseline, or evaluator configuration used to judge its own work, independent verification collapses even if the final result object has a separate verifier identity.

At the same time, immediately executing arbitrary hidden tests or WorkUnit commands on the host would create a new remote-code-execution risk.

## Decision

Adopt **Evaluator Sovereignty** as an IDKMesh invariant.

The evaluator's control data is a separate verifier-owned object (`EvaluatorPlan`) that:

1. is cryptographically bound to the exact WorkUnit digest and expected source revision;
2. may be public or hidden from the worker;
3. must remain outside the candidate workspace when independence is required;
4. describes which verifier-owned checks implement the WorkUnit's required validator IDs;
5. cannot grant merge/integration authority;
6. is independently hashed and recorded in VerificationResult provenance.

The first local validator backend is intentionally `metadata_only`. It performs deterministic schema, scope, artifact-digest, provenance, and verification-request checks but never executes candidate-controlled code on the host.

## Rationale

This preserves two independent security boundaries:

```text
worker cannot rewrite evaluator
verifier cannot automatically integrate candidate
```

It also lets IDKMesh make useful progress on independent verification before a safe sandbox execution backend exists.

The deterministic scope rule is:

```text
Delta = complete_candidate_snapshot XOR trusted_baseline_snapshot

Authorized(p) =
  Allowed(p)
  AND Writable(p)
  AND NOT Forbidden(p)

ScopePass = all(Authorized(p) for p in Delta)
```

The verifier derives `Delta` itself rather than trusting the candidate's declared output list.

## Consequences

### Positive

- a worker cannot hide an unauthorized file merely by omitting it from ResultManifest;
- artifact tampering can be detected independently;
- evaluator configuration is reproducible and content-addressable;
- hidden evaluator details can remain verifier-controlled where appropriate;
- verifier outputs remain auditable without becoming merge authority;
- future sandboxed hidden tests have an explicit control-plane object to attach to.

### Costs

- coordinator/verifier storage must preserve evaluator plans separately from candidate workspaces;
- complete baseline snapshots cost hashing/storage time;
- metadata-only verification does not establish semantic code correctness;
- sandbox execution remains necessary for real hidden/regression/security tests.

## Alternatives considered

### Put all verification commands directly in WorkUnit

Rejected as the sole design. Public declarative validator requirements belong in WorkUnit, but the worker should not control the concrete evaluator implementation used to judge its own output.

### Trust ResultManifest artifact declarations

Rejected. The worker could omit unauthorized changes. The verifier must derive the changed-path set independently.

### Execute candidate or WorkUnit commands directly on the verifier host

Rejected for v0.1. This creates an unnecessary code-execution risk before sandbox/resource/network boundaries are implemented.

### Let the verifier merge when checks pass

Rejected. Verification evidence and integration authority remain separate layers.

## Follow-up

The next verifier execution backend should run trusted hidden evaluator code plus an untrusted candidate inside a disposable sandbox, with the evaluator mounted read-only and outside candidate write authority. The metadata-only backend should remain available as a cheap deterministic preflight layer.
