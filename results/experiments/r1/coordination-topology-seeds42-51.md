# R1 collective-capability scaling reference

Evidence level: **synthetic mechanism only**.

## Marginal verified-success changes

| Difficulty | Family | N | Mean delta | 95% interval | Class |
| --- | --- | ---: | ---: | --- | --- |
| easy | homogeneous | 1→2 | 0.0870 | [0.0604, 0.1136] | positive |
| easy | homogeneous | 2→5 | 0.0055 | [-0.0200, 0.0310] | uncertain |
| easy | homogeneous | 5→10 | -0.0015 | [-0.0238, 0.0208] | uncertain |
| easy | structural_diversity | 1→2 | 0.1650 | [0.1369, 0.1931] | positive |
| easy | structural_diversity | 2→5 | 0.0580 | [0.0406, 0.0754] | positive |
| easy | structural_diversity | 5→10 | 0.0035 | [-0.0077, 0.0147] | uncertain |
| easy | diverse_verifiers | 1→2 | 0.1700 | [0.1517, 0.1883] | positive |
| easy | diverse_verifiers | 2→5 | 0.0655 | [0.0545, 0.0765] | positive |
| easy | diverse_verifiers | 5→10 | -0.0145 | [-0.0309, 0.0019] | uncertain |
| medium | homogeneous | 1→2 | 0.0520 | [0.0091, 0.0949] | positive |
| medium | homogeneous | 2→5 | 0.0200 | [-0.0068, 0.0468] | uncertain |
| medium | homogeneous | 5→10 | -0.0085 | [-0.0414, 0.0244] | uncertain |
| medium | structural_diversity | 1→2 | 0.2180 | [0.1838, 0.2522] | positive |
| medium | structural_diversity | 2→5 | 0.0820 | [0.0606, 0.1034] | positive |
| medium | structural_diversity | 5→10 | 0.0240 | [0.0054, 0.0426] | positive |
| medium | diverse_verifiers | 1→2 | 0.1745 | [0.1426, 0.2064] | positive |
| medium | diverse_verifiers | 2→5 | 0.1460 | [0.1256, 0.1664] | positive |
| medium | diverse_verifiers | 5→10 | 0.0035 | [-0.0171, 0.0241] | uncertain |
| hard | homogeneous | 1→2 | 0.0570 | [0.0347, 0.0793] | positive |
| hard | homogeneous | 2→5 | 0.0175 | [-0.0116, 0.0466] | uncertain |
| hard | homogeneous | 5→10 | -0.0300 | [-0.0636, 0.0036] | uncertain |
| hard | structural_diversity | 1→2 | 0.2030 | [0.1782, 0.2278] | positive |
| hard | structural_diversity | 2→5 | 0.1980 | [0.1646, 0.2314] | positive |
| hard | structural_diversity | 5→10 | 0.0550 | [0.0320, 0.0780] | positive |
| hard | diverse_verifiers | 1→2 | 0.1900 | [0.1693, 0.2107] | positive |
| hard | diverse_verifiers | 2→5 | 0.2030 | [0.1785, 0.2275] | positive |
| hard | diverse_verifiers | 5→10 | 0.0635 | [0.0419, 0.0851] | positive |

## Scaling exponent by coordination topology

Ordinary least squares on log(metric) against log(N), fitted per seed.

