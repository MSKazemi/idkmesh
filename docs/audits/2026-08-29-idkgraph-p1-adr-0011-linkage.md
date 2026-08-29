# IDKGraph P1 — ADR-0011 Accepted-Decision Linkage Review

**Date:** 2026-08-29
**Issue:** #152, Phase 2 (accepted-decision linkage review)
**Baseline source revision:** `7f28bc3c1b` (`main` after PR #321 and PR #322)
**Scope:** the single current `accepted_decision_without_document_link` warning

## Why this is a separate record

The original Phase 2 pass is recorded in
[`2026-08-28-idkgraph-p1-adr-linkage-triage.md`](2026-08-28-idkgraph-p1-adr-linkage-triage.md).
It reviewed the five warnings present in the #149 baseline and drove that count to
zero. That record is **not** edited here; it remains a reproducible snapshot of the
state it reviewed.

This is a continuation pass for one warning that appeared afterwards.

## Observed baseline drift

The #152 issue text describes a 2026-08-28 baseline of 125 `orphan_document_candidate`
and 5 `accepted_decision_without_document_link` warnings. Rerunning the canonical
observatory at `7f28bc3c` gives a materially different picture:

```text
orphan_document_candidate                        = 27
accepted_decision_without_document_link          =  1
document_referenced_only_by_non_markdown_artifact = 11
deterministic hard errors                        =  0
```

The reduction is the cumulative effect of the already-merged cohort-1 and
architecture/conversation navigation passes, not of this change. The issue text's
counts should be read as historical, not current.

## The warning under review

```text
source_id:   decision:ADR-0011
source_path: docs/decisions/ADR-0011-discovery-surface-completion.md
rule:        accepted_adr_without_document_implements_edge
status:      Accepted
```

ADR-0011 was merged by PR #320 earlier the same day. It carries an explicit
`**Status:** Accepted` and had no `## Implementation references` section, so the
deterministic T3 mapper created no `document --implements--> decision` edge. The
detector behaved exactly as specified; this is a real linkage gap, not a
false positive.

## Classification

Applying the Phase 2 questions from the original triage:

| Question | Answer |
| --- | --- |
| Does the ADR really have an explicit accepted status? | Yes — `**Status:** Accepted`. |
| Is there a current repository document that operationalizes the decision? | Yes — `docs/PAGES_SETUP.md`, the canonical discovery-surface runbook. |
| Was the relationship already explicit enough to declare deterministically? | **No.** See below. |
| Would declaring it improve traceability rather than only lower a count? | Yes. |

**Classification: confirmed traceability gap, with a genuine documentation defect
underneath it.**

The honest obstacle was that `docs/PAGES_SETUP.md` did not actually record the
decision. It lists post-activation checks for the public front door but said
nothing about whether the welcome discussion must be pinned. A reader following
the runbook could not tell that pinning is optional. Declaring an `implements`
edge to a document that did not reflect the decision would have manufactured a
graph edge to clear a warning — precisely the failure mode #152 prohibits.

## Change made

Two edits, in this order:

1. `docs/PAGES_SETUP.md` gains a short **"Welcome-discussion pinning is optional"**
   subsection recording that pin state is not independently witnessable from
   repository evidence, that a pin carries no authority/correctness/security/
   reproducibility/participation control, and that its absence does not block
   discovery-surface completion. It links ADR-0011 as the governing decision.
2. `docs/decisions/ADR-0011-discovery-surface-completion.md` gains a
   `## Implementation references` section naming `docs/PAGES_SETUP.md`.

Edit 1 is the substantive one: it makes the runbook correct. Edit 2 only declares
the now-true relationship in the form the deterministic mapper reads.

No ADR status, decision text, rationale, consequence, security policy, or
implementation behaviour was changed. No issue was closed. No document was moved,
deleted, or bulk-linked.

## Deterministic effect

Canonical command:

```bash
python tools/idkgraph_observatory.py . --output-dir /tmp/idkgraph-observatory --pretty
```

| Category | Before | After |
| --- | ---: | ---: |
| `accepted_decision_without_document_link` | 1 | 0 |
| `orphan_document_candidate` | 27 | 26 |
| `document_referenced_only_by_non_markdown_artifact` | 11 | 11 |
| deterministic hard errors | 0 | 0 |
| `implements` edges in T3 | 11 | 12 |
| total typed T3 edges | 13 | 14 |
| mapped T3 nodes | 459 | 460 |

One orphan candidate was resolved as a side effect, and it is worth naming rather
than counting: this record cites
[`2026-08-28-idkgraph-p1-adr-linkage-triage.md`](2026-08-28-idkgraph-p1-adr-linkage-triage.md)
as the prior pass it continues, which gives that record its first inbound Markdown
link. That is a byproduct of writing an honest provenance reference, not a target.
No orphan candidate was created: this record is itself linked from
[`../README.md`](../README.md), consistent with how the earlier IDKGraph P1 records
are indexed.

## Detector precision vs repository quality

These are distinct, and #152 asks that they not be conflated.

- **Detector precision:** on this candidate the rule was **correct**. It fired on a
  genuine missing relationship and produced no false positive. Its Phase 2 record
  is now 6 warnings raised, 6 confirmed traceability gaps, 0 false positives.
- **Repository quality:** the underlying defect was *not* a missing graph edge. It
  was that the discovery-surface runbook omitted a decision that governs it. The
  warning surfaced a documentation gap that a reader — not a graph — would have
  hit. That is the useful outcome; the edge is bookkeeping.

The rule's precision on accepted-decision linkage is materially better than its
precision on orphan candidates (cohort 1: 6 of 15 confirmed). The two rules should
not be evaluated, or trusted, as one detector.

## Reviewer effort

Approximately 25 minutes: reading the rule implementation in
`tools/idkgraph_repository_mapping.py` to establish the exact edge semantics,
reading ADR-0011 and `docs/PAGES_SETUP.md`, determining that the relationship was
not yet true, and recording before/after evidence.

The dominant cost was **not** the fix. It was deciding whether the relationship was
real enough to declare. A reviewer who skipped that step could have closed the
warning in about two minutes and left the runbook wrong.

## Known limitation — recurrence

Nothing prevents the next accepted ADR from reintroducing this warning; PR #320 did
exactly that. A blocking gate is deliberately **not** proposed here, because
requiring an `implements` edge before an ADR may merge would convert a warning count
into a hard optimization target and would pressure authors to declare edges to
whatever document is nearest. The observatory workflow already runs on
`docs/decisions/ADR-*.md`, so the warning is visible on the pull request that
introduces it. Visibility, reviewed case by case, is the intended control.

## What this does not resolve

Issue #152 remains open. Its outstanding evidence gate is the independent human
review of orphan cohort 1 requested in #167, which by construction cannot be
supplied by the repository owner or by automation. This pass adds no authority to
the automated classifier and makes no claim about the cohort-1 classifications.

## References

- issue #152 — IDKGraph P1 warning-debt triage
- issue #167 — independent orphan-cohort review (open evidence gate)
- PR #320 — merged ADR-0011
- [`2026-08-28-idkgraph-p1-adr-linkage-triage.md`](2026-08-28-idkgraph-p1-adr-linkage-triage.md)
- [`2026-08-28-idkgraph-p1-orphan-cohort-1.md`](2026-08-28-idkgraph-p1-orphan-cohort-1.md)
- `tools/idkgraph_observatory.py`, `tools/idkgraph_repository_mapping.py`
