# Marginal verifier selection: out-of-sample validation protocol

**Issue:** #693. **Status:** exploratory held-out diagnostic implemented; no confirmatory or external result.

The existing marginal-evidence tool measures gate-specific contributions on
historical ground-truthed candidate rows. In-sample contribution can overfit.
A model family label is not proof of independence.

## Evaluation freeze
Before reviewing test outcomes, choose corpus partition by task/repository
where metadata permits; never split near-identical patches across training and
test. Freeze selected panel S, candidate set V, quorum G, ranking score,
bootstrap count and random seed on calibration-only rows.

## Competing selection rules
- Highest standalone verifier accuracy.
- One-per-declared-family (family uniqueness proxy).
- Lowest measurable pairwise error correlation.
- Uniform eligible candidate seeded at freeze.
- Marginal measured error reduction with uncertainty.

Every rule receives the same S, V, review budget and candidate rows. Optimize
on calibration only. Evaluate the selected verifier on held-out tasks using
paired panel-error difference, false-accept and false-reject rates separately,
and report uncertainty at the task/repository cluster level.

## Abstention and falsifiers
Abstain if insufficient non-probe rows, censored effective votes,
unmeasurable correlation or an interval spanning both benefit and harm.
A winning in-sample rank that underperforms accuracy selection on held-out
rows falsifies claimed predictive advantage. Report negative and neutral
results, raw denominators, seed and the exact corpus revision.

**Authority:** diagnostic only. No provider dispatch, verifier sovereignty,
acceptance, GitHub merge or human decision is granted.


## Implemented exploratory held-out primitive

`idkmesh.marginal_evidence.analyze_heldout_verifier_addition(calibration,
holdout, current_verifier_ids=..., candidate_verifier_ids=...)`
validates complete independent *candidate IDs*, identical gate/quorum/verifier
identities, and analyzes **calibration only** to select a unique candidate
with a positive measured panel-error improvement. It abstains on unresolved,
non-positive or tied point estimates; after selection it audits only the
frozen candidate on the held-out rows. Input digests and sample counts are
retained. Tests prove that changing held-out verdicts cannot change
calibration selection and that overlap/quorum mismatch fails closed.

**Scientific limitation:** disjoint IDs do not establish independent
repositories, patches or task groups. The current matrix format carries no
task-family provenance, so an external preregistered group splitter is still
required. The method is *exploratory point-estimate only*, not a supported
routing algorithm or a publishable out-of-sample estimate without uncertainty
intervals and group-level replication. Human integration remains separate.
