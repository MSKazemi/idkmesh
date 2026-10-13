# Physarum routing: synthetic-to-field decision gate

**Issue:** #630. **State:** proposal for falsification, no field proof.

The synthetic stress and failover-frontier code provides reproducible simulation
evidence, not measured production topology. Product-level adaptive routing
remains blocked by admitted-path telemetry in #649.

## Pre-field decision rule
Freeze simulation configuration and seeds before comparing Physarum against
static shortest-path, discounted Thompson and explicit multipath/failover.
Report success rate, recovery after a shift, mean burden per successful task,
failure-attribution noise sensitivity and confidence/dispersion per regime.
Run stationary, gradual, transient, node-loss, correlated failures, both graph
densities and multiple parameter settings. Compare **at matched burden** to
avoid claiming resilience gains paid for with hidden resource cost.

## Falsifiers
If the Pareto frontier of an adaptive baseline dominates the proposed policy
across stationary and shift fixtures, do not integrate. If results depend on
one arbitrary conductance floor or one random seed, report sensitivity instead
of a general benefit. If an available deployment is flat/single-hop, there is
no legitimate multi-path topology and this routing policy stays research only.

## Field prerequisite
Collect real already-admitted nodes, explicit edge meaning, path latency and
failure attribution before designing any canonical topology snapshot. Every
future shadow recommendation must bind to an exact admitted-pool digest and
freeze before outcome; it never grants eligibility, spend or merge authority.

**Next evidence:** run fixed-seed replication, publish code/config digests and
record negative results. None of those runs are claimed by this file.


## Reproducible synthetic evidence commands

Run from the repository root with a pinned Python environment and source
revision, and retain full stdout JSON before interpreting the results:

```bash
git rev-parse HEAD
mkdir -p results   # results/ is gitignored scratch output
python sim/physarum_compute_routing_stress.py \
  --seed-start 1 --seeds 20 --epochs 80 --tasks-per-epoch 20 \
  --topology all > results/physarum-routing-stress.json

python sim/physarum_compute_routing_stress.py \
  --seed-start 1 --seeds 20 --epochs 80 --tasks-per-epoch 20 \
  --topology all --failover-frontier \
  > results/physarum-routing-failover-frontier.json

python sim/physarum_compute_routing_stress.py \
  --seed-start 1 --seeds 20 --epochs 80 --tasks-per-epoch 20 \
  --topology dense --environment abrupt-shift --parameter-sweep \
  > results/physarum-routing-parameter-sweep.json

sha256sum results/physarum-routing-*.json
```

These commands are **proposed reproduction steps**, not experiments
performed by this PR. The frontier command compares both topologies, all
available regimes and the configured failover retry-probability sweep; the
parameter command deliberately selects a single topology and environment,
as required by its CLI parser. Use the exact same seed cohort, environment
and topology when comparing strategies.

### Decision ledger fields

For every condition record: exact code commit; Python version; all CLI
arguments; output digest; synthetic topology; admitted-edge assumption;
number of independent seeds; per-policy successful task fraction; mean
burden per attempted and per successful task; paired burden-matched
frontier gap; dispersion/uncertainty; cases dominated by discounted Thompson
or failover; and the reason a hypothesis was retained or rejected.

**Stop condition:** do not recommend even shadow deployment if a realistic
strong baseline dominates at matched burden, if results only hold in one
hand-picked regime/parameter setting, or if source-provenance and paired
seed reproducibility are missing. A synthetic win can only nominate a
*future field study*, never establish resource admission or product benefit.
