# Branch and PR convergence continuation

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner instruction

Continue maintaining IDKMesh professionally and consider **branches as well as pull requests**, not only the visible open PR queue.

## Maintainer interpretation

A Git branch is not an integration unit by itself.

The repository had accumulated a large branch graph while PRs were being merged, squashed, superseded, rebuilt, used for evidence, and sometimes reused after merge. Treating every ahead/diverged branch as mergeable work would reintroduce duplicate implementations and stale ancestry.

The operating rule for this pass was therefore:

```text
branch -> classify provenance/current value
       -> exact diff/evidence review
       -> clean current-main PR when useful
       -> preserve negative/evidence history
       -> retire only when safe
```

Direct branch merge authority remained zero throughout.

## Canonical branch audit

The repository already contained the read-only branch-convergence auditor from merged PR #123. It was reused rather than replaced.

The auditor:

- reads branches and PR lineage;
- distinguishes squash-integrated source heads from true unique work;
- preserves active/evidence-sensitive branches;
- rejects direct branch merge as an integration strategy;
- has read-only `contents` / `pull-requests` permissions.

### First refreshed snapshot in this pass

The first live refresh observed:

```text
total branches                         113
cleanup eligible                        59
integrated via merged PR                54
orphan / no unique commits               5
post-merge branch moved                  5
orphan diverged                          7
closed-unmerged evidence branch          6
closed-unmerged unique work             34
```

That snapshot was used to inspect moved and orphan branches rather than immediately deleting refs.

### Settled snapshot after convergence work

Final settled audit:

- workflow run `33187644986`;
- job `98927547838`;
- artifact `9695119980`;
- artifact digest `sha256:e9f8358bbd2eece0ed78c0875b469f12ec080cfce52638239073b81b25c9065d`.

Result:

```text
branches observed                      131
non-default branches                   130
cleanup eligible                        69
direct branch merges allowed             0

canonical                                1
active draft PR                          1
integrated via merged PR                62
orphan / no unique commits               7
orphan diverged                          7
post-merge branch moved                  5
closed-unmerged evidence branch          9
closed-unmerged unique work              39
```

The branch count increased because the repository continued creating and merging research/evidence work while maintenance was underway. The important result is not a cosmetically low count; it is an explicit lifecycle state and a safe convergence decision for the high-risk categories.

The canonical maintenance ledger is issue #127.

## Post-merge moved branches

A merged PR does not authorize commits added to its branch later. Five such branches were inspected.

### `acceptance/real-node-verifier-520ad2c`

The branch had advanced after merged PR #113 by a missing conversation record. That record was preserved on `main` as:

`docs/conversations/2026-08-28-real-node-verifier-e2e.md`

After preservation, the stale source branch has no remaining integration reason.

### `ace-hardening-converged-v0`

The branch was reused after merged #98 for later R3 research already represented by the canonical research lineage. Do not merge the reused branch.

### `feat/conjunctive-evolution-current-main`

Its executable post-merge minimization delta was later represented by merged #150. Do not merge the reused source branch.

### `fix/resource-registry-runtime-boundary`

Later branch movement was represented by the canonical runtime/evidence path. Do not merge stale ancestry.

### `maintenance/branch-convergence-audit-v0`

The branch was reused after its audit PR for later Free Resource / benchmark-contract work that landed through separate reviewed PRs. It should not be merged as one combined branch.

## Diverged orphan decisions

### Retire / do not revive

- `feat/local-independent-validator-v2` — duplicate obsolete validator/EvaluatorPlan-v0.1 architecture; canonical verifier/Evaluator Sovereignty supersedes it.
- `idkgraph/p1-adr-linkage-triage` — useful semantics rebuilt cleanly and merged through #155.
- `idkgraph/p1-warning-sample` — useful sampler rebuilt and merged through #162, with follow-up classification #166.
- `planning/refresh-current-priorities-post-evidence` — replacement #154 became known-stale before integration; historical reasoning was preserved but a false `CURRENT_PRIORITIES` snapshot was not merged.
- `integration/real-node-verifier-e2e` — old real-node/verifier harness superseded by #108/#113 and later real two-attempt/report/replay evidence.
- `planning/current-execution-graph-v2` — operationally stale planning snapshot, superseded by current planning/triage surfaces.
- `fix/phase-b2-v03-calibration` — historical pre-v0.4 calibration work; semantic boundary superseded by #164/#171 and later Task-001 calibration evidence.

