# ADR-0008 — Verification Uses Independent Evidence, Not Raw Vote Count

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related experiments:** E012, E013
- **Related issues:** #22, #30, #71

## Context

IDKMesh expects many humans, AI agents, tests, tools, and compute workers to propose and verify artifacts. A naive implementation could treat verification as a simple quorum: if enough reviewers agree, accept the result.

E012 demonstrated a failure mode of that approach in a controlled synthetic model. Five individually 75%-accurate verifiers were evaluated while their error correlation increased. As correlation approached one, internal disagreement fell to zero while false-accept and false-reject rates approached the error rate of one verifier. Nominal reviewer count therefore overstated effective evidence count.

E013 tested a simple response: collapse declared independence groups to equal-weight group decisions. Using the same 11 verifier votes in groups `[7,1,1,1,1]`, group-balanced voting substantially improved accuracy when the 7-member cluster had correlated errors. However, when all 11 errors were genuinely independent, group balancing was worse because it discarded real independent information.

The combined result rules out two simplistic policies:

1. `more agreeing reviewers = proportionally more evidence`;
2. `always discount reviewers that share a metadata group`.

## Decision

IDKMesh verification should treat **estimated independent information** as the relevant quantity, not raw reviewer/model/account count.

### Required principles

1. **Preserve raw evidence.** Aggregated decisions must not erase the underlying verifier outputs, tests, provenance, confidence, or disagreement.
2. **Do not equate unanimity with independence.** Agreement is weaker evidence when failure modes are shared.
3. **Track evidence provenance.** Relevant dimensions may include model/provider family, prompt/reasoning template, test origin, retrieval/data source, toolchain, execution environment, organization/trust domain, and shared dependencies.
4. **Measure dependence from outcomes where possible.** Metadata groups are hypotheses about correlation, not ground truth. Historical error correlation and calibration should eventually influence evidence weights.
5. **Keep uncertainty about the weighting model.** A learned correlation or reliability estimate is itself fallible evidence and must not become an unquestioned authority.
6. **Use risk-sensitive verification.** High-risk Work Units should demand stronger and more independent evidence than low-risk work.
7. **Retain multiple aggregation baselines.** Naive majority, group-aware methods, Bayesian/log-odds approaches, robust aggregation, independent tests, and human escalation should remain experimentally comparable rather than collapsing into one permanent formula prematurely.

## Mathematical direction

For a nominal group of size `N` with average pairwise error correlation `rho`, a useful heuristic is:

`N_eff ~= N / (1 + (N - 1) rho)`

This expresses the design intuition that ten highly correlated reviewers can contain far less than ten reviewers' worth of independent information.

For verifier `i` with estimated correctness probability `p_i`, reliability evidence can be expressed with log odds:

`w_i = log(p_i / (1 - p_i))`

A future correlation-aware rule may discount `w_i` by estimated redundancy. The exact formula is **not** decided by this ADR; it must be chosen through falsifiable experiments.

## Consequences

### Positive

- Reduces false confidence from replicated/correlated AI agents.
- Makes heterogeneous models, tools, tests, and trust domains structurally valuable when they add independent information.
- Encourages reproducible independent testing instead of superficial reviewer multiplication.
- Gives provenance data a concrete verification purpose.
- Connects swarm diversity metrics to real quality gates.

### Costs and risks

- Correlation estimation requires history and ground-truth or delayed outcome signals.
- New contributors/verifiers have sparse evidence histories.
- Dependence can change over time or under distribution shift.
- Colluding actors may attempt to appear independent.
- Metadata-based grouping can incorrectly discount genuinely independent reviewers.
- A complex weighting model can become opaque and create governance risk.

Therefore raw evidence, simple baselines, calibration diagnostics, and human-readable explanations remain required.

## Rejected alternatives

### One verifier, one equal vote

Rejected as a universal high-stakes rule because correlated reviewers can create false confidence simply through replication.

### Permanent group-balanced voting

Rejected as the final rule because E013 showed it loses useful information when group members are actually independent.

### One global reputation score

Rejected because reliability is task-, domain-, tool-, and time-dependent, and one scalar score hides uncertainty and correlation.

## Next experiment

E014 should estimate verifier reliability and dependence from a calibration history, then evaluate on a held-out stream. Compare at least:

1. naive majority;
2. declared-group balancing as an oracle-like reference baseline;
3. empirically inferred dependence groups or effective-sample-size weighting;
4. Bayesian/log-odds reliability weighting.

The key question is no longer whether correlation matters. It is whether IDKMesh can **learn enough about correlation and reliability to improve verification without creating a new source of false confidence**.
