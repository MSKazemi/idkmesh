# Algorithm Collaboration Fabric

**Status:** architecture proposal v0.1
**Date:** 2026-08-28
**Authority:** design and decision-support only; no merge, approval, spending, or autonomous-governance authority

## Purpose

IDKMesh already contains many useful algorithms, but the important systems problem is no longer only **which algorithm is good**. It is:

> How can different algorithms cooperate without duplicating responsibility, amplifying each other's errors, or turning a statistical score into authority?

The proposed answer is an **Algorithm Collaboration Fabric (ACF)**: a typed blackboard / federated-control architecture in which algorithms publish bounded signals to shared project state and downstream algorithms consume only the signal classes they are allowed to use.

The algorithms do **not** negotiate one global fitness score.

The system instead separates:

```text
observe
  -> represent
  -> prioritize
  -> generate
  -> admit resources
  -> route/execute
  -> verify
  -> aggregate evidence
  -> control flow
  -> learn
  -> govern/integrate
  -> observe again
```

The most important invariant is:

> Better prediction, routing, optimization, or evidence can improve a proposal, but none of those algorithms can manufacture integration authority.

---

## 1. Why composition is harder than adding algorithms

Many current IDKMesh algorithms can influence similar-looking quantities:

- Pareto / NSGA-II ranks alternatives;
- UCB chooses under-explored strategies;
- multiplicative weights changes long-horizon strategy mass;
- Bayesian health models update historical beliefs;
- R2 randomized scheduling chooses workers under load/churn;
- R4 stigmergy learns task-worker affinity;
- R3 evolutionary search proposes orchestration policies;
- verification backpressure controls generation rate;
- sequential evidence decides whether repeated experiment evidence is strong enough to nominate a policy;
- ACE/community controllers regulate community growth;
- branch convergence chooses the next integration-review action;
- human/GitHub governance decides whether a protected change is actually integrated.

If all of these directly optimize the same scalar, the project risks:

1. **double counting** the same evidence;
2. **positive-feedback lock-in** where one early signal reinforces every layer;
3. **authority leakage** where an optimization signal becomes an integration decision;
4. **control oscillation** where several controllers change the same variable at incompatible timescales;
5. **Goodhart failure** where activity/popularity replaces verified useful work;
6. **false independence** where correlated or non-discriminating verifiers are counted as independent evidence.

Therefore algorithms should collaborate by **role separation + typed interfaces + timescale separation + provenance**.

---

## 2. Canonical collaboration graph

```text
                         +-----------------------+
                         | Constitution / Policy |
                         | hard guards + limits  |
                         +-----------+-----------+
                                     |
                                     v
+------------------+       +---------+----------+
| GitHub / runtime | ----> | Observation layer |
| public evidence  |       | observatories      |
+------------------+       +---------+----------+
                                     |
                                     v
                         +-----------+-----------+
                         | IDKGraph / state      |
                         | typed project model   |
                         +-----+-------------+---+
                               |             |
                    priorities |             | resource/task facts
                               v             v
                   +-----------+---+    +----+----------------+
                   | Portfolio /   |    | Resource admission  |
                   | exploration   |    | hard capability/cost|
                   | Pareto/UCB/MW |    | /trust filters      |
                   +-------+-------+    +---------+-----------+
                           |                      |
                           v                      v
                   +-------+--------+     +-------+---------+
                   | Candidate /    |     | Routing          |
                   | policy proposal|     | R2 + R4          |
                   | R3 / workers   |     | load + affinity  |
                   +-------+--------+     +-------+---------+
                           |                      |
                           +----------+-----------+
                                      |
                                      v
                              +-------+-------+
                              | Execution     |
                              | ResultManifest|
                              +-------+-------+
                                      |
                                      v
                        +-------------+-------------+
                        | Independent verification |
                        | EvaluatorPlan -> result  |
                        +-------------+-------------+
                                      |
                  +-------------------+-------------------+
                  |                   |                   |
                  v                   v                   v
          +-------+------+   +--------+--------+  +-------+---------+
          | Backpressure |   | Sequential /   |  | Learning        |
          | verification |   | aggregate      |  | Bayes/R4/UCB/MW |
          | debt/fanout  |   | evidence       |  | parameter update|
          +-------+------+   +--------+--------+  +-------+---------+
                  |                   |                   |
                  +-------------------+-------------------+
                                      |
                                      v
                         +------------+-------------+
                         | Governance / integration |
                         | PR gate + human decision |
                         +------------+-------------+
                                      |
                                      v
                                    main
                                      |
                                      +----> next observation cycle
```

