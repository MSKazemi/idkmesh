# IDKGraph P1 independent-review follow-up

Date: 2026-08-28
Repository: `MSKazemi/idkmesh`

## User direction

Continue improving IDKMesh from the current repository state.

## Repository state observed

- P0 IDKGraph Issue #20 is complete.
- PR #130 was closed unmerged because it duplicated the canonical identity layer; later T1–T5 work landed separately.
- Residual deterministic health checks landed through PR #149.
- Accepted-ADR linkage debt was reviewed and corrected through PR #155.
- A deterministic 15-item orphan-warning cohort was frozen through PR #162.
- That cohort was classified/corrected through PR #166:
  - 6 confirmed navigation gaps;
  - 7 intentional project-memory records;
  - 2 reference-evidence records;
  - 0 uncertain.
- Issue #152 remains open because automated/AI-assisted review cannot truthfully invent independent human reviewer time or independent agreement.
- Issue #35 remains an external GitHub administration gate for branch protection/rulesets before stronger autonomous writes.

## Action taken

Created a bounded independent-review experiment instead of adding more automatic repair:

- `docs/research/IDKGRAPH_P1_INDEPENDENT_REVIEW_PROTOCOL.md`
- `examples/idkgraph-p1-review-session.example.json`

The protocol freezes the same 15-item cohort, defines reviewer independence and anchoring disclosures, requires self-reported active review minutes rather than inferring attention from GitHub timestamps, and specifies descriptive agreement/action-cost metrics.

## Scientific boundary

The objective is not to maximize agreement with the original PR #166 classification. Disagreement, uncertainty, and higher review cost are valid evidence.

The first milestone is one complete eligible independent 15-item review. Further reviews should be retained rather than selectively discarded.

## Safety boundary

No automatic classification, link insertion, move, deletion, issue closure, or merge authority is added. The experiment collects review evidence only.
