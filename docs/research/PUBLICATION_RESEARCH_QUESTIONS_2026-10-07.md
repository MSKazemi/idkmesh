# Publication-Oriented Scientific Questions for IDKMesh

**Date:** 2026-10-07  
**Status:** publication strategy / research agenda  
**Repository baseline inspected:** `main@7ac46d39ba629fce7dafc4b25c69cbcee5c1f03e`  
**Evidence rule:** implemented mechanisms, synthetic experiments, observed real runs, and independently reviewed empirical evidence are different evidence classes and must never be merged rhetorically.

## 1. Scientific thesis

IDKMesh should not try to publish the claim that "swarms are better."

The scientifically useful thesis is narrower and falsifiable:

> **Under fixed compute, verification, communication, and human-attention budgets, when does adding heterogeneous human/AI participation increase independently verified useful work, when does it merely duplicate correlated error, and when does coordination or verification cost make the collective worse?**

That thesis creates a coherent research program around four quantities:

[
	ext{useful generation}
	imes
	ext{composability}
	imes
	ext{verification quality}
-
	ext{coordination cost}
-
	ext{failure cost}.
]

The expression is a scaffold, not a proven law. Each paper should operationalize only the terms it actually measures.

### Primary outcome family

Do not optimize raw agents, commits, votes, tokens, or accepted candidates. Report **Verified Useful Work per Unit of Scarce Resource (VUWSR)** as a vector:

- independently verified task success / useful output;
- escaped defects and failure severity;
- candidate-generation compute;
- verification compute;
- wall-clock latency;
- human attention;
- communication / coordination traffic;
- duplicated work;
- energy where measurable.

A paper may define one primary endpoint, but it must keep the underlying cost/quality vector visible.

## 2. What makes an IDKMesh question paper-worthy?

A question should become a manuscript only when it has all six:

1. **Falsifiable hypothesis** — a result can make the preferred mechanism lose.
2. **Strong baseline** — not only a weak strawman.
3. **Matched budget** — gains cannot come only from spending more.
4. **Correct unit of analysis** — tasks/items are not replaced by repeated attempts as fake independent samples.
5. **Evidence gate** — synthetic evidence is not presented as real-task evidence.
6. **Kill criterion** — the project states what observation would make the claim uninteresting or false.

This is the filter used below.

## 3. Current novelty check: where the literature has moved

This is a **targeted novelty check as of 2026-10-07, not a systematic literature review**.

Several adjacent results now exist, so IDKMesh should position papers around what its evidence uniquely adds rather than around broad slogans.

