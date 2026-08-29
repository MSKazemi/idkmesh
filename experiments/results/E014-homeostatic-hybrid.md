# E014 — Homeostatic Stigmergy reference result

**Source:** GitHub Actions run `33182701273`, job `98887690954`, Python 3.11.16  
**Configuration:** 40 seeds, 24 workers, 50 epochs.

This is a **synthetic result**, not evidence about real open-source contributors.

## Mean results

| Strategy | Verified utility / cost | Duplicate rate | Task coverage | Max selection share |
| --- | ---: | ---: | ---: | ---: |
| fixed ACO | 0.5584 | 0.1551 | 8.000 | 0.1944 |
| capability-only | 0.8690 | 0.4281 | 4.825 | 0.3833 |
| homeostatic hybrid | 0.6754 | 0.2796 | 7.850 | 0.2515 |

## What changed

Relative to fixed ACO, Homeostatic Stigmergy produced about **20.9% higher verified utility per cost**. The price was about **80.3% more duplicate work**, **29.4% more concentration**, and a small **1.9% decrease in task coverage**.

Relative to capability-only routing, the hybrid produced about **22.3% lower verified utility per cost**, but also about **34.7% less duplicate work**, **34.4% less selection concentration**, and about **62.7% more task coverage**.

## Interpretation

This is a promising intermediate tradeoff, not a winner-takes-all result.

The hybrid appears to do what the biological/control hypothesis intended:

```text
capability exploitation
        +
evidence-backed stigmergic memory
        +
density-dependent negative feedback
        =
an intermediate operating point
```

It moves substantially toward capability-only efficiency while preserving much more ecological/task diversity than capability-only routing.

However, it does **not** dominate either simpler mechanism:

- capability-only remains better on immediate utility efficiency;
- fixed ACO remains better on duplication and concentration;
- the hybrid therefore belongs on a Pareto frontier rather than replacing the baselines outright.

## Why this matters for IDKMesh

A self-evolving system should not optimize one scalar objective until everything concentrates on one path. Nor should it preserve diversity so strongly that useful exploitation is unnecessarily sacrificed.

The current evidence suggests a more general control principle:

> **Use strong local exploitation while capacity is healthy; increase diversity and anti-herding pressure as duplication, concentration, or review load approaches unsafe levels.**

That principle can apply beyond task routing to:

- community Growth Seed generation;
- verifier allocation;
- agent/model diversity;
- experiment portfolio selection;
- repository restructuring proposals;
- compute scheduling.

## Evidence gate

Do **not** connect this algorithm to live repository task assignment yet.

Next evidence should be:

1. sensitivity analysis of the homeostatic controller itself;
2. historical repository replay using real issue/PR/evidence events;
3. compare recommendations against simpler baselines without taking actions;
4. only then consider advisory shadow mode.

A favorable synthetic result is not permission for autonomous routing.

## Related

- `docs/algorithms/HOMEOSTATIC_STIGMERGY_ROUTING.md`
- `docs/algorithms/ACO_STIGMERGIC_TASK_ROUTING.md`
- `sim/homeostatic_stigmergy_sim.py`
- `experiments/results/E014-reference-sweep.md`
- `experiments/results/E014-parameter-pareto.md`
