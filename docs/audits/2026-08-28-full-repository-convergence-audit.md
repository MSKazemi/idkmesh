# Full Repository Convergence Audit — 2026-08-28

Status: current-state audit after rapid integration of the Verified Swarm Runner, ACE safety/evidence stack, and mathematical foundations.

## Executive conclusion

IDKMesh is no longer bottlenecked by lack of theory or by a large PR queue. The repository has converged to one open pull request, PR #91, containing the canonical real local worker. Its exact head has green Node/Phase-0 CI and completed controlled-Docker positive/negative acceptance. A fresh real node bundle has also been replayed through the merged EvaluatorPlan metadata-only verifier path. The remaining blocker for #91 is intentionally a separate human/reviewer inspection of the exact-head runtime evidence.

The highest-value sequence is now:

```text
1. protect main in GitHub settings
2. obtain independent human review of PR #91 exact head
3. integrate PR #91 unchanged
4. connect the real node behind the merged two-attempt orchestrator
5. render/replay that real multi-attempt run through the merged Evidence Report layer
6. freeze 5–10 real repository benchmark tasks
7. measure diversity, verifier correlation, backpressure, cost, and human attention on real evidence
8. only then increase autonomy, fan-out, federation, or community reproduction
```

## 1. Repository integration state

### Open PR queue

Only PR #91 remains open at this audit.

PR #91 exact head:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Observed state:

- mergeable;
- draft;
- exact-head Node CI successful;
- exact-head Phase 0 successful;
- controlled Docker acceptance complete for positive case and negative A–E2 matrix;
- worker has no independent acceptance or merge authority;
- remaining gate is a separate human/reviewer inspection.

The project should not manufacture independence by treating the same repository owner, proposing automation, or acceptance harness as a separate reviewer.

### Recently converged foundations

The following previously competing/stale paths have been replaced by clean current-main convergence PRs and integrated:

- verifier output-authority boundary;
- EvaluatorPlan v0.2 metadata-only unified-diff backend;
- patch-evidence completeness hardening;
- non-selecting Evidence Report/replay;
- two-attempt deterministic orchestrator;
- controlled Docker acceptance harness/evidence;
- real node -> independent verifier E2E evidence;
- ACE workflow security convergence;
- recoverable live-open-work capacity model;
- ACE cohort observation, lineage, and shadow controller;
- fail-closed Phase-B activation gate;
- current execution target graph.

Old superseded PRs should remain public provenance rather than being revived.

## 2. Security and governance

### P0 blocker: main remains unprotected

Public branch metadata still reports:

```text
protected: false
protection.enabled: false
required_status_checks.enforcement_level: off
```

This is now the largest governance gap.

Repository-side safeguards are substantially stronger than the external integration boundary. No additional autonomous repository-write authority should be granted until GitHub rulesets/branch protection actually enforce the project invariants.

Minimum external controls remain:

- PR-based integration for protected structural/code/governance changes;
- stable required checks;
- block force pushes and deletion under normal operation;
- independent review where risk policy requires it;
- narrow auditable bypass/recovery capability;
- no automation able to propose, approve, and merge the same protected change alone.

ACE should remain fail-closed while this is unresolved.

## 3. Product path: Verified Swarm Runner

### Already demonstrated

The repository has executable evidence for:

```text
canonical WorkUnit
 -> real Docker-isolated node execution
 -> ResultManifest + patch/log evidence
 -> verifier-owned EvaluatorPlan
 -> metadata-only independent patch/log verification
 -> canonical VerificationResult
 -> explicit human integration decision remains required
```

This is a meaningful milestone: worker execution and independent verification now exist as separate trust boundaries on real runtime output.

### Remaining v0.1 product proof

The missing end-to-end demonstration is now narrower:

```text
one WorkUnit
 -> two isolated real node attempts
 -> independent verification per completed candidate
 -> preserve worker/verifier failures and disagreements
 -> combined non-selecting Evidence Report
 -> deterministic/semantic replay from saved metadata
 -> human decision outside worker/verifier authority
```

Do this before adding sophisticated routing or a large benchmark inventory.

### Heterogeneity gate

After the two-real-attempt path is stable, add one deliberately simple second real adapter. The adapter should prove coordinator neutrality, not maximize model sophistication.

Only then prioritize mini-SWE-agent/OpenHands/A2A/MCP integrations as product-critical work.

## 4. Verification and evidence

The verification architecture is currently one of the strongest repository areas.

Preserve these invariants:

