# Preregistration v1 — forecasting the value of the next coding agent

**Experiment:** E046 · **Program items:** X2 (this document), X3, X4, X5 · **Hypotheses:** H1, H2, H3 of the
[Scientific Program](SCIENTIFIC_PROGRAM.md)
**Issues:** #973 (this freeze), #975, #976, #977 · **Epic:** #969
**Registered:** 2026-10-09, frozen by the merge commit of the pull request that adds this file.

## 1. Frozen artefacts

| artefact | value |
|---|---|
| analysis code | `experiments/agent_value_forecast.py` |
| analysis code SHA-256 | `67aa3068b52cf67baa6c3862f03fee8ae93a6ad0568de3d26f7b5a1848f28f7d` |
| upstream data | `SWE-bench/experiments` at commit `40f164d5b8f1d249bf95a6df8b74b577fd8e519d` (the same commit as E045) |
| seed | `20261009` |

Any change to the analysis code after the merge is an **amendment**. The results
record must list it, give its reason, and report the frozen version's output as
well.

## 2. What has and has not been seen

- **Seen (exploratory):** the `verified` split. E045 described it; E046's code
  was developed and tuned on it. The retained exploratory output is
  [`E046-verified-exploratory.json`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/results/E046-verified-exploratory.json).
- **Not seen (confirmatory):** the `lite`, `test`, `multilingual` and
  `multimodal` splits at the pinned commit. Before this freeze only their
  directory names were listed. None of their files has been downloaded or read.
- **Tuning disclosed.** Two settings were chosen on `verified`:
  - the Rasch difficulty prior (precision 0.01), selected among
    {1, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001} using 30 pilots;
  - computing population curves in exact closed form instead of by Monte Carlo.

  Because the prior was chosen on `verified`, a Rasch success there is
  **in-sample**. Only the held-out splits test it.

## 3. Instruments and unit of analysis

- **One split is one instrument.** Agents are the submissions with a usable
  per-instance result. The rules are E045's: an explicit `resolved` list wins,
  and an all-false per-instance file is a missing evaluation and is dropped.
- **Task universe:** the union of instance ids appearing in any list-valued
  field of any `results.json`, or as a key of any `per_instance_details.json`,
  in the split.
- **Competence screen:** solve rate ≥ 0.05.
- **Feasibility:** a split is analysed only with ≥ 20 competent agents and
  ≥ 100 tasks. Otherwise it is reported as **infeasible** and excluded from the
  decision rules.
- **Known limitation, not modelled in v1:** submissions are not exchangeable
  draws. Many share a model, a scaffold or an organisation, and leaderboard
  entry is self-selected. Pilots are drawn uniformly from the competent
  submissions. Provenance-aware analysis is T1's job (#974) and will be a
  separate registration.

## 4. Estimands

- **Population curve.** C(m) is the exact mean oracle coverage of a uniformly
  random m-subset of the split's competent agents. A task solved by c of M
  agents is missed with probability C(M − c, m)/C(M, m). It is evaluated on the
  grid G = {2, 5, 10, 20, 40} ∩ [m < M], plus M itself.
- **Pilot.** k = 10 agents drawn uniformly without replacement, with 200 pilots
  per split (100 for Rasch). Sensitivity analyses use k = 5 and k = 20, with 50
  pilots each.
- **Forecasters.** Each sees only the pilot's k × N outcomes:

  | name | model | parameters |
  |---|---|---|
  | independence | 1 − (1 − p̄)^m | 1 |
  | kish | 1 − (1 − p̄)^{n_eff}, n_eff = m / (1 + (m − 1)·φ̄) | 2 |
  | shared_shock | w·p̄ + (1 − w)(1 − (1 − p̄)^m), w = φ̄ | 2 |
  | beta_binomial | 1 − B(α, β + m)/B(α, β), method-of-moments α, β | 2 |
  | rasch | per-task q_t = mean_j σ(a_j − b_t); ridge precision 0.01 on b, 25 alternating Newton sweeps | N + k |
  | incidence | Chao et al. 2014 incidence rarefaction (m ≤ k) and extrapolation (m > k) | non-parametric |
  | pilot_only | incidence rarefaction for m ≤ k, flat beyond (baseline) | — |