| Difficulty | Family | Topology | Metric | Exponent | 95% interval | Class |
| --- | --- | --- | --- | ---: | --- | --- |
| easy | homogeneous | flat | verified_success_rate | 0.0459 | [0.0351, 0.0568] | positive |
| easy | homogeneous | role_specialized | verified_success_rate | 0.0569 | [0.0403, 0.0736] | positive |
| easy | homogeneous | task_dag | verified_success_rate | 0.0678 | [0.0547, 0.0810] | positive |
| easy | homogeneous | flat | verified_utility_per_unit_cost | -0.9541 | [-0.9649, -0.9432] | negative |
| easy | homogeneous | role_specialized | verified_utility_per_unit_cost | -0.9431 | [-0.9597, -0.9264] | negative |
| easy | homogeneous | task_dag | verified_utility_per_unit_cost | -0.9322 | [-0.9453, -0.9190] | negative |
| easy | structural_diversity | flat | verified_success_rate | 0.1126 | [0.1032, 0.1220] | positive |
| easy | structural_diversity | role_specialized | verified_success_rate | 0.0907 | [0.0808, 0.1005] | positive |
| easy | structural_diversity | task_dag | verified_success_rate | 0.1384 | [0.1275, 0.1493] | positive |
| easy | structural_diversity | flat | verified_utility_per_unit_cost | -0.8874 | [-0.8968, -0.8780] | negative |
| easy | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.9093 | [-0.9192, -0.8995] | negative |
| easy | structural_diversity | task_dag | verified_utility_per_unit_cost | -0.8616 | [-0.8725, -0.8507] | negative |
| easy | diverse_verifiers | flat | verified_success_rate | 0.1115 | [0.1047, 0.1182] | positive |
| easy | diverse_verifiers | role_specialized | verified_success_rate | 0.0931 | [0.0844, 0.1019] | positive |
| easy | diverse_verifiers | task_dag | verified_success_rate | 0.1383 | [0.1270, 0.1496] | positive |
| easy | diverse_verifiers | flat | verified_utility_per_unit_cost | -0.8885 | [-0.8953, -0.8818] | negative |
| easy | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.9069 | [-0.9156, -0.8981] | negative |
| easy | diverse_verifiers | task_dag | verified_utility_per_unit_cost | -0.8617 | [-0.8730, -0.8504] | negative |
| medium | homogeneous | flat | verified_success_rate | 0.0450 | [0.0258, 0.0642] | positive |
| medium | homogeneous | role_specialized | verified_success_rate | 0.0501 | [0.0228, 0.0774] | positive |
| medium | homogeneous | task_dag | verified_success_rate | 0.0633 | [0.0360, 0.0906] | positive |
| medium | homogeneous | flat | verified_utility_per_unit_cost | -0.9550 | [-0.9742, -0.9358] | negative |
| medium | homogeneous | role_specialized | verified_utility_per_unit_cost | -0.9499 | [-0.9772, -0.9226] | negative |
| medium | homogeneous | task_dag | verified_utility_per_unit_cost | -0.9367 | [-0.9640, -0.9094] | negative |
| medium | structural_diversity | flat | verified_success_rate | 0.1835 | [0.1648, 0.2022] | positive |
| medium | structural_diversity | role_specialized | verified_success_rate | 0.1304 | [0.1096, 0.1512] | positive |
| medium | structural_diversity | task_dag | verified_success_rate | 0.2154 | [0.1944, 0.2364] | positive |
| medium | structural_diversity | flat | verified_utility_per_unit_cost | -0.8165 | [-0.8352, -0.7978] | negative |
| medium | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.8696 | [-0.8904, -0.8488] | negative |
| medium | structural_diversity | task_dag | verified_utility_per_unit_cost | -0.7846 | [-0.8056, -0.7636] | negative |
| medium | diverse_verifiers | flat | verified_success_rate | 0.1953 | [0.1737, 0.2169] | positive |
| medium | diverse_verifiers | role_specialized | verified_success_rate | 0.1434 | [0.1240, 0.1628] | positive |
| medium | diverse_verifiers | task_dag | verified_success_rate | 0.2156 | [0.1956, 0.2356] | positive |
| medium | diverse_verifiers | flat | verified_utility_per_unit_cost | -0.8047 | [-0.8263, -0.7831] | negative |
| medium | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.8566 | [-0.8760, -0.8372] | negative |
| medium | diverse_verifiers | task_dag | verified_utility_per_unit_cost | -0.7844 | [-0.8044, -0.7644] | negative |
| hard | homogeneous | flat | verified_success_rate | 0.0463 | [0.0285, 0.0642] | positive |
| hard | homogeneous | role_specialized | verified_success_rate | 0.0731 | [0.0328, 0.1135] | positive |
| hard | homogeneous | task_dag | verified_success_rate | 0.0976 | [0.0761, 0.1191] | positive |
| hard | homogeneous | flat | verified_utility_per_unit_cost | -0.9537 | [-0.9715, -0.9358] | negative |
| hard | homogeneous | role_specialized | verified_utility_per_unit_cost | -0.9269 | [-0.9672, -0.8865] | negative |
| hard | homogeneous | task_dag | verified_utility_per_unit_cost | -0.9024 | [-0.9239, -0.8809] | negative |
| hard | structural_diversity | flat | verified_success_rate | 0.3396 | [0.3207, 0.3585] | positive |
| hard | structural_diversity | role_specialized | verified_success_rate | 0.2254 | [0.2016, 0.2492] | positive |
| hard | structural_diversity | task_dag | verified_success_rate | 0.3725 | [0.3531, 0.3918] | positive |
| hard | structural_diversity | flat | verified_utility_per_unit_cost | -0.6604 | [-0.6793, -0.6415] | negative |
| hard | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.7746 | [-0.7984, -0.7508] | negative |
| hard | structural_diversity | task_dag | verified_utility_per_unit_cost | -0.6275 | [-0.6469, -0.6082] | negative |
| hard | diverse_verifiers | flat | verified_success_rate | 0.3415 | [0.3262, 0.3568] | positive |
| hard | diverse_verifiers | role_specialized | verified_success_rate | 0.2212 | [0.2044, 0.2380] | positive |
| hard | diverse_verifiers | task_dag | verified_success_rate | 0.3625 | [0.3441, 0.3809] | positive |
| hard | diverse_verifiers | flat | verified_utility_per_unit_cost | -0.6585 | [-0.6738, -0.6432] | negative |
| hard | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.7788 | [-0.7956, -0.7620] | negative |
| hard | diverse_verifiers | task_dag | verified_utility_per_unit_cost | -0.6375 | [-0.6559, -0.6191] | negative |

## Coordination-topology exponent contrast versus flat

