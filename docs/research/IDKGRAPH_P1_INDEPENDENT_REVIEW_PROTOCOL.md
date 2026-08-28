# IDKGraph P1 Independent Review Protocol

Date: 2026-08-28
Issue: #152
Status: review experiment protocol

## Purpose

Measure whether an independent reviewer agrees with the first evidence-backed classification of the frozen 15-item `orphan_document_candidate` cohort, and measure the human attention cost required to reach those judgments.

This experiment exists because automated or AI-assisted review must not invent human reviewer time, independence, or agreement.

## Frozen cohort

Use the exact cohort frozen before classification in #152 / PR #162:

- category: `orphan_document_candidate`
- sample size: 15
- public seed: `idkgraph-p1-orphans-v1`
- eligible population at freeze: 132
- frozen source revision: `d0bafb7fe64a5d15db82e721a281e0dee2d3cc30`

Candidate order:

1. `docs/conversations/2026-08-28-target-execution-convergence-followup.md`
2. `docs/community/ACE_LINEAGE_PROTOCOL.md`
3. `docs/research/R2_SCALE_REGIME_SWEEP.md`
4. `docs/findings/2026-08-28-agent-ecosystem-and-idkmesh-evolution.md`
5. `docs/conversations/2026-08-28-free-resource-mesh-integration-outcome.md`
6. `docs/conversations/2026-08-28-framework-and-multidisciplinary-collaboration.md`
7. `docs/conversations/2026-08-28-continue-ace-consolidation-and-live-capacity.md`
8. `docs/architecture/EVOLUTION_ARTIFACT_MINIMIZATION.md`
9. `docs/findings/science-blockchain-sources-2026-08-28.md`
10. `docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md`
11. `docs/conversations/2026-08-28-run-evidence-and-replay-continuation.md`
12. `docs/research/R1_SWARM_DIVERSITY_EXPERIMENT.md`
13. `docs/security/ACE_THREAT_MODEL.md`
14. `docs/conversations/2026-08-28-repository-audit-resource-contract-boundary.md`
15. `docs/conversations/2026-08-28-verification-orchestration-collaboration.md`

## Reviewer eligibility

A review counts as independent evidence when the reviewer:

- is not the author of the original cohort classification in PR #166;
- did not generate the original 15 labels being compared;
- records their GitHub identity or a stable public pseudonymous identifier;
- states whether they read the original classification before completing their own judgments.

Reading the repository itself is expected. Reading the previous classification is allowed, but must be disclosed because it changes interpretation of agreement.

## Review procedure

For each candidate, assign exactly one primary label:

- `navigation_gap`
- `intentional_memory`
- `reference_evidence`
- `uncertain`
- `other`

If `other`, provide a short label and explanation.

For every candidate record:

- confidence from 0 to 1;
- one short evidence note;
- whether a repository change is recommended;
- optional proposed change type (`link`, `index`, `move`, `archive_review`, `none`, `other`).

Do not edit the repository during the classification pass. Classification and intervention are separate stages.

## Attention measurement

The reviewer records:

- `started_at` and `completed_at` if they are comfortable doing so;
- **self-reported active review minutes** as the primary attention measure;
- optional interruption minutes separately.

GitHub issue/PR timestamps are **not** treated as active attention time. They include idle time, interruptions, and unrelated work.

The reviewer may omit wall-clock timestamps and report active minutes only.

## Independence / anchoring field

Record one of:

- `blind_to_original_labels`
- `saw_original_labels_after_own_review`
- `saw_original_labels_before_review`

The first two provide stronger independent-confirmation evidence than the third.

## Comparison metrics

Once at least one eligible review is submitted, compute only descriptive metrics initially:

### Exact agreement

`A = matches / 15`

where canonical comparison maps:

- `confirmed_navigation_gap` -> `navigation_gap`
- `intentional_project_memory` -> `intentional_memory`
- `reference_evidence` -> `reference_evidence`
- `uncertain` -> `uncertain`

### Action agreement

Collapse labels into:

- action: `navigation_gap`
- no immediate action: `intentional_memory`, `reference_evidence`
- unresolved: `uncertain`, `other`

Report the confusion matrix rather than only one percentage.

### Attention cost

Report:

`minutes_per_candidate = active_review_minutes / reviewed_candidates`

and, when a reviewer recommends corrections:

`minutes_per_confirmed_action = active_review_minutes / action_count`.

Do not interpret lower time as automatically better; rushed review may reduce accuracy.

## Stopping rule

The first milestone is **one independent complete 15-item review**.

Do not continuously resample until agreement looks favorable. If further reviewers participate, retain all eligible reviews and report them separately plus aggregate descriptive statistics.

## Anti-Goodhart constraints

- warning count is not the target;
- agreement with PR #166 is not the target;
- reviewer speed is not the target;
- no label is changed merely to increase inter-reviewer agreement;
- disagreement and uncertainty are useful evidence;
- one cohort must not be generalized to the full warning population without additional samples.

## Submission format

Use `examples/idkgraph-p1-review-session.example.json` as the structural template. A reviewer may submit the completed JSON in a PR, attach it to #152, or provide equivalent structured Markdown in the issue.

The review record must not contain secrets, private contact information, or sensitive personal data.

## Deterministic validation and descriptive scoring

After completing the JSON template, a reviewer or maintainer can validate the evidence locally without asking an automated system to reinterpret any document:

```bash
python tools/idkgraph_review_session.py path/to/completed-review.json \
  --output /tmp/idkgraph-review-metrics.json
```

The validator fails closed when the frozen cohort identity, rank/path order, reviewer disclosure, active-review minutes, finite confidence values, labels, or evidence notes are incomplete or inconsistent. The checked-in example is intentionally a template and therefore does **not** pass as completed evidence until its placeholders and timing fields are replaced by a real reviewer.

For a valid completed session, the tool reports only descriptive quantities derived from reviewer-entered data:

- exact-label agreement with the frozen PR #166 reference labels;
- the action / no-immediate-action / unresolved confusion matrix;
- reviewer label counts;
- active minutes per candidate;
- recommended-change count and minutes per recommended change when nonzero;
- an explicit disagreement list.

The tool has no document-classification model and no repair authority. It must never fill missing human judgments, infer reviewer minutes, transform disagreement into agreement, or treat agreement as correctness.

## Relationship to prior evidence

The original AI-assisted classification remains at:

`docs/audits/2026-08-28-idkgraph-p1-orphan-cohort-1.md`

That document should not be rewritten to make later reviews agree with it. New independent evidence should be appended as new artifacts, preserving provenance and disagreement.
