# R1 collective-capability scaling

**Issue:** #13
**Evidence:** synthetic mechanism, not real coding-agent performance

## Question

The original R1 experiment compares orchestration structures at one swarm size.
This extension asks the narrower scaling question:

> As N moves through 1, 2, 5, and 10, what verified-success increment is
> observed, what extra compute and verifier attention does it consume, and does
> the answer change with controlled task difficulty?

It is designed to retain saturation and negative marginal returns. It does not
fit a real-world scaling law from invented worker probabilities.

## Design

The reference run uses 200 synthetic tasks for each of 10 deterministic seeds
(42 through 51) at three worker-quality assumptions:

| Difficulty label | Synthetic base-success probability |
| --- | ---: |
| easy | 0.82 |
| medium | 0.65 |
| hard | 0.45 |

Three curves share the same one-worker baseline:

1. homogeneous replication;
2. structural diversity with configured worker-error correlation 0.25;
3. structural diversity plus randomized verifier assignment.

At each N, the homogeneous and diversity conditions have equal attempt counts.
The committed report explicitly checks equality of the synthetic compute and
attention proxies. Comparisons use paired seed indices and retain every raw
trial metric.

The N comparisons are not common-random-number task replays: changing the
number of profiles changes random-number consumption inside R1. They are paired
deterministic seeded trials, not identical hidden task instances. A real
prospective experiment must freeze actual tasks, candidate budgets, and hidden
verification before execution.

## Outputs

- [machine-readable seeded results](../../results/experiments/r1/collective-scaling-seeds42-51.json.gz)
- [compact generated table](../../results/experiments/r1/collective-scaling-seeds42-51.md)
- [runner](../../randomness_lab/r1_scaling.py)

Reproduce from the repository root:

    python -m randomness_lab.r1_scaling \
      --tasks 200 \
      --trials 10 \
      --swarm-sizes 1,2,5,10 \
      --difficulties easy:0.82,medium:0.65,hard:0.45 \
      --seed 42 \
      --output /tmp/r1-scaling.json.gz \
      --report /tmp/r1-scaling.md

The output reports, for every adjacent N pair:

- verified-success-rate delta and descriptive 95% interval;
- verified utility per synthetic resource cost;
- regression and security-failure deltas;
- added compute and verifier-attention proxies;
- success-rate points per added worker and per added compute unit.

The intervals are descriptive normal approximations over 10 seeds. They are not
a power calculation or a substitute for task-level hierarchical analysis.

## Reference observations

Under the frozen assumptions, homogeneous replication gained clearly from 1 to
2 workers at every difficulty, then its 2-to-5 and 5-to-10 success increments
were statistically ambiguous. For the hard condition, the homogeneous mean
change from 5 to 10 was negative (-0.0300, interval [-0.0636, 0.0036]).

Structural diversity retained positive success increments longer. At hard
difficulty, its mean increments were +0.2030 (1 to 2), +0.1980 (2 to 5), and
+0.0550 (5 to 10). These are simulator observations under an assumed 0.25 error
correlation, not estimates of real model diversity.

All families paid approximately linearly for more attempts. Consequently,
verified utility per synthetic unit cost fell sharply as N increased even when
absolute success rose. The mechanism therefore demonstrates the distinction
between higher success probability and another worker being cost-effective.

At equal N and attempt count, the synthetic diversity conditions beat the
maximally correlated homogeneous condition in this frozen run. That result is
partly constructed by the correlation assumptions; it must not be cited as
evidence that heterogeneous coding agents outperform replicated models.

## Issue #13 evidence audit

| Required configuration or dimension | Current evidence after this change |
| --- | --- |
| one strong coding model | missing measured run |
| one small model | missing measured run |
| 5 homogeneous small agents | synthetic proxy only |
| 10 homogeneous small agents | synthetic proxy only |
| 10 heterogeneous agents | synthetic structural-diversity proxy only |
| planner + implementers + tester + reviewer | missing |
| task-DAG team + independent verification | missing |
| multiple difficulty levels and seeds | synthetic only |
| hidden tests / regressions / security defects | synthetic outcomes only |
| real compute, wall time, reviewer minutes | missing; proxies only |
| messages, bytes, duplicated work | missing |
| pairwise error correlation | configured/mechanism-level; real measurement missing |
| marginal value of N+1 | implemented for synthetic R1 curves |

The repository has adjacent scheduling, evolutionary-orchestration,
verification-correlation, and benchmark-contract work. Those artifacts answer
important mechanism questions, but they are not exchangeable observations from
one preregistered task corpus and therefore cannot be pooled into an empirical
coding-agent scaling curve.

## Closure boundary

Issue #13 remains open. The minimum real experiment still needs a prospectively
frozen held-out software-task corpus, all seven configurations, fixed and fully
recorded budgets, independent verification, retained failures, and analysis of
the requested real metrics. This runner supplies analysis mechanics and a
machine-readable gap ledger; it does not manufacture the missing observations.

## Community impact

Contributors now have one deterministic command and one explicit gap table to
extend. A future real run can challenge the synthetic assumptions rather than
reverse-engineering which N comparisons and cost questions were intended.
