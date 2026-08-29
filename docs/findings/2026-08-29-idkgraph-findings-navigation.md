# IDKGraph Findings Navigation Pass

**Source revision:** `1021c056` (`main`)

**Scope:** `docs/findings/` only

**Related:** issue #152, Phase 3 (bounded corrections)

## Why this cohort was reviewed at all

`docs/README.md` states that for archive and evidence collections
*"category-level discoverability can be sufficient"* and that one inbound link
per archival record must not be manufactured merely to reduce a warning counter.
That rule is correct and is not being overridden here.

The defect is different. At the source revision `docs/findings/` held 15
documents with no directory index, and the collection is **not** homogeneous
archive material. It mixes documents that still state a working project
thesis — `distributed-agent-coding.md`, cited by issue #2, and
`2026-08-28-emergence-from-vague-goals.md`, cited by issue #22 — with dated
landscape studies, bounded repository-health evidence, and external source notes
that explicitly disclaim endorsement. A reader arriving at the directory listing
cannot tell which is which, and the flat date-prefixed filenames do not help.

Distinguishing current thesis from retained history is the navigation gap. The
warning delta below is a consequence of closing it, not the reason for the pass.

## Classification

All 15 documents were read and classified into four groups. The index links each
document exactly once.

| Group | Count | Basis |
| --- | ---: | --- |
| working theses and program framing | 4 | still states a position the project builds on |
| repository-health and navigation evidence | 5 | bounded issue #152 review with a measured delta |
| growth, discovery, and free-compute landscape | 3 | dated diagnosis of the project's external position |
| historical records and source notes | 3 | retained memory or external citations, not guidance |

No document was moved, renamed, deleted, reclassified in its own text, or given
new authority. No detector rule changed. No warning was suppressed.

Only three cross-references to open issues are stated, and each is a citation
that already exists in the issue body — #2, #10, and #22. Associations that
looked plausible but were not present in repository or issue text were dropped
rather than asserted.

## Measured effect

The canonical observatory was run on the source revision and on the proposed
tree, with output written outside the scanned repository:

```bash
python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-observatory --pretty
```

| Finding | Before | After |
| --- | ---: | ---: |
| `orphan_document_candidate` | 26 | **16** |
| `document_referenced_only_by_non_markdown_artifact` | 11 | **9** |
| `docs/findings/` findings | 12 | **0** |
| `accepted_decision_without_document_link` | 0 | 0 |
| unexpected deterministic errors | 0 | 0 |

The two resolved notices and ten resolved warnings are exactly the twelve
`docs/findings/` findings; no finding outside this directory changed.

## Reviewer effort and precision

Reading and classifying 15 documents took roughly 30 minutes of review effort
in this pass; those are not independent-human minutes. The
detector was accurate on this cohort: every flagged document genuinely had no
inbound Markdown link, and the two `document_referenced_only_by_non_markdown_artifact`
notices correctly identified documents reachable only from non-Markdown
artifacts. Zero false positives were observed on this rule at this revision.

That is a statement about the **detector**, not about the repository. The
repository quality question — whether these documents needed an index — was
answered separately above, and for a genuinely homogeneous archive the honest
answer would have been no.

## What this does not claim

This pass does not claim independent-human review minutes. Issue #167 remains
the separate independent-review gate for issue #152, and the author of this pass
is not an independent reviewer.
