# Results ledger

**Refs:** issue 2 (many small coding agents versus one strong model), issue 13,
issue 22, issue 30. This page advances none of them to completion.

**Purpose:** one place where every experiment record in
[`experiments/README.md`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/README.md)
is stated in a single sentence together with the *kind* of evidence behind it
and the verdict the record itself reaches, including every negative and
falsifying verdict. Each cell was written from that record's own status line,
abstract, results and decision text, not from the program summary.

## What this ledger is NOT

- It is **not** a claim that many small agents beat one strong model. No such
  result exists here. There is no real strong-model arm anywhere in this
  repository: the only real language-model *producer* run is E029, a 0.5B
  open-weight model, and it produced 0 of 60 candidates the verifier could even
  judge. Issue 2's central comparison remains unmeasured.
- It is **not** a statement that simulation results describe real agents,
  people or repositories. A `synthetic` row is evidence about a model, whatever
  its effect sizes look like.
- It is **not** independent review. Records were written by the owner and by
  owner-controlled AI tooling; the ledger summarizes them and adds no
  verification of its own beyond the structural guard test named below.
- It is **not** a substitute for the records. A one-sentence headline drops
  conditions; follow the record link before quoting a number.
- Public-observed rows (E045 to E047) analyse results that third parties
  published for agents they ran. We ran none of those agents.

## Evidence classes

Exactly one per row.

| class | meaning |
|---|---|
| `synthetic` | Outcomes are drawn from a simulator or toy model we wrote. Some parameters may have been measured elsewhere (for example from E017), but the outcomes themselves are generated. |
| `public-observed` | Execution-graded outcomes that third parties published for systems they ran; we analyse them and run no agent ourselves. |
| `real-run` | We executed real models or real programs and recorded what they actually did, on a corpus we constructed or on our frozen benchmark. A constructed corpus is not a sample of real-world work. |
| `analytic` | Derived in closed form or by a deterministic recursion with no sampling noise. Still a statement about a model, not about the world. |

## Verdicts

Exactly one per row, taken from what the record itself concludes about its own
central question or hypothesis.

| verdict | meaning |
|---|---|
| `supported` | The record's central claim held in the conditions it tested. Conditions are in the headline and the record. |
| `falsified` | The record's preregistered or stated claim failed. |
| `partially falsified` | Part of the claim held and part failed, or the record itself says it was partly falsified or only holds conditionally. |
| `inconclusive` | The record says the test could not decide the question. |
| `negative result` | The instrument or mechanism did not deliver what it was built to deliver, and the record says so. |
| `see record` | The record states no single verdict: it is a design, an exploratory pilot, or a multi-part trade-off. Read the record. |

Later records sometimes qualify earlier ones. Where a record's own text says so,
the headline names the later record. Read the chain, not one row.

## Ledger

