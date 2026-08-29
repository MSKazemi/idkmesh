# R1 — Swarm Diversity vs Replication

**Issue:** #30  
**Status:** Synthetic experiment implementation; not yet evidence about real coding agents.

## Research question

When does controlled stochastic diversity improve **verified** outcomes compared with simply replicating the same worker?

The experiment is intentionally designed so that it can report that diversity hurts. Agent count is not treated as a proxy for intelligence.

## Conditions

The R1 runner compares six conditions:

1. `single_deterministic` — one worker, deterministic scheduler;
2. `identical_replication` — `N` equal workers with maximally correlated base errors;
3. `seed_only` — `N` equal workers with partial stochastic decorrelation but the same structural label;
4. `structural_diversity` — `N` structurally distinct labels with lower configurable error correlation;
5. `bandit_selected` — Thompson sampling chooses a fixed-size subset from a larger heterogeneous pool;
6. `diverse_random_verifiers` — structurally diverse workers plus randomized assignment across independent verifier identities.

Conditions 2–6 use the same fixed attempt budget `N` except that the single-worker baseline intentionally uses one attempt.

## What "structural diversity" means here

This first synthetic model does **not** claim to model real differences between models, prompts, tools, or organizations. Structural diversity is represented by distinct labels and a separately controlled error-correlation parameter.

That separation matters:

```text
seed variation != structural diversity != low error correlation
```

The experiment records all three rather than collapsing them into one number.

## Candidate outcome model

A synthetic worker first produces a base-success outcome under the shared correlation environment. A selected candidate then receives additional synthetic checks:

- hidden-test pass;
- regression failure;
- security failure.

A candidate is ground-truth `is_good` only when it succeeds, passes the hidden check, and has no regression or security failure.

These are experiment variables, not claims about actual defect distributions in coding agents.

## Verification model

A verifier has:

- sensitivity;
- false-positive rate;
- human-attention cost proxy.

Verifier decisions can be partially correlated within a task. The randomized-verifier condition distributes candidates over several verifier identities, each with its own per-task shared draw.

The integration policy selects the first candidate accepted by its assigned verifier. This intentionally makes false acceptance measurable rather than assuming that the simulator has a perfect selector.

## Metrics

Each condition records raw seeded trials and, optionally, raw per-task candidate records.

Primary metrics include:

- verified task success rate;
- probability that at least one good candidate existed;
- selected hidden-test pass rate;
- selected regression rate;
- selected security-failure rate;
- false-acceptance rate;
- abstention rate;
- missed-good-candidate rate;
- configured and realized pairwise base-error correlation;
- compute per task;
- parallel latency proxy;
- human-attention proxy;
- structural-diversity fraction;
- verified utility per unit of compute + attention proxy.

Every across-trial metric reports mean, sample standard deviation, min/max, and a descriptive normal-approximation 95% interval. Raw trials remain available and should be preferred for serious analysis.

## Negative results are first-class

Every non-replication condition is compared with `identical_replication`. The machine-readable result includes:

```text
delta_mean_verified_success_rate
lower_success_than_replication

delta_mean_verified_utility_per_unit_cost
lower_utility_than_replication
```

No code path rewrites or suppresses a negative delta.

## Run

From the repository root:

```bash
python -m randomness_lab.r1 \
  --tasks 500 \
  --trials 30 \
  --swarm-size 5 \
  --seed 42 \
  --output results/r1.json
```

For a lighter run that keeps trial metrics but omits per-task records:

```bash
python -m randomness_lab.r1 \
  --tasks 500 \
  --trials 30 \
  --no-task-records \
  --output results/r1-summary.json
```

## Interpretation guardrail

This experiment is a **mechanism test**, not a benchmark result.

A synthetic result such as "structural diversity beats replication at correlation 0.25" means only that the implementation behaves as expected under those assumptions. It does not establish that real multi-model coding swarms have that correlation or quality distribution.

The next evidence step is to replace synthetic worker outcomes with adapters that replay or execute real bounded coding-task results while keeping the same result schema.

## Next steps

The assumption sweep, synthetic N-scaling curves, and conservative real-result
replay adapter now exist. See [R1 collective-capability scaling](R1_COLLECTIVE_SCALING.md)
for the N = 1, 2, 5, 10 reference and the explicit issue #13 coverage ledger.

The remaining steps require evidence rather than more synthetic plumbing:

1. Run on held-out coding tasks with hidden tests and publish raw results.
2. Measure real pairwise failure correlation by model/prompt/tool/role rather than assuming it.
3. Compare randomized verifier assignment with genuinely different verifier models/tools.
4. Execute the planner/role and task-DAG configurations under the same frozen budgets.

The project should not promote a swarm strategy into the Verified Swarm Runner solely because it performs well in this synthetic experiment.
