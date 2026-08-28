# Continuation: anytime-valid sequential evidence

Date: 2026-08-28

User request: continue strengthening `MSKazemi/idkmesh` with a more solid mathematical and algorithmic background and implement the result with GitHub-native automation.

## Repository state checked first

The live `main` branch was read directly rather than inferred from repository-wide commit search. At the start of this continuation it was:

```text
523b10819abe1e88ce0207665098248ac0ed980b
Record successful Phase B2 Task 003 calibration (#201)
```

GitHub reported `main` as `protected: false` with status-check enforcement off. This remains a hard governance boundary; the new work does not increase autonomous write or integration authority.

The open PR set was also checked. Current open work covered ProjectManifest/DomainPack interfaces (#202), a guarded zero-cost compute pulse (#195), and the canonical node evidence path (#159). None implemented sequential statistical evidence under optional stopping.

An earlier repository-wide commit search surfaced commits that were not on canonical `main`; the direct branch read corrected that immediately. The branch ref is the source of truth for this implementation.

## Mathematical gap selected

The existing mathematical layer already includes:

- Bayesian evidence and lower-confidence scoring;
- correlation-aware effective sample size and Bayesian vote aggregation;
- NSGA/Pareto ranking and crowding distance;
- multiplicative weights and UCB exploration;
- entropy/Jensen-Shannon diversity;
- DAG unlock value;
- Lyapunov-style homeostatic potential;
- conjunctive live-governance guards.

The missing primitive was optional-stopping-safe sequential evaluation. Repeatedly applying ordinary fixed-horizon confidence intervals can create false evidence simply because the repository keeps observing.

## Implementation decision

Add a small dependency-free `Sequential Evidence Kernel` rather than modify the live Evolution Loop.

The kernel provides:

1. a union-Hoeffding confidence sequence using a summable time-indexed error budget;
2. paired candidate-minus-baseline sequential evaluation;
3. bounded inverse-propensity off-policy evidence;
4. Kish effective sample size for importance-weight concentration;
5. fail-closed handling when any importance ratio is clipped;
6. a hard non-compensation rule: strong statistics cannot override a failed governance guard.

A positive output is only `experiment_candidate`. It is not approval, merge authority, activation authority, or proof of causality.

## GitHub execution boundary

The companion workflow is intentionally narrow:

```text
permissions: contents: read
```

It runs only when the sequential-evidence files change (plus manual dispatch), tests Python 3.11 and 3.13, uses immutable Action SHAs already used by the repository mathematical workflows, publishes a deterministic demonstration artifact, and grants no repository mutation permission.

## Next evidence step

The implementation should be accepted only if its pull-request checks pass on the exact candidate head. Because `main` remains unprotected, this mathematical layer must not be used to justify increased autonomous repository writes.
