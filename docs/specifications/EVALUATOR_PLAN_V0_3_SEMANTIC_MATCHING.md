# EvaluatorPlan v0.3 semantic matching

Status: experimental, required before a successor to the burned Phase B2 first-five pilot.

## Why a new version exists

The first frozen Phase B2 pilot exposed an ambiguity that must not be repaired by changing history.

EvaluatorPlan v0.2 uses:

```json
"required_added_text": ["..."]
```

Deterministic patch verifier v0.1.1 interprets each value as an **exact full added-line requirement**. The burned pilot's plans instead contained semantic fragments. Once a real task solution exposed that mismatch, changing v0.2/v0.1.1 to substring matching would have changed the meaning of already-frozen evidence.

Therefore v0.2 and verifier v0.1.1 remain unchanged. Substring semantics use a new schema and verifier version.

## Version matrix

| EvaluatorPlan | Verifier adapter version | Semantic field | Meaning |
| --- | --- | --- | --- |
| v0.2 | `deterministic-patch-verifier` `0.1.1` | `required_added_text` | every configured value must equal one complete added line |
| v0.3 | `deterministic-patch-verifier` `0.2.0` | `required_added_substrings` | every configured value must occur within at least one individual added line |

The canonical `experiments/evaluator_plan_runner.py` routes both versions. It does not reinterpret a v0.2 plan as v0.3.

## v0.3 substring semantics

For each `required_added_substrings[i] = s`, verification succeeds for that semantic requirement iff there exists an added line `L` parsed from a structurally valid unified-diff hunk such that:

```text
s is a contiguous, case-sensitive substring of L
```

More formally:

```text
match(s, A) = 1  iff  exists L in A such that s ⊑ L
```

where `A` is the set/list of validated-hunk added lines and `⊑` means contiguous substring containment.

All configured substrings are required:

```text
semantic_pass = AND_s match(s, A)
```

The operation is deliberately simple:

- case-sensitive;
- contiguous;
- one added line at a time;
- no regular expressions;
- no cross-line matching;
- no fuzzy/edit-distance matching;
- no execution of candidate code.

## Reuse of the hardened v0.1.1 core

`experiments/substring_patch_verifier.py` is a versioned semantic adapter over the existing hardened metadata-only patch-verifier core.

It independently parses the same candidate patch, maps each required substring to a concrete matching added line when one exists, and delegates structural diff validation, artifact hashing, log integrity, WorkUnit scope, and required-check construction to the unchanged v0.1.1 core.

The resulting VerificationResult adds an explicit `added-substring-semantic-observation` evidence item containing:

- semantic mode;
- required substrings;
- parsed added lines;
- per-substring matched line;
- missing substrings;
- parse error, if any.

This makes the new semantic decision auditable without changing the historical verifier implementation.

## Required provenance

A v0.3 VerificationResult must preserve:

- verifier adapter: `deterministic-patch-verifier`;
- verifier adapter version: `0.2.0`;
- exact EvaluatorPlan v0.3 canonical digest in `provenance.verifier_config_digest` after canonical runner binding;
- evaluator plan id/digest/visibility/execution mode/backend in namespaced extensions;
- semantic mode `added_line_substring_all`;
- legacy structural-core version `0.1.1` as an implementation provenance detail.

A plan/result version mismatch fails closed in the canonical runner.

## Contrast test

The repository uses the same candidate patch for the version boundary test. The patch adds:

```text
<!-- patch-evaluator expected -->
```

Both contrast plans require the fragment:

```text
patch-evaluator expected
```

Expected behavior:

```text
EvaluatorPlan v0.2 + verifier 0.1.1 -> reject
EvaluatorPlan v0.3 + verifier 0.2.0 -> support
```

The v0.2 rejection is intentional evidence that historical exact-line meaning has not changed. The v0.3 support proves that substring meaning is introduced only under the new version.

The self-test also requires both versions to report the same candidate-patch digest, proving the semantic comparison did not change candidate bytes.

## Successor-cohort rule

A successor Phase B2 cohort may use v0.3 only after:

1. schema validation is green;
2. the v0.2 regression test remains green;
3. the v0.3 contrast test is green;
4. exact plan/verifier provenance checks are green.

The burned first-five cohort must remain burned with its original definition digest. Task 001 is already known and cannot be presented as untouched held-out evidence in a successor cohort.

## Authority boundary

Neither v0.2 nor v0.3 executes candidate code. Neither verifier recommendation grants:

- canonical repository writes;
- push authority;
- pull-request approval;
- merge authority;
- automatic candidate selection;
- spending authority.

Verification remains decision-support evidence for a later integration/human-governance stage.

Related: issue #157, PR #153, PR #160, `benchmarks/phase-b2-first-five/BURN_NOTICE.md`, `schemas/evaluator-plan-v0.2.schema.json`, and `schemas/evaluator-plan-v0.3.schema.json`.
