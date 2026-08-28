# Conversation Record — EvaluatorPlan v0.2 Repository-Patch Convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner direction

The project owner asked the assistant to continue improving the public repository.

This continuation followed the executable Verified Swarm Runner critical path rather than adding another theory layer.

## Trigger

PR #76 originally introduced a private `VerifierPlan v0.1` for repository-patch reconstruction and hidden Docker checks.

While that branch was open, `main` accepted **Evaluator Sovereignty** in PR #81 / ADR-0009 and established `EvaluatorPlan v0.1` as the canonical verifier-owned control-plane object.

Independent review therefore found a protocol-convergence problem:

```text
EvaluatorPlan + VerifierPlan
```

would create two overlapping ways to bind evaluator identity, hidden checks, validator coverage, and source provenance.

PR #76 was moved to draft and the repository was instructed to converge rather than preserve both protocols.

## Decision

Extend the accepted EvaluatorPlan lineage explicitly:

```text
EvaluatorPlan v0.1
  execution_mode = metadata_only
  deterministic/no-candidate-code evaluation

EvaluatorPlan v0.2
  execution_mode = repository_patch
  exact WorkUnit/source binding
  patch integrity and scope checks
  verifier-owned hidden container commands
```

The old `schemas/verifier-plan-v0.1.schema.json` is removed from the branch.

## EvaluatorPlan v0.2 invariants

The new schema requires:

- exact WorkUnit id;
- exact WorkUnit version;
- canonical WorkUnit SHA-256 digest;
- immutable source revision;
- verifier identity/type/adapter/version;
- exact required/requested validator set;
- source input and candidate artifact identity;
- hidden check definitions;
- policy requiring plan/output separation, verifier/worker identity separation, and fresh workspace per hidden command.

Runtime validation fails closed when the EvaluatorPlan binding drifts from either the WorkUnit or the worker ResultManifest source provenance.

Duplicate check IDs are rejected before execution so a later check cannot overwrite status/evidence from an earlier check.

## Check contamination finding and repair

The earlier patch verifier mounted the same patched workspace read-write into every hidden check.

That made evaluation order-dependent:

```text
check A mutates candidate
 -> check B observes mutation from A
```

and allowed one hidden command to contaminate another verifier's evidence subject.

The revised runtime keeps one evaluator-owned patched base workspace for artifact/scope measurement and creates a fresh disposable copy for each `container_command`:

```text
base patched candidate
  -> copy A -> check A -> discard
  -> copy B -> check B -> discard
  -> copy C -> check C -> discard
```

A hidden command may create build/test files inside its own disposable copy, but those files cannot change later checks or the base integrity/scope evidence.

A unit test mutates the first check copy and verifies that the second copy and base candidate remain unchanged.

## Correlation metadata

The previous implementation marked `shared_runtime=true` whenever the worker reported any container image at all.

The revised implementation only marks it true when the worker-reported configured image equals the evaluator configured image. This is still a coarse proxy and should later use immutable image/runtime provenance where available.

## Versioning

The repository-patch evaluator package is moved to `0.2.0` to reflect the control-plane contract change.

`VerificationResult` remains v0.1; this work changes evaluator configuration/runtime semantics, not the independent evidence result protocol.

## Remaining gates

This convergence does **not** make the repository-patch evaluator production-ready.

Still required before readiness/merge:

- synchronize the branch with current `main`;
- green schema/unit/provenance CI after the migration;
- immutable evaluator container image runtime provenance comparable to the hardened node path;
- bounded whole-evaluation time/resource policy;
- stronger host Git/source-reconstruction isolation;
- controlled real Docker acceptance;
- benchmark/evaluator corpus work required by issue #5.

The safer metadata/JSON evaluator remains preferred whenever candidate code execution is unnecessary.

## Principle reinforced

> **Extend an accepted control-plane protocol explicitly instead of creating a parallel protocol with overlapping authority.**

This keeps worker, evaluator, evidence, and integration authority composable as IDKMesh grows.
