# ChatGPT scheduled-agent branch audit — 2026-09-18

## Finding

Yes. ChatGPT scheduled tasks connected to GitHub can create branches when their prompt grants that behavior and the connected GitHub capability has write access.

In the current IDKmesh ChatGPT task set:

- **IDKmesh Reliability Agent** is enabled and runs hourly at minute 35. Its prompt uses branch prefix `agent/reliability/` and allows a new reliability PR in BUILD mode when repository concurrency and overlap guards permit it.
- **IDKmesh Weekly Steward** is enabled and runs every four hours. Its prompt permits using a focused branch and pull request when direct edits are not appropriate.
- Most other branch-producing specialist tasks (frontend, backend, bugfix, product, community, builder, etc.) are currently disabled.

Therefore branch proliferation can come from ChatGPT scheduled agents even though no in-repository GitHub Actions workflow continuously creates branches.

## Important distinction

A scheduled ChatGPT task is external to `.github/workflows/`. It can inspect the repository and, when authorized, call GitHub write operations such as creating a branch, committing changes, and opening a PR. Its behavior is controlled by its scheduled prompt and available connector permissions.

The enabled reliability task does **not** require creating a branch on every run. Its prompt first checks operating mode, PR budget, and file overlap; a new branch is only allowed in BUILD mode.

## Recommendation

Keep branch-producing scheduled agents bounded:

1. At most one active PR per specialist role.
2. Global cap on simultaneous agent-authored implementation PRs.
3. Reuse/repair an existing role branch before creating another.
4. Every branch must map to one issue/work unit.
5. Merge or retire branches promptly after completion.
6. Prefer consolidation mode when review/PR pressure rises.
7. Periodically audit branches created by ChatGPT scheduled tasks separately from GitHub Actions.

This separation is important when diagnosing branch growth: GitHub Actions may be read-only while external ChatGPT agents still have GitHub write authority.
