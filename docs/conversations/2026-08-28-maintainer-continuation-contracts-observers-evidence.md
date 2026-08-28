# Maintainer continuation — contracts, observers, and evidence boundaries

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

This record summarizes the maintainer/integration continuation after the large PR/branch convergence pass. The governing rule throughout was transactional: every accepted merge changes canonical `main`, so earlier eligibility, branch-plan, and exact-head judgments become historical until revalidated.

## 1. Project/domain contract boundary

PR #202 merged the first executable `Core -> DomainPack -> ProjectManifest` boundary.

It added:

- ProjectManifest and DomainPack JSON schemas;
- repository examples;
- a deterministic contract validator;
- focused tests;
- a read-only pinned CI workflow;
- specification and conversation documentation.

The PR was rebuilt on then-current `main` while preserving the ten reviewed implementation blobs exactly, and fresh combined-tree Project Domain Contracts, Phase 0, IDKGraph, randomness, and Evolution checks passed before merge.

Issue #6 is complete.

## 2. Branch Steward convergence

Historical planner PR #205 was not merged twice. Merged #211 had already transplanted its six implementation blobs onto current `main`, so #205 was closed as superseded.

PR #215 added canonical branch-state resnapshotting after every `main` push.

PR #217 then added PR-lifecycle observation. Maintainer review corrected an initial freshness race: `pull_request_target` must never use contributor-head code, and its first design also must not allow a recorded pre-merge `base.sha` scan to supersede a newer `main` push scan.

The corrected observer used trusted canonical code, but real repository activity exposed a second-order control problem: **observation itself consumed too much GitHub API capacity**.

Post-#221 Branch Convergence Audit run `33205890139` passed deterministic tests and then exhausted the GitHub App installation API budget during O(branches) live classification.

PR #222 therefore made the Branch Steward homeostatic:

- PR lifecycle events are cheap **plan invalidations** only;
- they perform no checkout, no repository-code execution, and no GitHub API scan;
- proposed auditor/planner PRs run deterministic tests only;
- full scans run only on `main` push, schedule, or manual dispatch;
- canonical full scans reserve 1500 core requests when observable;
- mid-scan rate exhaustion is captured as `full_scan_complete=false` and `merge_authorized=false`;
- no partial branch plan is emitted;
- non-rate-limit auditor errors still fail normally.

Exact post-merge evidence:

- #222 merge commit: `40fd0a9e08ff05e8fd4208699412024fa41da105`;
- canonical push run `33206373560`, job `98968345231`: SUCCESS under current rate pressure; planner SKIPPED; blocked/no-plan evidence retained;
- artifact `9699810801`, digest `sha256:3abbb0fbd360f57125170d76d281e305a38ca0d780ecef323ee356d6d45d50c4`;
- #222 close lifecycle run `33206373662`, job `98968345923`: only the three-step invalidation job ran; full audit job was SKIPPED.

Issue #127 contains the canonical branch-lifecycle record. No fresh branch counts should be inferred from a blocked/incomplete scan.

## 3. Human review evidence remains human

PR #203 merged a machine-checkable IDKGraph review-session format and validator. It can validate reviewer identity/independence disclosure, anchoring exposure, active review minutes, labels, confidence, evidence and recommendations.

It does **not** create a reviewer, infer semantic labels, approve work, or grant integration authority.

During integration the IDKGraph workflow was also hardened with immutable action SHAs and `persist-credentials: false`.

This distinction matters for the remaining PRs: project automation may validate independent human evidence, but cannot manufacture the independence itself.

## 4. Algorithm Collaboration Fabric

PR #214 merged the Algorithm Collaboration Fabric architecture.

The key non-compensation rule is now canonical:

```text
hard safety / feasibility gate
    cannot be overridden by
soft optimization or collaboration score
```

Correctness verification and integration governance remain separate authority planes. A future collaboration signal may route attention or nominate bounded experiments, but cannot make unsafe or unverified work acceptable.

## 5. Active compute pulse remains externally blocked

Draft PR #213 installs a fail-closed zero-cost GitHub Actions compute mechanism, but issue #35 remains an external governance blocker because public GitHub metadata still reports `main` as unprotected.

