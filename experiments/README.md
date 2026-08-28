# IDKMesh experiments

Experiments are small, reproducible programs used to test IDKMesh hypotheses before those hypotheses become architecture or automation.

## ACE population simulator

`ace_population_sim.py` is a standard-library-only simulation of the community-reproduction ideas in [`COMMUNITY_GROWTH_ENGINE.md`](../COMMUNITY_GROWTH_ENGINE.md).

It is **illustrative, not empirical evidence**. Its purpose is to make assumptions executable and falsifiable.

Run all default scenarios:

```bash
python experiments/ace_population_sim.py --check
```

Machine-readable output:

```bash
python experiments/ace_population_sim.py --check --format json
python experiments/ace_population_sim.py --format csv
```

Run one scenario and override parameters:

```bash
python experiments/ace_population_sim.py \
  --scenario overload \
  --k 6 \
  --decay 0.96 \
  --spawn-rate 2.0 \
  --verification-probability 0.86 \
  --review-capacity 4
```

The three default scenarios are:

1. **under-reproduction** — follow-up activity dies out;
2. **healthy-reproduction** — useful activity continues while review load remains bounded;
3. **overload** — an activity-maximizing policy generates more work than reviewers can absorb.

Each scenario can compare two policies:

- `governed` — reproductive credit and spawning are suppressed by review load using the ACE carrying-capacity function;
- `raw` — the same activity is allowed to reproduce without the capacity gate.

The default overload scenario deliberately demonstrates that **more raw activity can produce the same verified output while leaving substantially more unreviewed work**. This is a model behavior to challenge, not a claim that real communities have these exact parameters.

The `--check` flag asserts that the default scenarios still demonstrate their intended qualitative behavior. CI runs this check for changes to the simulator.

## Phase 0 experiment harness

`harness.py` validates the repository's Phase 0 schemas and deterministic experiment fixtures. It has separate dependencies and responsibilities from the ACE simulator; the population simulator intentionally stays standard-library-only so it remains easy for newcomers to run.
