# Power-of-d Scheduling Under Churn

Status: experimental benchmark for issue #31.

This benchmark asks a narrow question that matters for IDKMesh scale:

> Can a scheduler using only a few random load observations retain useful load balance and resilience under heterogeneous workers and churn, while avoiding the coordination cost of a global least-loaded scheduler?

It is a synthetic experiment, not evidence that a particular policy will be best in production.

## Policies

The benchmark currently compares:

1. `random` — one random worker, with no dynamic load lookup;
2. `power-of-two` — sample two workers and choose the lower observed load;
3. `power-of-three` — the same idea with three samples;
4. `capability-power-of-two` — restrict the sample to workers that advertise the task capability;
5. `global-least-loaded-oracle` — inspect all workers' current availability/capability/load and choose the least loaded eligible worker.

The oracle is deliberately treated as a **high-information reference**, not a free baseline. Its `metadata_reads` cost is O(N) per assignment, while power-of-d uses O(d) dynamic load reads.

## Replayable trace

A `TraceSpec` contains:

- seed;
- worker count;
- number of arrival steps;
- base arrival rate;
- burst probability and multiplier;
- churn probability.

Worker capacities/capabilities, task arrivals, and worker availability are derived deterministically from this compact specification. This avoids materializing an O(workers × steps) availability matrix and makes 100k-worker experiments possible without enormous trace files.

Save and replay exactly the same trace:

```bash
python -m randomness_lab.scheduling \
  --workers 1000 \
  --steps 100 \
  --seed 42 \
  --trace-output results/scheduling-trace.json \
  --output results/scheduling-all.json

python -m randomness_lab.scheduling \
  --trace-input results/scheduling-trace.json \
  --policy power-of-two \
  --output results/scheduling-power-two.json
```

The result includes a SHA-256 digest of the trace specification. Every policy in one comparison receives the same trace.

## Environment

Synthetic workers vary in:

- service capacity;
- CPU/GPU capability set;
- current availability under churn.

Tasks vary in:

- arrival time;
- work size;
- required CPU/GPU capability.

Arrivals can be bursty. Failed routing attempts remain pending and can be retried, allowing the benchmark to report recovery after churn rather than treating every transient failure as permanent task loss.

## Stale observations

Use `--observation-lag N` to make local load observations N snapshots old.

With lag `0`, power-of-d policies see live load changes caused by earlier assignments in the same scheduling burst. With positive lag, they route from an older snapshot while actual worker load continues to change.

The global oracle always sees current simulated availability and load; that richer information is reflected in its metadata-read proxy.

## Metrics

The benchmark retains raw per-policy metrics rather than collapsing them to a single score:

- task count / completion rate;
- unfinished tasks;
- failed assignments;
- unreachable-worker assignments;
- capability mismatches;
- tasks requiring retry;
- retry recovery rate;
- mean assignment attempts per task;
- maximum and p95 queue depth;
- mean and p95 task system time;
- utilization;
- Jain fairness over completed tasks per worker;
- dynamic metadata reads;
- metadata reads per task.

`metadata_reads` is a **relative coordination-information proxy**, not measured network bytes. A later real-node experiment must measure actual control-plane bandwidth, messages, latency, and CPU overhead.

## Suggested scale sweep

Issue #31 proposes:

```text
1 -> 10 -> 100 -> 1,000 -> 10,000 -> 100,000 workers
```

Example:

```bash
for n in 1 10 100 1000 10000 100000; do
  python -m randomness_lab.scheduling \
    --workers "$n" \
    --steps 50 \
    --seed 42 \
    --churn-probability 0.05 \
    --output "results/scheduling-${n}.json"
done
```

For large worker counts, choose arrival/step settings appropriate to the machine running the simulator. Reporting a 100k-worker synthetic result must not be described as operating a real 100k-node network.

## Important comparisons

Useful experiment sweeps include:

### Churn

```text
0%, 1%, 5%, 10%, 25%
```

### Observation staleness

```text
0, 1, 2, 5, 10 steps
```

### Burstiness

Vary both burst probability and burst multiplier.

### Capability heterogeneity

Compare generic power-of-two with capability-aware power-of-two. Generic routing is intentionally allowed to produce capability mismatches so the cost of ignoring static capability information remains visible.

## What would count as evidence?

A useful result is not simply “power-of-two has a shorter queue.” IDKMesh should look for a Pareto region where a local policy maintains acceptable queue/wait/failure metrics while requiring dramatically less dynamic coordination state than the global oracle.

We should also publish regimes where power-of-two performs badly, for example under extreme staleness, capability mismatch, or pathological churn.

## Safety and scope

The benchmark:

- uses only the Python standard library;
- executes no Work Unit commands;
- uses no secrets;
- performs no network access;
- does not modify repository state while running;
- does not make autonomous scheduling decisions for real IDKMesh workers.

The current model is intentionally small enough to challenge and replace.
