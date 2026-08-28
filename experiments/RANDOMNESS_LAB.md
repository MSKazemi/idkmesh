# IDKMesh Randomness Lab v0

This directory contains the first executable simulator for issue #29 and the stochastic-policy research track described in `docs/research/RANDOMNESS_ROADMAP.md`.

The lab is intentionally small and uses only the Python standard library. It is designed to test **coordination ideas**, not to claim that synthetic worker behavior is representative of real humans, models, or networks.

## Research rule

> Randomness controls exploration, not acceptance.

Every simulated candidate is still passed through an independent verifier model. A stochastic policy can choose what to try; it cannot bypass the verification gate.

## Run

From the repository root:

```bash
python experiments/randomness_lab.py \
  --policy all \
  --workers 8 \
  --tasks 200 \
  --trials 30 \
  --seed 20260828 \
  --shared-outcome-probability 0.25 \
  --churn-probability 0.05 \
  --verifier-accuracy 0.98
```

Outputs:

- `results/randomness-lab.jsonl` — one machine-readable record per trial and policy;
- `results/randomness-lab-summary.json` — parameters, synthetic worker specifications, and 95% normal-approximation intervals for the main metrics.

## Included policies

The policy interface is shared across all implementations.

- `greedy` — choose the currently best posterior-mean worker;
- `epsilon_greedy` — mostly exploit, occasionally explore randomly;
- `softmax` — Boltzmann/softmax exploration over posterior means;
- `ucb` — upper-confidence-bound exploration;
- `thompson` — Thompson sampling with Beta posteriors;
- `power_of_two` — sample two available workers and choose the better current estimate.

Use `--policy <name>` to isolate one policy or `--policy all` for a comparison.

## Environment model

Synthetic workers have heterogeneous:

- success probability;
- compute-cost proxy;
- latency proxy;
- availability under churn.

A seeded workload is generated once per trial and then reused across policies. This uses **common random numbers**, so policy comparisons are not confounded by each policy receiving a completely different task realization.

### Correlated errors

`--shared-outcome-probability` controls positive dependence between worker outcomes. For a fraction of tasks, workers are evaluated against a shared random draw; otherwise they receive independent draws.

This parameter is deliberately **not called rho** and is not an exact target Pearson correlation coefficient. The simulator separately measures the realized mean pairwise error correlation and reports it in every result.

This distinction matters because IDKMesh should not report a mathematically precise correlation value unless the generator actually enforces that value.

## Verification model

`--verifier-accuracy` is the probability that the verifier's accept/reject verdict matches the simulated ground truth.

The result records:

- accepted candidates;
- verified successes;
- escaped failures (incorrect work accepted by the verifier);
- correct candidates rejected by the verifier;
- failed assignments from churn;
- compute-cost proxy;
- latency;
- human-attention proxy;
- selection diversity;
- realized pairwise worker error correlation.

The current verifier is intentionally simple and symmetric. It is a placeholder for future experiments with verifier diversity, risk-adaptive verification, correlated verifier failures, and quorum policies.

## Reproducibility

For a fixed configuration and seed, the simulator is deterministic. Trial seeds and worker specifications are written into the result envelope.

Run the tests with:

```bash
python -m unittest discover -s experiments/tests -v
```

The initial tests check:

- fixed-seed reproducibility;
- all registered policies are exercised;
- a perfect verifier cannot accept incorrect work;
- repeated generation of the same seeded workload is identical.

## Adding a policy

1. Implement a `Policy` subclass in `experiments/randomness_lab.py`.
2. Give it a stable `name`.
3. Add it to `POLICY_NAMES` and `policy_factory()`.
4. Make selection depend only on the available-worker list, `PolicyState`, and the provided seeded RNG.
5. Do not add an acceptance path to the policy. Acceptance belongs to verification.
6. Add a focused test when the policy introduces a new invariant.

This keeps exploration strategies interchangeable through one interface.

## Adding an environment feature

Environment changes belong in `generate_workload()` or a future explicit environment interface. Prefer generating a common seeded workload that can be replayed across policies.

Useful next environment features include:

- task families requiring different worker capabilities;
- bursty arrivals and queue state;
- stale load observations;
- malicious workers;
- explicit security/regression failure classes;
- verifier populations with controllable correlation;
- non-stationary worker quality;
- heterogeneous task size and deadline distributions.

When an environment change affects the meaning of a metric, version the output schema or document the compatibility boundary explicitly.

## Scientific limitations

This v0 model is deliberately illustrative.

- Synthetic quality is sampled from a simple distribution.
- `shared_outcome_probability` creates dependence but does not directly set a desired correlation coefficient.
- Human-attention and compute are proxies, not measurements.
- No queueing network is modeled yet.
- No real AI model or coding benchmark is executed.
- Confidence intervals summarize repeated simulator trials; they do not imply external validity.

Negative results are expected and should be retained. A stochastic policy is useful only if it improves a relevant Pareto dimension under a defined workload and verification regime.

## Relationship to the roadmap

This v0 is a foundation for:

- #30 — stochastic diversity vs deterministic replication;
- #31 — power-of-two scheduling under churn;
- #32 — evolutionary orchestration with verification and diversity;
- #13 — collective-intelligence scaling laws;
- #14 — verification scaling.

It should remain a small research harness until those experiments reveal which abstractions deserve promotion into core IDKMesh architecture.
