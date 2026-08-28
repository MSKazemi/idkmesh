# IDKIP-0002: IDK-MOSAIC — A Living Collective-Intelligence Control Loop

- **Status:** Draft
- **Authors:** TBD (initiated from IDKMesh project discussion)
- **Created:** 2026-08-28
- **Discussion:** TBD
- **Implementation:** TBD
- **Supersedes:**
- **Superseded by:**

## Summary

This proposal introduces **IDK-MOSAIC**: a speculative, testable meta-algorithm for coordinating humans, AI agents, tools, and distributed compute when the goal is incomplete, changing, disputed, or initially unknown.

**MOSAIC** stands for **Multi-Objective Self-Organizing Adaptive Intelligence Collective**.

The central idea is that IDKMesh should not optimize only for the best immediate answer. It should also optimize the **ecology that produces answers**. Candidate solutions, coordination policies, verification methods, contributor roles, and even task decompositions can compete and evolve. However, they do so inside explicit safety, provenance, reversibility, and governance constraints.

MOSAIC combines ideas inspired by:

- **biology:** evolution, mutation, recombination, ecological niches, immune systems, homeostasis, quorum sensing, apoptosis, and symbiosis;
- **physics:** statistical mechanics, entropy, temperature, annealing, branching processes, phase transitions, criticality, and energy/resource budgets;
- **mathematics/computer science:** Bayesian evidence, information theory, multi-objective optimization, graph theory, bandits, multiplicative weights/replicator dynamics, robust statistics, and constrained optimization;
- **psychology/cognitive science:** independent judgment, calibration, cognitive diversity, anti-conformity mechanisms, curiosity/information gain, and protection against groupthink;
- **society/politics:** polycentric governance, checks and balances, juries/sortition, local autonomy, public dissent, constitutional constraints, and reversible experimentation;
- **economics/game theory:** incentives, repeated games, reputation, mechanism design, exploration/exploitation, and delayed rewards for durable value.

The proposal is **not** a claim that these disciplines reduce to one formula. It is a design hypothesis: carefully chosen mechanisms from each field may form a more adaptive coordination loop than any single optimizer, voting rule, scheduler, or swarm algorithm.

---

## Problem

IDKMesh is intentionally trying to coordinate work under uncertainty. A conventional project assumes that the target is known and decomposes it into tasks. IDKMesh may instead face situations where:

- the final target is only partially understood;
- contributors disagree about what the target means;
- no central participant knows the whole system;
- there are many possible decompositions;
- agents have different capabilities and biases;
- the correct verification method is itself uncertain;
- useful work can generate new questions rather than only answers;
- local improvements can damage global system quality;
- a majority can be confidently wrong because members share the same information source or model family;
- early architectural choices can prematurely collapse exploration.

A single objective function is therefore dangerous. If IDKMesh optimizes one visible number, the system may Goodhart that number and become worse in dimensions that were not measured.

The coordination problem is closer to maintaining a **healthy evolving ecosystem** than to executing a static task queue.

---

## Motivation

The existing IDKMesh architecture already proposes interacting goal/evidence, work, and participant/capability graphs, plus a verification-first loop. MOSAIC proposes a mathematical control policy for making those graphs adapt over time.

The proposal attempts to answer a deeper question:

> Can a distributed community reach coherent, high-quality complex systems without beginning with a perfectly coherent shared goal, if the system has good local rules for exploration, verification, selection, memory, diversity, and governance?

Nature suggests that complex structure can emerge from local interaction, variation, selection, feedback, and environmental memory. Human institutions suggest that robust collective action often depends on multiple centers of authority, monitoring, conflict-resolution, and the ability to adapt rules. Collective-intelligence research suggests that heterogeneity and structured independence matter, while simple majority aggregation can lose specialized information. Active-inference work provides a formal way to combine pragmatic value and information-seeking value.

MOSAIC turns those inspirations into an experimentally falsifiable control loop.

---

## Scope

This IDKIP covers:

- how alternative coordination policies are represented and selected;
- how uncertainty controls exploration versus convergence;
- how task decomposition can self-regulate rather than explode;
- how contributors/agents are matched to tasks while preserving novelty;
- how evidence is aggregated while discounting correlation;
- how verification can behave like an adaptive immune system;
- how reputation evolves from delayed verified outcomes;
- how autonomous subcommunities/cells can form and dissolve;
- how governance can remain polycentric without losing common constraints;
- how the whole mechanism can be evaluated in simulation before wide deployment.

---

## Non-goals

