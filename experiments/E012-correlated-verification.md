# E012 — Correlated Verification Failure

## Research question

When multiple verifiers review the same candidate, how much protection does majority voting provide when their errors are correlated?

This experiment extends E011 by replacing the perfect viability oracle with an imperfect verifier panel.

## Model

Each candidate has a true viability state determined by the simulator's reliability/security/budget invariants.

A verifier matches that ground truth with probability `p`.

For a panel of `n` verifiers, correlation is modeled with a simple shared-shock mixture:

- with probability `rho`, all verifier correctness states are shared;
- with probability `1-rho`, verifier correctness states are sampled independently.

Therefore:

- `rho = 0` approximates independent verifier errors;
- `rho = 1` makes all verifier errors perfectly correlated.

The panel accepts when the positive-vote fraction exceeds the configured quorum.

This is intentionally a controlled synthetic mechanism. It is not claimed to be a fitted statistical model of real humans or AI reviewers.

## Reference configuration

```text
seeds = 50
agents = 40
generations = 30
goal change = generation 15
verifiers = 5
individual verifier accuracy = 0.75
majority quorum = 0.5
correlation = [0, 0.25, 0.5, 0.75, 1.0]
```

Reproduce with:

```bash
python sim/run_verifier_correlation_sweep.py --pretty
```

Machine-readable summary:

`experiments/results/E012-correlated-verification-50-seed-summary.json`

## Key result

For the QD strategy:

| Error correlation | False accept rate | False reject rate | Panel disagreement rate | Post-change mean |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0.108688 | 0.103848 | 0.764742 | 0.863467 |
| 0.25 | 0.143338 | 0.140311 | 0.574629 | 0.862843 |
| 0.50 | 0.174632 | 0.176936 | 0.384194 | 0.860189 |
| 0.75 | 0.220152 | 0.211872 | 0.194468 | 0.859301 |
| 1.00 | 0.254179 | 0.248811 | 0.000000 | 0.862554 |

The same qualitative verification pattern appears across random, scalar, and QD search.

### Observation

Increasing correlation destroys much of the reliability benefit of a verifier panel. At full correlation, five reviewers are effectively one error source: the panel has zero internal disagreement while false-accept and false-reject rates are about 25%.

This gives an important IDKMesh warning:

> **Unanimity can become less informative as verifier dependence increases.**

A low disagreement rate is not necessarily evidence of high correctness. It can also mean that reviewers share the same blind spot, model family, prompt, tests, toolchain, training data, or compromised dependency.

## Architectural implication

Verification policy should care about **independence provenance**, not only reviewer count.

Candidate signals include:

- model/provider family;
- prompt/reasoning template;
- toolchain;
- test origin;
- data/retrieval source;
- execution environment;
- organization/trust domain;
- historical error correlation;
- shared dependencies.

A nominal quorum of five highly correlated verifiers should have lower effective evidence weight than five demonstrably diverse verifiers.

A useful approximation already tracked in `MATHEMATICAL_FOUNDATIONS.md` is effective sample size under average correlation:

`N_eff ~= N / (1 + (N-1) rho)`

For `N=5` and `rho=1`, `N_eff=1`.

**Update:** E015 later measured effective panel size directly and found this approximation is
optimistic for accurate verifiers — effective size has an accuracy-dependent ceiling that the
formula lacks. Use it as intuition, not as a panel-sizing rule. See
[`E015-verification-phase-diagram.md`](E015-verification-phase-diagram.md).

## What this does NOT show

- It does not prove the exact error rates of real AI or human verifier panels.
- It does not establish that the shared-shock model is the best correlation model.
- It does not yet model strategic collusion or Byzantine verifiers.
- It does not yet fit correlation from observed verifier histories.
- Search strategies still do not have strictly matched total proposal/evaluation budgets.
- The QD result staying relatively stable in this toy model should not be generalized to real software tasks.

## Next experiments

1. Match total verification cost while varying panel size and diversity.
2. Estimate pairwise verifier correlation from synthetic histories instead of supplying `rho` directly.
3. Compare naive majority vote against correlation-discounted voting.
4. Add verifier specialization by defect class.
5. Add malicious/colluding verifier groups.
6. Make independent test generation a separate evidence channel.
7. Connect the simulator to the repository's `VerificationResult` provenance contract.
8. Move the same experiment onto real bounded software tasks with hidden tests.

## Falsifiable hypothesis for the next iteration

A correlation-aware aggregation rule should reduce false acceptance at a comparable verification budget when verifier errors are heterogeneous and dependent.
