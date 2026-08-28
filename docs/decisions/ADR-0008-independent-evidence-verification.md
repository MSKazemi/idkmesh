# ADR-0008 — Verification Uses Independent Evidence, Not Raw Vote Count

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related experiments:** E012, E013, E015
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

For a nominal group of size `N` with average pairwise error correlation `rho`, a widely used heuristic is:

`N_eff ~= N / (1 + (N - 1) rho)`

This expresses the design intuition that ten highly correlated reviewers can contain far less than ten reviewers' worth of independent information.

For verifier `i` with estimated correctness probability `p_i`, reliability evidence can be expressed with log odds:

`w_i = log(p_i / (1 - p_i))`

A future correlation-aware rule may discount `w_i` by estimated redundancy. The exact formula is **not** decided by this ADR; it must be chosen through falsifiable experiments.

E015 has since run that test on the `N_eff` heuristic above. See the follow-up section below: the heuristic survives as design intuition but **fails as a verification budget**, so it must not be promoted into the aggregation rule unmodified.

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

## Follow-up — E015 tested the `N_eff` heuristic

This ADR deferred the exact formula to falsifiable experiment. E015 supplied one for the
`N_eff ~= N / (1 + (N-1) rho)` term, measuring effective panel size directly across a
630-cell grid. The shared-shock mixture makes pairwise error correlation *exactly* `rho`, so
the heuristic is fed the parameter it asks for.

Outcome: it is exact at `rho = 0` and `rho = 1`, wrong in between, and **the sign of its
error is not fixed**.

- Usually conservative — median 1.43x understatement over 280 cells — which is harmless.
- But as `N` grows it converges to `1 / rho`, while true effective size converges to a lower
  **accuracy-dependent ceiling**: the `n` solving `E_indep(n, p) = rho (1 - p)`. The shared
  branch can be diluted but never outvoted, so panel error floors at `rho (1 - p)` no matter
  how many verifiers are added.
- At `p = 0.90`, `rho = 0.125` the heuristic promises 8 effective verifiers against a ceiling
  of 4.59, implying a panel error **14x lower** than the model delivers.

The optimistic corner is accurate verifiers with modest shared dependence, i.e. the regime
this ADR is trying to build toward. This does not change the decision — principle 1 (count
independent evidence, not votes) is reinforced, not weakened — but it constrains the
implementation:

1. `N / (1 + (N-1) rho)` stays as **design intuition only**. It must not be used to size a
   panel or to set an acceptance threshold.
2. A risk-sensitive policy (principle 6) should first compute the ceiling. If the ceiling is
   below the confidence a Work Unit requires, **no panel size reaches it**; additional
   reviewers are wasted spend and the only remaining moves are raising verifier accuracy or
   reducing shared dependence.
3. This strengthens principle 5: the redundancy discount is itself a fallible model, and the
   first one this project wrote down was wrong in the unsafe direction.

Reference implementation: `effective_n_ceiling` in `sim/e015_analyze.py`.
Full result: [`../../experiments/E015-verification-phase-diagram.md`](../../experiments/E015-verification-phase-diagram.md).

## Follow-up — E016 tried to measure `rho` on real verifiers and could not

E015's critique of the `N_eff` heuristic, and every correlation result before
it, rests on a synthetic shared-shock mixture in which `rho` is set by hand.
E016 attempted to measure it directly: 20 open-weight verifiers (4 model
families x 5 prompt templates) on 72 candidate solutions whose ground truth is
decided by executing hidden tests.

The panel produced no usable measurement. None of the 20 agents discriminated
above chance (mean Youden `J = +0.049`, 0/20 significant after Bonferroni), six
returned one constant verdict for all 72 tasks, and the majority vote
(accuracy `0.514`) lost to a rule that rejects everything unread (`0.639`).

Two things follow for this ADR:

1. **The independence assumption is still untested against reality.** This ADR
   reasons about verifiers that share errors; E016 does not tell us how much
   real ones do. That gap is unchanged.
