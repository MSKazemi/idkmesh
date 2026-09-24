---
title: "Reproducing E017: When 25 Verifiers Behaved Like One — IDKMesh"
description: "A concise reproduction guide for IDKMesh E017: 25 programmatic verifiers, measured correlated errors, an effective panel size of 1.00, and a 3.7x quorum improvement."
image: "/assets/idkmesh-social.png"
---

# Reproducing E017: when 25 verifiers behaved like one

E017 is IDKMesh's retained experiment on **measured verifier dependence**. It
does not use synthetic reviewer votes for its headline result: 25 deterministic
partial test oracles vote on a 72-candidate corpus whose correctness is decided
by executable hidden tests.

The main result is deliberately narrow:

> On this programmatic verifier panel, majority voting over 25 reviewers
> produced an error rate of 0.2083, compared with 0.2044 for a single average
> verifier. The measured effective panel size was therefore 1.00 of 25.

The experiment also found that changing the aggregation rule mattered much more
than adding reviewers: requiring at least 24 of 25 acceptance votes reduced the
observed error to 0.0556, about 3.7x below majority vote.

This page gives the shortest reproducible path to those numbers, the retained
artifact identity, and the conditions under which the interpretation should be
revised.

## Retained experiment

Canonical record:

- [E017 — Measured verifier correlation, and why the shared-shock model is the wrong shape](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md)

Retained vote artifact:

- `experiments/results/E017-partial-oracle-votes.jsonl.gz`
- Git blob SHA: `0b710ba6d376da6a688edcc0cab9bf6fb98e322a`
- retained compressed size: 8,535 bytes

Reproduction code:

- `sim/e017_verify.py` — builds and runs the partial-oracle panel;
- `sim/e017_oracles.py` — deterministic input-region generators;
- `sim/e017_analyze.py` — discrimination, correlation, panel-error, effective-size, model-shape, and quorum analysis;
- `tests/test_e017_item_difficulty.py` and `tests/test_e017_oracles.py` — pinned mechanism tests.

The experiment and analyzer use the Python standard library. The analysis does
not need a network connection or an external model API.

## 1. Verify that you have the retained artifact

From a clean repository checkout:

```bash
git hash-object experiments/results/E017-partial-oracle-votes.jsonl.gz
```

Expected Git blob SHA:

```text
0b710ba6d376da6a688edcc0cab9bf6fb98e322a
```

A different hash means you are not analyzing the retained E017 vote artifact
described on this page. That does not make the new artifact invalid, but it is a
different reproduction input and should be reported as such.

## 2. Run the pinned mechanism tests

```bash
python -m pytest -q \
  tests/test_e017_item_difficulty.py \
  tests/test_e017_oracles.py
```

These tests check properties such as deterministic seeded draws, distinct input
regions, the panel-model probability distributions, and the item-difficulty
fit machinery. Passing them verifies the analysis mechanism; it does not by
itself reproduce the observed panel result.

## 3. Analyze the retained votes

```bash
python sim/e017_analyze.py \
  experiments/results/E017-partial-oracle-votes.jsonl.gz \
  --trials 200000
```

The high-value acceptance checks are:

| Quantity | Retained E017 value |
| --- | ---: |
| Verifiers | 25 |
| Verifiers discriminating above chance | 25 / 25 |
| Mean verifier accuracy | 0.7956 |
| Mean within-region error correlation | 0.8924 |
| Mean cross-region error correlation | 0.5263 |
| Mean all-pairs error correlation | 0.5873 |
| Majority-vote panel error | 0.2083 |
| Single-average-verifier error | 0.2044 |
| Measured effective panel size | **1.00 of 25** |
| `N/(1+(N-1)rho)` heuristic | 1.66 |
| 24-of-25 acceptance error | 0.0556 |

The stochastic model checks inside the analyzer use fixed seeds. Tiny
platform-level floating-point differences are possible; the interpretation
should not depend on the last decimal place.

## 4. Regenerate the vote panel

The retained artifact is enough to reproduce the published analysis. To rerun
the verifier panel itself:

```bash
python sim/e017_verify.py \
  --seeds 5 \
  --draws 6 \
  --out /tmp/e017-votes.jsonl
```

Then analyze the regenerated file:

```bash
python sim/e017_analyze.py /tmp/e017-votes.jsonl --trials 200000
```