This proposal does **not**:

- claim that biological or political metaphors are proofs;
- claim that self-organized criticality automatically appears in software communities;
- require cryptocurrency, tokens, or monetary incentives;
- require global consensus for every decision;
- let an evolving algorithm modify security/safety invariants without explicit high-impact governance;
- remove human responsibility for irreversible decisions;
- assume one universal fitness function is discoverable;
- require millions of machines for initial validation;
- require a new agent communication protocol.

The initial test should be a single-machine or small-cluster simulation.

---

# Proposal

## 1. Treat IDKMesh as four co-evolving populations

MOSAIC maintains populations rather than one fixed strategy:

1. **Problem hypotheses** — interpretations of what should be achieved.
2. **Solution strategies** — candidate decompositions, implementations, research paths, and designs.
3. **Verification strategies** — tests, critics, benchmarks, formal checks, red teams, and human review processes.
4. **Coordination policies** — schedulers, aggregation rules, topology, role assignment, incentive/reputation rules, and exploration parameters.

A policy is therefore not just an algorithm for solving tasks. It can describe *how the collective thinks*.

Each policy has:

- parameters;
- provenance;
- observed outcomes;
- uncertainty;
- resource cost;
- failure history;
- contexts in which it works;
- related/ancestor policies;
- independent evidence supporting or contradicting it.

This is analogous to a genotype/phenotype distinction only as an engineering metaphor: a policy description is the inheritable representation; its observed behavior in a workload is the phenotype.

---

## 2. Use a multi-objective evidence fitness instead of one score

For candidate `i`, define a contextual fitness vector:

\[
\mathbf{f}_i =
(V_i, G_i, I_i, D_i, R_i, S_i, -C_i, -X_i)
\]

where:

- `V_i` = independently verified correctness/value;
- `G_i` = alignment with the current goal/hypothesis;
- `I_i` = information gain / uncertainty reduction;
- `D_i` = diversity or novelty contribution;
- `R_i` = reproducibility/robustness;
- `S_i` = social/community value, such as enabling other contributors;
- `C_i` = resource cost (compute, latency, reviewer attention, money, energy);
- `X_i` = security, abuse, irreversibility, and externality risk.

Do **not** permanently collapse this vector into one scalar.

For a bounded experiment, a temporary contextual score may be used:

\[
F_i(t) =
\alpha_t V_i + \beta_t G_i + \gamma_t I_i + \delta_t D_i +
\epsilon_t R_i + \zeta_t S_i - \lambda_t C_i - \mu_t X_i
\]

The weights are themselves policy parameters and can vary by task class. High-risk work should increase `mu`; exploratory research should increase `gamma` and `delta`; production integration should increase `alpha` and `epsilon`.

Whenever possible, use Pareto dominance and retain multiple non-dominated candidates instead of prematurely choosing one winner.

### Why this matters

This is the first anti-Goodhart mechanism. A candidate that is fast but fragile, popular but correlated, correct but impossible to maintain, or novel but unverified should not dominate merely because one metric is large.

---

## 3. Active-inference-inspired task value: reward useful uncertainty reduction

When the goal is unclear, the best next task may be the task that teaches the system what to do next.

For a possible task/action `a`, estimate:

\[
Q(a) =
\mathbb{E}[U(a)]
+ \kappa \, \mathbb{E}[IG(a)]
- \lambda C(a)
- \mu X(a)
\]

where:

- `U(a)` = expected pragmatic utility;
- `IG(a)` = expected information gain;
- `C(a)` = cost;
- `X(a)` = risk.

One information-gain form is:

\[
IG(a) =
\mathbb{E}_{o \sim p(o|a)}
\left[
D_{KL}\big(p(z|o,a)\;||\;p(z)\big)
\right]
\]

where `z` is an uncertain latent hypothesis and `o` is a possible observation/result.

This means a failed prototype can be highly valuable if it eliminates an important hypothesis cheaply and reproducibly.

**Design implication:** IDKMesh should be able to create explicit "question tasks" and "disambiguation tasks", not only implementation tasks.

---

## 4. Biology-inspired variation: mutation, recombination, niches, and speciation

For each problem, MOSAIC should maintain a small population of genuinely different candidate approaches.

Variation operators may include:

- **mutation:** change one assumption, tool, model family, architecture, test method, or parameter;
- **recombination:** combine independently successful components from different candidates;
- **duplication/divergence:** copy a useful module and let the copy specialize;
- **niche formation:** reserve budget for approaches serving underexplored constraints or communities;
- **speciation:** prevent a dominant strategy from immediately eliminating a structurally different but plausible strategy.

