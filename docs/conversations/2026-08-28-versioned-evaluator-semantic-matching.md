# Conversation record — versioned evaluator semantic matching

Date: 2026-08-28

Repository: `MSKazemi/idkmesh`

## User direction

The user asked IDKMesh to continue development of the public repository.

## Context inherited from the immediately preceding work

The first frozen Phase B2 five-task pilot was burned after task 001 exposed an evaluator-contract mismatch:

- task 001 was solved in PR #153, merge `c04ae627a7ff6b0bd700aae36afdb60f3cb8af97`;
- the frozen plans encoded semantic fragments in `required_added_text`;
- deterministic patch verifier v0.1.1 treats `required_added_text` as exact full added-line requirements;
- PR #160 therefore preserved the pilot as burned diagnostic evidence rather than changing evaluator meaning after the outcome;
- the original cohort definition digest remains `sha256:4fdec8a2768e32dc223b218ed70aec3a67aefcd87c64b72c5675c9921a4eab5c`;
- issue #157 was opened as the P0 version-boundary task.

## Versioning decision

Historical semantics stay immutable:

```text
EvaluatorPlan v0.2
 -> deterministic-patch-verifier 0.1.1
 -> required_added_text
 -> exact complete added-line equality
```

New substring semantics get new versions:

```text
EvaluatorPlan v0.3
 -> deterministic-patch-verifier 0.2.0
 -> required_added_substrings
 -> case-sensitive contiguous containment within one validated-hunk added line
```

No regex, fuzzy matching, or cross-line matching is introduced.

## Implementation

Branch:

`fix/evaluator-semantic-matching-v0.3`

PR:

`#164 — Version EvaluatorPlan substring semantics as v0.3`

Changes:

1. `schemas/evaluator-plan-v0.3.schema.json`
   - new schema version;
   - verifier adapter version fixed to `0.2.0`;
   - explicit `required_added_substrings` field;
   - schema description defines case-sensitive, contiguous, single-added-line semantics.

2. `experiments/substring_patch_verifier.py`
   - new versioned semantic adapter;
   - leaves `experiments/local_verifier.py` v0.1.1 unchanged;
   - reuses the legacy hardened unified-diff/provenance/log/scope core;
   - independently maps each required substring to a concrete parsed added line;
   - adds `added-substring-semantic-observation` evidence;
   - emits verifier adapter version `0.2.0`;
   - records semantic mode `added_line_substring_all` and legacy core version `0.1.1`.

3. `experiments/evaluator_plan_runner.py`
   - canonical runner now recognizes EvaluatorPlan v0.3;
   - v0.2 continues routing to the unchanged exact-line verifier;
   - v0.3 routes to the substring adapter;
   - plan/result verifier identity and exact plan digest remain fail-closed bindings;
   - runner version advances to `0.3`.

4. Contrast fixtures
   - v0.2 plan requires fragment `patch-evaluator expected` as exact text;
   - v0.3 plan requires the same fragment as a substring;
   - both evaluate the same existing patch that adds `<!-- patch-evaluator expected -->`.

5. `semantic-version-self-test`
   - v0.2 must reject the fragment contrast;
   - v0.3 must support it;
   - both must observe the exact same candidate-patch digest;
   - v0.2 result must report verifier `0.1.1`;
   - v0.3 result must report verifier `0.2.0`;
   - both must bind their exact EvaluatorPlan canonical digests;
   - v0.3 must include explicit substring semantic evidence.

6. Phase 0 CI
   - keeps the existing v0.2 patch self-test;
   - adds compile + semantic-version self-test;
   - security note states that neither version executes candidate code.

7. `docs/specifications/EVALUATOR_PLAN_V0_3_SEMANTIC_MATCHING.md`
   - durable version matrix, formal semantics, provenance, migration, successor-cohort rule, and authority boundary.

## Exact-head evidence before this archive commit

PR head `a070f9d2e85d9842147e8fca99e749d3fb3b7c72` passed:

- Phase 0 schema check run `33193279824` — success;
- Evaluator plan binding run `33193279855` — success;
- IDKMesh Evolution Loop run `33193279823` — success.

Within Phase 0, both critical steps passed:

- `Preserve EvaluatorPlan v0.2 patch semantics`;
- `Prove EvaluatorPlan semantic version boundary`.

The second test proves, using the same candidate patch and same semantic fragment:

```text
v0.2 / verifier 0.1.1 -> reject
v0.3 / verifier 0.2.0 -> support
```

This is evidence that the old meaning was preserved rather than silently changed.

## Successor benchmark rule

A successor Phase B2 cohort may be frozen only after this version boundary is merged and green.

The burned v1 pilot remains burned. Its WorkUnits, EvaluatorPlans, source SHA, and definition digest must not be rewritten.

Task 001 is already known and may not be represented as untouched held-out evidence in a successor.

## Authority boundary

No part of this work grants:

- automatic candidate selection;
- canonical-state write authority;
- push authority;
- pull-request approval;
- merge authority;
- paid-compute/spending authority.

Candidate code is not executed by the metadata-only patch verifier. Verification remains evidence for later human/governance integration.
