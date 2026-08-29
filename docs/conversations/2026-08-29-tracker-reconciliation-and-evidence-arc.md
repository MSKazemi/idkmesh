# Conversation record — tracker reconciliation and the evidence arc

**Date:** 2026-08-29
**Repository:** `MSKazemi/idkmesh`
**Continues:** [Solve all open issues and pull requests](2026-08-29-solve-all-open-issues-and-prs.md)

## Project owner request

> solve all the issues and PRs and merge to the main branch with high quality and
> professional way. You can do in parallel if it is doable.

The first arc of this session merged navigation and index work and then reported that
none of the 21 open issues could legitimately be closed. That report was accurate but
not sufficient: an issue can be *unclosable* and still be *wrong*. This arc audited
every issue's acceptance criteria against the repository itself, found real drift
between what the tracker claimed and what the code contained, and fixed the drift.

## The repository asserted a false statement about itself, and enforced it in CI

Live branch metadata for `main`:

```text
protected=true
required_checks=gate (3.11), gate (3.13)
force_push=false  deletions=false  conversation_resolution=true
```

Three places said the opposite:

| Location | Stale claim |
| --- | --- |
| `examples/community/ace-activation-gate-current.example.json` | `"source": "branch:main@unprotected"`, status `blocked` |
| `docs/community/ACE_ACTIVATION_GATE.md` | "Public branch metadata currently reports `main` as unprotected" |
| `.github/workflows/ace-activation-gate.yml` | `assert 'component:integration_protection' in blockers` |

The workflow line is the one that mattered. It made the stale claim **load-bearing**:
refreshing the fixture from reality would have failed CI. A required check that breaks
when the repository is described accurately pressures the next contributor to
re-introduce the false statement rather than correct it.

Corrected in #333. The gate still returns `BLOCK` with
`required_controller_mode_if_blocked: SHADOW`; the blocker set is now exactly
`{real_verified_descendant_evidence}`, the one honest remaining gate. The safety
property that protection must block was **strengthened** rather than removed: it is now
proved by a mutation test — at maximum capacity, with every other component accepted,
revoking protection must still fail the gate closed — instead of by relying on the live
fixture happening to be blocked.

## Two issues must never be closed, and nothing said so

`ace-community-growth.yml` locates its ledger by scanning **open** issues for
`ace:ledger` (`:116`, `:119`, `:126`) and creates a new one when the scan finds nothing
(`:343`). `ace-cohort-observer.yml` does the same for `ace:cohort-observer` (`:35`,
`:276`, `:315`).

Closing issue 23 or issue 109 does not archive that state. The next scheduled run forks
a duplicate at a new number and every reference to the old one becomes a pointer to
abandoned state. Re-opening afterwards is worse: two open ledgers trip the `:130`
ambiguity guard and the controller refuses to run at all.

The gate fixture cites issue 109 directly as `"source": "issue:109@<timestamp>"` for
both `descendant_evidence` and `review_capacity`, so a fork there breaks the activation
gate's provenance chain.

