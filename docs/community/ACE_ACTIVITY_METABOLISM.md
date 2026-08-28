# ACE Activity Metabolism

**Status:** canonical community-loop specialization / shadow-mode controller design
**Date:** 2026-08-28

IDKMesh already has the ingredients for a nature-inspired self-improving repository: project fitness, community reproduction, carrying capacity, stigmergy, replicator dynamics, exploration temperature, structural entropy, verification backpressure, and lineage evidence. The missing layer is a single rule that composes them.

This document defines that community-specific composition as **ACE Activity Metabolism**. [`../../ITERATION_MODEL.md`](../../ITERATION_MODEL.md) defines the whole-system lifecycle and shared vocabulary.

The core idea is biological rather than promotional:

> Repository activity is raw environmental input. IDKMesh should metabolize it into verified capability, knowledge, repair, or reproductive opportunity. Activity itself is not fitness.

This extends `ITERATION_MODEL.md`, `COMMUNITY_GROWTH_ENGINE.md`, `docs/community/COMMUNITY_GROWTH_DYNAMICS.md`, and `docs/community/ACE_GITHUB_CONSTRAINED_EVOLUTION.md`. It does not replace their detailed models.

## 1. The no-wasted-event invariant

No honest algorithm can guarantee that every commit, issue, comment, review, star, or pull request improves the project. Some events are wrong, redundant, adversarial, or simply uninformative.

What IDKMesh *can* require is:

```text
Every substantive event must become one of:

1. verified improvement;
2. uncertainty-reducing evidence;
3. risk/debt detection or repair;
4. a bounded descendant opportunity;
5. a quiet observation that updates future selection.
```

Therefore:

```text
activity != improvement
```

but:

```text
activity -> observation -> evidence -> selection -> adaptation
```

should hold for every supported event class.

A negative experiment, rejected PR, failed workflow, or critical comment can improve the *next* state by exposing a bad hypothesis or risk. This is the repository analogue of metabolism: useful structure is extracted from heterogeneous inputs; harmful material is not amplified merely because it exists.

## 2. Two coupled state spaces

### Project state

Reuse the canonical state from `ITERATION_MODEL.md`:

```text
S_t = [G_t, Q_t, C_t, V_t, M_t, H_t, R_t]
```

where `G/Q/C/V/M/H` are positive fitness dimensions and `R` is accumulated risk/debt.

Project fitness remains:

```text
Phi(S_t) = sum positive weighted dimensions - weighted risk/debt
```

### Community/ecology state

Use a second compact state:

```text
E_t = [R_c, L, K, W, T, U]
```

where:

- `R_c` = verified community reproduction number;
- `L` = review/verification/maintainer load;
- `K` = sustainable carrying capacity;
- `W` = strategy weights;
- `T` = exploration temperature / uncertainty budget;
- `U` = unresolved lineage/measurement uncertainty.

The repository is healthy only when project and community state improve together. A burst of contribution that increases `Q` while overwhelming `L > K` is not healthy scaling.

## 3. Event metabolism receipt

For each normalized GitHub event `e_t`, create a quiet **metabolism receipt**:

```text
M(e_t) = (
  project_delta,
  information_gain,
  risk_delta,
  lineage_refs,
  review_cost,
  novelty,
  verification_state
)
```

The first versions may contain prior estimates, but all such values must be labeled as estimates. Real descendant/verification evidence should replace priors over time.

Every receipt is evidence. Only some receipts justify public actuation.

### Novelty / diminishing-return factor

Repeated identical events should have lower marginal influence:

```text
nu(e) = 1 / sqrt(1 + N_type(e))
```

This prevents ten near-identical comments or commits from receiving ten times the evolutionary credit of the first informative one.

## 4. Ecological capacity gate

Reuse the ACE logistic carrying-capacity governor:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

Interpretation:

- `Capacity ~ 1`: the community can absorb more descendant work;
- `Capacity ~ 0`: growth pressure should collapse toward consolidation, review, repair, or no action.

This gate applies regardless of raw popularity or activity.

## 5. Metabolic yield

For an observed event, define a non-negative useful-yield accounting quantity:

```text
Y(e) =
  a * max(0, DeltaPhi_verified)
+ b * InformationGain
+ c * max(0, -DeltaRisk)
+ d * VerifiedDescendantValue
```

then capacity- and novelty-adjust it:

```text
Y_eff(e) = Y(e) * nu(e) * Capacity(L)
```

Important rules:

- unverified raw activity contributes no `VerifiedDescendantValue`;
- a merge is not automatically verification;
- a negative result can have positive `InformationGain`;
- a security finding can have positive value through `-DeltaRisk`;
- the formula is an accounting model for experiments, not a permanent universal utility function.

The coefficients `a..d` are versioned policy parameters and must eventually be calibrated from outcomes.

## 6. Autocatalysis: make useful work create useful work

A successful contribution should leave a **stigmergic catalyst** in the repository so another contributor can act without private context.

Candidate catalyst types are the existing ACE strategies:

```text
reproduce
challenge
extend
explain
review
onboard
consolidate
```

A catalyst is not necessarily a new issue. It can be:

- a clearer acceptance test;
- a linked reproduction task;
- a benchmark case;
- a documented extension point;
- an explicit unanswered question;
- an ownership/review opportunity;
- an onboarding example;
- a consolidation proposal.

The lineage protocol in #25 / PR #48 provides the causal chain:

```text
parent -> seed/catalyst -> descendant -> verification
```

This is essential: without lineage, ACE cannot distinguish real community reproduction from coincidental activity.

## 7. Community reproduction

