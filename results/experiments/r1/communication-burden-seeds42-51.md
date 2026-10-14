# R1 communication burden (structural)

Evidence level: **synthetic mechanism only**. Message counts are **structural, not measured bytes**.

Percentile bootstrap intervals over the lab's deterministic seeds; descriptive, not hypothesis tests.

## Structural messages per task

| N | flat | role_specialized | task_dag | all-to-all reference |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 3 | 3 | 0 |
| 2 | 6 | 5 | 6 | 2 |
| 5 | 15 | 11 | 15 | 20 |
| 10 | 30 | 21 | 30 | 90 |

## Success per message, by difficulty, family, and topology

| Difficulty | Family | Topology | N | Messages | Success | Success per message | Elasticity |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| easy | diverse_verifiers | flat | 1 | 3 | 0.7175 [0.7010, 0.7335] | 0.2392 [0.2337, 0.2445] | 0.111 [0.105, 0.118] |
| easy | diverse_verifiers | flat | 2 | 6 | 0.8875 [0.8780, 0.8960] | 0.1479 [0.1463, 0.1493] |  |
| easy | diverse_verifiers | flat | 5 | 15 | 0.9530 [0.9445, 0.9610] | 0.0635 [0.0630, 0.0641] |  |
| easy | diverse_verifiers | flat | 10 | 30 | 0.9385 [0.9270, 0.9480] | 0.0313 [0.0309, 0.0316] |  |
| easy | diverse_verifiers | role_specialized | 1 | 3 | 0.7175 [0.7010, 0.7335] | 0.2392 [0.2337, 0.2445] | 0.110 [0.100, 0.120] |
| easy | diverse_verifiers | role_specialized | 2 | 5 | 0.7155 [0.6985, 0.7305] | 0.1431 [0.1397, 0.1461] |  |
| easy | diverse_verifiers | role_specialized | 5 | 11 | 0.8550 [0.8425, 0.8670] | 0.0777 [0.0766, 0.0788] |  |
| easy | diverse_verifiers | role_specialized | 10 | 21 | 0.8565 [0.8420, 0.8705] | 0.0408 [0.0401, 0.0415] |  |
| easy | diverse_verifiers | task_dag | 1 | 3 | 0.7175 [0.7010, 0.7335] | 0.2392 [0.2337, 0.2445] | 0.138 [0.128, 0.150] |
| easy | diverse_verifiers | task_dag | 2 | 6 | 0.7225 [0.7055, 0.7365] | 0.1204 [0.1176, 0.1227] |  |
| easy | diverse_verifiers | task_dag | 5 | 15 | 0.9195 [0.9080, 0.9300] | 0.0613 [0.0605, 0.0620] |  |
| easy | diverse_verifiers | task_dag | 10 | 30 | 0.9420 [0.9305, 0.9530] | 0.0314 [0.0310, 0.0318] |  |
| easy | homogeneous | flat | 1 | 3 | 0.7175 [0.7025, 0.7325] | 0.2392 [0.2342, 0.2442] | 0.046 [0.036, 0.056] |
| easy | homogeneous | flat | 2 | 6 | 0.8045 [0.7845, 0.8220] | 0.1341 [0.1308, 0.1370] |  |
| easy | homogeneous | flat | 5 | 15 | 0.8100 [0.8010, 0.8190] | 0.0540 [0.0534, 0.0546] |  |
| easy | homogeneous | flat | 10 | 30 | 0.8085 [0.7935, 0.8250] | 0.0270 [0.0265, 0.0275] |  |
| easy | homogeneous | role_specialized | 1 | 3 | 0.7175 [0.7025, 0.7325] | 0.2392 [0.2342, 0.2442] | 0.067 [0.048, 0.085] |
| easy | homogeneous | role_specialized | 2 | 5 | 0.7165 [0.6955, 0.7385] | 0.1433 [0.1391, 0.1477] |  |
| easy | homogeneous | role_specialized | 5 | 11 | 0.8055 [0.7945, 0.8175] | 0.0732 [0.0722, 0.0743] |  |
| easy | homogeneous | role_specialized | 10 | 21 | 0.7970 [0.7785, 0.8160] | 0.0380 [0.0371, 0.0389] |  |
| easy | homogeneous | task_dag | 1 | 3 | 0.7175 [0.7025, 0.7325] | 0.2392 [0.2342, 0.2442] | 0.068 [0.055, 0.080] |
| easy | homogeneous | task_dag | 2 | 6 | 0.7085 [0.6900, 0.7265] | 0.1181 [0.1150, 0.1211] |  |
| easy | homogeneous | task_dag | 5 | 15 | 0.8020 [0.7895, 0.8150] | 0.0535 [0.0526, 0.0543] |  |
| easy | homogeneous | task_dag | 10 | 30 | 0.8180 [0.8055, 0.8295] | 0.0273 [0.0269, 0.0276] |  |
| easy | structural_diversity | flat | 1 | 3 | 0.7175 [0.7020, 0.7330] | 0.2392 [0.2340, 0.2443] | 0.113 [0.103, 0.121] |
| easy | structural_diversity | flat | 2 | 6 | 0.8825 [0.8650, 0.8965] | 0.1471 [0.1442, 0.1494] |  |
| easy | structural_diversity | flat | 5 | 15 | 0.9405 [0.9320, 0.9480] | 0.0627 [0.0621, 0.0632] |  |
| easy | structural_diversity | flat | 10 | 30 | 0.9440 [0.9375, 0.9505] | 0.0315 [0.0312, 0.0317] |  |
| easy | structural_diversity | role_specialized | 1 | 3 | 0.7175 [0.7020, 0.7330] | 0.2392 [0.2340, 0.2443] | 0.107 [0.097, 0.118] |
| easy | structural_diversity | role_specialized | 2 | 5 | 0.7125 [0.6900, 0.7325] | 0.1425 [0.1380, 0.1465] |  |
| easy | structural_diversity | role_specialized | 5 | 11 | 0.8405 [0.8265, 0.8545] | 0.0764 [0.0751, 0.0777] |  |
| easy | structural_diversity | role_specialized | 10 | 21 | 0.8550 [0.8440, 0.8665] | 0.0407 [0.0402, 0.0413] |  |
| easy | structural_diversity | task_dag | 1 | 3 | 0.7175 [0.7020, 0.7330] | 0.2392 [0.2340, 0.2443] | 0.138 [0.129, 0.149] |
| easy | structural_diversity | task_dag | 2 | 6 | 0.7045 [0.6895, 0.7180] | 0.1174 [0.1149, 0.1197] |  |
| easy | structural_diversity | task_dag | 5 | 15 | 0.9045 [0.8925, 0.9175] | 0.0603 [0.0595, 0.0612] |  |
| easy | structural_diversity | task_dag | 10 | 30 | 0.9390 [0.9315, 0.9480] | 0.0313 [0.0311, 0.0316] |  |
| medium | diverse_verifiers | flat | 1 | 3 | 0.5745 [0.5460, 0.6025] | 0.1915 [0.1820, 0.2008] | 0.195 [0.175, 0.216] |
| medium | diverse_verifiers | flat | 2 | 6 | 0.7490 [0.7380, 0.7615] | 0.1248 [0.1230, 0.1269] |  |
| medium | diverse_verifiers | flat | 5 | 15 | 0.8950 [0.8800, 0.9100] | 0.0597 [0.0587, 0.0607] |  |
| medium | diverse_verifiers | flat | 10 | 30 | 0.8985 [0.8840, 0.9145] | 0.0300 [0.0295, 0.0305] |  |
| medium | diverse_verifiers | role_specialized | 1 | 3 | 0.5745 [0.5460, 0.6025] | 0.1915 [0.1820, 0.2008] | 0.170 [0.148, 0.190] |
| medium | diverse_verifiers | role_specialized | 2 | 5 | 0.5695 [0.5515, 0.5890] | 0.1139 [0.1103, 0.1178] |  |
| medium | diverse_verifiers | role_specialized | 5 | 11 | 0.7405 [0.7155, 0.7625] | 0.0673 [0.0650, 0.0693] |  |
| medium | diverse_verifiers | role_specialized | 10 | 21 | 0.7565 [0.7425, 0.7705] | 0.0360 [0.0354, 0.0367] |  |
| medium | diverse_verifiers | task_dag | 1 | 3 | 0.5745 [0.5460, 0.6025] | 0.1915 [0.1820, 0.2008] | 0.216 [0.198, 0.236] |
| medium | diverse_verifiers | task_dag | 2 | 6 | 0.5765 [0.5455, 0.6070] | 0.0961 [0.0909, 0.1012] |  |
| medium | diverse_verifiers | task_dag | 5 | 15 | 0.8325 [0.8205, 0.8440] | 0.0555 [0.0547, 0.0563] |  |
| medium | diverse_verifiers | task_dag | 10 | 30 | 0.8785 [0.8625, 0.8950] | 0.0293 [0.0287, 0.0298] |  |
| medium | homogeneous | flat | 1 | 3 | 0.5745 [0.5475, 0.6040] | 0.1915 [0.1825, 0.2013] | 0.045 [0.027, 0.063] |
| medium | homogeneous | flat | 2 | 6 | 0.6265 [0.6050, 0.6445] | 0.1044 [0.1008, 0.1074] |  |
| medium | homogeneous | flat | 5 | 15 | 0.6465 [0.6270, 0.6645] | 0.0431 [0.0418, 0.0443] |  |
| medium | homogeneous | flat | 10 | 30 | 0.6380 [0.6250, 0.6510] | 0.0213 [0.0208, 0.0217] |  |
| medium | homogeneous | role_specialized | 1 | 3 | 0.5745 [0.5475, 0.6040] | 0.1915 [0.1825, 0.2013] | 0.059 [0.029, 0.089] |
| medium | homogeneous | role_specialized | 2 | 5 | 0.5585 [0.5385, 0.5800] | 0.1117 [0.1077, 0.1160] |  |
| medium | homogeneous | role_specialized | 5 | 11 | 0.6335 [0.6115, 0.6545] | 0.0576 [0.0556, 0.0595] |  |
| medium | homogeneous | role_specialized | 10 | 21 | 0.6230 [0.6065, 0.6395] | 0.0297 [0.0289, 0.0305] |  |
| medium | homogeneous | task_dag | 1 | 3 | 0.5745 [0.5475, 0.6040] | 0.1915 [0.1825, 0.2013] | 0.063 [0.037, 0.089] |
| medium | homogeneous | task_dag | 2 | 6 | 0.5455 [0.5365, 0.5530] | 0.0909 [0.0894, 0.0922] |  |
| medium | homogeneous | task_dag | 5 | 15 | 0.6435 [0.6315, 0.6570] | 0.0429 [0.0421, 0.0438] |  |
| medium | homogeneous | task_dag | 10 | 30 | 0.6360 [0.6115, 0.6560] | 0.0212 [0.0204, 0.0219] |  |
| medium | structural_diversity | flat | 1 | 3 | 0.5745 [0.5480, 0.6025] | 0.1915 [0.1827, 0.2008] | 0.183 [0.166, 0.200] |
| medium | structural_diversity | flat | 2 | 6 | 0.7925 [0.7780, 0.8090] | 0.1321 [0.1297, 0.1348] |  |
| medium | structural_diversity | flat | 5 | 15 | 0.8745 [0.8600, 0.8890] | 0.0583 [0.0573, 0.0593] |  |
| medium | structural_diversity | flat | 10 | 30 | 0.8985 [0.8840, 0.9105] | 0.0300 [0.0295, 0.0303] |  |
| medium | structural_diversity | role_specialized | 1 | 3 | 0.5745 [0.5480, 0.6025] | 0.1915 [0.1827, 0.2008] | 0.155 [0.132, 0.176] |
| medium | structural_diversity | role_specialized | 2 | 5 | 0.5590 [0.5420, 0.5745] | 0.1118 [0.1084, 0.1149] |  |
| medium | structural_diversity | role_specialized | 5 | 11 | 0.7275 [0.7130, 0.7415] | 0.0661 [0.0648, 0.0674] |  |
| medium | structural_diversity | role_specialized | 10 | 21 | 0.7305 [0.7140, 0.7490] | 0.0348 [0.0340, 0.0357] |  |
| medium | structural_diversity | task_dag | 1 | 3 | 0.5745 [0.5480, 0.6025] | 0.1915 [0.1827, 0.2008] | 0.215 [0.195, 0.234] |
| medium | structural_diversity | task_dag | 2 | 6 | 0.5735 [0.5560, 0.5940] | 0.0956 [0.0927, 0.0990] |  |
| medium | structural_diversity | task_dag | 5 | 15 | 0.8235 [0.8110, 0.8355] | 0.0549 [0.0541, 0.0557] |  |
| medium | structural_diversity | task_dag | 10 | 30 | 0.8805 [0.8705, 0.8905] | 0.0294 [0.0290, 0.0297] |  |
| hard | diverse_verifiers | flat | 1 | 3 | 0.3805 [0.3685, 0.3935] | 0.1268 [0.1228, 0.1312] | 0.342 [0.327, 0.355] |
| hard | diverse_verifiers | flat | 2 | 6 | 0.5705 [0.5495, 0.5905] | 0.0951 [0.0916, 0.0984] |  |
| hard | diverse_verifiers | flat | 5 | 15 | 0.7735 [0.7610, 0.7895] | 0.0516 [0.0507, 0.0526] |  |
| hard | diverse_verifiers | flat | 10 | 30 | 0.8370 [0.8205, 0.8520] | 0.0279 [0.0274, 0.0284] |  |
| hard | diverse_verifiers | role_specialized | 1 | 3 | 0.3805 [0.3685, 0.3935] | 0.1268 [0.1228, 0.1312] | 0.262 [0.244, 0.280] |
| hard | diverse_verifiers | role_specialized | 2 | 5 | 0.3725 [0.3615, 0.3830] | 0.0745 [0.0723, 0.0766] |  |
| hard | diverse_verifiers | role_specialized | 5 | 11 | 0.5750 [0.5500, 0.6035] | 0.0523 [0.0500, 0.0549] |  |
| hard | diverse_verifiers | role_specialized | 10 | 21 | 0.5780 [0.5565, 0.5990] | 0.0275 [0.0265, 0.0285] |  |
| hard | diverse_verifiers | task_dag | 1 | 3 | 0.3805 [0.3685, 0.3935] | 0.1268 [0.1228, 0.1312] | 0.363 [0.345, 0.379] |
| hard | diverse_verifiers | task_dag | 2 | 6 | 0.4085 [0.3920, 0.4255] | 0.0681 [0.0653, 0.0709] |  |
| hard | diverse_verifiers | task_dag | 5 | 15 | 0.6865 [0.6735, 0.6990] | 0.0458 [0.0449, 0.0466] |  |
| hard | diverse_verifiers | task_dag | 10 | 30 | 0.8125 [0.7985, 0.8295] | 0.0271 [0.0266, 0.0276] |  |
| hard | homogeneous | flat | 1 | 3 | 0.3805 [0.3680, 0.3925] | 0.1268 [0.1227, 0.1308] | 0.046 [0.030, 0.064] |
| hard | homogeneous | flat | 2 | 6 | 0.4375 [0.4260, 0.4510] | 0.0729 [0.0710, 0.0752] |  |
| hard | homogeneous | flat | 5 | 15 | 0.4550 [0.4355, 0.4760] | 0.0303 [0.0290, 0.0317] |  |
| hard | homogeneous | flat | 10 | 30 | 0.4250 [0.4050, 0.4500] | 0.0142 [0.0135, 0.0150] |  |
| hard | homogeneous | role_specialized | 1 | 3 | 0.3805 [0.3680, 0.3925] | 0.1268 [0.1227, 0.1308] | 0.085 [0.036, 0.132] |
| hard | homogeneous | role_specialized | 2 | 5 | 0.3935 [0.3710, 0.4145] | 0.0787 [0.0742, 0.0829] |  |
| hard | homogeneous | role_specialized | 5 | 11 | 0.4545 [0.4370, 0.4705] | 0.0413 [0.0397, 0.0428] |  |
| hard | homogeneous | role_specialized | 10 | 21 | 0.4390 [0.4040, 0.4720] | 0.0209 [0.0192, 0.0225] |  |
| hard | homogeneous | task_dag | 1 | 3 | 0.3805 [0.3680, 0.3925] | 0.1268 [0.1227, 0.1308] | 0.098 [0.078, 0.119] |
| hard | homogeneous | task_dag | 2 | 6 | 0.3755 [0.3495, 0.3950] | 0.0626 [0.0583, 0.0658] |  |
| hard | homogeneous | task_dag | 5 | 15 | 0.4375 [0.4105, 0.4635] | 0.0292 [0.0274, 0.0309] |  |
| hard | homogeneous | task_dag | 10 | 30 | 0.4645 [0.4485, 0.4815] | 0.0155 [0.0149, 0.0161] |  |
| hard | structural_diversity | flat | 1 | 3 | 0.3805 [0.3680, 0.3935] | 0.1268 [0.1227, 0.1312] | 0.340 [0.323, 0.358] |
| hard | structural_diversity | flat | 2 | 6 | 0.5835 [0.5595, 0.6050] | 0.0973 [0.0932, 0.1008] |  |
| hard | structural_diversity | flat | 5 | 15 | 0.7815 [0.7665, 0.7995] | 0.0521 [0.0511, 0.0533] |  |
| hard | structural_diversity | flat | 10 | 30 | 0.8365 [0.8260, 0.8470] | 0.0279 [0.0275, 0.0282] |  |
| hard | structural_diversity | role_specialized | 1 | 3 | 0.3805 [0.3680, 0.3935] | 0.1268 [0.1227, 0.1312] | 0.267 [0.239, 0.294] |
| hard | structural_diversity | role_specialized | 2 | 5 | 0.3855 [0.3670, 0.4050] | 0.0771 [0.0734, 0.0810] |  |
| hard | structural_diversity | role_specialized | 5 | 11 | 0.5660 [0.5460, 0.5845] | 0.0515 [0.0496, 0.0531] |  |
| hard | structural_diversity | role_specialized | 10 | 21 | 0.5955 [0.5745, 0.6180] | 0.0284 [0.0274, 0.0294] |  |
| hard | structural_diversity | task_dag | 1 | 3 | 0.3805 [0.3680, 0.3935] | 0.1268 [0.1227, 0.1312] | 0.372 [0.354, 0.390] |
| hard | structural_diversity | task_dag | 2 | 6 | 0.3850 [0.3665, 0.4015] | 0.0642 [0.0611, 0.0669] |  |
| hard | structural_diversity | task_dag | 5 | 15 | 0.6985 [0.6850, 0.7125] | 0.0466 [0.0457, 0.0475] |  |
| hard | structural_diversity | task_dag | 10 | 30 | 0.8095 [0.7865, 0.8290] | 0.0270 [0.0262, 0.0276] |  |

## Scope boundary

Message counts are structural, not measured bytes, derived from a stated counting rule over three synthetic topology definitions. Success rates are synthetic. Percentile bootstrap intervals over the lab's seeds are descriptive, not multiplicity adjusted, and the ordering of topologies by message count is a property of the counting rule. Nothing here measures real agents or real communication and it cannot close issue 13.

Duplicated attempts: not computed for the R1 result (the R1 result holds per-seed aggregate metrics only; no candidate identity or per-task trace exists to compare).