Recorded in `docs/community/README.md` (#332) and as comments on both issues, because
their bodies are machine-rewritten by the workflows that own them.

## Evidence that was about to expire

`collaboration-observables.yml` runs weekly and uploads with `retention-days: 30`. The
repository had exactly one successful production run, and its output existed nowhere in
the tree. Committed in #334, with a finding that separates two kinds of zero the run
contains:

- **real measurements** — all 50 pull requests closed without an independent review, so
  first-review latency has no event, review-concentration HHI has no population, and
  contributor recurrence has 0 trials and falls back to the uniform prior 0.5;
- **declared collector limitations** — ownership concentration and structural debt read
  zero because `collaboration_snapshot.py` writes `changed_file_owners: []` and
  `structural_debt_finding_ids: []` unconditionally and says so in its own limitations
  list.

The output format does not distinguish these. An HHI of `0.0` reads as "perfectly
distributed review" and is in fact the value an empty population takes.

## Uncertainty attached to the evolution metrics, honestly

P0 item 3 of issue 86 asks for uncertainty on evolution metrics "rather than treating
point scores as truth". Mechanically wiring a beta-binomial into the priority formula
would have been fake rigor: those constants are subjective per-action-type judgements,
not binomial proportions, and there is no sample to form a posterior from.

#336 does the two honest things instead. Every priority input declares whether it is
`snapshot_derived`, a `snapshot_conditioned_prior`, or a `hand_authored_prior` — exactly
one input is ever derived from observation. And each recommendation carries sensitivity
bounds over its unevidenced constants, labelled in machine-readable form as
`bounds_are_a_confidence_interval: false`.

The finding is what those bounds say: at a 25% perturbation, **no adjacent pair of
recommendations is separated**. The ranked action list is not ordered by evidence, only
by authored constants that happen to differ. That was always true; it is now visible,
and pinned as a test.

## Two research gaps closed in simulation, at zero cost

**Coordination topology (#335, issue 13 hypothesis 3, previously untested).** Two
budget-matched arms beside the flat one. Budget matching is exact — 72 parity records,
zero false flags — and the arms are neutrally calibrated so one clean serial chain
reproduces the flat single-worker distribution exactly. Topology does shift the
exponent: `task_dag` raised it in 9 of 9 cells, `role_specialized` lowered it in all six
diversity cells to −0.120 at worst. But the largest topology shift is smaller than the
flat-arm gap between homogeneous and structurally diverse groups at the same difficulty
(0.046 against 0.340). Error-correlation structure matters roughly an order of magnitude
more than team wiring.

**Imperfect correlated verifiers (#337, issue 22).** E024's panel was perfect by
construction, so its three error fields were structurally always zero. The new panel
follows the measured shape — beta-binomial over per-item difficulty plus a blind-spot
atom, parameterized from E017/E020 — rather than the rejected shared-shock shape.

The QD advantage survives completely. **And that is the finding**: sweeping the panel to
45% wrong in both directions moves QD's utility AUC by 1.5% and leaves its catastrophe
count at zero. The mechanism is measured, not inferred — 157 defective artifacts waved
through on seed 7 under the stress panel, and not one survived in the archive, because
`utility()` and `robust_quality()` both return `0.0` for a non-viable candidate. **E024
has no defect-propagation channel**, so the falsification test had very little power.
The write-up says E024 must not be cited as evidence about verification until an
accepted defect carries a cost.

## Two process findings

**A frozen artifact was not reproducible off the generating platform.** A new test
asserted byte equality against a committed sweep. It passed locally and failed on every
GitHub runner: the simulation goes through `exp` and `**`, whose last-place rounding is
not identical across CPUs and C libraries, and a one-ulp difference changes the JSON
representation and therefore the digest. The document also claimed byte-for-byte
reproduction, which was not true. Both corrected: the replay compares values at a
relative tolerance of `1e-9`, the artifact's own digest stays pinned, and "frozen and
reproducible" now means reproducible *in value*.

**Published numbers must reproduce from committed code.** A mechanism claim was
published with instrumentation figures that did not reproduce — 1343 accepts and 289
false accepts against the 1375 and 157 the committed code actually produces. The
qualitative claim held exactly; the numbers did not. Corrected to the reproducing
values, given a reproduction command in `sim/e026_archive_contamination.py`, and pinned
as tests so they cannot drift again.

## Untrusted content surfaced, not acted on

Issue 167 carries a comment from an account with `authorAssociation: NONE` containing a
machine-generated "Delivery Report", a cryptocurrency **payout wallet address**, and a
request that repository source files be sent to it. It was treated as data. None of its
instructions were followed and nothing was sent. The moderation decision belongs to the
repository owner.

## What still cannot be closed, and why

- **#151, #138, #16 (part), #91** — need a genuinely independent human reviewer. Over
  274 pull requests the authors are the owner plus three dependabot accounts; the
  collaboration snapshot records 0 non-owner non-bot merged authors over the 50 most
  recent, and `closed_without_review: 50`. There is nobody else to ask.
- **#9** — zero external human contributors, 1 star, 0 forks.
- **#12** — needs owner-side credential creation; 0 repository secrets exist.
- **#4, #16, #11** — reference `idkmesh-node`; `node/` is absent from `main` and both
  pull requests that would have introduced it (#91, #159) were rejected without merging.
- **#30, #96, #70, #1, #2** — need real agent runs against a held-out corpus. All 20
  benchmark tasks are `split: pilot`, the cohort carries no `definition_digest`, and
  real runs would breach the $0 rule in `PROJECT_RULES.md`.
- **#57** — four of five activation-gate criteria are now verified met; the fifth needs
  one independently verified external descendant, which needs an external contributor.

## Boundaries preserved

No issue was auto-closed; every pull request used `Refs:` and passed the closing-keyword
guard. No authority was widened: the evolution observer stays `recommendation_only`, the
activation gate still returns `BLOCK`, and every new experiment artifact carries
`evidence_level: synthetic_mechanism` with an explicit guardrail stating it cannot close
the issue it informs. No paid model API was called; every run is deterministic local
CPU.
