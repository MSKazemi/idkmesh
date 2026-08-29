# R2 Factor-Isolation and Coordination-Cost Evidence

This report completes the remaining synthetic Phase B/C evidence requested by
issue #84 after the capability-rarity sweep merged in PR #262. It varies
availability lag, load lag, outage correlation, and offered load separately
across five trace seeds. It also reports deterministic coordination-cost
proxies and a separate host-specific CPU/memory profile.

## Reproduction

```bash
python3 -m randomness_lab.r2_factor_sweep --self-test

python3 -m randomness_lab.r2_factor_sweep \
  --benchmark \
  --seeds 41,42,43,44,45 \
  --workers 100 \
  --ticks 30 \
  --drain-ticks 300 \
  --output results/experiments/r2/reference-factor-isolation-seeds41-45.json

python3 -m randomness_lab.r2_factor_sweep \
  --profile \
  --repetitions 5 \
  --output results/experiments/r2/reference-factor-isolation-profile.json
```

- deterministic benchmark SHA-256:
  `988b002bdbbd28a92c34825381ccbe45f09384780494a3300f91457987f680fa`;
- host profile SHA-256:
  `0265c4cc971b7e4f8cbf0f8113a2850676378540715a4cbacc44f36b81cdc0ee`;
- deterministic cells: 16;
- raw matched runs: 80 (five retained seeds per cell);
- policies per run: one-random, power-two, power-three,
  capability-power-two, and global-least-loaded.

The timing artifact records its Python/platform identity. It is pinned evidence,
not bit-reproducible output; the main factor artifact remains deterministic.

## Factor controls

| Sweep | Changed | Held fixed within each seed |
| --- | --- | --- |
| availability staleness | availability lag: 0, 1, 2, 5, 10 ticks | one 20%-churn trace, load lag zero |
| load staleness | load lag: 1, 2, 5, 10 ticks | the same trace and zero-lag baseline, availability lag zero |
| failure shape | dispersed independent starts vs one simultaneous regional outage | workers, tasks, outage count, and six-tick duration |
| saturation | requested offered load: 0.25–1.25 capacity-work/tick | nested task prefixes, workers, no outages, zero lag |

All conditions are synthetic and grant no integration authority.

## Companion capability-rarity evidence

PR #262 supplies the non-overlapping capability-prevalence sweep at 50%, 20%,
10%, 5%, 1%, and 0.1%. Its matched five-seed artifact and guarded interpretation
are documented in
[`R2_CAPABILITY_RARITY_SWEEP.md`](../../../docs/research/R2_CAPABILITY_RARITY_SWEEP.md).
This report does not duplicate those cells.

## Independent staleness effects

| Changed factor | lag | capability-two p95 | failed unreachable |
| --- | ---: | ---: | ---: |
| zero-lag baseline | 0 | 10.40 | 0.0 |
| availability lag | 1 | 10.20 | 28.8 |
| availability lag | 2 | 10.60 | 53.2 |
| availability lag | 5 | 11.00 | 119.6 |
| availability lag | 10 | 10.00 | 145.8 |
| load lag | 1 | 11.00 | 0.0 |
| load lag | 2 | 12.60 | 0.0 |
| load lag | 5 | 16.91 | 0.0 |
| load lag | 10 | 23.01 | 0.0 |

Availability lag manifests as misrouting to unavailable workers. Load lag does
not create unreachable attempts when availability is current, but it more than
doubles p95 response by sending work using stale queue observations. Combining
these into one `stale` preset would hide those different mechanisms.

## Regional versus independent outages

Both conditions remove 20 workers for six ticks per seed. Independent failures
have dispersed start times and workers; the correlated condition removes one
zone's sampled workers simultaneously.

