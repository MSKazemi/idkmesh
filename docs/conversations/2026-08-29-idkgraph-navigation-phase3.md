# Conversation record — IDKGraph P1 Phase 3 bounded-corrections arc

**Date:** 2026-08-29
**Repository:** `MSKazemi/idkmesh`
**Continues:** [Solve all open issues and pull requests](2026-08-29-solve-all-open-issues-and-prs.md)

## Instruction

The project owner asked to solve all open issues and pull requests and merge to
`main` with high quality, in parallel where possible.

The predecessor record covers the triage: 21 open issues audited against their own
acceptance criteria, and the conclusion that none could be truthfully closed. That
conclusion is unchanged. This record covers what was done next — the work that was
actually available.

## What was selected and why

Issue #152 was the only open issue whose remaining work is deterministic,
in-repository, reviewable, and inside the hard zero-cost compute rule. Its Phase 3
asks for bounded corrections: small explicit links or index updates for confirmed
navigation gaps, one cohort at a time, each with a measured observatory delta.

Five passes were merged, each one directory cohort or one mechanism.

## Result

| Pull request | Cohort | orphan | notice |
|---|---|---:|---:|
| #326 | `docs/findings/` (15 documents) | 26 -> 16 | 11 -> 9 |
| #327 | `docs/audits/` (10 documents) | 16 -> 9 | 9 -> 9 |
| #328 | `docs/community/` (12 documents) | 9 -> 5 | 9 -> 5 |
| #329 | index-drift guard and repair | 5 -> 3 | 5 -> 4 |
| #330 | three residual documents | 3 -> 0 | 4 -> 4 |

Deterministic errors were 0 at every step. For each pass the resolved findings
were exactly that cohort's own findings; nothing else moved and nothing was added.

## The finding worth keeping

The deterministic observatory has a structural blind spot. It reports a document
only when **no** inbound Markdown link exists anywhere in the repository, so a
document that is linked from some unrelated page but missing from its own
directory index is invisible to it.

Five documents had drifted out of the `docs/specifications/` and `docs/research/`
indexes exactly that way. Two of the five had never been flagged by any
observatory run.

The response was a test rather than another index:
`tests/test_documentation_directory_index.py` asserts, for each directory whose
README claims whole-directory coverage, that the index exists, every document is
linked, no link dangles, and nothing is linked twice. It was verified failing
against the unrepaired tree — naming exactly those five documents — before the
repair, and is wired into the observatory workflow beside the conversation-index
guard.

This is the same defect class that produced the conversation-index guard earlier
in the project. Index drift recurs; it needs a mechanism, not a repair.

## What was deliberately not done

- The archive rule in `docs/README.md` was preserved. Every cohort was justified
  on a defect other than the warning count, and the four remaining notices —
  documents owned by the workflows that execute them — were left standing rather
  than given manufactured inbound links.
- ADR-0011 was left untouched. Its backticked repo-relative path is what creates
  the typed `implements` edge, so converting it to a Markdown link would clear a
  warning by changing edge semantics.
- No document anywhere was moved, renamed, deleted, reclassified in its own text,
  or given new authority. No detector rule was changed or weakened.
- Cross-references in the new indexes were restricted to citations that already
  exist in the referenced document or issue. Associations that looked plausible
  but were not written down were dropped rather than asserted.
- No issue was closed. Issue 152 in particular stays open: this work was
  authored and verified by the same actor, and the independent human review that
  gates it is a separate issue.

## Verification

Every pass ran the full suite and the deterministic link gate on a clean worktree
before pushing, and every exact-head check passed before merge. The suite grew
from 732 tests and 72 subtests to 736 and 96. `main` was verified green after each
merge.
