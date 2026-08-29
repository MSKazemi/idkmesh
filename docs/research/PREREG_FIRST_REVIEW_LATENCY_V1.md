# Preregistration v1: First-Review Latency and Contributor Recurrence

**Protocol id:** `prereg-first-review-latency-v1`
**Registered:** 2026-08-30, against `main` with **zero** eligible observations.
**Analysis code:** `scripts/prereg_first_review_latency.py` — the specification *is* the code.
**Status:** registered and not analyzable. No estimate has been produced.

## Why register now

Issue 86 asks for one preregistered causal community experiment, naming
first-review latency to second-contribution probability as the example.

The credible moment to register is when the data cannot possibly have informed the design.
That moment is now, and it is checkable rather than asserted. The most recent production
snapshot, `results/collaboration/snapshot-2026-08-29T22-03-24Z.json`, contains **zero**
independent reviews across fifty pull requests. Running the analysis script against it
returns `analyzable: false` with both arms empty and every unit falling into the
`never_independently_reviewed` stratum.

There is no result to have peeked at. A protocol written after contributors arrive could
never make that claim.

## Hypothesis

A contributor whose first pull request receives its first independent review sooner is more
likely to make a second contribution.

## Specification

Every value below is a constant in the analysis script. Changing one forks the protocol
into a new version; it does not amend this one.

| Element | Value | Note |
| --- | --- | --- |
| Unit | The author's earliest closed pull request in the window | One unit per author |
| Exposure | Hours from `review_ready_at` to `first_independent_review_at` | |
| Boundary | **72 hours**, closed on the slow side | Named in issue 86; fixed before data |
| Arms | `reviewed_within_boundary`, `reviewed_after_boundary` | |
| Stratum | `never_independently_reviewed` | Reported, excluded from the estimate |
| Outcome | A second closed pull request by the same author | |
| Window | **90 days** from the first closure | |
| Estimand | Risk difference, `p_fast - p_slow` | |
| Prior | Beta(1, 1) on each arm | No prior evidence exists to be informed by |
| Inference | Deterministic grid convolution, 2001 points | No RNG, no seed |
| Minimum | **20 units in each arm** | Below this, no estimate is produced at all |

`analyzable: false` is a result, not a failure. An estimate from an underpowered sample is
the specific outcome this document exists to prevent.

## The exclusion that matters most

`never_independently_reviewed` is currently the entire population. Excluding it is not a
convenience: a unit with no review has no exposure value, so it cannot be assigned to an
arm without inventing one.

But the exclusion is also the study's largest threat. If review is allocated by the same
judgment that predicts contributor quality, the two arms differ by more than latency, and
the unreviewed stratum differs from both. That is not fixable by analysis.

## This is not a causal design, and the randomized version is specified

The observational arm above yields an association. `interpretation` is hard-coded to
`descriptive_association_not_a_causal_effect` and `authority.causal_claim` to `false` so
that no consumer can read it as more.

To earn the causal claim, review order must be randomized rather than chosen:

1. Collect pull requests that are review-ready and not yet reviewed into a batch.
2. Randomize each into `prompt` (reviewed within 24 hours) or `standard` (reviewed on the
   normal queue), with the assignment recorded before review.
3. Analyze by intention-to-treat on assignment, not on realized latency.
4. Pre-register the batch size from a power calculation on the observational estimate.

This is not implemented, and it must not be implemented while a single maintainer is the
only reviewer: deliberately delaying a newcomer's first review to fill an arm is an
experiment on people, and the cost falls on the contributor rather than the researcher.
**The randomized design is contingent on a reviewer pool large enough that the standard arm
is the status quo rather than an imposed delay.**

## Threats to validity, stated before any data

- **Closure is a proxy for merge.** The snapshot carries no merged flag, so a closed-unmerged
  pull request counts as a unit and as recurrence. This inflates both arms and is declared in
  the script rather than hidden.
- **Bounded window.** Fifty pull requests is not repository history. A contributor whose first
  pull request precedes the window is misclassified as new.
- **Pseudonymized identity.** One human with two accounts is two contributors.
- **Recurrence is not value.** A second closed pull request may be trivial or may be rejected.
- **Single-maintainer confounding.** With one reviewer, latency reflects that person's
  availability, which correlates with everything else about the repository at that moment.
- **Right censoring.** A contributor whose first closure is within 90 days of the cutoff has
  not had a full window to recur, and is currently counted as not recurring.

## Anti-Goodhart commitment

First-review latency must not become a target. If this study finds an association, the
response is not to minimize latency: a reviewer optimizing the clock produces faster, worse
reviews, and the measured outcome improves while the thing it proxies degrades.

Nothing in CI enforces latency, no workflow reads this protocol's output, and the analysis
script declares `policy_activation: false` and `github_write: false`.

## Stopping rule

The analysis runs whenever a collaboration snapshot is collected. It reports nothing until
both arms reach 20 units. There is no interim look, no optional stopping, and no
data-dependent choice of boundary or window — because there is nothing left to choose.

## Registration evidence

```console
$ PYTHONPATH=. python scripts/prereg_first_review_latency.py \
    results/collaboration/snapshot-2026-08-29T22-03-24Z.json
  "analyzable": false,
  "not_analyzed_because": "each arm requires at least 20 units; observed 0 and 0"
```

The machinery is validated against synthetic populations with known answers in
`tests/test_prereg_first_review_latency.py`, including direction, reversal, the null case,
the boundary, the recurrence window, and determinism. The correctness of the analysis is
therefore established before the data exists, which is the other half of what
preregistration is for.
