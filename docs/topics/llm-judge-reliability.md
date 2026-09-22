---
title: "LLM-as-a-Judge Reliability and Evaluator Bias — IDKMesh"
description: "How to reason about LLM-as-a-judge reliability: evaluator calibration, correlated errors, panel independence, evidence classes, and authority boundaries."
image: "/idkmesh/assets/idkmesh-social.png"
---

# LLM-as-a-judge reliability

**An LLM-as-a-judge is an evaluator, not an oracle.** Its verdict becomes useful only to the extent that its error rate, calibration, independence, task fit, and authority are understood.

IDKMesh's broader verification work applies the same discipline to any automated evaluator: record what the evaluator saw, what plan it used, what artifacts it judged, and what evidence supports its conclusion.

## Do not confuse agreement with independence

A panel can contain many judges and still behave like far fewer independent judges if they fail on the same items. IDKMesh therefore distinguishes nominal panel size from **effective independent votes**.

The project's E017 experiment measured this effect using independently seeded partial **test oracles—programs, not language models**—on a real defect corpus. It is evidence about correlated verification errors and quorum design, not a claim that the same numeric result applies to LLM judges.

See [verifier panels](verifier-panels.html) and the retained [E017 record](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md).

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

[Browse all AI-agent trust topics](https://mskazemi.com/idkmesh/topics/).

**Last reviewed:** 2026-09-22.
