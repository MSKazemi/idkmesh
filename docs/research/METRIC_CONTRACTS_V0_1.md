# Metric Contracts v0.1

Status: descriptive contract, read from the code at repository revision `a805a6bd`
(2026-10-14). It records what each production metric **actually computes today**, not
what a theory document says it should compute. Where the two differ, the code wins and
the gap is stated as an open item.

This page implements the "Requirements" clause of issue #86 (refs #86): a metric or
mechanism that feeds a recommendation must document its assumptions, observables,
uncertainty, prediction, baseline, failure modes (including Goodhart risks), and human
and security constraints. It does **not** close #86: it documents the current state and
makes the gaps visible and guarded; it does not remove them.

Companion pages: [Metric Uncertainty v0.1](METRIC_UNCERTAINTY_V0_1.md) (the Beta-Binomial
helper and reporting rules) and [Collaboration Observables v0.1](COLLABORATION_OBSERVABLES_V0_1.md)
(the collaboration analyzer and its preregistered analysis). Those pages describe the
shared machinery; this page is the per-metric contract.

## How this page is guarded

`tests/test_metric_contracts.py` reads the metric keys out of the code by AST and fails if
a key has no `###` entry here, if an entry lacks any of the seven labelled fields, or if an
entry names a metric the code no longer emits. It checks that the fields **exist and are
non-empty**. It cannot check that the prose is true; that remains a review duty.

## Cross-cutting open items

These apply to many entries and are stated once so each entry can stay short.

- **Hand-authored priors and weights are still in use.** `config/evolution-policy-v1.json`
  holds uniform replicator priors (six at `0.142857`, one at `0.142858`), the carrying-capacity
  constants (`K`, `tau`, issue and PR weights), the targets, and the control-energy weights.
  `state/evolution-live-policy.json` holds a second hand-authored set for the live governor.
  Nothing in the scoring path fits or updates them from outcomes. This is a **known open
  item, not a solved one**.
- **Most repository-evolution signals are bare point values.** A signal such as
  `main_protection` or `branch_pressure` is a deterministic function of one snapshot. It has no
  sampling interval, no posterior and no censoring model. Only the collaboration
  Beta-Binomial rows and the bootstrap latency rows carry an interval, and those intervals
  cover sampling noise under stated assumptions, not measurement validity.
- **No predictive claim has been validated.** "Prediction" below records what the code or a
  document *uses the metric for* (a mode switch, a blocker, a pressure term, a preregistered
  contrast). None of these uses has been calibrated against outcomes in this repository.
- **Every metric is recommendation-only.** The emitted `authority` blocks set
  `recommendation_only`, `automatic_merge`, `automatic_branch_mutation` and
  `automatic_issue_creation` as shown in the code; no metric grants merge, moderation,
  ranking, spending or policy authority.
- **Missing keys do not all fail the same way.** `main_protection` fails closed (absent means
  `0.0`); `workflow_pin_ratio` fails open (absent means `1.0`); the external-witness and
  branch inputs default to `0`. Each entry says which applies.

## Emission map

Which module emits which metric. `scripts/evolution_live_governor.py` duplicates part of
`scripts/repository_evolution_score.py` rather than importing it, so the two must be read
separately. As of the audited revision the governor is referenced by its own test and the
operations module map, and by no workflow under `.github/workflows/`.

| Metric | Emitted by | Function |
| --- | --- | --- |
| `main_protection` | score, governor | `normalized_signals` / `live_signals` |
| `review_capacity` | score, governor | `capacity_metrics` then `normalized_signals` / `live_signals` |
| `independent_review_coverage` | score, governor | `review_metrics` then `normalized_signals` / `live_signals` |
| `starter_task_supply` | score, governor | `normalized_signals` / `live_signals` |
| `external_witness` | score, governor | `normalized_signals` / `live_signals` |
| `workflow_pin_ratio` | score, governor | `normalized_signals` / `live_signals` |
| `work_diversity` | score (inside `signals`); governor (top-level field, outside `signals`) | `normalized_signals` with `shannon_diversity` (score); `work_diversity` (governor) |
| `branch_pressure` | score only | `normalized_signals` |
| `branch_health` | governor only (`1 - branch_pressure`) | `live_signals` |
| `control_energy_proxy` | score only | `control_energy` |
| `homeostatic_potential` | governor only | `evolution_math.homeostatic_potential` |
| `strategy_weights` | score only | `strategy_pressures`, `replicator_response` |
| `priority` | score only | `_priority`, `_scored` |
| `first_independent_review_latency`, `cycle_latency`, `review_concentration`, `ownership_concentration`, `contributor_recurrence`, `ci_evidence`, `review_queue`, `structural_debt`, `evidence_derived_strategy_priors` | `scripts/collaboration_observables.py` | `analyze` |

