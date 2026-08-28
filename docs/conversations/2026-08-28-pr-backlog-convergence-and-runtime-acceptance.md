# PR backlog convergence, runtime acceptance, and real multi-attempt continuation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner request

Continue IDKMesh development and reduce the large open pull-request backlog by solving, integrating, repairing, or retiring PRs according to evidence rather than leaving parallel branches indefinitely open.

## Triage policy used

The integration pass applied four categories:

1. **merge now** — low-risk/reversible work whose exact head had the relevant green checks;
2. **repair/rebase** — useful work whose semantics were current but whose branch had drifted behind `main`;
3. **keep gated** — runtime/security/governance work that still required an explicit independent or administrative gate;
4. **close as superseded/deferred** — stale branches whose useful design was preserved but whose implementation no longer matched the current architecture or review-capacity priorities.

The pass deliberately did **not** treat author confidence, PR age, or volume as acceptance evidence.

## Backlog result

The open PR queue started this turn at approximately **17 open PRs** and converged to one intentional human-review-gated worker PR after concurrent project integrations were reconciled.

Important integrations during the pass included:

- PR #92 — deterministic temporal verification-backpressure benchmark;
- PR #48 — causal ACE parent-to-descendant lineage evidence;
- PR #106 — refreshed ACE cohort observer, integrated concurrently while old #40 closed;
- PR #68 — refreshed and integrated offline ACE activity-metabolism/shadow controller;
- PR #111 — patch-evaluator evidence-completeness hardening, integrated concurrently;
- PR #99 — refreshed execution target graph / PR-triage planning, integrated concurrently;
- PR #112 — fail-closed ACE Phase-B activation gate;
- PR #113 — first real canonical-node bundle verified end-to-end by the current EvaluatorPlan v0.2 verifier.

Stale/deferred branches closed during the pass included:

- PR #36 — old Repository Homeostasis Engine implementation; preserve the design, rebuild only from current main after the protected-integration prerequisite;
- PR #43 — broad GitHub Reflex Observatory; useful design history, but deferred because narrower evidence sensors now exist and review/integration capacity is the bottleneck.

PR #108 is retained as historical acceptance/evaluator evidence but was not merged after a later revision exposed cross-layer evaluator drift.

## Exact-head runtime acceptance found a real defect

The controlled Docker acceptance path for canonical node PR #91 first tested frozen head:

`d638a2f78e4a89353b98e91052233e365f56f90a`

The positive smoke task reached Docker but failed with a Python `SyntaxError`: the JSON fixture decoded `\n` into literal newlines inside a single-quoted `python -c` payload.

The correct response was to **reject the candidate, repair it, and rerun the gate**, not waive the test.

The fixture was changed to an escape-free `chr(10)` construction and a regression test was added that parses the canonical WorkUnit JSON and compiles the decoded Python payload.

## Final canonical node acceptance evidence

Current evidence-bound PR #91 head:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Exact-head prerequisite CI:

- IDKMesh Node CI `33185901079` — success;
- Phase 0 schema check `33185901058` — success.

Controlled Docker acceptance run:

`33186111350`

Positive evidence:

- worker exited successfully and emitted canonical ResultManifest v0.1;
- exactly `README.md` changed;
- candidate/stdout/stderr digests independently matched observed files;
- no untracked, unpackaged-artifact, path-policy, protected-metadata, output-policy, or runtime-policy violations;
- patch was not truncated;
- configured image was resolved to immutable image/repository-digest evidence;
- network remained disabled;
- root filesystem was read-only;
- Linux capabilities were dropped;
- `no-new-privileges` remained enabled;
- CPU/RAM/PID bounds were applied;
- Docker socket was not mounted;
- worker output remained an unverified candidate with no acceptance/merge authority.

Fail-closed negative matrix:

1. forbidden/out-of-scope tracked-file modification;
2. ignored untracked artifact;
3. task-visible Git-pointer tampering;
4. oversized/truncated candidate patch;
5. absent configured local image;
6. locally retagged image lacking the expected immutable repository digest.