Paired per-seed exponent differences at a matched attempt and verification budget.

| Difficulty | Family | Topology | Metric | Exponent delta | 95% interval | Changes exponent |
| --- | --- | --- | --- | ---: | --- | --- |
| easy | homogeneous | role_specialized | verified_success_rate | 0.0110 | [0.0002, 0.0218] | yes |
| easy | homogeneous | task_dag | verified_success_rate | 0.0219 | [0.0119, 0.0320] | yes |
| easy | homogeneous | role_specialized | verified_utility_per_unit_cost | 0.0110 | [0.0002, 0.0218] | yes |
| easy | homogeneous | task_dag | verified_utility_per_unit_cost | 0.0219 | [0.0119, 0.0320] | yes |
| easy | structural_diversity | role_specialized | verified_success_rate | -0.0220 | [-0.0291, -0.0148] | yes |
| easy | structural_diversity | task_dag | verified_success_rate | 0.0258 | [0.0192, 0.0323] | yes |
| easy | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.0220 | [-0.0291, -0.0148] | yes |
| easy | structural_diversity | task_dag | verified_utility_per_unit_cost | 0.0258 | [0.0192, 0.0323] | yes |
| easy | diverse_verifiers | role_specialized | verified_success_rate | -0.0183 | [-0.0267, -0.0100] | yes |
| easy | diverse_verifiers | task_dag | verified_success_rate | 0.0268 | [0.0184, 0.0352] | yes |
| easy | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.0183 | [-0.0267, -0.0100] | yes |
| easy | diverse_verifiers | task_dag | verified_utility_per_unit_cost | 0.0268 | [0.0184, 0.0352] | yes |
| medium | homogeneous | role_specialized | verified_success_rate | 0.0051 | [-0.0072, 0.0175] | no |
| medium | homogeneous | task_dag | verified_success_rate | 0.0183 | [0.0031, 0.0336] | yes |
| medium | homogeneous | role_specialized | verified_utility_per_unit_cost | 0.0051 | [-0.0072, 0.0175] | no |
| medium | homogeneous | task_dag | verified_utility_per_unit_cost | 0.0183 | [0.0031, 0.0336] | yes |
| medium | structural_diversity | role_specialized | verified_success_rate | -0.0531 | [-0.0638, -0.0424] | yes |
| medium | structural_diversity | task_dag | verified_success_rate | 0.0319 | [0.0225, 0.0413] | yes |
| medium | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.0531 | [-0.0638, -0.0424] | yes |
| medium | structural_diversity | task_dag | verified_utility_per_unit_cost | 0.0319 | [0.0225, 0.0413] | yes |
| medium | diverse_verifiers | role_specialized | verified_success_rate | -0.0519 | [-0.0675, -0.0363] | yes |
| medium | diverse_verifiers | task_dag | verified_success_rate | 0.0203 | [0.0076, 0.0330] | yes |
| medium | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.0519 | [-0.0675, -0.0363] | yes |
| medium | diverse_verifiers | task_dag | verified_utility_per_unit_cost | 0.0203 | [0.0076, 0.0330] | yes |
| hard | homogeneous | role_specialized | verified_success_rate | 0.0268 | [-0.0086, 0.0621] | no |
| hard | homogeneous | task_dag | verified_success_rate | 0.0513 | [0.0197, 0.0828] | yes |
| hard | homogeneous | role_specialized | verified_utility_per_unit_cost | 0.0268 | [-0.0086, 0.0621] | no |
| hard | homogeneous | task_dag | verified_utility_per_unit_cost | 0.0513 | [0.0197, 0.0828] | yes |
| hard | structural_diversity | role_specialized | verified_success_rate | -0.1142 | [-0.1401, -0.0883] | yes |
| hard | structural_diversity | task_dag | verified_success_rate | 0.0329 | [0.0196, 0.0461] | yes |
| hard | structural_diversity | role_specialized | verified_utility_per_unit_cost | -0.1142 | [-0.1401, -0.0883] | yes |
| hard | structural_diversity | task_dag | verified_utility_per_unit_cost | 0.0329 | [0.0196, 0.0461] | yes |
| hard | diverse_verifiers | role_specialized | verified_success_rate | -0.1204 | [-0.1354, -0.1054] | yes |
| hard | diverse_verifiers | task_dag | verified_success_rate | 0.0210 | [0.0072, 0.0348] | yes |
| hard | diverse_verifiers | role_specialized | verified_utility_per_unit_cost | -0.1204 | [-0.1354, -0.1054] | yes |
| hard | diverse_verifiers | task_dag | verified_utility_per_unit_cost | 0.0210 | [0.0072, 0.0348] | yes |

## Scope boundary

All worker quality, correlation, defects, and verifier behavior are synthetic. These curves test analysis mechanics and expose negative regimes; they are not empirical scaling laws for coding agents and cannot close issue #13.

The machine-readable companion retains every seeded trial, equal-attempt comparison, cost delta, and the explicit issue #13 coverage gaps.
