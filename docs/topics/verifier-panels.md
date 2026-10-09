---
title: "How Many Independent Votes Is a Verifier Panel Worth?"
description: "Correlated errors shrink a verifier or LLM-judge panel's effective votes: 1.00 of 25 measured in E017, when N/(1+(N-1)rho) misleads, and how to audit."
image: "/assets/idkmesh-social.png"
---

# Verifier panels and independent review

**A verifier panel is only as strong as the independent evidence its members contribute.** Ten reviewers that fail on the same cases may be worth much less than ten independent votes.

This problem is central to IDKMesh because agentic systems can cheaply create both candidates and reviewers. Counting votes without measuring dependence can make a review gate look stronger while adding little real protection.

## How many independent votes is a verifier panel worth?

**Short answer: fewer than its head-count whenever its members fail on the same items, and the only reliable way to know how many is to measure their verdicts against cases with known outcomes.** On an observed 25-verifier panel in [E017](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md) — every verifier a program, not an LLM judge — majority vote was worth **1.00** independent vote. A separate 2026 study of nine frontier LLM judges reports a panel worth about two independent votes ([Kohli, arXiv:2605.29800](https://arxiv.org/abs/2605.29800)).

Here, *effective independent votes* means the size of a panel of truly independent verifiers, at the same mean accuracy, that would make the same panel error. `idkmesh gate-audit` reports it as `panel.effective_votes`; see the [Gate Audit v0.1 field reference](https://mskazemi.com/idkmesh/specifications/GATE_AUDIT_V0_1.html).

## The design-effect formula, and when it is optimistic

The usual shortcut is the Kish design effect applied to votes, where `rho` is the mean pairwise error correlation between panel members:

```text
N_eff = N / (1 + (N - 1) * rho)
```

With E017's measured `rho = 0.5873` and `N = 25`, the formula gives 25 / (1 + 24 × 0.5873) ≈ **1.66**. The measured effective size was **1.00**, so on that panel the formula overstated the independent evidence by 1.66x.

The reason is that one average correlation does not describe *where* errors fall. E017's errors clustered by item: four defects were missed by all 25 verifiers, and most panel failures were partial majorities rather than unanimous misses — a shape that a single shared-correlation model under-predicts. In a simulated grid that assumes that item-difficulty shape, [E018](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E018-dependence-model-shape.md) reports the formula overstating independence in 441 of 441 cells, against 17 of 441 under a shared-shock model — a result about the assumed shape, not about every panel.

The formula is not always wrong. On Kohli's nine-judge natural-language-inference panel, the paper reports that the empirical curve closely tracks the Kish prediction (about 2.18 effective votes at a mean correlation of 0.391). The two results together support a conditional rule rather than a universal one: **the formula is only as good as the assumption that one correlation summarizes your panel's dependence — measure the panel before trusting it.**

## Run the audit from a repository clone

`gate-audit` is not published on PyPI yet; install it from a clone. It is standard-library only.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

Without installing anything, `python3 -m idkmesh.cli gate-audit examples/gate-audit/panel-votes.example.json --pretty` runs the same audit from the repository root. An excerpt of the report:

```text
"evidence_class": "synthetic",
...
"nominal_votes": 5,
"effective_votes": 1.6944444444444438,
"heuristic_n_eff": 3.6588245300435087,
```

The bundled input is a **synthetic** demonstration, and the report says so in `evidence_class`; its numbers show the output format and are not a measurement of any real panel. To audit your own gate, replace it with verdicts you collected on candidates with a known `ground_truth`, plus seeded known-bad probes, following the input format in the specification linked above. The report is diagnostic and grants no acceptance or merge authority.

## Related 2026 work on correlated judges

- **Kohli, [*Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels*](https://arxiv.org/abs/2605.29800).** Nine frontier LLMs from seven model families on three natural-language-inference datasets provide about two independent votes; the best single judge matches or outperforms the full panel, and established aggregation methods close at most 11% of the gap. This paper reached the "reviewer count is not evidence count" conclusion for LLM judges; IDKMesh does not claim priority for it. E017 adds a different setting — executable ground truth, programmatic verifiers, one-sided missed-defect errors, and quorum consequences — in which the Kish formula was optimistic rather than accurate.
- **Xin, [*Are Verifier Errors Independent Within a GRPO Group? Evidence from Qwen2.5 Rollouts*](https://arxiv.org/abs/2609.06386).** Across 24,998 eight-completion groups, the pooled within-group verifier-error correlation is 0.530, which under an exchangeable-error model corresponds to an effective sample size of 1.70 per group. This is dependence across completions scored by one verifier, not across a panel of evaluators.
- **Shu, [*Blind to the Pivotal Vote: Aggregate Independence Metrics Miss Where Verification Actually Helps*](https://arxiv.org/abs/2608.06940).** Adding a different evidence source, such as executing a test suite, produced no distinguishable change in a panel's effective-vote count, yet its entire accuracy gain concentrated on decisions with a one-vote margin. Effective votes and decision-level utility are complementary measurements.
- **Shu, [*When Verifiers Vote Backwards under Verdict Substitution: Signed Pivotal Value in Correlated Self-Consistency*](https://arxiv.org/abs/2609.26144).** Substituting one verdict can change only one-vote-margin decisions, and the sign of that change can be negative: on MATH-500 a different-model verifier gave a +24.2 percentage-point pivotal gain while a role-reversed configuration gave −11.2 points.

## Nominal votes versus effective votes

A panel's nominal size is the number of reviewers. Its effective size asks how much independent information the panel actually contains.

IDKMesh's `gate-audit` diagnostic accepts a matrix of observed verdicts and reports:

- effective independent votes;
- error-correlation structure;
- the behavior of seeded known-bad probe candidates.

The tool is diagnostic. It does not grant acceptance or merge authority.

## Why correlated errors matter

Reviewers can correlate because they share the same tests, training data, architecture, prompt, blind spot, or task misunderstanding. Majority voting assumes more than "different names in the panel"; it depends on how errors line up across items.

That is why IDKMesh treats verifier diversity as an empirical property rather than a label.

## Quorums do not repair every panel

Raising a quorum can help only when the panel contains useful discriminating evidence. If reviewers systematically miss the same defect, requiring more of the same votes does not create new information.

The right response may be to change the evaluator, add a different kind of evidence, improve hidden tests, or route difficult cases to a human specialist. For automated judges, see [LLM-as-a-judge reliability](https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html).

## What IDKMesh measured on an observed verifier panel

[E017](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md) measured a panel of **25 independently seeded partial test oracles** over a **72-candidate** corpus whose ground truth came from hidden tests. These verifiers were programs, not people or LLM judges, and every recorded error was a genuine missed defect.

The observed panel looked large but carried far less independent evidence:

| Measurement | Observed result |
| --- | ---: |
| Mean verifier accuracy | 0.7956 |
| Mean pairwise error correlation | 0.5873 |
| Majority-vote panel error | 0.2083 |
| Single-verifier error | 0.2044 |
| Measured effective panel size | **1.00 of 25** |
| Common N/(1+(N-1)rho) heuristic | 1.66 |
| Error with a 24-of-25 acceptance quorum | 0.0556 |

Under majority vote, the 25-verifier panel was therefore no better than a single member on that corpus. The common effective-size heuristic still overstated the measured panel by 1.66x.

The highest-leverage change was not adding reviewers. Because the test-oracle errors were one-sided missed defects, changing the aggregation rule from majority acceptance to a much stricter quorum cut error from **0.2083 to 0.0556**, about **3.7x**. Four defects remained invisible to every verifier, so no quorum could eliminate the floor.

## What that result does not prove

It is evidence about this measured programmatic panel, not a universal constant for human reviewers or LLM judges. The verifier diversity structure was constructed, the corpus contains 72 candidates from 24 problems, and the one-sided error property comes from partial test oracles.

IDKMesh attempted a live LLM-verifier measurement earlier in [E016](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E016-live-verifier-correlation.md), but the 20 LLM verifiers did not discriminate above chance strongly enough to make their correlation estimate meaningful. The repository therefore does **not** claim that a 25-LLM panel is worth one vote.

The transferable lesson is narrower and more useful: **measure reviewer competence and shared error structure before treating reviewer count as independent evidence.**

Reproduce the retained votes, analysis, and acceptance metrics with the [E017 reproduction guide](https://mskazemi.com/idkmesh/research/E017_VERIFIER_PANEL_REPRODUCIBILITY.html).

## Common questions

<a id="q-what-is-an-effective-independent-vote"></a>
### What is an effective independent vote?

It is a way of expressing how much independent information a correlated panel contains relative to an idealized set of independent reviewers.

<a id="q-how-do-i-measure-review-panel-reliability"></a>
### How do I measure review panel reliability?

Collect verdicts on cases with known or externally established outcomes, inspect per-item errors, measure dependence/correlation, and include seeded probes that the gate should reject.

<a id="q-are-more-ai-reviewers-always-better"></a>
### Are more AI reviewers always better?

No. More reviewers increase value only when they add sufficiently independent useful evidence relative to their cost and latency.

<a id="q-what-is-a-verification-quorum"></a>
### What is a verification quorum?

A quorum is the threshold or rule used to turn individual verification results into a panel-level recommendation. Its usefulness depends on reviewer quality and dependence.

<a id="q-how-can-i-try-this-in-idkmesh"></a>
### How can I try this in IDKMesh?

Run the [gate-audit quickstart](https://mskazemi.com/idkmesh/start.html) and read the [Gate Audit v0.1 specification](https://mskazemi.com/idkmesh/specifications/GATE_AUDIT_V0_1.html).

<a id="q-how-do-i-choose-diverse-verifiers"></a>
### How do I choose diverse verifiers?

Choose evaluators that differ in evidence source, implementation, model family, tests, or expertise where those differences are relevant to likely failure modes. Diversity is valuable when it reduces shared blind spots, not when it is only cosmetic.

<a id="q-what-is-correlated-verifier-error"></a>
### What is correlated verifier error?

It means multiple reviewers are wrong on the same items more often than independent reviewers would be. Correlation reduces how much new information each additional vote contributes.

<a id="q-how-should-i-set-a-verification-quorum"></a>
### How should I set a verification quorum?

Set it from measured reviewer performance, risk tolerance, and the cost of false acceptance versus false rejection. A quorum should be validated on representative cases rather than copied from panel size alone.

<a id="q-when-should-a-verifier-panel-abstain"></a>
### When should a verifier panel abstain?

Abstention is appropriate when required evidence is missing, reviewers disagree beyond the calibrated decision boundary, or the case is outside the evaluators' demonstrated competence.

<a id="q-how-do-i-detect-fake-diversity-in-a-review-panel"></a>
### How do I detect fake diversity in a review panel?

Compare item-level error patterns, prompts, tools, data sources, model/provider lineage, and evaluator design. Nominally different reviewers that fail on the same cases are not providing much independent protection.

[Browse all AI-agent trust topics](https://mskazemi.com/idkmesh/topics/).

**Last reviewed:** 2026-10-09.
