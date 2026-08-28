# Ten Field-Defining Questions for IDKMesh

IDKMesh sits at the intersection of collective intelligence, multi-agent AI, distributed systems, open-source collaboration, economics, verification, and human-computer interaction. The following questions are intentionally more fundamental than individual implementation choices. A good answer to any one of them could produce reusable theory, benchmarks, algorithms, or design principles for the broader field.

These questions complement the larger catalog in [`RESEARCH_QUESTIONS.md`](../../RESEARCH_QUESTIONS.md).

## 1. What is the scaling law of collective intelligence?

**Question:** How does the verified problem-solving capability of a human+AI network change as we add more agents, more diversity, more compute, and more communication?

We need something analogous to a scaling law:

`Collective capability = f(agent quality, N, diversity, topology, coordination, verification, communication, memory)`

The important result is not simply whether more agents help. We need to identify regimes in which performance is sublinear, linear, superlinear, saturated, or negative.

**Useful evidence:** controlled experiments from 1 -> 10 -> 100 -> 1,000+ workers, with quality, cost, latency, human attention, and error correlation measured together.

## 2. When does adding more intelligence make the system worse?

**Question:** Is there a measurable coordination threshold or phase transition beyond which additional agents increase noise, duplicated work, conflict, security exposure, and verification burden faster than they increase useful output?

A large collective may fail because of coordination complexity even when every individual participant is competent.

**Useful evidence:** a model that predicts the point at which marginal verified value of another participant becomes zero or negative, and mechanisms that move that threshold outward.

## 3. What is the correct unit of work for collective intelligence?

**Question:** What properties must a task have so that thousands or millions of independent humans and agents can work locally while their results remain globally composable?

This is deeper than ordinary task decomposition. The field needs a theory of a **Work Unit**: bounded context, explicit inputs and outputs, dependencies, uncertainty, required evidence, validation rules, permissions, cost, and failure semantics.

**Useful evidence:** a formal Work Unit model and benchmarks showing which decomposition strategies minimize coupling, rework, integration failures, and context requirements.

## 4. How should independent evidence and useful diversity be measured?

**Question:** How can a system distinguish genuinely independent reasoning from 1,000 agents repeating the same correlated mistake?

Raw vote count is not evidence. Model family, prompt lineage, training overlap, information sources, execution traces, code ancestry, and failure patterns may all create hidden dependence.

**Useful evidence:** practical diversity and error-correlation metrics that predict when an additional reviewer or agent materially increases confidence.

## 5. Can verification scale as fast as generation?

**Question:** What architecture allows verification capacity to grow at least as fast as the production of code, claims, plans, and other artifacts?

If generation grows exponentially while trustworthy review remains scarce, the mesh creates an unmaintainable pile of plausible output rather than knowledge.

A possible research target is a **verification law** connecting generation rate, validator diversity, confidence, risk, and allowed integration rate.

**Useful evidence:** adaptive protocols that allocate testing, review, fuzzing, formal methods, replication, and human attention according to expected risk and information gain.

## 6. How should a collective reason when the goal itself is uncertain?

**Question:** How can thousands of participants make progress when they disagree not only about the solution, but about what problem should be solved?

Most coordination systems assume a fixed objective. Real scientific, civic, and software problems contain ambiguous requirements, conflicting values, unknown unknowns, and changing evidence.

**Useful evidence:** representations and algorithms that preserve competing hypotheses, measure confidence, fund exploration, detect convergence, and allow the system to revise goals without erasing dissent or history.

## 7. What incentive system produces truthful, high-quality contribution rather than activity?

**Question:** How can humans and agents be rewarded for information gain, reliability, verification, negative results, calibration, maintenance, and useful disagreement without encouraging spam, collusion, metric gaming, or Sybil attacks?

Contribution quantity is a dangerous proxy for contribution value.

**Useful evidence:** incentive and reputation mechanisms that remain robust under strategic behavior and that reward long-term verified impact rather than visible activity.

## 8. What trust model allows an open mesh to remain safe?

**Question:** How can a system accept useful work and compute from unknown or partially trusted humans, agents, and machines without giving them unsafe authority over the project or each other?

This includes sandboxing, least privilege, reproducibility, provenance, Byzantine behavior, supply-chain security, privacy, data access, and collusion.

**Useful evidence:** a layered trust architecture where the cost of attack grows faster than the value of successful manipulation, while honest newcomers can still contribute easily.

## 9. Can the coordination system improve itself without losing control of its objectives?

**Question:** Under what constraints can IDKMesh modify its own scheduling, decomposition, review, governance, reputation, and communication policies based on measured outcomes?

Self-improvement creates a Goodhart problem: once a metric controls evolution, the system may optimize the metric rather than the underlying purpose.

**Useful evidence:** a safe evolutionary loop with immutable or slowly changing constraints, shadow evaluation, rollback, adversarial testing, multi-objective metrics, and explicit human governance over high-impact changes.

## 10. What experiment would convince a skeptical researcher that this field matters?

**Question:** What single reproducible benchmark or demonstration would provide strong evidence that large-scale human+AI collective intelligence offers capabilities that centralized teams or single powerful models do not?

A field needs a falsifiable flagship result, not only architecture diagrams.

A strong experiment might show that a heterogeneous decentralized team can solve, verify, and maintain a difficult real-world task with better **verified useful work per unit of human attention and compute** than strong centralized baselines.

**Useful evidence:** an open benchmark with hidden tests, security evaluation, cost accounting, failure analysis, reproducible traces, and baselines ranging from one strong model to structured multi-agent and human teams.

---

## A possible unifying research objective

Many of these questions can be connected through one optimization target:

> **Maximize verified useful progress while minimizing human attention, compute, communication, risk, and loss of useful diversity.**

A simplified research objective could be written as:

`J = VerifiedUtility - lambda_c*Compute - lambda_h*HumanAttention - lambda_m*Communication - lambda_r*Risk + lambda_d*UsefulDiversity`

The exact form should not be treated as truth. The research challenge is to define measurable terms, discover their interactions, and test which formulations predict real outcomes.

## Suggested priority

If IDKMesh can answer only three questions first, prioritize:

1. **Scaling law of collective intelligence** — establishes whether and when scale creates value.
2. **Verification scaling** — determines whether that value can remain trustworthy.
3. **Work Unit theory** — determines whether useful work can actually be distributed and recombined.

Together, these three could form the scientific core around which the rest of the project develops.
