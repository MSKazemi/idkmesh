# IDKMesh Research Questions

This document captures open questions that should drive experiments, prototypes, literature review, and architecture decisions.

## Collective coding and quality

- Can many smaller AI coding agents collectively match or exceed a larger model on software-engineering tasks?
- Under what conditions does ensemble size improve quality, and when do correlated errors cause failure?
- How should diversity between models, prompts, tools, data sources, and reasoning strategies be measured?
- What is the minimum verification structure needed before an AI-generated change can enter an enterprise-grade codebase?
- Is it better to parallelize generation, criticism, testing, formal verification, or all four?
- How should the system measure marginal value of an additional agent?

## Ambiguous goals and collaborative discovery

- How can a community collaborate when participants do not initially share the same interpretation of the goal?
- How should uncertainty, competing hypotheses, and unresolved requirements be represented in the project graph?
- Can multi-armed bandits, MCTS, or Bayesian experimental design allocate attention to competing interpretations?
- When should the system converge on one architecture, and when should it deliberately preserve multiple competing branches?
- Can exploration temperature be controlled explicitly over the life cycle of a project?

## Task decomposition

- How can a high-level objective be decomposed into tasks that are independently solvable but safely composable?
- What graph structures best represent code dependencies, evidence, assumptions, tests, and decisions?
- Can decomposition quality itself be learned or evolved?
- How should cross-cutting requirements such as security, reliability, and observability be represented so they are not lost during decomposition?

## Distributed compute

- Which tasks are well suited to unreliable commodity laptops, and which require tightly coupled infrastructure?
- What scheduling algorithm performs best under heterogeneous CPU/GPU/memory/bandwidth and unpredictable churn?
- How effective are work stealing, min-cost flow, auctions, or learned scheduling at different network scales?
- How much redundancy is economically justified for validation?
- When should replication be replaced by erasure/coded computation?
- How should data locality and privacy constrain task placement?

## Consensus and state

- Which state requires strong consensus and which state can remain eventually consistent?
- Where are CRDTs sufficient?
- How should the system limit expensive global coordination?
- Can local or hierarchical consensus provide most benefits at much lower communication cost?
- What Byzantine tolerance is needed for different trust domains?

## Reputation, incentives, and economics

- How should reliability, expertise, novelty, and calibration be represented separately?
- Can Bayesian reputation models handle newcomers more fairly than simple point scores?
- How should correlated contributors be discounted so a cluster of similar agents cannot dominate by volume?
- Can proper scoring rules incentivize truthful uncertainty reports from AI agents and humans?
- Can Shapley-value approximations meaningfully measure contribution in software and research workflows?
- Which anti-Sybil mechanisms are compatible with openness and privacy?
- Is a financial/token incentive actually needed, or can reputation, access, recognition, and reciprocal compute be sufficient?
- What game-theoretic equilibria emerge under different reward schemes?

## Governance

- How can a large open-source community make decisions without either chaos or permanent centralized gatekeeping?
- Which decisions should be meritocratic, democratic, delegated, experimentally selected, or protected by constitutional rules?
- Can multiple governance mechanisms coexist at different layers?
- How should disputes between empirical evidence, maintainer judgment, and community preference be resolved?
- How can governance itself be measured and improved?

## Robustness and adversaries

- What fraction of faulty or malicious nodes can each validation protocol tolerate?
- How can colluding agents be detected when they submit mutually consistent but false results?
- How should the system distinguish correlated honest error from coordinated manipulation?
- Which critical components should require formal verification?
- How should provenance and supply-chain integrity work across thousands of autonomous contributors?

## Information theory and diversity

- What measure best distinguishes useful diversity from random noise?
- Can mutual information or error-correlation metrics estimate whether another agent adds independent evidence?
- How should the system price or reward information gain?
- Can entropy thresholds help decide when to explore versus converge?

## Evolutionary mechanisms

- Can scheduling, review, aggregation, and governance mechanisms compete experimentally and receive resources according to measured performance?
- How do we prevent evolutionary optimization from exploiting proxy metrics instead of real project goals?
- What safeguards are required before the platform is allowed to modify its own coordination policies?

## Statistical physics inspiration

- Are percolation models useful predictors of network survivability under churn?
- Can simulated-annealing schedules improve collective architecture search?
- Do spin-glass analogies yield practical methods for highly coupled software design constraints, or are they merely descriptive metaphors?
- Can synchronization models identify harmful over-convergence among agents?

## Distributed learning

- When does federated or DiLoCo-like training make sense on volunteer or community compute?
- How should non-IID data, asynchronous participation, bandwidth limits, and malicious updates be handled together?
- Which compression and local-training strategies minimize communication without degrading model quality?

## Open-source community and dissemination

- What existing open-source governance models scale best to thousands of contributors?
- Which contribution pathways allow non-experts, domain experts, researchers, and compute donors all to contribute meaningfully?
- How should documentation, benchmarks, onboarding, issue design, and public experiments be structured to attract contributors?
- What evidence or prototype would make IDKMesh compelling enough to earn organic attention and GitHub stars?

## Early experiments

1. Compare 1 large coding model versus ensembles of smaller heterogeneous models on the same repository task set.
2. Measure accuracy against ensemble size while deliberately varying error correlation.
3. Compare majority vote, log-odds weighting, Bayesian aggregation, and robust aggregation.
4. Build a small goal/task/evidence DAG and test human+agent decomposition workflows.
5. Simulate 10/100/10,000 heterogeneous compute nodes with churn and compare centralized scheduling, work stealing, and matching algorithms.
6. Simulate Byzantine workers and compare replication, quorum, median/trimmed mean, and coded computation.
7. Test a CRDT-backed shared task state under partitions and reconnection.
8. Run a multi-armed-bandit experiment that dynamically reallocates compute among competing agent strategies.
9. Evaluate proper scoring rules for agent confidence calibration.
10. Prototype a contribution graph and compare simple reputation to Bayesian and approximate-Shapley approaches.

Each experiment should specify a falsifiable hypothesis, baseline, metric, dataset/workload, and stopping rule before execution.
