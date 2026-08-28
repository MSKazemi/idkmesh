# ACE v1 Policy Controller — Phase A

**Status:** Offline experimental controller. No GitHub actuation.

This document specifies the first executable policy-learning layer for ACE (Autocatalytic Community Evolution). It implements the Phase-A portion of Issue #57 while deliberately leaving all GitHub write integration disabled.

## Purpose

ACE v0 observes repository activity and estimates community pressure. The next step is not to create more automated GitHub activity. It is to learn, generation by generation, which bounded community strategies produce **verified useful descendants per unit of scarce human attention**.

Phase A therefore implements a pure deterministic function:

```text
previous strategy weights
+ verified lineage evidence
+ review-load state
+ eligible parent count
        |
        v
strategy fitness
        |
        v
replicator-mutator update
        |
        v
carrying-capacity safety gate
        |
        v
DORMANT / EXPLORE / GROW / CONSOLIDATE
        |
        v
0 or 1 bounded recommendation
```

The function does not call GitHub and does not create issues, comments, PRs, labels, or merges.

## Strategies

The initial policy simplex contains seven strategies:

- `reproduce` — independently reproduce prior work;
- `challenge` — try to falsify an assumption or result;
- `extend` — implement one bounded extension;
- `explain` — make useful work easier for newcomers to understand;
- `review` — spend effort on independent verification/review;
- `onboard` — lower the friction of a first/next useful contribution;
- `consolidate` — reduce growth pressure and spend capacity on review, cleanup, security, and integration.

These names are hypotheses, not constitutional categories. They can evolve after evidence exists.

## Evidence-only fitness

For strategy `i`, the Phase-A fitness shape is:

```text
f_i = verified_value_i / (1 + reviewer_minutes_i + maintainer_minutes_i)
      - lambda_latency * added_review_latency_i
      - lambda_noise * unproductive_public_writes_i
```

Only explicit verified descendants contribute to the positive numerator.

Therefore:

```text
raw activity != positive fitness
merge != verification
comment count != usefulness
stars != usefulness
```

Unverified activity can still impose review/noise costs and therefore create zero or negative fitness.

## Evidence deduplication

Every evidence record has a stable `evidence_id`.

- identical repeated records are counted once;
- reuse of one ID for conflicting records fails closed;
- duplicate GitHub events therefore cannot multiply fitness.

This is important because GitHub delivery/reprocessing behavior and future observatories can expose the same lineage fact more than once.

## Replicator-mutator update

Given prior normalized weights `w_i`, measured fitness `f_i`, learning rate `eta`, mutation/exploration rate `mu`, and mean strategy fitness `f_bar`:

```text
w_i* = w_i * exp(eta * (f_i - f_bar))
```

Normalize, then preserve exploration:

```text
w_i' = (1 - mu) * normalize(w_i*) + mu / n
```

When `mu > 0`, every strategy remains reachable. ACE therefore does not permanently eliminate a strategy merely because it performed poorly in a small early sample.

This is inspired by evolutionary replicator-mutator dynamics, but it is an engineering policy update rather than a biological claim.

## Carrying-capacity governor

Review capacity is modeled with the existing ACE logistic governor:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

where:

- `L` = review-load proxy;
- `K` = desired carrying capacity;
- `tau` = transition softness.

When capacity drops below the consolidation threshold, Phase A transfers a bounded fraction of probability mass from growth strategies toward `consolidate`.

This is a **safety/homeostasis transform**, not learned positive fitness. Growth strategies retain non-zero probability even under pressure.

## Mode selection

The controller chooses one of four modes:

### DORMANT

No evidence exists for the generation.

### EXPLORE

Evidence exists but verified reproduction is absent or below a convincing self-reproduction regime.

### GROW

There are verified descendants, measured `R_community >= 1`, and review capacity remains healthy.

### CONSOLIDATE

Review capacity falls below the safety threshold. This mode dominates raw reproduction signals.

For an eligible-parent inventory of size `P` and `V` unique verified descendants:

```text
R_community = V / P
```

The eligible-parent inventory must come from an independent observer/inventory so parents with zero descendants remain visible. This matches the survivorship-bias guard described in PR #48.

## Public-action invariant

The model contains the invariant:

```text
public autonomous ACE actions per generation <= 1
```

`max_public_actions > 1` is rejected by configuration validation.

Even the pure model emits **zero** public actions when:

- the external activation gate is not passed;
- actuation is disabled;
- review capacity is below the action floor;
- the generation has no evidence-backed recommendation;
- mode is `CONSOLIDATE`.

Phase A itself has no GitHub actuator at all. The modeled `public_actions` field exists so these gates can be tested before Phase B exists.

## Activation gate

A future GitHub adapter must remain disabled until Issue #57's external conditions are independently satisfied, including:

- cohort observation accepted or equivalently available;
- reviewed lineage evidence protocol;
- real descendant evidence rather than activity proxies;
- review-capacity state available without competing writers;
- ACE security review has no blocker;
- repository integration controls are strong enough for the requested authority.

A recommendation is not permission.

## Deterministic fixtures

`experiments/ace_policy_controller.py --fixtures` includes three illustrative states:

1. **under-reproduction** — activity exists but nothing is verified; positive fitness is not invented;
2. **healthy reproduction** — verified descendants exceed eligible parents while capacity is healthy;
3. **overload** — verified work exists but review load forces `CONSOLIDATE` and zero public growth actions.

These are invariant tests and intuition pumps, not empirical measurements of the IDKMesh community.

## Tests

`tests/test_ace_policy_controller.py` verifies:

- normalized strategy weights;
- non-zero exploration probabilities;
- no positive fitness from unverified activity;
- evidence deduplication;
- conflicting duplicate evidence fails closed;
- healthy reproduction can produce at most one modeled action;
- overload forces consolidation and zero actions;
- activation gate blocks otherwise healthy action;
- action budget cannot exceed one;
- fixed inputs produce deterministic output.

## Relationship to concurrent ACE work

- **PR #40:** cohort observation / eligible-parent evidence surface.
- **PR #44:** illustrative population/review-load dynamics simulation.
- **PR #48:** parent -> seed -> descendant lineage evidence protocol.
- **Issue #26:** ACE workflow threat model.
- **Issue #57 / this Phase A:** pure generational policy learning.

The separation is intentional. Measurement, simulation, lineage semantics, policy learning, security, and GitHub actuation should remain independently reviewable.

## Next step after review

Do not jump directly to an autonomous Growth Seed generator.

After the Phase-A controller and prerequisite evidence surfaces are accepted, the next experiment should replay real or curated ACE lineage snapshots through the pure controller and compare its recommendations with human review. Only then should a metadata-only Phase-B adapter be proposed, initially with zero autonomous public actions or an explicit opt-in gate.
