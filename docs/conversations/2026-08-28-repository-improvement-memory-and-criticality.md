# Repository improvement, project memory, and criticality

Date: 2026-08-28

## Project-owner request

The project owner asked to:

- check the live `MSKazemi/idkmesh` repository;
- improve it;
- ensure that substantive project material continues to be preserved in the public repository;
- choose one additional physical formula/algorithm worth adding and explain why.

## Repository findings

The repository has advanced rapidly beyond its initial research-only state. Current main contains executable schemas, an experiment harness, an emergence simulator and reference result, zero-project-spend compute policy artifacts, constitutional evolution work, community automation, IDKGraph/self-evolution designs, and a large structured conversation archive.

`PROJECT_RULES.md` already contains a strong mandatory chat-to-repository preservation rule. The weakness is not absence of the rule; it is that repository memory did not yet have an explicit coverage/index layer for auditing whether conversation records have been promoted into decisions, research, specifications, code, or evidence.

The repository also still reports `main` as unprotected. Issue #35 tracks that prerequisite before stronger autonomous write/merge behavior is allowed.

During the audit, two competing randomness-lab implementations were visible as PR #39 and PR #41. PR #39 subsequently merged. PR #41 should therefore be treated as a candidate source of unique improvements, not merged as a second overlapping foundation without convergence/review.

## Improvement 1 — auditable project memory

Added `docs/project-memory/README.md` defining:

- memory layers;
- a memory coverage invariant;
- maturity states (`captured`, `promoted`, `executable`, `verified`, `superseded`);
- a structured audit process;
- future IDKGraph relationships between conversation, decision, specification, experiment, and evidence.

A project-memory manifest/audit is added in the same change so archived project knowledge can be enumerated and checked for path-level consistency.

## Improvement 2 — physics addition

The existing `SCIENTIFIC_FOUNDATIONS.md` already contains substantial physics: Boltzmann selection, simulated annealing, Helmholtz free energy, Ising/QUBO, diffusion, spectral connectivity, percolation, Kuramoto synchronization, transport, control/Lyapunov ideas, renormalization, and Landauer's principle.

Therefore the selected new addition is **fluctuation–response / susceptibility**, not another repeated optimization metaphor.

For observable `X` and conjugate field `h`, static susceptibility is

`chi_X = d <X> / d h`.

In an appropriate canonical equilibrium setting where `h` couples linearly to `X`, one obtains

`chi_X = beta * Var(X)`.

IDKMesh is not assumed to be an equilibrium physical system. The engineering version is measured empirically:

`chi_(y,u) ~= (E[y | u + delta_u] - E[y | u]) / delta_u`.

This asks a new question: **how sensitive is the current mesh state to the next small perturbation?**

Candidate uses include early warning for verification overload, worker churn, coordination collapse, cell partition pressure, community review overload, and repository restructuring pressure.

The dedicated research note is `docs/research/CRITICALITY_AND_FLUCTUATION_RESPONSE.md`.

## Why this physical principle

Most existing physical models in IDKMesh help search, coordinate, optimize, or represent topology. Susceptibility adds an early-warning capability:

- high load says the system is stressed now;
- high susceptibility says the system may be fragile even before load looks catastrophic.

This is especially useful for a self-growing system that wants to adapt before failure rather than only react afterward.

## Scientific guardrail

The project must not claim a literal thermodynamic phase transition merely because an engineering response curve becomes steep. The fluctuation–dissipation theorem has equilibrium assumptions that IDKMesh generally does not satisfy. Both response and variance should be measured and compared with ordinary queue/utilization/change-point baselines.

## Next actions

1. Keep all substantive project turns archived and promoted under `PROJECT_RULES.md`.
2. Make project-memory coverage machine-auditable.
3. Treat PR #41 as a convergence candidate after PR #39 merged, preserving only independently useful differences.
4. Run a small criticality/susceptibility experiment in simulation before using the signal in any controller.
5. Continue issue #35 so `main` becomes a protected integration boundary.
6. Keep Repository Homeostasis PR #36 proposal-first until reviewed against current rapidly changing main.

## Community impact

Project memory lowers dependence on private maintainer context. The criticality work creates a bounded research contribution path spanning statistical physics, control, queueing, distributed systems, and simulation without requiring contributors to understand the entire IDKMesh architecture.