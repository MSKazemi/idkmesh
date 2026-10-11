# E046 — Per-item difficulty forecasts how many tasks a team of coding agents will cover; correlation-only models do not

**Status:** confirmatory, preregistered. The analysis was frozen by
[`PREREG_AGENT_VALUE_FORECAST_V1`](../docs/research/PREREG_AGENT_VALUE_FORECAST_V1.md)
in merge commit `5d71f20` (2026-10-09 10:06 +02:00), **before** any held-out
split was downloaded. The run used the frozen code unchanged:
`analysis_sha256 = 67aa3068b52cf67baa6c3862f03fee8ae93a6ad0568de3d26f7b5a1848f28f7d`.
**Program items:** X3 (#975), X4 (#976), X5 (#977); hypotheses H1–H3 of the
[Scientific Program](../docs/research/SCIENTIFIC_PROGRAM.md).

## Question

From a pilot of 10 coding agents, can we forecast the following, and which
model of agent dependence gets them right?

- how much a larger, randomly drawn team covers;
- what share of tasks no agent will ever solve.

Does choosing agents that complement each other beat choosing the most
accurate ones?

## Instruments

Source: `SWE-bench/experiments` at commit `40f164d5`, execution-decided
per-instance outcomes, never vendored. The retained output is
[`results/E046-confirmatory.json`](results/E046-confirmatory.json).

| split | tasks | submissions with results | competent (solve rate ≥ 0.05) | feasible (≥ 20 competent and ≥ 100 tasks)? |
|---|---:|---:|---:|---|
| lite | 300 | 84 | 78 | **yes** |
| test | 2294 | 24 | 18 | no, infeasible |
| multilingual | 301 | 14 | 14 | no, infeasible |
| multimodal | 301 | 12 | 12 | no, infeasible |

The registered decision therefore rests on **one** held-out instrument.

## Registered results (Lite, held out)

| forecaster (10-agent pilot) | coverage-curve MAE | population-coverage MAE |
|---|---:|---:|
| independence | 0.2031 | 0.1167 |
| Kish design effect | 0.1619 | 0.2945 |
| shared shock | 0.0816 | 0.1989 |
| **beta-binomial** | **0.0316** | **0.0267** |
| incidence (Chao et al. 2014) | 0.0501 | 0.1010 |
| Rasch (prior tuned on Verified) | 0.0502 | 0.0843 |
| pilot only (baseline) | 0.0805 | 0.1898 |

The population curve is the exact mean coverage of a random team. On Lite it
rises from 0.479 (m = 2) to 0.689 (m = 10) and 0.8833 (all 78 agents). The
blind-spot floor is **35/300 = 0.1167**, and mean pairwise φ is **0.4966**.

- **H1 — shape: supported.** The beta-binomial beats both two-parameter
  comparators. Kish − beta-binomial = 0.133, 95% CI [0.1018, 0.1532].
  Shared shock − beta-binomial = 0.0501, 95% CI [0.0259, 0.0651]. These come
  from a task-cluster bootstrap with 200 replicates. Kish is the formula behind
  the "nine judges, two effective votes" result. As a *forecaster* of team
  coverage it is the second-worst model, after independence.
- **H2 — forecast: supported, by one estimator.** The beta-binomial forecasts
  the 78-agent coverage within **0.0267** (tolerance 0.03), with a bias of
  −0.0111. The Rasch prior that was best on the already-seen Verified split
  **failed out of sample** (0.0843). That failure is the reason the analysis
  was frozen.
- **H3 — selection: supported.**
  - At the primary k = 5, greedy complementarity selection covers 0.8258 of
    held-out tasks against 0.7613 for top-5-by-accuracy. Tasks covered by only
    one of the two: 13 vs 3, exact McNemar p = 0.0213.
  - At k = 10: 0.8516 vs 0.7806, 12 vs 1, p = 0.0034.
  - At k = 3: 9 vs 3, p = 0.146.
  - Random teams of 5 cover 0.6035.

**Registered cross-split decision:** H1 **supported**, H2 **supported**
(beta-binomial), H3 **supported**, each over one feasible split.

## Threats, and a post-hoc robustness check

- **Lite is not independent of Verified.** 93 of Lite's 300 tasks (31%) are
  also Verified tasks, and 19–27 of its 78 agents match a Verified submission
  name. The freeze guarantees the owner had not seen Lite's outcomes; it does
  not make Lite a different population.
- **Post-hoc check, unregistered.** The frozen functions were re-run on the
  207 Lite tasks that are *not* in Verified. Output:
  [`results/E046-posthoc-lite-disjoint-from-verified.json`](results/E046-posthoc-lite-disjoint-from-verified.json).

  | | result | what it says |
  |---|---|---|
  | H1 | beta-binomial MAE 0.0365; Kish gap CI [0.1264, 0.1636], shared-shock gap CI [0.0202, 0.0479] | **Holds** |
  | H2 | beta-binomial error 0.048 | **Does not hold** (above 0.03); the floor rises to 0.1594 |
  | H3 | greedy 0.7383 vs top-5 0.6916, 11 vs 6, p = 0.33; greedy at least as good in 97% of re-splits | Same direction, **not significant** |

- **Submissions are not exchangeable agents**, and pilots ignore provenance
  (shared models and scaffolds). Provenance-aware registration v2 depends on
  T1 (#974).
- One feasible split: a single instrument cannot show the result generalises
  across task families.

## What this establishes

1. **Robust:** for forecasting how much a team of real coding agents covers,
   per-item difficulty (beta-binomial) beats pairwise-correlation models (Kish
   design effect, shared shock) by a wide margin. This holds on held-out data
   and on the tasks that do not overlap Verified. Choosing a dependence model by
   pairwise correlation alone gives the wrong ensemble forecast.
2. **Promising but fragile:**
   - a 10-agent pilot forecast of population coverage within 0.03 (H2);
   - complementarity selection beating top-k at equal size (H3).

   Both pass the registered rule but not the post-hoc overlap check. Each needs
   the v2 registration with provenance and more feasible instruments before it
   is quoted as general.
3. **Negative:** the Rasch prior tuned in-sample did not transfer. In-sample
   forecaster tuning on this kind of data overfits.