The collaboration analyzer consumes a snapshot built by `scripts/collaboration_snapshot.py`;
the evolution score consumes a different snapshot built by `scripts/evolution_snapshot.py`.
The two snapshots do not share collection code, so a notion such as "independent review" is
implemented twice with different rules (stated in the relevant entries).

## Repository-evolution signals

Source of inputs: `scripts/evolution_snapshot.py` (`collect`). All signals below are in
`[0, 1]` and are recomputed from scratch for each snapshot.

### `main_protection`

- **Assumptions:** GitHub's branch-API `protected` boolean for the default branch is an adequate proxy for "integration is externally protected". Treats protection as present or absent, with no notion of how strong the rules are.
- **Observables:** `integration.main_protected` in the evolution snapshot, taken from the branch API `protected` field in `evolution_snapshot.collect`. `normalized_signals` maps true to `1.0` and everything else, including a missing key, to `0.0`.
- **Uncertainty:** None modelled. It is a bare binary value read from one API response; there is no interval, and a stale or failed read is not represented as uncertainty.
- **Prediction:** Used as a hard guard, not a forecast. A value below `1.0` forces mode `GUARD` in `determine_mode`, adds the `main_unprotected` blocker, drives `protect` strategy pressure and the `protection_deficit` weight (`2.0`), and emits the `protect-main` action marked `requires_admin`. No claim is made that protection predicts any outcome.
- **Baseline:** None. The comparison is the constant target `1.0`; there is no historical or peer baseline.
- **Failure modes / Goodhart risks:** The boolean is satisfied by any protection rule, including one that requires zero reviews or does not bind administrators, so `1.0` does not mean the review gate is enforced. Fails closed on a missing key, which is the safe direction. Because it is a flag, the cheapest way to raise it is to enable a trivial rule.
- **Human / security constraints:** Reads repository metadata only. The score never changes branch protection; the `protect-main` action needs a human with admin rights. Do not treat `1.0` as evidence of review independence.

### `review_capacity`

- **Assumptions:** Open work consumes reviewer attention additively, with ready PRs weighted most, growth-seed issues next, and other open issues least and capped. The remaining capacity is a logistic function of load with no further structure. The weights, the cap, `K = 8.0` and `tau = 2.0` are authored constants.
- **Observables:** `capacity_metrics` counts non-draft and draft open PRs, issues carrying the exact label `growth-seed`, and other open issues (capped at `other_issue_cap = 20`). Load is `ready_pr_weight*ready + draft_pr_weight*draft + growth_seed_weight*growth + other_issue_weight*capped_other`; capacity is `1 / (1 + exp((load - K) / tau))`.
- **Uncertainty:** None modelled. Counts come from bounded pagination (`_request_all`, at most five pages of 100) and truncation is not propagated into the value. The weights and logistic constants carry no interval.
- **Prediction:** Below `0.35`, or with more ready PRs than `max_ready_prs`, `determine_mode` selects `CONSOLIDATE`. Below `minimum_capacity` (`0.6`) it adds the `review_capacity_below_target` blocker. It also feeds the `consolidate`, `integrate` and `explore` pressures and the capacity deficit. The code does not validate that this load model predicts actual review delay.
- **Baseline:** The raw ready-PR count rule (`max_ready_prs`) coexists with it, and the review-queue age in the collaboration analyzer is the closest observed quantity. No comparison between them is made.
- **Failure modes / Goodhart risks:** Converting PRs to drafts, closing issues, or removing the `growth-seed` label lowers load without removing work. Label-driven weighting means whoever controls labels controls the value. The logistic saturates, so large changes in load near the extremes barely move capacity.
- **Human / security constraints:** Reviewer burden is the quantity being protected; do not use a low value to pressure volunteers to review faster. Label text is untrusted input and is matched only as an exact string.

### `independent_review_coverage`

