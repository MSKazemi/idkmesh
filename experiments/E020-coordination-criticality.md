# E020 — Coordination criticality with matched susceptibility probes

**Status:** completed synthetic mechanism experiment for issue #49

**Result:** earlier sensitivity with a measurable false-alarm cost; no evidence
that susceptibility dominates an ordinary utilization threshold

## Protocol

The default run sweeps base generation probabilities
`0.30, 0.34, 0.36, 0.38, 0.39, 0.40` over 40 seeds. Each seed uses 20 generator
slots, worker capacity 12, verifier capacity 8, 240 ticks, and a 40-tick `+5%`
probe starting at tick 80.

```bash
python experiments/criticality_susceptibility.py --self-test
python experiments/criticality_susceptibility.py \
  --benchmark \
  --output /tmp/E020-coordination-criticality-40-seed.json
```

The committed raw artifact is gzip-compressed:

[`results/E020-coordination-criticality-40-seed.json.gz`](results/E020-coordination-criticality-40-seed.json.gz)

Artifact SHA-256:
`4ed44f304ebd8648844ed9613166ad4e50cf3906dac76aa1c376fe42c4dd4c60`.

It contains every control, pulse, and sustained-stress trial, including queue
histories, input-draw digests, outcomes, paired finite differences, recovery
censoring, and aggregate confidence intervals.

## Main result

Sustained `+5%` stress first met the predeclared overload criterion at base load
`0.38`, where 23/40 trials (`57.5%`) ended overloaded.

| Signal | First alert | Lead versus `0.38` | False-alert cells before onset |
| --- | ---: | ---: | ---: |
| superlinear backlog susceptibility | 0.34 | +0.04 | 2 |
| 90% offered-utilization threshold | 0.38 | 0.00 | 0 |
| one-window absolute backlog threshold | 0.39 | -0.01 | 0 |

The susceptibility signal was earlier, but not unambiguously better: its two
early alerts were false under the experiment's own future-stress criterion.
The simple utilization threshold detected the measured onset without a false
alert in this six-cell grid. The absolute queue threshold was late.

## Response curve

The backlog finite difference steepened toward the measured boundary, and
recovery became increasingly censored.

| Base load | Mean backlog susceptibility | Mean observed recovery ticks | Censored recovery trials | Future-stress overload rate |
| ---: | ---: | ---: | ---: | ---: |
| 0.30 | 2.2604 | 0.10 | 0/40 | 0.0% |
| 0.34 | 10.0735 | 0.95 | 0/40 | 0.0% |
| 0.36 | 29.4010 | 4.63 | 0/40 | 7.5% |
| 0.38 | 117.5247 | 26.74 | 1/40 | 57.5% |
| 0.39 | 270.9856 | 39.08 | 16/40 | 87.5% |
| 0.40 | 530.3281 | 57.63 | 32/40 | 97.5% |

Recovery means include observed recoveries only; the separate censored count is
essential and prevents non-recovery from being silently averaged away.

## Other requested metrics

The raw artifact reports uncertainty for:

- mean, peak, and variance of total queue backlog;
- mean latency;
- verified throughput;
- escaped synthetic failures;
- recovery time and censoring.

No single scalar is promoted as canonical. The baseline and perturbed variants
retain the same latent-workload digest for every seed, and their pre- and
post-pulse arrival counts match exactly.

## Interpretation

This is a useful negative/qualified result. A response probe can buy warning
lead, but it also adds alert noise and requires deliberately injected load. On
this model, ordinary utilization is the cleaner default signal. Susceptibility
is a possible secondary diagnostic when false-alert cost is acceptable.

The model is synthetic, discrete, and intentionally homogeneous. The tested
boundary depends on the generator count, capacities, horizon, perturbation,
alert definitions, and Bernoulli arrivals. It is not evidence of a literal
thermodynamic transition, and it is not a production-control calibration.

## Reproducibility and safety

`tests/test_criticality_susceptibility.py` covers exact replay, common random
numbers, perturbation-window isolation, uncertainty/raw-result retention,
fail-closed input validation, and the absence of acceptance/integration
authority. Phase 0 CI runs both the self-test and unit suite.
