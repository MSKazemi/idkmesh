# R2 Capability-Rarity Evidence

This report records the first factor-isolated capability-prevalence sweep for
issue #84. It is synthetic evidence about routing information, not a universal
scheduler ranking.

## Reproduction and Integrity

```bash
python3 -m randomness_lab.r2_capability_rarity \
  --workers 1000 \
  --fractions 0.5,0.2,0.1,0.05,0.01,0.001 \
  --seeds 41,42,43,44,45 \
  --ticks 100 \
  --arrivals 1 \
  --drain-ticks 250 \
  --output results/experiments/r2/capability-rarity-seeds41-45.json
```

- implementation/data revision: `eaa81795c1544754a9647d73631d0d443d5935fa`;
- raw JSON SHA-256: `e418f587d40fa9f18361eb666841475a5b32d1eb65c8271e4248f42dd2b18527`;
- six prevalence cells and five matched seeds per cell;
- identical base topology and task stream across prevalence cells for each seed;
- deterministic nested capable-worker subsets;
- no churn, bursts, availability lag, or load lag;
- one unit-work task per tick, with 250 drain ticks.

Each aggregate retains raw seed values, mean, range, sample standard deviation,
and a Student-t 95% interval clipped to the metric domain.

## Results

All values below are five-seed means. “Failed” is the number of capability
mismatch routing attempts, not the number of unfinished tasks.

| Capable workers | One-random completion | Power-two completion | Power-three completion | Capability-two completion | One-random failed | Capability-two probes | Oracle probes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 500 (50%) | 1.000 | 1.000 | 1.000 | 1.000 | 97.6 | 2.0 | 500.0 |
| 200 (20%) | 1.000 | 1.000 | 1.000 | 1.000 | 423.6 | 2.0 | 200.0 |
| 100 (10%) | 1.000 | 1.000 | 1.000 | 1.000 | 905.0 | 2.0 | 100.0 |
| 50 (5%) | 1.000 | 1.000 | 1.000 | 1.000 | 1,970.8 | 2.0 | 50.0 |
| 10 (1%) | 0.950 | 0.934 | 0.920 | 1.000 | 9,333.6 | 2.0 | 10.0 |
| 1 (0.1%) | 0.224 | 0.244 | 0.230 | 1.000 | 26,166.8 | 1.0 | 1.0 |

The one-random completion interval was `[0.9285, 0.9715]` at 1% and
`[0.1787, 0.2693]` at 0.1%. Capability-aware power-two and the oracle completed
every task with zero capability mismatch in every seed. The three
capability-oblivious policies met the existing `loses_badly` condition in all
30 policy/cell seed comparisons; capability-aware power-two did so in none.

The information-cost result is conditional. Capability-aware routing used two
metadata probes per attempt while at least two workers were eligible, then one
probe at 0.1%. The oracle scanned the entire eligible pool, from 500 probes at
50% to one at 0.1%. Thus the local policy matched the oracle in these controlled
cells with bounded lookup cost, but only because the capability directory was
perfect and current.

## Limits and Next Evidence

Eligible capacity necessarily falls with prevalence (the five-seed capacity
range is 1–4 units at 0.1%). Offered load is fixed and initially feasible even
for a one-capacity worker, but repeated routing misses create backlog that the
rarest cell cannot recover. Results therefore quantify the combined operational
effect of rarity and the policy's information access, not an abstract lookup
probability alone.

Issue #84 still needs independent availability/load-lag sweeps, a correlated
regional-outage model, an explicit workload-saturation sweep, and stronger
coordination-cost measurements. No result here covers those regimes.