### Extract / rebuild, never merge wholesale

`interop-runtime-integration` contains a useful A2A/MCP binding idea but is more than a hundred commits behind and hard-codes Work Unit schema `0.1` while the project has newer canonical contracts. Issue #17 remains the correct tracker. Only the interop semantics should be rebuilt on current `main`, with current contract/SDK conformance and heterogeneous adapters.

`growth/fast-discovery-20260828` contains useful discovery/first-contact analysis. Its primary current admin action is already durable in issue #173. The stale branch should not be merged wholesale; durable docs/front-door content may be extracted through a clean current-main PR after time-sensitive external free-resource claims are revalidated.

## IDKGraph and ACE convergence

### PR #155 — merged

Resolved accepted-ADR linkage warnings by adding explicit evidence-backed references, not by weakening detectors.

Exact live observatory result before merge:

- 269 nodes;
- 0 deterministic errors;
- 0 accepted-decision linkage warnings;
- residual orphan-document findings remained warnings for later review.

### PR #156 — merged

Rebuilt the ACE population experiment on canonical recoverable `live-open-work-v1` capacity instead of the obsolete cumulative-load assumption. The experiment remains deterministic/offline/toy research and creates no Phase-B actuation authority.

### PR #162 / #166 — merged concurrently

Rebuilt the orphan-warning sampler on current `main` and then classified a frozen warning cohort without weakening IDKGraph semantics.

## Phase B2 benchmark falsification and semantic versioning

The benchmark lane produced important negative evidence rather than being forced to pass.

### Task 001 evidence failure

PR #158 generated a straightforward Task-001 fix that passed its path-boundary behavior but was rejected by the frozen metadata evaluator. The mismatch was real: the frozen plan used a semantic fragment while verifier 0.1.1 interpreted `required_added_text` as exact whole-line equality.

The correct response was not to edit the frozen benchmark after seeing the answer.

### Burn the pilot

Merged PR #160 burned the first-five pilot while preserving the original frozen WorkUnits, EvaluatorPlans, and pre-outcome definition digest.

### Explicit semantic boundary

PR #164 introduced v0.3 added-line substring semantics while preserving v0.2 exact-line meaning.

Pre-v0.3 successor-freeze PR #163 was closed instead of silently translating its frozen commitment; its anti-Goodhart reasoning was preserved in:

`docs/conversations/2026-08-28-phase-b2-evaluator-freeze-audit-and-v2.md`

### v0.4 transition semantics

Parallel #170 and #171 initially introduced overlapping verifier-0.3.0 implementations.

#171 was selected as the canonical layer because it cleanly preserves:

```text
v0.2 / 0.1.1 = exact added-line equality
v0.3 / 0.2.0 = added-line substring matching
v0.4 / 0.3.0 = required added + removed line substring transitions
```

Its exact-head Evaluator Plan Binding, Phase 0, randomness, IDKGraph, and Evolution checks were green. It merged as commit:

`c60549c43232231c724fe3aaaac1f08a26998cbe`

#170's earlier Task-001 calibration run failed because its supposed inert decoy unexpectedly changed the vulnerable behavior. The branch subsequently advanced and its latest head produced a successful calibration run. That calibration evidence is useful, but #170 remains closed because it also contains a second v0.4 schema/runner/verifier implementation. The correct next action is to extract only the successful Task-001 behavioral/adversarial calibration onto current `main`, calling the canonical #171 transition verifier.

Issue #157 records this remaining calibration extraction boundary.

## Canonical node branch convergence

Historical PR #91 contained the accepted worker bytes but had become a stale integration branch relative to modern `main`.

Clean replacement PR #159 was created from current `main`.

At convergence review:

- historical #91 head: `520ad2c9aa5825476de4957da4702d6823f4edb3`;
- replacement #159 head: `61cafa86f7e0e86343d73182862e3cead1080ab9`.

