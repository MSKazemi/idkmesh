# C8-E: Owner-only setup for GitHub-first bootstrap

**Issue:** #596 · **Status:** manual checklist available; no owner setup performed

The generated bootstrap file plan is not a deployment. After reviewing
`idkmesh init --github --dry-run`, an authorized repository owner must:

1. Review project and connector policy; keep secret *references*, not values, in tracked configuration.
2. Authorize only selected provider GitHub Apps with least privileges.
3. Protect the integration branch, requiring appropriate checks, approvals and force-push restrictions.
4. Create the `idkmesh-dispatch` environment with explicit reviewer approvals.
5. Put provider credentials in environment-scoped secrets or approved secret storage, never WorkUnits or logs.
6. Review the generated workflows and pin the runtime to a vetted immutable revision.
7. Confirm the pinned runtime implements `python -m idkmesh.cli github-workflow`.
   This runner does **not** exist on current `main`; the generated wrappers intentionally fail closed.
8. Record who approved each setting, the checked revision and the observed results.

The deterministic owner-action checklist can be rendered offline:

```python
from idkmesh.github_bootstrap import build_github_bootstrap_plan, render_owner_action_checklist
plan = build_github_bootstrap_plan(idkmesh_ref="a" * 40)
print(render_owner_action_checklist(plan))
```

The all-`a` SHA is a *test fixture*, not a real published runtime. Substitute a
reviewed tag or SHA during adoption.

Checklist rendering is read-only. C8-F safe apply/re-run and C8-G fresh-repo
pilot remain pending; none of these instructions claims they were performed.
