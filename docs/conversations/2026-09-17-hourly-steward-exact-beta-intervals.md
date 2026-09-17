# Hourly Steward: Exact Beta Posterior Intervals

Date: 2026-09-17  
Issue: #86  
Base revision: `93c3d7c2eb08c193e05b55c1d88c64c21377b3e2`

## Project-owner request

The project owner asked the IDKMesh issue steward to handle exactly one valuable,
well-scoped open issue, avoid work already covered by an active pull request,
read the relevant implementation/tests/architecture/documentation first, make a
production-quality integrated change, preserve scientific validity, add tests and
documentation, run the applicable validation, and merge only when the exact-head
quality gates and review/conflict requirements are satisfied.

## Repository inspection

The steward refreshed current `main`, inspected the open issue and pull-request
queues, and selected one bounded part of issue #86, "Research program:
operationalize the mathematical foundation." No open pull request was found that
was changing `scripts/metric_uncertainty.py` or this Beta-posterior contract.

The relevant current implementation already separated prior-only Bayesian values
from empirical observations, but its reported 95% Beta-posterior uncertainty was
still the clipped normal approximation `mean +/- 1.96 * sd`. The research
documentation explicitly named that approximation as a remaining limitation,
especially for sparse or extreme samples.

## Change made

This run introduces `beta-binomial-v3` and makes the primary 95% posterior
uncertainty interval the equal-tail Beta interval `[q(0.025), q(0.975)]`.

The implementation stays dependency-free. It evaluates the regularized
incomplete beta CDF with a convergent continued fraction and inverts the CDF by a
fixed-count deterministic bisection. The historical normal approximation remains
available under explicit legacy fields so downstream evidence can be compared
rather than silently reinterpreted.

A custom legacy `z` value no longer populates a field named
`approx_interval_95`: the generic normal interval is retained, but only the
historical `z = 1.96` case is labelled as the compatibility 95% approximation.
`conservative_lower_bound()` prefers the exact interval and still accepts a
v2-style summary that only contains the old approximate interval.

Because the nested metric contract changes, the collaboration-observables method
is versioned from v0.3 to v0.4 and its focused regression tests/documentation are
updated in the same branch.

## Scientific basis and falsifiability

For a Beta posterior, an equal-tail 95% credible interval is defined by the 2.5th
and 97.5th posterior percentiles. This is distinct from substituting a Gaussian
approximation to the posterior mean/variance and clipping the result to the unit
interval.

The implementation is tested without depending on a statistics package by using
closed-form cases. For example, a `Beta(2, 1)` posterior has CDF `x^2`, so its
quantile at probability `p` is exactly `sqrt(p)`. The regression suite compares
the numerical interval against that analytic result. During development, several
parameter combinations were also spot-checked against an independently installed
scientific-statistics implementation; that development comparison is supporting
evidence, not a repository dependency or independent human review.

## Assumptions and limitations

The exact quantile calculation improves the numerical interval under the declared
Beta-Binomial model; it does not validate that model. The credible interval is
conditional on the prior and observation model, is not a frequentist confidence
interval, and makes no causal claim. Contributor observations and CI checks may be
dependent or non-exchangeable, so interval precision must not be mistaken for
independent evidence quality.

The numerical routine uses finite-precision floating-point arithmetic. Its public
contract is protected by analytic regression cases and repository CI, but a
future high-stakes/extreme-parameter use should cross-check it against a mature
special-functions implementation before expanding authority.

No metric produced by this change gains policy, merge, moderation, or GitHub-write
authority. Owner-controlled AI work in this run is not independent review.

## Validation record

Before opening the pull request, the focused metric uncertainty tests were
reconstructed and run locally: 12 tests passed. Exact-head repository CI is the
integration authority for the final branch because the automation environment did
not have a reliable full GitHub checkout path.

The pull request/issue discussion should record the final exact-head CI result and
merge status once available.