Use the evidence-backed measure already proposed by ACE:

```text
R_c(W, t) =
    verified descendants in window W
    ---------------------------------
    eligible matured verified parents
```

The target is not unbounded `R_c`.

IDKMesh should aim for:

```text
R_c > 1 for retained verified useful collaboration
```

while remaining:

```text
subcritical in unverified work,
review debt,
spam,
risk,
and maintainer overload.
```

That is the ecological operating region.

## 8. Strategy evolution: replicator-mutator rule

After a generation has descendant evidence, assign each catalyst strategy `i` a measured fitness such as:

```text
f_i =
    verified_descendant_value_i
    --------------------------------------------
    1 + reviewer_minutes_i + maintainer_minutes_i
    - lambda_latency * added_review_latency_i
    - lambda_noise * unproductive_public_writes_i
```

Then update strategy weights:

```text
w_i* = w_i * exp(eta * (f_i - mean_fitness))
```

Normalize and preserve mutation/exploration:

```text
w_i(t+1) =
    (1 - mu) * normalize(w_i*)
    + mu / n
```

with `mu > 0`.

This is the main nature-inspired learning mechanism: strategies that repeatedly produce verified descendants per scarce attention reproduce in policy space; unsuccessful strategies lose weight but never vanish completely.

Raw stars, comments, commits, issues, and PR counts must not enter the numerator.

## 9. Exploration temperature

Use the existing Boltzmann/annealing idea only for *selection among plausible actions*:

```text
P(i) proportional to exp(score_i / T)
```

Increase `T` when:

- uncertainty is high;
- hypotheses are weakly distinguished;
- experiments are cheap/reversible;
- the repository is stagnant.

Decrease `T` when:

- evidence is strong;
- review capacity is constrained;
- structural entropy is rising;
- risk is high.

Randomness controls exploration, never acceptance.

## 10. Generational action rule

Do not make every event create another public event.

Use:

```text
many events
  -> metabolism receipts
  -> lineage + verification evidence
  -> generation evaluation
  -> strategy-weight update
  -> capacity gate
  -> 0 or 1 bounded public action
```

Initial invariant:

```text
public autonomous ACE actions per generation <= 1
```

`0` is a valid and often optimal action.

This preserves the user's requirement that every activity contributes to project evolution while avoiding a notification/spam feedback loop.

## 11. Response mode

A generation chooses among:

```text
DORMANT
EXPLORE
GROW
CONSOLIDATE
```

Suggested policy:

```text
if review/security/governance load exceeds capacity:
    CONSOLIDATE
elif lineage evidence is insufficient:
    DORMANT or EXPLORE in shadow mode
elif R_c < 1 and capacity is healthy:
    EXPLORE
elif R_c >= 1 and capacity is healthy:
    GROW
else:
    DORMANT
```

No mode grants merge authority.

## 12. Mapping GitHub activity into the metabolism

| GitHub activity | Quiet system contribution | Possible later catalyst |
| --- | --- | --- |
| push/commit | provenance + changed-surface observation | test, explanation, consolidation |
| issue opened | goal/uncertainty signal | bounded hypothesis or newcomer task |
| issue closed | resolution/evidence signal | reproduction or documentation seed |
| PR opened | candidate capability + review demand | review/challenge |
| PR merged | candidate parent, not automatically verified | reproduce/extend/explain |
| review | verification/risk evidence | reviewer ownership |
| comment | clarification, dissent, requirement, or noise evidence | update task/goal only if informative |
| workflow failure | risk/debt evidence | repair task |
| workflow success | verification evidence only for what the workflow actually tests | reproducible example |
| star/fork | discovery signal only | never automatic fitness credit |

Thus every supported activity is observed, but only evidence-backed activity is amplified.

## 13. Relationship to current implementation

Existing infrastructure already covers much of the observation layer:

- `.github/workflows/evolution-loop.yml` observes issues, PRs, reviews, and comments;
- `.github/workflows/ace-community-growth.yml` observes community events and maintains the Growth Ledger;
- `scripts/evolution_score.py` creates prior-labeled fitness observations;
- PR #40 proposes cohort observability;
- PR #48 proposes lineage evidence;
- PR #44 proposes the bounded ACE population simulator;
- issue #57 defines the evidence-gated generational policy controller.

Therefore the next implementation should **not** add another public-event bot.

The next implementation is the Phase-A controller from #57 in shadow mode: deterministic lineage/capacity input -> strategy update -> mode -> recommendation, with no public actuation.

## 14. Safety and anti-Goodhart constraints

Hard constraints:

- activity count is not success;
- no self-merge;
- no one actor proposes, verifies, and integrates its own high-impact change;
- no public-write amplification when `L > K`;
- no positive descendant fitness without explicit verification evidence;
- duplicate/replayed events must not multiply causal credit;
- community growth cannot override security/governance constraints;
- human attention is a scarce resource in the objective;
- negative results remain first-class evidence;
- all policy weights and formulas are challengeable through normal review.

## 15. The canonical loop

```text
GitHub activity
   -> quiet observation
   -> metabolism receipt
   -> project-state update / uncertainty update
   -> lineage link when causal relationship exists
   -> independent verification
   -> descendant value + attention cost
   -> ecological capacity gate
   -> replicator-mutator policy update
   -> 0 or 1 bounded catalyst
   -> next generation
```

This is the desired self-improvement mechanism:

> **Every activity teaches the mesh; verified useful activity can reproduce; reproduction is throttled by carrying capacity; strategy selection evolves from descendant evidence; and the repository remains quiet when additional activity would make the system worse.**
