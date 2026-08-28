# EvaluatorPlan v0.4 — added/removed transition semantics

EvaluatorPlan v0.4 is a **versioned metadata-only** successor to the first three evaluator-plan meanings.

It exists because Phase B2 calibration exposed two different failure modes in weaker semantic proxies:

1. exact full-line matching can reject a legitimate implementation when the plan contains only a fragment;
2. added-substring presence alone can be Goodharted by an inert mention that does not remove the unsafe mechanism.

The version boundary is therefore explicit:

| EvaluatorPlan | Verifier adapter | Static semantic contract |
|---|---|---|
| v0.2 | `deterministic-patch-verifier` 0.1.1 | every `required_added_text` value must equal a complete added line |
| v0.3 | `deterministic-patch-verifier` 0.2.0 | every `required_added_substrings` value must occur inside at least one added line |
| v0.4 | `deterministic-patch-verifier` 0.3.0 | every required added substring must occur in an added line **and** every required removed substring must occur in a removed line |

Historical v0.2 and v0.3 meanings are not reinterpreted.

## Contract

A v0.4 `unified_diff` backend requires both:

```json
{
  "required_added_substrings": ["safe_call("],
  "required_removed_substrings": ["unsafe_call("]
}
```

For each configured value:

- matching is case-sensitive;
- matching is contiguous substring matching;
- a match must occur within one individual validated hunk line;
- added matches do not span lines;
- removed matches do not span lines;
- no regular-expression, fuzzy, AST, or semantic-equivalence behavior is implied.

The verifier still applies the inherited checks for:

- strict, count-balanced textual Git unified-diff structure;
- candidate artifact SHA-256 integrity;
- required worker-log coverage and SHA-256 integrity;
- WorkUnit allowed/forbidden/write path scope;
- worker execution status;
- exact WorkUnit/source/EvaluatorPlan provenance binding;
- verifier identity distinct from the worker.

Candidate code is never executed by this metadata-only backend.

## Why require removal as well as addition?

Suppose the intended change is:

```text
unsafe_call(args.value)
        ->
safe_call(args.value)
```

An added-substring-only evaluator can be satisfied by an unrelated addition such as:

```text
<!-- safe_call( -->
```

while leaving `unsafe_call(args.value)` untouched.

v0.4 can encode the transition rather than only the destination vocabulary:

```text
added line contains:   safe_call(
removed line contains: unsafe_call(
```

The inert decoy fails because it contains no removed line matching `unsafe_call(`.

## Calibration matrix

The checked-in calibration fixtures use the **same correct patch bytes** across historical versions and a separate Goodhart decoy:

- `verification/fixtures/patch-transition/correct.patch`
- `verification/fixtures/patch-transition/decoy.patch`

Expected outcomes:

| Candidate | v0.2 exact line | v0.3 added substring | v0.4 transition |
|---|---:|---:|---:|
| correct replacement | reject | support | support |
| inert added-text decoy | n/a | support | reject |

This intentionally preserves the evidence that v0.3 added-substring matching alone is insufficient for the calibrated transition objective.

## Evidence-strength boundary

v0.4 is still a **static proxy**, not proof of runtime correctness or security.

A patch can potentially remove and add the expected textual forms while still being behaviorally wrong. Therefore:

> Use v0.4 to express a bounded textual transition when that transition is independently meaningful, but do not substitute substring checks for behavioral verification when a stronger verifier is available.

For security-sensitive or functional claims, a future task may pair metadata-only transition evidence with a separately versioned and explicitly sandboxed negative/behavioral evaluator. That higher-risk evaluator must have its own authority, isolation, provenance, and pre-outcome commitment. v0.4 itself remains non-executing.

## Provenance

A VerificationResult produced under v0.4 must retain:

- exact WorkUnit digest;
- exact ResultManifest digest;
- exact EvaluatorPlan v0.4 digest;
- source revision;
- verifier adapter version `0.3.0`;
- semantic mode `added_and_removed_line_substring_all`;
- added-substring evidence inherited from v0.3;
- removed-substring evidence introduced by v0.4.

The canonical evaluator runner reports v0.4 runner version `0.4` while preserving the current runner-version marker for v0.1–v0.3 results.

## Phase B2 rule

The original `phase-b2-first-five` cohort remains burned and its frozen plans/digest must not be changed.

A future successor cohort may use v0.4 only after:

1. v0.2 exact-line reproducibility remains green;
2. v0.3 added-substring reproducibility remains green;
3. the v0.4 correct/decoy calibration matrix is green;
4. exact plan/verifier provenance is green;
5. the new cohort is frozen before candidate outcomes are observed.

Task 001 from the burned cohort is already solved and must not be reused as untouched held-out evidence.

## Authority

EvaluatorPlan v0.4 adds no authority to:

- write canonical repository state;
- push branches;
- approve pull requests;
- merge changes;
- automatically select a candidate;
- spend project funds.

Verifier output remains decision support. Integration authority remains external.