Define a behavioral distance `d(i,j)` between candidates based on features such as architecture, dependency set, model family, reasoning strategy, outputs, tests, and failure modes.

A novelty score can be:

\[
D_i = \frac{1}{k}\sum_{j \in kNN(i)} d(i,j)
\]

A minimum novelty budget should survive even when one approach is temporarily winning.

### Psychological reason

If all agents see each other's answer before producing their own, social convergence can destroy the independence needed for useful aggregation. MOSAIC therefore separates:

1. **independent generation**;
2. **commitment of initial claims/predictions**;
3. **deliberation and critique**;
4. **revision**;
5. **aggregation**.

This is the computational equivalent of protecting independent judgment before discussion.

---

## 5. Stigmergic coordination: let artifacts coordinate agents indirectly

Social insects coordinate partly by modifying a shared environment. IDKMesh already has the natural equivalent: the Git repository and Goal/Evidence Graph.

Workers should therefore coordinate primarily through durable artifacts:

- claim nodes;
- evidence nodes;
- failed experiments;
- benchmark results;
- patches;
- tests;
- unresolved questions;
- risk flags;
- capability advertisements;
- provenance records.

A worker should not need global knowledge of the collective. It observes a local neighborhood of the graph and reacts to high-value opportunities.

Each artifact can carry fields such as:

```yaml
state: open | disputed | verified | rejected | superseded
uncertainty: 0..1
expected_information_gain: 0..1
risk: 0..1
needed_capabilities: [...]
replication_count: n
independent_evidence_count: n
expires_or_recheck_after: timestamp
```

This turns the repository into part of the coordination algorithm rather than only a storage location.

---

## 6. Ecology-inspired task markets and bandit allocation

IDKMesh should not assign every task to the historically best agent. That would create monoculture and starve new contributors of evidence-building opportunities.

For agent/strategy `a` on task class `x`, use an exploration-aware allocation score such as:

\[
A(a,x) =
\hat\mu_{a,x}
+ c\sqrt{\frac{\ln N_x}{n_{a,x}+1}}
+ \rho D_{a,x}
+ \kappa IG_{a,x}
- \lambda C_{a,x}
- \mu X_{a,x}
\]

where the second term is a UCB-style exploration bonus.

Interpretation:

- proven agents receive work because expected quality is high;
- under-tested agents receive some work because uncertainty about them is high;
- diverse agents receive some work because correlated failure is dangerous;
- expensive/risky agents receive less work unless the task justifies it.

This creates an **ecology of capability niches** rather than a single global leaderboard.

---

## 7. Evolutionary-game update: strategies reproduce by verified fitness

Let `w_i(t)` be the resource share allocated to coordination strategy `i`.

A discrete replicator/multiplicative-weights update can be:

\[
w_i(t+1)
= \frac{w_i(t)\exp\{\eta(F_i(t)-\bar F(t))\}}
{\sum_j w_j(t)\exp\{\eta(F_j(t)-\bar F(t))\}}
\]

with:

\[
\bar F(t)=\sum_j w_j(t)F_j(t)
\]

This does **not** mean low-performing strategies are deleted immediately. A minimum exploration floor `w_min` preserves alternatives while uncertainty is high.

Strategies should be evaluated per context rather than globally. A strategy may be excellent for documentation, poor for security-critical code, and unknown for research.

---

## 8. Physics-inspired adaptive temperature: exploration should be a state variable

MOSAIC uses an exploration temperature `T`.

Candidate selection can use:

\[
P(i) = \frac{\exp(F_i/T)}{\sum_j \exp(F_j/T)}
\]

- high `T` -> broad exploration;
- low `T` -> concentrated exploitation.

Unlike ordinary simulated annealing, the temperature should **not only decrease with time**. The environment and goal can change, so the system may need to "reheat".

Let `H_t` be the entropy of the active strategy distribution and `U_t` be unresolved uncertainty. A simple homeostatic update is:

\[
T_{t+1}=
\mathrm{clip}\left(
T_t \exp\left[
 k_H(H^*-H_t)
+ k_U(U_t-U^*)
+ k_S S_t
\right],
T_{min},T_{max}
\right)
\]

where:

- `H*` is target diversity;
- `U*` is tolerated uncertainty;
- `S_t` is stagnation or evidence of environmental change.

Therefore:

- diversity collapse -> temperature rises;
- new uncertainty -> temperature rises;
- stagnation -> temperature rises;
- stable verified convergence -> temperature falls.

This is **homeostatic annealing**, not a one-way cooling schedule.

---

## 9. Criticality-inspired control: regulate the branching ratio of work

A common failure of agentic systems is task explosion: every task creates many subtasks, reviews, questions, and follow-ups. Another failure is premature convergence: no new useful work is generated.

Define the **useful branching ratio**:

\[
b_t = \frac{\text{verified useful child work items created in window }t}
{\text{parent work items completed in window }t}
\]

Target approximately:

\[
b^* \approx 1
\]

Interpretation:

- `b << 1`: the system is subcritical; exploration is dying;
- `b >> 1`: the system is supercritical; coordination debt and task explosion grow;
- `b ≈ 1`: work can propagate without immediate extinction or uncontrolled explosion.

This is an engineering analogy to branching/critical systems, not a claim of physical universality.

Let `q_t` be the threshold required before a proposed child task is admitted. Update:

\[
q_{t+1}=\mathrm{clip}\big(q_t + k_b(b_t-b^*),q_{min},q_{max}\big)
\]

If task branching explodes, the evidence/value threshold rises automatically. If the system becomes inert, the threshold falls.

This single control variable may be extremely useful for scaling IDKMesh from tens to millions of logical work items.

---

## 10. Immune-system-inspired verification

The generation population and verification population should be distinct.

MOSAIC treats unverified artifacts as antigens: they are allowed to circulate in quarantined form, but not to become trusted state until checked.

Verification roles include:

- **innate defenses:** deterministic tests, static analysis, schema validation, permission boundaries, content hashes;
- **adaptive defenses:** targeted adversarial tests generated from the specific candidate;
- **negative selection:** construct detectors for classes of behavior that valid solutions should never exhibit;
- **clonal expansion:** when a suspicious pattern appears, allocate more independent verifiers to that region;
- **immune memory:** record failure signatures and automatically test future related contributions;
- **apoptosis:** automatically retire stale, superseded, irreproducible, or repeatedly harmful artifacts/policies from active use while preserving history.

High-risk work should require multiple **orthogonal** forms of evidence, not merely multiple votes from similar agents.

---

## 11. Correlation-aware evidence instead of naive majority voting

Ten agents using the same base model, prompt, retrieval source, and test harness are not ten independent witnesses.

For hypothesis `H`, start with prior log odds `L_0` and aggregate evidence using correlation discounts:

\[
L(H|E) = L_0 + \sum_j d_j \log BF_j
\]

where:

- `BF_j` is the Bayes factor or calibrated evidence contribution from verifier `j`;
- `d_j \in [0,1]` discounts correlated or low-independence evidence.

An implementable first approximation is:

\[
d_j = \frac{q_j r_j}{1 + \sum_{k<j}\rho_{jk}}
\]

where:

- `q_j` = evidence quality;
- `r_j` = verifier reliability/calibration;
- `rho_jk` = estimated correlation with previous evidence sources.

Correlation features can include:

- same model family;
- same prompt template;
- same human team;
- same source documents;
- same test generator;
- same organization;
- shared dependency chain;
- copied reasoning/artifacts.

The point is not perfect Bayesian inference. The point is to make **independence a first-class resource**.

---

## 12. Psychology-inspired calibration and anti-groupthink rules

Every worker that makes uncertain claims should be encouraged to state confidence before seeing peer results.

Track calibration with a proper scoring rule such as the Brier score for binary claims:

\[
BS = \frac{1}{N}\sum_{n=1}^{N}(p_n-y_n)^2
\]

Reputation should reward calibrated uncertainty, not only confident success.

Additional rules:

- generate first, deliberate second;
- preserve minority hypotheses until evidence crosses a rejection threshold;
- reward useful falsification;
- ask agents to predict what result would change their mind;
- separate "proposal" and "critic" roles for important work;
- randomly rotate reviewers to reduce stable echo chambers;
- expose provenance so copied consensus can be detected;
- allow an explicit "I don't know" outcome without reputation damage when uncertainty is genuine.

The desired psychology is **epistemic humility with active curiosity**, not indecision.

---

## 13. Politics-inspired polycentric cells

MOSAIC should not have one global scheduler making every decision.

The system can form temporary or durable **cells** around graph communities, components, disciplines, or goals.

A cell may control:

- its local task ordering;
- local worker matching;
- local experiments;
- local review queues;
- local reputation signals;
- local documentation conventions.

