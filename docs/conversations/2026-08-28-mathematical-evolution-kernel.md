# Mathematical evolution kernel implementation pass

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner direction

The owner asked to continue development, make the mathematical and algorithmic foundation substantially more solid and intelligent, and implement the resulting mechanisms using GitHub Actions and other GitHub-native capabilities while keeping the work public in the repository.

## Audit findings

The repository already contained substantial mathematical architecture and simulation work:

- IDKGraph as a typed temporal directed hypergraph;
- multi-objective Work Unit value and graph unlock ideas;
- quality-diversity emergence experiments;
- correlated-verifier and independence-aware aggregation experiments;
- guarded self-evolution with Pareto search, simulated annealing, replicator/bandit ideas, homeostasis, and a Lyapunov-like repository potential.

The main implementation gap was not lack of formulas. It was the distance between those formulas and the live GitHub-native evolution loop.

Two concrete weaknesses were found:

1. `scripts/evolution_score.py` converted events into small direct additive deltas, so uncertainty was not represented and repeated activity could look like progress by construction.
2. `.github/workflows/evolution-loop.yml` updated state only inside an ephemeral Actions checkout and uploaded it. A later run normally began from the checked-in seed again, so the observer did not have trusted cross-iteration memory.

## Implementation

### Mathematical kernel

Added `scripts/evolution_math.py`, a deterministic standard-library-only kernel implementing:

- Beta Bayesian soft-evidence updates, posterior variance, and conservative confidence bounds;
- reliability-weighted Bayesian/log-odds vote aggregation;
- equicorrelation effective sample size for correlated evidence;
- normalized Shannon entropy;
- Jensen-Shannon divergence;
- Pareto non-dominated sorting;
- NSGA-II-style crowding distance;
- multiplicative-weights / discrete-replicator policy updates with an exploration floor;
- UCB1-style exploration allocation;
- discounted downstream graph unlock value;
- quadratic homeostatic/Lyapunov-style potential and non-increase condition.

Every algorithm family has an executable deterministic demonstration.

### Tests

Added `tests/test_evolution_math.py` covering:

- posterior movement and uncertainty reduction;
- entropy/JSD boundary cases;
- loss of effective sample size under correlation;
- correlation-aware vote aggregation;
- Pareto fronts and crowding;
- normalized multiplicative-weights updates with preserved exploration;
- UCB exploration of unseen arms;
- graph unlock ordering;
- Lyapunov/homeostatic improvement;
- deterministic demo replay.

### Versioned mathematical policy

Added `state/evolution-math-policy.json` so coefficients are data rather than hidden code constants. It contains:

- Bayesian prior/evidence parameters;
- signed event evidence hypotheses;
- homeostatic targets/scales/weights;
- UCB exploration coefficient;
- multiplicative-weights learning/exploration parameters;
- diversity thresholds;
- graph unlock decay;
- Pareto objective directions.

These values remain hypotheses and must be calibrated against delayed real outcomes.

### Evolution scorer v2

Reworked `scripts/evolution_score.py` so events produce signed soft evidence rather than additive score declarations.

The scorer now:

- migrates old v1 state into Beta beliefs if needed;
- updates posterior beliefs by dimension;
- reports posterior means and confidence bounds;
- tracks actor/event entropy;
- computes risk-adjusted scalar fitness only as a diagnostic;
- computes a homeostatic potential;
- requires both positive diagnostic delta and a Lyapunov-style condition before calling an observation a meaningful improvement;
- bounds the JSONL event ledger;
- preserves read-only/no-authority semantics.

### Evolution state v2

Upgraded `state/evolution-state.json` to a Bayesian seed containing Beta beliefs, activity counts, and homeostatic/checkpoint signals.

### Trusted cross-run Actions memory

Updated `.github/workflows/evolution-loop.yml` with a read-only checkpoint protocol.

For a trusted `main` run, the workflow:

1. queries the GitHub Actions API for the previous successful `main` evolution-loop run;
2. uses first-party `actions/download-artifact` to restore the previous checkpoint if present;
3. runs the Bayesian update;
4. uploads a new checkpoint artifact.

PR runs cannot become the source of future trusted-main state. The workflow keeps only `contents: read` and `actions: read` permissions.

This provides actual iteration-to-iteration memory while issue #35 remains unresolved and `main` remains unprotected.

### Mathematical GitHub Actions gate

Added `.github/workflows/mathematical-evolution-kernel.yml`.

It runs on relevant pushes/PRs, manual dispatch, and a weekly schedule. On Python 3.11 and 3.13 it:

- compiles the mathematical kernel and scorer;
- runs all invariant tests;
- validates state/policy JSON;
- generates the deterministic mathematical demo;
- smoke-tests the Bayesian scorer;
- publishes replayable artifacts for 30 days;
- publishes a detailed GitHub job summary.

## Safety boundary

No new merge, approval, issue-write, PR-write, secret, or repository-content write authority was granted to Actions.

The mathematical algorithms allocate evidence/experiments and produce recommendations. They do not supersede independent verification, branch protection, or human/governance integration authority.

## Next scientific step

The next useful mathematical advance is calibration rather than adding more unmeasured formulas.

Build a delayed-outcome dataset linking event/action classes, worker/adapter choices, verification structures, and maintenance policies to real outcomes such as regressions, reverts, verifier disagreement, benchmark movement, review burden, newcomer completion, security findings, and verified-useful-work latency.

Then compare models by held-out predictive calibration and use UCB/multiplicative-weights only for bounded experiments whose outcomes are recorded.
