# 2026-10-13 — review branches for safe mainline integration

## Owner request

"Work on the branches. We have some branches we needed to merge to the main."

## Evidence

At `main@ea1fc610ed50fc4ba28e26ff8c6c95526e1f9c2a`, GitHub reported 10 branch refs including `main`, no open PRs, and nine diverged branch refs. Eight had a closed-unmerged original PR explicitly superseded by an already-merged replacement. The ninth, `fix/e9-no-empty-pass-20261013`, has no PR and duplicates less strict conformance behavior already integrated through PR #1107.

See the [dated branch-by-branch audit](../audits/2026-10-13-branch-convergence-reconciliation.md) for head SHAs, counts, PR/replacement links, and code observations.

## Decision

No direct merge, PR merge, force push, or branch deletion was justified by the available evidence. Preserve the historical branches while the independent maintainer decides whether any exact-SHA evidence or external consumer still needs a branch ref. There is no unmerged feature identified that merits a transplant on current `main`.

## Follow-up

1. Review the audit as a normal PR and check its exact-head CI and documentation gates.
2. Separately approve archival/retirement of superseded refs **only** after an evidence-reference audit; do not treat `ahead_by` as proof of incomplete work.
3. Start future changes from current `main`, with fresh PRs and independent review.

AI-assisted evidence reconciliation only; no claim of independent human review.

## Owner follow-up: smaller branch inventory

The project owner requested professionally reducing branch count without losing useful code, architecture, tests or historical evidence. Since the first audit, PR #1111 merged into main. A separate proposal now adds an operator-run lease-guarded retirement tool, eight exact old-head manifest entries, negative-control tests, and a safety runbook. Deletion still requires independent review, a live remote preflight and explicit human confirmation. Current connected GitHub tooling cannot delete branch refs directly; no production branch deletion was performed during this development.

## Additional protected-main consolidation review (2026-10-13)

At `main@e52247ab`, historical PR #1113 and the C8-G acceptance PR #1115 were merged; the remaining old branches are eight superseded refs and one held E9 orphan, plus the active retirement-tool proposal. The original retirement PR #1116 had an unintended closing-keyword guard failure in its historical commit message. Replacement PR #1117 retained the *exact Git tree* `8b3522465b983a54f2ec9936ab0c9da9059be92b` from the original safe snapshot on a clean-mainline parent without rewriting the earlier review history. A subsequent safety improvement to the replacement requires the retained `refs/pull/N/head` to agree with the pinned historical SHA; the deletion command additionally suppresses local pre-push hooks and tag following. New exact-head CI, independent review, offline archival and external-dependency checks remain mandatory. No historic branch was deleted or reintegrated in this review.

## Live branch-reduction and archive validation (2026-10-13)

The owner reiterated a small-branch, enterprise-quality approach that does not discard unique work, negative research evidence or public PR provenance. Live branch inventory is dynamic while the new E5 secret-scanning PR is in review. The superseded historical branches still must not be merged wholesale.

The operator retirement proposal is strengthened with a **required**, external, self-contained Git archive for each exact branch deletion. Previously, the operator-run tool relied on an attestation that a bundle existed. It now checks the original branch ref and SHA in the bundle inventory, runs Git bundle verification, and proves the historic commit can be restored by a fresh empty bare clone; tests cover missing, symlinked, stale, checkout-local and prerequisite-dependent incremental bundles. This ensures the archive is useful even if all source refs are eventually retired. It does not check external consumers or grant merge/deletion approval. CI and independent review must be repeated for the updated PR head. No remote branch was deleted during this review.
