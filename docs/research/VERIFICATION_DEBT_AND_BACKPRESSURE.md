# Verification Debt and Risk-Weighted Backpressure

Status: experimental research/design note  
Date: 2026-08-28  
Related: issues #5 and #14

## 1. The important idea: verification debt

IDKMesh should not measure verification backlog only as a count of unreviewed candidates.

Ten trivial documentation candidates and ten security-sensitive dependency changes do not create the same trust burden. The system therefore needs a first-class control signal for **unverified risk**.

Define **verification debt** as the amount of risk-weighted evidence work still required before pending candidates can be treated as sufficiently checked.

For candidate `i`, the current reference model is:

```text
Debt_i = risk_i
       * max(uncertainty_i, uncertainty_floor)
       * (1 + impact_i)
       * verification_cost_i
       * (1 + lambda * diversity_deficit_i)
```

where:

- `risk` estimates consequence/severity if the candidate is wrong;
- `uncertainty` represents how little confidence the system has before independent evidence;
- `impact` represents blast radius / project importance;
- `verification_cost` estimates scarce verifier effort;
- `diversity_deficit = 1 - evidence_diversity` increases debt when existing evidence is highly correlated;
- `lambda` controls how strongly correlated evidence increases pressure.

Total queue debt is:

```text
D = sum_i Debt_i
```

This value is **not** a probability of failure and is not a final quality score. It is a controller signal.

## 2. Why this matters

A generation-first swarm can fail even if each individual worker is useful:

```text
candidate generation rate > independent verification capacity
    -> verification queue grows
    -> human/reviewer attention saturates
    -> low-quality evidence is accepted or review stalls
    -> additional agents reduce system value
```

The architecture should therefore make generation capacity subordinate to evidence capacity.

A useful invariant is:

> **IDKMesh may generate candidates aggressively only while its independent verification system can keep verification debt inside a stable operating region.**

This converts verification from a passive final gate into an active flow-control mechanism.

## 3. Algorithm: Risk-Weighted Verification Backpressure (RWVB)

`experiments/verification_backpressure.py` implements a deterministic reference controller.

RWVB has two coupled decisions.

### 3.1 Which candidates receive verifier capacity?

For each queued candidate:

```text
Priority_i = risk_i
           * max(uncertainty_i, uncertainty_floor)
           * (1 + impact_i)
           * (1 + lambda * diversity_deficit_i)
           * age_factor_i
           / verification_cost_i
```

The scheduler allocates the next verification window to candidates with the highest risk-clearing pressure per unit verification cost.

A starvation guard handles candidates that have waited longer than `max_wait_steps` before normal priority ordering.

This is deliberately simple enough to benchmark against FIFO, pure risk ordering, and more sophisticated schedulers later.

### 3.2 How much new candidate generation is allowed?

Let:

```text
load = total_verification_debt / verification_capacity_per_window
```

Use two watermarks:

- if `load > high_watermark`, multiplicatively reduce generation fan-out;
- if `load < low_watermark`, allow fan-out to expand;
- otherwise keep fan-out unchanged.

Reference control law:

```text
fanout_next = fanout * exp(-eta * overload)
```

for overload, with the corresponding positive exponent when safely underloaded, clipped between configured minimum and maximum fan-out.

This creates a negative feedback loop:

```text
more unverified risk
 -> more verification pressure
 -> less new generation
 -> queue can clear
 -> fan-out may grow again
```

## 4. Relationship to classical backpressure

RWVB is inspired by MaxWeight/backpressure methods from queueing/network control, where scheduling decisions use queue backlog pressure to stabilize constrained stochastic systems.

Useful references:

- L. Tassiulas and A. Ephremides, *Stability Properties of Constrained Queueing Systems and Scheduling Policies for Maximum Throughput in Multihop Radio Networks*, IEEE Transactions on Automatic Control, 1992.
- Michael J. Neely, *Stochastic Network Optimization with Application to Communication and Queueing Systems*, 2010.
- Neely's backpressure notes: https://ee.usc.edu/stochastic-nets/docs/backpressure.pdf
- Stochastic Network Optimization resources: https://ee.usc.edu/stochastic-nets/

IDKMesh is **not claiming the throughput-optimality theorem of classical backpressure for this heuristic transformation**. Candidate risk, verification cost, evidence diversity, and generation fan-out have different semantics from packet queues and link capacities. The connection is an engineering inspiration that must be tested.

## 5. Relationship to independent VerificationResult

The new contract:

`schemas/verification-result-v0.1.schema.json`

makes verification a separate protocol object:

```text
WorkUnit
  -> worker attempt
  -> ResultManifest (candidate self-report)
  -> independent verifier
  -> VerificationResult (checks + evidence + recommendation)
  -> integration/human decision
```

The harness now enforces several cross-object invariants:

- VerificationResult must reference the exact ResultManifest/WorkUnit attempt;
- evidence references must resolve inside the VerificationResult;
- required WorkUnit validators must appear as checks;
- validators requested by the worker ResultManifest must appear;
- when the WorkUnit requires independence, verifier identity must differ from worker identity;
- an `accept_candidate` recommendation requires passed verification and passed required checks.

The verifier recommendation is still **not an automatic merge decision**.

## 6. Evidence diversity as a first-class variable

A system with five verifiers can still have almost one effective verifier if they share the same model, prompt, runtime, data, or failure mode.

The VerificationResult therefore records basic correlation signals:

- shared model family;
- shared runtime;
- observed worker identity;
- correlation notes.

The current scheduler compresses this into `evidence_diversity` for the experimental algorithm. Future experiments should replace this hand-entered value with measured error correlation where possible.

## 7. What to measure

Issue #14 should compare at least:

1. FIFO verification;
2. highest-risk-first;
3. cheapest-first;
4. RWVB without fan-out control;
5. RWVB with verification-debt fan-out control.

Measure raw outcomes:

- escaped defect rate;
- accepted candidates/time;
- verification queue length;
- total verification debt;
- maximum waiting time;
- verifier compute;
- human review minutes;
- false rejection rate;
- security/regression detection;
- generation fan-out;
- correlation/diversity of evidence.

## 8. Failure modes / cautions

RWVB can be wrong or gamed if:

- risk estimates are systematically biased;
- high-cost candidates starve despite age protection;
- low-risk labels are strategically abused;
- estimated verification cost is inaccurate;
- evidence diversity is guessed rather than measured;
- the controller oscillates because response rate is too aggressive;
- high-risk work monopolizes all verification indefinitely.

Therefore parameters are experiment inputs, not permanent governance constants.

## 9. Near-term architecture consequence

For the local Verified Swarm Runner, the queue should not be:

```text
workers -> candidates -> FIFO verifier
```

Prefer the explicit control structure:

```text
                 +----------------------------+
                 | verification debt / load   |
                 +-------------+--------------+
                               |
                               v
WorkUnits -> generators -> candidate queue -> verifier scheduler
               ^                   |                 |
               |                   |                 v
               +--- fan-out control+        VerificationResults
                                                     |
                                                     v
                                             integration decision
```

The central architectural idea is simple:

> **Generation is supply; verification is trust capacity; verification debt is the pressure connecting them.**
