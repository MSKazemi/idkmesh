# Project continuation — refresh current priorities after evidence convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner request

Continue improving the public repository.

## Repository state inspected

The live repository had advanced far beyond the older `docs/planning/CURRENT_PRIORITIES.md` snapshot.

Observed facts at this continuation point:

- `main` at inspection: `af77440ba31aa9b53035818db02b09b9286401c7`;
- public GitHub metadata still reported `main` as unprotected and required-status enforcement off;
- issue #35 remained the external/admin P0 protection gate;
- PR #91 was the only open pull request and remained intentionally draft pending genuinely separate human review of exact-head runtime evidence;
- issue #4 already recorded real success/success and real success/failure two-attempt evidence with exact replay;
- issue #5 already had the real verifier/report/replay substrate, and the first five Phase B2 benchmark definitions had subsequently been frozen on `main` through merged #134;
- issue #20 IDKGraph P0 was closed completed;
- the read-only mathematical repository-evolution observatory had advanced through merged #143/#144/#148;
- ACE Bootstrap Cohort Observatory #109 reported capacity approximately `0.915` but zero claims, zero candidate PRs, zero verified descendants, and zero distinct external participants, with recommendation `HOLD_COHORT_1`.

## Diagnosis

The repository is no longer mainly bottlenecked by missing mechanisms.

The limiting state is now:

```text
unprotected integration boundary
          +
canonical worker awaiting separate human review
          +
insufficient held-out real-task corpus
          +
zero external ACE descendants
```

This means the correct project posture is **convergence + external evidence**, not another controller, protocol, queue, or large theory layer.

## Bounded action

Refresh `docs/planning/CURRENT_PRIORITIES.md` so it stops directing contributors toward already-completed or superseded work.

The refreshed ordering is:

1. protect `main` in GitHub settings (#35);
2. obtain separate human review of exact #91 evidence;
3. put the real node behind the existing adapter boundary;
4. add one trivial heterogeneous real adapter;
5. execute/replay the first five frozen benchmark tasks;
6. grow the held-out real corpus for #70/#30;
7. measure diversity vs replication under fixed budgets;
8. only then feed real measurements into scheduler/evolution policy.

In parallel, ACE remains `HOLD_COHORT_1`: recovered review capacity is not reproduction evidence.

## Preserved invariants

- proposal is not proof;
- CI success is not independent approval;
- worker success is not acceptance;
- observatory scores are decision support, not merge authority;
- no autonomous actor should propose, approve, and merge the same protected change;
- real negative/inconclusive evidence must be retained;
- new complexity should not outrun verification and reviewer capacity.

## Community impact

A current priority map reduces contributor misdirection and duplicate implementation. Newcomers and agents should now see that the highest-value work is no longer inventing mechanisms, but crossing the remaining protection, witness, benchmark, and external-community evidence gates.
