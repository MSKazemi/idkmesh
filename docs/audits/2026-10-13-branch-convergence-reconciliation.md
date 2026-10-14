# Branch convergence reconciliation — 2026-10-13

**Snapshot, not a live merge authorization.** Inspected repository: [MSKazemi/idkmesh](https://github.com/MSKazemi/idkmesh), canonical baseline `main@ea1fc610ed50fc4ba28e26ff8c6c95526e1f9c2a`. The snapshot records all **nine** non-`main` branches returned by the GitHub branches API at this revision. There were **zero open PRs**. For each non-main branch, the GitHub compare API reported `status=diverged`, with commits both ahead of and behind `main`. Every branch head below is exact; re-evaluate before any future operation.

**Verdict:** **0 eligible for direct or PR merge today.** Eight source branches belong to intentionally closed, unmerged PRs whose maintainers identified already-merged replacements. The ninth is an orphan divergent branch containing a weaker duplicate of conformance guards now on `main`. Do **not** bulk merge, rebase, force-push, delete, or automatically reopen any of these branches. This is consistent with the [branch convergence policy](../planning/BRANCH_CONVERGENCE_POLICY.md), which requires a new bounded PR and independent review for genuinely unique useful work.

## Verified branch inventory

`Ahead/behind` counts are from comparing **`main...branch`** against baseline `ea1fc610ed50`, not evidence of unintegrated useful behavior. The old branch history often remains ahead after a transplant/squash merge.

| Branch (exact head) | Ahead / behind | Original PR | Mainline replacement/evidence | Decision |
| --- | ---: | --- | --- | --- |
| `agent/issue-745-cors-delta` (`579b2891c3174a0038babb6405837021b2a69faa`) | 2 / 69 | [#1042](https://github.com/MSKazemi/idkmesh/pull/1042) closed-unmerged | [#1064](https://github.com/MSKazemi/idkmesh/pull/1064), merged as `39e4dc87`; maintainer explicitly superseded #1042 | Preserve until archival check; do not re-merge local UI cross-origin tests |
| `agent/issue-745-openapi-compat-gate` (`4416f1dfa210458fe95c79061dc0b3b619370c05`) | 2 / 69 | [#1039](https://github.com/MSKazemi/idkmesh/pull/1039) closed-unmerged | [#1063](https://github.com/MSKazemi/idkmesh/pull/1063), merged as `b783a654`; maintainer explicitly superseded #1039 | Do not reintroduce the older OpenAPI/schema-compat implementation |
| `agent/issue-745-permission-matrix` (`907a37960fa059f3aace8439ab1edd3881c17d9e`) | 2 / 69 | [#1043](https://github.com/MSKazemi/idkmesh/pull/1043) closed-unmerged | [#1069](https://github.com/MSKazemi/idkmesh/pull/1069), merged as `e2c7d0a6`; maintainer noted later qualification-report improvements | Do not undo the mainline permission/report boundaries |
| `agent/20261012-issue-608-parallel` (`2beb3520e4685c0a246e9eb4cfbf4944460a3f2c`) | 3 / 30 | [#1078](https://github.com/MSKazemi/idkmesh/pull/1078) closed-unmerged | [#1095](https://github.com/MSKazemi/idkmesh/pull/1095), merged as `2461c963` | Do not merge older Projects projection behavior |
| `agent/20261012-issue-664-parallel` (`b9fb1768bf8930fd6f494a4f364a4d096c13252f`) | 4 / 30 | [#1086](https://github.com/MSKazemi/idkmesh/pull/1086) closed-unmerged | [#1092](https://github.com/MSKazemi/idkmesh/pull/1092), merged as `0cdf0519`; maintainer closed draft as duplicative | Do not duplicate the current privacy-safe visibility funnel guidance |
| `cli-help-examples-1029-8825333565183622993` (`fee10dd7936cfe2fa3367bcf27f13b3a1ef668ae`) | 4 / 69 | [#1033](https://github.com/MSKazemi/idkmesh/pull/1033) closed-unmerged | [#1044](https://github.com/MSKazemi/idkmesh/pull/1044), merged as `63f27cb0` | Help examples already integrated; avoid duplicate CLI modifications |
| `fix/c13-workunit-form-preview-20261013` (`94fa91c83f2e0f5267f164a74947d5a097bb2a3b`) | 1 / 31 | [#1084](https://github.com/MSKazemi/idkmesh/pull/1084) closed-unmerged | Maintainer identified [#1049](https://github.com/MSKazemi/idkmesh/pull/1049) and follow-ons as the stronger integrated parser/preview; #1049 merged as `40126a00` | Do **not** overwrite current WorkUnit intake contract |
| `fix/e9-no-empty-pass-20261013` (`475b3eb1735fe658c2a0b098f38752e50a44fecf`) | 1 / 22 | None; **orphan-diverged** | [#1107](https://github.com/MSKazemi/idkmesh/pull/1107), merged as `436dd58e`, already rejects empty selections and flags zero-assertion scenarios as **FAIL** | Its older zero-assertion **UNKNOWN** semantics are weaker/different. No useful transplant identified |
| `jules-1000812529289196511-6748be38` (`63f91382e4b2d0eb0323f6118c7896fd4e4899b3`) | 3 / 69 | [#1032](https://github.com/MSKazemi/idkmesh/pull/1032) closed-unmerged | [#1041](https://github.com/MSKazemi/idkmesh/pull/1041), merged as `02656a65` | Help examples already integrated; do not re-merge |

The corresponding GitHub PR discussion and explicit maintainer closure comments are the source for each declared supersession. This inventory did not establish byte-identical diffs across every old and replacement PR; preserve the old commits as public history rather than asserting bitwise identity.

## Current-main spot checks

At the snapshot base, the following canonical files exist and contain the expected integration surfaces:

- `tools/openapi_catalog.py` and `tests/test_api_cors_csrf_matrix.py`: OpenAPI parsing and local-browser boundary regression coverage.
- `tests/test_enterprise_authz_permission_matrix.py`: enterprise policy decision-matrix coverage.
- `idkmesh/github_routing_projection.py` and `idkmesh/github_workunit_intake.py`: current planning and intake modules.
- `docs/community/VISIBILITY_AND_COMMUNITY_GROWTH_LOOP.md`: source windows and attribution distinctions.
- `idkmesh/cli.py`: help-example formatter and examples.
- `idkmesh/enterprise_conformance.py` and `tests/test_enterprise_conformance.py`: reject an empty selected scenario set and assert zero-check scenarios cannot report successful conformance.

These are source/contract observations, **not** a new CI run or an independent security audit.

## Classification, safe next actions, and no-loss rules

- **Eight `closed-unmerged-unique-work`:** their PRs were intentionally closed for supersession. Compare status alone cannot safely infer a merge. Do not create replacement PRs for already-integrated semantics.
- **One `orphan-diverged`:** the #676 conformance fix has a reviewed, stronger replacement on `main`. Do not transplant its weaker reporting semantics.
- **Zero active integration PRs:** all nine branch refs remain readable for historical/provenance inspection; source branches may remain ahead after their replacement was squash-merged.
- **Retirement is a separate human-governed action:** before deleting any branch, check references in workflows, issue discussions, documented exact-SHA evidence, experiments and external consumers. Confirm its content is durably represented and that no frozen evidence relies on the branch name. Deletion was **not** performed or authorized by this audit.
- **New work should start from current `main`:** if an independent reviewer identifies genuinely unique, useful code in one old head, extract only that bounded delta to a fresh branch/PR, preserve its origin, run exact-head Python gates and CodeQL, and obtain independent review before merge.

## Provenance and limitations

Read-only GitHub branch enumeration, `main...branch` comparisons, each source branch's full PR-history query, PR closure comments, successor PR merge metadata and selected live-`main` source checks were used. Local Git checkout and pytest were unavailable because the execution container could not resolve `github.com`; no CI results are claimed for this audit branch yet. This record is an AI-assisted reconciliation and **not** independent maintainer approval.

**Community impact:** explicitly distinguishing stale duplicate branches from live work prevents new contributors from wasting review time or accidentally resurrecting superseded security and intake behavior. The [current branch policy](../planning/BRANCH_CONVERGENCE_POLICY.md) and [read-only branch audit tool](https://github.com/MSKazemi/idkmesh/blob/main/tools/branch_convergence_audit.py) remain the executable/process sources of truth.

## Follow-up: eight guarded retirement candidates

This earlier branch count is a dated snapshot, not the live inventory. The reconciliation itself was merged as [PR #1111](https://github.com/MSKazemi/idkmesh/pull/1111), commit c47ea2f2818549d8cd012d24bf0cc69c773f8f65.

The [eight-item manifest](branch-retirement-2026-10-13.json) includes only branches whose original PRs were closed without merging and for which an explicit replacement PR **did** merge. Original PR head SHAs and replacement-merge ancestry were independently checked against current main at the time of drafting. Actual cleanup requires fresh checks, human verification of active workflows and *external* frozen-evidence references, and an explicit operator action. The manifest is not an approval.

**Excluded:** fix/e9-no-empty-pass-20261013 has no original PR and its old zero-assertion semantics are weaker than the current main implementation. Keep it until independently reviewed. Active C13-E, C8-G and retirement-tool work, as well as any future branch opened by a contributor, are not cleanup candidates merely because they are young, ahead or behind main.

See the [lease-guarded runbook](../operations/BRANCH_RETIREMENT_V0_1.md). No historic source branch was merged or deleted as part of this update.
