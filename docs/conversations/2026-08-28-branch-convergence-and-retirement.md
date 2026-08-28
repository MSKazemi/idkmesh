# Branch convergence and retirement pass

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`  
**User request:** reduce the very large branch population, merge useful work toward `main`, and delete garbage/stale branches.

## Outcome

The repository branch population was reduced from **170 to 71** without bulk-merging stale branch history into `main`.

The cleanup followed the canonical Branch Steward distinction:

- branches already integrated through merged pull requests are **retirement candidates**, not candidates to merge again;
- branches with no unique commits may be retired;
- branches with unique work or evidence value must be preserved for extraction/review rather than deleted solely to reduce the count;
- open review/hold branches must not be bypassed.

After the final fresh Branch Steward audit, the remaining 71 refs correspond to `main` plus unique/extract-or-retire work, evidence-preservation branches, one draft/human-review hold, and one integration-review branch.

## Open PR integration decision

No open pull request was merged during this cleanup.

- PR #159 remains intentionally draft and requires genuinely separate human review before integration.
- PR #219 remains the self-evolution methodology integration candidate and explicitly requires independent review.

The user's request to merge useful branches therefore did not justify overriding those project review gates. Already-integrated source branches were deleted instead of being merged a second time.

## Retirement execution

The GitHub connector did not expose a direct delete-ref operation, so a temporary one-shot GitHub Actions workflow was used under the user's explicit branch-cleanup authorization. The workflow had bounded `contents: write` permission, exact expected-head checks, no force update, and no merge/rebase operation. Evidence artifacts were retained for each pass, and the workflow was removed from `main` after use.

### Initial pass and correction

The first one-shot manifest was broader than the canonical Branch Steward retirement queue. It contained **102** entries rather than the canonical **98** candidates from the last complete pre-cleanup audit.

The first execution deleted 86 exact-head refs. Review of its evidence artifact exposed that **28 deleted refs belonged to unique/evidence-preservation or extract-or-retire lanes rather than the retirement lane**.

Those 28 branch refs were immediately restored to their exact original commit SHAs. No commit objects or branch contents were lost. This correction was performed before continuing the cleanup.

Evidence:

- first deletion run: `33209199718`
- artifact: `9700943564`

### Corrected canonical batch

A second manifest was rebuilt from the actual canonical Branch Steward retirement queue and excluded the restored evidence/unique-work refs by construction.

The remaining **40** unchanged canonical retirement candidates were deleted successfully:

- 40 eligible;
- 40 deleted and verified absent;
- 0 skipped;
- 0 failures;
- 0 post-delete verification mismatches.

Evidence:

- corrected run: `33209752839`
- artifact: `9701122522`

The repository then had **75 branches**.

### Fresh post-cleanup audit and final four

A fresh Branch Convergence Audit on the 75-branch state (`main` at `48f2144b0721fac61f57bc245b5c413621fb8044`) found only four remaining retirement candidates:

1. `feature/project-domain-contracts-v0` — integrated via PR;
2. `feature/idkgraph-p1-review-session-validator` — integrated via PR;
3. `fix/branch-audit-rate-limit-feedback` — integrated via PR;
4. `feature/active-compute-pulse` — closed/unmerged with no unique commits.

Fresh audit evidence:

- Branch Steward run: `33209884971`
- artifact: `9701161122`

The first tiny four-ref execution failed safely because it attempted `git push --delete` without a checked-out Git repository. Its evidence proved **0 refs were deleted** and the branch count remained 75.

- failed transport run: `33209970484`
- artifact: `9701181878`

The transport was changed to GitHub's ref API while preserving the same four exact-head candidates. The corrected run succeeded:

- 4 eligible;
- 4 deleted and verified absent;
- 0 skipped;
- 0 failures;
- 0 verification mismatches;
- **71 repository branches remaining**.

Final evidence:

- run: `33210089214`
- artifact: `9701229671`

The temporary write-capable retirement workflow was deleted from `main` immediately afterward.

## Net effect

```text
initial branches = 170
final branches   = 71
net reduction    = 99 branches
reduction rate   = 58.2%
```

No stale branch was merged merely to reduce branch count. No force update was used. Unique/evidence branches accidentally included by the first broad manifest were restored exactly before the canonical cleanup proceeded.

## Remaining branch policy

The remaining branch population should not be bulk-deleted. The fresh Branch Steward classification indicates that it is dominated by unique-work/extraction and evidence-preservation lanes rather than garbage.

Next branch reductions should therefore happen through **convergence**, not blind deletion:

1. review/extract useful unique commits into focused current-main PRs;
2. independently review and resolve #159 and #219;
3. retire their source refs only after integration/closure and a fresh audit;
4. keep running the read-only Branch Convergence Audit after meaningful lifecycle changes;
5. configure `main` branch protection/rulesets before granting any persistent autonomous branch-write authority.

## Safety lesson

Branch count is not itself a sufficient deletion objective. A retirement operation must be tied to a typed state (`integrated-via-pr`, `no-unique-commits`, etc.) and exact immutable head evidence. When an execution manifest and the canonical classifier disagree, fail closed or restore first, then continue from a fresh classification.
