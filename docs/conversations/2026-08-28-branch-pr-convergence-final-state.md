# Final state: professional PR + branch convergence pass

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

Continue maintaining IDKMesh professionally and treat **branches as part of the integration graph**, not only pull requests.

## Resulting integration posture

At the end of this maintenance pass, a fresh open-PR search showed one intentional integration candidate:

- **PR #159** — canonical local-node replacement, draft.

Its exact candidate remains:

`61cafa86f7e0e86343d73182862e3cead1080ab9`

Current raw GitHub PR state reports it clean/rebaseable. It already has fresh exact-head CI and fresh controlled Docker positive + A-E2 evidence. No separate human review has been submitted yet, so it remains draft under issue #138. Automation must not convert its own evidence into approval.

## Final branch audit snapshot

The canonical read-only branch-convergence auditor completed successfully:

- workflow run `33187644986`;
- job `98935743278`;
- artifact `9696098894`;
- artifact digest `sha256:deb4355beed74d3863676b18e91a7469ea4c2268c1d247700f3b7120805dcd48`.

Point-in-time state:

```text
branches observed                      147
cleanup-eligible                        81
direct branch merges allowed             0

canonical                                1
active draft PR                          1
active review PR                         1
integrated via merged PR                73
orphan / no unique commits               8
orphan diverged                          8
post-merge branch moved                  6
closed-unmerged evidence branch          9
closed-unmerged unique work              40
```

The one review PR in the audit snapshot was #191. It merged immediately afterward; its exact source head had green emergence-sim, randomness-lab, and Evolution CI. A fresh PR search after that merge returned only draft #159.

Issue #127 is the canonical branch-lifecycle ledger. The connected GitHub surface used in this pass has no delete-ref operation, so cleanup-safe refs were classified but not force-moved or fake-deleted.

## Important convergence actions in this pass

### Canonical worker branch

- historical #91 closed as stale integration ancestry while preserving its exact evidence;
- #159 rebuilt the same worker blobs on modern `main`;
- candidate-bound #169 reran the full controlled Docker matrix on #159 exact head;
- #169 closed unmerged after evidence purpose;
- issue #138 now asks only for genuinely separate human review.

### Evaluator semantics and calibration

- #171 merged canonical EvaluatorPlan v0.4 / verifier 0.3.0 transition semantics;
- #175 routed v0.4 through benchmark-cohort validation;
- #176 merged Task-001 legitimate-vs-inert-decoy calibration against the canonical verifier only;
- duplicate verifier implementation #170 stayed closed while its useful calibration idea was extracted.

### Benchmark evidence discipline

- first five-task pilot remains burned rather than rewritten;
- #182 is the active frozen/scored successor cohort with definition digest `sha256:3182d8710e1239c19cb95daddd0677241c0cd9123614786fd919b036922dbdd9`;
- #187 produced a successful frozen-definition Task-001 single-worker baseline attempt;
- durable receipt: `docs/evidence/phase-b2-successor-task001-attempt001.json`;
- a merge race landed #187's one-shot workflow/tool, and #190 removed only those two historical execution files while preserving the evidence;
- contaminated parallel freeze #185 was closed;
- #186 is a separate future **unfrozen scaffold**, not a competing scored cohort;
- #189 calibrated only future-scaffold Task 005; four scaffold tasks remain calibration-pending and no scored scaffold outcome exists.

### Branch rescue: interoperability

- old `interop-runtime-integration` branch was not merged wholesale;
- #181 rescued only the useful A2A/MCP semantic-binding files onto current `main`;
- #183 corrected A2A v1 negotiated protocol/service-parameter semantics while leaving MCP `2026-07-28` unchanged;
- issue #17 now tracks official SDK/TCK conformance and heterogeneous adapters, not stale branch integration.

### Research and CI

- #179 merged cost-weighted quorum research as research-only evidence;
- #184 fixed E015 false-green CI coverage;
- #191 merged a conservative quorum-frontier analysis tool separately from its wider, still-independent result run.

## External/admin blockers remain external

- **#35** — protect `main` using actual GitHub branch/ruleset settings;
- **#127** — physically delete exact cleanup-safe refs using a deletion-capable admin surface;
- **#138** — separate human review of #159;
- **#173** — repository description/topics/Discussions/Pages discovery settings.

## Maintainer invariant

```text
branch existence         != integration request
merged PR source branch  != merge again
CI success               != independent approval
worker success           != acceptance
verifier recommendation  != merge authority
benchmark calibration    != scored outcome
healthy capacity         != permission
```

Prefer one canonical implementation per responsibility, preserve negative evidence, extract useful stale-branch deltas onto current `main`, and optimize verified durable progress per unit of reviewer/maintainer attention rather than branch/PR/event volume.