This graph is deliberately asymmetric. Verification and governance sit downstream of generation and execution, not inside the same optimizing agent.

---

## 3. Shared blackboard: IDKGraph as the semantic state bus

`IDKGraph` is the natural semantic blackboard because it already models typed nodes such as:

- Goal;
- Question;
- Hypothesis;
- Constraint;
- WorkUnit;
- Artifact;
- Evidence;
- Decision;
- Metric;
- Contributor / Agent / ComputeResource;
- Policy;
- Experiment.

The collaboration rule should be:

```text
algorithm output
  -> typed evidence/signal artifact
  -> provenance-bound IDKGraph update/projection
  -> downstream consumer
```

not:

```text
algorithm A mutates hidden state inside algorithm B
```

This makes the system inspectable and replayable.

### Projections remain specialized

Do not force all algorithms to operate on the full graph.

Use projections:

```text
IDKGraph
  +-> executable WorkUnit DAG / AND-OR graph
  +-> contributor/task bipartite graph
  +-> evidence/provenance graph
  +-> document/concept graph
  +-> resource/capability graph
  +-> branch/PR integration graph
```

Each algorithm receives the smallest projection necessary for its job.

---

## 4. Typed algorithm signal envelope

Algorithms should exchange a small common envelope rather than raw undocumented scalars.

Conceptually:

```json
{
  "signal_id": "...",
  "producer": "algorithm-id/version",
  "scope": ["stable-id-or-revision"],
  "signal_type": "priority|affinity|risk|capacity|evidence|guard|proposal",
  "estimate": "typed value",
  "observation_model": "named model or deterministic rule",
  "evidence_mass": "sample size / effective sample size / count / digest set",
  "uncertainty": "interval or explicit not-applicable",
  "assumptions": [],
  "failure_modes": [],
  "evidence_refs": [],
  "source_revision": "exact SHA / graph revision",
  "fresh_until": "optional bounded validity",
  "authority_ceiling": "observe|recommend|propose",
  "generated_at": "timestamp"
}
```

This follows the repository's uncertainty rule: a metric that influences evolution should expose its observation model, evidence mass, uncertainty, assumptions, and failure modes rather than only a generic confidence number.

### Hard rule

```text
missing provenance or unknown model
        -> signal may remain telemetry
        -> signal cannot silently become stronger evidence
```

---

## 5. Role ownership matrix

| Algorithm family | Owns | May influence | Must not own |
| --- | --- | --- | --- |
| IDKGraph / observatories | state representation and measured facts | all downstream planning | correctness or merge decisions |
| Pareto / NSGA-II | multi-objective attention frontier | which work deserves inspection | acceptance |
| Graph unlock | prerequisite/bridge value | work priority | correctness |
| UCB | bounded exploration choice | which strategy to test | production promotion |
| Multiplicative weights / replicator | longer-term experiment-budget mixture | resource share among strategies | constitutional authority |
| Bayesian evolution | historical uncertain health belief | attention need / guard diagnostics | causality or integration |
| R3 evolutionary orchestration | orchestration-policy proposals | experiment candidates | self-promotion |
| Free Resource Mesh + admission | allowed concrete resource set | execution capacity | capability invention |
| R2 | local load/churn scheduling | worker assignment | trust/correctness |
| R4 | verified task-worker affinity | routing preference | positive update from activity alone |
| Verifier / EvaluatorPlan | candidate evidence | VerificationResult | merge authority |
| correlation-aware aggregation | effective evidence strength | verifier combination | independence without measurement |
| Sequential Evidence Kernel | repeated-experiment evidence strength | policy nomination | merge/activation |
| verification backpressure | verifier queue + generation fanout | how much new work is allowed | candidate correctness |
| ACE/community evolution | bounded onboarding/growth | invitations / community experiment rate | correctness from popularity |
| branch convergence planner | integration-review ordering | which PR/branch to examine next | direct branch merge |
| GitHub/human governance | protected integration decision | canonical main | statistical optimization |

The collaboration fabric should reject configurations where two algorithms both claim the same final authority.

---

## 6. How the mathematical algorithms should collaborate

### 6.1 Pareto first, bandits second

Use Pareto/NSGA-II to keep real trade-offs visible:

```text
z_i = (
  impact,
  information_gain,
  unlock,
  diversity,
  -risk,
  -cost,
  -review_burden
)
```

Then use UCB only to allocate a bounded exploration budget **within or among admissible strategy/frontier regions**.