Git-tree/blob inspection confirmed all 14 worker/workflow/test/schema blobs carried by #91 were byte-identical on #159. #159 adds only a convergence conversation record.

Byte equality was explicitly **not** treated as acceptance equality.

#91 was closed as the historical exact-evidence branch so the repository would have one canonical worker integration path.

Historical #91/#37/#108 evidence remains public provenance for the old exact head, including the failed-first Docker run, fixture correction, regression guard, and later passing matrix.

## Fresh #159 evidence

Fresh exact-head CI on #159:

- Node CI `33193136252` — success;
- Phase 0 `33193136271` — success;
- randomness-lab `33193136289` — success;
- Evolution `33193136417` — success.

A new candidate-bound read-only evidence PR #169 reused the previously reviewed #108 runtime acceptance mechanics by blob identity and changed only the replacement candidate/CI binding.

#169 workflow:

- run `33193838388`;
- job `98925820770`;
- candidate `61cafa86f7e0e86343d73182862e3cead1080ab9`;
- `all_acceptance_checks_passed: true`;
- `worker_acceptance_authority: false`.

Positive evidence confirmed:

- schema-valid succeeded ResultManifest;
- expected `README.md`-only candidate change;
- no path/untracked/unpackaged/protected-metadata/output/runtime violations;
- non-truncated patch;
- matching patch/stdout/stderr digests;
- immutable image ID + matching repository digest;
- network-none, read-only root, capability drop, no-new-privileges, PID/CPU/RAM bounds, read-only Git metadata, and no Docker socket.

Negative A-E2 cases all failed closed:

- forbidden/out-of-scope tracked path;
- ignored untracked artifact;
- task-visible Git pointer tampering;
- oversized/truncated patch;
- absent local image;
- locally retagged image without matching repository digest.

#169 was then closed **without merge** because it is one-shot candidate-bound evidence instrumentation. Its run/logs remain provenance without leaving a stale SHA-bound workflow on `main`.

## Remaining worker gate

PR #159 is intentionally still draft.

Mechanical runtime acceptance is complete. The remaining gate is a genuinely separate human/reviewer inspection through issue #138.

Neither blob equality, worker success, green CI, the runtime harness, the PR author, nor project automation is allowed to manufacture that approval.

If #159's head/tree changes, the relevant evidence must be rebound/re-evaluated.

## Branch deletion boundary

The connected GitHub maintenance surface available in this session does not expose branch-ref deletion.

Therefore this pass did **not** fake deletion by force-moving refs.

Issue #127 records 69 cleanup-eligible branches at the settled audit snapshot. A deletion-capable repository-admin pass should:

1. revalidate each exact branch head immediately before deletion;
2. preserve evidence-sensitive refs until durable run/commit/artifact references are sufficient;
3. confirm no open PR or external workflow depends on the branch name;
4. delete only verified cleanup-safe refs;
5. rerun the canonical audit and measure the actual reduction.

Branch count is coordination hygiene, not a project-success metric.

## External integration and growth gates

Public metadata continued to report `main` as unprotected. Issue #35 remains the P0 repository-admin safety gate before stronger autonomous repository writes.

Public repository metadata also still showed an empty description, no topics, Discussions disabled, Pages disabled, homepage unset, and zero stars/forks. Issue #173 tracks the GitHub-native discovery/admin actions. These settings should be improved without turning stars/comments/PR count into the optimization target.

## End state of this continuation

At the final settled branch audit:

```text
131 branches
69 cleanup-eligible
0 direct branch merges allowed
1 active draft PR
```

After resolving the overlapping v0.4 review queue, the live open-PR search again contained only **#159**.

The next highest-value actions are therefore external or evidence-bound rather than another parallel architecture branch:

1. separate human review of #159 (#138);
2. protect `main` (#35);
3. physically retire exact cleanup-safe branches through a deletion-capable admin surface (#127);
4. extract the successful Task-001 behavioral calibration onto canonical v0.4 without a second verifier implementation (#157);
5. rebuild interoperability on current contracts rather than reviving `interop-runtime-integration` (#17);
6. activate GitHub-native discovery surfaces (#173).

The repository should continue preferring convergence, independent evidence, and clear contributor entry points over raw branch/PR/event volume.
