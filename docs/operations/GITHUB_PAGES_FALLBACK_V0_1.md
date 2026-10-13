# GitHub Pages disabled or unavailable: C14-H fallback

**Issue:** #609. **Status:** operator procedure, no live outage drill claimed.

The read-only generator in idkmesh/github_pages_site.py is optional. Site
availability is never a precondition for dispatch, verification or human
approval. Published summaries are not canonical evidence.

## Recovery checklist
1. Treat DNS errors, HTTP failures, stale revisions and missing files as a
   view outage, not proof that a run failed or succeeded.
2. Open the linked GitHub Issue and PR for the affected WorkUnit.
3. Read the durable canonical GitHub run/evidence ledger, rather than an
   ephemeral Actions artifact or cached Pages summary.
4. Bind each retained candidate to an exact source SHA and digest; inspect
   verification and independent human decision separately.
5. If durable evidence is unavailable, report EVIDENCE UNAVAILABLE; never
   interpret a previously positive Pages summary as fresh approval.
6. Restore the view only from public-safe C14-D projections after validating
   repository scope and digests. Keep secrets, prompts and raw logs private.

## Promotion fixtures
Disable Pages entirely; simulate stale site and missing ledger independently;
test that no workflow changes run authority, that old data cannot appear as
current and that restricted evidence cannot enter the public rebuild.

**Remaining:** execute and retain an outage drill. No publication or site
configuration operation is performed by this document.


## Offline fallback manifest

`build_github_pages_outage_fallback(public_projection, repository=...)`
in `idkmesh.github_pages_site` now returns a deterministic, read-only
summary of the exact source revision, WorkUnit/evidence/decision digests, and
canonical candidate PR links already present in a public-safe C14-D
projection. The returned `canonical_evidence_availability` is always
`unverified`: the helper performs no GitHub or ledger read and never
claims an old cached view is fresh. Negative tests prove that altered privacy
policy and cross-repository links fail validation, and that generating the
fallback cannot mutate the supplied projection.

It is an **offline locator**, not a health probe, durable evidence store, or
automated Pages publication/recovery workflow. Owner-run outage exercises
remain necessary before C14-H is declared complete.
