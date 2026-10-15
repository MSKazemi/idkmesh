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
file, network, GitHub, verification, decision, or repository mutation. A
separate step decides whether and where to write it: the local-directory writer
below, or a later publication step (not part of this slice).

## Writing the site to a local directory

```bash
idkmesh pages-site --repository owner/name \
  --projection projections/run-1.json projections/run-2.json --out site
```

The implementation is `idkmesh/github_pages_writer.py`
(`write_github_pages_site(files, out_dir, force=False)`), driven by
`idkmesh pages-site`. The command reads each `--projection` file as strict JSON
(no duplicate keys, no `NaN`), at most 500 files, passes them through
`render_github_pages_site` (which re-validates every projection through the
C14-D renderer first), and writes exactly the returned files. It adds no
manifest, marker, or other file. `--json` prints the repository, output
directory, and per-file size and SHA-256. It makes no network or GitHub call and
does not publish: copying the directory to a Pages branch or artifact is a
separate, not yet built step.

Write guarantees:

- Every path in the map is re-checked: relative, `/`-separated, each segment
  `[A-Za-z0-9_][A-Za-z0-9_.-]*` (or exactly `.nojekyll`), at most 256 bytes,
  no case-insensitive duplicates, no path that is both a file and a directory
  prefix, at most `2 + 2 * 500` files and 8 MiB. Absolute paths, `..`, `.`,
  backslashes, drive letters, and NUL are refused before any write.
- All files are written into a fresh sibling staging directory
  (`.<name>.idkmesh-tmp-<random>`) with exclusive creation and then moved to
  the target with a rename. Any failure removes the staging directory; a
  failed swap restores the previous directory. Files are never written through
  an existing path, so planted symlinks inside the target are never followed.
- The `--out` directory itself must not be a symlink, and its parent must
  already exist.
- A missing or empty `--out` is accepted. A non-empty directory is replaced
  without `--force` only if it is recognisably a site this command produced:
  exactly the generated layout (`.nojekyll`, `index.html`, `runs/<16 hex>.html`,
  `data/runs/<16 hex>.json`), no symlinks, and an `index.html` carrying the
  generated `noindex` meta tag and disclaimer. Anything else is refused and left
  untouched.
- `--force` replaces any other directory, except the filesystem root, the
  current directory and its ancestors, the home directory and its ancestors,
  and any directory containing `.git`. It deletes the old contents.

Residual risk: another process swapping `--out` between the check and the
rename is not defended against.

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
surfaces remain the source of truth (the offline fallback is C14-H, see
[the fallback procedure](../operations/GITHUB_PAGES_FALLBACK_V0_1.md)).

The caller, not this module, must establish that the repository and data are
public before building the C14-D projections.

## Non-goals

- no publication step, workflow, or GitHub API call (the local writer above
  only writes a directory);
- no provenance timeline (the public projection carries no timestamps, so none
  is invented);
- no JavaScript, search, or interactive filtering;
- no release or attestation metadata on the site (the offline release record is
  [GitHub Release Provenance](GITHUB_RELEASE_PROVENANCE_V0_1.md), C14-F;
  attestation is C14-G, not built);
- no functional-correctness claim from publication.