For capability-power-two, the regional condition raises mean maximum pending
tasks from 1.2 to 4.8 and mean p95 churn recovery from 7.32 to 8.84 ticks. Its
overall p95 response moves only from 8.31 to 8.80 and all tasks eventually
complete. This is a modest synthetic effect, not a general resilience claim.
Locality mismatch stays near 0.67 in both conditions because none of the five
baseline policies is locality-aware.

## Workload saturation

The realized five-seed mean offered loads are 0.247, 0.499, 0.744, 1.000, and
1.253 work/capacity-tick. All tasks eventually complete because the run includes
a drain horizon, so response time—not completion alone—exposes saturation.

| requested load | capability-two p95 | oracle p95 | capability-two utilization | oracle utilization |
| ---: | ---: | ---: | ---: | ---: |
| 0.25 | 5.00 | 5.00 | 0.218 | 0.218 |
| 0.50 | 5.41 | 5.00 | 0.418 | 0.440 |
| 0.75 | 7.20 | 5.00 | 0.581 | 0.656 |
| 1.00 | 11.20 | 5.60 | 0.676 | 0.848 |
| 1.25 | 17.40 | 11.20 | 0.704 | 0.870 |

The local two-choice policy approaches the oracle at low load, then loses
latency ground near and above capacity. This is the requested separation of
fleet-size protocol scaling from workload saturation and is evidence against a
universal power-of-two claim.

## Coordination cost and host profile

Every run reports metadata probes; request, probe, assignment, and directory
message counts; a transparent 64/48/96/80-byte wire model; capability-directory
initial and churn operations; scheduler state entries; and locality mismatch.
These are protocol-cost proxies, not packet captures.

For the zero-lag staleness baseline, the five-seed mean costs are:

| policy | metadata probes | modeled messages | modeled bytes | directory init/churn ops | state entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| one-random | 4,705.8 | 11,259.0 | 704,400 | 0 / 0 | 2,008.0 |
| power-two | 9,610.8 | 16,244.8 | 944,410 | 0 / 0 | 2,008.0 |
| power-three | 14,994.0 | 21,808.0 | 1,213,920 | 0 / 0 | 2,008.0 |
| capability-power-two | 3,663.2 | 7,493.0 | 482,189 | 118.8 / 49.6 | 2,126.8 |
| global least-loaded | 81,098.0 | 84,888.4 | 4,195,936 | 118.8 / 49.6 | 2,126.8 |

The capability-aware local policy pays directory state and updates, but avoids
enough blind retries to use fewer total messages here. The oracle pays the same
directory cost and about 22 times as many metadata probes.

The five-repetition CPython profile on the recorded host produced these medians:

| policy | process CPU (ms) | traced peak bytes |
| --- | ---: | ---: |
| one-random | 646.49 | 1,260,119 |
| power-two | 952.17 | 1,251,063 |
| power-three | 1,071.08 | 1,251,007 |
| capability-power-two | 619.64 | 1,248,119 |
| global-least-loaded | 642.96 | 1,246,743 |

These measurements include this Python implementation and workload behavior.
For example, blind policies can spend more CPU retrying failed capability
assignments, while the 100-worker oracle remains cheap enough to scan on this
host. They must not be extrapolated to a real distributed fleet.

## Decision and limits

Together with PR #262, the issue #84 synthetic acceptance matrix is complete:
repeated raw seeds, factor-isolated capability and lag sweeps, a distinct
regional failure model, a separate saturation sweep, negative regimes, and
stronger coordination costs are all retained. The evidence supports bounded
local sampling in some regimes, not universal power-of-two optimality.

Remaining questions—real packet sizes, distributed directory consistency,
hardware-level CPU/memory, multi-resource matching, checkpointing, replicated
tasks, and malicious workers—require different systems or experiments. They are
not inferred from this simulator and do not block the bounded Phase B/C result.

Selection and closure rationale are preserved in
[`2026-08-29-issue-84-factor-isolation-closure.md`](../../../docs/conversations/2026-08-29-issue-84-factor-isolation-closure.md).