- **Assumptions:** A ready PR is "independently reviewed" when at least one reviewer who is not the author and not a bot has submitted an `APPROVED` or `CHANGES_REQUESTED` review on the PR's **current head SHA**. Independence means only a different login, not a different organisation or an uncorrelated judgment.
- **Observables:** `evolution_snapshot._normalize_pr` records `independent_review_count` per open PR. `review_metrics` returns reviewed ready PRs divided by ready PRs, and `1.0` when there are no ready PRs. Reviews on an older head are not counted, and a PR whose review list was truncated counts as having none.
- **Uncertainty:** None modelled. It is a ratio of small integers reported as a point value. The Beta-Binomial helper in `scripts/metric_uncertainty.py` exists and is used by the collaboration analyzer, but this signal does not use it.
- **Prediction:** Below `0.5` with at least one ready PR selects mode `VERIFY`; below `1.0` adds the `ready_prs_lack_independent_review` blocker; it drives `verify` and `integrate` pressure and the review deficit (weight `1.2`). Whether coverage predicts defect escape or recurrence is not tested here.
- **Baseline:** None emitted. The target is the constant `1.0`.
- **Failure modes / Goodhart risks:** The empty case returns `1.0`, so a repository with no ready PRs looks perfectly covered. Rubber-stamp approvals and a second account controlled by the author both count as independent. A force-push after approval resets coverage to zero for that PR, which is conservative but noisy. The count is of reviewers, not of review quality.
- **Human / security constraints:** The snapshot stores counts, not reviewer logins. The metric must not be used to rank or discipline individual reviewers.

### `starter_task_supply`

- **Assumptions:** The number of open issues labelled exactly `good first issue` measures how much bounded newcomer work is available, and two such issues is enough (`minimum_starter_tasks = 2`).
- **Observables:** Count of open issues whose labels include `good first issue`, divided by `max(1, minimum_starter_tasks)` and clamped to `[0, 1]` in `normalized_signals`.
- **Uncertainty:** None modelled. Point value from a bounded issue listing; it saturates at the target so it cannot distinguish two issues from twenty.
- **Prediction:** Below `1.0` while `review_capacity >= 0.5` emits the `improve-starter-surface` action, and it feeds the `onboard` pressure and the starter deficit (weight `0.8`). The link from starter-task supply to contributor arrival is a hypothesis and is not validated here.
- **Baseline:** None. The target is a constant.
- **Failure modes / Goodhart risks:** Relabelling issues satisfies the metric without making any task suitable for a newcomer. The label says nothing about whether the task is well specified, still open to claim, or already being worked on. Saturation hides over- or under-supply beyond the target.
- **Human / security constraints:** Label content is untrusted. Do not use this to solicit specific individuals; outreach remains a human, approved action.

### `external_witness`

- **Assumptions:** The number of distinct non-owner, non-bot participants observed is a usable proxy for independent outside engagement, and one such participant meets the target (`minimum_external_participants = 1`).
- **Observables:** `external_participant_count` in the evolution snapshot: distinct logins, other than the repository owner and accounts typed as bots, seen as authors of open issues and PRs, authors of PRs merged in the last 30 days, reviewers, and commenters. `normalized_signals` divides by `max(1, minimum_external_participants)` and clamps.
- **Uncertainty:** None modelled. A set size from bounded pagination; truncation is not propagated. Missing values default to `0`.
- **Prediction:** Below `1.0` together with low starter supply and capacity at or above `0.5` selects `ONBOARD`; it feeds the `onboard` pressure and the external-witness deficit (weight `1.2`). No outcome is predicted from it.
- **Baseline:** None. With the current target of one, the signal is effectively binary.
- **Failure modes / Goodhart risks:** Any commenter counts, including a drive-by, a promotional or spam account, an owner's second account, or an owner-operated automation not typed as a bot. Team members other than the owner count as external. The metric measures presence, not independence or contribution quality, and it is trivially gamed by a sockpuppet.
- **Human / security constraints:** The snapshot keeps only the count, not the logins. Do not publish or cross-reference the underlying identifiers without minimisation, and do not use the count to single out individuals.

### `workflow_pin_ratio`

- **Assumptions:** A GitHub Actions `uses:` reference pinned to a 40-hex commit SHA is supply-chain-safer than a floating tag or branch, and every external reference deserves equal weight.
- **Observables:** `evolution_snapshot.scan_workflow_pins` walks `.github/workflows/*.y*ml` line by line with a regular expression (not a YAML parser), skips `./` and `docker://` references and references without `@`, and reports pinned over total, or `1.0` when there are none. `normalized_signals` clamps it.
- **Uncertainty:** None modelled. It is a full enumeration of the scanned tree, so there is no sampling error, but the line-based scan can mis-handle unusual YAML and that error is not quantified.
- **Prediction:** Below `minimum_workflow_pin_ratio` (`0.95`) adds the `workflow_dependencies_not_fully_pinned` blocker, emits `pin-workflow-dependencies`, and feeds the `maintain` pressure and the pin deficit (weight `0.8`). It is a hygiene rule, not a forecast of compromise.
- **Baseline:** None. The target is a constant.
- **Failure modes / Goodhart risks:** Fails open: if `workflow_supply_chain` or `pin_ratio` is absent the value is `1.0`. A SHA pin proves immutability, not safety, and a pin to a malicious or abandoned commit scores perfectly. Every use counts equally, so a privileged action and a trivial one weigh the same. Pinning can be satisfied while the real exposure lives in scripts or reusable workflows.
- **Human / security constraints:** The scan reads the checked-out tree and executes nothing. Changing pins is a reviewed change; the score only recommends it. Pinned references must still be re-reviewed when updated.