- worker success is not acceptance;
- verifier recommendation is not merge authority;
- ResultManifest and VerificationResult stay distinct;
- evaluator control stays outside candidate control;
- candidate patch/log digests are recomputed independently;
- required evidence is evaluator-owned rather than worker-optional;
- unsupported/ambiguous patch forms fail closed;
- negative outcomes remain first-class evidence;
- verification capacity constrains generation fan-out.

### Next empirical step

The verification-backpressure and correlated-evidence work is mainly synthetic today. Once real multi-attempt runs exist, collect measured:

- verification wall time;
- verifier compute;
- artifact sizes;
- failures by class;
- worker/verifier error correlation;
- queue latency;
- human review time;
- escaped defects/regressions where observable.

Use those measurements to replace hand-authored controller priors.

## 5. Mathematical foundation

The mathematical foundation is broad enough for the current phase. Do not add formulas merely for completeness.

Operationalize the existing model in this order:

1. machine-readable Goal–Task–Evidence graph;
2. repository observables with confidence/uncertainty;
3. measured queueing/review concentration/contributor recurrence;
4. correlated-verifier effective evidence size;
5. causal experiments for community interventions;
6. information-gain-aware next-task selection;
7. constrained multi-objective policy updates.

Every promoted metric should specify:

- assumptions;
- observable data;
- uncertainty;
- prediction;
- baseline;
- Goodhart/failure modes;
- human/security constraints;
- falsification path.

## 6. ACE/community system

The ACE stack is now structurally coherent:

```text
GitHub activity
 -> trusted cohort/exposure observation
 -> explicit causal lineage receipts
 -> recoverable live review-capacity measurement
 -> shadow generational controller
 -> external conjunctive activation gate
 -> bounded future actuator only if all evidence/authority gates pass
```

Current interpretation should remain conservative:

```text
capacity recovered != permission to act
activity != verified descendant
infrastructure merged != community reproduced
repository rules != GitHub-enforced protection
```

Do not increase Cohort-2 or Phase-B write activity merely because open-work pressure falls. Require external-participant and verified-descendant evidence.

## 7. Repository structure and documentation

The root remains documentation-heavy. This is a real navigation cost, but it is not the highest-value blocker while the first real product loop is one integration step from completion.

Recommended sequence:

- finish real runner integration first;
- run deterministic repository observatory/homeostasis checks;
- migrate only one coherent document group at a time;
- repair links and compare before/after navigation/structural metrics;
- avoid a bulk taxonomy rewrite.

`CONSTITUTION.md`, governance, human-flourishing constraints, mathematical foundations, evolution model, and project goals should remain easy to discover from the root/README even if their canonical bodies later move under `docs/`.

## 8. Issue hygiene

Open issues should increasingly be treated as one of four classes:

1. **blocking product/security gate** — directly on v0.1 or integration safety path;
2. **measured research experiment** — has falsifiable hypothesis and executable evidence plan;
3. **community contribution surface** — bounded, independently claimable, low integration cost;
4. **future/backlog** — valuable but explicitly not current priority.

Avoid opening new architecture/research issues unless they either unblock the real runner, create measurable evidence, or provide a high-quality community contribution surface.

Close/supersede issues when their canonical deliverable has landed rather than letting historical checklist language make the tracker appear less converged than the repository is.

## 9. Immediate priority table

### P0 — external/admin

**Protect `main`.** This cannot be replaced by repository documentation or workflows.

### P0 — review/integration

**Independent human review of PR #91 exact head.** If accepted and unchanged, mark ready and merge.

### P0 — product

**Real two-attempt orchestration + independent verification + Evidence Report/replay.** This is the shortest path to an honest v0.1 claim.

### P1 — benchmark

Freeze **5–10 real tasks** only after the complete real multi-attempt loop works.

### P1 — metrics

Replace synthetic/hand-authored priors with measured runtime, verification, queue, and human-attention data.

### P1 — community

Obtain the first external verified descendant and measure the full contribution funnel before increasing reproduction.

### P2

Heterogeneous adapters, official A2A/MCP conformance, larger R1/R2/R3/R4 experiments, structural migrations, federation, stronger autonomous routing.

## 10. Definition of the next successful iteration

The next important repository iteration is not another formula, workflow, or simulation.

It is:

> A separately reviewed canonical real node lands, two real isolated attempts run through the existing orchestrator, each completed candidate receives independent verification, the combined run is rendered/replayed through the Evidence Report layer, and the human integration decision remains external.

That iteration directly improves product quality, verification evidence, architecture convergence, contributor clarity, and the credibility of the IDKMesh thesis at the same time.
