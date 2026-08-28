# Run Evidence Report v0.1

**Status:** Experimental product-facing aggregation layer  
**Related:** #4, #5, #16, PR #72, PR #78, `schemas/result-manifest-v0.1.schema.json`, `schemas/verification-result-v0.1.schema.json`

## Purpose

The Verified Swarm Runner needs one place where a human can inspect the evidence from a multi-attempt run without collapsing worker claims and verifier evidence into a vote.

The current canonical trust pipeline is:

```text
WorkUnit
 -> worker attempt
 -> ResultManifest (worker self-report)
 -> independent verifier
 -> VerificationResult (evidence + recommendation)
 -> human / governance integration decision
```

`Run Evidence Report v0.1` is a **read-only aggregation view over that pipeline**. It does not replace any canonical protocol object above and does not recreate the closed candidate-level Evidence Report proposal from PR #42. The independent verifier protocol is `VerificationResult v0.1`.

The report answers a narrower product question:

> What happened to every attempt in this run, what independent evidence exists for each attempt, where do verifiers disagree or fail, and is the saved run reproducible?

## Invariants

A generated report MUST preserve these boundaries:

```text
worker success != verified correctness
verifier recommendation != integration decision
multiple recommendations != majority truth
report generation != candidate selection
replay equality != correctness
```

The generated report therefore has:

```json
{
  "human_decision": {
    "status": "pending",
    "selected_attempt_id": null,
    "integration_authority": "external_human_or_governance"
  },
  "authority": {
    "canonical_state_write": false,
    "git_push": false,
    "merge": false,
    "automatic_candidate_selection": false
  }
}
```

A later human/integration-decision record may refer to this report, but the generated report itself cannot be mutated into acceptance authority.

## Inputs

The first implementation consumes the deterministic run record emitted by:

`experiments/two_attempt_orchestrator.py`

That run record already retains:

- exact WorkUnit digest;
- exact orchestration config digest;
- verifier-policy digest;
- attempt order;
- worker adapter and ResultManifest identity/digest;
- independent verifier identity;
- VerificationResult semantic digest;
- VerificationResult binding to WorkUnit + ResultManifest;
- independent check status and recommendation;
- worker/result/verifier control failures;
- an explicit no-write/no-merge/no-selection authority block.

Before rendering, `run_evidence_report.py` validates those relationships again and fails closed on binding drift.

In particular:

```text
VerificationResult.result_manifest_digest == summarized ResultManifest digest
VerificationResult.work_unit_digest == run WorkUnit digest
```

If either relationship is inconsistent, no report is produced.

## Evidence states

Every attempt is mapped to exactly one report state:

| Evidence state | Meaning |
| --- | --- |
| `supported` | independent verifier recommendation is `accept_candidate` |
| `rejected` | independent verifier recommendation is `reject_candidate` |
| `inconclusive` | verifier says `escalate` / `insufficient_evidence`, or no conclusive recommendation exists |
| `worker_error` | worker adapter failed before producing usable candidate evidence |
| `result_manifest_error` | candidate ResultManifest could not be collected/parsed |
| `verification_error` | candidate exists but verifier control path failed |

The report never silently drops an errored attempt. One failed worker must not erase the evidence produced by a surviving peer.

## Disagreement

`verification_disagreement=true` when the run contains more than one distinct independent verifier recommendation.

Example:

```text
attempt A -> worker says succeeded -> verifier says accept_candidate
attempt B -> worker says succeeded -> verifier says reject_candidate
```

The correct product behavior is:

```text
preserve both histories
 -> show disagreement
 -> leave integration decision pending
```

not:

```text
count votes -> choose winner
```

This becomes more important later when verifier failures are correlated. IDKMesh already has research showing that raw verifier count is not equivalent to independent evidence.

## Deterministic replay

Replay is a provenance/reproducibility check, not a correctness proof.

For a saved deterministic run record `R` and its replayed record `R'`:

```text
ReplayMatch = SHA256(canonical(R)) == SHA256(canonical(R'))
```

The current fixture orchestration has no timestamps or nondeterministic worker execution, so complete-record equality is expected.

When real workers are added, replay semantics will need to distinguish:

- exact deterministic replay;
- provenance-equivalent replay;
- semantically equivalent but byte-different results;
- intentionally nondeterministic model/agent attempts.

Do not weaken v0.1 silently. Introduce an explicit later replay mode/version when real-worker evidence requires it.

## CLI

Self-test:

```bash
python experiments/run_evidence_report.py self-test
```

Generate one deterministic run plus JSON and Markdown evidence views:

```bash
python experiments/run_evidence_report.py generate \
  --config examples/orchestration/two-attempt-good-vs-bad.json \
  --run-output results/orchestration/demo.run.json \
  --report-json results/orchestration/demo.evidence.json \
  --report-markdown results/orchestration/demo.evidence.md
```

Re-render an existing saved run:

```bash
python experiments/run_evidence_report.py report \
  --run-record results/orchestration/demo.run.json \
  --report-json results/orchestration/demo.evidence.json \
  --report-markdown results/orchestration/demo.evidence.md
```

Check deterministic replay:

```bash
python experiments/run_evidence_report.py replay-check \
  --config examples/orchestration/two-attempt-good-vs-bad.json \
  --run-record results/orchestration/demo.run.json
```

All generated files are constrained to `results/`. The tool does not write canonical repository state.

## Machine-readable contract

See:

`schemas/run-evidence-report-v0.1.schema.json`

The schema is intentionally an aggregation schema. It references digests and summaries of canonical worker/verifier evidence; it is not a second verifier protocol.

## Self-test coverage

The built-in self-test checks that:

1. known-good and known-bad attempts remain one support + one rejection;
2. support/reject disagreement is visible;
3. the human integration decision remains `pending`;
4. automatic candidate selection remains disabled;
5. a peer worker failure remains visible while surviving evidence is retained;
6. replay of the same deterministic config matches the complete saved-run digest;
7. a tampered saved run fails replay equality;
8. ResultManifest/VerificationResult digest-binding drift is rejected before report generation.

## What this unlocks

This closes one control-plane gap in #16 without pretending the real worker path is complete.

The remaining critical path is still:

```text
canonical local node (#34)
 -> controlled Docker acceptance (#37)
 -> repository-candidate verification (#5 B1 / patch verifier work)
 -> plug real node adapter into the already-landed orchestration kernel
 -> use this evidence/replay surface over real attempts
 -> add one trivial heterogeneous real adapter
```

## Non-goals

- no automatic ranking/winner selection;
- no merge or push authority;
- no new candidate-level verification protocol;
- no claim that replay implies correctness;
- no execution of candidate code;
- no replacement for `VerificationResult v0.1`;
- no majority-vote shortcut;
- no distributed scheduler.