### `work_diversity`

- **Assumptions:** The label taxonomy in `CATEGORY_KEYWORDS` (verification, community, research, maintenance, governance, product, other) partitions open work meaningfully, and a more even spread over the **observed** categories is healthier.
- **Observables:** Open issues and open PRs are assigned the first matching category from their labels; the result is Shannon entropy of the category counts divided by `log(k)` for the `k` categories actually present. Zero items or one category give `0.0`. The score computes it in `shannon_diversity`; the governor computes the same normalised quantity via `evolution_math.normalized_entropy` and emits it outside `signals`.
- **Uncertainty:** None modelled. A descriptive statistic of the current snapshot with no interval, and it is sensitive to small counts.
- **Prediction:** In the score it appears only in the `explore` pressure; it is **not** in the control energy or in `determine_mode`. In the governor it is emitted but not fed to the homeostatic potential. No outcome is predicted from it.
- **Baseline:** None. Normalising by the observed support means two evenly split categories score the same `1.0` as seven evenly split ones, so there is no baseline for how many categories should exist.
- **Failure modes / Goodhart risks:** Label edits move it without changing the work. Normalisation by observed support hides a collapse in category count. The keyword list is hand-authored and first-match-wins, so label order changes the result. Diversity of labels is not diversity of ideas.
- **Human / security constraints:** Uses labels only; titles and bodies are untrusted and are not read. Do not let it steer people toward artificial label variety.

### `branch_pressure`

- **Assumptions:** Branch count above a soft limit signals coordination overhead, and the overhead rises linearly until the count reaches twice the limit.
- **Observables:** `branch_count` (number of branches returned by the branches API, at most three pages of 100) in the evolution snapshot. `normalized_signals` computes `clamp01(max(0, branches - soft) / soft)` with `soft = max(1, maximum_branch_count_soft)` (`40`).
- **Uncertainty:** None modelled. A deterministic count; it is `0` for any count at or below the soft limit and saturates at `1.0` from twice the limit.
- **Prediction:** It feeds the `consolidate` and `maintain` pressures, the `branch_pressure` deficit (weight `0.4`), and emits `converge-stale-branches` when positive. Whether branch count predicts coordination cost is not tested.
- **Baseline:** None. The soft limit of `40` is an authored constant.
- **Failure modes / Goodhart risks:** Counts branches, not staleness, ownership or merge state, so deleting live branches lowers it while a few badly diverged branches do not raise it. A repository below the soft limit is always `0`, which hides growth until it crosses. Deleting branches to move the number is destructive and is exactly what the recommendation is not allowed to do automatically.
- **Human / security constraints:** The recommendation points at a read-only convergence audit, never at bulk merging or deletion. Branch names can contain attacker-chosen text and are not interpreted.

### `branch_health`

- **Assumptions:** Identical to `branch_pressure`; it is the governor's complement of the same quantity.
- **Observables:** `live_signals` in `scripts/evolution_live_governor.py` computes `1.0 - branch_pressure` from `branch_count` and `maximum_branch_count_soft` with the same formula. Present only in the governor, not in the score.
- **Uncertainty:** None modelled; a point value derived from one count.
- **Prediction:** Enters the governor's homeostatic potential (target `1.0`, weight `0.4` in `state/evolution-live-policy.json`) and triggers the `repository_hygiene` need when below `1.0`. Not validated against any outcome.
- **Baseline:** None; the target is the constant `1.0`.
- **Failure modes / Goodhart risks:** The same as `branch_pressure`, with the additional risk that the two modules drift apart because the formula is duplicated rather than shared.
- **Human / security constraints:** The governor is recommendation-only and as audited is not wired into any workflow. See `branch_pressure`.

## Composite mechanisms

### `control_energy_proxy`

