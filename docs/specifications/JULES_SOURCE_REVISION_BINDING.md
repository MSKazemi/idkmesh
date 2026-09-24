# Jules trusted source-revision binding

C2 Session creation requires `ScmRevisionBinding.verified=True`, but that flag must never be set from a syntactically valid SHA alone.

The product trust chain is:

```text
authorized repository + branch + expected revision
 -> bounded GitHub ref transport
 -> GitHubBranchHeadReader
 -> exact SCM branch-head identity
 -> verify_jules_scm_revision(...)
 -> ScmRevisionBinding(verified=True)
 -> JulesSessionService.create_session(...)
```

`verify_jules_scm_revision` is a pure comparison boundary. It performs no network I/O and grants no dispatch authority. It returns a verified Jules binding only when repository, branch, and immutable revision all match the trusted SCM observation.

Repository identity is compared case-insensitively for GitHub while the authorized spelling is retained in the returned binding. Branch identity is exact/case-sensitive. Revision identity is hexadecimal and compared after lowercase normalization.

A mismatch is a `conflict`, not a successful rebind: source drift must be re-observed and explicitly admitted rather than silently changing the WorkUnit source revision.

This boundary is intentionally separate from both the GitHub reader and the Jules HTTP client so tests can prove that `verified=True` cannot arise from provider output or caller assertion alone.
