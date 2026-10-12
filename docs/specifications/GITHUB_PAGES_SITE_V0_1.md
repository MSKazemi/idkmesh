# GitHub Pages Site Projection v0.1

Status: experimental C14-E contract for issue #609.

## Purpose

Give a public, non-sensitive repository an optional **read-only** static view of
its IDKMesh runs without a separate server or UI: project health, active work,
verification debt, per-run provenance, and the public JSON behind each page.

The implementation is `idkmesh/github_pages_site.py`. It is a pure function
over the C14-D projections defined in
[GitHub Public Evidence Projection v0.1](GITHUB_PUBLIC_EVIDENCE_V0_1.md); it
never reads raw provider or evidence JSON.

```python
files = render_github_pages_site(projections, repository="owner/name")
```

The result is a deterministic `path -> text` mapping. The function performs no
file, network, GitHub, verification, decision, or repository mutation. A later
publication step (not part of this slice) decides whether and where to write it.

## Generated files

| Path | Content |
|---|---|
| `index.html` | Project health counts, active work, verification debt, all runs |
| `runs/<slug>.html` | One run: provenance facts, ordered attempts, evidence summary |
| `data/runs/<slug>.json` | The exact C14-D public JSON for that run |
| `.nojekyll` | Empty marker so Pages serves the files as written |

`<slug>` is the first 16 hex characters of the SHA-256 of the run ID, so
arbitrary run IDs never become file names. Files are returned in sorted path
order and input order does not matter.

## Definitions

- **Active work**: runs whose state is not `admission_blocked`, `decided`, or
  `cancelled`.
- **Verification debt**: active runs with at least one attempt in
  `candidate_observed`, `normalized`, `verification_requested`, or
  `verification_error`, i.e. a candidate with no retained verification result.
- **Awaiting human decision**: `human_decision_status = pending`.

These are counts over published metadata. They are not a correctness,
acceptance, or readiness claim.

## Safety rules

- Every input is re-validated by the C14-D renderer (exact key whitelist, fixed
  all-false authority, fixed public privacy flags) and then value-checked here:
  digests, revisions, and every enumerated state must match their closed
  vocabulary.
- The only outbound link is a candidate pull-request URL, accepted only when it
  is the canonical `https://github.com/<repository>/pull/<n>` for the Pages
  repository and the stated number.
- All text is HTML-escaped, and `{` / `}` are emitted as character references
  so Jekyll-built Pages cannot interpret Liquid delimiters.
- Pages contain no scripts, forms, iframes, images, stylesheets links, or
  external assets, and carry `noindex`. There is no control that mutates state.
- Input must be for exactly one repository, run IDs must be unique, at most 500
  runs are accepted, and the generated site is bounded to 8 MiB.

## Authority and availability

Pages is a publication surface, never a mutation or approval surface. Dispatch,
verification, human decision, canonical-state write, Git push, integration, and
merge authority are all absent. Pages being disabled or unavailable must not
affect coordination; the canonical ledger and the GitHub issue/PR/Actions
surfaces remain the source of truth (fallback behavior is C14-H).

The caller, not this module, must establish that the repository and data are
public before building the C14-D projections.

## Non-goals

- no publication step, workflow, or GitHub API call;
- no provenance timeline (the public projection carries no timestamps, so none
  is invented);
- no JavaScript, search, or interactive filtering;
- no release or attestation metadata (C14-F, C14-G);
- no functional-correctness claim from publication.
