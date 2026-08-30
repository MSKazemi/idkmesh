# IDKMesh experiments

Experiments are small, reproducible programs used to challenge IDKMesh hypotheses before those hypotheses become architecture or automation.

## Every experiment record

Each row's text is that record's own title, so this index cannot drift from what
the records say. `tests/test_documentation_directory_index.py` asserts the table
covers every Markdown document under `experiments/`; a new record that is not
listed here fails the suite rather than becoming quietly undiscoverable.

| record | question it settles |
|---|---|
| **E011** | [Emergence from vague goals](E011-emergence-vague-goals.md) |
| **E012** | [Correlated Verification Failure](E012-correlated-verification.md) |
| **E013** | [Independence-Aware Verifier Aggregation](E013-independence-aware-aggregation.md) |
| **E014** | [ACO stigmergic task routing](E014-aco-stigmergic-task-routing.md) |
| **E015** | [Verification Phase Diagram and Effective Independent Panel Size](E015-verification-phase-diagram.md) |
| **E016** | [Measuring verifier error correlation with live LLM verifiers](E016-live-verifier-correlation.md) |
| **E017** | [Measured verifier correlation, and why the shared-shock model is the wrong shape](E017-item-difficulty-and-quorum.md) |
| **E018** | [Which E015 conclusions depend on the shape of the dependence model?](E018-dependence-model-shape.md) |
| **E019** | [E013's aggregation rule under the dependence model E017 measured](E019-group-independence-under-item-difficulty.md) |
| **E020** | [The Acceptance-Quorum Frontier Under the Measured Dependence Shape](E020-quorum-frontier-under-measured-shape.md) |
| **E021** | [Coordination criticality with matched susceptibility probes](E021-coordination-criticality.md) |
| **E022** | [Seven-Mode Verification Scaling Matrix](E022-verification-scaling-matrix.md) |
| **E024** | [Matched-budget emergence after a goal change](E024-matched-budget-emergence.md) |
| **E025** | [Learned verifier reliability and dependence](E025-learned-verifier-reliability.md) |
| **E026** | [Does the E024 emergence result survive verifiers that are wrong together?](E026-imperfect-verifier-panel.md) |
| **E027** | [What changes when an accepted defect finally costs something?](E027-defect-propagation.md) |
| **E028** | [Does the archive still survive when the defect is invisible?](E028-latent-defect-dimension.md) |
| **E029** | [The first real model attempts on the frozen benchmark](E029-first-real-model-attempts.md) |
| **E030** | [Does the archive's advantage depend on being handed the future goal?](E030-supplied-goal-membership.md) |
| **E031** | [Does *learning* the goal rescue the consensus swarm?](E031-learned-goal-filter.md) |
| **E032** | [At a fixed budget, when is another agent worth adding?](E032-population-scaling.md) |
| **E033** | [How far can the goal drift before the archive stops helping?](E033-goal-distance.md) |
| **E034** | [The archive's failures are directional. Which direction?](E034-goal-direction.md) |
| **E035** | [Does the direction result survive at a second distance?](E035-direction-across-shells.md) |
| **E036** | [Does the archive survive contributors who optimise to pass the gate?](E036-adversarial-contributors.md) |
| **E037** | [Is the direction result about the goal geometry, or about a perfect verifier?](E037-ladder-under-panels.md) |

E014's sweeps publish their own result documents:
[reference sweep](results/E014-reference-sweep.md),
[parameter Pareto front](results/E014-parameter-pareto.md), and the
[homeostatic hybrid](results/E014-homeostatic-hybrid.md).

Numbering is historical and has gaps. E023 is a preregistration
(`experiments/E023-first-review-latency-recurrence.json`) rather than a written
record, and no artifact for E001-E010 exists in this repository.

The sections below give the longer write-up for a few of these. The full record
for every experiment is the linked document.

## E029 first real model attempts on the frozen benchmark

`tools/open_model_benchmark_probe.py` puts a pinned open-weight model
(`Qwen/Qwen2.5-Coder-0.5B-Instruct`) behind a network-disabled, read-only,
capability-dropped container as a candidate *producer*, and routes its output
through the existing independent EvaluatorPlan verifier. E029 is the first time
it was run: 60 real attempts across all 10 frozen work units, at zero paid API
spend.

```bash
./tools/open_model_producer_image.sh
python tools/open_model_benchmark_probe.py --self-test
python tools/open_model_probe_summary.py --self-test
```

The result is negative and blunt: 0 of 60 attempts produced a patch the verifier
was even asked to judge, and 56 of the 60 failures were unified-diff *protocol*
failures rather than failures of the proposed change. Pairwise attempt
correlation is therefore undefined, not zero. See
`E029-first-real-model-attempts.md`, linked in the index above.

## E022 verification-scaling matrix

`verification_scaling_matrix.py` compares all seven verification conditions
named in issue #14 on a matched, seeded hidden-defect stream. It separates
simulated acceptance from independently verified useful work and measures queue
stability, escaped defects, verification cost, and attention.

```bash
python experiments/verification_scaling_matrix.py --self-test
python experiments/verification_scaling_matrix.py --benchmark --summary-only
```

The result is a Pareto trade-off: independent tests maximize synthetic
throughput, tests plus adversarial review minimize escaped defects, and
risk-adaptive backpressure keeps overload bounded. See
`E022-verification-scaling-matrix.md`, linked in the index above.

## E021 coordination-criticality experiment

`criticality_susceptibility.py` compares matched constant-load, `+5%` pulse,
and sustained-stress runs in a generator/worker/verifier queue. It reports
finite-difference response with uncertainty and compares a superlinear-response
signal with ordinary utilization and absolute-backlog thresholds.

```bash
python experiments/criticality_susceptibility.py --self-test
python experiments/criticality_susceptibility.py --benchmark --summary-only
```

The 40-seed result is intentionally qualified: susceptibility warned earlier
but produced false alerts, while the utilization threshold detected the measured
onset without false alerts in the tested grid. See
`E021-coordination-criticality.md`, linked in the index above.

## ACE live-open-work population experiment

`ace_population_sim.py` is the replacement experiment for Growth Seed #27.

The earlier PR #44 was intentionally closed unmerged because it modeled review pressure as a cumulative historical queue. After #104 established the recoverable `live-open-work-v1` capacity model, #27 remained open specifically so the experiment could be rebuilt against the canonical state definition.

This program is **illustrative, not empirical community evidence**. It has no GitHub API access, no actuation authority, no merge authority, and no third-party dependencies.

### Canonical load model

The simulated current-state pressure is:

```text
L_t =
    1.00 * ready_PRs
  + 0.25 * draft_PRs
  + 0.50 * open_Growth_Seeds
  + 0.10 * min(other_open_human_issues, 20)
```

and:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

Historical event counts are deliberately absent. If open work closes, `L` falls and capacity can recover.

### Reproduction rule

Only verified useful output earns reproductive credit:

```text
Credit(t+1)
  = decay * Credit(t)
  + verified_descendants * novelty * gate
```

where:

```text
governed: gate = Capacity(L)
raw:      gate = 1
```

Credit may open new Growth Seeds. The `raw` comparator therefore represents reproduction that ignores carrying capacity; it is not a recommended production policy.

### Run it

```bash
python experiments/ace_population_sim.py --check
```

Machine-readable output:

```bash
python experiments/ace_population_sim.py --check --format json
python experiments/ace_population_sim.py --format csv
```

Run one scenario:

```bash
python experiments/ace_population_sim.py \
  --scenario overload \
  --policy both \
  --seed 20260828
```

Parameters such as `K`, `tau`, review slots, spawn rate, activation probability, verification probability, and the background issue count can be overridden from the CLI.

### Default regimes

1. **under-reproduction** — follow-up ACE work dies out;
2. **healthy-reproduction** — verified work repeatedly creates descendant opportunity while live pressure remains bounded;
3. **overload** — reproduction can create open work faster than the fixed review bottleneck can process it.

For fixed seed `20260828`, the default overload comparison is:

```text
governed:
  public activity       = 323
  reviewed PRs          = 160
  verified descendants  = 144
  final live load       = 7.75

raw:
  public activity       = 491
  reviewed PRs          = 160
  verified descendants  = 144
  final live load       = 91.75
```

So the raw policy creates **168 additional public activity events** and **84 additional units of final live pressure** while producing exactly the same reviewed and verified throughput in this deterministic toy regime.

That demonstrates a mechanism, not an empirical law:

```text
more activity != more useful throughput
```

when verification/review is already the bottleneck.

### What `R_community` means here

The simulator controls its own parent inventory. Each seed may create at most one candidate PR; when that candidate reaches terminal review, the seed is treated as an eligible matured parent. A successful review is a verified descendant.

Therefore the toy quantity is:

```text
R_community = verified descendants / eligible matured parents
```

This is intentionally simpler than real repository lineage. Production ACE must use the canonical #48 lineage protocol plus an independent eligible-parent inventory and must preserve right-censoring/verification semantics.

### Acceptance contract

`--check` and `tests/test_ace_population_sim.py` require that:

- the exact live-open-work weights remain canonical;
- the ordinary-issue term stays capped at 20;
- reducing current open work recovers capacity;
- historical event volume cannot affect `L` at fixed current state;
- the under-reproduction scenario exhausts active ACE work;
- the healthy scenario reproduces while staying bounded;
- in the default overload regime, raw reproduction creates more activity and pressure without increasing reviewed or verified throughput;
- the governed overload case returns to final `L <= K`.

### Safety / interpretation

The coefficients, `K=8`, `tau=2`, scenario probabilities, and spawn rates are bootstrap hypotheses chosen to expose qualitative regimes. They must not be cited as measured properties of open-source communities.

This experiment does not change the Phase-B gate. Even perfect simulated capacity cannot replace:

- real independently verified descendant evidence;
- actual GitHub branch/ruleset protection;
- explicit authority opt-in;
- independent integration controls.

See `docs/community/ACE_CAPACITY_MODEL.md`, `COMMUNITY_GROWTH_ENGINE.md`, merged #48, merged #68, merged #104, and merged #112.