All cells share project-wide constitutional invariants such as:

- provenance requirements;
- security boundaries;
- public decision records;
- Code of Conduct;
- no autonomous irreversible merge where policy forbids it;
- auditability;
- appeal/escalation routes.

This creates **polycentric governance**: many centers of action, with common interfaces and shared constraints.

### Checks and balances

For high-impact decisions, separate powers:

- **proposers** create options;
- **implementers** build prototypes;
- **verifiers** test them;
- **randomly sampled review juries** examine evidence;
- **maintainers/stewards** execute authorized integration;
- **auditors** inspect process/provenance after the fact.

No single role should both create, validate, and irreversibly integrate its own high-impact proposal.

---

## 14. Sortition-inspired review for important decisions

Popularity and permanent committees both create failure modes. For significant but reviewable decisions, MOSAIC can experiment with **sortition**: randomly select a small, capability-constrained panel from a sufficiently large eligible pool.

Sampling probability can be adjusted to ensure:

- capability coverage;
- conflict-of-interest avoidance;
- organizational diversity;
- model/tool diversity;
- newcomer inclusion;
- rotation over time.

Randomness makes capture and stable collusion harder and spreads governance experience.

Random selection is not sufficient for security-critical approval; it complements expert review and explicit evidence thresholds.

---

## 15. Society-inspired deliberative aggregation: small diverse groups, then aggregate

For ambiguous questions, do not place hundreds of agents into one conversation.

Instead:

1. sample several small heterogeneous groups;
2. collect independent initial positions;
3. allow structured deliberation within each group;
4. produce each group's consensus **plus dissent**;
5. aggregate across groups while accounting for independence and expertise.

This preserves local discussion while preventing immediate global conformity.

The resulting graph stores both consensus and unresolved minority claims.

---

## 16. Homeostatic resource budgets

Every living system has resource constraints. MOSAIC should treat compute, human attention, network traffic, money, and energy as limited budgets.

For each cell `c`:

\[
B_c(t+1) = B_c(t)
+ R_c^{verified}
+ R_c^{information}
- C_c
- P_c^{risk/failure}
\]

where rewards can be virtual scheduling credits rather than money.

A cell that repeatedly creates expensive unverified work loses expansion budget. A cell that generates reusable evidence or enables other work can gain budget even if it did not directly ship code.

This discourages uncontrolled replication.

---

## 17. Reputation as decaying, contextual, delayed evidence

A single global reputation number would be easy to game and unfair across domains.

Use contextual reputation `r_{a,d}` for actor `a` in domain `d`:

\[
r_{a,d}(t+1)=
(1-\delta)r_{a,d}(t)
+ \eta V_{a,d}^{delayed}
+ \kappa I_{a,d}
+ \rho C_{a,d}^{community}
- \mu P_{a,d}
\]

where:

- old reputation decays slowly;
- `V_delayed` rewards results that remain valid after later verification;
- information-producing negative results can earn value;
- documentation/review/community enablement can earn value;
- penalties are tied to verified harmful behavior, not mere disagreement.

Reputation should influence assignment and review weight, but never become unquestionable authority.

---

## 18. Constitutional constraints: not everything is allowed to evolve

Open-ended evolution without boundaries is unsafe.

Define hard constraints:

\[
h_k(x) \le 0, \quad k=1,\ldots,m
\]

A candidate that violates a hard constraint is ineligible regardless of fitness.

Examples:

- unauthorized privilege escalation;
- destructive access beyond the Work Contract;
- missing provenance for high-risk artifacts;
- bypassing mandatory human approval;
- violating repository safety/legal policy;
- silently weakening verification to improve benchmark scores.

Changing a constitutional constraint requires the repository's high-impact governance process and should never happen through ordinary automated mutation.

This is the political equivalent of a constitution and the engineering equivalent of a safety invariant.

---

# The MOSAIC control loop

A single iteration is:

```text
1. Observe graph state, goals, uncertainty, failures, budgets, and open questions.
2. Estimate uncertainty and detect stagnation/diversity collapse.
3. Form or resize local cells around active graph regions.
4. Generate several independent candidate actions/policies.
5. Preserve initial predictions/confidence before cross-talk.
6. Score candidates for utility, information gain, diversity, cost, and risk.
7. Allocate workers with exploration-aware matching.
8. Execute in isolation; write durable artifacts/evidence to the graph.
9. Trigger innate verification.
10. Trigger adaptive/immune verification proportional to novelty and risk.
11. Aggregate evidence with correlation discounts.
12. Integrate, quarantine, reject, or retain as competing hypotheses.
13. Update contextual reputation and strategy resource shares.
14. Mutate/recombine a bounded fraction of policies.
15. Adjust exploration temperature to restore healthy diversity/uncertainty balance.
16. Adjust child-task admission threshold to keep useful branching near target.
17. Spawn, merge, split, or dissolve cells based on graph structure and load.
18. Record dissent, provenance, decisions, and rollback points.
19. Repeat.
```

