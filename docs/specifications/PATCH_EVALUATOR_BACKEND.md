# Bound Unified-Diff Evaluator Backend

Status: experimental Phase B1  
Tracker: #5  
Product milestone: #16

## Purpose

IDKMesh's first real local node emits a repository candidate bundle rather than a JSON answer fixture:

```text
changes.patch
stdout.txt
stderr.txt
result-manifest.json
```

The candidate patch is still an **untrusted worker claim**. The verifier must independently reconstruct evidence from the bytes in that bundle and must not accept the node's own `changed_paths`, policy counters, or success status as proof.

This backend extends the existing canonical verification chain:

```text
WorkUnit
 -> ResultManifest
 -> EvaluatorPlan
 -> local_verifier backend
 -> VerificationResult
 -> human/integration decision
```

It does **not** create a second verifier package or a second VerificationResult protocol.

## EvaluatorPlan v0.2

`schemas/evaluator-plan-v0.2.schema.json` defines the first explicit non-JSON evaluator backend.

The plan remains:

- metadata-only;
- verifier-owned;
- bound to one exact WorkUnit id/version/digest;
- bound to one exact source revision;
- exact about the required validator IDs it claims to implement;
- outside candidate control;
- unable to write generated evidence into canonical tracked repository state.

The v0.2 backend is:

```text
backend.type = unified_diff
verifier.adapter = deterministic-patch-verifier
```

v0.1 remains the deterministic exact-JSON evaluator; it is not reinterpreted or overloaded with fake patch fields.

## WorkUnit authority

Patch-path authority comes from the WorkUnit, not the worker or EvaluatorPlan:

- `constraints.allowed_paths`;
- `constraints.forbidden_paths`;
- `permissions.filesystem_write`.

For the first fixture this is intentionally equivalent to the canonical node smoke boundary:

```text
allowed:   README.md
forbidden: .github/**, SECURITY.md
write:     README.md
```

The evaluator independently parses the unified diff and checks every observed old/new path against those rules.

## Verifier-owned semantic expectation

The first deterministic semantic check is deliberately narrow: the EvaluatorPlan specifies one or more exact lines that must appear as added hunk content.

This is not a universal semantic code reviewer. It is a verifier-owned acceptance fixture proving that:

- a worker-success candidate can still be rejected;
- a scope-valid candidate can still fail correctness;
- candidate code cannot rewrite the evaluator's expected result.

The canonical node integration can bind the same backend to the harmless README smoke marker after #34/#37 is synchronized and accepted.

## Independent observations

The backend independently reconstructs:

1. **ResultManifest binding**
   - schema-valid ResultManifest;
   - exact WorkUnit id/version/digest;
   - requested validators cover the WorkUnit-required validators.
2. **Candidate patch integrity**
   - candidate locator stays inside the candidate root;
   - regular non-symlink file;
   - SHA-256 recomputed from bytes;
   - verifier-owned maximum size enforced.
3. **Declared log integrity**
   - each declared log locator stays inside the candidate root;
   - regular non-symlink file;
   - SHA-256 independently recomputed;
   - verifier-owned maximum log size enforced.
4. **Patch scope**
   - old and new paths are independently parsed from `diff --git`, `---`, and `+++` headers;
   - `/dev/null` is treated as absence of one side, not a repository path;
   - absolute and parent-traversal paths fail closed;
   - every observed repository path is checked against WorkUnit path authority.
5. **Verifier-owned semantics**
   - added hunk lines are reconstructed from `+` lines excluding file headers;
   - all required added lines from the bound EvaluatorPlan must be present.
6. **Worker execution state**
   - a positive recommendation requires the ResultManifest status to be `succeeded`;
   - worker success alone is never sufficient.

The evaluator deliberately ignores worker extensions such as `changed_paths` or `policy_violation_count` as acceptance evidence. Those values may be useful diagnostics, but the verifier recomputes the relevant facts.

## Required validator alignment

For the first patch WorkUnit, the required validators are:

```text
result-manifest-schema
independent-review
```

The patch backend emits those **exact IDs** as its required VerificationResult checks.

`result-manifest-schema` covers the schema-valid, exact-bound worker claim.

`independent-review` aggregates the independently observed artifact/log integrity, patch scope, verifier-owned semantic condition, and conservative worker-status gate.

The EvaluatorPlan runner rejects a backend when its implemented validator set does not exactly match the WorkUnit-required set.

## Negative fixtures

`patch-self-test` uses self-consistent worker ResultManifests so the independent evaluator—not a malformed worker claim—creates the distinction:

1. **good**
   - honest patch digest;
   - allowed README-only scope;
   - expected verifier-owned added line;
   - expected result: support.
2. **wrong semantic**
   - honest patch digest;
   - allowed README-only scope;
   - wrong added line;
   - expected result: reject for correctness, not scope.
3. **forbidden path**
   - honest patch digest;
   - expected semantic line present;
   - touches `SECURITY.md`;
   - expected result: reject for scope.
4. **forged digest**
   - good candidate bytes;
   - altered worker-declared patch digest;
   - expected result: reject for provenance.
5. **binding drift**
   - correct candidate;
   - wrong bound WorkUnit digest;
   - expected result: fail closed before positive decision support.

## Safety boundary

The patch evaluator does not:

- apply the patch;
- execute candidate code;
- run worker-supplied commands;
- use network services or secrets;
- use project-paid compute;
- infer trust from worker success;
- select or merge a candidate;
- write generated verification evidence outside ignored root `results/`.

A future test/static-analysis/sandbox backend may execute trusted verifier-owned tools against a controlled materialization, but that requires a separately reviewed execution boundary.

## Next integration

After this metadata-only backend is green and reviewed:

1. bind EvaluatorPlan v0.2 to the synchronized canonical node smoke WorkUnit from #34;
2. run controlled Docker acceptance #37 to produce a real node bundle;
3. replay that exact bundle through the patch evaluator;
4. preserve ResultManifest + EvaluatorPlan + VerificationResult in the two-attempt orchestration record;
5. then create the first 5–10 task repository benchmark cohort.

Do not expand to a universal patch evaluator before one real node candidate is replayable end to end.
