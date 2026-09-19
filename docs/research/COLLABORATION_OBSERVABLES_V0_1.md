# Collaboration Observables (current analyzer v0.4; historical evidence v0.1)

Status: experimental, offline, observational

This layer turns a frozen normalized GitHub history into deterministic review,
ownership, recurrence, CI, queue, and structural-debt evidence. It does not
collect private data, interpret natural-language content, assert causality, or
write to GitHub.

The document keeps its historical `V0_1` path because committed production
evidence and findings already refer to that artifact. The executable analyzer is
now `collaboration-observables-v0.4`. v0.2 corrected HHI output for empty
observed populations. v0.3 separated empirical observations from prior-only
Beta posterior values. v0.4 replaces the normal approximation as the primary
Beta-posterior uncertainty interval with a deterministic equal-tail 95% credible
interval while retaining the old normal approximation as explicit compatibility
output.

## Input and replay

The input fixes a repository, cutoff timestamp, pull-request observations, and
contributor histories. Pull requests carry timestamps, independent reviewer
IDs, changed-file owner attributions, CI counts, structural-debt findings, and
optional strategy/outcome labels. Records are sorted by stable identifiers, and
bootstrap seeds are derived from repository plus cutoff, so record order cannot
change the output. Contributor timestamps must be unique within each contributor
record, and `inventory_complete` must be a JSON boolean; malformed or duplicate
observations fail closed instead of changing recurrence or completeness.

Run:

    python scripts/collaboration_observables.py tests/fixtures/collaboration_observables_snapshot.json
    python -m pytest -q tests/test_collaboration_observables.py tests/test_metric_uncertainty.py

## Live bounded collection

`scripts/collaboration_snapshot.py` collects the 50 most recently created pull
requests through public GitHub metadata. It retains no bodies or raw actor
logins, reserves API capacity before starting, and aborts rather than publish a
partially paginated review, timeline, or check inventory. The weekly/manual
`Collaboration Observables` workflow runs the collector and analyzer from
trusted `main` with read-only permissions.

The live window is explicitly incomplete repository history, and it treats
merged pull requests as the only meaningful-contribution proxy.

Collector `v0.2` adds two attributions, both bounded by that same window.
Ownership follows `last_merged_toucher_within_window-v1`: a path is owned by the
author of the most recent merged pull request inside the window that changed it,
and the model advances only after a merge, so a pull request is never credited
with ownership its own merge created. A path first seen inside the window has no
owner and is counted in `unattributed_changed_files` rather than guessed at.
Structural debt is not inferred at all: `--structural-debt-report` consumes the
deterministic `tools/idkgraph_observatory.py` inventory and attaches each finding
to the last pull request in the window that changed the finding's path. A finding
whose path the window never touched stays unattributed, and `inventory_complete`
is `true` only when a report was supplied **and** every finding in it reached a
pull request — so the downstream count can never claim completeness over an
undercount. Most importantly, it emits **no evidence-derived strategy prior**
unless a separate input has independently classified verified-useful outcomes;
merged status and green CI are not enough.

## Metric contracts

| Metric | Observable/model | Uncertainty | Prediction and baseline | Main failure modes |
| --- | --- | --- | --- | --- |
| First independent review latency | Hours from ready/open timestamp to first independent review | Deterministic 1,000-replicate bootstrap interval for the observed median; still-open items are right-censored and closed-without-review items are reported separately | Lower latency may predict recurrence; compare the preregistered 72-hour groups | Bots/self-review must be removed upstream; censoring and workload confounding |
| Cycle latency | Hours from creation to closure | Same observed-median bootstrap plus open-item count | Review concentration may predict longer cycles | Closure is not necessarily acceptance; right censoring |
| Review HHI | Share-squared over distinct independent reviewer–pull-request pairs; `null` when there are no eligible pairs | Descriptive snapshot only when observed; undefined for an empty population | Compare only observed populations; never treat an empty population as an equal-share baseline | Reviewer–PR pairs are not effort or quality; identity aliases; zero eligible observations |
| Ownership HHI | Share-squared over changed-file owner attributions; `null` when there are no owner attributions | Descriptive snapshot only when observed; undefined for an empty population | High observed concentration may identify bus-factor risk; no statement is made when no attribution exists | CODEOWNERS/attribution quality, multi-owner files, zero eligible observations |
| Contributor recurrence | Contributors with at least two meaningful contributions / observed contributors | Beta-Binomial posterior with exact equal-tail 95% posterior credible interval, explicit observed sample size, and prior-only status when the cohort is empty | Compare bounded observed cohorts, never raw activity volume | Eligibility and meaningful-contribution definitions; time-to-return requires a richer survival/cohort model; Beta-Binomial exchangeability assumptions |
| CI evidence | Passing / observed checks | Beta-Binomial posterior with exact equal-tail 95% posterior credible interval; empirical rate remains separate from the prior-derived posterior and zero checks remain prior-only | Compare like-for-like check suites | Check dependence, heterogeneous coverage, and violated exchangeability assumptions |
| Review queue | Count and age of open review-ready PRs at cutoff | Point-in-time state; no sampling interval | Rising age/queue indicates capacity pressure | Snapshot timing and draft-state quality |
| Structural debt | Stable finding IDs attached to observed PRs | Deduplicated bounded inventory count with completeness flag | Track changes only under stable detector definitions | Detector drift and incomplete inventory |

### HHI empty-population semantics (analyzer v0.2+)

For a non-empty observed population, the analyzer reports the standard
Herfindahl-Hirschman concentration statistic
`HHI = sum_i s_i^2`, where `s_i` is actor `i`'s share of the observed
attributions. For example, one observed actor has HHI `1.0`, while two actors
with equal observed shares have HHI `0.5`.