| Related work | What is already established | Consequence for IDKMesh |
| --- | --- | --- |
| [Kim et al., *Correlated Errors in Large Language Models*, ICML 2025](https://proceedings.mlr.press/v267/kim25e.html) | Large-scale evidence that LLM errors are correlated, including across strong models/providers. | "LLM errors are correlated" is not novel enough by itself. |
| [Kohli, *Nine Judges, Two Effective Votes*, 2026](https://arxiv.org/abs/2605.29800) | A 9-judge LLM panel can contain only about two independent votes; the best single judge can match/outperform the panel. | "Reviewer count is not evidence count" now has direct prior art. IDKMesh must lead with **dependence shape, executable ground truth, partial failures, blind spots, and quorum consequences**. |
| [Zhao et al., *CARE: Confounder-Aware Aggregation for Reliable LLM Evaluation*, ICML 2026](https://proceedings.mlr.press/v306/zhao26aq.html) | Correlated judge errors can arise from latent confounders; confounder-aware aggregation is an active method direction. | A new IDKMesh verifier paper must compare model/aggregation assumptions, not imply majority vote is the only alternative. |
| [Iyer et al., *Multiagent Quality-Diversity for Effective Adaptation*, ECAI 2025](https://doi.org/10.3233/FAIA251201) | Quality-diversity can improve adaptation in multi-agent learning. | "QD helps adaptation" is not enough. IDKMesh's differentiator is **goal geometry + imperfect/correlated verification + latent defects + adversarial gate pressure**. |
| [Krentsel et al., *Reality Is the Final Verifier*, 2026](https://arxiv.org/abs/2609.12039) | Agentic software engineering has unavoidable requirement/model gaps; verification is a resource-allocation problem. | IDKMesh's verification-capacity work should provide **measured/control evidence**, not only repeat the verification-first argument. |

### Immediate implication for the current manuscript

The canonical paper at `paper/main.tex` is still the closest IDKMesh asset to submission, but its strongest novelty is **not** the headline fact that correlated panels contain fewer effective votes.

The more defensible contribution stack is:

1. **execution-decided ground truth** on a 25-program verifier panel;
2. **partial panel failure** as the dominant observed failure shape;
3. evidence that a **shared-shock dependence model is structurally wrong** for this panel;
4. a same-parameter **item-difficulty / beta-binomial model** that fits that shape better;
5. an **irreducible all-verifier blind spot** that neither ordinary quorum changes nor panel growth removes;
6. consequences for **quorum design and aggregation under measured dependence**.

A stronger positioning/title candidate is therefore:

> **Dependence Shape Matters: Partial Failures, Blind Spots, and Quorum Limits in Executable Verification Panels**

The current title may remain for continuity, but the abstract/introduction should make the six items above—not "many reviewers are not many independent votes"—the novelty claim.

## 4. Ranked scientific questions

| Rank | Research question | Null / falsifier | Current evidence | Missing gate | Publication state |
| ---: | --- | --- | --- | --- | --- |
| **1** | **RQ1 — What dependence structure actually governs verifier-panel failure?** | Pairwise correlation plus a simple shared-shock model predicts the observed failure-count/quorum behavior adequately. | E017–E020; 25 real executable partial oracles; measured failures and blind spots. | Replication on at least one materially different verifier/task family would strengthen external validity. | **Closest to submission. Reposition novelty.** |
| **2** | **RQ2 — Under fixed total budget, when is another coding agent worth adding?** | After matching compute/verification budget, heterogeneous multi-agent systems provide no positive marginal verified value over the best single/replicated baseline. | R1/E032/E040 synthetic mechanism work. | Frozen real held-out coding corpus (#70), independent verification, real dependence measurement. | **Highest-impact next empirical paper.** |
| **3** | **RQ3 — When does diversity beat replication, and what does diversity cost?** | Any apparent gain disappears when candidate quality, budget, and correlation are controlled. | R1 help/hurt sweeps show correlation controls effect size while worker-quality penalty can flip the sign. | Same as RQ2; must measure real diversity/correlation instead of configuring it. | **Combine with RQ2, do not salami-slice.** |
| **4** | **RQ4 — How should verification capacity control generation pressure?** | Adaptive backpressure does not improve the defect/backlog/cost Pareto frontier over simpler fixed policies. | E021/E022/E043/E044; AVE ablations; deterministic queue/control mechanisms. | Replay/shadow evaluation on real workload traces and observed review/service times. | **Strong systems/control paper after one real trace layer.** |
| **5** | **RQ5 — Does diversity-preserving memory improve adaptation after goal change under imperfect verification?** | Once verifier imperfection, latent defects, goal distance/direction, and adversarial contributors are introduced, the archive no longer has robust adaptation advantage. | E024, E026–E039 contain a deep synthetic sequence with counterexamples. | Consolidated preregistered analysis and sharper comparison with current QD literature. | **Strong mechanism/simulation paper.** |
| **6** | **RQ6 — What WorkUnit granularity minimizes total verified completion cost?** | No interior optimum exists; finer or coarser decomposition monotonically dominates. | Protocol and decomposition infrastructure exists. | Controlled real benchmark that varies granularity on the same tasks. | **Promising but under-measured.** |
| **7** | **RQ7 — When is adaptive routing worth its own state/exploration overhead?** | Adaptive routing never beats simpler policies enough to repay route/state burden under matched load. | R2, ACO/stigmergic work, PHY-0/PHY-1; stationary Physarum negative control already useful. | Complete matched stress matrix: topology, churn, failures, stale estimates, nonstationarity. | **Medium readiness.** |
| **8** | **RQ8 — Is review capacity a carrying-capacity limit for agentic repositories?** | More generated activity continues to increase verified throughput even when review service is saturated. | ACE simulation, E043/E044, collaboration observables. | Longitudinal real repository data; avoid causal language without intervention/randomization. | **Mechanism paper possible; causal community paper not ready.** |
| **9** | **RQ9 — Can hierarchical coordination preserve decisions with sublinear global communication?** | Coarse-graining materially degrades scheduling/verification decisions before it saves enough coordination traffic. | Architecture/roadmap hypothesis. | Multi-scale simulator + controlled deployment evidence. | **Future.** |
| **10** | **RQ10 — Which trust/provenance mechanism is sufficient across independent organizations?** | Simpler signed/transparency-log designs satisfy the demonstrated threat model; stronger consensus/ledger machinery adds cost without needed assurance. | Architecture questions and provenance foundations. | Real multi-organization threat model/deployment. | **Future; do not build paper around hypothetical scale.** |

## 5. Recommended paper portfolio

### Paper A — finish/reposition first

**Preferred positioning:**  
**Dependence Shape Matters: Partial Failures, Blind Spots, and Quorum Limits in Executable Verification Panels**

**Core RQs**

- **A1:** Does pairwise error correlation determine the operational value of a verifier panel?
- **A2:** Which dependence model reproduces the *distribution* of verifier failures, not only mean correlation?
- **A3:** Can quorum tuning remove systematic panel blind spots?
- **A4:** When do declared diversity groups fail to correspond to empirical independence?

**Primary hypotheses**

- **H1:** A shared-shock model matched on mean correlation will materially mispredict partial majority failures.
- **H2:** An item-difficulty model with equal parameter count will fit the observed failure-count distribution and panel error better.
- **H3:** Observed unanimous misses create an error floor that quorum changes cannot cross.
- **H4:** Metadata-defined verifier groups will overstate independence relative to observed error vectors.

**Why it is publishable**

The paper has observed executable evidence, falsified modeling assumptions, an explicit negative result, and reproducible tooling. It also connects modern agent verification to the older N-version programming / input-difficulty literature in a technically meaningful way.

**Main risk**

External validity. One constructed 25-oracle panel over 72 items cannot justify universal claims about LLM judges, static analysers, code reviewers, or all verification systems.

**Best strengthening experiment**

Repeat the exact analysis protocol on one second panel with a genuinely different failure mechanism. Prefer a real code-analysis/test-generation/LLM-review setting with execution-decided labels.

**Do not split RQ1 and quorum into separate thin papers.** E017/E018/E020 are strongest as one coherent dependence-shape story.

---

### Paper B — highest-value next empirical paper

**Working title:**  
**When Is Another Agent Worth Adding? Fixed-Budget Scaling, Diversity, and Correlated Failure in AI Software Engineering**

This should combine population scaling and diversity-vs-replication.

#### Primary question

> At fixed candidate-generation and verification budgets, what is the marginal independently verified value of agent (N+1), and is that marginal value explained by worker quality, error independence, or coordination/verification overhead?

#### Experimental arms

For each frozen real coding task:

1. **single strong agent**;
2. **homogeneous replication** of the same agent/configuration;
3. **seed/prompt variation only**;
4. **structural heterogeneity** across models/prompts/tools where available;
5. optionally **coordinated topology** only after the flat arms are understood.

Use population sizes that the budget can support, for example (Nin{1,2,4,8}). Do not increase total allowed tokens/compute simply because (N) increases in the fixed-budget analysis.

#### Pre-register before execution

- frozen task IDs and source revisions;
- hidden evaluator/evaluator-plan digests;
- worker configurations;
- total per-task compute/token/time ceilings;
- population sizes;
- exclusion/failure rules;
- primary endpoint;
- statistical model;
- stopping rule;
- multiplicity plan;
- what counts as a protocol failure versus a task failure.

#### Primary estimands

1. **Verified success probability** per task.
2. **Marginal verified value**
   [
   Delta_N = V(N+1)-V(N)
   ]
   under fixed resource budget.
3. **Cost-normalized gain**
   [
   Delta_N / Delta	ext{scarce-resource}.
   ]
4. **Failure dependence** between attempts/agent families.
5. **Best-of-panel vs panel policy** performance.
6. **Human/verifier attention per accepted artifact**.

#### Statistical discipline

- Treat **tasks**, not attempts, as the principal independent sampling unit.
- Use task-level paired comparisons wherever possible.
- For binary success, prefer a hierarchical/binomial model or task-level paired bootstrap over pretending repeated agent attempts are independent observations.
- Report effect sizes and uncertainty, not only p-values.
- Keep protocol-format failures (such as E029's diff failures) as real outcomes; do not silently remove them.
- Separate exploratory subgroup analysis from confirmatory endpoints.
- Preserve negative and failed runs.

#### Kill criteria

The strong "collective advantage" claim fails if:

- the best single-agent baseline matches the heterogeneous collective within uncertainty at matched budget;
- gains vanish when verifier/human cost is included;
- diversity gains are explained entirely by spending more;
- dependence remains so high that nominal population growth does not add independent candidates.

Any of those outcomes is still publishable.

---

### Paper C — mechanism paper on adaptation

**Working title:**  
**Diversity as Memory Under Goal Drift: Quality-Diversity Search with Correlated Verification and Latent Defects**

Do **not** claim generic novelty for "quality-diversity helps adaptation"; related multi-agent QD work already exists.

The IDKMesh-specific scientific contribution should be the interaction of:

- goal distance;
- goal direction;
- archive memory;
- imperfect/correlated verifier panels;
- latent defects invisible to the objective;
- adversarial optimization against the gate.

The E024–E039 series is unusually valuable because it already contains results that break simple narratives. The paper should center those **boundary conditions**, not only the positive archive result.

**Kill criterion:** if the archive's apparent advantage disappears under a reasonable verifier/latent-defect model or is not robust across goal geometry, publish that boundary rather than rescuing the headline.

---

### Paper D — verification-capacity systems/control paper

**Working title:**  
**Generation Is Cheap, Verification Is Not: Backpressure for Agentic Software Engineering**

**Question**

> When candidate generation can scale faster than verification, which admission/verification policy maximizes verified throughput subject to an escaped-defect and backlog constraint?

**Baselines**

- no backpressure;
- fixed fan-out;
- fixed risk threshold;
- queue-length threshold;
- logistic/risk-adaptive controller;
- AVE-core only if ablations justify the additional complexity.

**Primary outcomes**

- verified useful throughput;
- escaped-defect rate/severity;
- queue area and p95 waiting time;
- verifier utilization;
- human attention;
- dropped/deferred work;
- oscillation/instability under workload changes.

**Required strengthening step**

Replay or shadow these policies on real issue/PR/agent-attempt traces using observed arrival and review/service distributions. Simulation alone should not be sold as empirical repository behavior.

---

### Paper E — adaptive routing under churn

**Working title:**  
**When Adaptive Routing Is Worth Its Complexity: Falsification-First Scheduling for Heterogeneous Agent and Compute Pools**

The scientific question is:

> Which non-stationarity regimes create enough benefit for adaptive routing to repay its additional state, exploration, and route burden?

The stationary Physarum result is exactly the right negative control: if a simple policy is already adequate, sophistication should lose.

The paper needs a factorial stress matrix covering at least:

- no shift;
- abrupt reliability shift;
- gradual drift;
- node churn/outage;
- correlated failures;
- stale routing observations;
- topology variation;
- capability scarcity.

Report the **region of superiority**, not a universal winner.

## 6. Publication-readiness scorecard

Scores are 1 (weak) to 5 (strong). "Extra work" is reversed: 5 means little additional evidence is required.

| Paper | Novelty after 2026 literature | Current evidence | Reproducibility | External validity | Extra work | Recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **A — dependence shape / blind spots** | 4 | 5 | 5 | 2 | 4 | **Finish first; sharpen novelty.** |
| **B — fixed-budget agent scaling** | 5 | 2 | 4 | 1 | 1 | **Highest-impact next experiment.** |
| **C — QD under goal drift + imperfect verification** | 4 | 4 | 5 | 2 | 3 | **Strong simulation/mechanism paper.** |
| **D — verification backpressure** | 4 | 4 | 5 | 2 | 3 | **Add real trace replay, then write.** |
| **E — adaptive routing** | 3 | 3 | 4 | 2 | 2 | **Complete stress matrix first.** |

## 7. Venue families by scientific contribution

This is a fit map, not a deadline recommendation.

| Contribution shape | Natural venue families |
| --- | --- |
| empirical AI software-engineering / agent evaluation | ICSE, FSE, ASE, MSR, TOSEM, TSE, EMSE |
| multi-agent coordination / collective intelligence | AAMAS; relevant NeurIPS/ICML/ICLR tracks or workshops depending maturity |
| verification/reliability/control of agentic software | ICSE/FSE/ASE, TSE/TOSEM, reliability/autonomic-computing venues |
| quality-diversity / adaptive multi-agent mechanisms | AAMAS, GECCO, ECAI, ALIFE; ML venues if the empirical contribution is strong enough |
| distributed scheduling / federated coordination | ICDCS, Middleware, CCGrid/HPDC-type venues when real systems evidence exists |

Choose the venue **after** fixing the scientific contribution and evidence class, not the reverse.

## 8. Claims IDKMesh should explicitly avoid today

Do not publish these as established conclusions:

- "many AI agents outperform one strong agent";
- "heterogeneous agents are better than homogeneous agents" without fixed-budget real evidence;
- "more reviewers improve safety";
- "declared model/provider diversity implies independent evidence";
- "IDKMesh demonstrates collective intelligence";
- "quality-diversity improves real software engineering";
- "adaptive verification ecology is universally superior";
- "IDKMesh scales to thousands or millions of real participants";
- "hierarchical federation preserves near-optimal decisions at Internet scale";
- "community automation causes contributor growth";
- "A2A/MCP interoperability proves trustworthy execution."

These are hypotheses, synthetic mechanisms, implemented contracts, or future evidence gates.

## 9. Best next experiment: decision

If IDKMesh can fund/obtain only **one major new scientific dataset**, it should be the real fixed-budget collective-coding experiment for Paper B.

Why this one:

1. it tests the project's central thesis directly;
2. it closes the largest gap in issue #13 / #30 / #70;
3. existing synthetic work already identifies the confounders that must be controlled;
4. both a positive and a negative result are interesting;
5. it creates a reusable real corpus for later verification, decomposition, routing, and coordination papers.

### Minimum viable publishable cohort

Do not optimize for a huge task count before methodology is sound. A credible pilot should first demonstrate:

- enough tasks to estimate task-to-task heterogeneity;
- at least two materially different task classes/difficulties;
- frozen repository revisions and hidden evaluation;
- repeated but bounded attempts;
- at least one strong modern single-agent baseline;
- homogeneous and heterogeneous matched-budget arms;
- independently retained failures;
- exact provenance;
- no data leakage from evaluator to candidate agent.

Use the pilot to estimate variance and then perform a real power/sample-size calculation for the confirmatory cohort. Do not invent a sample size from convention.

## 10. Paper-level reproducibility contract

Every IDKMesh manuscript should ship with a table mapping each quantitative claim to:

- exact repository revision/tag;
- experiment ID;
- raw artifact;
- generation command/workflow;
- task/corpus identity;
- worker/model version;
- evaluator version/digest;
- random seeds where relevant;
- evidence class;
- exclusions/failures;
- uncertainty method;
- known limitation.

The existing `paper/CLAIM_EVIDENCE_MAP.md` is the right pattern. New papers should use the same discipline.

## 11. Relation to existing repository research

This document is a publication-oriented projection, not a replacement for:

- `RESEARCH_QUESTIONS.md` — broad long-term question inventory;
- `docs/research/TOP_20_QUESTIONS.md` — prioritized project questions;
- `docs/research/FIRST_RESEARCH_PROGRAM.md` — initial joint program;
- `experiments/README.md` — experiment/evidence index;
- `docs/research/README.md` — research navigation;
- `paper/README.md` and `paper/CLAIM_EVIDENCE_MAP.md` — manuscript stewardship.

## 12. Conversation provenance

This document preserves and improves the outcome of the 2026-10-07 maintainer request to identify the scientific questions IDKMesh can answer and turn into papers.

The improvement pass checked current repository evidence and a targeted sample of current external literature before revising the ranking. It specifically corrected the risk of presenting "reviewer count is not evidence count" as if no closely related 2026 LLM-panel result existed.

This is owner-directed AI-assisted research planning, not independent scientific peer review and not a systematic literature review.

## Community impact

A publication roadmap should make it easier for contributors to answer three questions:

1. Which experiment closes a real scientific evidence gap?
2. Which repository result is synthetic versus observed?
3. What negative result would change the project's mind?

That makes reproducibility, replication, falsification, and negative evidence first-class contribution paths rather than secondary work.
