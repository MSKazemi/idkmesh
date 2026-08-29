# R1 Real-Result Replay

**Issue:** #30  
**Purpose:** Bridge the synthetic R1 experiments to actual IDKMesh worker results without creating a second competing result format.

## Inputs

The replay adapter consumes the existing Phase 0 contracts:

- `schemas/result-manifest-v0.1.schema.json` — a worker's candidate-result self-report;
- `schemas/verification-result-v0.1.schema.json` — an independent verifier's checks, findings, resource use, and decision support.

The Phase 0 schema validator remains the authoritative full JSON-Schema validator. `randomness_lab.r1_replay` performs additional R1-specific normalization and conservative evidence filtering after schema-valid records are produced.

## Trust boundary

A `ResultManifest` is **not truth**. The replay code does not infer correctness from:

- worker status alone;
- worker self-reported confidence;
- artifact presence;
- model identity;
- popularity or repeated output.

A candidate becomes conclusive for R1 only when at least one `VerificationResult` declares `independence.independent_from_worker: true` and the available independent evidence resolves to acceptance or rejection.

### Conclusive good

A candidate is counted as independently verified good only when:

- the worker result status is `succeeded`;
- every independent verification used by the replay has status `passed`;
- every independent verifier recommends `accept_candidate`;
- no required independent check is failed or errored.

### Conclusive bad

A candidate is counted as bad when any independent verifier supplies a clear rejection signal:

- verification status `failed`;
- recommendation `reject_candidate`;
- a required check with status `failed` or `error`.

### Inconclusive

No independent verifier, conflicting evidence, escalation, or insufficient evidence is **excluded**, not guessed. The report publishes exclusion counts.

This is intentionally conservative: unknown is not converted into failure or success merely to make a comparison easier.

## Structural diversity signature

R1 needs to compare repeated instances of one structure with candidates from different structures.

By default a structural signature is derived from the worker metadata:

```text
worker.type
+ worker.adapter
+ model.provider
+ model.name
+ model.version
```

A real experiment can override this with:

```json
{
  "extensions": {
    "r1_structural_signature": "planner:gpt-x|coder:model-y|tools:test-first"
  }
}
```

The override exists because meaningful structural diversity may include prompt strategy, role composition, toolchain, organization, or orchestration topology that cannot be inferred from the base v0.1 worker fields.

The replay report records both the signature and how it was obtained.

## Fixed-budget comparison

For swarm size `N`, a work unit is eligible only when it has:

1. at least `N` conclusive candidates from the baseline structural signature; and
2. at least `N` distinct structural signatures with conclusive candidates.

Each bootstrap sample compares equal candidate counts:

```text
replication:
  N candidates from the baseline signature

structural diversity:
  N distinct signatures
  one candidate sampled from each
```

This prevents an apparent diversity advantage caused solely by giving the diverse condition more attempts.

If `--baseline-signature` is omitted, the adapter chooses the signature covering the most work units with at least `N` replicas, then the most total candidates, with a deterministic tie-break. For a serious experiment, record and normally specify the intended baseline explicitly.

## Real metrics

The replay computes from actual supplied records:

- independently verified candidate success;
- independent-test coverage;
- regression findings;
- security findings;
- observed wall-clock proxy;
- compute units when recorded;
- human minutes when recorded;
- normalized utility per resource cost when resources are complete;
- structural-signature failure correlations on overlapping work units.

### Missing resources are not zero

If a selected candidate omits `compute_units` or `human_minutes`, the cost-based metric for that bootstrap trial becomes unavailable. The replay does not silently treat missing resource measurements as free work.

`--human-minute-cost-weight` is an explicit analysis coefficient in:

```text
normalized cost = compute_units + weight * human_minutes
```

It is **not** a currency conversion or economic claim. Reports must preserve the configured value.

## Bootstrap and classification

Eligible work units are resampled with replacement. Candidate selection inside each work unit is also sampled reproducibly from the recorded candidate pools.

For each bootstrap trial the replay stores signed deltas:

```text
structural diversity - replication
```

For verified success and, where resource data is complete, verified utility per normalized cost.

The empirical 2.5th and 97.5th percentiles form a descriptive bootstrap interval:

```text
interval entirely > 0 -> helps
interval entirely < 0 -> hurts
otherwise              -> uncertain
```

Raw bootstrap trials remain in the report.

## Failure correlation

For each pair of structural signatures, the replay reports:

- count of overlapping work units;
- Pearson correlation of binary failure on the first conclusive attempt per signature/work unit, when mathematically defined.

This is observational. A low measured correlation can make diversity more useful, but correlation itself does not prove causal independence.

## Run

Inputs may be JSON arrays, single JSON objects, JSONL files, or directories recursively containing `.json`/`.jsonl` files.

```bash
python -m randomness_lab.r1_replay \
  --results path/to/result-manifests/ \
  --verifications path/to/verification-results/ \
  --swarm-size 2 \
  --trials 500 \
  --seed 42 \
  --baseline-signature 'agent|adapter|provider|model|version' \
  --output results/r1-real-replay.json
```

Before replay, validate records through the Phase 0 schema workflow/harness.

For a BenchmarkCohort-backed real experiment, also run the fail-closed
readiness audit documented in
`docs/research/R1_CORPUS_READINESS.md`. The readiness command validates the
cohort/evidence bindings and checks the held-out task count, exact signature
budget, independent-test coverage, negative retention, and cost completeness
without changing this replay's decision rules.

## What replay can and cannot establish

Replay is stronger than synthetic probability assumptions because it uses measured outcomes from actual candidate artifacts and actual independent verification records.

But it remains **observational**. It can still be confounded by:

- harder tasks being routed to particular models;
- different compute budgets;
- different prompts or context windows hidden behind one signature;
- learning/order effects across attempts;
- selective retention of successful artifacts;
- verifier selection differences;
- benchmark leakage;
- incomplete resource accounting.

Therefore replay should be followed by a prospectively designed, held-out experiment where candidate generation budgets, task assignment, and verification policies are fixed before results are seen.

## Minimum useful real corpus for R1

For swarm size 2, a practical first corpus should include multiple held-out work units where each has:

- at least 2 conclusive attempts from the chosen replication baseline;
- at least 2 distinct structural signatures;
- independent verification for every included candidate;
- independent/hidden tests where applicable;
- compute and human-attention measurements when cost comparisons are intended;
- retained negative and failed results, not only successful candidates.

The project should publish the normalized replay report and the underlying non-sensitive evidence/provenance needed to reproduce it.

## Next step

Collect the first real R1 corpus from bounded coding tasks produced by the Verified Swarm Runner / Phase 0 harness, validate the manifests, run this replay unchanged, and publish the resulting help/hurt/uncertain map. Do not tune the replay rules after seeing the benchmark outcome without recording the change as a new analysis version.
