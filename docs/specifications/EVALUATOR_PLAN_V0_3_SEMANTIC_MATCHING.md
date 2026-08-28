# EvaluatorPlan v0.3 semantic matching

Status: **proposed additive verification contract**  
Issue: #157

## Why a new version exists

The original frozen Phase B2 first-five cohort exposed a contract mismatch only after task 001 had a real solution.

EvaluatorPlan v0.2 used:

```json
"required_added_text": ["resolve_repo_file(args.cohort"]
```

Deterministic patch verifier v0.1.1 has always interpreted each value as one **complete added line** from a structurally valid unified-diff hunk. A valid solution can contain that fragment inside a longer Python statement while still failing exact-line membership.

The correct response is not to reinterpret v0.2 after observing the outcome. The original cohort is retained as burned diagnostic evidence. v0.3 introduces an explicit semantic contract instead.

## Compatibility invariant

The following historical behavior is immutable:

```text
EvaluatorPlan v0.2
  verifier deterministic-patch-verifier v0.1.1
  required_added_text
  => exact complete added-line membership
```

No v0.3 code edits `schemas/evaluator-plan-v0.2.schema.json`, the v0.1.1 implementation, or the burned cohort plans/digests.

## v0.3 contract

EvaluatorPlan v0.3 binds:

```text
schema_version = 0.3
verifier.adapter = deterministic-patch-verifier
verifier.adapter_version = 0.2.0
backend.type = unified_diff
backend.required_added_substrings = [...]
```

Each configured substring must occur **verbatim within at least one added line returned by the existing strict unified-diff parser**.

Formally, for parsed added lines `A` and required fragments `R`:

```text
semantic_pass = for every r in R, there exists a in A such that r is a substring of a
```

Matching is case-sensitive and whitespace-sensitive. Newline characters are forbidden inside configured fragments.

Text outside a validated `@@` hunk cannot satisfy the contract because it never enters `A`.

## Safety composition

Patch verifier v0.2.0 is a semantic layer over the existing v0.1.1 metadata-only safety kernel. It reuses the existing implementation for:

- strict textual Git unified-diff parsing and count-balanced hunks;
- repository path extraction and WorkUnit write-scope enforcement;
- candidate artifact SHA-256 recomputation;
- required stdout/stderr coverage and digest verification;
- worker-status checks;
- ResultManifest / WorkUnit binding;
- candidate-code non-execution.

The new layer changes only the verifier-owned semantic predicate and the evidence that records how that predicate was evaluated.

## Evidence and provenance

VerificationResult remains v0.1. For a v0.3 plan it records:

- verifier adapter version `0.2.0`;
- exact original EvaluatorPlan v0.3 digest in `provenance.verifier_config_digest`;
- the same digest in the evaluator-plan extension;
- semantic mode `substring_in_validated_added_line`;
- required substrings;
- observed validated added lines;
- matching lines per substring;
- missing substrings, if any.

Verifier support remains decision support only. No candidate-selection, repository-write, push, approval, or merge authority is introduced.

## Required regression

The same existing good patch contains the complete added line:

```text
<!-- patch-evaluator expected -->
```

The regression deliberately evaluates the fragment:

```text
patch-evaluator expected
```

Expected outcomes:

```text
v0.2 + v0.1.1 required_added_text      => reject (not the complete line)
v0.3 + v0.2.0 required_added_substrings => support (fragment occurs inside line)
```

This locks the semantic distinction into executable evidence rather than prose.

## Successor cohort rule

A Phase B2 successor cohort may use v0.3 only after this versioned contract is green and independently reviewed. The successor must receive a new cohort identity/digest and must not treat the already-solved original task 001 as untouched held-out evidence.

The burned first-five cohort remains immutable and reproducible under v0.2/v0.1.1.
