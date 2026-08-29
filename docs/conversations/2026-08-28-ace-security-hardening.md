# Conversation Record — ACE Security Hardening Continuation

**Date:** 2026-08-28

## Project-owner instruction

The project owner asked the assistant to continue work directly in the public `MSKazemi/idkmesh` repository.

## Work completed earlier in this turn

The repository had two overlapping ACE pull requests:

- PR #44 for Growth Seed #27, the ACE population simulator;
- PR #48 for Growth Seed #25, lineage evidence, which also contained a second simulator implementation.

The overlap was reconciled so:

- PR #44 remains the simulator candidate for #27;
- PR #48 is narrowed to lineage evidence for #25;
- the revised lineage protocol requires an independent eligible-parent/seed inventory for the `R_community(W)` denominator so zero-descendant parents are not omitted;
- right-censoring is documented for newly created parents whose observation window has not matured.

PR #48's duplicate simulator and simulator-specific workflow were removed, and its fresh Phase 0 CI passed.

## Next dependency selected

After #25/#27 reconciliation, the next Bootstrap Cohort dependency was issue #26:

> Threat-model `.github/workflows/ace-community-growth.yml` before ACE gains stronger write capability.

This was prioritized because the workflow uses `pull_request_target` with `issues: write` and therefore crosses a privileged GitHub trust boundary even though its current behavior is metadata-only.

## Security findings

The workflow already had the most important invariant:

```text
pull_request_target
 -> no checkout of PR head
 -> no imports/builds/tests from PR code
 -> no secrets exposed to PR execution
 -> metadata only
```

That substantially limits fork-originated code-execution risk.

Several metadata-plane weaknesses were found:

1. any issue author could include `<!-- ACE_SEED` and cause the workflow to apply `growth-seed`;
2. the ledger was discovered largely by title, which is not a trusted identity;
3. malformed `ACE_STATE` JSON was silently ignored and replaced by default state;
4. issue scans used only the first 100 results, weakening deduplication as the repository grows;
5. any issue containing `spawned-from:pr-N` could poison the generated-seed dedupe check;
6. generated Growth Seeds copied untrusted PR titles into Markdown;
7. `actions/github-script@v7` used a moving tag rather than an immutable commit.

## Hardening applied on review branch

Branch: `security/ace-workflow-threat-model`

Changes to `.github/workflows/ace-community-growth.yml`:

- pin `actions/github-script` to commit `f28e40c7f34bde8b3046d885e986cb6290c5673b`, the `v7` tag target observed during this review;
- apply marker-derived `growth-seed` only when issue `author_association` is `OWNER`, `MEMBER`, or `COLLABORATOR`;
- add workflow-owned `ace:ledger` label and prefer it for canonical ledger identity;
- adopt the oldest legacy title + `ACE_STATE` ledger during migration and label it;
- fail closed if the ledger state block is missing or malformed;
- use `github.paginate` for ledger and deduplication scans;
- require the dedupe marker to appear on a `growth-seed`-labelled issue before it can suppress a generated seed;
- stop copying PR titles into generated issue bodies.

## Threat-model artifact

Added:

`docs/security/ACE_THREAT_MODEL.md`

It documents:

- assets;
- trust boundaries;
- attack surfaces;
- fork-originated PR analysis;
- permissions;
- ledger integrity;
- DoS/spam and recursion risks;
- prompt/content-injection boundary for future AI use;
- severity/likelihood table;
- abuse scenarios;
- required guards before stronger autonomy;
- explicit v0 security verdict.

## Security verdict

After the proposed hardening, ACE v0 is considered **safe enough for current metadata-only experimental operation**, subject to normal review and the hard invariant that PR-head code is never executed in the privileged workflow.

It is not considered safe enough for:

- autonomous merge;
- code execution from untrusted PRs;
- secrets access;
- governance/security policy mutation;
- privileged AI tool execution from issue/PR text;
- broad recursive write automation.

## Project principle reinforced

The security review produced a reusable rule for IDKMesh:

> **Text may propose; typed policy and verified evidence authorize.**

GitHub titles, bodies, comments, and markers are observations/evidence. They must not directly become authority simply because a privileged workflow can read them.

## Community impact

The hardening preserves the low-friction GitHub-native ACE experiment while reducing ways that untrusted activity can pollute labels, ledger identity, or deduplication. It also keeps the security review itself as an independently reviewable Growth Seed contribution rather than silently changing `main`.