- **Curve MAE.** For each pilot, the mean over G of |forecast(m) − C(m)|,
  averaged over pilots.
- **Population-coverage MAE.** The mean over pilots of |forecast(M) − C(M)|.
  Since the blind-spot floor is 1 − C(M), this is also the floor error.

## 5. Hypotheses, tests and per-split verdicts

**H1 — shape (X3, #975).** The beta-binomial (per-item difficulty, two
parameters) forecasts the curve better than the two-parameter comparators,
Kish and shared shock.

- *Test:* a task-cluster bootstrap with 200 replicates; each replicate
  resamples tasks with replacement and uses 40 fresh pilots. It produces 95%
  percentile intervals for (comparator MAE − beta-binomial MAE).
- *Verdict:*
  - **supported** if both intervals lie above 0;
  - **falsified** if either interval lies below 0;
  - **unresolved** otherwise.

**H2 — forecast (X4, #976).** From a 10-agent pilot, at least one prespecified
item-level forecaster — beta_binomial, rasch or incidence — forecasts C(M)
within 0.03.

- *Verdict per split:* each forecaster meets the tolerance or does not. Also
  reported: whether it beats pilot_only.

**H3 — selection (X5, #977).** Greedy complementarity selection beats
top-k-by-accuracy at equal k.

- *Split of tasks:* a task is a calibration task if the SHA-256 of its instance
  id, read as an integer, is even; all other tasks are held out.
- *Selectors,* run on calibration tasks with all competent agents available:
  - greedy maximisation of covered calibration tasks, with ties broken by
    calibration accuracy and then by name;
  - top-k by calibration accuracy.
- *Primary k is 5;* k = 3 and k = 10 are secondary.
- *Test:* a two-sided exact McNemar test on held-out tasks, comparing tasks
  covered only by greedy with tasks covered only by top-k.
- *Verdict:*
  - **supported** if greedy covers more and p < 0.05;
  - **falsified** if top-k covers more and p < 0.05;
  - **unresolved** otherwise.
- *Robustness, reported but not used for the verdict:* 200 random half-splits.

## 6. Cross-split decision rules

These apply over the feasible held-out splits only (`lite`, `test`,
`multilingual`, `multimodal`). `verified` is reported separately and never
counts.

- **H1 and H3:**
  - **supported** if more than half the feasible splits are supported and none
    is falsified;
  - **falsified** if more than half are falsified;
  - otherwise **unresolved**.
- **H2:**
  - **supported** if at least one of the three forecasters meets the tolerance
    on *every* feasible split;
  - otherwise **falsified**.

  Three forecasters are tried; no multiplicity correction is applied to a
  tolerance criterion, and every forecaster's result is reported.
- **No feasible split** means every hypothesis is **infeasible**, and that is
  reported as such.

## 7. Program consequences

This section restates the Scientific Program's kill criteria.

The program's headline claim is "agent value is forecastable from measured
dependence". It loses its worker-side support if H1 is falsified **and** no H2
forecaster beats pilot_only. A falsified H3 removes the selection algorithm
(A4) from the sizing advisor (T2, #982).

**Every outcome — supported, falsified, unresolved or infeasible — is published**
in an E046 results record. The record updates the program's §3–§5 and the issues
listed above.

## 8. Execution procedure

```bash
for split in lite test multilingual multimodal; do
  python experiments/agent_value_forecast.py fetch \
    --cache .cache/e046/$split --split $split \
    --commit 40f164d5b8f1d249bf95a6df8b74b577fd8e519d
done
python experiments/agent_value_forecast.py analyze \
  .cache/e046/lite .cache/e046/test .cache/e046/multilingual .cache/e046/multimodal \
  --out experiments/results/E046-confirmatory.json
```

`analysis_sha256` in the output must equal §1's digest. If it does not, the run
is an amendment.
