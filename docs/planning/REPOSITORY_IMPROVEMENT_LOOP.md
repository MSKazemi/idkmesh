# IDKMesh Repository Improvement Loop

**Status:** working operating contract  
**Date:** 2026-08-28

This document makes explicit how IDKMesh should improve itself from one repository iteration to the next.

The repository already has many ideas. The default strategy is therefore **convergence before expansion**: finish, verify, integrate, measure, and only then create more theory or automation.

## 1. What an iteration means

An **iteration** is not a commit, issue, pull request, or GitHub event by itself.

An iteration is a bounded state transition:

```text
observe current state
 -> identify the dominant bottleneck
 -> choose one bounded intervention
 -> implement as a reviewable proposal
 -> verify independently where appropriate
 -> integrate or reject
 -> measure the outcome
 -> update project memory and priorities
```

A GitHub event is an observation or action inside an iteration. It counts as improvement only when there is evidence that the project state became better.

## 2. What “better” means

IDKMesh should treat improvement as a multi-objective vector rather than one scalar target.

A candidate change should improve one or more of these dimensions without violating hard constraints or causing unacceptable regression elsewhere:

- **verified useful capability** — more real tasks can be completed correctly;
- **verification strength** — candidate claims are easier to test independently;
- **safety** — smaller authority, stronger isolation, better integration guards;
- **reproducibility** — results can be replayed from recorded inputs and versions;
- **community accessibility** — newcomers can understand, claim, complete, and review bounded work;
- **maintainability** — less ambiguity, duplication, structural debt, and hidden coupling;
- **interoperability** — clearer contracts between replaceable workers/tools;
- **evidence quality** — decisions depend more on observable outcomes and less on assumptions;
- **review scalability** — useful throughput rises without overwhelming scarce human attention;
- **community reproduction** — useful contributions create additional useful contributors/contributions;
- **research value** — uncertainty is reduced, including through negative results.

Important penalties include:

- new complexity;
- reviewer/maintainer attention;
- operational cost;
- security risk;
- coordination overhead;
- protocol duplication;
- irreversible or hard-to-rollback change.

The working north star remains:

```text
verified useful improvement
---------------------------------------
human attention + compute + complexity
```

This is a guide, not a permanent single objective. Hard safety/governance constraints and Pareto trade-offs take precedence.

## 3. How candidate work is ranked

Each repository review should begin with the current state of:

- `main` and repository protections;
- open pull requests and their verification state;
- blocking issues/dependencies;
- CI/workflow results;
- canonical schemas/protocols;
- product milestone state;
- verification capacity;
- repository structural health;
- ACE/community capacity and newcomer friction;
- outstanding research assumptions.

Then rank candidate actions approximately by:

```text
Priority(a) =
    expected_verified_value(a)
  * evidence_confidence(a)
  * dependency_unlock(a)
  * community_leverage(a)
  * reversibility(a)
  -------------------------------------------------
    1
  + review_attention(a)
  + implementation_complexity(a)
  + coordination_cost(a)
  + safety_risk(a)
```

This score is never allowed to override hard invariants.

### Hard invariants

At minimum:

1. proposal is not proof;
2. popularity/activity is not correctness evidence;
3. generation must not outrun verification capacity;
4. one autonomous actor must not propose, approve, and merge its own protected change;
5. untrusted issue/PR/comment text must not become executable instructions merely because it appears on GitHub;
6. no new competing canonical Work Unit/Result/Evidence protocol without explicit migration evidence;
7. stronger autonomous write authority requires stronger external GitHub guards first;
8. prefer reversible, bounded experiments over irreversible structural bets;
9. preserve negative results and provenance;
10. zero project-funded compute spend remains a project constraint unless governance explicitly changes it.

## 4. The default order of improvement

When several useful actions are available, use this order unless current evidence justifies a different one:

### Gate A — Safety and integration boundary

Protect canonical state and make the acceptance path enforceable.

Current example: Issue #35 before stronger self-writing automation.

### Gate B — Finish canonical executable contracts

Prefer one working path over several partially compatible paths.

Current example: synchronize, runtime-test, independently review, and integrate the canonical local node path / Issue #37; retire superseded protocol paths afterward.

### Gate C — Complete candidate -> evidence separation

A worker result is not accepted evidence by itself.

Current example: integrate independent evaluator/verifier evidence, then build the multi-worker runner.

### Gate D — Complete the smallest end-to-end product loop

Target:

```text
bounded Work Unit
 -> isolated candidates
 -> independent verification
 -> Evidence Report
 -> human integration decision
 -> replayable run
```

Do this before remote federation, large compute markets, or elaborate orchestration.

### Gate E — Make the repository observable before making it self-writing

Merge deterministic, read/proposal-first observatories before enabling actuators.

Then unify repository structure, GitHub collaboration, verification, and community-capacity evidence in the IDKGraph loop instead of maintaining separate conflicting controllers.

### Gate F — Convert community activity into descendant evidence

ACE should learn from:

```text
parent -> seed -> claim -> candidate -> verified descendant
```

rather than raw issue/comment/commit volume.

### Gate G — Produce one reproducible flagship result

Use the executable runner + verifier to answer a bounded scientific question such as:

> Under a fixed budget, when does useful diversity plus independent verification outperform simple homogeneous replication?

A real reproducible result should have higher priority than another grand architecture document.

### Gate H — Scale only after evidence

Only after the local loop works should IDKMesh spend major effort on remote nodes, decentralized state, larger agent populations, economic incentives, or internet-scale claims.

## 5. Default repository-improvement behavior

For each substantial IDKMesh collaboration turn, the default behavior should be:

1. **Inspect before proposing.** Read the current repository, recent commits, open PRs/issues, and relevant canonical documents.
2. **Find the bottleneck, not merely an interesting idea.** Prefer work that unlocks existing blocked value.
3. **Prefer integration over proliferation.** Merge/repair/simplify compatible work before creating parallel mechanisms.
4. **Choose one primary outcome.** Keep the iteration bounded enough to review and roll back.
5. **Use normal GitHub review boundaries.** Prefer a branch + pull request for substantive changes rather than direct mutation of `main`.
6. **Add tests/evidence with implementation.** A new mechanism without a way to falsify it is incomplete.
7. **Separate observation, recommendation, execution, verification, and integration authority.** Do not collapse these roles for convenience.
8. **Record the reasoning in durable project artifacts.** Distill useful project conversations into planning, decisions, findings, issues, experiments, or conversation records.
9. **Update priorities after evidence changes.** Do not keep following an obsolete plan because it was once written down.
10. **Create contributor surfaces.** When possible, leave behind a bounded task another person can understand and verify without private context.

## 6. When not to add something

Do **not** add a new algorithm, subsystem, document family, workflow, agent, or protocol merely because it is intellectually interesting.

First ask:

1. What current bottleneck does it remove?
2. What existing artifact should it integrate with or replace?
3. What is the smallest falsifiable experiment?
4. What is the verification path?
5. What reviewer attention will it consume?
6. What can be deleted or simplified if it succeeds?
7. Can an external contributor understand the new surface?
8. Is there a lower-complexity open-source component we should reuse?

If those questions do not have good answers, the default is to defer the idea and keep it as a research question rather than implementation work.

## 7. Current improvement focus

As of 2026-08-28, the repository is not bottlenecked by a shortage of theory.

The dominant improvement direction is:

```text
protect canonical integration
 -> finish canonical local execution
 -> finish independent evidence/verification
 -> complete the local Verified Swarm Runner
 -> unify observability/evolution evidence
 -> measure ACE descendant value
 -> publish one reproducible flagship experiment
 -> learn from the outcome
```

This means several kinds of work should usually wait:

- additional competing Work Unit/result protocols;
- stronger autonomous GitHub write/merge behavior before #35;
- new large architecture layers without executable consequences;
- blockchain/token infrastructure;
- global scheduler implementation;
- large Growth Seed expansion without measured capacity;
- internet-scale claims before local and small-network evidence.

See [`CURRENT_PRIORITIES.md`](CURRENT_PRIORITIES.md) and [`EXECUTION_TARGET_GRAPH.md`](EXECUTION_TARGET_GRAPH.md) for the live backlog and dependency view.

## 8. Definition of a successful repository iteration

A successful iteration should leave behind most of the following:

- a clearly stated before-state and bottleneck;
- a bounded change or experiment;
- tests/verification evidence;
- explicit risk/rollback path;
- less ambiguity or one newly demonstrated capability;
- updated issue/PR relationships;
- durable provenance/reasoning;
- a measurable outcome to inspect later;
- ideally, a new bounded contribution opportunity for someone else.

The key test is simple:

> **After this iteration, is IDKMesh more able to produce independently verified useful work with less fragile dependence on one maintainer or one agent?**

If the answer is unclear, the iteration should be treated as an experiment, not automatically as progress.
