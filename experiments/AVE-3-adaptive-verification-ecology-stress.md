# AVE-3 — Correlation, Capacity, Shift, Outage, and Adversarial Stress Grid

**Status:** synthetic stress experiment, not empirical evidence  
**Date:** 2026-09-22  
**Implementation:** `sim/adaptive_verification_ecology_stress.py`  
**Stress hooks:** `sim/adaptive_verification_ecology_ablation.py`  
**Tests:** `tests/test_adaptive_verification_ecology_stress.py`  
**Retained summary:** `experiments/results/AVE-3-stress-summary.csv`  
**Tracking:** issue #621

## Question

Do the narrower AVE findings from AVE-1/AVE-2 survive when the previously open
stress axes are isolated, and where does the controller still fail?

## Policies

AVE-3 intentionally reduces the policy set to four interpretable comparators:

1. `capability-only`;
2. `plus-verifier-diversity`;
3. `ave-core` — diversity + risk adaptation + backpressure/price-aware routing,
   without positive probe-derived trust;
4. `full-ave` — the original controller including probe memory.

Each environment uses 20 deterministic seeds, 24 workers, 50 epochs, and 12
verifiers.

## Stress axes

### Verifier correlation

Worker shocks are held fixed while verifier-family shock coupling changes:

- `verifier-corr-low`: 0.25x reference coupling;
- `verifier-corr-medium`: 1.0x;
- `verifier-corr-high`: 1.75x.

### Worker correlation

Verifier coupling is held fixed while worker-family shock frequency/severity
changes:

- `worker-corr-low`;
- `worker-corr-medium`;
- `worker-corr-high`.

### Review capacity

- `review-scarce`: 0.60x reference capacity;
- `review-medium`: 1.0x;
- `review-abundant`: 1.50x.

### Structural stresses

- `dominant-provider`: one worker family receives a capability advantage while
  other families receive a smaller penalty;
- `workload-shift`: demand changes halfway through the run from
  documentation/onboarding-heavy toward security/integration-heavy work;
- `provider-outage`: one worker family disappears halfway through;
- `verifier-outage`: one verifier family disappears halfway through;
- `selective-adversarial-verifier`: one verifier family appears excellent on
  known-bad probes but accepts most defective live candidates.

The stress mechanisms are synthetic and deliberately simple. They are designed
to falsify controller assumptions, not to model every production failure mode.

## Correlation result

Increasing verifier correlation worsens every policy's defect escape.

| Verifier correlation | Policy | Escape rate | High-risk escapes |
| --- | --- | ---: | ---: |
| low | verifier diversity | **0.0231** | 3.05 |
| low | AVE-core | 0.0466 | 0.45 |
| low | full AVE | 0.0446 | **0.40** |
| medium | verifier diversity | **0.0373** | 5.00 |
| medium | AVE-core | 0.0644 | 0.85 |
| medium | full AVE | 0.0624 | **0.70** |
| high | verifier diversity | **0.0709** | 8.60 |
| high | AVE-core | 0.1047 | **2.70** |
| high | full AVE | 0.0969 | 3.00 |

This reinforces the paper's central premise: declared panel size cannot substitute
for measured dependence. Verifier diversity remains the strongest broad
defect-escape policy in this synthetic family, while risk-adaptive AVE variants
trade some ordinary escape performance for much lower high-risk escape.

Worker correlation produces the same qualitative degradation. The verifier
diversity arm is comparatively insensitive in ordinary escape rate
(0.0303 -> 0.0373 -> 0.0396 across low/medium/high worker correlation), while
AVE-core/full AVE preserve sub-1 mean high-risk escapes in all three worker
correlation conditions.

## Capacity result

The shadow price behaves as intended.

For AVE-core:

| Review capacity | Attempts | Duplicate rate | Mean review price | Verified utility / cost |
| --- | ---: | ---: | ---: | ---: |
| scarce | 653.35 | **0.0249** | **1.5921** | **0.4200** |
| medium | 930.70 | 0.0762 | 0.5483 | 0.3822 |
| abundant | 1194.90 | 0.1560 | 0.0073 | 0.3542 |

When verification is scarce, the price rises and optional generation falls.
When verification is abundant, the price approaches zero and dispatch returns
toward the unconstrained workload.

This is useful control behavior, but it is not a free utility improvement:
capability-only remains more efficient on the simulator's utility/cost metric.
AVE's value is the risk/coverage/duplication tradeoff, not maximal raw throughput.

## Dominant provider and distribution shift

The dominant-provider stress does not force the adaptive policies into one
worker family. AVE-core retains full task coverage with task-family concentration
0.423, compared with 0.844 for capability-only.

Under the mid-run workload shift:

- capability-only duplicate rate rises to 0.470;
- verifier diversity reduces it to 0.180;
- AVE-core reduces it to 0.119;
- full AVE reduces it to 0.114.

AVE-core/full AVE also keep mean high-risk escapes near 1 while capability-only
reaches 31.6 in this synthetic shift.

This supports continued work on adaptive routing, but does not yet prove that
the current posterior/temperature mechanism detects real distribution shift
quickly enough.

## Outage result

Removing one worker family halfway through reduces throughput but does not
collapse the tested policies. Removing one verifier family increases verifier
concentration as expected, while the diversity and AVE policies continue using
the remaining families.

These are limited failure-isolation checks, not evidence for real distributed
availability or Byzantine fault tolerance.

## Critical negative result: selective adversarial verifier

The selective-adversary environment is the most important AVE-3 result.

The adversarial verifier family:

- rejects known-bad probes correctly with 99% probability;
- behaves normally on good live candidates;
- accepts most defective live candidates.

| Policy | Escape rate | High-risk escapes | Probe breach rate |
| --- | ---: | ---: | ---: |
| capability-only | 0.1105 | 38.25 | n/a |
| verifier diversity | **0.0811** | 10.85 | n/a |
| AVE-core | 0.1220 | **2.70** | n/a |
| full AVE | **0.1372** | 3.65 | 0.1856 |

Two points matter:

1. AVE-core still protects high-risk work much better than the cheap baseline,
   but its ordinary escape rate is worse than capability-only in this attack.
2. Full AVE is worse than AVE-core because a verifier that performs well on
   probes can exploit positive probe-derived trust.

Therefore **known-bad probe success must never be sufficient evidence for
positive verifier authority**.

This is a direct Goodhart/adversarial-selection failure: once a diagnostic
becomes a routing reward, a verifier can optimize the diagnostic without being
reliable on the target distribution.

## Decision

AVE-3 completes the requested synthetic environment grid in issue #621, but it
does **not** justify live activation.

Keep the useful parts:

- measured verifier-family diversity;
- risk-adaptive verifier floor/quorum;
- capacity-aware generation backpressure;
- bounded task-family learning.

Add a new trust invariant before any dry-run policy can be considered for
authority:

> **Diagnostic evidence may reduce trust or trigger escalation, but it may not
> create positive verifier authority unless it is calibrated against held-out
> live outcomes that the verifier could not select or recognize in advance.**

The next algorithmic experiment should implement this as a **Trust Evidence
Firewall** separating:

- probe/diagnostic evidence;
- held-out live outcome evidence;
- independence/correlation evidence;
- authority eligibility.

## Evidence boundary

All AVE-3 results are synthetic. The stress grid can falsify mechanisms cheaply,
but it cannot establish production safety, real coding-agent performance,
human-review behavior, or adversarial robustness.
