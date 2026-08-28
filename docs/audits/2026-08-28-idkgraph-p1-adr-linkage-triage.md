# IDKGraph P1 — Accepted-ADR Linkage Triage

**Date:** 2026-08-28  
**Issue:** #152  
**Baseline source:** PR #149 / completed P0 observatory  
**Scope:** all five `accepted_decision_without_document_link` warnings only

## Baseline

The P0 merge-state observatory reported:

- 266 typed repository nodes;
- 6 deterministic typed relations;
- 0 unexpected deterministic hard errors;
- 125 `orphan_document_candidate` warnings;
- 5 `accepted_decision_without_document_link` warnings.

This pass deliberately does **not** optimize the 125 orphan-candidate count. Those candidates require bounded sampling and human navigation review because absence of an inbound link does not prove a defect.

## Method

The residual health rule warns only when:

1. an ADR is mapped as a `decision` node;
2. its explicit `Status:` value begins with `Accepted`;
3. the deterministic T3 graph contains no `implements` edge from a mapped `document` node to that decision.

For every warning, this review asked:

- Does the ADR really have an explicit accepted status?
- Is there a current repository document that explicitly operationalizes or implements the decision?
- Is the relationship strong enough to declare deterministically without semantic inference?
- Would adding the relationship improve traceability rather than merely lower a warning count?

Only explicit current documents were accepted as implementation references. Proposed ADRs were not touched.

## Review results

| ADR | Classification | Implementation document(s) | Evidence for relationship |
| --- | --- | --- | --- |
| ADR-0004 — Verified Swarm Runner first product | Confirmed traceability gap | `docs/planning/EXECUTION_TARGET_GRAPH.md` | The execution graph defines the current bounded WorkUnit → real candidate → evaluator/verifier → multi-attempt → Evidence Report path and explicitly names Verified Swarm Runner v0.1 as target T4. |
| ADR-0006 — Zero-Project-Spend Compute | Confirmed traceability gap | `docs/architecture/RESOURCE_COMPUTE_ADMISSION.md` | The admission contract explicitly enforces the repository hard `$0` policy and states that the bridge may only reduce a concrete offer pool; it cannot create paid compute authority. |
| ADR-0007 — Verification debt/backpressure | Confirmed traceability gap | `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`; `docs/research/VERIFICATION_BACKPRESSURE_BENCHMARK.md` | The design note defines risk-weighted verification debt and RWVB, and the benchmark is the direct falsification/evaluation surface for that controller. |
| ADR-0008 — Independent evidence, not raw vote count | Confirmed traceability gap | `docs/architecture/MATHEMATICAL_EVOLUTION_KERNEL.md` | Section 3 implements reliability-weighted Bayesian/log-odds verification and equicorrelation effective sample size, explicitly extending the correlated-verifier experiments into a reusable aggregation primitive. |
| ADR-0009 — Evaluator Sovereignty | Confirmed traceability gap | `docs/research/EVALUATOR_PLAN_BINDING.md` | The document defines the schema-bound EvaluatorPlan control plane, exact WorkUnit/source binding, validator coverage, independence boundary, and content-addressed verifier configuration described by the ADR. |

## Changes made

Each accepted ADR now contains a deterministic `## Implementation references` section using repository-relative code-formatted paths understood by `tools/idkgraph_repository_mapping.py`.

No status, decision text, mathematical claim, security policy, or implementation behavior was changed.

The correction is therefore graph/provenance maintenance:

```text
current canonical document
        |
        | implements  (explicit ADR-declared relationship)
        v
accepted ADR decision node
```

## Expected deterministic effect

Before this patch:

```text
accepted_decision_without_document_link = 5
```

Expected after the canonical observatory reruns on this branch:

```text
accepted_decision_without_document_link = 0
```

That expected delta is an acceptance check, **not the reason for the edits**. The reason is that all five relationships are independently supported by current repository artifacts.

The 125 orphan candidates should remain essentially unchanged except for incidental graph/link effects from this new audit document. They are not part of this correction cohort.

## False-positive handling

No false-positive was found among the five accepted-ADR warnings in this bounded cohort: every warned ADR had a clear current implementation document but lacked the exact deterministic declaration consumed by T3.

This does **not** imply the detector has perfect precision. Issue #152 explicitly requires false-positive/intentional-warning cases to be retained when observed, especially during orphan-document sampling. This review does not suppress or reclassify any detector rule.

## Reviewer-attention note

This automated repository pass does not have a trustworthy human-review-minute measurement, so it does not invent one. Human review effort for this PR should be recorded separately if #152 uses attention cost in its final cohort analysis.

## Reproduction

Run the canonical observatory outside the scanned tree:

```bash
python tools/idkgraph_observatory.py . \
  --output-dir /tmp/idkgraph-observatory \
  --pretty
```

Then inspect `observatory.json` / `repository-health.md` and verify that:

- deterministic hard errors remain zero for the live repository;
- `accepted_decision_without_document_link` falls from 5 to 0;
- expected negative fixtures remain separately accounted for;
- orphan warnings are not bulk-suppressed.

## Next bounded cohort

Continue #152 with a deterministic sample of 10–20 orphan candidates. Classify them as real navigation gaps, intentional standalone/reference material, generated/test/example material, superseded/archival candidates, or uncertain. Apply only evidence-backed navigation/index corrections and preserve false positives.
