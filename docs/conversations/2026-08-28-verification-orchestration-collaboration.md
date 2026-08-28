# Conversation Record — Verification and Orchestration Collaboration

**Date:** 2026-08-28

## Project-owner instruction

The project owner asked ChatGPT to continue collaborating autonomously on IDKMesh and improve the public repository as needed, while retaining project work and decisions in the repository.

## Starting point

At the beginning of this continuation, the repository already had a substantial Phase 0 foundation: canonical WorkUnit and ResultManifest contracts, experiment schemas/harnesses, zero-project-spend compute policy, research simulators, community automation, and an open local-node prototype path.

The collaboration focused on turning the trust pipeline into executable, non-duplicative components:

```text
WorkUnit
  -> worker attempt
  -> ResultManifest
  -> independent verification
  -> VerificationResult
  -> coordinator / human / governance decision
```

The governing rules remained:

- proposal is not proof;
- evidence is not final authority;
- workers cannot certify themselves;
- project-paid compute remains zero unless governance explicitly changes the policy;
- runtime authority must remain bounded;
- parallel contributor work must be preserved rather than overwritten.

## 1. Canonical node integration remains gated, not prematurely merged

The older node prototype PR #21 predated the canonical Phase 0 contracts and defined a competing private Work Unit/result protocol.

The useful bounded-worker design was carried into PR #34, which uses the canonical WorkUnit v0.2 and worker ResultManifest v0.1 contracts and keeps node-only settings in a namespaced execution binding.

The node integration was upgraded to enforce current repository policy, including:

- immutable public GitHub source revision;
- source revision matching canonical provenance;
- network `none`;
- no secrets;
- read-only container root;
- dropped Linux capabilities;
- `no-new-privileges`;
- CPU/RAM/PID/time limits;
- path allow/write/forbidden checks;
- low-risk/public/untrusted MVP profile;
- required independent verification;
- `budget.project_spend_usd_max = 0`;
- `paid_fallback_allowed = false`.

Node and Phase 0 CI were green, but real Docker execution is unavailable in the assistant runtime. The repository therefore keeps the merge gate explicit in issue #37: controlled-host positive and negative Docker acceptance evidence is still required.

**Decision:** do not merge PR #34 until #37 is satisfied.

The obsolete PR #21 was closed to remove a competing implementation path. Its separate Gemini advisory-agent idea remains independently tracked in issue #12 rather than coupled to an obsolete worker protocol.

## 2. Duplicate verifier protocol was deliberately retired

A proposed `EvidenceReport v0.1` was developed in PR #42 while verification work was moving quickly.

During that work, a parallel contributor landed the canonical `VerificationResult v0.1`, which already occupied nearly the same protocol boundary: verifier identity, independence, checks, evidence, findings, provenance, and decision support without merge authority.

Maintaining both would have repeated the same protocol-fragmentation mistake avoided for Work Units.

**Decision:** close PR #42 as superseded and strengthen the existing `VerificationResult` contract instead of introducing a second verifier object.

## 3. Verification provenance is now cryptographically bound

PR #60 was merged as:

`3436f1e302763ddd5147129edc82198304bf6404`

It added `experiments/provenance_integrity.py` and made the verification chain bind to exact protocol objects rather than merely matching IDs.

The integrity checks require:

1. worker Work Unit id/version match the exact WorkUnit;
2. worker provenance contains the canonical SHA-256 of the exact WorkUnit JSON;
3. VerificationResult references the exact ResultManifest id;
4. VerificationResult provenance contains the canonical SHA-256 of the exact ResultManifest JSON;
5. VerificationResult provenance contains the same exact WorkUnit digest;
6. worker and verifier source revision agree;
7. observed worker identity is consistent;
8. a verifier claiming independence cannot reuse the worker identity.

A schema-shaped negative fixture with an intentionally wrong ResultManifest digest must fail CI.

This establishes object identity and lineage, not correctness or merge authority.

## 4. A zero-cost executable independent verifier now exists

PR #72 was merged as:

`7c0c04c61cb69923ecbec78f927cfa7a01ed0123`

It added the first executable independent verifier MVP:

- `experiments/local_verifier.py`;
- verifier-owned policy outside candidate workspace;
- isolated good and bad candidate fixtures;
- a bounded verifier WorkUnit;
- executable Phase 0 CI coverage;
- `docs/research/EXECUTABLE_VERIFIER_MVP.md`.

The MVP checks:

### Artifact integrity

Observed candidate bytes are SHA-256 hashed and compared with the worker-declared artifact digest.

### Candidate scope

The isolated candidate root must contain only verifier-policy-approved files.

### Independent acceptance