The key property is that **the control loop itself learns**.

---

# A compact mathematical state model

At time `t`, represent IDKMesh as:

\[
\mathcal{M}_t =
(G_t, P_t, A_t, E_t, R_t, B_t, \Theta_t)
\]

where:

- `G_t` = Goal/Evidence/Work graph;
- `P_t` = population of problem/solution/verification/coordination policies;
- `A_t` = actors and capabilities;
- `E_t` = evidence/provenance state;
- `R_t` = contextual reputations;
- `B_t` = resource budgets;
- `Theta_t` = meta-control parameters such as temperature, branching threshold, diversity targets, and risk thresholds.

The transition is:

\[
\mathcal{M}_{t+1}
= \Phi(\mathcal{M}_t, O_t, \xi_t)
\]

where `O_t` is new observation/evidence and `xi_t` is **controlled randomness**.

The purpose of randomness is not chaos. It is used for:

- exploration;
- randomized reviewer selection;
- mutation;
- tie breaking;
- adversarial test generation;
- audit sampling;
- preventing permanent capture by deterministic local optima.

The randomness rate is itself controlled by uncertainty, risk, and diversity.

---

# Why this synthesis may be useful

## Biology contributes survival without central planning

Evolution contributes variation and selection; ecology contributes niches and coexistence; immune systems contribute layered defense and memory; homeostasis contributes adaptive feedback; apoptosis contributes controlled retirement.

## Physics contributes regime control

Entropy measures diversity; temperature controls exploration; annealing provides probabilistic search; branching processes provide a simple task-explosion control signal; criticality suggests a useful engineering target between frozen order and runaway disorder; energy budgets make resource constraints explicit.

## Psychology contributes protection against correlated minds

Independent first judgments, calibrated confidence, dissent preservation, and anti-conformity mechanisms prevent a crowd of similar agents from becoming one repeated error.

## Politics contributes scalable legitimacy and conflict handling

Polycentric governance allows local autonomy; constitutions protect invariants; checks and balances separate proposal from verification and integration; sortition distributes oversight and makes fixed capture harder; public dissent preserves reopening conditions.

## Mathematics contributes falsifiability

Every metaphor should eventually become a measurable variable, update rule, graph transformation, probability, constraint, or experiment. If it cannot be measured or falsified, it should remain inspiration rather than architecture.

---

## Alternatives considered

### A. One central planner/scheduler

Simpler and easier to debug, but creates a bottleneck, single policy bias, and poor adaptation to heterogeneous goals.

### B. Pure majority voting

Easy to understand, but unsafe when participants are correlated, specialized knowledge is rare, or incentives favor conformity.

### C. Pure market/auction

Good for resource allocation when value is priced well, but weak when goals, externalities, public goods, and verification quality are uncertain.

### D. Pure genetic algorithm

Useful search mechanism but too narrow: it does not by itself solve governance, provenance, correlated verification, security boundaries, or community legitimacy.

### E. Pure reinforcement learning

Can optimize a reward, but IDKMesh's reward is ambiguous and changes over time; reward misspecification and Goodhart effects are central concerns.

### F. Pure active inference

Provides an attractive exploration/utility formulation but does not by itself specify distributed governance, immune verification, graph topology, or open-source community mechanisms.

### G. Pure blockchain consensus

Potentially useful for narrow trust/settlement problems, but unnecessarily expensive and rigid as a default coordination substrate. Consensus on a ledger is not equivalent to correctness of work.

### H. Do nothing; keep fixed policies

Best baseline for experiments. MOSAIC must beat simpler fixed schedulers before adoption.

---

## Interoperability / compatibility

MOSAIC is a coordination layer above existing IDKMesh abstractions.

It should consume and update:

- Goal/Evidence Graph nodes;
- Work Contracts;
- worker capability records;
- verification evidence;
- provenance;
- experiment metrics.

It should not replace A2A, MCP, Git, GitHub, OCI, or existing worker adapters.

A worker does not need to understand MOSAIC globally. It only needs a Work Contract plus the relevant local graph/evidence context.

