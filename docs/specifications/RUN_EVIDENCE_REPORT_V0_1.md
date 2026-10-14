---
description: "Run Evidence Report v0.1: one human-readable view of a multi-attempt run that keeps worker self-reports, verifier evidence, and disagreement separate."
---
# Run Evidence Report v0.1

**Status:** Experimental product-facing aggregation layer  
**Related:** #4, #5, #16, PR #72, PR #78, `schemas/result-manifest-v0.1.schema.json`, `schemas/verification-result-v0.1.schema.json`, `schemas/human-decision-record-v0.1.schema.json`

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

## Registering a result-only worker adapter

`experiments/two_attempt_orchestrator.py` ships three built-in worker adapters: `fixture-result`, `result-bundle` and `fixture-failure`. A fourth can be added from outside that module, with no coordinator edit, by registering it before the config that names it is validated:

```python
import two_attempt_orchestrator as orch

orch.register_adapter("my-bundle-source", MyBundleSource())
record = orch.run_config(config_path)   # config attempts may now use worker_adapter "my-bundle-source"
```

The API is `register_adapter(name, adapter)`, `unregister_adapter(name)` and `reset_registered_adapters()` (drops everything but the built-ins; intended for tests). `ADAPTER_CONTRACT` carries the contract below as data.

**What an adapter is.** A result collector, not a worker runtime. It receives a copy of one attempt specification from the orchestration config and returns `CollectedCandidate(result_manifest_path, candidate_root)`, both inside the repository, pointing at an already-produced ResultManifest and candidate bundle. It may raise `WorkerAttemptError` for an expected failure, which is recorded as a `worker_error` attempt without stopping its peer. A return value of any other type is also recorded as `worker_error`. The coordinator, not the adapter, loads the ResultManifest and routes it to the existing independent verifier, so the run record, evidence report and replay machinery need no change.

**What an adapter must not do.** It carries no canonical-write, push, merge or candidate-selection authority, and the run record's `authority` block stays fixed. It must not execute commands or open network connections inside this seam. This is a contract, not a sandbox: Python cannot confine an in-process callable, and the registry does not make any host execution safe. Anything that would execute a candidate belongs behind the [local agent execution boundary](LOCAL_AGENT_EXECUTION_BOUNDARY_V0_1.md), whose sandbox backend (#804) is not yet available, and must not be wired in through this seam.

**Registration rules.** `name` must be 1-64 lowercase kebab-case characters (`a-z`, `0-9`, a single `-` between parts, starting with a letter) and equal `adapter.name`; the adapter must be an instance with a `collect(spec)` method. A built-in or already registered name raises `ValueError`; nothing is overridden silently, and built-ins cannot be unregistered.

**Replay.** A run record stores only the adapter name, not the adapter. Replay re-runs the saved config, so a registered adapter replays to the same digest, provided it is deterministic and is registered in the replaying process first. If it is not, `validate_config` refuses the config with `unsupported worker_adapter '<name>'` and replay fails closed rather than falling back to saved metadata, which would let a replay pass without re-collecting anything. `replay_run.py` recomputes each raw VerificationResult sidecar from the attempt's own `result_manifest` and `candidate_root` keys, not from the adapter, so an adapter that returns any other location should not set those keys (no sidecar is then captured for that attempt, and the run record and report are still compared).

**Scope.** Registration is process-local and in-process: it is a Python seam, and nothing loads adapters from a config, a plugin directory or an entry point. The `idkmesh local-loop` command therefore only accepts the built-in names unless the calling process registers more first.

**Relationship to the connector registry.** `idkmesh/connector_registry.py` registers connector drivers keyed by connector kind and driver id for routing and capability declaration; it never collects results or runs a worker. This seam is the separate result-collection layer: an adapter is selected by a config's `worker_adapter`, a driver by a connector profile. The two share conventions (explicit registration, duplicates refused, stable error words such as `duplicate_adapter`) but not a protocol, and neither implies the other.

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

## Recording the human decision

The generated report's `human_decision` object is advisory data a human *reads*: it carries the machine-suggested `selected_attempt_id` and a `recommendation` from `{accept_candidate, reject_candidate, escalate, insufficient_evidence}`, and it is required to stay `{"status": "pending", "selected_attempt_id": null, ...}` on every generated report (see Invariants above). Nothing above records that a human actually looked at the evidence and decided.

`experiments/record_human_decision.py` closes that recording gap without granting the report itself, or the decision record, any new authority:

```text
run evidence report (read-only aggregation, human_decision always pending)
 -> experiments/record_human_decision.py record
 -> idkmesh-human-decision-record (schemas/human-decision-record-v0.1.schema.json)
```

The recorded decision:

- names the exact evidence report it decides on by `kind` + `schema_version` + `run_id` + a `canonical_digest` of the full report document, not by filename -- a decision record verified against a swapped, edited, or regenerated report at that same path fails closed;
- requires an explicit human choice from `{accept, reject, escalate}`, a distinct vocabulary from the report's own `recommendation` values, so a decision record can never be produced by simply echoing the machine-suggested recommendation;
- carries a free-text `rationale` and a `decider` identity, and is timestamped;
- is written as a new companion file under `results/`; it never mutates the evidence report it decides on.

CLI:

```bash
python experiments/record_human_decision.py record \
  --evidence-report results/orchestration/demo.evidence.json \
  --output results/orchestration/demo.decision.json \
  --decision-id orchestration/demo.decision.001 \
  --decision accept \
  --rationale "attempt-001 passed independent verification with all required checks." \
  --decider-id you@example.com \
  --selected-attempt-id attempt-001

python experiments/record_human_decision.py verify \
  --decision-record results/orchestration/demo.decision.json \
  --evidence-report results/orchestration/demo.evidence.json

python experiments/record_human_decision.py self-test
```

`record` refuses (non-zero exit) a malformed/nonexistent evidence report, a decision value outside `{accept, reject, escalate}`, or a `--selected-attempt-id` that does not appear in the referenced report's attempts. `verify` re-derives the report's digest and fails closed the moment it no longer matches the digest recorded in the decision.

Like the report itself, a decision record carries `authority: {canonical_state_write: false, git_push: false, merge: false}`: it documents that a decision was made, it does not execute it. Acting on the decision (a merge, a push, a state change) remains a separate, out-of-band step.

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
