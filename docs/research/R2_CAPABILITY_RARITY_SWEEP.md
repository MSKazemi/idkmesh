# R2 Capability-Rarity Sweep

This Phase B experiment isolates the prevalence of one required capability from
the bundled R2 stress regimes. It asks how much candidate information a local
scheduler needs as eligible workers become rare.

## Controlled Design

For each seed, every cell reuses the same worker capacities, zones, task
arrivals, and unit-work task stream. Every task requires `rare-capability`.
Deterministically ordered, nested worker subsets provide it at 50%, 20%, 10%,
5%, 1%, and 0.1% prevalence. Churn, bursts, availability lag, and load lag are
all zero; offered load stays at one task per tick. This avoids conflating
capability rarity with the earlier composite regimes or deliberate saturation.

The sweep compares `one-random`, `power-two`, `power-three`,
`capability-power-two`, and `global-least-loaded` on identical projected traces.
It retains five raw seeds per cell and reports the same bounded Student-t 95%
uncertainty summaries used by the repeated-seed scale study.

## Reproduce

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

Interpret completion, latency, capability-mismatch failures, and metadata
probes together. Capability-aware sampling can pay for additional metadata and
still fail under other factors not present here. These results do not establish
optimality under churn, stale observations, correlated regional loss,
heterogeneous requirements, or saturation; those remain separate issue #84
sweeps.

The first five-seed reference result and guarded interpretation are retained in
[`../../results/experiments/r2/capability-rarity-seeds41-45.md`](../../results/experiments/r2/capability-rarity-seeds41-45.md).
