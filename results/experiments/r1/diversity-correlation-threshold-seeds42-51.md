# E040 diversity advantage against assumed error correlation

Generator: `randomness_lab.r1_correlation_threshold.v1`  
Evidence level: `synthetic_mechanism`

Issue #13 hypothesis 2: at an equal attempt budget, above which assumed worker-error correlation is the heterogeneous arm's advantage over replication no longer resolvable?

## Verified-success-rate delta, diverse arm minus replication

Positive means the heterogeneous arm won at an equal attempt budget.
A cell reads `mean (classification)` where the classification is the
descriptive 95% interval's position relative to zero.

| family | difficulty | N | rho=0 | rho=0.25 | rho=0.4 | rho=0.55 | rho=0.7 | rho=0.85 | rho=1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| diverse_verifiers | easy | 2 | +0.1090 (pos) | +0.0830 (pos) | +0.0615 (pos) | +0.0460 (pos) | +0.0475 (pos) | +0.0165 (unc) | +0.0030 (unc) |
| diverse_verifiers | easy | 5 | +0.1780 (pos) | +0.1430 (pos) | +0.1275 (pos) | +0.0935 (pos) | +0.0605 (pos) | +0.0290 (pos) | +0.0005 (unc) |
| diverse_verifiers | easy | 10 | +0.1840 (pos) | +0.1300 (pos) | +0.1195 (pos) | +0.0945 (pos) | +0.0460 (pos) | +0.0335 (pos) | +0.0060 (unc) |
| diverse_verifiers | hard | 2 | +0.1855 (pos) | +0.1330 (pos) | +0.1215 (pos) | +0.0715 (pos) | +0.0710 (pos) | +0.0385 (pos) | -0.0065 (unc) |
| diverse_verifiers | hard | 5 | +0.4325 (pos) | +0.3185 (pos) | +0.2555 (pos) | +0.1960 (pos) | +0.1220 (pos) | +0.0500 (pos) | -0.0145 (unc) |
| diverse_verifiers | hard | 10 | +0.5385 (pos) | +0.4120 (pos) | +0.3290 (pos) | +0.2610 (pos) | +0.1640 (pos) | +0.1015 (pos) | +0.0235 (unc) |
| diverse_verifiers | medium | 2 | +0.1830 (pos) | +0.1225 (pos) | +0.1110 (pos) | +0.0815 (pos) | +0.0715 (pos) | +0.0450 (pos) | +0.0175 (unc) |
| diverse_verifiers | medium | 5 | +0.3175 (pos) | +0.2485 (pos) | +0.1965 (pos) | +0.1580 (pos) | +0.0955 (pos) | +0.0555 (pos) | +0.0095 (unc) |
| diverse_verifiers | medium | 10 | +0.3420 (pos) | +0.2605 (pos) | +0.2145 (pos) | +0.1675 (pos) | +0.1200 (pos) | +0.0510 (pos) | -0.0050 (unc) |
| structural_diversity | easy | 2 | +0.1030 (pos) | +0.0780 (pos) | +0.0630 (pos) | +0.0405 (pos) | +0.0265 (pos) | +0.0160 (unc) | +0.0000 (unc) |
| structural_diversity | easy | 5 | +0.1745 (pos) | +0.1305 (pos) | +0.1060 (pos) | +0.0800 (pos) | +0.0440 (pos) | +0.0260 (pos) | +0.0000 (unc) |
| structural_diversity | easy | 10 | +0.1835 (pos) | +0.1355 (pos) | +0.1085 (pos) | +0.0935 (pos) | +0.0525 (pos) | +0.0350 (pos) | +0.0000 (unc) |
| structural_diversity | hard | 2 | +0.1870 (pos) | +0.1460 (pos) | +0.1175 (pos) | +0.0970 (pos) | +0.0585 (pos) | +0.0250 (pos) | +0.0000 (unc) |
| structural_diversity | hard | 5 | +0.4265 (pos) | +0.3265 (pos) | +0.2610 (pos) | +0.1830 (pos) | +0.1245 (pos) | +0.0450 (pos) | +0.0000 (unc) |
| structural_diversity | hard | 10 | +0.5400 (pos) | +0.4115 (pos) | +0.3475 (pos) | +0.2410 (pos) | +0.1700 (pos) | +0.0995 (pos) | +0.0000 (unc) |
| structural_diversity | medium | 2 | +0.1910 (pos) | +0.1660 (pos) | +0.1140 (pos) | +0.0805 (pos) | +0.0695 (pos) | +0.0390 (pos) | +0.0000 (unc) |
| structural_diversity | medium | 5 | +0.3060 (pos) | +0.2280 (pos) | +0.1945 (pos) | +0.1405 (pos) | +0.1065 (pos) | +0.0590 (pos) | +0.0000 (unc) |
| structural_diversity | medium | 10 | +0.3445 (pos) | +0.2605 (pos) | +0.2210 (pos) | +0.1650 (pos) | +0.1030 (pos) | +0.0625 (pos) | +0.0000 (unc) |

