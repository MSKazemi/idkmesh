# Conversation: Field-Defining Questions and First Research Program

Date: 2026-08-28

## User request

The user asked IDKMesh to identify ten important questions that could help define and advance the field, then said to proceed with the suggested priorities.

Repository: `https://github.com/MSKazemi/idkmesh`

## Ten field-defining questions

1. What is the scaling law of collective intelligence?
2. When does adding more intelligence make the system worse?
3. What is the correct unit of work for collective intelligence?
4. How should independent evidence and useful diversity be measured?
5. Can verification scale as fast as generation?
6. How should a collective reason when the goal itself is uncertain?
7. What incentive system produces truthful, high-quality contribution rather than activity?
8. What trust model allows an open mesh to remain safe?
9. Can the coordination system improve itself without losing control of its objectives?
10. What experiment would convince a skeptical researcher that this field matters?

The full formulation was added to [`FIELD_DEFINING_QUESTIONS.md`](../../FIELD_DEFINING_QUESTIONS.md).

## Unifying objective proposed

Maximize verified useful progress while minimizing human attention, compute, communication, and risk, while preserving useful diversity.

A simplified scaffold is:

`J = VerifiedUtility - lambda_c*Compute - lambda_h*HumanAttention - lambda_m*Communication - lambda_r*Risk + lambda_d*UsefulDiversity`

This is not presented as a final mathematical law. It is a starting point whose terms must be operationalized and tested.

## First three priorities

The conversation selected three research priorities as the initial scientific core:

1. collective-intelligence scaling laws;
2. verification scaling;
3. Work Unit theory.

These were converted into contributor-ready research tracks:

- [Issue #13 — Measure the scaling law of collective intelligence](https://github.com/MSKazemi/idkmesh/issues/13)
- [Issue #14 — Make verification scale with generation](https://github.com/MSKazemi/idkmesh/issues/14)
- [Issue #15 — Define a formal Work Unit for composable distributed work](https://github.com/MSKazemi/idkmesh/issues/15)

Each issue includes falsifiable hypotheses, minimum experiments, primary metrics, deliverables, contribution ideas, and a concrete success criterion.

## Coordinated program

The three issues were combined into [`docs/research/FIRST_RESEARCH_PROGRAM.md`](../research/FIRST_RESEARCH_PROGRAM.md).

The program proposes the following experiment order:

1. create a reproducible experiment harness;
2. establish one-worker baselines;
3. scale generation while holding decomposition roughly fixed;
4. introduce and scale independent verification;
5. vary Work Unit granularity and task/evidence graph structure;
6. run a joint experiment varying worker scale, decomposition, and verification together.

## Candidate headline metric

The program proposes **Verified Useful Work per Unit of Scarce Resource (VUWSR)** as a useful family of metrics, reported separately against compute cost, wall-clock time, human attention, communication, and energy where measurable.

The project should not optimize raw agent count, token count, commit count, or task-completion count as proxies for progress.

## First milestone

The recommended first milestone is deliberately small:

> Run one reproducible benchmark that compares a strong single-agent baseline with several multi-agent configurations, records full cost and verification metrics, and publishes enough evidence for another contributor to reproduce or falsify the result.

The project should scale only after measurements show what deserves to be scaled.