The candidate is evaluated against verifier-owned deterministic expectations stored outside candidate control.

The important negative fixture is self-consistent:

```text
candidate answer        = 41
worker artifact hash    = correct for those exact bad bytes
candidate scope         = valid
artifact-digest check   = PASS
candidate-scope check   = PASS
independent acceptance  = FAIL
verifier recommendation = reject_candidate
```

This demonstrates that provenance integrity and correctness are distinct.

The verifier executes no candidate code, performs no network/provider call, uses no secrets, spends no project money, and has no merge authority.

Issue #5 remains open because repository-level regression/hidden checks and the first real 5–10 task benchmark cohort are still missing.

## 5. Two-attempt deterministic orchestration kernel landed

Issue #4 required a real control-plane path, but the canonical Docker node remains gated by #37. Rather than bypass that safety gate, the coordinator was implemented first against replayable fixture worker adapters and the real executable verifier.

PR #78 was merged as:

`be79ccffb8b2693fc8fe74a597fd312ddb8f283e`

The coordinator provides:

- exactly two deterministic attempt IDs and ordering;
- a small worker-adapter boundary;
- separate ResultManifest collection for each successful attempt;
- independent verification routing for every collected candidate;
- separate supported/rejected candidate outcomes;
- worker failure isolation;
- preservation of ResultManifest evidence if verification fails;
- narrow verifier/worker exception handling rather than broad exception swallowing;
- deterministic replay records using semantic verification fingerprints instead of volatile timestamps;
- exact WorkUnit, ResultManifest, verifier-policy, and verification provenance digests;
- CLI output restricted to the non-canonical `results/` subtree.

The authority self-test requires all of the following to remain false:

```text
canonical_state_write = false
git_push              = false
merge                 = false
automatic_selection   = false
```

The final synchronized Phase 0 run was `33182293777` and passed:

- schema/fixture validation;
- exact provenance integrity;
- executable independent verifier;
- two-attempt orchestration;
- verification backpressure;
- zero-cost routing;
- local capability discovery/routing;
- deterministic smoke.

Issue #4 remains open because real worker execution, timeout/kill behavior, parallel isolated workspaces, and the 3–5 worker phase are still pending.

## 6. Parallel work was preserved throughout

The repository was changing rapidly during this collaboration. Parallel contributors landed work including:

- WorkUnit v0.2 and trust/resource fields;
- zero-project-spend compute policy;
- local/free compute discovery and routing;
- verification backpressure;
- R1/R2 research and scheduling/churn simulations;
- R2 scale/stress-regime sweeps;
- evaluator-sovereignty and `EvaluatorPlan` work;
- community/evolution automation and documentation.

When branches drifted, synchronization used explicit two-parent merge commits and exact branch blobs rather than force-updating or overwriting parallel work.

One attempted ref update was correctly rejected as non-fast-forward because another collaborator had hardened the orchestrator in parallel. That collaborator change was inspected and preserved before the final merge.

## 7. Small verifier CLI usability bug tracked

Issue #82 was opened because the bare verifier self-test still defaults to:

```text
examples/verifier/good
examples/verifier/bad
```

while the isolated candidate roots are actually:

```text
examples/verifier/good/candidate-root
examples/verifier/bad/candidate-root
```

CI is unaffected because it passes the correct roots explicitly. The issue requests a two-line parser-default repair without weakening isolation or restoring duplicate candidate files.

## Current dependency chain

The practical executable path is now:

```text
canonical WorkUnit v0.2
        |
        v
bounded worker backend (PR #34)
        |
        | requires controlled Docker acceptance #37
        v
worker ResultManifest v0.1
        |
        v
independent verifier / EvaluatorPlan
        |
        v
VerificationResult v0.1
        |
        v
two-attempt coordinator baseline
        |
        v
future selection/integration policy
        |
        v
human/governance-controlled canonical state
```

## Highest-value next steps

1. Obtain independent controlled-host Docker evidence for #37.
2. Merge #34 only after that evidence passes.
3. Add a canonical node worker adapter to the two-attempt coordinator.
4. Run two real isolated worker attempts and route both ResultManifests through independent verification.
5. Add real timeout/kill/error evidence.
6. Add verifier-owned repository regression and hidden/independent acceptance checks.
7. Expand from two real attempts to 3–5 heterogeneous workers.
8. Build the first 5–10 replayable repository task benchmark cohort.
9. Measure verified useful work, human attention, compute, verifier load, communication, and failure correlation rather than raw output volume.

The project should continue to prefer one shared protocol per semantic boundary, explicit evidence, bounded authority, and fail-closed integration over fast but unverifiable agent volume.
