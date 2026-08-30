# R1 collective-capability scaling

**Issue:** #13
**Evidence:** synthetic mechanism, not real coding-agent performance

## Question

The original R1 experiment compares orchestration structures at one swarm size.
This extension asks the narrower scaling question:

> As N moves through 1, 2, 5, and 10, what verified-success increment is
> observed, what extra compute and verifier attention does it consume, and does
> the answer change with controlled task difficulty?

A second extension adds issue #13 hypothesis 3, which previously had no test at
all:

> At an identical attempt and verification budget, does the *coordination
> topology* of the group change the scaling exponent?

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

## Coordination-topology arms

Three coordination topologies now run over the same N grid, difficulties, and
seed set. The flat arm is unchanged; the two new arms are budget matched to it.

| Topology | Attempts per task | Verifications per task | Structure |
| --- | ---: | ---: | --- |
| `flat` | N | N | N independent attempts on the whole task, one verification each, first accepted candidate integrated |
| `role_specialized` | N | N | 1 planner attempt gates N-1 implementer attempts; a tester verifies each implementer candidate and a reviewer verifies the tester's pick |
| `task_dag` | N | N | ceil(N/2) attempts on a parent subtask and floor(N/2) on a child subtask blocked until a parent is accepted; blocked downstream budget is re-spent upstream |

Budget matching is the point of the comparison, so it is exact rather than
approximate. Every arm spends N attempt units and N verification units on every
task, including on tasks where a role or a downstream subtask produces nothing:
the reviewer is consulted once per task whether or not the tester passed
anything through, and blocked task-DAG capacity is re-spent on the blocking
parent. The committed run therefore records equal synthetic compute, equal
verifier attention, and equal parallel latency for all three arms at every cell,
and the tests assert it.

The arms are also *neutrally calibrated*, so that no topology is handed an
assumed quality advantage. Per-stage success, hidden-test, regression, and
security probabilities are split so that one clean serial chain reproduces the
flat single-worker candidate distribution exactly: a stage draws success at
`q**(1/stages)` and a defect at `1 - (1 - p)**(1/stages)`. A team of one has no
coordination structure, so at N=1 all three topologies share the flat
single-worker baseline cell.

The N comparisons are not common-random-number task replays: changing the
number of profiles changes random-number consumption inside R1. They are paired
deterministic seeded trials, not identical hidden task instances. A real
prospective experiment must freeze actual tasks, candidate budgets, and hidden
verification before execution.

## Outputs

- [machine-readable seeded results, flat arm](../../results/experiments/r1/collective-scaling-seeds42-51.json.gz)
- [compact generated table, flat arm](../../results/experiments/r1/collective-scaling-seeds42-51.md)
- [machine-readable seeded results, three topologies](../../results/experiments/r1/coordination-topology-seeds42-51.json.gz)
- [compact generated table, three topologies](../../results/experiments/r1/coordination-topology-seeds42-51.md)
- [machine-readable seeded results, correlation sweep](../../results/experiments/r1/diversity-correlation-threshold-seeds42-51.json.gz)
- [compact generated table, correlation sweep](../../results/experiments/r1/diversity-correlation-threshold-seeds42-51.md)
- [runner](../../randomness_lab/r1_scaling.py)
- [correlation-sweep runner](../../randomness_lab/r1_correlation_threshold.py)

Reproduce from the repository root:

    python -m randomness_lab.r1_scaling \
      --tasks 200 \
      --trials 10 \
      --swarm-sizes 1,2,5,10 \
      --difficulties easy:0.82,medium:0.65,hard:0.45 \
      --seed 42 \
      --output /tmp/r1-scaling.json.gz \
      --report /tmp/r1-scaling.md

    python -m randomness_lab.r1_scaling \
      --tasks 200 \
      --trials 10 \
      --swarm-sizes 1,2,5,10 \
      --difficulties easy:0.82,medium:0.65,hard:0.45 \
      --seed 42 \
      --topologies flat,role_specialized,task_dag \
      --output /tmp/r1-topology.json.gz \
      --report /tmp/r1-topology.md

The default invocation stays flat-only and reproduces the committed
`collective-scaling-seeds42-51` payload; a test replays it and compares every
value.

The replay compares values rather than bytes, and the reason is worth stating.
The payload reproduces byte for byte on the machine that generated it, but not
on every machine: the simulation goes through `exp` and `**`, whose last-place
rounding is not identical across CPUs and C libraries, and a one-ulp difference
changes the JSON representation and therefore the file digest. A byte-equality
replay would assert something about the runner rather than about the code, so
the test asserts value equality within a relative tolerance of `1e-9` instead.
The committed artifact's own digest is still pinned, so the file cannot change
silently. Treat "frozen and reproducible" for these artifacts as meaning
*reproducible in value*, not bit-identical off the generating platform.

The output reports, for every adjacent N pair:

- verified-success-rate delta and descriptive 95% interval;
- verified utility per synthetic resource cost;
- regression and security-failure deltas;
- added compute and verifier-attention proxies;
- success-rate points per added worker and per added compute unit.

With the topology arms enabled the output additionally reports, per difficulty,
family, and topology:

- the scaling exponent, fitted by ordinary least squares on log(metric) against
  log(N) separately for every seed, summarized as a mean with a descriptive 95%
  interval over seeds;
- the paired per-seed exponent difference against the flat arm, with the same
  interval and an explicit `changes_exponent` flag;
- a budget-parity record for every cell.

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

