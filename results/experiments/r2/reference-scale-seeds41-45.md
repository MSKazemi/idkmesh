# R2 Five-Seed Scale Evidence

This report repeats the existing R2 scale/regime experiment with trace seeds
41–45. It is descriptive Phase A evidence for issue #84, not a factor-isolated
causal experiment.

## Reproduction

```bash
python3 -m randomness_lab.r2_scale \
  --worker-counts 1,10,100,1000,10000,100000 \
  --seeds 41,42,43,44,45 \
  --regimes fresh,moderate,stale \
  --ticks 30 \
  --oracle-max-workers 10000 \
  --output results/experiments/r2/reference-scale-seeds41-45.json
```

- implementation/data revision: `b25f4d59a880ab189b6b16a7e94c6d314d87dd5b`;
- raw JSON SHA-256: `2ab05c9176801d4c95ae481f81ea37323319794a17dbc972038b1c75ea4bfb00`;
- cells: 18 (six worker counts × three stress regimes);
- raw matched runs: five per cell;
- policies: one-random, power-two, power-three, capability-power-two, and the
  global least-loaded oracle where allowed.

Each numeric aggregate retains its raw seed values, mean, minimum, maximum,
sample standard deviation, and a two-sided Student-t 95% interval clipped to
the metric's physical domain. Five seeds remain a small sample; the intervals
are uncertainty indicators, not guarantees.

## Selected Results

The table compares one metadata probe per routing attempt with the
capability-aware two-probe policy. Values are five-seed means.

| Regime | Workers | One-random p95 response | One-random failed assignments | Capability-two p95 response | Capability-two failed assignments |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh | 10 | 17.53 | 51.4 | 9.35 | 0.0 |
| fresh | 1,000 | 10.45 | 48.8 | 7.80 | 0.0 |
| fresh | 100,000 | 11.20 | 4,851.0 | 9.00 | 0.0 |
| moderate | 10 | 21.82 | 70.8 | 11.37 | 0.4 |
| moderate | 1,000 | 10.47 | 60.0 | 8.50 | 0.2 |
| moderate | 100,000 | 12.00 | 6,709.2 | 9.00 | 34.2 |
| stale | 10 | 38.64 | 103.8 | 27.94 | 4.8 |
| stale | 1,000 | 12.93 | 148.8 | 9.00 | 1.6 |
| stale | 100,000 | 12.00 | 13,116.4 | 9.00 | 268.4 |

Capability-aware sampling sharply reduced capability-mismatch and unreachable
routing attempts in these cells while using about two probes per attempt rather
than one. That is a useful local-information trade, not proof of optimality.

The existing `loses_badly` diagnostic still fired in 3 of 75 oracle-comparable
capability-power-two runs. All three were in the stale 10-worker cell. The same
count occurred for ordinary power-two; power-three triggered 5 times and
one-random 9 times. Negative cells remain in the raw data.

The stale one-worker cell was the only aggregate with incomplete runs: mean
completion was about 0.855 and one seed reached 0.613. At 100,000 workers the
oracle is explicitly skipped, while utilization stays below one percent because
arrival rate is capped. Those cells measure local-policy coordination cost, not
fleet saturation.

## Limits and Next Evidence

The named regimes change churn, observation lag, and burstiness together.
Therefore this run does not identify which factor causes a change. Issue #84
still needs separate capability-rarity, availability/load-lag, regional-outage,
and workload-intensity sweeps. Scheduler CPU, memory, messages, and directory
maintenance cost also remain Phase C work.
