# R1 verifier panel frontier

Generator: `randomness_lab.r1_panel_frontier.v1`.
Swarm size 5, 250 tasks, seeds (42, 43, 44).

> This is a simulator. Worker quality, verifier sensitivity, both correlations and the attention costs are invented parameters. A cell here is evidence about the model, not about real coding agents. Read cells, not the mean of cells: the two dependence shapes move in opposite directions in parts of this grid, so any average over shape cancels a real effect. And read the decisive counts, not the raw ones: most raw billing reversals are cells sitting near a tie, which is why the raw statistic reads 85% at two seeds and 45-52% at sixteen to thirty-two.

## Does the billing change the verdict?

Of 80 (panel size, need, shape, correlation) cells, **58** reverse whether the panel beats a single verifier when the billing changes.

| k | need | shape | rho | per_verifier | per_candidate |
| ---: | ---: | --- | ---: | --- | --- |
| 3 | 1 | item_difficulty | 0.0 | False | True |
| 3 | 1 | item_difficulty | 0.25 | False | True |
| 3 | 1 | item_difficulty | 0.5875 | False | True |
| 3 | 1 | item_difficulty | 0.75 | False | True |
| 3 | 1 | item_difficulty | 1.0 | False | True |
| 3 | 1 | shared_shock | 0.0 | False | True |
| 3 | 1 | shared_shock | 0.25 | False | True |
| 3 | 1 | shared_shock | 0.5875 | False | True |

## Shape separation, cell by cell

Never averaged over shape: the two move in opposite directions in parts of this grid, so a mean over shape cancels a real effect.

| k | need | rho | billing | shared_shock | item_difficulty | delta |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 3 | 1 | 0.0 | per_candidate | 0.5697 | 0.5697 | +0.0000 |
| 3 | 1 | 0.0 | per_verifier | 0.4821 | 0.4821 | +0.0000 |
| 3 | 1 | 0.25 | per_candidate | 0.5927 | 0.5515 | -0.0412 |
| 3 | 1 | 0.25 | per_verifier | 0.5015 | 0.4667 | -0.0349 |
| 3 | 1 | 0.5875 | per_candidate | 0.5527 | 0.5709 | +0.0182 |
| 3 | 1 | 0.5875 | per_verifier | 0.4677 | 0.4831 | +0.0154 |
| 3 | 1 | 0.75 | per_candidate | 0.5297 | 0.5745 | +0.0448 |
| 3 | 1 | 0.75 | per_verifier | 0.4482 | 0.4862 | +0.0379 |
| 3 | 1 | 1.0 | per_candidate | 0.5285 | 0.5467 | +0.0182 |
| 3 | 1 | 1.0 | per_verifier | 0.4472 | 0.4626 | +0.0154 |
| 3 | 2 | 0.0 | per_candidate | 0.5685 | 0.5685 | +0.0000 |
| 3 | 2 | 0.0 | per_verifier | 0.4810 | 0.4810 | +0.0000 |
| 3 | 2 | 0.25 | per_candidate | 0.5915 | 0.5491 | -0.0424 |
| 3 | 2 | 0.25 | per_verifier | 0.5005 | 0.4646 | -0.0359 |
| 3 | 2 | 0.5875 | per_candidate | 0.5527 | 0.5588 | +0.0061 |
| 3 | 2 | 0.5875 | per_verifier | 0.4677 | 0.4728 | +0.0051 |
| 3 | 2 | 0.75 | per_candidate | 0.5297 | 0.5685 | +0.0388 |
| 3 | 2 | 0.75 | per_verifier | 0.4482 | 0.4810 | +0.0328 |
| 3 | 2 | 1.0 | per_candidate | 0.5285 | 0.5467 | +0.0182 |
| 3 | 2 | 1.0 | per_verifier | 0.4472 | 0.4626 | +0.0154 |
| 3 | 3 | 0.0 | per_candidate | 0.5127 | 0.5127 | +0.0000 |
| 3 | 3 | 0.0 | per_verifier | 0.4338 | 0.4338 | +0.0000 |
| 3 | 3 | 0.25 | per_candidate | 0.5564 | 0.5176 | -0.0388 |
| 3 | 3 | 0.25 | per_verifier | 0.4708 | 0.4379 | -0.0328 |