---

## Security / abuse considerations

### Evolution can optimize attacks

Any optimizer can discover harmful strategies if the fitness function rewards them. Therefore execution must remain sandboxed and hard constraints must dominate fitness.

### Reputation gaming

Mitigations:

- delayed rewards;
- contextual reputation;
- independent verification;
- random audits;
- provenance;
- anti-Sybil mechanisms where necessary;
- no automatic privilege from a scalar score.

### Collusion and correlated agents

Mitigations:

- independence metadata;
- randomized reviewers;
- model/tool/source diversity requirements;
- correlation discounts;
- hidden tests;
- adversarial verification.

### Task explosion / denial of service

Mitigations:

- useful branching-ratio controller;
- per-cell budgets;
- admission thresholds;
- quotas;
- task expiry;
- backpressure.

### Governance capture

Mitigations:

- public records;
- rotating reviewers;
- scoped authority;
- appeals;
- reversible experiments;
- preserved dissent;
- no permanent automatic authority from reputation alone.

### Goodhart pressure

Mitigations:

- multi-objective fitness;
- rotating/hidden metrics;
- delayed real-world validation;
- metric diversity;
- explicit externality/risk term;
- human/community evaluation.

### Unsafe self-modification

Meta-policy mutation cannot modify constitutional constraints or privilege boundaries through the normal loop.

---

## Community Impact

Potential benefits:

- newcomers can enter through small niches instead of competing globally;
- non-code contributions can earn explicit evidence value;
- alternative ideas can survive long enough to be tested;
- local cells can reduce central maintainer bottlenecks;
- failure reports and reproductions become valuable contributions;
- community governance can decentralize gradually with evidence.

Potential costs:

- the conceptual model is complex;
- too many scores can confuse contributors;
- automated reputation can feel coercive or unfair;
- over-formalized governance can create bureaucracy;
- experimental randomness can make behavior harder to predict.

Therefore the user-facing interface should stay simple. Contributors should not need to understand every equation. The mathematics should primarily govern internal policy experiments and observability.

---

## Measurable success criteria

MOSAIC should not be accepted because it sounds biologically or mathematically elegant.

A prototype should show statistically credible improvement over simpler baselines in several of these dimensions:

1. higher verified task success rate at equal compute budget;
2. lower correlated-failure rate;
3. better discovery of initially hidden task requirements;
4. fewer unnecessary tasks per useful artifact;
5. less reviewer concentration/bottlenecking;
6. faster recovery after changing the goal or workload distribution;
7. maintained strategy diversity without large quality loss;
8. improved newcomer opportunity without reducing verification quality;
9. lower catastrophic integration rate under adversarial workloads;
10. useful negative-result production and reuse;
11. stable operation across a wide range of agent counts;
12. graceful degradation when some agents are malicious, unavailable, or poor quality.

A MOSAIC controller that cannot outperform a simple fixed scheduler on meaningful workloads should remain research only.

---

## Experiment / evidence plan

### Phase 0 — simulator

Implement a single-process simulator with logical agents.

Variables:

- agent skill distributions;
- correlation clusters;
- malicious-agent fraction;
- task difficulty;
- hidden requirements;
- cost distributions;
- verification accuracy;
- goal drift;
- network/communication constraints.

Compare:

1. central greedy scheduler;
2. random scheduler;
3. UCB scheduler;
4. majority-vote verification;
5. fixed diverse panel;
6. MOSAIC without homeostatic controls;
7. MOSAIC full experimental controller.

### Phase 1 — repository benchmark

Run the algorithms on bounded GitHub tasks through existing worker adapters.

Measure:

- pass rate on hidden tests;
- cost;
- wall time;
- diversity;
- evidence independence;
- number of generated subtasks;
- number of false integrations;
- reviewer load;
- reproducibility.

### Phase 2 — goal ambiguity benchmark

Give the system intentionally incomplete problem statements with hidden evaluation criteria. Measure whether information-seeking tasks discover missing requirements before expensive implementation.

### Phase 3 — environmental change

Change the workload midway. Test whether adaptive temperature and policy populations recover faster than fixed optimization policies.

### Phase 4 — adversarial ecology

Introduce colluding/correlated agents, metric gaming, flaky tests, and malicious proposals. Test immune verification, correlation discounting, random audits, and governance separation.

### Stopping rule

Do not expand to volunteer distributed compute until the control loop demonstrates clear benefit and bounded failure modes in simulation and small trusted environments.

---

