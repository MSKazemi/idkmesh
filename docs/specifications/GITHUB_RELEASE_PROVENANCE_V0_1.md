# GitHub Release Provenance v0.1

Status: experimental C14-F contract for issue #609.

## Purpose

The second-project pilot is meant to publish a normal GitHub Release whose
provenance names the exact source and the run evidence behind it. This contract
defines the **metadata record** for such a release: a deterministic, offline
binding of a proposed release (tag, target commit, distributable artifact
digests) to the public-safe run evidence (C14-D projections) that the release
references, plus draft release notes rendered from the same record.

It is a record, not an action. It creates no tag, no GitHub Release, and no
attestation, and it makes no file, network, or GitHub call.

The implementation is `idkmesh/github_release_provenance.py`; the command is
`idkmesh release-provenance`.

```python
record = build_github_release_provenance(
    projections,            # C14-D public-safe projections for the repository
    repository="owner/name",
    tag="v0.1.0",
    target_commit="<40- or 64-hex commit>",
    artifacts=[GitHubReleaseArtifact("pkg-0.1.0.tar.gz", "sha256:<hex>")],
)
json_text = render_github_release_provenance_json(record)
notes_md = render_github_release_notes(record)
```

## Command

```bash
idkmesh release-provenance --repository owner/name --tag v0.1.0 \
  --target-commit <40-hex-commit> \
  --artifact pkg-0.1.0.tar.gz=sha256:<64-hex> \
  --projection projections/run-1.json projections/run-2.json
# add --notes to print draft release-note Markdown instead of the JSON record
```

Each `--projection` is read as strict JSON (no duplicate keys, no `NaN`), at
most 500 files and 100 artifacts. The record or the notes go to standard
output; any rejected input prints `error: ...` on standard error, writes
nothing to standard output, and exits 2. Redirecting the output to a file is the
caller's decision.

## What the record contains

| Field | Meaning |
|---|---|
| `repository` | `owner/name` every projection must be for |
| `release.tag` | Proposed tag name (plain Git tag characters, no `..`) |
| `release.target_commit` | Exact 40- or 64-hex commit the release would point at, **as supplied by the caller** |
| `release.publication_state` | Always `metadata_only` |
| `artifacts[]` | Name and `sha256:<hex>` digest per distributable artifact, **as supplied by the caller**, sorted by name |
| `evidence[]` | One entry per referenced run, sorted by `run_id`: run state, WorkUnit ID/version/digest, run `source_revision`, evidence-report digest, human-decision status and record digest, candidate PR number and head SHA or bundle digest per attempt, and `projection_digest` |
| `attestation` | Fixed: `status = not_claimed`, owner C14-G |
| `claims` | Fixed all-false list of what is **not** claimed (below) |
| `authority` | Fixed all-false ceiling: the seven C14-D flags plus tag creation, release creation, and attestation |
| `record_digest` | Canonical SHA-256 over every other field |

`projection_digest` is the canonical digest of the C14-D projection. It equals
the canonical digest of the parsed `data/runs/<slug>.json` file that the C14-E
Pages site publishes for the same run, so a release entry can be matched to the
public JSON it was derived from.

The record carries **no timestamps**: the public projection has none, and none
are invented. It therefore is not a provenance timeline.

## What is explicitly not claimed

The `claims` object is fixed to `false` and the notes repeat it in prose:

- `release_published`, `tag_created`: nothing was created or published;
- `attestation_present`: no artifact attestation exists (C14-G);
- `target_commit_verified_against_git`: the commit is a caller assertion, not
  checked against any repository;
- `artifact_digests_verified_against_build`: digests are caller assertions, not
  checked against a build or an uploaded asset;
- `run_evidence_proven_contained_in_release`: referenced runs are not shown to
  be ancestors of the target commit (squash merges rewrite SHAs, so ancestry
  cannot be inferred from the projection offline);
- `functional_correctness`: a digest, a verifier recommendation, or this record
  never proves correctness.

Setting any of these to `true`, or `publication_state` to anything else, makes
the record invalid.

## Validation and safety

- Every projection is re-validated by the shared C14-D/C14-E validator
  (`validate_public_projection`, the same checks `render_github_pages_site`
  applies) before any field is copied, and must be for the stated repository.
- Run IDs, attempt IDs, WorkUnit IDs, tags, and artifact names must use a
  restricted character set (no backticks, brackets, whitespace, braces, or
  `@`), because the notes are Markdown. A projection whose run ID falls
  outside it is rejected rather than escaped.
- The validator accepts only the exact v0.1 shape: unknown keys anywhere,
  unsorted or duplicate entries, relaxed claims/authority, and a
  `record_digest` that does not match the content are all rejected, so a
  hand-built or mutated record cannot be rendered.
- Only the PR number, head SHA, and bundle digest of a candidate are carried;
  PR URLs, artifact locators, provider references, worker/verifier identities,
  logs, and prompts never reach the record.
- Output is bounded to 1 MiB (JSON) and rendered with sorted keys.

## Relationship to other C14 slices

- C14-D ([GitHub Public Evidence Projection](GITHUB_PUBLIC_EVIDENCE_V0_1.md))
  is the only evidence input.
- C14-E ([GitHub Pages Site Projection](GITHUB_PAGES_SITE_V0_1.md)) publishes
  the matching per-run public JSON. The Pages site does not render release
  records.
- C14-G (artifact attestation integration) is not built. This record only
  reserves its place as `attestation.status = not_claimed`; it never states
  that an attestation exists.
- C14-H (Pages-disabled fallback) is unaffected: this record needs no Pages.

## Non-goals

- no `git tag`, GitHub Release creation, asset upload, or GitHub API call;
- no signing keys, secrets, or attestation, and no build-provenance claim;
- no verification of the commit or artifact digests, and no computation of
  artifact digests (the caller supplies them, for example from `sha256sum`);
- no release-readiness or acceptance decision, and no gating on run state:
  runs are listed with their actual state, whatever it is;
- no timestamps and no provenance timeline.
