# Conversation Record — ACE Hardening Convergence

**Date:** 2026-08-28

## Why this consolidation happened

ACE's own Growth Ledger entered `CONSOLIDATE` mode with review load far above its carrying-capacity target. During review of the open ACE stack, two safety PRs were found to be modifying the same privileged workflow independently:

- PR #51 — fail closed while `main` is unprotected;
- PR #62 — threat-model and harden ACE metadata handling.

Keeping both as long-lived conflicting PRs would increase exactly the kind of review/integration burden that ACE is designed to suppress.

The user asked the project to continue. The correct interpretation of "continue" under zero carrying capacity was therefore **consolidate existing work**, not create another independent growth mechanism.

## Decision

Create one fresh convergence branch from current `main` that preserves both safety models and adds explicit regression tests.

The converged workflow combines:

### From the metadata-security path

- immutable `actions/github-script` commit pin;
- trusted-author requirement for marker-driven `growth-seed` labels;
- workflow-owned `ace:ledger` identity;
- fail-closed ledger parsing;
- full pagination for issue scans;
- dedupe markers that count only real `growth-seed` issues;
- no interpolation of untrusted PR title text into generated issues;
- explicit no-checkout/no-PR-code-execution invariant under `pull_request_target`.

### From the protected-integration path

- read the actual GitHub metadata for branch `main`;
- `mainProtected = Boolean(mainBranch.protected)`;
- force ACE into `CONSOLIDATE` when the protected integration boundary is absent;
- disable the bounded reproductive actuator while `main` is unprotected;
- keep the evidence ledger operational so observation continues without increasing authority;
- document the bootstrap ruleset/branch-protection target and single-maintainer constraints.

## Regression contract

`tests/test_ace_workflow_hardening.py` statically checks the privileged workflow for the most important invariants:

- pinned action dependency;
- no `actions/checkout`;
- **no YAML shell `run:` step in the privileged `pull_request_target` workflow**;
- no `contents: write`;
- trusted marker authorization;
- workflow-owned ledger identity;
- fail-closed state parsing;
- no `pr.title` interpolation;
- branch-protection actuation gate;
- labeled dedupe requirement.

The explicit no-shell-execution check was ported from the later #51 contract work into this convergence branch so PR #98 remains the single canonical safety review surface.

The path-scoped workflow `.github/workflows/ace-workflow-hardening-check.yml` runs these checks with Python 3.11 and 3.13 and has `contents: read` only.

## Governance conclusion

Repository files and agent instructions cannot enforce integration safety by themselves.

The canonical invariant is:

> No autonomous actor may propose, approve, and merge the same protected change by itself.

The repository therefore treats actual GitHub protection/ruleset state as external evidence, not as a documentation preference.

## Relationship to ACE Phase B

This convergence does not activate Phase B.

Even after this hardening is reviewed, stronger community actuation remains blocked by the broader activation gate work:

```text
observer accepted
AND lineage accepted
AND security accepted
AND controller accepted
AND protected integration enforced
AND independently verified descendant evidence
AND healthy/fresh review capacity
AND bounded write budget
AND forbidden capabilities disabled
```

At the time of this convergence, public branch metadata still reported `main` as unprotected and the ACE Growth Ledger reported near-zero capacity. Therefore the correct operating posture remained `SHADOW / CONSOLIDATE`.

## Empirical community state checked during continuation

The live ACE Growth Ledger later showed:

```text
mode = CONSOLIDATE
review_load ~= 45.55
K = 8 (current controller hypothesis)
capacity ~= 0
```

with 173 observed raw events. This is a direct example of the anti-Goodhart rule: high repository activity is not evidence that the project should create another community generation.

Bootstrap Growth Seeds #24–#28 were inspected. Their visible activity remained predominantly repository-owner driven; no inspected comment on #25/#26 represented an external contributor. Therefore Cohort 2 should remain gated on real external/verified descendant evidence rather than raw PR/commit velocity.

## PR cleanup

PR #62 was closed unmerged after its threat model and metadata hardening were preserved in this convergence path.

PR #51 temporarily accumulated an additional equivalent safety contract during concurrent work. Its only missing invariant relative to PR #98—the explicit ban on a shell `run:` step in the privileged workflow—was ported into `tests/test_ace_workflow_hardening.py` here.

Therefore PR #98 should remain the canonical safety integration surface and PR #51 can be closed as superseded without losing a safety property.

This reduces the open ACE review surface while retaining the stronger combined safety contract.
