# IDKGraph orphan-warning triage — cohort 001

Evidence for issue #152, Phases 1–3. Read-only observatory analysis followed by one
bounded correction.

- Source revision: `a37be5d6c741ae61377d7873ec7bb9dd14a4cc58`
- Cohort seed: `idkmesh-152-phase1`, sample size 15, category `orphan_document_candidate`
- Reproduce:

```bash
python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-observatory --pretty
python tools/idkgraph_warning_sample.py . \
  --category orphan_document_candidate --sample-size 15 \
  --seed idkmesh-152-phase1 --output /tmp/cohort.json --pretty
```

## The baseline in #152 no longer describes the repository

| Metric | #152 baseline (PR #149) | Observed at `a37be5d` |
|---|---:|---:|
| typed repository nodes | 266 | 362 |
| `orphan_document_candidate` | 125 | 176 |
| `accepted_decision_without_document_link` | 5 | **0** |

Phase 2 of #152 is therefore empty at this revision: there are no accepted-decision
linkage warnings left to review. The warning population is now a single category.

Two things moved the node count between those revisions: genuine repository growth, and
the discovery defect fixed in PR #225 — before that fix the graph also ingested untracked
and gitignored files, so the older figure was not reproducible across clones.

## Phase 1 — population structure

The 176 warnings are not evenly distributed. They concentrate almost entirely in one class:

| Directory | Warnings | Has index? |
|---|---:|---|
| `docs/conversations` | **113** | no |
| `docs/research` | 17 | no |
| `docs/specifications` | 11 | no |
| `docs/architecture` | 9 | no |
| `docs/findings` | 9 | no |
| everything else | 17 | — |

113 of 176 warnings (64%) were every file in `docs/conversations/`, without exception.

The structural cause is not per-document neglect: **only 2 of 17 `docs/` subdirectories had
an index README** (`docs/foundations/`, added in PR #224, and `docs/planning/`). The
repository has no directory-index convention, so whole directories orphan together.
`README.md` did link `docs/conversations/`, but as a *directory* link, which the rule
`typed_docs_document_without_inbound_local_markdown_link` correctly does not count as an
inbound link to any document.

## Phase 1 — cohort classification

12 of the 15 sampled candidates were `docs/conversations/` records, classified as one class.
The three others were checked individually for inbound references across Markdown, Python,
YAML and JSON.

| # | Candidate | Classification | Evidence |
|---|---|---|---|
| 1–6, 8–11, 13, 15 | `docs/conversations/*` (12 records) | real navigation gap, systemic | no index existed for 113 append-only records; reachable only by directory listing |
| 7 | `docs/interoperability/A2A_MCP_MAPPING_V0_1.md` | real navigation gap | zero inbound references of any kind, repository-wide; supports IDKIP-0001 (#17) |
| 12 | `docs/research/R1_HELP_HURT_SWEEP.md` | real navigation gap | zero inbound references of any kind |
| 14 | `docs/research/PHASE_B2_V2_TASK002_NONFINITE_ROUTER_CALIBRATION.md` | **false positive — retained** | not orphaned: owned and referenced by `.github/workflows/phase-b2-v2-task002-calibration.yml` |

Reviewer effort: ~25 minutes, dominated by per-candidate inbound-reference checks rather
than by judgement. Ambiguity was low because the dominant class was homogeneous.

### Retained false positive — detector precision, not repository quality

Candidate 14 is the important one. The rule considers only inbound **Markdown** links, so a
document owned by a workflow, script, or schema looks identical to an abandoned one. It is
reachable, maintained, and executed against — and still warns.

This is a precision limit of the detector, not debt in the repository. It is retained
deliberately, per #152's acceptance criteria, and **not** corrected.

Recommended rule refinement, for review rather than immediate implementation: treat a
document referenced from a non-Markdown repository artifact (workflow, script, schema) as
non-orphaned, and report that as a distinct lower-severity category. Implementing this
changes detector semantics and should carry its own deterministic fixture reproducing
candidate 14, so it is proposed here rather than bundled into this correction.

## Phase 3 — one bounded correction

Scope: `docs/conversations/` only — the single largest coherent class. No other directory
was touched, nothing was moved, deleted, or archived.

Added `docs/conversations/README.md`: a dated index of all 113 records with a scope note
explaining that they are append-only historical evidence, not living documentation.
`README.md`'s existing directory link now points at that index.

Measured on a clean worktree at `a37be5d`, with and without this change:

| Metric | Before | After |
|---|---:|---:|
| typed nodes | 362 | 364 |
| `orphan_document_candidate` | 176 | **64** |
| `docs/conversations` warnings | 113 | **0** |

The correction clears 113 warnings and adds one: `docs/findings/` has no index either, so
this report is itself an orphan candidate the moment it lands. That is left standing on
purpose. It is the cleanest available demonstration that the population is driven by the
missing directory-index convention rather than by per-document neglect — and a direct check
on whether this work was optimizing the number, which it was not.

### Why this is a navigation fix and not warning-count optimization

A directory holding 113 records with no entry point is a real navigation gap: a reader
arriving from `README.md` previously got a raw file listing with no dates, titles, or
statement of what the directory is for. The index answers those questions, and it is the
remedy #152's Phase 3 explicitly prefers ("small explicit links or index updates over bulk
restructuring").

The warning delta is a consequence of that fix, not its objective. The evidence for the
distinction is that the largest remaining classes — `docs/research` (17),
`docs/specifications` (11), `docs/architecture` (9) — were left untouched even though the
same one-file remedy would clear them. They need their own classification pass first, and
the retained false positive above was deliberately not "fixed" at all.

## Status against #152's acceptance criteria

- [x] No automatic mass linking, deletion, moving, or archiving — one index, one directory
- [x] Warning count not used as a standalone optimization objective
- [x] At least 10 orphan candidates evidence-classified — 15
- [x] All accepted-decision linkage warnings reviewed — the category is empty at this revision
- [x] At least one false-positive/intentional-warning case retained — candidate 14
- [x] Before/after observatory output and reviewer-effort evidence recorded
- [x] Final report distinguishes detector precision from repository quality
- [ ] Rule refinement backed by a deterministic fixture — **proposed, not implemented**

## Remaining, deliberately not done here

- 64 warnings remain, concentrated the same way: `docs/research` 17,
  `docs/specifications` 11, `docs/findings` 10, `docs/architecture` 9, `docs/community` 5,
  `docs/audits` 4, and 8 singletons elsewhere. Each directory needs its own bounded pass;
  the same one-file index remedy is likely to apply, but that should be established by
  classification rather than assumed from this cohort.
- The independent human review of this cohort is issue #167, which is the evidence gate for
  #152. This report is input to that review, not a substitute for it.