The panel is five input regions by five seeds: **25 verifiers**. The corpus has
72 candidate solutions from 24 problems.

Do not compare the gzip byte hash of a newly compressed file to the retained
artifact unless compression metadata is normalized. Compare the vote semantics
and analysis outputs instead.

## What was actually observed

### Declared diversity did not imply independence

Verifiers in the same declared input region had mean error correlation 0.8924.
Verifiers in different declared regions still had mean error correlation
0.5263. The region label was informative but did not create an independence
boundary.

### Majority vote added almost no protection

The 25-verifier majority-vote error was 0.2083. The mean single-verifier error
was 0.2044. Mapping the observed panel error back to an idealized independent
panel gave an effective size of **1.00**, despite 25 nominal members.

The common approximation `N_eff = N / (1 + (N - 1) rho)` returned 1.66, still
1.66x above the measured effective size on this panel.

### The shape of dependence mattered

A flat shared-shock model parameterized by the measured mean correlation
predicted a majority error around 0.1216, about 1.7x below the observed 0.2083.

A beta-binomial item-difficulty model at the same parameter count reproduced the
partial-failure shape much better and predicted a panel error of 0.1847. E020
later qualified that model too: it still under-predicts the observed unanimity
floor.

The useful conclusion is not that the beta-binomial is universally correct.
It is that **one pairwise correlation coefficient is not sufficient to describe
this panel's error geometry**.

### Quorum choice mattered more than panel size

These partial test oracles had one-sided errors: a verifier could miss a defect,
but the experiment observed zero false rejects of correct candidates.

| Acceptance threshold | Observed error |
| --- | ---: |
| 1 of 25 | 0.4167 |
| 13 of 25 — majority | 0.2083 |
| 19 of 25 | 0.0972 |
| 24 of 25 | 0.0556 |
| 25 of 25 | 0.0556 |

Changing majority to a 24-of-25 requirement reduced error by about **3.7x**.
Four defective candidates remained invisible to every verifier, producing an
irreducible floor that no quorum could remove.

## What this result does not establish

E017 should not be cited as evidence that 25 LLM judges equal one judge.

The measured verifiers are **programs**, not people or LLMs. Their diversity
structure is deliberately constructed from input regions and random seeds.
Their errors are one-sided because they are partial test oracles. The corpus is
72 candidates from 24 independent problems, all at Python function level.

IDKMesh separately attempted an LLM-verifier correlation experiment in
[E016](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E016-live-verifier-correlation.md).
That panel failed its competence screen, so its near-zero correlation could not
be interpreted as independence.

The transferable E017 lesson is narrower:

> Measure reviewer competence and shared error structure before converting
> reviewer count into an evidence claim.

## What would revise the current interpretation

A useful reproduction should be allowed to disagree. The interpretation should
be revised if, under a correctly matched implementation and corpus:

1. the retained artifact no longer produces the stated headline metrics;
2. independently implemented analysis finds a materially different panel error or correlation structure;
3. a replicated verifier construction produces low cross-region dependence and a majority-vote gain consistent with genuinely independent reviewers;
4. the apparent 3.7x quorum improvement disappears after correcting a bug, leakage, or hidden-test error;
5. broader corpora show that the observed item-difficulty/floor behavior is specific to these 24 problems.

A disagreement should be published with the code, artifact identity, corpus,
and exact aggregation rule. Failed reproduction is useful evidence.

## How to cite or reuse the result

For a technical discussion, link to this reproduction note and the canonical
E017 record. If using IDKMesh software or evidence contracts, the repository
also provides [CITATION.cff](https://github.com/MSKazemi/idkmesh/blob/main/CITATION.cff).

When reusing the headline number, preserve the scope:

> In IDKMesh E017, 25 independently seeded **programmatic partial test
> oracles** had a measured effective panel size of 1.00 under majority vote on a
> 72-candidate / 24-problem corpus.

Do not shorten that to a universal statement about human or LLM review panels.

## Related pages

- [Verifier panels and independent review](https://mskazemi.com/idkmesh/topics/verifier-panels.html)
- [LLM-as-a-judge reliability](https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html)
- [AI agent verification](https://mskazemi.com/idkmesh/topics/ai-agent-verification.html)
- [Research atlas](https://mskazemi.com/idkmesh/research.html)
- [E020 quorum frontier](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E020-quorum-frontier-under-measured-shape.md)

**Last reviewed:** 2026-09-24.