All six negatives failed as intended. Issue #37 was therefore completed for the exact accepted head.

## Exact-head rule

A central operational lesson is now explicit:

> **Acceptance evidence is bound to an exact candidate head. It is never inherited automatically by a changed head.**

During this pass PR #91 moved after earlier green evidence. The runtime matrix was rerun rather than carrying acceptance forward, even when the intervening delta was only test hardening.

## Real node -> independent verifier

A later revision of PR #108 exposed a useful integration failure after evaluator hardening in PR #111:

- the old E2E plan hard-coded patch-verifier adapter version `0.1` while current verifier version was `0.1.1`;
- the old plan omitted newly required `stdout`/`stderr` evidence coverage.

This was treated as **cross-layer contract drift**, not as a reason to weaken the verifier.

PR #113 solved the drift by deriving the real-run EvaluatorPlan from the canonical current v0.2 plan fixture, then replacing only exact WorkUnit/source/semantic bindings.

PR #113 workflow run `33186566651` proved:

```text
exact real node
  -> ResultManifest v0.1 + real patch/log bundle
  -> current EvaluatorPlan v0.2
  -> hardened metadata-only unified-diff verifier v0.1.1
  -> passing VerificationResult v0.1
  -> human integration decision still pending
```

The verifier executed no candidate code and preserved independent verification/evaluator provenance.

## Why PR #91 remains open

PR #91 is technically runtime-accepted on its exact head, but its contract intentionally requires a **separate human/reviewer inspection** before leaving draft or becoming the canonical worker.

The same project actor must not convert its own worker + same-owner automated evidence into independent approval. Therefore PR #91 remains deliberately open/draft until that human gate is satisfied.

## Repository-admin gate still unresolved

`main` is still publicly reported as unprotected. Issue #35 therefore remains a P0 administrative prerequisite before stronger autonomous write/merge authority. Repository files can fail closed around this condition; they cannot substitute for the actual GitHub ruleset/branch-protection setting.

## Current continuation: real two-attempt evidence

After PR backlog convergence and PR #113 single-attempt proof, development moved to issue #4/#16 rather than generating another architecture layer.

Branch:

`integration/real-two-attempt-evidence-v0`

The new experiment:

1. checks out the exact accepted node candidate separately from evaluator control;
2. runs two isolated real attempts from the same WorkUnit/source revision;
3. independently verifies each attempt through the already-merged #113 bridge/current EvaluatorPlan verifier;
4. creates the existing `idkmesh-two-attempt-run` evidence shape;
5. renders that real run through the merged non-selecting Run Evidence Report;
6. verifies the report remains deterministic when replayed from the saved run record;
7. runs a separate fault-isolation scenario where one real node invocation fails before ResultManifest creation while a peer's verified evidence remains preserved;
8. keeps the human decision pending and grants no automatic selection, canonical write, push, or merge authority.

CI, not this note, determines whether that experiment is accepted.

## System lessons

### 1. Integration is scarcer than generation

The repository repeatedly advanced while branches were being reconciled. This is direct operational evidence for the project thesis that parallel generation scales more easily than coherent verification/review/integration.

### 2. Failures are useful evidence

The first real Docker run found a fixture bug; the later node->verifier composition found evaluator-version/evidence drift. Both failures improved the architecture because the gates failed closed.

### 3. Derive integration fixtures from canonical contracts

Hard-coded copies of evolving plan/version requirements drift. Real integration harnesses should derive from canonical versioned fixtures/schemas wherever possible and override only the exact run-specific bindings.

### 4. Preserve negative history

Failed frozen heads and superseded PRs should remain public provenance. Closing or superseding a branch is not erasing the experiment.

## Remaining critical path

1. separate human review of exact-head PR #91;
2. finish and validate the real two-attempt + Evidence Report experiment;
3. extend the proven baseline to a bounded 3–5 attempt run and one heterogeneous adapter only after two-attempt evidence is reliable;
4. build the first 5–10 real-task benchmark cohort;
5. protect `main` through GitHub administration (#35) before stronger autonomy;
6. keep verification/reviewer backpressure as a first-class scaling constraint.
