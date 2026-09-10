# R1 verifier panel frontier

Generator: `randomness_lab.r1_panel_frontier.v1`.
Swarm size 5, 250 tasks, seeds (42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65).

> This is a simulator. Worker quality, verifier sensitivity, both correlations and the attention costs are invented parameters. A cell here is evidence about the model, not about real coding agents. Read cells, not the mean of cells: the two dependence shapes move in opposite directions in parts of this grid, so any average over shape cancels a real effect. And read the decisive counts, not the raw ones: most raw billing reversals are cells sitting near a tie, which is why the raw statistic reads 85% at two seeds and 45-52% at sixteen to thirty-two.

## Does the billing change the verdict?

Of 80 (panel size, need, shape, correlation) cells, **36** reverse whether the panel beats a single verifier when the billing changes.

| k | need | shape | rho | per_verifier | per_candidate |
| ---: | ---: | --- | ---: | --- | --- |
| 3 | 1 | item_difficulty | 0.0 | False | True |
| 3 | 1 | item_difficulty | 0.25 | False | True |
| 3 | 1 | item_difficulty | 0.5875 | False | True |
| 3 | 1 | item_difficulty | 0.75 | False | True |
| 3 | 1 | shared_shock | 0.0 | False | True |
| 3 | 1 | shared_shock | 0.25 | False | True |
| 3 | 1 | shared_shock | 0.75 | False | True |
| 3 | 2 | item_difficulty | 0.0 | False | True |

## Shape separation, cell by cell

Never averaged over shape: the two move in opposite directions in parts of this grid, so a mean over shape cancels a real effect.

| k | need | rho | billing | shared_shock | item_difficulty | delta |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 3 | 1 | 0.0 | per_candidate | 0.5542 | 0.5542 | +0.0000 |
| 3 | 1 | 0.0 | per_verifier | 0.4690 | 0.4690 | +0.0000 |
| 3 | 1 | 0.25 | per_candidate | 0.5526 | 0.5565 | +0.0039 |
| 3 | 1 | 0.25 | per_verifier | 0.4676 | 0.4709 | +0.0033 |
| 3 | 1 | 0.5875 | per_candidate | 0.5392 | 0.5476 | +0.0083 |
| 3 | 1 | 0.5875 | per_verifier | 0.4563 | 0.4633 | +0.0071 |
| 3 | 1 | 0.75 | per_candidate | 0.5453 | 0.5470 | +0.0017 |
| 3 | 1 | 0.75 | per_verifier | 0.4614 | 0.4628 | +0.0014 |
| 3 | 1 | 1.0 | per_candidate | 0.5420 | 0.5418 | -0.0002 |
| 3 | 1 | 1.0 | per_verifier | 0.4586 | 0.4585 | -0.0001 |
| 3 | 2 | 0.0 | per_candidate | 0.5523 | 0.5523 | +0.0000 |
| 3 | 2 | 0.0 | per_verifier | 0.4673 | 0.4673 | +0.0000 |
| 3 | 2 | 0.25 | per_candidate | 0.5514 | 0.5485 | -0.0029 |
| 3 | 2 | 0.25 | per_verifier | 0.4665 | 0.4641 | -0.0024 |
| 3 | 2 | 0.5875 | per_candidate | 0.5391 | 0.5400 | +0.0009 |
| 3 | 2 | 0.5875 | per_verifier | 0.4562 | 0.4569 | +0.0008 |
| 3 | 2 | 0.75 | per_candidate | 0.5450 | 0.5430 | -0.0020 |
| 3 | 2 | 0.75 | per_verifier | 0.4612 | 0.4595 | -0.0017 |
| 3 | 2 | 1.0 | per_candidate | 0.5420 | 0.5418 | -0.0002 |
| 3 | 2 | 1.0 | per_verifier | 0.4586 | 0.4585 | -0.0001 |
| 3 | 3 | 0.0 | per_candidate | 0.5053 | 0.5053 | +0.0000 |
| 3 | 3 | 0.0 | per_verifier | 0.4276 | 0.4276 | +0.0000 |
| 3 | 3 | 0.25 | per_candidate | 0.5135 | 0.5185 | +0.0050 |
| 3 | 3 | 0.25 | per_verifier | 0.4345 | 0.4387 | +0.0042 |
