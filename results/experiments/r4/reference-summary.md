# R4 Verified Stigmergic Routing Reference

**Status:** Reproducible synthetic mechanism evidence; not a production routing or
governance decision.

This report completes the frozen reference-evidence milestone for issue #97. It
uses CPython 3.12.3 and the R4 harness on `main` at
`5123f8c1f47c4ec5b1982863d0e90c8bf8b00232` and retains the full per-step
routing events, metrics, and pheromone snapshots for every policy.

## Reproduction

```bash
python3 -m randomness_lab.r4 \
  --scenario default \
  --steps 800 \
  --shift-step 400 \
  --task-seed 42 \
  --outcome-seed 4242 \
  --policy-seed 1337 \
  --output results/experiments/r4/reference-default.json

python3 -m randomness_lab.r4 \
  --scenario lockin \
  --steps 500 \
  --shift-step 100 \
  --task-seed 11 \
  --outcome-seed 1111 \
  --policy-seed 77 \
  --output results/experiments/r4/reference-lockin.json
```

| Artifact | Task-trace digest | File SHA-256 |
| --- | --- | --- |
| `reference-default.json` | `sha256:5ccda8c16d7fa26f90849320424fb84603ade8ca3b326d62fcde60685234c73d` | `29af5b29dbb2ddb7c231f497814b6a7ee3757190f84b1e4403c5314933f0a963` |
| `reference-lockin.json` | `sha256:672389d71d449dc7387d62cdc62877b75179e70d4dd3537d457d413d201d1e3b` | `f89cc9723054bfa1aa94762ba46fa74e5fbbb823e4c2691110a34942270e6bde` |

`tests/test_r4_reference.py` checks both fixed artifact hashes on every supported
runtime and requires byte-for-byte regeneration on the recorded Python 3.12
family. Python 3.11 can produce tiny floating-point serialization differences,
so cross-minor replay instead verifies scenario and trace identity, policy
coverage, the zero unverified-activity deposit invariant, and the deliberately
harmful lock-in result.

## Default specialization, shift, churn, and newcomer scenario

| Policy | Verified success | Post-shift success | Expected regret | Optimal assignment | Newcomer share |
| --- | ---: | ---: | ---: | ---: | ---: |
| greedy | 0.6350 | 0.4675 | 167.65 | 0.3225 | 0.0000 |
| random | 0.5825 | 0.5650 | 223.76 | 0.2100 | 0.1225 |
| stigmergy, evaporation | 0.5925 | 0.4200 | 212.08 | 0.2838 | 0.0050 |
| stigmergy, evaporation + exploration | 0.6775 | 0.5300 | **134.96** | **0.5112** | 0.1175 |
| stigmergy, no evaporation | 0.6238 | 0.4875 | 183.56 | 0.3038 | 0.0000 |
| Thompson | **0.6813** | **0.5400** | 136.57 | 0.4537 | **0.1588** |

The adaptive stigmergic policy had the lowest expected regret and highest
optimal-assignment rate in this one trace, but Thompson had slightly higher
realized success and post-shift success. Permanent pheromone and greedy routing
never tried either newcomer. Evaporation without an explicit exploration floor
tried the newcomers but allocated only four total assignments to them and
performed poorly. The result supports treating evaporation and exploration as
separate controls.

## Deliberate early-incumbent lock-in trap

| Policy | Verified success | Post-shift success | Expected regret | Recovery steps | Late-expert first assignment |
| --- | ---: | ---: | ---: | ---: | ---: |
| greedy | 0.718 | 0.765 | 103.80 | 142 | 247 |
| random | 0.588 | 0.530 | 177.10 | — | 100 |
| stigmergy, evaporation | 0.722 | 0.655 | 116.05 | 126 | 227 |
| stigmergy, evaporation + exploration | 0.762 | 0.710 | 94.80 | 100 | 137 |
| stigmergy, no evaporation | 0.250 | 0.065 | 359.70 | — | never |
| Thompson | **0.870** | **0.840** | **38.25** | **47** | 120 |

Permanent pheromone assigned 488 of 500 tasks to the early incumbent and never
tried the late expert. Evaporation plus exploration reduced regret by 264.9 and
raised post-shift success from 0.065 to 0.710, but Thompson was substantially
better on every primary quality/adaptation metric. This is a first-class
negative result for the claim that bio-inspired routing should replace a
conventional bandit.

## Integrity and interpretation

Every stigmergic run recorded:

```text
unverified_activity_pheromone_increase = 0.0
```

Only independently generated synthetic verified outcomes update pheromone.
Routing weight cannot accept a result, grant merge authority, or create
governance/reputation power.

These are two deterministic single-seed reference scenarios. They demonstrate
mechanisms and expose failure modes; they do not estimate population-level
performance, establish optimal hyperparameters, or justify deployment. Exact
floating-point serialization is runtime-family-bound even though the safety and
qualitative replay checks are cross-runtime. A future factor-isolated sweep may
vary evaporation and exploration across multiple seeds without changing or
reinterpreting this frozen evidence.
