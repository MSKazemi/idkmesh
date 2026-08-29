# Continuous branch-creation audit — 2026-08-29

## Question

Is there an agent or in-repository automation in `MSKazemi/idkmesh` that continuously creates new branches?

## Finding

**No in-repository agent or scheduled GitHub Actions workflow was found that continuously creates branches.**

The repository does have many non-`main` branches, including acceptance, benchmark, integration, feature, maintenance, and Codex-named branches. Their presence by itself does not prove that a resident continuous branch-creation agent exists; the GitHub branches endpoint does not expose the creator or creation event for each branch.

### Closest automated mechanisms

1. `.github/workflows/branch-convergence-audit.yml`
   - Runs on a daily schedule (`17 4 * * *`), on `main` pushes, PR lifecycle events, and manual dispatch.
   - Explicitly has only `contents: read` and `pull-requests: read` permissions.
   - Audits branch state and builds a deterministic merge plan; it does not create, push, merge, or delete branches.

2. `.github/workflows/evolution-loop.yml`
   - Runs on repository events plus a daily schedule (`17 5 * * *`).
   - Has no workflow-wide authority; its observer job has read-only `contents`, issues, PRs, and Actions permissions.
   - It observes and scores evolution state rather than mutating Git refs.

3. `.github/workflows/real-node-verifier-e2e.yml`
   - Has `contents: read`, `persist-credentials: false`, and explicitly documents that it has no push or merge authority.
   - It is PR/manual-dispatch driven, not continuous branch creation.

Repository code searches for branch-creation/push patterns such as `create branch`, `git branch`, and `git push` returned no matching implementation. GitHub code search reported an incomplete index for one permission query, so this is best understood as an audit of the currently visible repository mechanisms rather than proof about external tools.

## Interpretation

The large branch population is more consistent with branches created during manual work, pull-request work, external coding-agent sessions, or one-off integration/evidence work. An external agent connected through GitHub can create a branch without a branch-creation loop being defined inside this repository.

## Recommended policy

Do **not** add a branch-creation agent that creates branches simply because time passes. If autonomous branch creation is introduced later, make it demand-driven and bounded: create a branch only for a selected work unit, attach it to an issue/PR, enforce a branch budget and TTL, and converge or delete it after completion. The existing Branch Convergence Audit should remain the read-only governor over that lifecycle.
