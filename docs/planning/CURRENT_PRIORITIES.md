# IDKMesh Current Priorities

**Snapshot date:** 2026-08-28  
**Snapshot main:** `af77440ba31aa9b53035818db02b09b9286401c7`

This file records the highest-leverage next actions after inspecting current `main`, the live open-PR queue, issue state, ACE observatory state, recent runtime/evaluator evidence, and repository protection metadata.

IDKMesh has crossed a major boundary: the repository is no longer mainly missing internal mechanisms. It now has executable WorkUnit/ResultManifest contracts, an accepted-runtime worker candidate, independent evaluator control, real single- and two-attempt evidence, mixed success/failure replay, a non-selecting Evidence Report, deterministic IDKGraph repository observability, ACE lineage/capacity machinery, and a read-only mathematical evolution observatory.

The scarce resources are now:

1. externally enforced integration safety;
2. genuinely independent human/external witness evidence;
3. real held-out task data;
4. reviewer/community attention.

The repository should therefore **consolidate and collect reality-facing evidence before adding more autonomous machinery**.

---

## Priority rule

Rank work by:

```text
Priority(a) ~=
  ExpectedVerifiedDelta(a)
  * DependencyUnlock(a)
  * InformationGain(a)
  * CommunityMultiplier(a)
  -------------------------------------------------
  1 + ReviewCost(a) + CoordinationNoise(a) + SafetyRisk(a)
```

Hard non-compensation rule:

```text
internal evidence cannot compensate for
zero integration protection,
zero independent witness,
or zero real-task evidence.
```

Prefer finishing, verifying, integrating, measuring, or simplifying existing work over creating new theory, controllers, queues, or protocols.

---

# P0 — Protect the real integration boundary

**Issue:** #35

Public GitHub branch metadata still reports `main` as **unprotected**, with required-status enforcement off.

Repository-side safety work has already landed. The remaining blocker is external GitHub repository configuration.

Required admin outcome:

- require pull-request-based integration for protected structural/code/governance changes;
- block ordinary force-push and deletion;
- require stable relevant checks;
- preserve a narrow auditable recovery path;
- avoid broad automation bypass;
- preserve the invariant that no autonomous actor proposes, approves, and merges the same protected change by itself.

Until this is externally enforced:

- keep stronger autonomous actuation disabled;
- do not treat workflow instructions as a protection boundary;
- keep ACE/evolution machinery fail-closed or advisory where protection is required.

This remains the highest safety dependency because repository code cannot configure or substitute for the missing GitHub ruleset.

---

# P0 — Obtain independent human review of the canonical worker

**PR:** #91  
**Runtime acceptance:** #37  
**Product:** #16

PR #91 is currently the **only open pull request** and is intentionally draft.

Exact accepted-runtime worker head:

`520ad2c9aa5825476de4957da4702d6823f4edb3`

Already evidenced:

- exact-head Node CI and Phase 0 schema checks;
- controlled Docker positive path;
- negative A–E2 fail-closed matrix;
- immutable image/source/provenance evidence;
- real node -> independent verifier proof;
- real two-attempt success/success evidence;
- real success/failure peer-isolation evidence;
- non-selecting report/replay;
- worker acceptance authority remains false.

The remaining blocker is deliberately social/governance, not another automated test:

> a genuinely separate human/reviewer must inspect the exact-head evidence before the worker is treated as integrated canonical implementation.

Do not manufacture independence by having another project automation approve the same work.

If the #91 head changes, re-freeze and rerun the evidence that is bound to that exact SHA.

---

# P0 — Finish the v0.1 adapter boundary after #91 review

**Core issues:** #4, #16

The two-attempt control plane has already demonstrated:

```text
real worker success + real worker success
 -> independent verification
 -> non-selecting Evidence Report
 -> exact replay
```

and:

```text
real worker success + real worker failure
 -> surviving peer still independently verified
 -> explicit worker_error retained
 -> non-selecting mixed-outcome report
 -> exact replay
```

The next product step is therefore narrow:

1. after #91's separate review, place `idkmesh-node` behind the existing worker-adapter boundary;
2. keep coordinator core independent of node internals;
3. confirm the direct-adapter semantic result remains replayable;
4. add **one deliberately trivial heterogeneous real adapter** without changing coordinator internals;
5. only after that boundary is stable consider widening fan-out toward 3–5 attempts.

Do not add another WorkUnit, EvaluatorPlan, verifier, coordinator, or report protocol.

---

# P1 — Execute the first five frozen benchmark tasks

**Issue:** #5  
**Research corpus:** #70  
**Diversity question:** #30 / #2

