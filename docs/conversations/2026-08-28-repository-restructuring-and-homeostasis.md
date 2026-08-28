# Repository Restructuring and Homeostasis Discussion

Date: 2026-08-28

## Prompt

The project owner asked for the next steps, whether the growing repository should be restructured, and whether IDKMesh can use an algorithm that periodically restructures itself after iterations and new files are added.

## Repository observations

- IDKMesh now has typed `docs/` modules but also many substantial topic documents at repository root.
- The project is accumulating research/community material rapidly while the primary executable product path is still #4 + #5 -> #16.
- Issue #20 and `docs/architecture/SELF_EVOLVING_REPOSITORY.md` already define a guarded self-evolution direction and explicitly reject uncontrolled automatic moves.
- Repository metadata reports `main` as currently unprotected, which should be fixed before stronger autonomous write capabilities are introduced.

## Decision direction

Do not restructure simply every fixed number of commits.

Adopt a **Repository Homeostasis Engine (RHE)**:

- observe structure continuously;
- define structural evolution epochs from commits, changed files, and measured pressure;
- use hysteresis so the structure does not oscillate;
- generate typed bounded rewrite proposals;
- execute structural changes only through a branch/PR;
- independently verify links/tests/invariants;
- measure the actual effect after merge;
- retain provenance and rollback ability.

RHE v0 is proposal-only and cannot move/delete files or approve its own restructure.

## Initial epoch policy

Experimental starting values:

- 25 commits since structural baseline; or
- 15 distinct files changed; or
- structural pressure >= 60/100.

A future controller should use a lower healthy/reset band around 35/100 to reduce repeated restructuring near the trigger boundary.

## Initial implementation

Branch `repo-homeostasis-v0` adds:

- `.idkmesh/repository-homeostasis.json`;
- `tools/repo_observatory.py`;
- `.github/workflows/repository-homeostasis.yml`;
- `docs/architecture/REPOSITORY_HOMEOSTASIS_ALGORITHM.md`;
- a repository structure/next-steps audit.

The GitHub workflow is intentionally split so pull-request repository code runs only with read access. A separate write-capable ledger job does not check out or execute PR code.

## Proposed first real restructure

After the RHE proposal is verified, migrate only one coherent group of root documents (for example core foundation documents) into a typed `docs/foundations/` module, repair all links, rerun health checks, and compare before/after metrics.

Do not bulk-move the whole repository in one change.
