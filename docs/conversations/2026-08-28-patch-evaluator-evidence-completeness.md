# Project Conversation — Patch Evaluator Evidence Completeness

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Project-owner instruction

> Continue

Repository context: `https://github.com/MSKazemi/idkmesh`

## Continuation context

This turn began by rechecking the two previously externalized gates:

- canonical node PR #91 / controlled Docker issue #37;
- protected-autonomy issue #35 / ACE safety convergence.

During the recheck:

- PR #98 had merged, so repository-side ACE safety hardening was complete and #35 became purely a GitHub-admin protection/ruleset gate;
- raw GitHub state confirmed frozen node PR #91 remained clean/mergeable, so it was intentionally **not** resynchronized and its exact Docker-acceptance SHA remained unchanged;
- issue #5's patch-verifier lane had moved through stale PR #105 to clean replacement PR #107.

The repository repeatedly changed concurrently during the turn. The collaboration rule remained:

> converge on the active canonical implementation instead of reopening or multiplying superseded PRs.

## Evaluator convergence

PR #105 had become genuinely dirty after its stacked ancestry diverged from merged verifier safety work. An attempt was made to reconcile its existing branch using a normal two-parent merge:

```text
old #105 head
+ then-current main
-> current-main tree with only the 20 reviewed evaluator blobs overlaid
```

No force push was used.

While that reconciliation was in progress, repository activity intentionally closed #105 and opened PR #107 as the clean canonical replacement. #105 was not reopened. PR #107 then passed:

- Evaluator Plan Binding;
- Phase 0 schema check;
- IDKMesh Evolution Loop;

and merged into `main` as:

`2e5512f8ee905f9f21384ebba420dc36160ba37e`

This made the metadata-only unified-diff evaluator backend part of canonical `main`.

## Independent post-merge review

Green deterministic fixtures prove the intended examples, but they do not prove that the parser fails closed on adversarially incomplete evidence.

A source review of the newly merged backend found three concrete gaps.

### Finding A — semantic marker could exist outside a hunk

The original helper treated every patch line beginning with `+` (except `+++`) as an added line.

Therefore a malformed patch such as:

```text
diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
+<!-- patch-evaluator expected -->
```

had:

- independently parsed allowed path `README.md`;
- the verifier-owned required semantic string;
- no actual `@@` hunk.

Because the backend deliberately does not apply/execute candidate patches, its metadata parser itself must distinguish real hunk additions from arbitrary `+` text. Otherwise malformed, non-applicable evidence can satisfy a semantic condition.

### Finding B — required logs could be omitted entirely

The backend verified every log the worker declared, but initialized log integrity to `true` and never required that any log exist.

A worker could therefore omit both `stdout.txt` and `stderr.txt`, submit `logs: []`, and pass the log-integrity portion of independent review.

For the canonical node bundle, this is evidence loss: issue #5 explicitly intends to replay the patch **plus stdout/stderr plus ResultManifest**.

The required log set belongs to evaluator-owned policy, not worker choice.

### Finding C — a declared log without `digest` could crash

ResultManifest v0.1 permits a log object without a `digest` field. The patch verifier indexed `log["digest"]` directly.

That can produce an uncontrolled `KeyError` instead of a schema-valid VerificationResult containing a provenance rejection.

Fail-closed verification should turn incomplete optional worker fields into explicit evidence failures, not implementation crashes.

## Hardening implemented

A fresh branch was created from the exact post-#107 `main`:

`security/patch-evaluator-evidence-completeness`

### 1. Patch verifier version becomes 0.1.1

EvaluatorPlan remains schema version 0.2, but its bound deterministic patch verifier identity now records:

```text
adapter = deterministic-patch-verifier
adapter_version = 0.1.1
```

This keeps runtime provenance explicit for the tightened semantics.

### 2. EvaluatorPlan explicitly requires log types

EvaluatorPlan v0.2 backend policy now contains:

```json
"required_log_types": ["stdout", "stderr"]
```

The list is non-empty, unique, and restricted to ResultManifest log types.

The verifier requires each evaluator-owned required type **exactly once**. Additional declared logs may exist, but all declared logs must still pass digest/size/file checks and locators may not be duplicated.

### 3. Missing digest becomes a controlled rejection

The verifier now uses `log.get("digest")` and records:

```text
log digest is required by evaluator policy
```

rather than raising `KeyError`.

### 4. Unified-diff parsing becomes structural

The v0.1.1 parser supports a conservative textual Git unified-diff subset and fails closed on ambiguity.

It requires:

```text
diff --git <old> <new>
[known Git metadata]
--- <old>
+++ <new>
@@ -old[,count] +new[,count] @@
<hunk lines with balanced declared counts>
```

It also requires the normalized `diff --git` path set to equal the normalized `---`/`+++` path set.

Semantic `+` lines are collected **only while inside a structurally valid hunk**. Hunk old/new line counts are decremented and must finish exactly at zero. Extra or missing hunk lines fail closed.

Binary, mode-only, path-ambiguous, or otherwise unsupported patch shapes are intentionally rejected by this metadata-only v0.1.1 backend rather than guessed at.

## Regression tests

`tests/test_patch_evaluator_safety.py` adds independent cases for:

1. the known-good fixture still passes under verifier 0.1.1;
2. verifier-owned semantic text outside any hunk is rejected;
3. hunk line-count mismatch is rejected;
4. `logs: []` fails because required stdout/stderr evidence is missing;
5. a schema-valid log without `digest` produces a failed VerificationResult instead of a crash;
6. duplicate stdout / missing stderr fails required-log coverage.

The Evaluator Plan Binding workflow now runs these tests in addition to the existing JSON and patch self-tests.

## Safety / compatibility decision

This is intentionally conservative.

The metadata-only backend is not a general Git patch engine. It should not silently expand its accepted grammar faster than it can independently validate the evidence semantics.

If IDKMesh later needs binary patches, mode-only changes, unusual Git quoting, or other diff forms, those should arrive with dedicated fixtures and parser/evaluator evidence rather than being accepted implicitly.

## Critical-path effect

The intended trust chain becomes:

```text
real node bundle
 -> ResultManifest schema/binding
 -> evaluator-owned required artifact + log evidence
 -> strict textual unified-diff structure
 -> independent path/digest/semantic checks
 -> VerificationResult
 -> human/integration decision
```

This follow-up does not change #37's frozen node SHA and does not grant any integration authority.

After this hardening is independently accepted, issue #5 can use the patch backend with a stronger evidence-completeness boundary when the first controlled real node bundle becomes available.
