---
title: "LLM-as-a-Judge Reliability and Evaluator Bias — IDKMesh"
description: "LLM-as-a-judge reliability with measured failure evidence: calibration, discrimination, bias, correlated errors, panel independence, and authority boundaries."
image: "/assets/idkmesh-social.png"
---

# LLM-as-a-judge reliability

**An LLM-as-a-judge is an evaluator, not an oracle.** Its verdict becomes useful only to the extent that its error rate, calibration, independence, task fit, and authority are understood.

IDKMesh's broader verification work applies the same discipline to any automated evaluator: record what the evaluator saw, what plan it used, what artifacts it judged, and what evidence supports its conclusion.

## Do not confuse agreement with independence

A panel can contain many judges and still behave like far fewer independent judges if they fail on the same items. IDKMesh therefore distinguishes nominal panel size from **effective independent votes**.

The project's E017 experiment measured this effect using independently seeded partial **test oracles—programs, not language models**—on a real defect corpus. It is evidence about correlated verification errors and quorum design, not a claim that the same numeric result applies to LLM judges.

See [verifier panels](https://mskazemi.com/idkmesh/topics/verifier-panels.html) and the retained [E017 record](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md).

## What IDKMesh actually measured with LLM verifiers

IDKMesh attempted to measure live LLM-verifier error correlation in [E016](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E016-live-verifier-correlation.md). The result was negative in a useful way: **the deployed judges were not competent enough for their correlation numbers to mean what we wanted them to mean.**

The experiment used **20 verifiers** built from four open-weight model families and five prompt templates, producing **1,440 votes** over 72 Python candidate solutions with executable hidden-test ground truth.

| Measurement | E016 result |
| --- | ---: |
| Mean accuracy | 0.4743 |
| Mean Youden J | +0.0487 |
| Judges significantly above J=0 after correction | **0 of 20** |
| 20-judge majority-vote accuracy | 0.514 |
| Trivial always-reject accuracy | **0.639** |
| Unparseable votes | 7.0% |

Six judges emitted one constant verdict for all 72 tasks, three more emitted one verdict at least 95% of the time, and no individual judge showed discrimination above chance after correction.

That means the tempting near-zero pairwise error correlation reported by the analyzer was **not evidence of independence**. Noise and constant decision rules can also produce near-zero correlation. E016 therefore blocks the correlation interpretation rather than publishing a plausible-looking independence number.

## The practical lesson from the failed experiment

Before asking whether LLM judges are independent, first establish that they are actually judging the task. On an imbalanced corpus, raw accuracy can make a constant strategy look competent: in E016, rejecting every candidate without reading it scored 0.639, better than the 20-judge majority.

For a future LLM-judge panel, IDKMesh's preregistered retry gate requires discrimination checks before any correlation analysis: multiple judges significantly above chance, mean panel accuracy above 0.5 on a base-rate-balanced corpus, low parse failure, and no near-constant judges.

The experiment used small 1–2B open models and Python function-level correctness tasks. It does **not** establish that larger current models, commercial models, or LLM judges in other domains are unreliable. It establishes that evaluator competence must be measured before agreement, correlation, or panel size can be interpreted.

## What to measure in an LLM evaluator

A serious evaluator study should separate several questions:

- **accuracy:** does the judge reach the right conclusion on known cases?
- **calibration:** does reported confidence correspond to observed correctness?
- **stability:** does the verdict change under irrelevant prompt/order variations?
- **bias:** are some answer styles, providers, identities, or positions systematically preferred?
- **dependence:** do judges make errors on the same items?
- **coverage:** what kinds of failures can the evaluator not observe?
- **authority:** what is the verdict allowed to change?

A high average agreement score cannot answer all of these.

## Common questions

### Is LLM-as-a-judge reliable?

Sometimes, for a defined task and measured evaluator. Reliability should be established on representative cases and reported with limitations; it should not be inferred from model reputation.

### Does using several LLM judges make evaluation independent?

Not necessarily. Different models can share training data, prompts, abstractions, and item-level failure modes. Measure error dependence rather than counting brands.

### What is LLM judge calibration?

Calibration asks whether the evaluator's confidence or score meaningfully corresponds to correctness or outcome frequency. It is distinct from simple agreement.

### Should an LLM judge decide whether code is merged?

It can contribute evidence. Final integration authority should remain a separate policy decision, especially for security-sensitive or high-impact changes.

### How does IDKMesh represent evaluator evidence?

See the [EvaluatorPlan and VerificationResult specifications](https://github.com/MSKazemi/idkmesh/tree/main/docs/specifications) and [schema index](https://github.com/MSKazemi/idkmesh/blob/main/schemas/README.md).

### Can ChatGPT, Claude, or Gemini be used as an LLM judge?

They can be used as evaluators when the task, rubric, model/version, prompt, and observed reliability are recorded. Brand or model size alone does not establish that a judge is accurate for a particular evaluation.

### How can I reduce LLM-judge bias?

Use explicit rubrics, blinded ordering where possible, counterbalanced prompts, held-out calibration cases, multiple evidence types, and measurements for systematic preference rather than relying on one prompt format.

### Should an LLM judge know which model generated the answer?

Often it is safer to hide irrelevant producer identity when measuring output quality, because model names can introduce preference bias. Keep identity available in provenance even when it is blinded from the scoring prompt.

### How many LLM judges are enough?

There is no universal number. Add judges only while they contribute useful independent information relative to cost and latency; correlated judges can make a large panel behave like a much smaller one.

### What should happen when an LLM judge is uncertain?

Preserve or expose the uncertainty, request additional evidence, use a different evaluator class, or escalate to a human rather than forcing every case into an accept/reject verdict.

[Browse all AI-agent trust topics](https://mskazemi.com/idkmesh/topics/).

**Last reviewed:** 2026-09-23.
