# Continuation: benchmark calibration, worker refresh, and convergence — 2026-08-28

## User direction

Continue improving `https://github.com/MSKazemi/idkmesh`, keep the work public in the repository, and prefer real progress over creating more parallel pull requests.

## PR convergence and artifact minimization

The turn began by refreshing live repository state rather than relying on the previous snapshot.

PR #150 was merged after exact-head checks passed. Its executable change stopped retaining raw issue/PR body snapshots in the repository mathematical-portfolio artifact while preserving derived portfolio evidence. This reduces durable untrusted-text exposure without removing the useful control signal.

The repository remains explicitly constrained by its external integration state: a fresh `main` branch read still reported GitHub protection disabled, so no stronger autonomous write/merge authority was justified.

## Phase B2 benchmark discovery and capability boundary

The five-task Phase B2 cohort was already defined and frozen. Its WorkUnits are goal-level coding tasks, while the accepted `idkmesh-node` worker demonstrated safe execution of an explicit container command. That distinction matters:

```text
idkmesh-node = bounded execution substrate
not          = goal-to-code reasoning agent
```

The coordinator already exposes a worker-adapter boundary, so no new task protocol was needed.

A draft zero-secret open-weight producer probe (#161) was briefly prepared to test goal-level candidate generation on a standard public GitHub runner. The model would have seen only the frozen objective and frozen allowed-file text, with network-off/read-only inference and independent verification afterward.

Before that result could be interpreted, the original cohort produced a more important scientific result and was burned.

## Successful benchmark burn

A real solution for original Task 001 exposed a pre-outcome evaluator mismatch:

- frozen EvaluatorPlan v0.2 used a semantic fragment in `required_added_text`;
- deterministic patch verifier v0.1.1 correctly interpreted that field as exact complete-added-line membership;
- the valid solution contained the fragment inside a longer line and was rejected by the frozen predicate.

The repository preserved the benchmark freeze rather than changing the meaning after observing the outcome. Draft #161 was therefore closed without claiming benchmark evidence.

## Versioned evaluator semantics

Issue #157 then drove explicit versioning rather than reinterpretation.

PR #164 merged:

- v0.2 / verifier 0.1.1 = exact added-line equality;
- v0.3 / verifier 0.2.0 = added-line substring presence.

Later adversarial calibration showed that presence-only substring semantics are Goodhartable: an inert added-line mention can satisfy the lexical predicate while leaving the unsafe mechanism intact.

PR #171 therefore became the canonical next version and merged one implementation path:

- v0.4 / verifier 0.3.0 = required added **and removed** substring transition evidence;
- canonical implementation: `experiments/transition_patch_verifier.py` through `experiments/evaluator_plan_runner.py`;
- v0.2 and v0.3 historical meanings remain unchanged;
- metadata-only verification still executes no candidate code;
- v0.4 is explicitly a static transition proxy, not behavioral proof.

## Calibration evidence from closed #170

PR #170 originally attempted both a second v0.4 implementation and Task-001 behavioral/adversarial calibration. It was correctly closed without merge after #171 became canonical, because IDKMesh should not maintain two verifier stacks.

Its branch later advanced and produced useful successful calibration evidence on exact head:

`67e4af4716584a0da051c9a400951a35e8f153b0`

Dedicated calibration run:

- workflow `33194220134` — success;
- job `98927117312` — success;
- `calibration_passed: true`;
- evaluator plan digest `sha256:903e196df4e275ed96978eb3e3b264d3e616df45ddf9298c32167b39816604db`;
- verifier adapter version `0.3.0`.

Straightforward replacement:

- metadata verification: passed;
- recommendation: `accept_candidate`;
- behavioral path matrix: all absolute/traversal paths rejected as unsafe.

Inert decoy:

- metadata verification: failed;
- recommendation: `reject_candidate`;
- behavioral path matrix: vulnerable absolute/traversal paths still accepted.

The evidence is useful, but #170 must remain closed because its verifier implementation diverges from canonical #171.

## Canonical calibration extraction

The selected convergence action is therefore to extract **only** #170's Task-001 calibration surface onto current `main` and call #171's canonical transition verifier.

The calibration-only follow-up must contain no second:

- EvaluatorPlan v0.4 schema;
- evaluator-plan runner;
- transition verifier implementation.

It reuses the proven task-specific calibration harness and plan, verifies the burned cohort control state, checks out exact frozen source `9c53bb4069a5db1c0688dbbe7a8f028540cbf7c2`, reruns #171's version-boundary tests, and requires the same straightforward/decoy metadata+behavior matrix.

This preserves one implementation per responsibility while converting the successful #170 result into reproducible evidence for the canonical verifier.

## Worker refresh convergence

Historical worker PR #91 was closed as superseded by current-main replacement PR #159. The 14 worker implementation blobs are byte-identical, but evidence was deliberately re-earned on the replacement head rather than transferred by assumption.

PR #159 exact candidate:

`61cafa86f7e0e86343d73182862e3cead1080ab9`

Fresh CI is green, and candidate-bound evidence PR #169 ran the full controlled Docker positive/negative matrix on that exact head:

- run `33193838388` — success;
- job `98925820770` — success;
- `all_acceptance_checks_passed: true`;
- fail-closed negative A-E2 passed;
- `worker_acceptance_authority: false`.

PR #169 was closed without merge after recording the evidence on #159.

The only legitimate remaining gate for #159 is a genuinely separate human/reviewer inspection tracked by #138. Same-owner automation, green CI, byte identity, and the runtime harness are evidence but not independent approval.

## Current operating rule

The turn reinforced a useful self-evolution rule:

```text
calibration failure > schedule pressure
canonical convergence > duplicate implementation
historical evidence > silent reinterpretation
behavioral evidence > lexical proxy when available
independent human review > same-owner automated confidence
```

Do not freeze another scored Phase B2 successor merely because a lexical/static evaluator is available. First preserve the calibrated canonical evaluator boundary; then define any successor cohort under a fresh pre-outcome identity/digest with no observed outcomes and with already-solved Task 001 treated as calibration, not held-out evidence.