Recommended order:

```text
hard eligibility
   -> Pareto frontier
   -> diversity/crowding
   -> UCB exploration among remaining experiment choices
```

Do not let a high UCB bonus resurrect a candidate removed by a hard safety/capability constraint.

### 6.2 Multiplicative weights operates slower than UCB

UCB answers:

> What should receive the next bounded trial?

Multiplicative weights answers:

> Over many iterations, how should experimental attention be distributed among strategies?

Therefore:

```text
fast exploration choice: UCB
slow budget adaptation: multiplicative weights / replicator
```

The exploration floor in both layers prevents permanent extinction from early noise.

### 6.3 Bayesian history is context, not reward truth

Bayesian repository-health beliefs should influence **need** and uncertainty, not directly become the reward sent to every other adaptive algorithm.

For example:

```text
low conservative verification-health bound
   -> portfolio increases attention to verification work
```

not:

```text
Bayesian verification score rose
   -> every verification strategy receives positive causal reward
```

The latter would double-count unvalidated causal assumptions.

### 6.4 Sequential evidence validates repeated experiments

R3, UCB, or a new policy can generate a proposed experiment. Repeated observations should pass through the Sequential Evidence Kernel before claiming persistent improvement.

```text
candidate policy
  -> paired baseline experiment
  -> sequence of bounded effects D_t
  -> anytime-valid confidence sequence
  -> if hard guards pass and lower bound exceeds minimum effect:
       experiment_candidate
```

The output remains a nomination, not an integration action.

---

## 7. R2 + R4: a useful routing collaboration

R2 and R4 solve different parts of routing.

### R2 owns local coordination cost and load/churn

R2 asks:

> Can a small local sample route effectively without global current-state scans?

It provides mechanisms such as capability-aware power-of-two sampling and explicitly measures metadata-probe cost, staleness, churn, requeues, and locality.

### R4 owns learned task-worker affinity

R4 asks:

> Which eligible worker-task pairs have a verified history of useful outcomes, while still forgetting stale advantages and exploring newcomers?

Its key rule is:

```text
activity != pheromone
verified outcome -> pheromone update
```

### Recommended composition

Do not let R4 choose from the entire universe and do not let R2 ignore outcome history.

Use:

```text
WorkUnit
  -> policy/security/cost/capability admission
  -> eligible resource set E
  -> R2 small local sample S subset E
  -> R4 affinity/exploration inside S
  -> assignment
```

One candidate composite selection rule for research is:

```text
P(worker i | task a, S)
  proportional to
    exp(-lambda_L * normalized_observed_load_i)
    * tau[a,i]^alpha
    * exploration_bonus[a,i]
```

subject to the hard eligibility set `S`.

This should be tested against simpler baselines, not assumed better.

### Why this division is valuable

- R2 limits coordination metadata cost;
- R4 gives adaptation across verified outcomes;
- evaporation handles non-stationarity;
- explicit exploration gives newcomers a path;
- hard resource admission prevents learned affinity from bypassing cost/security/capability policy.

---

## 8. Verification backpressure should regulate R3 and worker fan-out

Verification is a scarce trust resource.

Let total risk-weighted verification debt be:

```text
D_t = sum_i Debt_i
```

and normalized load:

```text
q_t = D_t / verification_capacity_t.
```

The backpressure controller should output a bounded generation multiplier/fanout limit.

That signal should constrain:

- number of independent worker attempts;
- R3 population or candidate count for real experiments;
- number of concurrent branch/extraction proposals;
- ACE/community-generated new implementation tasks.

It should **not** change verifier verdicts.

Thus:

```text
high verification debt
   -> reduce new candidate supply
   -> preserve capacity for evidence clearing
```

This is one of the most important negative-feedback loops in the project.

---

## 9. Verification collaboration requires a discrimination gate

The repository's E016 live verifier experiment produced an important negative result: a nominally diverse panel can have different opinions while carrying essentially no useful task-level signal.

Therefore the collaboration pipeline must separate:

```text
verifier diversity
from
verifier discrimination
from
verifier independence
```

Recommended pipeline:

```text
candidate verifiers
  -> discrimination/calibration screen
  -> remove constant/non-informative instruments
  -> only then estimate dependence/correlation
  -> only then compute effective evidence mass
  -> aggregate recommendations
```

A near-zero measured correlation among noise or constant outputs is **not** evidence of useful independence.

Correlation-aware effective sample size should therefore require a preceding quality/discrimination gate.

