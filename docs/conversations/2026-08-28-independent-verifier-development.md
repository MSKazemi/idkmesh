# Conversation continuation — independent verifier development

**Date:** 2026-08-28

This record preserves the implementation work that followed the interoperability/system audit in the same project turn.

## Why this development was selected

The project-owner requested both evaluation and continued development.

After the interoperability layer was implemented, the repository's most important product gap was no longer the shape of verification evidence: `VerificationResult v0.1` had already landed through PR #47 and exact WorkUnit/ResultManifest/VerificationResult provenance binding was hardened through PR #60.

The remaining gap in issue #5 was **actual independent verifier execution**.

Therefore development moved to a new branch:

`verifier/independent-v0.1`

## Trust model

The implementation preserves the three-object protocol:

```text
WorkUnit v0.2
    -> worker
    -> ResultManifest v0.1 + candidate artifact
    -> independent verifier
    -> VerificationResult v0.1 + evidence
    -> human/governance/policy integration decision
```

The verifier is not allowed to merge or push.

## Verifier-side hidden plan

A new schema was added:

`schemas/verifier-plan-v0.1.schema.json`

This is deliberately **not part of the WorkUnit sent to the worker**.

The WorkUnit declares required validator IDs and evidence requirements. The verifier plan privately implements those requirements through modes such as:

- worker-result schema/lineage validation;
- candidate artifact integrity;
- repository scope policy;
- hidden test/lint/security commands in a separate Docker verifier sandbox.

The verifier refuses a plan that omits WorkUnit-required or worker-requested validators.

## Implemented runtime

Added:

- `verifier/src/idkmesh_verifier/model.py`;
- `verifier/src/idkmesh_verifier/runner.py`;
- `verifier/src/idkmesh_verifier/cli.py`;
- package entrypoints/metadata;
- unit tests;
- verifier CI;
- `verifier/README.md`.

### Input validation

The verifier checks:

- WorkUnit v0.2 schema;
- ResultManifest v0.1 schema;
- VerifierPlan v0.1 schema;
- exact canonical WorkUnit digest declared by the worker;
- WorkUnit/result id and version binding;
- full immutable Git source revision;
- WorkUnit provenance source revision consistency when declared;
- worker status succeeded;
- verifier identity different from worker identity;
- independent verification required;
- low-risk/public/sandbox-required policy for this MVP;
- no WorkUnit secrets;
- candidate artifact type is `patch`;
- all required/requested validator IDs are implemented by the private verifier plan.

### Candidate verification

For one candidate patch the verifier:

1. resolves the artifact under a bounded artifact root;
2. checks its SHA-256 against ResultManifest provenance;
3. clones the public Git source at the immutable worker source revision;
4. checks/applies the patch in a disposable checkout;
5. measures changed paths;
6. enforces WorkUnit `constraints.allowed_paths`, `constraints.forbidden_paths`, and `permissions.filesystem_write`;
7. executes configured hidden commands in a separate network-disabled Docker verifier sandbox;
8. writes an evidence file per check;
9. emits a schema-valid `VerificationResult v0.1` with exact WorkUnit, ResultManifest, source, and verifier-config digests.

## Sandbox policy

Hidden commands use Docker with:

- network disabled;
- read-only container root;
- Linux capabilities dropped;
- no-new-privileges;
- CPU/memory/PID limits;
- no Docker socket, host home, or credentials mounted;
- temporary candidate workspace.

This remains a controlled low-risk MVP. Docker is not treated as sufficient containment for arbitrary hostile public workloads.

## Decision support only

If all required checks pass, the verifier may emit:

`decision_support.recommendation = accept_candidate`

This means **the evidence supports accepting the candidate**. It is not an automated merge authorization.

If any required check fails, the runtime recommends rejection and records findings/evidence.

## Tests and CI

Unit tests cover:

- exact WorkUnit binding;
- self-verification rejection;
- wrong digest rejection;
- missing required hidden checks;
- risk/sandbox policy rejection;
- artifact-root escape rejection;
- repository scope enforcement;
- least-privilege Docker command shape;
- successful VerificationResult generation with mocked execution;
- rejection when scope policy fails despite a passing hidden command.

`.github/workflows/independent-verifier-check.yml` runs the existing Phase 0 contract/provenance checks and verifier unit tests without executing candidate code or Docker commands in GitHub-hosted CI.

## Remaining validation gate

Like the local worker backend, this verifier requires a separately recorded controlled Docker acceptance run before being described as maturity level 3 / realistically validated.

Issue #5 still also requires a real benchmark corpus and richer unauthorized dependency/security checks beyond the initial patch scope policy.
