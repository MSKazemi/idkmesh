# E045 — 169 real coding agents fail together, and a 10-agent pilot underestimates what the population covers

**Status:** exploratory pilot on observed public data. **Not confirmatory.** The
confirmatory test is preregistered in
[`docs/research/SCIENTIFIC_PROGRAM.md`](../docs/research/SCIENTIFIC_PROGRAM.md)
and must use splits this pilot has not opened.

## Why this record exists

Every quantitative finding in the verifier-panel paper rests on one constructed
instrument: 25 partial test oracles voting on 72 candidates (E017). Every
worker-side dependence result (E032, E040, E042) is a simulation. The research
program's central question, *when is another agent worth adding?*, had no real
population to measure.

One exists already. For every SWE-bench Verified leaderboard submission, the
SWE-bench project publishes which of the 500 instances that system resolved, as
decided by running the hidden test suite. That is an agent × task solve matrix
with execution-decided ground truth, built independently by many teams, and free
to read.

## Instrument

| | |
|---|---|
| source | `SWE-bench/experiments`, `evaluation/verified`, pinned commit `40f164d5b8f1d249bf95a6df8b74b577fd8e519d` |
| systems with usable per-instance results | 174 |
| competent systems (solve rate ≥ 5%, the analogue of E017's competence screen) | 169 |
| tasks | 500 |
| execution-graded outcomes | 169 × 500 = 84,500 |
| file digest (SHA-256 over the per-file digests) | `adfec04c1fae9c06f2fe5518a3856b21bef3d249a5c74a679203842969e4e87c` |

The upstream repository carries no licence file, so its data is **not vendored**.
[`public_agent_dependence.py`](public_agent_dependence.py) downloads it at the
pinned commit and records a digest of every file it reads; the retained summary
is [`results/E045-public-agent-dependence-pilot.json`](results/E045-public-agent-dependence-pilot.json).

```bash
python experiments/public_agent_dependence.py fetch   --cache .cache/swebench
python experiments/public_agent_dependence.py analyze --cache .cache/swebench
```

Some submissions carry a newer `per_instance_details.json` whose every
`resolved` flag is `false`. On the pinned commit these describe a missing
evaluation, not a system that solved nothing, and the loader drops them.

## Findings

All numbers come from the retained summary (seed 45, 200 random draws per point).

1. **Successes are strongly dependent.** Mean pairwise φ over all 14,196 pairs of
   competent systems is **0.4763**.
2. **The population has a blind spot.** **26 of 500** tasks (**0.052**, Wilson 95%
   [0.0357, 0.0751]) are resolved by none of the 169 systems. Only **10** tasks are
   resolved by exactly one system.
3. **Independence badly overstates ensemble coverage.** With a perfect
   selector ("oracle best-of-k"), random ensembles cover:

   | k | measured coverage | independence predicts |
   |---:|---:|---:|
   | 1 | 0.5390 | 0.5390 |
   | 2 | 0.7097 | 0.8168 |
   | 5 | 0.8051 | 0.9802 |
   | 10 | 0.8521 | 0.9997 |
   | 40 | 0.9091 | 1.0000 |

4. **A small pilot underestimates the population, and Chao2 recovers part of
   the gap.** Chao2 is ecology's incidence-based richness estimator: tasks play
   the role of species, agents the role of sampling units. A *k*-agent pilot's
   own coverage falls short of the 169-agent coverage (0.948) by 0.1424 at k = 5
   and 0.0965 at k = 10. Chao2 cuts that to a bias of 0.1018 and 0.0607, and to
   0.0079 at k = 40. It is still biased low, as a lower-bound estimator should be.

## What this does and does not show

- It **does** show that the effective-independence problem the paper measured on
  a constructed panel is present, and large, in a real population of
  separately submitted coding systems (many share a model or scaffold) on the *producer* side.
- The blind-spot floor here (0.052) is numerically close to E017's verifier
  floor (λ = 0.0556). They are **different quantities on different instruments**;
  the closeness is not evidence of a shared mechanism.
- Submissions are **not exchangeable samples of "agents"**. Many share a model,
  a scaffold, or an organisation, and leaderboard entry is self-selected. The
  confirmatory analysis must model model × scaffold provenance (the leaderboard
  audit by Liu et al. 2026 shows within-model scaffold ranges up to 29.8 points).
- "Population coverage" is itself a lower bound on what is solvable, so the
  Chao2 bias is measured against an observed reference, not ground truth.
- Oracle best-of-k assumes a **perfect verifier**. Whether real verifiers can
  harvest that coverage is the joint worker × verifier question (program
  hypothesis H4), which this pilot does not touch.
- The owner has now seen the Verified split. Any hypothesis tested on it from
  here on is exploratory. The Lite, Test, Multilingual and Multimodal splits of
  the same repository have **not** been opened and are reserved for confirmation.

## Next

The preregistered confirmatory study, its model families (independence, Kish
design effect, shared shock, beta-binomial, Rasch/2PL IRT, provenance-clustered
IRT, Chao2/iNEXT extrapolation) and its kill criteria are defined in
[`docs/research/SCIENTIFIC_PROGRAM.md`](../docs/research/SCIENTIFIC_PROGRAM.md).
