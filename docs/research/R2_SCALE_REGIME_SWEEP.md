# R2 Scale and Regime Sweep

**Issue:** #31  
**Depends on:** `randomness_lab.r2`

This layer asks a different question from a single scheduling run:

> How do local randomized schedulers behave as the worker population grows, and where does limited local information stop being enough?

## Default scales

The default CLI covers:

```text
1
10
100
1,000
10,000
100,000 workers
```

This matches the scale ladder in #31.

The global least-loaded oracle performs a full required-capability-pool scan on every routing attempt. That is intentionally an O(n)-information reference. By default it runs through 10,000 workers and is marked `skipped` at 100,000 workers.

This is not a missing result: the skip is itself part of the scalability model. The 100,000-worker cell exists to exercise the O(1)-sample local policies without pretending that a full scan is an efficient decentralized option.

The threshold is configurable with `--oracle-max-workers`.

## Stress regimes

Three named presets are included.

### `fresh`

- no synthetic churn;
- current availability;
- current load;
- light burstiness.

This approximates an information-rich, stable environment.

### `moderate`

- 10% of workers receive an outage window;
- availability lag = 2 ticks;
- load lag = 2 ticks;
- moderate arrival bursts.

### `stale`

- 20% of workers receive an outage window;
- availability lag = 5 ticks;
- load lag = 5 ticks;
- stronger burstiness.

These presets change several dimensions together. They are **descriptive stress regimes**, not causal one-factor experiments. If a result changes between `fresh` and `stale`, a later controlled sweep should isolate which factor caused the change.

## Workload scaling

To keep 100,000-worker simulations computationally bounded, arrivals do not scale linearly without limit.

The first rule is:

```text
arrivals_per_tick = clamp(ceil(worker_count / arrival_divisor), 1, max_arrivals_per_tick)
```

Defaults:

```text
arrival_divisor = 1,000
max_arrivals_per_tick = 100
```

This means the very large cells are scalability/protocol-overhead probes, not saturation tests of all available worker capacity.

A later capacity-saturation experiment should scale workload intensity separately and report the cost.

## Repeated traces

`--seeds` accepts multiple trace seeds. Each worker-count/regime/seed combination creates one exact R2 trace and runs the applicable policies on that same trace.

The output retains every raw seed-level policy metric and trace digest.

Aggregates report mean/min/max across seeds for:

- completion rate;
- p95 wait;
- p95 response;
- maximum and p95 queue depth;
- failed assignments;
- unreachable and capability-mismatch failures;
- metadata probes per routing attempt;
- capacity utilization;
- Jain utilization fairness;
- churn recovery.

With two or more seeds, every numeric aggregate also reports the sample standard
deviation and a two-sided 95% Student-t interval for the mean. A one-seed run
reports both fields as `null` rather than inventing uncertainty evidence. The
interval is clipped to the metric's physical domain: zero for all reported
metrics and one for rates, utilization, and Jain fairness.

## Oracle comparisons

When the oracle is available, every local policy gets a seed-matched comparison.

The first diagnostic `loses_badly` flag is intentionally simple:

```text
oracle completion advantage >= 0.10
OR
local p95 response >= 2 * oracle p95 response
```

This is a triage signal, not a scientific significance test. Raw metrics remain authoritative.

The comparison also reports:

```text
local metadata probes / oracle metadata probes
```

This exposes the quality-versus-information trade-off directly.

A local policy may be somewhat worse in latency while using orders of magnitude less global state. Whether that is a good trade depends on the application and should not be collapsed into one undocumented scalar score.

## One-worker normalization

With one worker, the scale runner adds every task-required capability to that one synthetic worker. This prevents the 1-node baseline from being dominated by an arbitrary impossible capability mismatch.

Larger populations retain the heterogeneous capability distribution from the underlying R2 generator.

## Run the full default scale ladder

```bash
python -m randomness_lab.r2_scale \
  --worker-counts 1,10,100,1000,10000,100000 \
  --seeds 42 \
  --regimes fresh,moderate,stale \
  --ticks 30 \
  --oracle-max-workers 10000 \
  --output results/r2-scale.json
```

For a stronger repeated experiment:

```bash
python -m randomness_lab.r2_scale \
  --worker-counts 1,10,100,1000,10000,100000 \
  --seeds 41,42,43,44,45 \
  --regimes fresh,moderate,stale \
  --ticks 50 \
  --oracle-max-workers 10000 \
  --output results/r2-scale-5-seeds.json
```

The 100,000-worker runs may be materially more expensive than the smaller cells. Keep the raw configuration with every published result.

## Interpretation

The sweep is specifically designed to allow several outcomes:

1. **Power-of-two approaches oracle quality at dramatically lower metadata cost.**
2. **Capability-aware power-of-two helps while capability-oblivious sampling fails.**
3. **Staleness destroys much of the local policy benefit.**
4. **The local policy is worse in quality but still preferable because the oracle's metadata cost is unscalable.**
5. **A local policy loses badly in a rare-capability or high-churn regime.**
6. **Differences remain too small or unstable across seeds to justify a strong conclusion.**

All are useful findings.

## Remaining research gaps

The current scale sweep still does not isolate:

- capability rarity as an independent factor;
- regional/correlated failures;
- network bytes and topology;
- multi-resource matching;
- checkpointing;
- replicated tasks;
- malicious/faulty workers;
- capability-directory maintenance cost;
- true scheduler CPU/memory cost.

Those should become separate experiments rather than hidden parameters inside one opaque benchmark.

## Evidence rule

Do not claim that power-of-two is universally optimal because of its classic balls-into-bins result or because it wins one R2 cell.

IDKMesh needs the **regime map**: where the local rule works, where additional capability/state information is worth paying for, and where the assumptions behind a simple randomized scheduler fail.
