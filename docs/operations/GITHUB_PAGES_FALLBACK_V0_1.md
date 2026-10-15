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

## Offline fallback bundle

`idkmesh pages-fallback` (module `idkmesh/github_pages_fallback_bundle.py`)
renders the **same** validated C14-D public-safe projections that
`idkmesh pages-site` renders as HTML into a self-contained directory that needs
no server, so a developer can still read a run when Pages is disabled:

| Path | Content |
|---|---|
| `README.md` | project health, active work, verification debt and all runs (same measures as the Pages index) |
| `runs/<slug>.md` | per-run provenance, attempts and evidence summary |
| `data/runs/<slug>.json` | the canonical public projection, byte-identical to the Pages file |
| `outage/<slug>.json` | the offline locator above (`canonical_evidence_availability: unverified`) |
| `MANIFEST.json` | `path`, `size_bytes` and `sha256` of every other file, plus all-false claims |

```bash
idkmesh pages-fallback --repository owner/name --projection run-1.json --out fallback
idkmesh pages-fallback --verify fallback            # read-only, exit 0 only if intact
```

Guarantees, each covered by `tests/test_github_pages_fallback_bundle.py`:

* **Untrusted text is inert.** Run, attempt and connector identifiers are
  escaped to numeric entities for HTML, Markdown syntax, autolinks (`:` and
  `.`), mentions (`@`), math and Liquid delimiters; whitespace collapses to one
  line; control and bidirectional characters are refused. Only fixed relative
  links and the canonical same-repository PR URL become links; no image or
  inline HTML is emitted.
* **Deterministic.** Sorted paths, no timestamps, no randomness: the same
  inputs give byte-identical output.
* **Fail closed.** Every projection passes the Pages validator first; a
  wrong repository, duplicate run, unknown field or oversize bundle writes
  nothing.
* **Path-safe write.** Paths are fixed relative POSIX names; the target must
  not exist or must be an empty real directory (never replaced, never a
  symlink); files are staged in a sibling directory and renamed into place.
* **Verifiable.** `--verify` checks the exact file set, sizes and SHA-256
  digests, then re-renders the bundle from its embedded projections and
  requires byte equality, so a hand-edited file fails even if its manifest
  entry was recomputed. The manifest is **not a signature**: someone who can
  rewrite the whole directory can forge a consistent bundle.

It is a view, never canonical evidence, and it grants no dispatch,
verification, human-decision, write, push, integration or merge authority.
There is no network or GitHub call and nothing is uploaded. **Wiring is a
separate reviewed change:** no workflow was added or modified, so uploading the
directory as an Actions artifact (retention-limited, therefore never the only
copy of evidence) and deciding when to run it are still open. Owner-run outage
exercises also remain necessary before C14-H is declared complete.