---

## 10. Learning update graph

A verified outcome should update only the algorithms whose model semantically owns that evidence.

Example successful candidate:

```text
VerificationResult
  +-> R4: update task-worker pheromone
  +-> verifier calibration: update reliability evidence
  +-> verification debt: remove/adjust queue debt
  +-> experiment result stream: append observation
  +-> sequential evidence: update candidate-vs-baseline sequence
  +-> Bayesian repository observer: bounded health evidence if policy maps it
  +-> IDKGraph provenance: attach verification/evidence edges
```

It should **not** automatically:

- merge the PR;
- award contributor governance power;
- declare a causal improvement;
- give all adaptive policies reward;
- bypass held-out discipline.

This selective update graph prevents one observation from being counted repeatedly under different names.

---

## 11. Multiple timescales

Algorithms should operate at deliberately different timescales.

| Timescale | Main algorithms | Typical variable |
| --- | --- | --- |
| per routing decision | R2 / R4 | worker assignment |
| per candidate/result | verifier, evidence binding | pass/fail/evidence |
| per verification window | RWVB backpressure | fanout / verifier priority |
| per experiment batch | sequential evidence | policy nomination |
| per research generation | R3 evolution | orchestration genome population |
| per repository observation | Bayesian observer / portfolio | health beliefs / attention |
| per community generation | ACE | onboarding/growth proposal |
| per integration transaction | branch planner + governance | one PR decision |

This helps prevent controllers from fighting each other.

For example, a routing algorithm may adapt every task while the repository strategy mixture changes only after a larger batch of trustworthy evidence.

---

## 12. Homeostasis as a cross-layer safety diagnostic

Use the Lyapunov-style potential as a system-level diagnostic:

```text
V(R) = sum_j q_j * ((x_j - target_j) / scale_j)^2.
```

For a bounded automated change or experiment:

```text
hard_invariants_pass
AND V_after <= V_before + tolerance
```

can be a useful **additional** condition.

Do not optimize `V` alone. It is a health envelope, not a complete utility function.

A candidate can reduce `V` while still being incorrect; independent verification remains required.

---

## 13. Community algorithms should consume verified opportunities, not raw activity

ACE/community evolution can collaborate with the portfolio and graph layers as follows:

```text
IDKGraph unmet goals / ready WorkUnits
  -> portfolio identifies bounded opportunities
  -> review capacity + carrying capacity checked
  -> ACE emits limited contributor/onboarding opportunities
  -> contributors produce candidates
  -> independent verification
  -> verified lineage evidence
  -> later community-generation update
```

The reinforcement signal should be:

```text
verified useful descendant
```

not:

```text
comment / commit / issue / follower count
```

This preserves the project's existing anti-Goodhart rule that activity is not correctness.

---

## 14. Branch convergence is the final coordination layer before governance

The branch merge planner should consume the outputs of all earlier layers as evidence, but retain a narrow job:

```text
which branch/PR should be reviewed next?
```

It should never reinterpret:

- R4 pheromone as merge evidence;
- UCB priority as approval;
- Bayesian posterior as branch authority;
- sequential evidence as permission to bypass review;
- verifier recommendation as a merge command.

A useful collaboration boundary is:

```text
technical algorithms
  -> evidence and priority
  -> branch convergence planner
  -> exact-head integration review
  -> human/protected GitHub decision
```

After every merge, `main` changes and the plan must be recomputed.

---

## 15. Conjunctive controller as a safety membrane

The existing Conjunctive Evolution Control is the correct pattern for combining heterogeneous algorithms.

Use:

```text
soft optimization signals
AND conservative uncertainty bounds
AND live capacity
AND hard guards
```

not one weighted sum.

Generic form:

```text
AdmissibleAction(a,t) =
    HardGuards(a,t)
    AND Capacity(a,t)
    AND EvidenceSufficient(a,t)
    AND ProvenanceCurrent(a,t)
    AND AuthorityAllows(a,t)
```

Only after `AdmissibleAction` is true should ranking algorithms decide **which** admissible action to recommend.

This creates a strong separation:

```text
feasibility / safety = conjunctive
preference / exploration = comparative
integration = external governance
```

---

## 16. A complete iteration

A mature IDKMesh iteration can be written as:

```text
O_t = Observe(GitHub_t, runtime_t)
G_t = UpdateIDKGraph(O_t)

H_t = HardGuards(G_t)

F_t = ParetoFront(G_t)
A_t = ExploreWithUCB(F_t)
M_t = SlowMixtureUpdate(A_t, historical_evidence)

B_t = VerificationBackpressure(queue_t, verifier_capacity_t)
C_t = GenerateCandidates(A_t, fanout=B_t)

E_t = ResourceAdmission(C_t, policy_t, resource_evidence_t)
X_t = Route(C_t, E_t, R2_state_t, R4_state_t)

R_t = Execute(X_t)
V_t = IndependentVerify(R_t, evaluator_owned_plan_t)

Q_t = UpdateSequentialEvidence(V_t)
L_t = SelectiveLearningUpdate(V_t, Q_t)

P_t = BranchConvergencePlan(G_t, V_t, Q_t)
D_t = ExternalIntegrationDecision(P_t, H_t)

if D_t changes main:
    invalidate plan
    begin t+1 from a new observation snapshot
```

The final decision `D_t` is intentionally outside the optimization/learning loop.

---

## 17. Anti-feedback rules

The fabric should enforce at least these rules:

1. **No raw activity reinforcement into correctness.**
2. **No learning update without provenance to the observation that caused it.**
3. **No duplicated reward for one event across multiple adaptive algorithms unless each update models a distinct quantity.**
4. **No verifier correlation estimate before verifier discrimination/calibration is established.**
5. **No exploration algorithm may override a hard gate.**
6. **No routing history may expand the hard eligible-resource set.**
7. **No worker self-report may become independent VerificationResult.**
8. **No sequential/statistical evidence may become merge authority.**
9. **No branch planner may directly merge arbitrary branch refs.**
10. **No self-evolution algorithm may be the sole proposer, verifier, approver, and merger of its own protected change.**

---

## 18. What should be implemented next

The next useful implementation is not another optimization algorithm.

It is a small **algorithm-signal contract** that makes the collaboration fabric machine-readable.

Recommended v0.1 tasks:

1. define `algorithm-signal-v0.1.schema.json`;
2. require exact producer/version/source revision;
3. require an authority ceiling;
4. support deterministic signal types: `guard`, `priority`, `capacity`, `affinity`, `evidence`, `proposal`;
5. support uncertainty metadata consistent with `METRIC_UNCERTAINTY_V0_1.md`;
6. add provenance/evidence references;
7. add freshness / expiry semantics;
8. implement a validator that rejects unknown authority escalation;
9. build one end-to-end experiment:

```text
IDKGraph WorkUnit
 -> portfolio priority signal
 -> verification-backpressure capacity signal
 -> resource admission
 -> R2+R4 routing proposal
 -> ResultManifest
 -> VerificationResult
 -> selective learning signals
 -> branch/governance recommendation
```

The experiment should prove **information flow and authority separation**, not superiority of every algorithm.

---

## 19. Success criterion

The fabric is working when algorithms can improve each other's decisions while remaining replaceable.

A useful architecture-level objective is:

```text
CollaborativeValue =
  verified useful progress * information gained * resilience
  ----------------------------------------------------------
  coordination cost * verification debt * duplicated evidence * authority risk
```

This is a conceptual objective, not a production scalar fitness.

The deeper success criterion is structural:

> Each algorithm can be changed, falsified, or removed without breaking the authority boundaries of the whole system.

That is how IDKMesh can become more intelligent without making one algorithm the brain, judge, and governor at the same time.

---

## Related canonical surfaces

- `docs/architecture/IDKGRAPH_TASK_AND_EVOLUTION_MODEL.md`
- `docs/architecture/MATHEMATICAL_EVOLUTION_KERNEL.md`
- `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO.md`
- `docs/architecture/CONJUNCTIVE_EVOLUTION_CONTROL.md`
- `docs/architecture/RESOURCE_COMPUTE_ADMISSION.md`
- `docs/architecture/SEQUENTIAL_EVIDENCE_KERNEL.md`
- `docs/research/R2_SCHEDULING_CHURN_EXPERIMENT.md`
- `docs/research/R3_EVOLUTIONARY_ORCHESTRATION.md`
- `docs/research/R4_STIGMERGIC_ROUTING.md`
- `docs/research/VERIFICATION_DEBT_AND_BACKPRESSURE.md`
- `docs/research/METRIC_UNCERTAINTY_V0_1.md`
- `docs/research/PHASE_0_SPEC.md`
- `docs/planning/BRANCH_CONVERGENCE_POLICY.md`
- `docs/planning/BRANCH_MERGE_EXECUTION_PLAN.md` (canonical execution plan integrated by PR #211)