There is no share vector when the observation count is zero, so HHI is not
mathematically defined for that snapshot. Analyzer v0.2 therefore emits:

```json
{
  "model": "observed-share-hhi-v2",
  "observations": 0,
  "distinct_actors": 0,
  "hhi": null,
  "status": "undefined_empty_population",
  "counts": {},
  "uncertainty": "undefined_without_observations"
}
```

For non-empty populations, `status` is `observed` and `uncertainty` remains
`descriptive_snapshot_no_population_inference`. This is a semantic correctness
change, not a new estimator or a health threshold. In particular, the analyzer
does not convert HHI into contributor rankings, causal claims, or policy
authority.

### Beta evidence and exact posterior intervals (analyzer v0.4)

Contributor recurrence and CI evidence use a declared Beta-Binomial observation
model. A posterior distribution is mathematically defined even with zero
trials, but its value then comes entirely from the prior. Under the default
`Beta(1, 1)` prior, a zero-trial posterior mean is `0.5`; that is **not** an
observed 50% recurrence or CI pass rate.

Analyzer v0.4 consumes `beta-binomial-v3`, which preserves that empirical/prior
boundary and makes the primary interval the exact equal-tail posterior interval.
For posterior `Beta(alpha, beta)`, the 95% interval is the pair of posterior
quantiles `q(0.025)` and `q(0.975)`. The dependency-free implementation computes
those quantiles by deterministic bisection over the regularized incomplete beta
CDF. A zero-trial default-prior summary therefore includes:

```json
{
  "model": "beta-binomial-v3",
  "trials": 0,
  "observed_sample_size": 0,
  "empirical_rate": null,
  "evidence_status": "prior_only_no_observations",
  "posterior_mean": 0.5,
  "prior_pseudocount_mass": 2.0,
  "posterior_concentration": 2.0,
  "credible_interval_95": [0.025, 0.975],
  "interval_method": "equal-tail-beta-posterior",
  "interval_mass": 0.95
}
```

When trials exist, `evidence_status` becomes `observed` and `empirical_rate`
reports the raw bounded proportion separately from the prior-regularized
posterior mean. The compatibility field `effective_sample_size` remains the Beta
posterior concentration, not the empirical observation count; consumers should
use `observed_sample_size` for the latter.

The v1/v2 normal approximation is retained as compatibility evidence rather than
silently disappearing. With the historical default `z = 1.96`,
`approx_interval_95` retains the old rounded interval and
`legacy_normal_interval` carries the same value. For a caller that supplies a
custom `z`, the generic legacy interval remains available but
`approx_interval_95` becomes `null`; a custom normal interval is not mislabeled
as a 95% interval. `conservative_lower_bound()` prefers
`credible_interval_95` and falls back to the historical approximation only when
reading an older v2-style summary.

This corrects an important sparse-data failure mode of the normal approximation:
clipping `mean +/- 1.96 * sd` to `[0, 1]` is not the same as computing posterior
quantiles and can distort uncertainty near the boundaries. The exact interval is
still **Bayesian and model-conditional**. It is not a frequentist confidence
interval, does not guarantee repeated-sampling coverage, does not establish that
observations are independent or exchangeable, and does not turn an observational
metric into a causal result. CI checks in particular can be strongly dependent.
For very high-stakes or extreme-parameter use, the dependency-free numerical
routine should be cross-checked against a dedicated numerical-statistics library;
its repository contract is protected by analytic closed-form regression cases and
the normal exact-head test gates.

The output also derives provisional strategy weights only from independently
classified verified-useful outcomes, using the same explicit Beta evidence
model. A strategy row cannot exist without at least one classified outcome, so
those rows are observed rather than prior-only. These are evidence summaries,
not production-policy activation.

## Committed production evidence

The scheduled workflow uploads its output with `retention-days: 30`, so a run's
artifact expires. The first successful production run
(`33229934255`, head `16f4ba59`, cutoff `2026-08-29T02:50:35.294099Z`) is
therefore committed under `results/collaboration/`, and read in
[First Production Collaboration-Observables Snapshot](../findings/2026-08-29-collaboration-observables-first-snapshot.md).

That historical v0.1 artifact encoded an empty reviewer population with review
HHI `0.0`. Under the corrected v0.2+ contract, the same absence of eligible
reviewer–pull-request pairs is represented as `null` with
`status: undefined_empty_population`. The old `0.0` must not be interpreted as
evidence of perfectly distributed review: there were no eligible review
observations from which to estimate concentration. The committed artifact is
left unchanged so historical evidence remains reproducible.

The first production note is still worth reading before interpreting any zero
in this pipeline: some zero-valued observables are real counts, one is a
point-in-time queue reading, and some observables are absent from the collector.
A numeric zero is only meaningful under the metric's declared contract. The same
principle applies to Bayesian values: a posterior can be mathematically
well-defined while the empirical sample size is still zero, and a posterior
credible interval describes uncertainty under the chosen probabilistic model
rather than proving that model's assumptions.

## Preregistered community analysis

The E023 JSON record under experiments freezes the population, exposure,
90-day outcome, estimand, exclusions, covariates, missing-data rule, and
analysis before any outcome dataset is added. Its primary contrast is first
independent substantive review at or below 72 hours versus above 72 hours.

The initial study is observational. Even a positive association cannot establish
that faster review caused recurrence because task difficulty, contributor
experience, maintainer load, and selection may confound both. A causal claim
requires a separately preregistered randomized or credible quasi-experimental
design.

## Security and human constraints

Contributor IDs in public evidence should be minimized or pseudonymized when a
stable aggregate is sufficient. Natural-language bodies are outside the input.
No metric grants merge, moderation, ranking, spending, or policy authority.
Results must not be used to pressure volunteer reviewers or contributors.