- **Assumptions:** A weighted sum of squared deficits summarises overall distance from a healthy state, and the authored weights express the relative importance of the deficits. The report itself states it is not a Lyapunov proof.
- **Observables:** `control_energy` in `scripts/repository_evolution_score.py`: protection, review, starter, external-witness and workflow-pin deficits are `1 - signal`; the capacity deficit is `clamp01((minimum_capacity - capacity) / minimum_capacity)`; the branch term is the signal itself. Energy is `sum(weight * deficit^2)` with the weights from `control_energy_weights`.
- **Uncertainty:** None modelled. The weights (`2.0`, `1.4`, `1.2`, `0.8`, `1.2`, `0.8`, `0.4`) are hand-authored and carry no interval; error in the inputs is not propagated.
- **Prediction:** Emitted and printed in the report; `determine_mode` does not read it, so it does not currently change any decision. No claim is made that lower energy predicts a better outcome.
- **Baseline:** None. There is no historical series, null model, or comparison with an unweighted sum.
- **Failure modes / Goodhart risks:** Squaring lets one saturated deficit dominate. The capacity deficit is one-sided (no penalty for spare capacity). `work_diversity` is not an input. Because the weights are authored, the ranking of what matters is an opinion presented as a number.
- **Human / security constraints:** Advisory only. It must not be used to evaluate people or to unlock automation; the authority block keeps merge and mutation disabled.

### `homeostatic_potential`

- **Assumptions:** The governor's quadratic potential around authored target bands, scaled and weighted, measures distance from a healthy current state. Historical belief must not compensate for a current hard-guard failure (the governor's stated conjunctive rule).
- **Observables:** `evolution_math.homeostatic_potential` over the seven `live_signals` using `homeostasis.targets`, `scales` and `weights` from `state/evolution-live-policy.json`. The key sets must match exactly or it raises.
- **Uncertainty:** None modelled. Targets, scales and weights are authored and carry no interval.
- **Prediction:** Emitted by the governor for monitoring. The mode and blockers are decided by threshold rules, not by this value. No predictive claim is validated.
- **Baseline:** None. The target for most signals is `1.0`; `review_capacity` targets `0.75`.
- **Failure modes / Goodhart risks:** Same single-snapshot and authored-weight limits as `control_energy_proxy`; a second policy file means the two modules can disagree on what is healthy. Targets of `1.0` reward saturation.
- **Human / security constraints:** Recommendation-only; the governor is not referenced by any workflow at the audited revision.

### `strategy_weights`

- **Assumptions:** A replicator-mutator update with uniform authored priors, a selection strength `eta = 0.8` and a mutation rate `mu = 0.08` turns the current strategy pressures into an allocation. The pressures themselves are hand-weighted linear formulas of the signals (constants such as `1.5`, `0.55`, `0.65` live in `strategy_pressures`, not in the policy).
- **Observables:** `strategy_pressures` maps signals and ready-PR count to seven non-negative pressures; `replicator_response` multiplies each prior by `exp(eta * (pressure - mean_fitness))`, renormalises, mixes in `mu/n` uniform mutation, and renormalises. The report calls it a response to the **current** evidence, not historical learning.
- **Uncertainty:** None modelled. The output is a deterministic function of one snapshot and the authored constants; there is no interval and no estimate of how much the uniform prior or `eta` drives the result.
- **Prediction:** It is displayed as a strategy allocation; it does not select the mode or the ranked actions. No claim is validated that the allocation improves outcomes.
- **Baseline:** The uniform prior is itself the null: with equal pressures the output stays near uniform. No alternative allocation rule is compared.
- **Failure modes / Goodhart risks:** **Hand-authored priors are still used and this is a known open item.** The collaboration analyzer can emit `evidence_derived_strategy_priors`, but the score does not consume them; the only consumer found at the audited revision is the issue evidence gate, which counts them. The weights read as a learned distribution but are an authored response. Mutation mixing guarantees every strategy keeps nonzero weight regardless of evidence.
- **Human / security constraints:** Advisory display only; the weights must not be treated as a mandate to reassign people or work.

### `priority`

- **Assumptions:** Candidate action priority is a multiplicative benefit-over-cost form: value, confidence, and shifted unlock, community and reversibility terms over `1 +` review, complexity, coordination and risk. Each part is in `[0, 1]`.
- **Observables:** `_priority` and `_scored` in `scripts/repository_evolution_score.py`. Each part carries a provenance label: `snapshot_derived` (only `unlock`, from the same-repository reference in-degree divided by five), `snapshot_conditioned_prior` (an authored constant selected by an observed boolean, such as whether a PR has an independent review), or `hand_authored_prior`.
- **Uncertainty:** Partly modelled and explicitly **not statistical**. `priority_bounds` is a one-sided joint perturbation of every non-derived part by `AUTHORED_SENSITIVITY = 0.25`, in the helping and hurting direction. The emitted `priority_uncertainty` states `bounds_are_a_confidence_interval: false`; the fraction is itself authored. Adjacent recommendations whose bounds overlap are flagged by `separated_from_next`.
- **Prediction:** Ranks at most ten recommendations; the ranking is a recommendation order, not a forecast of value delivered. Most inputs are authored constants, so the order mostly reflects the authors' priors.
- **Baseline:** None beyond the overlap flag. There is no random or arrival-order baseline, and no replay against actual merged outcomes.
- **Failure modes / Goodhart risks:** **Hand-authored constants dominate and this is a known open item.** Only one of nine parts is derived from the snapshot, and the sensitivity fraction is arbitrary. The in-degree is from text references, which an author can add. A recommendation with a high `priority` may still be unseparated from its neighbour.
- **Human / security constraints:** Natural-language bodies are untrusted; only bounded numeric references are extracted. Actions marked `requires_admin` need a human. Nothing is executed or opened automatically.

