# R1 communication burden (structural)

**Issue:** #13
**Evidence:** synthetic mechanism, not real coding-agent performance or real communication

## Question

Issue #13's metric list names messages communicated, duplicated work, and curves for
communication burden. [R1 collective-capability scaling](R1_COLLECTIVE_SCALING.md)
declares those not represented. This page adds the part that can be derived without
inventing observations: **structural** message counts for the three coordination
topologies the lab already defines, structural redundancy, and success-versus-message
curves with seed-bootstrap uncertainty.

Every count below is **structural, not measured bytes**. No agent exchanged a message,
and no token, byte, or latency was measured.

## Method

[`randomness_lab/r1_communication_burden.py`](https://github.com/MSKazemi/idkmesh/blob/main/randomness_lab/r1_communication_burden.py)
is a downstream analyzer over the frozen schema-v2 topology artifact
`results/experiments/r1/coordination-topology-seeds42-51.json.gz`. It does not edit or
re-run the generator (`randomness_lab/r1_scaling.py`); the R1 tests pass unchanged, a test
pins the input artifact's SHA-256, and another asserts the module imports only four
constant names from the generator and assigns to no attribute.

### Counting rule

A message is one directed transfer of a task statement, plan, candidate, or verdict along
one edge of the topology's role graph, counted once per task episode. The lab has no
multi-round exchanges, so a "round" here is one task. H is the integrating hub.

| Topology | Edges per task | Messages per task |
| --- | --- | ---: |
| `flat` | H to W_k, W_k to V_k, V_k to H, for k = 1..N | 3N |
| `role_specialized` (N >= 2) | H to planner (1), planner to implementer (N-1), implementer to tester (N-1), tester to reviewer (1), reviewer to H (1) | 2N + 1 |
| `task_dag` (N >= 2) | dispatch, candidate hand-off, and verdict for every attempt; the child dispatch carries the accepted parent artifact; blocked child budget is re-spent on parent attempts at the same three messages each | 3N |

A team of one has no coordination structure and uses the flat rule (3 messages) in every
topology. Totals per trial are the per-task count times the 200 tasks of each trial. The
critical path is 3 hops for `flat`, 5 for `role_specialized`, and 3 to 6 for `task_dag`
depending on whether the parent is accepted.

| N | flat | role_specialized | task_dag | all-to-all reference |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 3 | 3 | 0 |
| 2 | 6 | 5 | 6 | 2 |
| 5 | 15 | 11 | 15 | 20 |
| 10 | 30 | 21 | 30 | 90 |

The all-to-all column is `N(N-1)` and is a reference contrast only; no lab arm is
all-to-all. **The ordering of topologies by message count is a property of this rule.**
`role_specialized` is cheaper because the tester's per-candidate verdicts stay inside one
role; a rule that routes every verdict through the hub would make it 3N like the others.
`task_dag` has the same count as `flat` by construction.

### Redundancy, and why duplication is only partly defined

The R1 result holds per-seed aggregate metrics only. It carries no candidate identity and
no per-task trace, so the requested definition, *an attempt whose candidate equals an
earlier candidate in the same task*, **cannot be computed from it**, and the committed
result records `duplicated_attempts_in_r1_result: null` with that reason.
`count_duplicated_attempts` implements the definition for a caller-supplied trace
(tested on a hand-built one) and is applied to no R1 data. Two other quantities are
defined and reported, and neither is content duplication:

- **Structural replicated attempts**: attempts beyond the first on the same unit of work,
  by design. For N=10, `flat` has 9, `role_specialized` 8, and `task_dag` 8 to 9 (a range,
  because whether the child budget is re-spent depends on a per-task acceptance the result
  does not carry).
- **Unproductive attempts per task**: `N * (1 - verified success rate)`, the attempts
  spent on tasks that did not end in a verified success. Every arm spends exactly N
  attempts per task, which the committed parity records already show.

### Curves and uncertainty

For each of 27 (difficulty, family, topology) groups the analyzer reports, at N = 1, 2, 5,
10: verified success, verified successes per message (`success / messages`), and
unproductive attempts, each with a percentile bootstrap interval; the success gain per
added message between adjacent sizes; and a per-seed log-log elasticity of success on
messages. Contrasts against `flat` are paired per seed. Intervals come from 2,000
resamples of the 10 existing seeds (42 to 51) with a fixed bootstrap seed, and one
resample set is shared by every topology within a (difficulty, family) pair so contrasts
resample identical seeds. They are descriptive, not multiplicity adjusted, and the seeds
are not common-random-number task replays (see the R1 scaling page).

Reproduce from the repository root:

    python -m randomness_lab.r1_communication_burden \
      --output /tmp/r1-communication-burden.json.gz \
      --report /tmp/r1-communication-burden.md

- [machine-readable result](https://github.com/MSKazemi/idkmesh/blob/main/results/experiments/r1/communication-burden-seeds42-51.json.gz)
- [full generated tables](https://github.com/MSKazemi/idkmesh/blob/main/results/experiments/r1/communication-burden-seeds42-51.md)

## Results

All numbers are synthetic-simulator observations.

**Success per message falls with N everywhere.** In all 27 groups, the mean verified successes per
message decreases at every step from N=1 to N=10. For flat homogeneous at easy difficulty
it goes 0.239, 0.134, 0.054, 0.027. Because messages grow roughly linearly in N while
success saturates, extra workers are not communication-cost-effective in this simulator,
the same shape the compute-cost result already showed.

**Marginal success per added message is positive early and mostly unresolved late.**
Counted over the 27 groups, the interval for success gain per added message was
positive in 10 groups for 1 to 2, in 24 for 2 to 5, and in 11 for 5 to 10. It was
uncertain in 16, 3, and 15 groups respectively, and negative in 1, 0, and 1. The
negative cases are `task_dag` medium homogeneous at 1 to 2 and `flat` easy
`diverse_verifiers` at 5 to 10 (a small negative, -0.0010 per added message, with an
interval of [-0.0020, -0.00003]). Between 5 and 10 workers the data mostly cannot
distinguish a positive gain from zero.

**`role_specialized` looks better per message, but that is mostly the cheaper count.**
At N=10 its success per message exceeds `flat` with an interval above zero in 7 of 9
cells, and is unresolved in the other 2. Its absolute success is lower: for example,
medium structural diversity is 0.7305 against 0.8985 for `flat`. A ratio rewards a cheaper
arm that succeeds less, so read this column together with the success column. At N=2 it
is *worse* per message in 5 of 9 cells and better in 3.

**`task_dag` is not better per message.** At N=2 it is worse than `flat` per message in
all 9 cells, at N=5 in 6 of 9 (3 unresolved), and at N=10 worse in 3, better in 1, and
unresolved in 5. Its per-seed success-versus-message elasticity is nevertheless higher
than `flat` in all 9 cells (differences +0.018 to +0.051, all intervals above zero), the
same sign as the existing exponent result. That is a slope from a lower N=2 level, not a
level advantage, exactly as the R1 scaling page cautions. `role_specialized` elasticity
differs from `flat` in 5 of 9 cells (1 higher, 4 lower, all four lower in the medium and
hard diversity cells) and is unresolved in 4. Because the message axis is 2N+1 rather
than proportional to N, its elasticity is not the exponent on the R1 scaling page.

## What this does not show

- It does not measure communication. The message counts follow from a stated rule over
  three synthetic topology definitions; change the rule and the ordering can change.
- It does not measure duplicated work. Content-level duplication is undefined on these
  traces, so the issue's duplicated-work metric stays open. The structural replication
  and unproductive-attempt figures are by-design and by-outcome quantities, not equal
  candidates.
- It does not vary a communication budget K or shared memory M. No arm is given less
  communication to see what it costs in success; the curves vary N and topology only, so
  nothing here says whether communication *causes* the success differences.
- It does not use real agents, real tasks, or measured costs. All worker quality,
  correlation, defect, and verifier parameters are the synthetic R1 assumptions.
- The frozen generator's own gap ledger still lists "measured inference cost, reviewer
  minutes, communication bytes, and duplication" as not represented. That clause is left
  unchanged: it is true (bytes and duplication remain unmeasured), and editing it would
  change a committed artifact's digest.

Issue #13 stays open. A real run still needs a prospectively frozen task corpus and
recorded message traffic before any claim about communication cost can be made.
