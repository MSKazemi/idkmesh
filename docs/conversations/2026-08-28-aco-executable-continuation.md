# Conversation record — executable ACO continuation

**Date:** 2026-08-28

## Trigger

After adding the biology-inspired ACO stigmergic task-routing proposal, the project owner asked to continue.

## Decision

Do not connect ACO directly to live GitHub task assignment yet. First convert the biological analogy into a deterministic, falsifiable simulator with simple baselines and CI.

## Added implementation

- `sim/aco_stigmergy_sim.py`
  - synthetic heterogeneous tasks and workers;
  - random, greedy, capability-only, and ACO routing;
  - evidence-backed pheromone deposits;
  - evaporation and bounded pheromone state;
  - congestion and correlated-attempt penalties;
  - explicit exploration floor;
  - JSON output and reproducible seeds.
- `sim/run_aco_sweep.py`
  - repeated-seed comparison;
  - same generated worker population per strategy for each replicate;
  - aggregate utility/cost, duplication, coverage, concentration, and neglect metrics.
- `tests/test_aco_stigmergy_sim.py`
  - deterministic replay;
  - probability normalization;
  - evaporation;
  - evidence reinforcement;
  - pheromone bounds;
  - anti-congestion/correlation behavior;
  - bounded output metrics.
- `experiments/E014-aco-stigmergic-task-routing.md`
  - predeclared question, baselines, metrics, rejection conditions, and evidence ladder.
- `.github/workflows/aco-stigmergy-sim.yml`
  - tests on Python 3.11 and 3.13;
  - JSON smoke tests for single runs and repeated-seed sweeps.

## Evidence ladder

ACO should advance only through explicit stages:

1. unit/mechanics tests;
2. repeated synthetic simulation;
3. historical repository replay;
4. advisory shadow mode;
5. bounded live experiment.

A favorable synthetic result is **not** permission for autonomous production routing.

## Safety / anti-Goodhart constraints

- Pheromone is a routing signal, not truth, reputation, or authority.
- Unverified popularity/activity must not create strong reinforcement.
- Routing never grants permissions, approves work, or bypasses verification.
- Evaporation, lower/upper bounds, explicit exploration, congestion penalties, and correlation discounts preserve alternatives and reduce herding.
- Negative experimental results should be retained and can justify rejecting ACO.

## Next experiment if PR #56 is accepted

Run E014 over many seeds and parameter combinations, then add a historical replay adapter that reads public repository task/evidence events without making changes. Only if both stages show a useful Pareto tradeoff should IDKMesh consider a metadata-only advisory recommender.
