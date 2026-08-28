# Worker ResultManifest v0.1

Status: experimental contract
Tracking issue: #3

## Purpose

`ResultManifest v0.1` is the machine-readable boundary between an IDKMesh worker attempt and the rest of the coordination/verification system.

It answers:

- which Work Unit was attempted;
- which worker/adapter/model attempted it;
- what candidate artifacts were produced;
- which logs and metrics were recorded;
- how much resource was used;
- what the worker itself claims/confidently believes;
- which source revision, Work Unit, environment, and configuration produced the result;
- which artifacts should be handed to independent validators.

It deliberately does **not** answer:

> Is this candidate accepted as correct?

Acceptance belongs to independent verification and integration policy.

## Protocol separation

```text
WorkUnit
   |
   v
worker / agent / human
   |
   v
ResultManifest
(candidate artifacts + worker self-report)
   |
   v
independent verifier(s)
   |
   v
verification evidence
   |
   v
selection / integration / experiment result
```

This separation prevents a worker from becoming its own verifier.

## Required fields

### Identity

- `schema_version`
- `id`
- `work_unit_id`
- `work_unit_version`
- `attempt`

### Worker

The `worker` object records a stable worker identity/type plus the adapter used. Optional model metadata remains generic and does not put provider-specific fields in the coordinator core.

### Status and time

A worker may report one of:

- `succeeded`
- `failed`
- `error`
- `timeout`
- `cancelled`

A status of `succeeded` means only that the worker completed according to its own execution semantics. It is not an acceptance verdict.

### Candidate artifacts

Every produced artifact has:

- stable artifact id;
- artifact type;
- locator;
- SHA-256 digest;
- optional media type and description.

Artifact hashes make later verifier evidence refer to a specific candidate rather than an ambiguous mutable path.

### Logs and metrics

Logs remain references to artifacts rather than unbounded inline output. Metrics are intentionally open numeric fields because task classes will discover different useful measurements during the experimental period.

### Resources

At least wall-clock time is required. CPU time, memory, compute units, human minutes, and token counts are optional when measurable.

### Self-report

`self_report` is explicitly named to prevent confusion with independent evidence. It may contain:

- summary;
- claims;
- optional confidence plus a stated meaning.

Confidence is not trusted merely because it is numerically precise. Future experiments should evaluate calibration.

### Provenance

The manifest records:

- digest of the Work Unit actually executed;
- immutable source revision/reference;
- optional worker-configuration digest;
- environment/tool-version metadata.

### Verification request

The worker identifies which validators are expected and which produced artifact ids should be evaluated. The worker requests verification; it does not fill in the verifier's verdict.

## Negative invariant

The schema uses `additionalProperties: false` at the shared top level and intentionally defines no `accepted` field.

`examples/results/invalid-self-acceptance.result-manifest.json` contains an illegal top-level `accepted: true`. The Phase 0 validator requires that this fixture fail schema validation.

This makes the principle **worker success is not acceptance** executable in CI.

## Relationship to Experiment Result

`experiment-result-v0.1.schema.json` represents a normalized experimental run after relevant verification outcomes are known.

`result-manifest-v0.1.schema.json` represents a worker candidate before independent acceptance.

They should not be merged merely because both contain the word "result".

## Next research questions

1. Which artifact/log/provenance fields are actually needed across coding, testing, review, research, and documentation Work Units?
2. Should confidence remain in the common schema or move to an extension until calibration experiments justify it?
3. Which environment fields are sufficiently portable to standardize?
4. How should ResultManifest reference remote/content-addressed artifacts when execution becomes federated?
5. What separate `VerificationResult` / evidence schema best supports multiple independent verifiers without collapsing them into a single vote?

Changes should be driven by real worker/validator experiments rather than theoretical completeness.
