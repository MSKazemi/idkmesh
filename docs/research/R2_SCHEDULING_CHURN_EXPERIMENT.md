# R2 — Randomized Scheduling Under Churn

**Issue:** #31  
**Status:** Executable simulation harness

## Research question

Can a scheduler that inspects only one, two, or three local candidates achieve useful load balance and resilience without maintaining the expensive global state used by an oracle scheduler?

R2 is designed to compare both **scheduling quality** and **coordination information cost**.

A policy that produces a shorter queue only because it scans every eligible worker should not be described as free decentralization.

## Policies

The first harness implements:

1. `one-random` — sample one worker from the whole population;
2. `power-two` — sample two workers and choose the lower observed load;
3. `power-three` — sample three workers and choose the lower observed load;
4. `capability-power-two` — sample two workers from the static capability index, then choose the lower observed load;
5. `global-least-loaded` — inspect the full required-capability pool using current availability and current load; this is a **high-information reference**, not a decentralized implementation.

The local capability-oblivious policies intentionally make capability mismatch measurable. `capability-power-two` separates the benefit of a small static capability index from the benefit of globally current load state.

## Replayable trace

Task arrivals and worker outages are generated **before** any scheduling policy runs.

An R2 trace contains:

- worker capacities;
- worker capabilities;
- worker zones;
- task arrival ticks;
- task work sizes;
- required capabilities;
- preferred zones;
- worker outage windows;
- trace seed.

The exact trace is serializable to JSON and hashed with SHA-256. Every policy result records the same trace digest.

This means policy comparisons do not accidentally receive different arrival bursts or different worker failures.

## Synthetic population

The default generator creates heterogeneous workers with capacities from `{1, 2, 4}`, capabilities from `{python, cpu, gpu}`, and three locality zones.

Tasks have heterogeneous work size and capability/locality requirements. Arrivals can be bursty.

A configurable fraction of workers receives an outage window. The first model uses non-overlapping outage windows per worker so availability can be reproduced cheaply even at large worker counts.

These distributions are experiment controls, not claims about future volunteer-compute populations.

## Stale information

Two independent lag parameters are modeled:

```text
availability_observation_lag
load_observation_lag
```

A local scheduler can therefore select a worker that appeared online in its stale view but is actually unavailable now.

Load history is stored as per-worker change events. A scheduler queries the load that was visible at `tick - load_lag`, which avoids storing a dense worker-by-time matrix.

The global oracle uses current availability and current load.

## Assignment failures

Routing failures are split into:

- no sampled worker appeared available;
- selected worker is actually unreachable because availability was stale;
- selected worker lacks the required capability.

A failed task remains pending and can be routed again on the next tick.

This distinguishes membership staleness from capability-oblivious routing.

## Worker loss and recovery

When a worker enters an outage, queued/in-flight tasks on that worker are evicted and returned to the pending queue.

By default `restart_work_on_churn = true`: work performed in the current failed attempt is lost because no checkpoint is assumed.

R2 records:

- requeued tasks;
- lost work units;
- outage events that evicted tasks;
- time until all tasks evicted by each outage eventually complete;
- unrecovered outage events at the simulation horizon.

A later experiment can add checkpoints and compare the trade-off explicitly rather than silently assuming durable progress.

## Load and service model

Each online worker can process `capacity` work units per tick using FIFO queue order.

New assignments are routed after the tick's existing queues consume capacity, so a task assigned at tick `t` begins service no earlier than tick `t+1`.

The simulation can continue for configurable drain ticks after the final trace arrival.

## Metadata cost

R2 counts a **metadata probe** whenever a scheduler inspects a worker's availability/load information for routing.

Approximate first-model cost:

```text
one-random              -> 1 probe / attempt
power-two               -> <= 2 probes / attempt
power-three             -> <= 3 probes / attempt
capability-power-two    -> <= 2 probes / attempt
full global oracle      -> size(required-capability pool) probes / attempt
```

Static capability-index maintenance is not yet modeled as network traffic. The report therefore understates the total cost of capability discovery, but it makes the dominant global-load scan visible.

## Metrics

Every policy reports raw machine-readable metrics including:

### Completion / latency

- total/completed/unfinished tasks;
- completion rate;
- mean and p95 wait to first service;
- mean and p95 end-to-end response time.

### Queues

- maximum worker queue depth;
- p95 of the maximum worker queue depth at each tick;
- mean tick-maximum queue depth;
- maximum pending-task backlog.

### Routing failures

- routing attempts;
- successful assignments;
- no-observed-candidate failures;
- unreachable assignments;
- capability mismatches.

### Coordination overhead

- total metadata probes;
- mean metadata probes per routing attempt.

### Resource use / balance

- work units actually processed, including repeated work after a failed worker restart;
- online capacity utilization;
- Jain fairness index over per-worker utilization;
- fraction of workers that performed work;
- locality mismatch rate.

### Churn

- requeues;
- lost work;
- recovered/unrecovered churn events;
- mean and p95 churn recovery ticks.

## Fairness metric

For worker `i`:

```text
u_i = processed_work_i / online_capacity_opportunity_i
```

The reported Jain index is

```text
J = (sum_i u_i)^2 / (n * sum_i u_i^2)
```

This normalizes for heterogeneous worker capacity before measuring spread of utilization.

It should not be interpreted as moral/social fairness; it is a load-distribution statistic.

## Run

Generate one trace, save it, and benchmark all policies:

```bash
python -m randomness_lab.r2 \
  --workers 1000 \
  --ticks 500 \
  --arrivals 8 \
  --churn-fraction 0.10 \
  --availability-lag 3 \
  --load-lag 3 \
  --trace-seed 42 \
  --policy-seed 1337 \
  --trace-output results/r2-trace.json \
  --output results/r2-benchmark.json
```

Replay that exact trace later:

```bash
python -m randomness_lab.r2 \
  --trace results/r2-trace.json \
  --policies one-random,power-two,capability-power-two,global-least-loaded \
  --availability-lag 3 \
  --load-lag 3 \
  --policy-seed 1337 \
  --output results/r2-replay.json
```

The trace digest should remain identical.

## A deliberately bad local regime

The test suite includes a population where only one worker has a rare required capability and the other workers cannot execute those tasks.

Capability-oblivious randomized routing produces many mismatches, while the global oracle does not.

This is important: R2 is not designed to prove that power-of-two is always superior. A small local sample can lose badly when useful workers are rare or discovery information is poor.

The research question is where a small amount of indexing/state is enough to capture most of the oracle benefit.

## Limitations of the first model

The first harness does not yet model:

- network topology or transfer latency;
- dynamic capability acquisition;
- multi-resource jobs (CPU + RAM + GPU jointly);
- preemption;
- checkpoints;
- replicated execution;
- malicious workers;
- correlated regional failures;
- scheduler CPU cost;
- network bytes per metadata message;
- decentralized capability-index maintenance.

These should be added only when they answer a measured question; the initial simulator should remain understandable and falsifiable.

## Next step

Run a reproducible scale/regime sweep over:

- 1, 10, 100, 1,000, 10,000, and where practical 100,000 workers;
- churn fraction;
- availability/load staleness;
- capability rarity;
- burst intensity;
- task-size heterogeneity.

Publish both the regimes where power-of-two approaches the oracle and the regimes where it fails badly.
