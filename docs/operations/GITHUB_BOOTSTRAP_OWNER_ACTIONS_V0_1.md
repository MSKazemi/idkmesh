# C8-E: Owner-only setup for GitHub-first bootstrap

**Issue:** #596 · **Status:** manual checklist available; no owner setup performed

The generated bootstrap file plan is not a deployment. After reviewing
`idkmesh init --github --dry-run`, an authorized repository owner must:

1. Review project and connector policy; keep secret *references*, not values, in tracked configuration.
2. Set `.idkmesh/project.json` `metadata.github_issue_preview.allowed_paths` (and any forbidden paths) before expecting issue preview. The generated seed intentionally has no preview write scope.
3. Authorize only selected provider GitHub Apps with least privileges.
4. Protect the integration branch, requiring appropriate checks, approvals, and force-push restrictions.
5. Create the `idkmesh-dispatch` environment with explicit reviewer approvals.
6. Put provider credentials in environment-scoped secrets or approved secret storage, never WorkUnits or logs.
7. Review the generated workflows and pin the IDKMesh runtime to a vetted immutable revision.
8. Confirm that pinned runtime provides the `python -m idkmesh.cli github-workflow` phases the wrappers require. The current [runner contract](../specifications/GITHUB_WORKFLOW_RUNNER_V0_1.md) keeps `preview` and `status` read-only while `dispatch` and `verify` fail closed.
9. Record who approved each setting, the checked revision, and the observed results.

The canonical bootstrap plan carries these owner actions, so
`idkmesh init --github --dry-run --json` exposes them without performing
repository or GitHub mutations. The same canonical action set can be rendered
as a standalone checklist:

```python
from idkmesh.github_bootstrap import build_github_bootstrap_plan, render_owner_action_checklist

plan = build_github_bootstrap_plan(idkmesh_ref="a" * 40)
print(render_owner_action_checklist(plan))
```

The all-`a` SHA is a *test fixture*, not a real published runtime. Substitute a
reviewed tag or SHA during adoption.

Checklist rendering is read-only. C8-F safe apply/re-run and C8-G fresh-repo
pilot remain pending; none of these instructions claims they were performed.