The first five Phase B2 benchmark task definitions have now been frozen pre-outcome on `main` (merged work from #134), covering multiple task families rather than repeatedly exercising one smoke task.

The next credibility step is **execution, not more benchmark design**.

For each frozen task, retain:

- immutable source revision;
- canonical WorkUnit;
- evaluator-owned EvaluatorPlan/control;
- worker ResultManifest and candidate bundle;
- independent VerificationResult;
- negative/failed attempts, not only successes;
- non-selecting run/report/replay evidence where multi-attempt execution is used;
- task family/difficulty metadata;
- compute/wall-time/human-attention fields when they are actually known.

Gate tasks 6–10 on the first five replaying cleanly and on available verification/reviewer capacity.

The first five are a product/benchmark milestone; they are **not yet enough** to answer the broader diversity research question universally.

---

# P1 — Run the first real diversity experiment without changing the analysis after outcomes

**Issue:** #70  
**Research question:** #30 / #2

The existing R1 machinery already distinguishes synthetic mechanism evidence from real coding evidence and can replay independently verified ResultManifest/VerificationResult records.

Current real two-attempt smoke evidence shows reliable orchestration but not useful diversity: the two normal attempts produced the same patch bytes/digest. That is a replication/control-plane result, not evidence that diversity helps.

The first real decision gate should therefore remain prospectively fixed:

```text
N = 2 replication baseline
vs
N = 2 prospectively distinct structural signatures
```

under equal attempt budgets on frozen held-out WorkUnits.

Primary outcome:

- run the already-merged `r1_replay` rules unchanged;
- classify success delta as `helps`, `hurts`, or `uncertain`;
- measure pairwise failure correlation rather than assuming independence;
- retain exclusions, inconclusive verification, failed candidates, and negative findings;
- report per-signature marginal quality so "diversity" is not confused with simply choosing a stronger worker.

A useful first real research target remains at least ~20 eligible work units, grown from the first five only after the evidence pipeline is stable.

Do not justify 3–5 worker diversity fan-out merely because two-worker execution is technically reliable.

---

# P1 — Keep ACE in First-Contact / HOLD mode until a real external descendant exists

**Live observatory:** #109  
**Cohort seeds:** #24–#28  
**Lineage:** #48

Latest live ACE Bootstrap Cohort state at this snapshot:

- trusted seeds: 5;
- claimed seeds: 0;
- seeds with candidate PRs: 0;
- verified descendant PRs: 0;
- distinct external participants: 0;
- seed reproduction ratio: `0.000`;
- ACE capacity: approximately `0.915`;
- recommendation: `HOLD_COHORT_1`.

This is important: review capacity has recovered, but **capacity is not reproduction evidence**.

Do not create Cohort 2 merely because capacity is high.

The next useful ACE/community outcomes are reality-facing:

1. make open contribution/review surfaces truthful and discoverable;
2. obtain one real external claim/candidate/review/descendant path;
3. record causal parent -> seed -> descendant evidence under the existing lineage contract;
4. measure reviewer attention consumed by that descendant;
5. only then reconsider another generation.

Optimize:

```text
verified useful external descendants
------------------------------------
reviewer + maintainer attention
```

not activity counts, stars, comments, issue count, or synthetic self-interaction.

---

# P1 — Use the observatories; do not immediately add another self-rewrite layer

**IDKGraph P0:** #20 — completed  
**Evolution observatory:** merged #143/#144/#148 lineage

Deterministic IDKGraph repository extraction/health/replay is now integrated, including stable identity mapping, link integrity, WorkUnit cycle checks, typed repository mapping, health reporting, and replayable outputs.

The mathematical evolution layer is also now live in read-only/advisory form with portfolio scoring, Bayesian history, Pareto/diversity treatment, dependency unlock, and fail-closed hard-gate behavior.

The correct next use is to **consume those observations to guide bounded decisions**, not add another controller.

Rules:

- observatory output is decision support, not correctness proof;
- health metrics must not silently become merge authority;
- Bayesian/Pareto scores cannot override hard safety or witness gates;
- retain only the minimum durable evolution artifacts needed for replay/provenance;
- prefer fixing a measured defect over increasing observatory sophistication.

---

# P2 — Scale only after the current boundaries produce evidence

Defer until the P0/P1 gates above move:

- 3–5 worker fan-out beyond the stable two-adapter boundary;
- larger held-out corpora beyond the first validated cohort;
- volunteer/distributed compute expansion;
- broader external protocol adapters;
- advanced scheduler/evolutionary worker selection;
- stronger autonomous repository mutation.

These become more useful after real benchmark, witness, and protection evidence exists.

---

# What not to do now

Avoid spending primary project attention on:

- another autonomous controller or agent queue;
- another ledger/capacity model;
- another WorkUnit/result/evaluator/orchestrator protocol;
- more grand architecture without an executable decision implication;
- Cohort 2 without external descendant evidence;
- claims that many agents/diversity outperform replication before the real corpus exists;
- automatic merge/self-approval;
- blockchain/token mechanisms;
- million-node/global-scheduler claims;
- treating observatory scores, CI green status, or worker success as independent acceptance.

---

# Recommended execution order

```text
1. Protect main in GitHub settings (#35)                 [external/admin]
        |
2. Separate human review of exact #91 evidence          [external witness]
        |
3. Direct idkmesh-node adapter behind existing boundary
        |
4. One trivial heterogeneous real adapter
        |
5. Execute + replay the first five frozen benchmark tasks
        |
6. Grow a held-out real corpus for #70/#30
        |
7. Measure diversity vs replication under fixed budgets
        |
8. Feed measured evidence into scheduling/evolution policy
```

In parallel, keep ACE in `HOLD_COHORT_1` and prioritize one genuine external contribution lineage over additional generated activity.

---

# Current project bottleneck

The repository is no longer bottlenecked by lack of ideas, schemas, algorithms, or internal automation.

The bottleneck is the membrane between the internally coherent mesh and independent reality:

```text
unprotected integration boundary
          +
canonical worker awaiting separate human review
          +
insufficient held-out real-task corpus
          +
zero external ACE descendants
          =
current limiting state
```

The next strong iteration should increase **external trust or real measured evidence per unit reviewer attention**, not repository complexity.

See also:

- `docs/planning/REPOSITORY_IMPROVEMENT_LOOP.md`
- `ITERATION_MODEL.md`
- `EVOLUTION.md`
- `ROADMAP.md`
