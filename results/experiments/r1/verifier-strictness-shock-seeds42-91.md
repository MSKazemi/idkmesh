# R1 verifier dependence — a within-task strictness shock

Arm `structural_diversity`, 50 seeds x 300 tasks per cell.

## What reads a candidate

- verifiers per candidate: [1]
- arms with one verifier: bandit_selected, identical_replication, seed_only, single_deterministic, structural_diversity
- arms with a pool: diverse_random_verifiers

## The shock is invisible in the marginals

| rho_v | P(accept \| good) | P(accept \| bad) | corr(accept_0, accept_1) | P(good accepted \| a bad one was) |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.9695 | 0.0298 | 0.1576 | 0.9657 |
| 0.25 | 0.9702 | 0.0301 | 0.1687 | 0.9819 |
| 0.50 | 0.9705 | 0.0294 | 0.1734 | 0.9805 |
| 0.75 | 0.9682 | 0.0297 | 0.2208 | 0.9895 |
| 1.00 | 0.9707 | 0.0321 | 0.2318 | 1.0000 |

## At rho_v = 1 the task is solvable in closed form

| metric | predicted | observed | absolute error |
| --- | ---: | ---: | ---: |
| abstention_rate | 0.1110 | 0.1101 | 0.0010 |
| false_acceptance_rate | 0.0116 | 0.0120 | 0.0004 |
| verified_success_rate | 0.8774 | 0.8779 | 0.0005 |

## Swarm size does not buy the penalty back

| N | verified at rho_v=0 | verified at rho_v=1 | penalty | 95% CI |
| ---: | ---: | ---: | ---: | --- |
| 2 | 0.7859 | 0.7779 | +0.0079 | [+0.0004, +0.0155] |
| 3 | 0.8600 | 0.8426 | +0.0174 | [+0.0085, +0.0263] |
| 5 | 0.9026 | 0.8779 | +0.0247 | [+0.0174, +0.0320] |
| 8 | 0.9035 | 0.8787 | +0.0247 | [+0.0182, +0.0313] |
| 12 | 0.9061 | 0.8835 | +0.0227 | [+0.0161, +0.0292] |
| 20 | 0.9061 | 0.8805 | +0.0255 | [+0.0184, +0.0327] |

Penalty slope over N >= 5: +0.00020 per e-fold. Change from N=5 to N=20: +0.0009 [-0.0093, +0.0111].

## A second verifier removes most of it

| pool | assignment | penalty | 95% CI | 1/K would predict |
| ---: | --- | ---: | --- | ---: |
| 1 | fixed | +0.0247 | [+0.0174, +0.0320] | 0.0247 |
| 2 | random | +0.0048 | [-0.0016, +0.0112] | 0.0123 |
| 3 | random | -0.0014 | [-0.0085, +0.0057] | 0.0082 |
| 4 | random | +0.0001 | [-0.0072, +0.0074] | 0.0062 |
| 5 | random | -0.0009 | [-0.0077, +0.0060] | 0.0049 |
| 8 | random | +0.0025 | [-0.0036, +0.0087] | 0.0031 |

## Guardrail

verifier_error_correlation is a within-task strictness shock on one verifier, not dependence between verifiers. It must not be cited as evidence about panel independence, and the beta-binomial reshape E040 asked for cannot be applied to it: there is no panel in randomness_lab whose joint-failure shape could be changed. Giving this lab a panel is a design change to run_r1_condition, not a sweep.