## Collaboration observables

Source: `scripts/collaboration_observables.py` (`analyze`, method
`collaboration-observables-v0.4`), over a snapshot from `scripts/collaboration_snapshot.py`.
Logins are pseudonymised in that snapshot (`actor:` plus a repository-salted digest prefix).
The snapshot's own `limitations` list states that the window is bounded and not full
history, that merged PRs are the only contribution proxy, and that ownership is the last
merged toucher inside the window.

### `first_independent_review_latency`

- **Assumptions:** Hours from the first ready-for-review time to the first independent review is the relevant latency. PRs are treated as exchangeable draws for the bootstrap. Independent means a non-author, non-bot reviewer; a `COMMENTED` review counts if its body is non-empty, together with `APPROVED` and `CHANGES_REQUESTED`.
- **Observables:** Per PR, `review_ready_at` is the first `ready_for_review` timeline event, else the creation time for a non-draft PR. `first_independent_review_at` is the earliest eligible review at or after that time and not after the cutoff. The analyzer computes hours for PRs that have both, plus counts of right-censored PRs (no review, still open) and `closed_without_review`.
- **Uncertainty:** A deterministic percentile bootstrap of the median: 1,000 resamples seeded from a SHA-256 of the repository, cutoff and a label, interval from the 2.5th and 97.5th percentiles of the resampled medians. It covers only PRs that **were** reviewed. Censored PRs are counted but excluded from the median, which biases it toward faster reviews. No survival model is applied. Percentile bootstrap intervals on very small samples are known to be unreliable and coverage has not been evaluated here. An empty sample emits `median_hours: null`.
- **Prediction:** The preregistered analysis (`scripts/prereg_first_review_latency.py`, `PREREG_FIRST_REVIEW_LATENCY_V1.md`) contrasts first review at or below 72 hours with above 72 hours against 90-day recurrence. It is observational; a causal claim would need a separate randomised or quasi-experimental design.
- **Baseline:** The analyzer emits none. The only comparison is the preregistered 72-hour split, which is itself a chosen threshold.
- **Failure modes / Goodhart risks:** Pressure to shorten the number rewards fast, shallow, comment-only reviews that still count. Right-censoring and workload confounding bias it. Reviews before the ready time are ignored. The analyzer trusts the snapshot's bot and author filtering for the timestamp, and re-checks it only for the reviewer lists.
- **Human / security constraints:** Reviewers are pseudonymised. The number must not be used to pressure volunteer reviewers or to rank individuals. Natural-language review bodies are not read, only checked for being non-empty upstream.

### `cycle_latency`

- **Assumptions:** Hours from PR creation to closure is the cycle time, and closure of any kind is the event. Same exchangeability assumption as the review latency.
- **Observables:** `closed_at` minus `created_at` for closed PRs, in hours; `right_censored` is the count of PRs with no `closed_at`.
- **Uncertainty:** The same deterministic percentile bootstrap of the median over closed PRs with its own seed label. Open PRs are excluded from the median and only counted, so the median is biased downward in a repository with a long open tail. No survival or competing-risk model is applied.
- **Prediction:** The collaboration doc suggests review concentration may lengthen cycles. This is a hypothesis; no model in the repository tests it.
- **Baseline:** None emitted by the analyzer: no pre-period, peer repository or null model is compared against the median.
- **Failure modes / Goodhart risks:** `closed_at` includes closed-without-merge, so a faster close is not a faster acceptance. Closing stale PRs en masse shortens it. Censoring and PR-size heterogeneity are not adjusted for.
- **Human / security constraints:** Aggregate only; do not use it to evaluate a contributor or reviewer.

### `review_concentration`