Maintainer review found and fixed an activation-ordering flaw: the early workflow gate originally depended only on main protection + repository opt-in, while canonical repository/ref/event validation happened later in the Python adapter. A manual dispatch on a non-main ref could therefore reach dependency installation/repository scripts before final rejection.

The draft branch now requires, **before any active step**:

- repository `MSKazemi/idkmesh`;
- exact ref `refs/heads/main`;
- event in `{schedule, workflow_dispatch}`;
- GitHub reports protected main;
- repository variable `ACTIVE_COMPUTE_PULSE_ENABLED` is exactly `true`;
- protection-query errors fail closed.

The corrected draft head passed Phase 0, IDKGraph and Evolution checks. It remains draft because mechanism readiness is not activation authority.

## 6. Adversarial evidence envelope and finite numeric domain

PR #216 added a sharp count-contamination envelope for scalar reports under at most `f` arbitrary reports.

For sorted observations `x_(1) <= ... <= x_(n)` and `f < n`:

```text
L_f = mean(lowest n-f reports)
U_f = mean(highest n-f reports)
```

Every admissible honest-report subset mean lies in `[L_f, U_f]`; the endpoints are sharp under the count-only assumption.

Maintainer review found a numeric-contract defect before merge: ordinary Python comparisons allow `NaN` to evade bound checks. A concurrent squash merge captured the pre-fix version, so corrective PR #218 was created from actual merged `main` and added finite-domain checks for reports, bounds, threshold and margin plus regression tests.

PR #218 merged as `0504eac6274579dd6daf5b7c32ab405a77d9bc09`.

The envelope remains report-level decision support only; it makes no truth, Sybil-resistance or Byzantine-consensus claim.

## 7. Typed Evidence Aggregation Fabric and strict Boolean correction

PR #220 merged a typed, non-scalar evidence lattice. It deliberately does not multiply provenance, discrimination, correlation, contamination, sequential and drift channels into one confidence number.

Focused post-merge review found a fail-open typing bug: control fields were read using Python truthiness, so values such as `"false"` could behave as true.

Corrective PR #221 made these fields strict required Booleans:

- `hard_guard.payload.passed`;
- `provenance.payload.valid`;
- `discrimination.payload.passed`;
- `drift.payload.detected_change`.

Truthy strings, numeric substitutes and missing fields now fail closed. PR #221 merged as `95660ebd7c72b28a7a81a875b897b685ec0d6d4e` after the dedicated Evidence Aggregation Fabric, randomness and Evolution checks passed.

## 8. Current open integration boundaries

At the end of this record the live PR queue contains three intentionally held paths:

### #219 — canonical self-evolution methodology

Open and review-ready, labeled `help wanted`.

Its own risk section requires **independent review before integration**. No PR review has been submitted. It therefore remains outside `main`; author/project automation does not manufacture the required independent approval.

### #213 — active zero-cost compute pulse

Draft. Mechanically hardened, but external issue #35 (protected `main`) remains unsatisfied. Merge must not be interpreted as activation.

### #159 — canonical local worker

Draft. Exact candidate already has fresh CI and controlled Docker positive + A–E2 evidence, but issue #138 requires a genuinely separate human reviewer. Automation, worker success, byte equality, or verifier evidence are not that reviewer.

## 9. Control-system lesson

This continuation produced a useful repository-level control law:

```text
more observation != more knowledge
```

when observation consumes a shared scarce resource.

The safer rule is:

```text
if state changes but observation capacity is low:
    invalidate old belief
    reduce authority
    wait for enough sensing capacity
else:
    resnapshot
    recompute
```

This is the same homeostatic principle used in ACE and other IDKMesh controllers: resource pressure suppresses amplification rather than being compensated by activity.

## Maintainer invariant

```text
event != action
action != candidate
candidate != verified result
verification != approval
approval != merge
merge != realized improvement
stale observation != current authority
blocked observation != partial permission
```

The repository should continue optimizing verified durable progress per unit of reviewer, maintainer, compute **and observation** cost—not branch, PR, workflow or event volume.