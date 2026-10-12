# Parallel worker 01 — issue #607 GitHub governance preflight

**Date:** 2026-10-11  
**Issue:** #607 — C12 GitHub governance and secret-access baseline

## Owner request

Continue solving useful open IDKMesh issues and keep documentation synchronized
with every implementation.

## Selection

The live issue/PR backlog was inspected before selection. Work requiring real
external evidence was skipped, and active overlapping API/intake/evidence PRs
were avoided. Issue #607 was selected because C12-A had already landed through
PR #929, while C12-B through C12-H remained repository-contained, bounded, and
unclaimed.

Parallel worker slot 01 posted the repository claim only after checking open
pull requests for overlap.

## Implementation

The new C12 preflight reuses the canonical guard vocabulary from
`idkmesh/github_governance_policy.py`. It does not create a second policy
model.

The implementation adds:

- normalized trusted GitHub governance observations;
- PASS/WARN/FAIL/UNKNOWN/NOT_APPLICABLE evaluation;
- fail-closed `require_governance()` enforcement for FAIL/UNKNOWN;
- conservative workflow-source linting for least privilege, immutable action
  references, checkout credential persistence, untrusted-PR secret isolation,
  protected environments, and OIDC token permission;
- explicit-owner CODEOWNERS recommendation generation;
- OIDC workflow-shape preflight without authenticating to a cloud provider;
- `idkmesh doctor --github` rendering and exit semantics;
- deterministic examples, tests, and synchronized C12/admin/specification docs.

## Authority and evidence boundary

The preflight performs no GitHub administration and reads no secret values. It
does not dispatch work, verify or accept candidates, approve changes, or merge.
Ruleset/branch-protection metadata is not represented as proof that a human
reviewer was independent.

Missing or inaccessible required evidence is UNKNOWN and blocks the requested
operation rather than being interpreted as secure. The committed examples are
synthetic deterministic fixtures, not observations of a real target
repository.
