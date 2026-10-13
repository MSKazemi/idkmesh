---
description: "Operator-reviewed, exact-SHA retirement of already superseded GitHub branches without losing PR and evidence history."
---
# Branch Retirement v0.1

**Authority boundary:** This is a manual operational procedure, **not** an autonomous branch cleanup service or a merge gate. The original [branch audit](../audits/2026-10-13-branch-convergence-reconciliation.md) and [eight-branch manifest](../audits/branch-retirement-2026-10-13.json) preserve the original full commit IDs, the closed PRs and their merged replacement PRs.

## Preconditions

1. Independently review each historical PR, its closure decision, the exact branch head, and the already-merged replacement. Preserve any unique code, experiments, negative findings or research evidence before retirement.
2. Check workflows, repository configuration, published docs, issues, release and acceptance records, and **external consumers** for branch-name/exact-SHA dependencies. A historical audit mention is provenance, not an active dependency. Hold anything uncertain.
3. Obtain explicit maintainer review/approval for **these exact refs**. Green CI does not confer deletion authority.
4. Before deletion, preserve old refs in an offline, verified Git bundle: fetch remote branch refs, run `git bundle create /secure/archive/idkmesh-before-retirement.bundle --all`, then `git bundle verify /secure/archive/idkmesh-before-retirement.bundle`. Retain its checksum and a secure copy outside the checkout. This prevents otherwise-unreachable commits from being lost.
5. Use a clean local checkout of **current main** with Git origin pointing to MSKazemi/idkmesh. The tool validates **both** the effective fetch URL and the single effective Git push URL (including `remote.origin.pushurl` and `url.*.pushInsteadOf` rewrites); multiple push destinations, mismatched fetch/push URL strings (even two protocols for the same repository), and remote push-mirror mode are refused. The checkout,
origin and effective push URL are revalidated immediately before **each**
non-atomic deletion. Never run cleanup from an old feature branch. Your authenticated Git origin must have deletion permission.

## Dry-run (default)

~~~bash
export GITHUB_TOKEN="<read-only GitHub API token>"
python tools/branch_retirement.py --manifest docs/audits/branch-retirement-2026-10-13.json
python -m pytest -q tests/test_branch_retirement.py
~~~

The tool only issues GitHub **GET** requests by default. Every candidate must match its pinned head; the original PR must remain closed and unmerged; no open PR may exist; the replacement must actually have merged; and the replacement merge commit must be an ancestor of current main. A dry-run result is **not** deletion authorization. Keep the GitHub token private; Git push credentials are separate.

## Execute only after human evidence attestation

~~~bash
python tools/branch_retirement.py \
  --manifest docs/audits/branch-retirement-2026-10-13.json \
  --execute \
  --branch agent/issue-745-cors-delta \
  --attest I_REVIEWED_BRANCH_EVIDENCE_AND_EXTERNAL_REFERENCES
~~~

Before deletion the tool requires the reviewed origin, exact local main HEAD, clean worktree, stable GitHub main and **fresh** PR/branch checks. It uses Git push with an exact SHA --force-with-lease, so moving a source branch after review rejects deletion. It never invokes a generic force-push, direct merge, unapproved rebasing or branch cleanup by name pattern.

**One branch per execution:** the full eight-branch manifest may be inspected in dry-run mode, but `--execute` requires `--branch` selecting exactly one listed ref. After a real deletion, record the result, recheck the remote branch inventory and dependencies, and independently authorize the next ref. The literal attestation string is an operator assertion, **not proof of human identity or external-consumer clearance**; a separate human review remains mandatory.

**Excluded:** main, active PRs, changed/protected/frozen branches, recent work such as C13-E/C8-G, and fix/e9-no-empty-pass-20261013 (a no-PR orphan still needing independent evidence review). The historical PRs stay available as audit references after deleting a source branch.

## Verification and aftercare

The isolated negative-control suite passed **13 tests and 10 subtests**. A disposable local bare-Git test confirmed a mismatched expected SHA blocks deletion and an exact matching lease permits it. These are **not** live destructive GitHub tests. Exact-head PR Gate, a separate reviewer and operator authorization remain required before using execute.

After a successful operator run, rerun the read-only branch convergence audit, verify remaining remote refs and open PRs, inspect workflows for broken dependencies, and save actual deletion results in a dated repository audit. Do not interpret a smaller branch number as evidence of better code.

## Community Impact

Keeping only meaningful working refs improves contributor navigation, while durable PR references and exact SHA evidence protect useful experiments and explain why obsolete implementations were not re-merged.