2. **Verifier competence is a precondition for the independence question, and
   it is not free.** Panel diversity along the axes this ADR hypothesises —
   model family and prompt — moved the accept rate from 0.14 to 0.80 while
   carrying no task-level signal at all. Diversity of *opinion* is not evidence;
   a panel can be maximally diverse and jointly uninformative.

Practical consequence: any aggregation rule this ADR eventually specifies must
be gated on a per-verifier discrimination check, not on accuracy. On an
imbalanced corpus a constant verifier can post the panel's best accuracy score.

See [`../../experiments/E016-live-verifier-correlation.md`](../../experiments/E016-live-verifier-correlation.md).

## Follow-up — E017 measured `rho`, and found the model shape wrong

E016 could not measure verifier correlation. E017 did, using partial test
oracles that pass the discrimination screen. Three consequences for this ADR:

1. **A declared independence label predicts correlation only partly.** Verifiers
   sharing an input-region label correlate at `+0.892`; verifiers sharing no
   declared attribute still correlate at `+0.526`. Metadata grouping is
   informative but systematically overstates independence, so an aggregation
   rule keyed on declared groups alone will over-count evidence. This is the
   measured form of E013's warning.
2. **`rho` is not a sufficient statistic for panel error.** Fed the measured
   `rho`, the shared-shock mixture underestimates real panel error by 1.71x, and
   a nested version matching the block structure by 1.62x. Real panels fail
   *partially* — a majority wrong while a minority is right — which shared-shock
   assigns near-zero probability. An item-difficulty (beta-binomial)
   parameterisation at the same parameter count reproduces it. Any aggregation
   rule this ADR specifies should be evaluated under that model, not under a
   single correlation knob.
3. **Aggregation rule can matter more than panel size.** For the one-sided
   errors typical of test-based verification, moving from majority to
   unanimity-to-accept cut error 3.7x, while growing the panel from 1 to 25
   changed nothing (effective size 1.00). The ADR should therefore require
   measuring error sidedness before choosing a quorum.

See [`../../experiments/E017-item-difficulty-and-quorum.md`](../../experiments/E017-item-difficulty-and-quorum.md).

## Follow-up — E020 found the shape decides the aggregation rule, and both models miss the floor

E017 established that the shared-shock mixture has the wrong shape. E020 asks what
that costs operationally, using E017's 1800 real verdicts together with the E016
corpus base rate (46 of 72 candidates defective).

**1. The shared-shock model gets the highest-leverage decision backwards.** Fitted to
the real panel and asked how much a better acceptance quorum could buy, it answers
1.00x — no quorum beats majority, because its floor `rho*mu = 0.1186` is already
reached below majority. The measured answer is **3.75x** (0.2083 at majority, 0.0556
at the best quorum). Choosing the rule well is the largest available error reduction
on this panel, and it is free; the model in use through E012, E013 and E015 says it
is worthless.

**2. The optimum's location is set by the shape, not by `rho`.** At `n = 25`, sweeping
correlation, base rate and cost asymmetry, the shared-shock optimum spans 12-14 of 25
— always near majority. The item-difficulty optimum spans 1-25, the entire range.
Changing `rho` from 0.25 to 0.80 moves the optimum by one verifier; changing the shape
at fixed `rho` moves it by up to twelve. Eliciting `rho` is therefore not the useful
calibration step for panel design.

**3. Neither two-parameter model predicts the floor, and they err in opposite
directions.** At unanimity: real 0.0556, shared-shock 0.1186 (2.13x too high),
beta-binomial 0.0313 (1.77x too low). The shared-shock floor is `rho*mu`, a property
of correlation. The beta-binomial has no floor, decaying as `n^-0.576`. The real floor
is `lambda = 0.0556` — the 4 defects **every** verifier in the panel misses. That is a
shared blind spot, escapable only by adding a different *kind* of verifier, not by
decorrelating or by adding more of the same.

Consequence for this ADR: `lambda` joins `rho` as a quantity to measure, and it bounds
what any aggregation rule can deliver. See
[`E020-quorum-frontier-under-measured-shape.md`](../../experiments/E020-quorum-frontier-under-measured-shape.md).

## Implementation references

- `docs/architecture/MATHEMATICAL_EVOLUTION_KERNEL.md`
