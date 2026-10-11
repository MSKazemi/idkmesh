# E047 — The H1 result survives removing duplicate models, and choosing agents by model organisation loses to choosing by complementarity

**Status:** exploratory. Every split analysed here had been opened before this
code was written, so nothing below is confirmatory. It tests E046's main
disclosed threat: leaderboard submissions are not exchangeable agents.
**Program items:** T1 (#974), robustness of H1 (X3, #975), the deferred
declared-diversity arm of H3 (X5, #977).

## Provenance

[`submission_provenance.py`](submission_provenance.py) downloads each
submission's `metadata.yaml` from `SWE-bench/experiments@40f164d5` and never
vendors it. It parses:

- the model, falling back to the display name;
- the model organisation;
- the scaffold;
- the number of attempts.

Model names are canonicalised: provider prefixes, date and `latest` suffixes,
and punctuation are stripped, and tokens are sorted, so `claude-3-opus-20240229`,
`Claude 3 Opus` and `claude-opus-3-latest` become one model. Placeholders
(`[]`, "multiple", "mixed models", "undisclosed") count as unknown. The
retained output, including the per-submission table, is
[`results/E047-provenance-aware.json`](results/E047-provenance-aware.json).

| split | competent submissions | distinct models | no model recorded | model organisations | multi-attempt submissions |
|---|---:|---:|---:|---:|---:|
| verified | 169 | 66 | 31 | 12 | **81** |
| lite | 78 | 15 | 19 | 4 | 10 |

The leaderboard is much less diverse than its row count suggests.

- 169 Verified rows come from 66 identifiable models and 12 model
  organisations.
- Nearly half of them (81) are themselves multi-attempt systems, already a form
  of ensemble.

## H1 with one submission per model

The frozen E046 functions (`analysis_sha256 = 67aa3068…`, unchanged) were re-run
on a population with **one submission per model**. The representative is the
lexicographically first submission name, chosen blind to outcomes. Submissions
without a model are each kept as their own group.

| split | population | beta-binomial curve error | Kish | shared shock | Kish − beta-binomial, 95% CI | shared shock − beta-binomial, 95% CI |
|---|---:|---:|---:|---:|---|---|
| verified | 97 | 0.0430 | 0.0888 | 0.0814 | [0.0254, 0.0741] | [0.0216, 0.0616] |
| lite | 34 | 0.0304 | 0.1389 | 0.0525 | [0.0795, 0.1304] | [0.0025, 0.0367] |

**H1 holds on both splits after deduplication.** Every interval excludes zero.
On Lite the margin over shared shock narrows (its lower bound is 0.0025), so
that comparison is the weakest link.

The beta-binomial's population-coverage error on deduplicated Lite is 0.0281,
inside the 0.03 tolerance. On deduplicated Verified it is 0.0496, outside it.
That matches E046's verdict that H2 is fragile.

Blind-spot floors rise once duplicates are removed, because fewer distinct
systems cover less:

- Lite: from 0.1167 to **0.19**;
- Verified: from 0.052 to **0.072**.

## Declared diversity versus complementarity (the H3 arm deferred to T1)

The comparison is between two selectors, each fitted on the calibration half
and scored on the held-out half of the tasks (same split as E046):

- **greedy complementarity selection;**
- **top-k by accuracy with at most one submission per model organisation.**

Submissions with no recorded organisation count as distinct organisations,
which favours the diversity selector.

| split | k | greedy | one per organisation | only greedy | only diverse | exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| lite | 3 | 0.7742 | 0.6968 | 18 | 6 | 0.0227 |
| lite | 5 | 0.8258 | 0.7290 | 19 | 4 | **0.0026** |
| lite | 10 | 0.8516 | 0.7677 | 16 | 3 | 0.0044 |
| verified | 5 | 0.8898 | 0.8701 | 6 | 1 | 0.125 |
| verified | 10 | 0.9016 | 0.8819 | 7 | 2 | 0.180 |

Choosing agents by **declared** diversity (one per model organisation) never
beats choosing them by **measured** complementarity. On Lite it is clearly
worse. This is the worker-side counterpart of the panel paper's finding that
declared verifier groups misstate independence.

## Limits

- Exploratory. Both splits were seen before this analysis.
- Model canonicalisation is a heuristic. It can merge two distinct models that
  share tokens, or miss aliases that use other names. Unknown-model
  submissions may duplicate known ones.
- Deduplicating to the first name is one outcome-blind rule among several. It
  does not identify the "true" independent set.
- A confirmatory version needs data published after 2026-10-09, since all five
  splits are now seen.
