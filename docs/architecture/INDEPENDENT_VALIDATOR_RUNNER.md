# Independent Validator Runner

## Status

Implemented as the first safe local verifier slice for issue #5.

Primary executable:

- `experiments/local_validator.py`

Contracts:

- `schemas/work-unit-v0.2.schema.json`
- `schemas/result-manifest-v0.1.schema.json`
- `schemas/evaluator-plan-v0.1.schema.json`
- `schemas/verification-result-v0.1.schema.json`

## Why this layer exists

IDKMesh cannot trust a worker merely because the worker says a task succeeded. The verifier must independently inspect the candidate against a trusted policy and preserve machine-readable evidence.

The first executable trust path is now:

```text
trusted WorkUnit
      |
      v
untrusted worker attempt
      |
      v
ResultManifest + candidate workspace
      |
      |  evaluator control remains outside candidate workspace
      v
trusted EvaluatorPlan
      |
      v
local independent validator
      |
      v
VerificationResult + evidence bundle
      |
      v
later integration/human policy
```

A `VerificationResult` is decision support. It does not grant merge authority.

## Architectural idea: Evaluator Sovereignty

The worker and verifier should not share control over the evaluator.

IDKMesh therefore separates four objects:

1. **WorkUnit** — the public work/acceptance contract: scope, permissions, required validators, evidence requirements, risk, budget, and provenance.
2. **ResultManifest** — the worker's untrusted self-report and candidate artifact declarations.
3. **EvaluatorPlan** — verifier-owned implementation/binding for independent checks. It may be public or hidden from the worker.
4. **VerificationResult** — verifier evidence and recommendation, which remains separate from integration authority.

The EvaluatorPlan is cryptographically bound to the exact WorkUnit digest and expected source revision. When independent verification is required, the local runner refuses an evaluator plan located inside the candidate workspace.

This is intentionally analogous to keeping a test oracle outside the program under test: the candidate may change its own files, but it must not be able to rewrite the rule that decides whether those changes are acceptable.

## v0.1 safety boundary

The current local validator is deliberately **metadata-only**.

It performs deterministic checks but does **not** execute candidate-controlled code, scripts, tests, package hooks, or WorkUnit commands on the host.

Built-in checks are:

- input JSON Schema validation;
- candidate-vs-baseline file snapshot comparison;
- write-scope / forbidden-path enforcement;
- candidate symlink rejection;
- produced-artifact SHA-256 verification;
- WorkUnit digest and source-revision provenance validation;
- verification-request completeness and evaluator coverage.

This lets IDKMesh establish a real independent verifier loop without prematurely creating a remote-code-execution surface.

## Deterministic scope algorithm

Let:

- `B(p)` be the trusted baseline digest of path `p`;
- `C(p)` be the candidate digest of path `p`;
- `Delta` be every added, modified, or deleted path between the complete baseline and candidate snapshots.

Then:

```text
Delta = symmetric_file_difference(B, C)
```

For each changed path `p`:

```text
Authorized(p) =
    InAllowedPaths(p)
    AND InFilesystemWriteAuthority(p)
    AND NOT InForbiddenPaths(p)
```

The deterministic scope check passes iff:

```text
ScopePass = for every p in Delta: Authorized(p)
```

This matters because a candidate may omit an unauthorized file from its own ResultManifest. The verifier therefore derives the change set from the workspace snapshot rather than trusting the worker's declared artifact list.

## Artifact integrity algorithm

For every produced artifact that the ResultManifest declares:

```text
ObservedDigest = SHA256(candidate_root / artifact.locator)
ArtifactPass = ObservedDigest == ResultManifest.artifact.digest
```

Candidate-local path resolution rejects traversal outside the candidate root.

## Provenance binding

The verifier recomputes the canonical WorkUnit digest:

```text
WorkUnitDigest = SHA256(canonical_json(WorkUnit))
```

The following must agree:

```text
EvaluatorPlan.binding.work_unit_digest
ResultManifest.provenance.work_unit_digest
recomputed WorkUnitDigest
```

When configured, the ResultManifest source revision must also equal the evaluator's trusted expected revision.

## Verification coverage

The worker's requested validator list is not authoritative. The WorkUnit is.

The runner checks that:

- every required WorkUnit validator is covered by the EvaluatorPlan;
- the worker did not silently omit required validators from its verification request;
- requested evidence artifact IDs actually exist in the ResultManifest;
- every required verifier-plan check also affects the overall decision.

A coverage gap yields insufficient or failed evidence rather than silently accepting the candidate.

## Result bundle

A verifier run writes outside the candidate workspace:

```text
<output-dir>/
  verification-result.json
  evidence/
    <check>.json
    ...
```

Each evidence file is SHA-256 hashed and referenced from `VerificationResult.checks[].evidence_ids`.

The result records:

- exact WorkUnit / ResultManifest / attempt binding;
- verifier identity and version;
- independence/correlation metadata;
- deterministic check status;
- findings;
- resource use;
- candidate change count;
- WorkUnit, ResultManifest, and evaluator-plan digests;
- a recommendation.

## CLI

Run the safety suite:

```bash
python experiments/local_validator.py self-test
```

Create a trusted baseline snapshot from a pristine worktree:

```bash
python experiments/local_validator.py snapshot \
  --root /path/to/pristine-worktree \
  --output /trusted/control/baseline.json
```

Run metadata-only verification:

```bash
python experiments/local_validator.py verify \
  --work-unit /trusted/control/work-unit.json \
  --result-manifest /trusted/control/result-manifest.json \
  --evaluator-plan /trusted/control/evaluator-plan.json \
  --candidate-root /isolated/candidate-worktree \
  --output-dir /trusted/results/run-001
```

The WorkUnit, ResultManifest, and EvaluatorPlan should be copied/read from trusted coordinator/verifier storage. The candidate root is treated as untrusted.

## Self-test cases

CI executes deterministic tests proving that:

1. a candidate whose changes stay inside declared write authority and whose artifacts/provenance match can pass;
2. a worker cannot hide a forbidden-path mutation by omitting it from ResultManifest;
3. artifact tampering after ResultManifest creation is detected by SHA-256 mismatch;
4. verifier control data inside the candidate workspace is rejected.

## Hidden tests: next safe extension

Issue #5 still requires hidden/regression/static/security checks. They should not be added by simply executing arbitrary `validators[].command` entries on the host.

The next execution backend should instead use a disposable sandbox with this boundary:

```text
trusted evaluator/test bundle (read-only, outside candidate control)
             +
      candidate workspace (untrusted)
             |
             v
       disposable sandbox
             |
             v
 normalized evidence only
```

Candidate network access, secrets, filesystem mounts, CPU/RAM/time, and process capabilities must be bounded by policy. The hidden evaluator must not be writable by the worker.

A future `EvaluatorPlan` version can add sandboxed executable checks after that execution boundary is implemented and threat-modeled.

## What this solves now

This slice materially advances issue #5 by implementing:

- an actual independent validator runner;
- a separate verifier-controlled evaluator contract;
- deterministic unauthorized file/path checks;
- candidate artifact hash verification;
- provenance/source-revision checks;
- machine-readable VerificationResult/evidence generation;
- reproducible baseline snapshots;
- a fail-closed evaluator-control boundary.

## What remains for issue #5

Still open:

- sandboxed hidden/regression test execution;
- lint/type/static analysis backends;
- security/fuzz/property backends;
- stronger runtime resource measurement in sandbox;
- fixed-snapshot repository benchmark tasks;
- the initial 20-50 task benchmark corpus for Experiment #2;
- cross-verifier disagreement aggregation.

The next implementation should add a **sandbox execution backend**, not weaken the metadata-only runner's host-safety invariant.