| record | evidence class | headline result | verdict | record link |
|---|---|---|---|---|
| E011 | `synthetic` | In a one-seed smoke test on a toy five-trait landscape, constraint-guided Quality-Diversity had the best post-change mean (0.897 versus 0.658 for fixed scalar evolution), and the record states this is not statistically significant evidence. | `inconclusive` | [E011](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E011-emergence-vague-goals.md) |
| E012 | `synthetic` | With five verifiers at 0.75 accuracy, rising error correlation raises false-accept from 0.109 to 0.254 while panel disagreement falls to 0, so unanimity stops being informative, in a controlled shared-shock model that is not fitted to real reviewers. | `supported` | [E012](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E012-correlated-verification.md) |
| E013 | `synthetic` | Group-balanced voting lost to naive majority when errors were independent (0.065 versus 0.034 error) and won from correlation 0.25 upward, so independence-aware weighting can hurt; E019 later showed the win disappears when groups share task difficulty. | `supported` | [E013](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E013-independence-aware-aggregation.md) |
| E014 | `synthetic` | In a 40-seed synthetic routing sweep, ACO cut duplicate work and kept full task coverage but had 35.7 percent lower verified utility per cost than capability-only routing, and its homeostatic hybrid only reached an intermediate point without dominating either; its three sweep documents live under `experiments/results/E014-*.md`. | `partially falsified` | [E014](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E014-aco-stigmergic-task-routing.md) |
| E015 | `synthetic` | Correlation caps the effective independent panel size (even rho 0.125 caps a 21-member panel at about 10.6 at p 0.75), and the standard N_eff heuristic was found optimistic exactly where accurate verifiers have modest shared dependence; E018 later re-scoped the ceiling as specific to the shared-shock model. | `partially falsified` | [E015](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E015-verification-phase-diagram.md) |
| E016 | `real-run` | Twenty live 1-2B LLM verifiers on 72 candidates showed no discrimination above chance (0 of 20 agents significant, mean Youden J 0.049), so the experiment could not measure error correlation and no AI verifier panel has been measured here. | `negative result` | [E016](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E016-live-verifier-correlation.md) |
| E017 | `real-run` | Twenty-five programmatic partial test oracles (not AI verifiers) over a constructed 72-candidate corpus had mean pairwise error correlation 0.587 and a majority vote no better than one member (effective size 1.00), which falsifies the shared-shock shape and the N_eff heuristic on that panel. | `supported` | [E017](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E017-item-difficulty-and-quorum.md) |
| E018 | `analytic` | Recomputing E015's grid in closed form shows an item-difficulty shape predicts more panel error than shared-shock in 438 of 441 cells and makes the N_eff warning hold in every cell, while E015's accuracy-dependent ceiling turns out to be an artifact of the shared-shock shape. | `supported` | [E018](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E018-dependence-model-shape.md) |
| E019 | `synthetic` | E013's crossover at correlation 0.25 survives the change to the item-difficulty shape, but group balancing never beats naive majority at any correlation once declared groups share task difficulty, as E017 found real groups do. | `partially falsified` | [E019](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E019-group-independence-under-item-difficulty.md) |
| E020 | `real-run` | Re-analysing E017's retained votes (no new collection), neither two-parameter model predicts the unanimity floor (real 0.0556 against 0.1186 and 0.0313), the dependence shape rather than correlation decides the best quorum, and the panel's floor rests on 4 of 72 tasks. | `partially falsified` | [E020](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E020-quorum-frontier-under-measured-shape.md) |
| E021 | `synthetic` | A superlinear-susceptibility probe warned earlier than a 90 percent utilization threshold (lead 0.04) but raised two false alerts, so there is no evidence it beats the ordinary utilization threshold in this toy queue. | `negative result` | [E021](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E021-coordination-criticality.md) |
| E022 | `synthetic` | Across seven verification modes no policy dominates (independent tests maximize throughput, tests plus adversarial review minimize escaped defects), while risk-adaptive backpressure keeps the queue bounded at a final queue of 12.85 against 386 to 600 without it, all in synthetic units. | `supported` | [E022](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E022-verification-scaling-matrix.md) |
| E024 | `synthetic` | With matched budgets the Quality-Diversity archive beat random, scalar and planner arms in 100 of 100 paired seeds but only 51 of 100 against the majority-vote swarm, so the original hypothesis is partly falsified and survives only as a reliability claim (0 of 100 catastrophic seeds against 44). | `partially falsified` | [E024](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E024-matched-budget-emergence.md) |
| E025 | `synthetic` | Learned verifier weighting cut held-out error from 0.2312 to 0.0597 in a stable regime but reversed under reliability shift (0.2182 against 0.1071 for naive), so it is not a safe default and not production-ready reputation. | `partially falsified` | [E025](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E025-learned-verifier-reliability.md) |
| E026 | `synthetic` | Giving E024 a measured-parameter correlated verifier panel changed nothing (QD 0 of 100 catastrophic, ordering unchanged), and the record concludes the landscape barely transmits verifier error, so the test had little power to falsify anything. | `inconclusive` | [E026](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E026-imperfect-verifier-panel.md) |
| E027 | `synthetic` | Once an accepted defect costs something, random search collapses from 0 to 94 of 100 catastrophic seeds while the archive stays at 0 of 100, but the record bounds this because apparent quality alone separates viable from defective candidates at AUROC 0.94, so it is not evidence that diversity defeats verifier error. | `supported` | [E027](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E027-defect-propagation.md) |
| E028 | `synthetic` | With viability made invisible to the quality signal, the archive stays at 0 of 100 catastrophic seeds in 18 of 20 cells but reaches 3 of 100 under the measured panel and 62 of 100 under the unmeasured stress panel, so the claim that it never fails is falsified while its best-mean ordering survives. | `partially falsified` | [E028](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E028-latent-defect-dimension.md) |
| E029 | `real-run` | A pinned 0.5B open-weight coder model made 60 real attempts on the 10 frozen work units and produced 0 well-formed patches (56 of 60 failures were unified-diff protocol failures), so this measured diff compliance rather than coding ability and says nothing about larger models. | `negative result` | [E029](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E029-first-real-model-attempts.md) |
| E030 | `synthetic` | Switching to a future goal the arms do not hold costs the archive at most 4.4 percent of its lead and leaves it at 0 of 100 catastrophic seeds, while the majority-vote swarm loses its whole lead and goes negative; E033 later showed that 95.6 percent retention was one favourable goal. | `supported` | [E030](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E030-supplied-goal-membership.md) |
| E031 | `synthetic` | A learned goal filter rescues the consensus swarm only if it starts learning after the goal moves (catastrophic seeds 38 to 39 down to 20 to 22), whereas learning from generation 0 roughly doubles its failures and spreading beliefs backfires when the goal leaves the supplied set. | `supported` | [E031](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E031-learned-goal-filter.md) |
| E032 | `synthetic` | At a fixed budget the record returns a split verdict on issue 13's first hypothesis: diminishing returns appear for three of five arms and negative returns appear, but not in the arm or along the axis the obvious unmatched sweep suggests. | `partially falsified` | [E032](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E032-population-scaling.md) |
| E033 | `synthetic` | At a matched change size the archive's rescue decays from 78.3 percent retention at distance 0.21 to about 5 percent at 0.35, so E030's 95.6 percent was a favourable draw and the supportable number is a rate rather than a radius. | `partially falsified` | [E033](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E033-goal-distance.md) |
| E034 | `synthetic` | At a fixed distance the archive's lead runs from -4.894 to +4.471 and is negative for 24.2 percent of directions, and the viability-floor mechanism the record preregistered to explain it was falsified by its own test. | `falsified` | [E034](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E034-goal-direction.md) |
| E035 | `synthetic` | Repeating the direction ladder at two more distances shows direction dominating distance holds, the spread does not grow with distance, and the simplicity trait E034 leaned on reverses sign, so two E034 claims were withdrawn. | `partially falsified` | [E035](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E035-direction-across-shells.md) |
| E036 | `synthetic` | The archive was never strictly beaten by an optimising adversary in 48 cells, but the preregistered reason to expect failure was wrong: two equal-accuracy panels differ only in correlation and give 0 versus 58 catastrophic seeds in 100, so correlation is the attack surface. | `partially falsified` | [E036](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E036-adversarial-contributors.md) |
| E037 | `synthetic` | The directional structure from E030 to E035 survives a panel that gets 45 percent of its decisions wrong, while the archive's absolute lead is panel-dependent (about 40 percent larger on stress) and the mechanism for that is unknown. | `supported` | [E037](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E037-ladder-under-panels.md) |
| E038 | `synthetic` | The preregistered prediction held 4 of 4: an arm-blind gate is not arm-neutral, because the share of an arm's errors that are false accepts runs from 0.014 to 0.605 with its base rate of proposing viable work. | `supported` | [E038](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E038-symmetric-gate.md) |
| E039 | `synthetic` | Of five preregistered clauses 3 held and 2 were falsified: the panel reads an artifact through one bit, giving the blind spot an address baits the optimising arms, coordination did not pay against it, and the archive was not the most exposed arm. | `partially falsified` | [E039](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E039-content-addressed-blind-spot.md) |
| E040 | `synthetic` | The preregistered expectation of a correlation knee was wrong (advantage is proportional to retained independence in 17 of 18 curves), the grid can never show the diverse arm losing, and so it cannot falsify issue 13's hypothesis 2, which stays open. | `negative result` | [E040](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E040-diversity-correlation-threshold.md) |
| E041 | `synthetic` | The R1 lab's verifier_error_correlation is a within-task strictness shock on a single verifier rather than verifier correlation, so the lab has no verifier panel and cannot be cited as evidence about verifier independence. | `negative result` | [E041](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E041-verifier-strictness-shock.md) |
| E042 | `synthetic` | E040's hedge that its slopes were the optimistic end points the wrong way (slopes rise in 16 of 18 curves) and its proportionality holds in only 8 of 18 curves under the item-difficulty shape, so the hedge is withdrawn. | `falsified` | [E042](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E042-worker-dependence-shape.md) |
| E043 | `synthetic` | Billed per verifier read, a panel never beat a single verifier (0 of 80 cells), and the one unbilled advantage appears only at k=5 with correlation 0 and vanishes at a smaller sample, in an invented cost model. | `negative result` | [E043](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E043-panel-frontier.md) |
| E044 | `analytic` | A logistic review-capacity governor has the analytic interior fixed point L* = K + tau ln(A/S - 1) and creates negative feedback on backlog, but a sharp governor (tau 0.1) is locally unstable and K=8, tau=2 remain uncalibrated bootstrap values. | `supported` | [E044](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E044-review-capacity-governor.md) |
| E045 | `public-observed` | Across 169 public SWE-bench Verified systems pairwise success correlation is 0.4763, 26 of 500 tasks are solved by none, and independence overstates 10-agent oracle coverage (0.852 measured against 0.9997), as an exploratory non-confirmatory pilot. | `see record` | [E045](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E045-public-agent-dependence-pilot.md) |
| E046 | `public-observed` | On the held-out SWE-bench Lite split a beta-binomial per-item model forecast team coverage far better than Kish or shared-shock models and all three registered hypotheses passed, but H2 and H3 failed or lost significance in an unregistered check on the 207 Lite tasks outside Verified. | `supported` | [E046](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E046-agent-value-forecast.md) |
| E047 | `public-observed` | After keeping one submission per model the beta-binomial advantage holds on Verified and Lite, and choosing agents one per model organisation never beat choosing by measured complementarity, in an exploratory analysis of already-seen splits. | `supported` | [E047](https://github.com/MSKazemi/idkmesh/blob/main/experiments/E047-provenance-aware-agent-value.md) |
| PHY-0 | `synthetic` | In a synthetic abrupt-shift fixture Physarum routing reached 0.905 post-shift success against 0.651 for Thompson at about 15 percent more route burden, which the record calls a positive mechanism result and not a reason to deploy. | `supported` | [PHY-0](https://github.com/MSKazemi/idkmesh/blob/main/experiments/PHY-0-physarum-compute-routing.md) |
| PHY-0A | `synthetic` | With no environment shift Thompson routing had the highest completion (0.9699) at near-zero extra burden while Physarum was 0.53 points lower at about 6.1 percent more burden, so the control does not support a universal Physarum advantage. | `negative result` | [PHY-0A](https://github.com/MSKazemi/idkmesh/blob/main/experiments/PHY-0A-physarum-stationary-routing.md) |
| PHY-1 | `synthetic` | Explicit multipath failover had higher synthetic success than Physarum in all 16 topology and environment cells and a burden-matched frontier gave a simpler baseline the same advantage, so the record recommends rejecting promotion to a dry-run planner. | `negative result` | [PHY-1](https://github.com/MSKazemi/idkmesh/blob/main/experiments/PHY-1-stress-matrix.md) |
| AVE-0 | `synthetic` | In a synthetic reference sweep the combined AVE controller cut escaped defects by about 45 percent and high-risk escapes by about 94 percent against capability-only routing but cost 43 percent more review and had about 48 percent lower verified utility per cost, and the record says it is deliberately not an AVE-wins claim. | `see record` | [AVE-0](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-0-adaptive-verification-ecology.md) |
| AVE-1 ablation | `synthetic` | Component ablation found verifier-family diversity the strongest broad defect-escape reducer and risk adaptation the strongest high-risk reducer, while probe-derived positive trust worsened escapes (21.95 to 43.25 one-sided) and entropy exploration showed no consistent safety gain. | `partially falsified` | [AVE-1 ablation](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-1-adaptive-verification-ecology-ablation.md) |
| AVE-1 targeted | `synthetic` | This record is a study design for a smaller core policy without probe-derived positive trust and states no result of its own; its results are in the AVE-2 targeted record. | `see record` | [AVE-1 targeted](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-1-targeted-core-policy.md) |
| AVE-2 targeted | `synthetic` | The smaller AVE-core is a trade-off rather than a universal winner (verifier diversity alone had the fewest ordinary escapes, AVE-core the fewest high-risk escapes and duplicates, and full AVE edged it in the scarce-review case). | `see record` | [AVE-2 targeted](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-2-adaptive-verification-ecology-targeted.md) |
| AVE-2 adversarial | `synthetic` | This record specifies the adversarial and non-stationary matrix and its decision rule and reports no result of its own; AVE-3 reports the stress grid. | `see record` | [AVE-2 adversarial](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-2-adversarial-matrix.md) |
| AVE-3 | `synthetic` | Under a selective adversarial verifier full AVE was worse than AVE-core (escape rate 0.1372 against 0.1220) and AVE-core's ordinary escape rate was worse than capability-only, so probe success must never create positive verifier authority and live activation is not justified. | `partially falsified` | [AVE-3](https://github.com/MSKazemi/idkmesh/blob/main/experiments/AVE-3-adaptive-verification-ecology-stress.md) |

## Not in the ledger

- **E023** is a preregistration
  (`experiments/E023-first-review-latency-recurrence.json`), not a written
  record, so it has no result to state.
- **E001 to E010** have no artifact in this repository.
- **The E014 sweep documents** (`experiments/results/E014-reference-sweep.md`,
  `E014-parameter-pareto.md`, `E014-homeostatic-hybrid.md`) are summarized in the
  E014 row rather than listed separately, because they are result documents of
  that one record.
- **Preregistrations and amendments** under `docs/research/` (for example the
  agent-value forecast and verifier-panel external-validity registrations) are
  frozen analysis plans. They are not experiment records and are not ledgered
  here.

## Reading the ledger honestly

- Most rows are `synthetic`. The few rows that touch something real are E016,
  E017, E020 and E029 (we ran them) and E045 to E047 (third-party data we
  analysed). Of those, only E029 involves a language model producing candidate
  patches, and it is negative.
- The real-data rows do not contain one coding-agent corpus that compares small
  agents with a strong model under equal budgets, so issue 2's comparison is
  unmeasured. The R1 real-corpus gate in
  [R1 Real-Corpus Readiness Gate](R1_CORPUS_READINESS.md) reports blocked for the
  same underlying reason.
- A `supported` verdict on a `synthetic` row means the mechanism behaved as the
  record predicted inside its own model. It is not a measurement of any real
  agent population.

## Guard

`tests/test_results_ledger.py` reads this file and
[`experiments/README.md`](https://github.com/MSKazemi/idkmesh/blob/main/experiments/README.md)
and fails when an indexed record has no ledger row, has two, carries an evidence
class or verdict outside the sets above, or when a ledger row points at a record
the experiments index does not list. It checks structure only. It cannot check
that a headline is faithful to its record.
