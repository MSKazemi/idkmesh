# E040's diversity advantage under a correctly shaped worker panel

10 seeds x 200 tasks per cell; 18 curves per shape.

## The two shapes are matched

| rho | shared-shock marginal | item-difficulty marginal | shared-shock corr | item-difficulty corr | shared-shock P(all fail) | item-difficulty P(all fail) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.3203 | 0.3200 | 0.0059 | -0.0072 | 0.0032 | 0.0032 |
| 0.25 | 0.3229 | 0.3179 | 0.2507 | 0.2487 | 0.0856 | 0.0425 |
| 0.40 | 0.3225 | 0.3196 | 0.4042 | 0.4034 | 0.1326 | 0.0837 |
| 0.55 | 0.3220 | 0.3185 | 0.5479 | 0.5483 | 0.1795 | 0.1343 |
| 0.70 | 0.3239 | 0.3220 | 0.7046 | 0.7031 | 0.2297 | 0.1941 |
| 0.85 | 0.3231 | 0.3179 | 0.8543 | 0.8503 | 0.2769 | 0.2533 |
| 1.00 | 0.3219 | 0.3207 | 1.0000 | 1.0000 | 0.3219 | 0.3207 |

## Cross-runner check against E040

Largest absolute difference from E040's published slopes: `0.0000` across 9 cells.

## Slopes

| family | difficulty | N | shared-shock | R2 | item-difficulty | R2 | change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| structural_diversity | easy | 2 | 0.1018 | 0.9977 | 0.1091 | 0.9973 | +7.2% |
| structural_diversity | easy | 5 | 0.1739 | 0.9989 | 0.2097 | 0.9766 | +20.6% |
| structural_diversity | easy | 10 | 0.1847 | 0.9976 | 0.2307 | 0.9456 | +24.9% |
| structural_diversity | medium | 2 | 0.1997 | 0.9929 | 0.1806 | 0.9930 | -9.6% |
| structural_diversity | medium | 5 | 0.3118 | 0.9980 | 0.3364 | 0.9942 | +7.9% |
| structural_diversity | medium | 10 | 0.3517 | 0.9989 | 0.3787 | 0.9770 | +7.7% |
| structural_diversity | hard | 2 | 0.1931 | 0.9981 | 0.2021 | 0.9789 | +4.7% |
| structural_diversity | hard | 5 | 0.4266 | 0.9987 | 0.4603 | 0.9986 | +7.9% |
| structural_diversity | hard | 10 | 0.5504 | 0.9989 | 0.5709 | 0.9909 | +3.7% |
| diverse_random_verifiers | easy | 2 | 0.1098 | 0.9907 | 0.1159 | 0.9856 | +5.6% |
| diverse_random_verifiers | easy | 5 | 0.1905 | 0.9951 | 0.2145 | 0.9761 | +12.6% |
| diverse_random_verifiers | easy | 10 | 0.1853 | 0.9944 | 0.2316 | 0.9438 | +25.0% |
| diverse_random_verifiers | medium | 2 | 0.1816 | 0.9852 | 0.1806 | 0.9896 | -0.6% |
| diverse_random_verifiers | medium | 5 | 0.3262 | 0.9985 | 0.3510 | 0.9903 | +7.6% |
| diverse_random_verifiers | medium | 10 | 0.3509 | 0.9984 | 0.3807 | 0.9762 | +8.5% |
| diverse_random_verifiers | hard | 2 | 0.1865 | 0.9914 | 0.2070 | 0.9883 | +11.0% |
| diverse_random_verifiers | hard | 5 | 0.4277 | 0.9988 | 0.4657 | 0.9959 | +8.9% |
| diverse_random_verifiers | hard | 10 | 0.5483 | 0.9982 | 0.5682 | 0.9935 | +3.6% |

- curves proportional at R2 >= 0.99: shared-shock 17, item-difficulty 8, of 18
- slope rose in 16 curves, fell in 2
- mean slope change: +8.7% (range -9.6% to +25.0%)
- E040's hedge holds (slopes mostly fall): **False**

## Guardrail

Neither shape is right. E020 measured a real panel and found a blind-spot floor lambda that the shared shock overshoots and the beta-binomial does not have at all -- at n=25 the beta-binomial predicted 0.0313 against a measured 0.0556. So this run does not establish that the diversity advantage is larger than E040 reported. It establishes only that E040's hedge is unsupported in the direction it was stated, and that the true direction is unknown because both candidate shapes miss the feature the one measured panel actually had.