[E040](../../experiments/E040-diversity-correlation-threshold.md) measured how
much of it the assumption constructs, by rerunning this grid across a ladder of
assumed correlations instead of the single `0.25`. The answer is: all of the
size and none of the sign. The advantage is proportional to retained
independence, `1 - rho`, at an uncentered R-squared of at least `0.99` through
the origin in 17 of 18 curves, and the two arms coincide by construction at
`rho = 1.0`. There is no correlation at which this harness reports the diverse
arm losing, so its equal-budget result cannot be evidence that the effect
exists — only a sized effect under a stated assumption, which is how the
paragraph above already asks it to be read.

E040 also splits the `diverse_verifiers` arm off from `structural_diversity` and
finds the verification half contributes nothing distinguishable: randomizing
verifier assignment raised the fitted slope in 5 of 9 cells, by at most `0.0181`
against worker-diversity slopes running to `0.5504`. Every verifier in the pool
is built with the same sensitivity and false-positive rate, so randomizing which
one reads a candidate cannot add independence the pool does not have. Claims
about independent verification need an arm that moves
`verifier_error_correlation`, which this grid holds fixed at `0.60`.

## Coordination-topology exponent comparison

Under the frozen assumptions and at an exactly matched budget, coordination
topology does shift the success scaling exponent, but by an amount that is small
next to the effect of error-correlation structure. Mean fitted exponents for
verified success rate, per family, in the order easy / medium / hard:

| Family | flat | role_specialized | task_dag |
| --- | ---: | ---: | ---: |
| homogeneous | 0.046 / 0.045 / 0.046 | 0.057 / 0.050 / 0.073 | 0.068 / 0.063 / 0.098 |
| structural_diversity | 0.113 / 0.184 / 0.340 | 0.091 / 0.130 / 0.225 | 0.138 / 0.215 / 0.373 |
| diverse_verifiers | 0.112 / 0.195 / 0.342 | 0.093 / 0.143 / 0.221 | 0.138 / 0.216 / 0.363 |

Reading the paired per-seed contrasts against the flat arm:

- `task_dag` raised the exponent in all 9 difficulty-by-family cells, with
  descriptive intervals excluding zero in all 9. The mean shift ranged from
  +0.018 to +0.051.
- `role_specialized` moved the exponent in 7 of 9 cells. It *lowered* the
  exponent in all six diversity cells (down to -0.120 at hard difficulty) and
  raised it slightly in the easy homogeneous cell; the medium and hard
  homogeneous cells were statistically ambiguous.
- The largest topology shift observed, -0.120, is smaller than the gap between
  the homogeneous and structurally diverse flat arms at the same difficulty
  (0.046 versus 0.340). In this simulator, who the workers are and how their
  errors correlate matters roughly an order of magnitude more than how the team
  is wired.

The mechanism behind each direction is visible in the design rather than in a
fitted parameter. `role_specialized` spends one of its N attempt units on
coordination instead of on another attempt, which costs it exactly where extra
independent attempts pay — under low error correlation — and costs it nothing
where they do not, under the maximally correlated homogeneous arm. `task_dag`
converts one monolithic acceptance decision into two smaller ones and draws its
shared error shock once per subtask.

This is not a clean win for decomposition. The exponent is a slope, not a level:
`task_dag` also has to clear two acceptance gates instead of one, and the
committed payload retains its absolute success rates, abstention rates, and
false-acceptance rates so that a slope improvement cannot be read as a level
improvement without checking.

## Limitations of the topology comparison

- **This is a synthetic mechanism study. It does not measure real coding
  agents.** No model was called. Planner quality, implementer quality, subtask
  decomposability, defect rates, and verifier behavior are all invented
  parameters, and the topology arms inherit every limitation of the flat arm.
- The `task_dag` advantage depends on an assumption that is stated but not
  measured: that the correlated error shock is redrawn for each subtask, because
  subtasks are distinct pieces of work. If real decomposed subtasks share the
  failure mode of the parent task, that advantage should shrink or vanish. The
  same assumption gives the planner and implementation stages of
  `role_specialized` independent draws.
- Decomposition depth is fixed at two, and the DAG is a two-node chain rather
  than a wide graph. Fan-out, fan-in, and re-planning after a failed subtask are
  not represented.
- The exponents are fitted over four N points on a bounded, saturating metric.
  They summarize a curve; they are not the exponent of a power law that anything
  here is claimed to follow.
- The intervals are descriptive normal approximations over 10 seeds, with no
  multiplicity correction across the 36 reported contrasts. Read
  `changes_exponent` as a flag for where to look, not as a hypothesis test.
- Budget matching is exact for attempts, verifications, synthetic compute,
  attention, and parallel latency. It does not cover the real costs of
  coordination itself: planning tokens, hand-off latency, context transfer, or
  reviewer minutes. A real role-specialized team pays for coordination in ways
  this simulator does not charge it for, so the role-specialized arm here is
  measured on generous terms.

## Issue #13 evidence audit

| Required configuration or dimension | Current evidence after this change |
| --- | --- |
| one strong coding model | missing measured run |
| one small model | missing measured run |
| 5 homogeneous small agents | synthetic proxy only |
| 10 homogeneous small agents | synthetic proxy only |
| 10 heterogeneous agents | synthetic structural-diversity proxy only |
| planner + implementers + tester + reviewer | synthetic budget-matched topology arm |
| task-DAG team + independent verification | synthetic budget-matched topology arm |
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