- **Assumptions:** The Herfindahl-Hirschman index over distinct reviewer-PR pairs measures how concentrated reviewing is. A reviewer is counted once per PR regardless of how many reviews they submitted.
- **Observables:** `_hhi` over lower-cased reviewer logins, one entry per distinct reviewer per PR; sum of squared shares. The analyzer raises an error if a listed reviewer is the author or a bot. Reported with counts, the number of distinct actors and an explicit status.
- **Uncertainty:** Not modelled: `descriptive_snapshot_no_population_inference`. With no pairs the index is `null` and the status is `undefined_empty_population`, never a default value.
- **Prediction:** High concentration may signal a review bottleneck; the collaboration doc records this only as a hypothesis for cycle time.
- **Baseline:** None. The index is bounded below by one over the number of distinct reviewers, so it is not comparable across populations of different size; a repository with two reviewers cannot score below `0.5`.
- **Failure modes / Goodhart risks:** Reviewer-PR pairs are not effort or quality. Identity aliases split or merge actors. Spreading token reviews across more people lowers the index without improving review. Zero observations yield no value, which must not be read as perfect equality.
- **Human / security constraints:** The `counts` field holds pseudonymised actors; keep it minimised in any public artifact and do not use it to single out individuals.

### `ownership_concentration`

- **Assumptions:** Each changed file is attributed to one owner, the **last merged toucher inside the bounded window**, not to a CODEOWNERS entry, and concentration of those attributions approximates bus-factor risk.
- **Observables:** `_hhi` over `changed_file_owners`, one attribution per changed path per PR; the snapshot builds them from `OWNERSHIP_MODEL = last_merged_toucher_within_window-v1`, and the collector does not read CODEOWNERS.
- **Uncertainty:** Not modelled: the same descriptive-only status as `review_concentration`, `null` when there are no attributions.
- **Prediction:** High concentration may identify bus-factor risk; the code makes no statement when no attribution exists. Not validated.
- **Baseline:** None, with the same size-dependent lower bound as `review_concentration`.
- **Failure modes / Goodhart risks:** The window is not repository history, so ownership of old files is unobserved and absent files do not count. A single large PR attributes many files at once. Multi-owner files collapse to one owner. One actor splitting commits across accounts lowers it.
- **Human / security constraints:** Pseudonymised actors only. Ownership concentration describes files, not people; do not use it for performance assessment or to reassign work.

### `contributor_recurrence`

- **Assumptions:** A contributor is a non-owner, non-bot author of a merged PR in the window; recurrence is having at least two distinct merged-contribution timestamps. Contributors are treated as exchangeable Bernoulli trials with a uniform prior.
- **Observables:** `analyze` counts contributors with two or more distinct meaningful-contribution timestamps over all contributors, and passes the counts to `beta_binomial_summary`. Every listed contributor has at least one contribution by construction, so the success rate is conditional on that.
- **Uncertainty:** Modelled: Beta-Binomial posterior (`beta-binomial-v3`) with exact equal-tail 95% credible interval (`credible_interval_95`) from the Beta quantile, the empirical rate kept separate from the posterior mean, and `prior_only_no_observations` when there are no contributors. The prior is the default Beta(1, 1), a hand-authored uniform prior; this is a known open item. The exchangeability assumption is almost certainly wrong for contributors (heavy-tailed activity) and the interval does not account for it.
- **Prediction:** Used as an outcome in the preregistered E023 analysis contrasting review-latency groups; no forecast of future recurrence is produced.
- **Baseline:** None emitted. The collaboration doc says to compare bounded observed cohorts, never raw activity volume.
- **Failure modes / Goodhart risks:** The window truncates history, so a returning contributor outside it is missed. Merged PRs are the only contribution proxy, so reviewers and issue authors are invisible. Splitting one change into two merged PRs manufactures recurrence. Time-to-return needs a richer cohort or survival model than this.
- **Human / security constraints:** Pseudonymised actors. Do not target or contact individuals because of their recurrence status; outreach is a separate, approved human action.

### `ci_evidence`

- **Assumptions:** Each conclusive check run on a PR head is an exchangeable Bernoulli trial and passing is `success`. Conclusive means `success`, `failure`, `cancelled`, `timed_out`, `action_required`, `stale` or `startup_failure`; neutral, skipped and in-progress runs are excluded.
- **Observables:** `_ci_counts` per PR from the latest check runs on the head SHA; the analyzer sums passed and total across all PRs and calls `beta_binomial_summary`.
- **Uncertainty:** Modelled with the same `beta-binomial-v3` exact equal-tail 95% interval and default Beta(1, 1) prior (hand-authored, known open item). Zero checks is reported as prior-only. The effective sample size is overstated because check runs on one PR are strongly dependent (matrix legs, retries, shared infrastructure failures) and pooling weights large PRs more.
- **Prediction:** None used for decisions in the analyzer. The collaboration doc suggests comparing like-for-like check suites only.
- **Baseline:** None emitted by the analyzer: no per-check historical rate or comparison with another suite is reported alongside the pooled rate.
- **Failure modes / Goodhart risks:** Deleting or skipping flaky checks raises the pass rate. A green check is not a correct change. Pooling hides one PR with many failures.
- **Human / security constraints:** Counts only; no log content is read. A pass rate must not stand in for independent human review.

