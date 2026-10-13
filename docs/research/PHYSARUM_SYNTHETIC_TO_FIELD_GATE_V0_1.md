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
