# IDKMesh Scientific Program

**Date:** 2026-10-09
**Status:** canonical statement of the project's scientific targets. It decides
*what IDKMesh is trying to find out*. How each paper is written is decided by
[`PUBLICATION_RESEARCH_QUESTIONS_2026-10-07.md`](PUBLICATION_RESEARCH_QUESTIONS_2026-10-07.md),
and how the product proves its engineering claims by
[`ENGINEERING_ANSWER_STRENGTHENING_PLAN_2026-10-07.md`](../planning/ENGINEERING_ANSWER_STRENGTHENING_PLAN_2026-10-07.md).
**Umbrella issue:** [#968](https://github.com/MSKazemi/idkmesh/issues/968) — epics #969 (S1–S2), #971 (S3), #972 (S4)

[`RESEARCH_QUESTIONS.md`](https://github.com/MSKazemi/idkmesh/blob/main/RESEARCH_QUESTIONS.md) remains the long-horizon
idea backlog: about ninety questions, from consensus to quantum annealing.
Those questions are **not** current targets. A question becomes a target only when
this document names it, gives it a falsifier, and links an issue.

---

## 1. The question

> **When does adding another AI agent — a worker that writes code, or a verifier
> that judges it — increase independently verified useful work, and can that be
> predicted from a small pilot before the cost is paid?**

Every IDKMesh mechanism exists to answer, or to act on the answer to, this
question. That includes WorkUnits, isolated attempts, verifier-owned evaluation,
gate-audit, routing and backpressure.

### Formal statement

For a task distribution *T*, a worker set *W* and a verifier panel *P* with an
acceptance rule *q*, let *V(W, P)* be the probability that a task ends with an
accepted candidate that is actually correct. The program measures three
quantities and their marginals:

| quantity | meaning | limited by |
|---|---|---|
| **coverage** *C(W)* | P(at least one worker produces a correct candidate) | worker dependence and the worker blind-spot floor λ_W |
| **harvest** *H(P, q \| W)* | P(the panel accepts a correct candidate and no incorrect one) | verifier dependence, the verifier blind-spot floor λ_V, and the quorum |
| **cross-dependence** | whether verifiers are fooled exactly where workers produce plausible but wrong candidates | the joint shape of worker and verifier failures |

The decision quantities are the marginal values Δ_W = V(W ∪ {w}, P) − V(W, P)
and Δ_P = V(W, P ∪ {v}) − V(W, P), each set against the cost of the added agent.
They are measured in Verified Useful Work per Unit of Scarce Resource, the
outcome vector defined in the publication strategy, §1.

The product consequence is a single operator-facing answer: **"for this task
class, run *n* workers and *m* verifiers, choose these ones, and expect this
much verified work; past that point, send the task to a human."**

---

## 2. Who this is for

| audience | the decision they face | what the program gives them |
|---|---|---|
| **Engineering leaders and platform teams running coding agents** (primary) | How many attempts, agents and reviewers to pay for, and which ones | A sizing advisor that predicts marginal verified value from a pilot (engineering target T2), plus evidence of when *not* to add agents |
| **AI-for-SE and LLM-evaluation researchers** (primary) | Is my ensemble, judge panel or best-of-N result as independent as it looks? | A dependence-shape theory with preregistered out-of-sample tests, and a reproducible public instrument |
| **Benchmark and leaderboard maintainers** | What does the field collectively fail at? Is a new task informative? | Population coverage, blind-spot floors, and forecast curves per split |
| **Software-reliability and N-version-programming researchers** | Does the Eckhardt–Lee picture still hold for AI-built software? | The first large modern test of item-difficulty dependence on execution-graded AI systems |
| **Open-source contributors** | Where can I do real research with a laptop? | Bounded, reproducible experiment tasks at zero project spend |

**Not the audience:** token or crypto incentive design, and claims of "collective
intelligence" or AGI. The program makes neither claim (§9).

---

## 3. Hypotheses

Each hypothesis names its falsifier before any confirmatory data is opened.

| ID | hypothesis | falsified if | instrument | status |
|---|---|---|---|---|
| **H1 — shape** | A per-item difficulty model (beta-binomial or IRT) predicts held-out ensemble behaviour better than independence, the Kish design effect, or a shared-shock mixture at equal parameter count. Ensemble behaviour means the coverage curve, partial-failure counts and blind-spot floor. | On held-out splits, the Kish or shared-shock forecast error is ≤ the item-difficulty error on the primary endpoint | Worker side: public SWE-bench splits (X3). Verifier side: E017, plus the X6 and X7 panels | Supported on one verifier panel (E017/E020); worker side untested |
| **H2 — forecast** | From a pilot of k ≤ 10 agents, the best preregistered estimator forecasts population coverage and the blind-spot floor within an absolute error of 0.03 | No estimator meets the tolerance at k = 10 on held-out splits | Public splits (X4) | Exploratory pilot (E045): Chao2 mean absolute error is 0.0609 at k = 10, so it fails the tolerance; IRT-based forecasts not yet tried |
| **H3 — selection** | Complementarity-aware selection beats choosing the most accurate agents, and beats choosing for declared provider or family diversity, at equal ensemble size | Paired by task, top-k-by-accuracy matches or beats it on held-out tasks | Public splits (X5) | Untested |
| **H4 — harvest** | With real, imperfect verifiers, the verified gain from more workers is capped by verifier dependence. The best split of a fixed budget between workers and verifiers is predictable from the two measured shapes | Fixed heuristics (all workers; 50/50) match the predicted split's verified value | X6 + X7 + X8 | Synthetic only (E040, E043: "a panel does not pay for itself") |
| **H5 — attack surface** | Escapes are determined by verifier correlation, not mean verifier accuracy, when candidates are adversarial or plausibly wrong | At matched accuracy, the correlated and decorrelated panels have equal escape rates on real plausibly-wrong patches | X6 (patches that pass visible tests but fail hidden ones) | Synthetic (E036: 0 vs 58/100) |
| **H6 — controlled confirmation** | In IDKMesh's own matched-budget cohort, the H1–H4 predictions calibrated on public data hold within their intervals | The predictions miss outside their intervals on the frozen cohort | Own cohort (X9; Paper B in the publication strategy) | Protocol work underway (#936 steps 3–5, #70, #13) |

**Secondary tracks.** These are kept, but they do not compete for the next
unit of effort:

- quality-diversity adaptation under goal drift (Paper C, E024–E039);
- verification backpressure (Paper D, E021/E022/E044);
- adaptive routing (Paper E, PHY and R2).

They return to the front only when the main question needs them, for example
when backpressure turns out to be the binding constraint in H4.

---

## 4. What is already established

| thread | established | falsified | biggest open question |
|---|---|---|---|
| **Verifier dependence** (E012–E020, E025, E043) | Head count is not evidence: on the real panel the effective size is ≤ 1. Shared shock is the wrong shape (11 of 15 majority failures are partial). A blind-spot floor exists (λ = 0.0556). Choosing the quorum buys 3.75×; adding verifiers buys nothing | E015's accuracy-dependent ceiling; declared-group balancing as a safe default; a panel paying for itself under per-read billing | Does the shape replicate on verifiers whose diversity was not designed in? |
| **Worker dependence** (E032, E040, E042, **E045**) | In simulation, advantage is proportional to independence (R² ≥ 0.99 in 17/18 curves). In **169 real systems**, mean φ = 0.4763, 26/500 tasks are unsolved by all, and independence overstates best-of-10 coverage by 0.148 | Issue #13's H1 as stated; E040's hedge (E042) | Which dependence shape forecasts a held-out population? |
| **Adversaries** (E036–E039, AVE-3) | Correlation is the attack surface; attacker effort matters more than attacker fraction; probe trust can be gamed | "Coordination always helps the attacker" (E039) | Real plausibly-wrong candidates |
| **Real producers** (E016, E029) | 1–2B models can neither verify (0/20 discriminate) nor produce (0/60 accepted) on the frozen benchmark | — | A producer strong enough to measure |

The full per-experiment ledger is the [experiment index](https://github.com/MSKazemi/idkmesh/blob/main/experiments/README.md).

---

## 5. Experiments to complete

Ordered by what unblocks what. **X1 to X6 need no project spend:** public data,
plus local CPU or Docker.

| ID | question | tests | instrument | needs | issue |
|---|---|---|---|---|---|
| **X1** | Is worker dependence large in a real population? | (pilot) | SWE-bench Verified, 169 systems | — | **Done: [E045](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E045-public-agent-dependence-pilot.md)** (exploratory) |
| **X2** | Freeze the confirmatory analysis before any held-out data is opened | H1–H3 | Preregistration naming the Lite, Test, Multilingual and Multimodal splits and a post-freeze temporal holdout | X1 | #973 |
| **X3** | Which dependence shape forecasts held-out ensemble behaviour? | H1 | Held-out public splits | X2, A1 | #975 |
| **X4** | Can a k-agent pilot forecast population coverage and the floor? | H2 | Held-out public splits | X2, A2 | #976 |
| **X5** | Does complementarity-aware selection beat accuracy and diversity labels? | H3 | Held-out public splits | X2, A4 | #977 |
| **X6** | Does E017's verifier shape replicate on real candidates at scale? | H1, H4, H5 | Partial-oracle panels (subsets of each task's hidden tests) voting on real submitted patches | T5, T3 | #979 |
| **X7** | Do LLM judges on the same patches share that shape? | H1, H4 | Locally served open-weight judges, screened by Youden's J as in E016 | X6, zero-spend compute | #980 |
| **X8** | Is the best worker/verifier budget split predictable? | H4 | Joint model fitted on X3 + X6, validated on held-out tasks | X3, X6, A6 | #981 |
| **X9** | Do the calibrated predictions hold in IDKMesh's own cohort? | H6 | Frozen matched-budget cohort | T3, T4, #936 step 3 | #936 (steps 3–5), #70 |
| **X10** | Second verifier family for the existing paper | H1 | Preregistered replication | zero-spend compute | #936 (step 2) |

**Kill criteria for the whole program.** The headline claim, *"agent value is
forecastable from measured dependence"*, is withdrawn if all three of the
following hold:

1. H1 is falsified on both the worker side and the verifier side.
2. No H2 estimator beats "use the pilot's own coverage".
3. The selection gain in H3 is not distinguishable from zero.

Each of those outcomes would still be published.

---

## 6. Algorithms the program must deliver

Each algorithm is evaluated against the simplest baseline that answers the same
decision. Each ships as a diagnostic first; none gains dispatch or acceptance
authority from this program.

| ID | algorithm | baseline it must beat | used by |
|---|---|---|---|
| **A1** | **Dependence-shape fitting and selection.** Fits independence, Kish, shared shock, beta-binomial, Rasch/2PL IRT and provenance-clustered IRT, with cross-validation grouped by task and by model × scaffold provenance | Pairwise φ plus the Kish design effect | X3, X6, X7 |
| **A2** | **Coverage forecasting.** Incidence-based rarefaction and extrapolation (Chao2, and iNEXT-style per Chao et al. 2014) against IRT-based Monte Carlo, with intervals | The pilot's own observed coverage | X4, T2 |
| **A3** | **Marginal value of agent k+1**, for workers and for verifiers; it extends the panel evidence-contribution work in #693 | Standalone accuracy | T2, X5 |
| **A4** | **Complementarity-aware selection.** Greedy maximisation of predicted coverage, which is monotone submodular, giving the (1 − 1/e) guarantee of Nemhauser, Wolsey &amp; Fisher 1978 on a known matrix | Top-k by accuracy; one per provider or family | X5, T2 |
| **A5** | **Dependence-aware quorum choice.** Picks the acceptance threshold from the fitted verifier shape (E020) | Simple majority | X6, gate-audit |
| **A6** | **Generate-versus-verify budget allocator.** Splits a fixed budget between worker attempts and verifier calls to maximise predicted *V* | All workers; 50/50; all verifiers | X8, T2 |
| **A7** | **Blind-spot routing.** Flags tasks predicted to sit in λ_W or λ_V and routes them to a human instead of spending more agents on them | No routing | T2 |

---

## 7. Engineering targets

These are the product capabilities the science needs, and that turn its answers
into something an operator uses. Targets without a new issue already have a
canonical owner; this program does not create parallel ones.

| ID | target | why the science needs it | owner |
|---|---|---|---|
| **T1** | Reproducible ingestion of public execution-graded matrices: pinned upstream commit, per-file digests, provenance fields (model, scaffold, organisation, date) | X2 to X5 are only as credible as their data lineage | #974 |
| **T2** | **Ensemble sizing advisor** (`idkmesh` CLI, alongside `gate-audit`): given a measured matrix, report shape, forecast, marginal value, recommended selection and split, and blind-spot tasks | It is the product surface for A2–A7, and the operator-facing answer in §1 | #982 |
| **T3** | A real sandbox backend for untrusted agent and test execution | X6, X7 and X9 execute untrusted patches and agents | #804 |
| **T4** | The golden-path local loop producing a ResultManifest and a VerificationResult per attempt | X9 needs the product's own execution-graded attempts | #682, #16, #943 |
| **T5** | A partial-oracle panel harness for public patches: run subsets of each task's hidden tests against submitted patches and record a verdict matrix | X6 is the at-scale replication of E017 | #978 |
| **T6** | Capability truth and claim-drift gate | Public wording must follow the evidence class (§9) | #944 |

---

## 8. Novelty and prior art

These sources were checked on 2026-10-09 by reading the primary abstracts; the
search notes are linked in the umbrella issue. **Absence below means "not found
by that search", not "does not exist".** Re-run the novelty check before
submission.

| work | what it already establishes | consequence for IDKMesh |
|---|---|---|
| Eckhardt &amp; Lee 1985; Littlewood &amp; Miller 1989 | Item-difficulty dependence between independently developed versions | We test the model's *ensemble-design predictions* on modern AI systems; the model is not ours |
| Kuncheva &amp; Whitaker 2003 | Diversity measures and their weak link to ensemble accuracy | Our claim is forecasting, not a new diversity score |
| Kim et al., ICML 2025, "Correlated Errors in Large Language Models" | Over 350 LLMs agree on about 60% of shared errors on leaderboard multiple choice; more accurate models are more correlated | Correlation itself is known. We target execution-graded coding, forecasting, and selection |
| Kohli 2026, arXiv 2605.29800 | Nine LLM judges amount to about two effective votes (Kish) | Already credited in the panel paper. Kish is a baseline we must beat |
| Shu 2026, arXiv 2608.06940 | Verification gains concentrate on pivotal (one-vote-margin) queries | Consistent with partial-failure structure; cite in H4 |
| Ge et al. 2026, arXiv 2604.00594 | IRT with task features predicts per-task success of coding agents | IRT fit quality is prior art. Our estimand is ensemble coverage, marginal value, and the floor |
| Liu et al. 2026, arXiv 2609.17394 | SWE-bench top entries share outcomes (nesting 0.935) and cannot be ordered by McNemar; within-model scaffold range up to 29.8 points | Closest data overlap. They audit *rankings*; we forecast *ensemble value* and must model the scaffold provenance they identify |
| Chao 1987; Chao et al. 2014 (*Ecological Monographs* 84:45–67) | Incidence-based richness estimation and extrapolation | We transfer the estimators; the transfer and its validation are the contribution |

**The novelty claim this program is built to earn.** We found no prior study
that does any of the following:

1. forecasts, out of sample, the oracle ensemble coverage and blind-spot floor
   of real coding agents from a small pilot;
2. ranks dependence models by the *ensemble-design decisions* they get right
   (size, selection, quorum, budget split) rather than by fit;
3. joins worker-side and verifier-side dependence into one verified-useful-work
   model, with a budget-allocation rule tested on execution-graded data.

### What "10× more novelty and scientific value" means here

This is a target expressed in measurable levers, not a measured increase.

| lever | before this program | after X1–X8 |
|---|---|---|
| real execution-graded observations | 1,800 votes (25 oracles × 72 items, E017) | 84,500 worker outcomes on Verified alone (E045), plus four held-out splits and an at-scale verifier panel |
| systems not designed by the author | 0 (25 oracles constructed by the author) | 169 leaderboard systems from many teams; shared models and scaffolds are modelled as provenance, not assumed independent |
| claim type | descriptive, on one panel | **predictive**, with preregistered out-of-sample tests |
| scope | the verifier side | the worker side, the verifier side and the joint model |
| decision output | a diagnostic | algorithms A2–A7 in an operator CLI (T2) |
| project spend | zero | zero for X1–X6 |

---

## 9. Claims the program will not make

Everything in §8 of the publication strategy still applies. In addition:

- the worker floor (E045, 0.052) and the verifier floor (E017, 0.0556) are **not**
  claimed to be one mechanism; their numerical closeness is a coincidence until
  a model explains it;
- leaderboard submissions are **not** treated as independent random draws of
  "agents". Provenance is modelled, not assumed away;
- oracle best-of-k coverage is **not** presented as achievable. It is an upper
  bound until H4 measures harvest;
- no result on the Verified split, which has already been seen, is called
  confirmatory.

---

## 10. Roadmap

Phases are gated by evidence, not dates. A phase starts when its predecessor's
exit gate is met.

| phase | content | exit gate |
|---|---|---|
| **S0 — charter and pilot** | This document; E045; issues | Merged on `main` |
| **S1 — freeze** | X2 preregistration; T1 ingestion with provenance | The preregistration is merged with its analysis-code digest **before** any held-out split is downloaded |
| **S2 — worker-side confirmation** | X3, X4, X5 with A1, A2, A4 | Results published, negative or not. This is the working basis for a new **Paper F: "Forecasting the value of the next coding agent"** |
| **S3 — verifier side at scale** | T5, then X6 and X7, plus #936 step 2 (X10) | E017's shape is replicated or falsified on real candidates; Paper A revised with a second instrument |
| **S4 — joint model and product** | X8, A6, A7, and T2 shipping as a diagnostic CLI | The advisor's recommendations beat its baselines on held-out tasks |
| **S5 — controlled confirmation** | X9 (#936 steps 3–5) | Calibrated predictions tested on IDKMesh's own frozen cohort (Paper B) |

### Paper portfolio after this program

| paper | question | status |
|---|---|---|
| **A** — dependence shape in a verifier panel | H1, verifier side | Under revision. S3 supplies the missing external validity |
| **F** — forecasting the value of the next coding agent (new) | H1–H3, worker side, public data | Fastest high-novelty paper: zero spend, preregistrable now |
| **B** — fixed-budget collective coding | H6 | Needs T3 and T4 and the own cohort |
| **G** — generate versus verify: budget allocation under measured dependence (new) | H4, H5 | After S3 |
| C, D, E | secondary tracks | Unchanged |

---

## 11. Maintaining this document

- When an experiment in §5 lands, update its row, §3's status column and §4
  in the same pull request.
- When a hypothesis is falsified, keep the row, mark it **falsified**, and link
  the evidence. Do not delete it.
- New targets enter only with a falsifier and an issue. Ideas without both go
  to [`RESEARCH_QUESTIONS.md`](https://github.com/MSKazemi/idkmesh/blob/main/RESEARCH_QUESTIONS.md).