### `review_queue`

- **Assumptions:** The age of open review-ready PRs at the cutoff measures review backlog; waiting time since ready is the relevant age.
- **Observables:** For PRs with `review_ready` true and no closure, age in hours from `review_ready_at` to the cutoff; the analyzer reports the count, the median and a linearly interpolated 95th percentile.
- **Uncertainty:** Not modelled: a point-in-time state with no sampling interval (`point_in_time_queue-v1`). With few PRs the 95th percentile is close to the maximum.
- **Prediction:** The collaboration doc says rising age or queue indicates capacity pressure; this is not validated and is not used by a decision rule in the analyzer.
- **Baseline:** None emitted. It is the nearest observed quantity to the modelled `review_capacity`, but they are never compared.
- **Failure modes / Goodhart risks:** Snapshot timing dominates; draft-state discipline changes who is counted. Converting a stuck PR to draft removes it from the queue. Closing stale PRs improves it without any review happening.
- **Human / security constraints:** Aggregate ages only. Do not use it to shame maintainers or volunteer reviewers.

### `structural_debt`

- **Assumptions:** Stable finding IDs from the deterministic IDKGraph observatory, attributed to the last observed PR that touched the finding's path, give a bounded count of structural debt in the window.
- **Observables:** `analyze` counts distinct `structural_debt_finding_ids` across PRs and reports the IDs, the number of PRs observed, and the snapshot's `inventory_complete` flag, which is true only if a report was supplied and every finding reached a PR.
- **Uncertainty:** Not modelled: a deduplicated bounded inventory count with a completeness flag (`bounded_inventory_count-v1`). It is a lower bound on debt when the inventory is incomplete.
- **Prediction:** None. The collaboration doc says to track changes only under stable detector definitions.
- **Baseline:** None emitted; comparison across snapshots is meaningful only if the detector is unchanged.
- **Failure modes / Goodhart risks:** Detector drift changes the count without any change in the code. Findings outside the window are unattributed. Deleting or restructuring code to evade a detector lowers the count without reducing real debt.
- **Human / security constraints:** Findings are structural identifiers, not file contents. Do not treat the count as an individual's score.

### `evidence_derived_strategy_priors`

- **Assumptions:** Strategy outcomes labelled `verified_useful` with independent verification are exchangeable Bernoulli trials per strategy, and normalising the per-strategy posterior means gives a usable weight. The independence of verification is asserted by the snapshot, not checked.
- **Observables:** Rows with a `strategy` need a boolean `verified_useful` and `verification_independent` true, otherwise the analyzer raises an error. Per strategy, `beta_binomial_summary` over verified-useful counts, then `normalized_weight = posterior_mean / sum of posterior_means`.
- **Uncertainty:** Each row carries the full `beta-binomial-v3` summary with the exact equal-tail 95% interval, default Beta(1, 1) prior (hand-authored, known open item). The normalised weight itself carries no interval. With one strategy the weight is `1.0` regardless of sample size.
- **Prediction:** None. It is a candidate replacement for the authored replicator priors, but nothing in `repository_evolution_score.py` consumes it; the issue evidence gate counts the rows.
- **Baseline:** The authored uniform prior it would replace. No comparison against it has been run.
- **Failure modes / Goodhart risks:** Empty by design on current snapshots: the analyzer emits no prior unless a separate input has classified outcomes, and merged status or green CI alone is not enough. A self-reported strategy label or an unverifiable independence flag would poison it. The normalisation of independent posterior means is not a model of strategy choice.
- **Human / security constraints:** Emits no prior without independent verification. It must never activate policy; `authority.policy_activation` is `false` in the output.

## Not covered by this page

These outputs are emitted but not contracted here. They are derived from, or are rules over,
the metrics above: the `mode` and `blockers` threshold rules, `control_deficits`,
`strategy_pressure`, `dependency_graph`, `review.approval_coverage`, and the preregistered
first-review-latency analysis (which has its own preregistration). Adding any of them as a
standalone metric would add an entry here and a row to the guard test.