## Key research hypotheses

### H1 — Homeostatic exploration

Adaptive reheating based on uncertainty, stagnation, and diversity collapse will recover from goal changes better than monotonic annealing or fixed exploration.

### H2 — Useful branching control

Maintaining a bounded useful branching ratio will reduce task explosion while preserving discovery of necessary subtasks.

### H3 — Correlation-aware verification

A smaller diverse verifier set with independence weighting will outperform a larger homogeneous majority at equal cost.

### H4 — Immune memory

Persisting failure signatures will reduce recurrence of known failure classes with low marginal verification cost.

### H5 — Polycentric cells

Local autonomous cells with common constitutional constraints will scale reviewer throughput better than a global queue without materially increasing integration inconsistency.

### H6 — Information-value tasks

Explicit information-gain scoring will solve ambiguous tasks more efficiently than directly attempting implementation first.

### H7 — Protected minority hypotheses

A bounded diversity/speciation budget will improve adaptation after environment/goal shifts versus winner-take-all selection.

---

## Dissent / unresolved questions

1. Is `b ≈ 1` actually a useful target for software-task branching, or should it vary by phase and graph depth?
2. How should correlation between agents/evidence sources be estimated without invasive telemetry?
3. Can reputation remain useful without creating social status pathologies?
4. Which metrics should be public versus hidden to reduce gaming while preserving transparency?
5. How much randomness is acceptable in high-stakes work allocation and governance?
6. What is the smallest set of MOSAIC mechanisms that beats a simpler scheduler?
7. How should diversity be measured: implementation distance, provenance distance, model-family distance, behavioral disagreement, or all of them?
8. Can local polycentric cells avoid fragmentation and incompatible norms?
9. How should human values and community impact enter the fitness vector without pretending they are precisely measurable?
10. Which constitutional invariants should be hard-coded versus governed through IDKIPs?
11. How should stale or harmful policies be archived without losing useful historical evidence?
12. Could the system oscillate between exploration and convergence rather than stabilize? If so, are those oscillations useful or pathological?

These are part of the research program, not edge cases to hide.

---

## Migration / rollback

MOSAIC should be introduced only as an experimental policy plugin.

Existing fixed schedulers and verification rules remain available as baselines and rollback targets.

Every adaptive parameter update must be logged. Experiments should support deterministic replay by recording random seeds, policy versions, graph snapshots, and worker provenance.

No MOSAIC experiment should autonomously change repository governance or production security policy.

---

## Implementation links

TBD.

Suggested initial modules:

```text
idkmesh/
  policy/
    mosaic/
      state.py
      fitness.py
      diversity.py
      temperature.py
      branching.py
      allocator.py
      evidence.py
      immune.py
      reputation.py
      cells.py
  simulator/
    agents.py
    workloads.py
    adversaries.py
    experiments.py
```

The implementation structure is illustrative and should not be treated as an architectural commitment.

---

## External inspirations / prior art

These references support individual mechanisms; none establishes the complete MOSAIC synthesis.

- Active inference and the combination of pragmatic and epistemic/information-seeking value: https://pmc.ncbi.nlm.nih.gov/articles/PMC9662737/
- Active inference and expected free energy: https://pmc.ncbi.nlm.nih.gov/articles/PMC5167251/
- Evolutionary game theory and replicator dynamics: https://plato.stanford.edu/entries/game-evolutionary/
- Stigmergic coordination in social insects: https://pmc.ncbi.nlm.nih.gov/articles/PMC6030583/
- Information aggregation and heterogeneity in collective intelligence: https://www.nature.com/articles/s44159-022-00054-y
- Small-group deliberation and aggregation: https://www.nature.com/articles/s41562-017-0273-4
- Diversity and wisdom of crowds: https://www.nature.com/articles/s41598-021-95914-7
- Elinor Ostrom on polycentric governance: https://www.nobelprize.org/prizes/economic-sciences/2009/ostrom/lecture/
- Self-organizing systems and adaptive complexity: https://www.nature.com/articles/s44260-025-00031-5
- Adaptation near criticality: https://www.nature.com/articles/s41598-018-25925-4
- Optimization by self-organized criticality: https://www.nature.com/articles/s41598-018-20275-7
- Artificial immune-system research, including negative selection and immune-inspired self-healing: https://link.springer.com/book/10.1007/978-3-642-33757-4

---

## Decision history

- **2026-08-28 — Draft:** Initial multidisciplinary synthesis proposed for experimentation. No architectural adoption decision has been made.
