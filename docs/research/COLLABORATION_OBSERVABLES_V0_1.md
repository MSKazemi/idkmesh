# Collaboration Observables v0.1

Status: experimental, offline, observational

This layer turns a frozen normalized GitHub history into deterministic review,
ownership, recurrence, CI, queue, and structural-debt evidence. It does not
collect private data, interpret natural-language content, assert causality, or
write to GitHub.

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
    python -m unittest tests.test_collaboration_observables -v

## Metric contracts

| Metric | Observable/model | Uncertainty | Prediction and baseline | Main failure modes |
| --- | --- | --- | --- | --- |
| First independent review latency | Hours from ready/open timestamp to first independent review | Deterministic 1,000-replicate bootstrap interval for the observed median; unreviewed items separately right-censored | Lower latency may predict recurrence; compare the preregistered 72-hour groups | Bots/self-review must be removed upstream; censoring and workload confounding |
| Cycle latency | Hours from creation to closure | Same observed-median bootstrap plus open-item count | Review concentration may predict longer cycles | Closure is not necessarily acceptance; right censoring |
| Review HHI | Share-squared over independent review events | Descriptive snapshot only | Compare with equal-share baseline and future cycle latency | Event counts are not effort or quality; identity aliases |
| Ownership HHI | Share-squared over changed-file owner attributions | Descriptive snapshot only | High concentration may identify bus-factor risk | CODEOWNERS/attribution quality and multi-owner files |
| Contributor recurrence | Contributors with at least two meaningful contributions / observed contributors | Beta-binomial posterior with explicit evidence mass | Compare cohorts, never raw activity volume | Eligibility and meaningful-contribution definitions |
| CI evidence | Passing / observed checks | Beta-binomial posterior | Compare like-for-like check suites | Check dependence and heterogeneous coverage |
| Review queue | Count and age of open review-ready PRs at cutoff | Point-in-time state; no sampling interval | Rising age/queue indicates capacity pressure | Snapshot timing and draft-state quality |
| Structural debt | Stable finding IDs attached to observed PRs | Deduplicated bounded inventory count with completeness flag | Track changes only under stable detector definitions | Detector drift and incomplete inventory |

The output also derives provisional strategy weights only from independently
classified verified-useful outcomes, using the same explicit Beta evidence
model. These are evidence summaries, not production-policy activation. Empty
or sparse histories remain visibly uncertain.

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