## Where the advantage stops resolving

| family | difficulty | N | highest resolved rho | first unresolved rho | monotone | slope vs 1-rho | R^2 | resolved at 0.5873 |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| diverse_verifiers | easy | 2 | 0.7 | 0.85 | no | 0.1098 | 0.9907 | yes |
| diverse_verifiers | easy | 5 | 0.85 | 1 | yes | 0.1905 | 0.9951 | yes |
| diverse_verifiers | easy | 10 | 0.85 | 1 | yes | 0.1853 | 0.9944 | yes |
| diverse_verifiers | hard | 2 | 0.85 | 1 | yes | 0.1865 | 0.9914 | yes |
| diverse_verifiers | hard | 5 | 0.85 | 1 | yes | 0.4277 | 0.9988 | yes |
| diverse_verifiers | hard | 10 | 0.85 | 1 | yes | 0.5483 | 0.9982 | yes |
| diverse_verifiers | medium | 2 | 0.85 | 1 | yes | 0.1816 | 0.9852 | yes |
| diverse_verifiers | medium | 5 | 0.85 | 1 | yes | 0.3262 | 0.9985 | yes |
| diverse_verifiers | medium | 10 | 0.85 | 1 | yes | 0.3509 | 0.9984 | yes |
| structural_diversity | easy | 2 | 0.7 | 0.85 | yes | 0.1018 | 0.9977 | yes |
| structural_diversity | easy | 5 | 0.85 | 1 | yes | 0.1739 | 0.9989 | yes |
| structural_diversity | easy | 10 | 0.85 | 1 | yes | 0.1847 | 0.9976 | yes |
| structural_diversity | hard | 2 | 0.85 | 1 | yes | 0.1931 | 0.9981 | yes |
| structural_diversity | hard | 5 | 0.85 | 1 | yes | 0.4266 | 0.9987 | yes |
| structural_diversity | hard | 10 | 0.85 | 1 | yes | 0.5504 | 0.9989 | yes |
| structural_diversity | medium | 2 | 0.85 | 1 | yes | 0.1997 | 0.9929 | yes |
| structural_diversity | medium | 5 | 0.85 | 1 | yes | 0.3118 | 0.9980 | yes |
| structural_diversity | medium | 10 | 0.85 | 1 | yes | 0.3517 | 0.9989 | yes |

## What the verification half of hypothesis 2 is worth

The two arms differ by exactly one thing: `diverse_verifiers` randomizes
verifier assignment over a pool, `structural_diversity` keeps one fixed
verifier. The slope difference is what that buys.

| difficulty | N | worker-diversity slope | + verifier diversity | increment | share |
| --- | ---: | ---: | ---: | ---: | ---: |
| easy | 2 | 0.1018 | 0.1098 | +0.0079 | +7.8% |
| easy | 5 | 0.1739 | 0.1905 | +0.0166 | +9.6% |
| easy | 10 | 0.1847 | 0.1853 | +0.0006 | +0.3% |
| hard | 2 | 0.1931 | 0.1865 | -0.0065 | -3.4% |
| hard | 5 | 0.4266 | 0.4277 | +0.0011 | +0.3% |
| hard | 10 | 0.5504 | 0.5483 | -0.0021 | -0.4% |
| medium | 2 | 0.1997 | 0.1816 | -0.0181 | -9.1% |
| medium | 5 | 0.3118 | 0.3262 | +0.0144 | +4.6% |
| medium | 10 | 0.3517 | 0.3509 | -0.0008 | -0.2% |

## Summary

- curves measured: 18
- curves whose advantage is proportional to retained independence (uncentered R^2 >= 0.99 through the origin): 17
- curves still resolved at the one correlation this repository has measured: 18
- curves resolved at every swept correlation: 0
- cells where randomizing verifier assignment raised the slope: 5 of 9
- largest absolute verifier-assignment increment: 0.0181 (9.6% of the worker-diversity slope in that cell)

## Reference point

The only pairwise error correlation measured in this repository is `0.5873`, on a 25-model verifier panel, not coding workers (`experiments/E017-item-difficulty-and-quorum.md`). E017 also found that a flat shared-shock model at this correlation understates the joint-failure tail by about 1.71x, so it is not a sufficient statistic and this runner's parameterization is the optimistic one.

## Guardrail

The swept quantity is a parameter of a synthetic shared-shock environment, not a measurement of real coding agents. A threshold here bounds when the assumption carries the result; it does not establish that heterogeneous coding agents beat replicated ones.
