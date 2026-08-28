# ACE Generation Evidence Interface

**Status:** Phase-A / shadow-controller interface  
**Related:** #25 / PR #48, #40, #57 / PR #68, `ACE_ACTIVITY_METABOLISM.md`

The ACE generational controller must not collapse **causal evidence**, **denominator inventory**, and **value/cost measurement** into one object.

The canonical Phase-A input therefore has three independent evidence layers:

```text
parents
  -> who is eligible for the reproduction denominator?

lineage_receipts
  -> which descendant is causally linked and independently verified?

strategy_outcomes
  -> what measured value/cost should update policy fitness?
```

This separation prevents two important errors:

1. a high self-reported value cannot manufacture causal reproduction;
2. a lineage receipt does not invent maintainer time, latency, noise, or utility value that was never measured.

## 1. Parent inventory

`parents` is an independent inventory of potential denominator items.

Minimal shape:

```json
{
  "id": "MSKazemi/idkmesh#pr:39",
  "verified": true,
  "matured": true
}
```

Only parents satisfying both:

```text
verified == true
matured == true
```

enter the denominator.

This is where right-censoring belongs: a new verified parent remains `matured=false` until its observation window has elapsed.

PR #40 contributes bootstrap cohort/exposure evidence, but a Growth Seed is not automatically identical to every future eligible parent. A generation snapshot must make denominator semantics explicit rather than deriving them from whichever descendants happened to exist.

## 2. Lineage receipts

`lineage_receipts` are **prevalidated receipts** compatible with the ACE lineage protocol from PR #48.

Example:

```json
{
  "identity": "lineage:pr39-reproduction",
  "parent": "MSKazemi/idkmesh#pr:39",
  "seed": "MSKazemi/idkmesh#issue:29",
  "descendant": "MSKazemi/idkmesh#pr:58",
  "descendant_type": "reproduce",
  "status": "verified",
  "recorded_at": "2026-08-28T14:30:00Z",
  "verified": true,
  "reviewer_minutes": 8,
  "verifier": "github:independent-reviewer"
}
```

The Phase-A controller assumes structural/schema validation occurred before the receipt reached the controller. It still enforces local safety invariants:

- lineage identity is unique;
- parent reference exists in the provided parent inventory when one is present;
- status is one of `candidate`, `merged`, `verified`, `rejected`;
- `verified` boolean agrees exactly with `status == verified`;
- reviewer minutes are finite and non-negative.

The reproduction numerator is:

```text
count(lineage receipt where status=verified and verified=true)
```

A merge, label, comment, or strategy-outcome row does not enter this numerator by itself.

## 3. Strategy outcomes

`strategy_outcomes` carry measured policy-learning quantities and must reference a known lineage identity.

Example:

```json
{
  "lineage_identity": "lineage:pr39-reproduction",
  "strategy": "reproduce",
  "value": 1.0,
  "maintainer_minutes": 2,
  "added_review_latency_hours": 0.5,
  "unproductive_public_writes": 0
}
```

A strategy outcome is **not** causal proof.

Positive value enters strategy fitness only when its linked lineage receipt is verified.

Reviewer minutes remain on the lineage receipt because they are part of verification evidence. The outcome must not duplicate them. Maintainer time, added latency, public-write noise, and measured value live on the outcome because they require separate observation.

Initial strategy fitness remains:

```text
f_i =
  verified linked outcome value
  -------------------------------------------
  1 + reviewer minutes + maintainer minutes
  - lambda_latency * added review latency
  - lambda_noise * unproductive public writes
```

The exact utility/value definition is experimental and must remain versioned and challengeable.

## 4. Reproduction and fitness are different questions

A verified receipt with no strategy outcome:

- **does** count toward causal reproduction;
- **does not** invent positive strategy fitness.

An outcome with a large value linked to an unverified receipt:

- **does not** count toward causal reproduction;
- **does not** create positive strategy benefit;
- may still carry measured cost/noise penalties.

This is intentional.

## 5. Full controller flow

```text
#40 / other observer
 -> independent parent/exposure inventory

#48 lineage validator
 -> validated causal receipts

measurement layer
 -> strategy outcomes / attention / latency / noise

#68 shadow controller
 -> R_community
 -> strategy fitness
 -> replicator-mutator update
 -> carrying-capacity homeostasis
 -> DORMANT / EXPLORE / GROW / CONSOLIDATE
 -> recommendation
```

No step above grants merge authority.

## 6. Current result contract

The Phase-A controller reports:

```text
evidence_format = ace-lineage-receipts+strategy-outcomes-v1
```

and preserves the rule:

> **Causal reproduction comes only from verified lineage receipts; positive strategy value comes only from measured outcomes linked to a verified receipt.**

## 7. Activation boundary

The controller remains shadow-only by default:

```text
activation_gate_passed = false
actuation_enabled = false
```

Even when a recommendation exists, no modeled public action is emitted unless both gates are true, capacity is healthy, the mode is not `CONSOLIDATE`, and the public-write budget is at most one.

Actual GitHub actuation remains a separate, independently reviewed integration step and is additionally gated on the repository safety/protection work in PR #51.
