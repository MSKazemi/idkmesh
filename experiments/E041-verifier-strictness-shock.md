# E041 — the R1 lab's "verifier correlation" is not verifier correlation

**Module:** [`randomness_lab/r1_verifier_dependence.py`](../randomness_lab/r1_verifier_dependence.py)
**Artifacts:** [machine-readable](../results/experiments/r1/verifier-strictness-shock-seeds42-91.json.gz) · [generated table](../results/experiments/r1/verifier-strictness-shock-seeds42-91.md)
**Tests:** [`tests/test_r1_verifier_dependence.py`](../tests/test_r1_verifier_dependence.py)
**Refs:** [#13](https://github.com/MSKazemi/idkmesh/issues/13), [#30](https://github.com/MSKazemi/idkmesh/issues/30)

[E040](E040-diversity-correlation-threshold.md) closed by naming the next test:

> The next test that would move this is a sweep of `verifier_error_correlation`
> against a beta-binomial joint-failure shape rather than a flat shared shock,
> using E017's fitted parameters as the reference point.

**That test cannot be run, and the reason is the finding.** A joint-failure
shape describes how the errors of a *panel* co-occur.
[`randomness_lab/r1.py`](../randomness_lab/r1.py) has no panel. There is no
joint distribution over verifiers to give a different shape.

This is the same class of finding as E040's own — a statement about the
repository's tooling rather than about coding agents — and it lands on the half
of hypothesis 2 that E040 left open. E040 showed the `diverse_verifiers` arm
moves verifier *assignment* rather than verifier *independence*. E041 goes one
step further: independence between verifiers is not a quantity this lab has.

## Result 1 — one verifier reads each candidate, in every arm

`run_r1_condition` selects exactly one verifier per candidate — 
`condition.verifiers[0]` under `fixed` assignment, `rng.choice(...)` under
`random` — writes one `verifier` name and one `accepted` flag onto the candidate
record, and integrates `accepted_candidates[0]`. No quorum, vote, or aggregation
rule appears anywhere in `randomness_lab`; the word does not occur in the
package. Five of the six arms `build_r1_conditions` returns are constructed with
a single verifier, and the sixth, `diverse_random_verifiers`, draws its pool of
three to five from one parameter set, so its members are interchangeable by
construction.

This is asserted by test rather than by prose. If the lab is later given a real
panel, `LabStructureTests` fails, which is the signal that this record has been
superseded rather than quietly invalidated.

## Result 2 — what the parameter actually couples

The mechanism is four lines of `_verifier_accepts`: with probability `rho` a
candidate is judged against a uniform draw *shared with every other candidate
the same verifier reads in the same task*, otherwise against a fresh one. It is
a within-task strictness shock on one verifier.

The measurements separate the two readings cleanly. `shared_draw` is itself
uniform, so the marginals cannot move; only the within-task joint can.

| rho_v | P(accept \| good) | P(accept \| bad) | corr(accept_0, accept_1) | P(good accepted \| a bad one was) |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.9695 | 0.0298 | 0.1576 | 0.9657 |
| 0.25 | 0.9702 | 0.0301 | 0.1687 | 0.9819 |
| 0.50 | 0.9705 | 0.0294 | 0.1734 | 0.9805 |
| 0.75 | 0.9682 | 0.0297 | 0.2208 | 0.9895 |
| 1.00 | 0.9707 | 0.0321 | 0.2318 | 1.0000 |

The accept rates sit on the configured sensitivity `0.97` and false-positive
rate `0.03` at every correlation. The within-task figures move.

The last column is the signature of a shared draw rather than of panel
dependence: a draw below the false-positive rate is necessarily below
sensitivity, so a task that accepted a bad candidate has accepted every good one
in the same task. At `rho = 1` that probability is exactly `1.0000`, not
approximately.

Two further checks pin the reading:

- **It is inert when a task has one candidate.** On `single_deterministic`,
  which runs `attempts_per_task = 1`, the difference between `rho = 0` and
  `rho = 1` is `-0.0065`, interval `[-0.0165, +0.0034]` — an interval narrower
  than twice the largest effect measured elsewhere in this run, so it would have
  caught one. A within-task shock with nothing to couple does nothing, which a
  property of the verifiers themselves could not do.
- **At `rho = 1` the task is solvable exactly.** One uniform `u` decides
  everything: below `f` all candidates are accepted, between `f` and `s` the
  good ones are, above `s` none are. With `g` the probability a task produced a
  good candidate and `g0` the probability its first candidate was good:

| metric | closed form | predicted | observed | absolute error |
| --- | --- | ---: | ---: | ---: |
| abstention | `(1-s) + (s-f)(1-g)` | 0.1110 | 0.1101 | 0.0010 |
| verified success | `f*g0 + (s-f)*g` | 0.8774 | 0.8779 | 0.0005 |
| false acceptance | `f*(1-g0)` | 0.0116 | 0.0120 | 0.0004 |

Maximum absolute error `0.0010`. The parameter is understood, not merely
described.

## Result 3 — the cost does not amortize over swarm size

This is the part that bears on issue #13, which scales `N`. Raising the shock
from `rho_v = 0` to `rho_v = 1` costs verified success, and the cost is flat in
`N` once a task has enough candidates for the shock to bite:

| N | verified at rho_v=0 | verified at rho_v=1 | penalty | 95% CI |
| ---: | ---: | ---: | ---: | --- |
| 2 | 0.7859 | 0.7779 | +0.0079 | [+0.0004, +0.0155] |
| 3 | 0.8600 | 0.8426 | +0.0174 | [+0.0085, +0.0263] |
| 5 | 0.9026 | 0.8779 | +0.0247 | [+0.0174, +0.0320] |
| 8 | 0.9035 | 0.8787 | +0.0247 | [+0.0182, +0.0313] |
| 12 | 0.9061 | 0.8835 | +0.0227 | [+0.0161, +0.0292] |
| 20 | 0.9061 | 0.8805 | +0.0255 | [+0.0184, +0.0327] |

All six penalties resolve. Over the plateau the OLS slope is `+0.00020` per
e-fold, and the change from `N = 5` to `N = 20` — a fourfold increase in swarm
size — is `+0.0009`, interval `[-0.0093, +0.0111]`. The interval is what carries
the claim: it excludes amortizing away more than about `0.0093` of a `0.0247`
penalty, so more than roughly a third of the cost cannot be bought back by
quadrupling the swarm.

Note what the plateau is *not*. Verified success stops rising near `N = 5` at
both correlations, and that ceiling belongs to the worker side — the shared-shock
worker correlation floors the probability that a task produced no good candidate
at all. The verifier shock is a roughly constant offset below that ceiling, not
its cause.

## Result 4 — a second verifier removes almost all of it

The shared draw is keyed by verifier, so two candidates read by different
verifiers are never coupled. At `N = 5`:

| pool | assignment | penalty | 95% CI | 1/K would predict |
| ---: | --- | ---: | --- | ---: |
| 1 | fixed | +0.0247 | [+0.0174, +0.0320] | 0.0247 |
| 2 | random | +0.0048 | [-0.0016, +0.0112] | 0.0123 |
| 3 | random | -0.0014 | [-0.0085, +0.0057] | 0.0082 |
| 4 | random | +0.0001 | [-0.0072, +0.0074] | 0.0062 |
| 5 | random | -0.0009 | [-0.0077, +0.0060] | 0.0049 |
| 8 | random | +0.0025 | [-0.0036, +0.0087] | 0.0031 |

One verifier is penalized; two are not, and the interval at `K = 2` is tight
enough to exclude half the single-verifier penalty. The decay is faster than
`1/K`, which is the obvious guess and is wrong: abstention through this channel
needs *every* verifier used in the task to have drawn strict, so it falls
geometrically in the number of distinct verifiers rather than in proportion to
the pool.

Unlike `rho = 1` at `K = 1`, this has no closed form here. The geometric
argument gives the direction and it survives the data, but a prediction built
from that term alone underestimates the residual penalty at `K >= 2`, so a
second channel is present that this record does not model and does not quote a
number for. What is established is that the collapse is real, that it is
complete by `K = 2` within the resolution of this run, and that it is faster
than `1/K`.

**This reframes what `diverse_random_verifiers` is for.** E040 measured that arm
on the worker-correlation slope and found it buys nothing distinguishable, which
stands. On the verifier axis it buys the entire penalty back. The arm's function
is immunity to verifier strictness shock, not added worker-side advantage, and
those are different claims about the same arm.

## Reproduction

From the repository root:

    python -m randomness_lab.r1_verifier_dependence \
      --tasks 300 \
      --trials 50 \
      --seed 42 \
      --correlations 0,0.25,0.5,0.75,1.0 \
      --swarm-sizes 2,3,5,8,12,20 \
      --pool-sizes 1,2,3,4,5,8 \
      --output results/experiments/r1/verifier-strictness-shock-seeds42-91.json.gz \
      --report results/experiments/r1/verifier-strictness-shock-seeds42-91.md

That is the default invocation and it reproduces the committed payload. The
replay test compares by value at a relative tolerance of `1e-9` rather than by
digest, for the reason
[`docs/research/R1_COLLECTIVE_SCALING.md`](../docs/research/R1_COLLECTIVE_SCALING.md)
gives for its own artifacts. The whole run takes about eighteen seconds.

## What this does not establish

- **No model was called.** Sensitivity, false-positive rate, worker quality and
  both correlations are invented parameters. Every number is a statement about
  the simulator.
- **The comparisons are unpaired.** `_verifier_accepts` draws the correlation
  coin before deciding whether to draw again, so two runs at the same seed and
  different `rho` consume different numbers of values and diverge after the
  first candidate. Seeds match nothing beyond that point, so the intervals are
  Welch rather than paired, and are wider for it.
- **The intervals are descriptive.** Normal approximations over 50 seeds with no
  multiplicity correction across the cells reported here.
- **Result 4's mechanism is bounded, not solved.** The `K >= 2` residual is
  unexplained; see the numbers above.
- **The plateau ceiling is a worker-side artifact.** It is set by the flat
  shared-shock worker correlation, which
  [E017](E017-item-difficulty-and-quorum.md) showed is the wrong shape, so the
  ceiling's *value* should not be quoted. Result 3's claim is about the
  penalty's flatness, which is a difference between two arms that share that
  artifact.
- **Nothing here says panel dependence does not matter.** It says this lab
  cannot speak to it. [E018](E018-dependence-model-shape.md) and
  [E020](E020-quorum-frontier-under-measured-shape.md) are where panels live, and they already carry
  the beta-binomial shape E040 asked for.

## Decision

1. **E040's decision item 3 is closed as not executable, and replaced.** The
   beta-binomial reshape it asked for has no target in `randomness_lab`. The
   `sim/` experiments already apply that shape to real panels; the R1 lab would
   need a panel before the question could be asked of it.
2. **`verifier_error_correlation` must not be cited as evidence about verifier
   independence** — in `R1_COLLECTIVE_SCALING.md`, `R1_HELP_HURT_SWEEP.md`, or
   anywhere else. It is a within-task strictness shock. The parameter name is
   the trap; the guardrail string in the artifact exists to be quoted alongside
   it.
3. **Hypothesis 2's verification half remains untested,** and E041 narrows why:
   E040 found the arm meant to test it moves assignment rather than
   independence, and E041 finds the lab has no independence axis to move.
   Giving `run_r1_condition` a panel with a quorum is the prerequisite, and that
   is a design change, so per `AGENTS.md` it belongs in an issue before it
   belongs in a commit.
4. **The one result that transfers to a design choice** is Result 4: if a lab or
   a real deployment routes every candidate of a task through one reviewer, a
   single bad day costs a flat, unamortizable share of throughput, and a second
   reviewer removes almost all of it. That is a statement about the simulator's
   structure, and it is the kind of structure real review queues also have.
