# Continuation: evidence aggregation fabric convergence

Date: 2026-08-28

User request: continue strengthening `MSKazemi/idkmesh` mathematically and implement the result with GitHub-native automation.

## Canonical precondition

The sharp Adversarial Evidence Envelope merged through PR #216 as:

```text
17e77b07c700afd04ce41a5ff72641653608436c
```

A direct default-branch read confirmed that exact commit as canonical `main` and still reported:

```text
protected: false
required status-check enforcement: off
```

The canonical `main` Adversarial Evidence Envelope workflow run:

```text
33204917325
```

completed successfully. Its retained artifact:

```text
9699250868
```

contains byte-identical Python 3.11 and 3.13 JSON payloads. The actual mathematical payload SHA-256 is:

```text
6290b45db8db841520f292162e1bea1cccd4da92d9424952338a733d57ecf984
```

This matches the exact PR evidence hash, so the merged implementation preserved deterministic behavior on canonical `main`.

## Concurrent architecture checked

Before #216 merged, `main` also added `docs/architecture/ALGORITHM_COLLABORATION_FABRIC.md` through PR #214. That architecture already reserves a distinct pipeline stage:

```text
verify -> aggregate evidence -> control flow -> learn -> govern/integrate
```

and explicitly states that algorithms should not negotiate one global fitness score or manufacture integration authority.

Its role table already includes correlation-aware aggregation and the Sequential Evidence Kernel, but the ACF was authored concurrently with the newer Anytime Drift Guard and Adversarial Evidence Envelope.

The clean convergence task is therefore not to replace the ACF. It is to make its **aggregate evidence** stage precise and executable using the now-canonical evidence algorithms.

## Composition problem

The repository now has several evidence channels whose numbers are not algebraically interchangeable:

```text
correlation-aware Bayesian evidence
count-contamination honest-report envelope
anytime sequential confidence sequence
temporal change detection
provenance/discrimination checks
hard governance guards
```

A tempting but invalid design would turn them into something like:

```text
combined_confidence = posterior * contamination_score * drift_score * ...
```

No reviewed joint probabilistic model justifies that product. “No drift detected” is not a probability of correctness, and a sharp worst-case contamination interval is not a Bayesian likelihood term.

## Decision

Implement a **typed evidence lattice** rather than a scalar aggregate.

Every signal must carry:

```text
signal_id
producer
scope_id
claim_id
signal_type
observation_model
evidence_mass
uncertainty
assumptions
failure_modes
evidence_refs
source_revision
authority_ceiling
payload
```

Before composition, every channel must refer to exactly the same:

```text
scope_id
claim_id
source_revision
```

This prevents evidence from different candidates, different propositions, or stale revisions from being mixed merely because the numeric direction is favorable.

## Evidence channels

The executable composer requires:

```text
provenance
discrimination
correlation
contamination
sequential
drift
hard_guard
```

Each keeps its own model and payload.

The composer deliberately returns:

```json
{
  "composite_confidence": null,
  "scalarized_score": null,
  "double_counting_claim": false
}
```

A downstream consumer that wants a new scalar must define a separate reviewed joint model.

## Non-compensation ordering

The composer retains every detected blocker but exposes one deterministic bounded recommendation:

```text
hard guard failure
  -> guarded
invalid provenance
  -> observe_invalid_provenance
non-discriminating instrument
  -> observe_non_discriminating
low correlation-adjusted effective evidence
  -> observe_correlation_uncertainty
robust contamination rejection
  -> insufficient_support
contamination uncertainty
  -> observe_adversarial_uncertainty
drift detected
  -> observe_drift
sequential evidence not yet sufficient
  -> observe / insufficient_effect
all channels adequate
  -> experiment_candidate
```

The priority controls the recommendation only. All blockers remain in the evidence artifact so fixing the first blocker cannot hide secondary problems.

## Important mathematical separations

Correlation and contamination remain orthogonal:

```text
correlation channel:
  probabilistic evidence strength under a declared reliability/dependence model

contamination channel:
  deterministic honest-report mean range under <= f arbitrary accepted reports
```

Sequential evidence controls optional stopping under its bounded common-mean assumptions.

Drift controls temporal pooling assumptions.

None of these establishes external truth, Sybil resistance, or integration authority.

## Human-review convergence

The recently added IDKGraph human review-session validator operates one layer earlier. It validates/describes one review artifact and its provenance disclosures. The Evidence Aggregation Fabric composes several already accepted typed signals for the same exact claim/revision.

Structural validity of one review does not prove independence or immunity to arbitrary-report faults; conversely, an adversarial envelope does not validate a review's provenance.

## Executable implementation

This convergence adds:

- `scripts/evidence_aggregation_fabric.py`;
- `tests/test_evidence_aggregation_fabric.py`;
- `docs/architecture/EVIDENCE_AGGREGATION_FABRIC.md`;
- `.github/workflows/evidence-aggregation-fabric.yml`;
- this public conversation provenance record.

The tests cover all-clear nomination, hard-guard dominance, invalid provenance, non-discrimination, low effective evidence despite high posterior probability, adversarial uncertainty/rejection, drift, insufficient sequential effect, multiple blocker retention, missing channels, scope/claim/revision mismatch, duplicate channels, evidence-reference requirements, invalid decisions, and invalid effective-evidence mass.

The strongest operational output remains:

```text
experiment_candidate
```

not merge, approve, activate, write, or reset.
