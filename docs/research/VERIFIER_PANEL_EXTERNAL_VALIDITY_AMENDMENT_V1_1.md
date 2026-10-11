# Verifier-Panel External-Validity Preregistration — Amendment v1.1

**Date:** 2026-10-11  
**Status:** pre-outcome amendment; no X6 or X7 confirmatory verifier matrix is used here  
**Amends:** VERIFIER_PANEL_EXTERNAL_VALIDITY_PREREG_V1.md  
**Issues:** #936, #971, #979, #980, #1023  
**Security dependency:** #804

## 1. Why this amendment exists

Preregistration v1 correctly froze the main scientific question, the requirement
for a materially different replication family, the competence screen, the
held-out confirmatory stage, and the rule that negative or infeasible outcomes
must be retained.

The later S3 program introduced a stronger real-candidate instrument: public
SWE-bench patches submitted by systems the project did not design. That improves
candidate realism substantially. It also creates design details that v1 did not
freeze tightly enough.

This amendment closes those details before S3 confirmatory verifier outcomes are
collected. It does not erase or rewrite v1. Where the two documents conflict,
this dated amendment governs S3 and #936 Step 2.

The amendment is deliberately conservative. A result can be positive, negative,
unresolved, underpowered, compromised, or infeasible. No later family may be
introduced merely because an earlier family produced an unfavorable result.

## 2. Two different external-validity questions

S3 contains two scientifically different replications and they must not be
collapsed into one claim.

### 2.1 X6: candidate-distribution external validity

X6 applies deterministic partial-test verifiers to real public candidate patches.
It answers:

> **Does E017's dependence shape persist when the candidate patches were produced
> by real systems and were not designed by IDKMesh?**

This is valuable external validity on the **candidate distribution**.

However, X6's proposed verifier members are subsets of the same hidden-test
collection whose full result supplies the official execution label. Therefore
the verifier evidence is nested inside the adjudication suite. A verifier that
rejects because one of its subset tests fails has, by construction, observed
evidence that also contributes to the full-suite failure.

Consequences:

- X6 must not be described as an independent-ground-truth verifier-family
  replication.
- X6 alone must not satisfy #936 Step 2's positive external-validity exit.
- X6 may support claims about real-patch partial-test dependence, quorum behavior,
  and candidate-distribution transfer.
- The nesting limitation must travel with every X6 paper-facing claim.

Where feasible, X6 should add a **disjoint-adjudication sensitivity analysis**:
tests assigned to an adjudication-only partition are never available to any
partial-oracle member. That sensitivity analysis is informative but does not
replace the official full-suite result.

### 2.2 X7/X10: verifier-family external validity

A positive Paper A external-validity claim requires at least one verifier family
whose verdict mechanism does not contain the ground-truth tests or their outputs.

X7 is the currently named primary path: locally served open-weight LLM judges on
the same frozen patches. An X7 judge may receive the issue/task text, candidate
patch, declared public repository context, and the frozen judging prompt. It
must not receive:

- hidden tests;
- hidden expected outputs;
- official pass/fail labels;
- execution logs from the hidden suite;
- the gold patch or a diff against the gold patch.

X10 may use another materially different verifier family under its own
pre-outcome preregistration. X10 cannot erase, replace, or relabel a negative X7
outcome after that outcome is visible.

**Paper A positive exit rule:** candidate realism from X6 is not enough. The
positive external-validity exit requires X7, X10, or an equivalently independent
family to complete its frozen confirmatory analysis. If no such family passes the
competence/compute gate, Step 2 exits as negative or infeasible rather than by
weakening the definition of independence.

## 3. Unit of analysis and duplicate patches

Public benchmark submissions are not independent draws. Multiple systems can
submit byte-identical or semantically identical patches, and one organization can
submit many closely related systems.

The primary item identity is:

> **(task_id, canonical_patch_sha256)**

Before any verifier verdict is analyzed:

1. normalize the patch representation by the frozen ingestion code;
2. compute canonical_patch_sha256;
3. collapse exact duplicate patches **within a task** to one primary item;
4. retain every upstream submission as provenance attached to that item.

Primary model fitting gives an exact duplicate patch only one vote.

Producer provenance is another sampling level. Where upstream metadata permits,
freeze a producer lineage as the tuple **(organization, base model, scaffold)**.
The primary patch-level summaries weight each task equally and, within a task,
each producer lineage equally before averaging unique patches within a lineage.
This prevents a team with many closely related submissions from dominating the
measured item-difficulty distribution.

A secondary **ecological-frequency** analysis may weight the same unique item by
the number of upstream submissions that produced it. That analysis is explicitly
secondary and cannot overturn the primary decision.

Near-duplicate patches are not automatically merged. Any semantic-deduplication
method would require a separate preregistered rule because it introduces another
modeling choice. Missing producer provenance is retained as unknown, not inferred
from patch content.

## 4. Candidate sampling and class balance

The patch inventory is frozen before X7/X10 verifier execution.

Selection may use upstream execution labels only to construct the two
ground-truth strata; it may not use any X7/X10 verifier outcome.

Each unique candidate has one official **execution label**:

- **official-pass** — passes the complete official evaluation used by S3;
- **official-fail** — fails that evaluation.

These are operational benchmark labels, not proofs of semantic program
correctness. Paper-facing text must not silently replace "official-pass" with
"correct" or "official-fail" with "incorrect" unless an additional independent
correctness argument exists.

The primary dependence analysis is **class-conditional**. It fits each competing
dependence model separately to official-pass and official-fail candidates, then
reports the macro-average of the two held-out log-score differences:

\[
\Delta_{\mathrm{macro}}
=
\frac{1}{2}
\left(
\Delta_{\mathrm{pass}}
+
\Delta_{\mathrm{fail}}
\right).
\]

This prevents a benchmark's pass/fail prevalence from manufacturing the headline
model comparison.

The pooled analysis retained by E017 is still reported for continuity, but is
secondary for S3.

For safety interpretation, the two unanimous-error events are named separately:

- **false-accept blind spot:** every verifier accepts an official-fail patch;
- **false-reject blind spot:** every verifier rejects an official-pass patch.

They are not pooled into one "blind-spot floor," and neither is described as a
semantic defect rate beyond the benchmark's execution contract.

## 5. Repository, task, and candidate clustering

Candidates share tests within a task, and tasks share code, conventions, and
failure modes within a source repository. Treating every patch as an independent
observation would create pseudo-replication.

The hierarchy is:

> **repository → task → unique patch**

All confirmatory uncertainty must respect that hierarchy.

### 5.1 Cross-validation

For S3, the primary model comparison is repository-grouped:

- if at least 8 eligible source repositories remain, use
  leave-one-repository-out cross-validation;
- if fewer than 8 remain, S3 may still report descriptive/task-level results,
  but it does not earn a cross-repository confirmatory claim.

No task or patch from a held-out repository appears in that fold's model fit.

A task-grouped analysis is reported as a sensitivity analysis for comparison with
v1/E017.

### 5.2 Bootstrap decision rule

Use 10,000 deterministic resamples with seed **20261011**.

Two intervals are reported:

1. a repository-cluster bootstrap that resamples repositories and retains their
   tasks/patches;
2. a task-cluster bootstrap that resamples tasks and retains their patches.

For a positive replication decision, the 95% interval for
\(\Delta_{\mathrm{macro}}\) must be strictly above zero under **both** cluster
schemes.

If one is above zero and the other overlaps zero, the confirmatory result is
**unresolved**.

This dual rule is intentionally conservative because the number of benchmark
repositories is much smaller than the number of candidate patches.

## 6. Competence screen — frozen now

The competence screen applies to the independent-family panel used for the Paper
A external-validity claim.

The complete candidate verifier inventory — checkpoint, prompt, context policy,
decoding parameters, and lineage label — is frozen **before calibration**.
Calibration may select among those frozen members, but it may not edit prompts,
swap models, enlarge context, or create a second calibration wave to rescue an
underperforming panel.

Panel selection uses calibration data only. Confirmatory data cannot add, remove,
reweight, or retune a member.

For every proposed verifier member:

1. run two exact-input replays under the frozen deterministic settings;
2. reject the member if those replays disagree;
3. reject constant-verdict members;
4. require Youden's \(J > 0\);
5. estimate a one-sided permutation p-value for \(J\) using **50,000**
   permutations and seed **20261011**;
6. apply **Bonferroni familywise correction at alpha = 0.05** across every
   proposed member screened in that calibration wave.

A verifier is eligible only if its corrected competence test passes.

For an LLM panel, prompt variants of one base checkpoint are separate panel
members but belong to the same **model lineage** for dependence reporting.
The confirmatory independent-family panel additionally requires:

- at least **20 eligible members**;
- at least **3 base-model lineages**;
- no one lineage contributing more than **50%** of eligible members.

If 12–19 competent members remain, the matrix may be retained as a feasibility
result but cannot satisfy the v1 positive confirmatory gate. If fewer than 12
remain, record the family as infeasible under this amendment.

### 6.1 Benchmark-contamination boundary for LLM judges

Public coding benchmarks may appear in model pretraining, instruction tuning, or
benchmark-specific fine-tuning. "The judge did not receive the hidden tests at
inference time" is therefore not proof that the checkpoint has never seen the
task, gold patch, or evaluation artifacts.

For every LLM lineage, retain:

- model/checkpoint release date;
- disclosed training-data cutoff when available;
- any disclosed SWE-bench/code-repair fine-tuning;
- whether benchmark contamination is **ruled out, known possible, or unknown**
  from public model documentation.

A lineage explicitly fine-tuned on the same benchmark's gold patches, hidden
tests, or official evaluation outputs is **ineligible for the primary
independent-family panel**.

Unknown contamination is not converted into "clean." The primary result reports
the contamination class of every lineage. If at least 20 eligible members remain
after excluding all lineages with known possible same-benchmark contamination,
run that exclusion as a preregistered sensitivity analysis. If fewer remain,
report the limitation rather than claiming contamination robustness.

This rule addresses known benchmark exposure; it cannot prove absence from an
undisclosed training corpus.

## 7. Execution failures and retry rule

The primary analysis requires a complete binary matrix after verifier-level
eligibility decisions.

One retry is allowed only for a documented infrastructure failure and must use
the exact same:

- candidate digest;
- verifier configuration;
- model/checkpoint digest;
- prompt digest;
- sandbox/image digest;
- seed and decoding settings.

Both the failed attempt and retry are retained.

After that retry:

- a member with any unresolved confirmatory verdict is excluded as a whole;
- items are never dropped selectively to repair a member;
- if fewer than 20 eligible members remain, the independent-family confirmatory
  result becomes infeasible rather than changing the threshold.

The retry rule does not permit prompt edits, model changes, larger context, or
different decoding after a confirmatory failure.

## 8. Power and precision gate replaces the arbitrary task minimum

The "at least 24 task groups / 72 candidates" language in v1 remains a historical
minimum, not the S3 sample-size justification.

Before confirmatory execution, Stage A must produce a machine-readable
power_plan.json from calibration data using a frozen script.

The script may use calibration outcomes only to estimate **variance and cluster
structure**. It must not use the observed calibration effect direction to choose
the confirmatory sample size.

### 8.1 Smallest effect of interest

The smallest predictive improvement the confirmatory design is powered to
distinguish is:

\[
\delta_0 = \log(1.10) \approx 0.09531
\]

nats per item in held-out predictive log density, corresponding to a 10% geometric
mean predictive-likelihood advantage. This 10% threshold is the ex-ante
**smallest effect of interest** for sizing: smaller positive effects are still
reported, but the design does not claim to have been powered to distinguish them.

### 8.2 Sizing rule

Using the calibration repository/task structure, center the calibration
per-task log-score differences at zero, inject \(+\delta_0\), and run a
deterministic cluster-resampling power simulation.

Evaluate candidate confirmatory task counts from the frozen ladder:

> **50, 75, 100, 150, 200, 300, 500, then the full eligible universe if different.**

Choose the smallest count for which the preregistered primary decision rule
(repository and task cluster intervals both above zero) succeeds in at least
**90% of 10,000 simulated cohorts**.

The confirmatory sample must also contain at least 8 source repositories and
enough correct and incorrect items to fit both class-conditional models.

If the available eligible universe cannot reach 90% simulated power for
\(\delta_0\), S3 is labeled **underpowered for the positive confirmatory claim**.
It may still publish the complete descriptive result; it may not lower
\(\delta_0\), change the decision rule, or extend the sample after unblinding.

## 9. Calibration/confirmatory separation

Stage assignment is frozen before any independent-family verifier run.

Tasks, not individual candidate patches, are the minimum separation unit.
No task may appear in both calibration and confirmatory stages.

Where repository counts permit, calibration and confirmatory repository sets
should also be disjoint. If that would leave fewer than 8 confirmatory
repositories, task-disjoint calibration is allowed, but the limitation must be
reported and the stronger new-repository generalization is not claimed.

The stage-assignment algorithm and seed are part of the frozen manifest.

## 10. Analysis-code and environment freeze

Before the first confirmatory verdict is computed, commit:

- exact analysis source SHA-256;
- exact power-planning source SHA-256;
- verifier inventory and lineage metadata;
- candidate inventory and patch digests;
- stage assignment;
- model/checkpoint identifiers and hashes where available;
- prompt/configuration digests;
- sandbox/container image digest;
- dependency lock or environment manifest;
- bootstrap/permutation seeds;
- upstream benchmark commit and file digests.

The confirmatory report must name the exact Git commit containing that freeze.

A later bug fix to analysis code requires:

1. retaining the original output;
2. documenting the defect;
3. rerunning from the same raw matrix;
4. reporting both the frozen and corrected analyses when the bug could affect the
   decision.

## 11. Primary decision hierarchy

The confirmatory interpretation is ordered so that a favorable secondary result
cannot rescue a failed primary gate.

1. **Instrument admissibility:** security/sandbox, provenance, stage separation,
   complete matrix, and competence gates pass.
2. **Power admissibility:** the frozen power plan reaches the 90% criterion or
   the full universe is explicitly underpowered.
3. **Primary independent-family H1:** class-macro, repository/task-clustered
   \(\Delta_{\mathrm{macro}}\) for item difficulty versus shared shock.
4. **Secondary shape diagnostics:** partial-majority failures, quorum frontier,
   Kish/effective votes, lineage correlations.
5. **Blind spots:** false-accept and false-reject unanimous errors, each with
   finite-sample uncertainty.
6. **X6 real-patch partial-oracle result:** candidate-distribution replication,
   always labeled with the nested-ground-truth limitation.

Only item 3 can supply the positive independent-family external-validity claim for
Paper A.

H1 is the only confirmatory hypothesis frozen by this amendment. H4 (budget
allocation/harvest) and H5 (attack surface) remain scientifically important, but
their confirmatory endpoints, multiplicity family, and decision rules must be
frozen separately before they can be called confirmatory. A favorable H4/H5
secondary pattern in the H1 dataset cannot be promoted after inspection.

## 12. Paper-facing language allowed after S3

### If the independent-family result is positive

Allowed, if supported by the retained artifacts:

> On a second, materially different verifier family over real public patches,
> the item-difficulty model predicted held-out error-count structure relative to
> execution-graded benchmark labels better than the equal-complexity
> shared-shock model under repository- and task-clustered inference.

Not allowed:

> Verifier dependence universally follows a beta-binomial model.

### If X6 is positive but X7/X10 is negative, unresolved, or infeasible

Allowed:

> The E017 shape transferred from constructed candidates to real public patches
> for a nested partial-test panel, but independent verifier-family external
> validity remained negative, unresolved, or infeasible.

This is a scientifically useful result and must not be hidden.

## 13. Security and execution gate

X6 executes untrusted third-party patches. It remains blocked on #804.

No result may be called an S3 execution result until the sandbox backend satisfies
its hostile-code acceptance tests. Raw subprocess execution is not an acceptable
substitute.

X7/X10 may consume the same frozen patch texts without executing them, but their
official labels must still come from the retained execution-graded source named
in the manifest. If the project requires local recomputation of those labels,
that recomputation inherits the #804 gate.

## 14. What remains unresolved after this amendment

This amendment makes the protocol substantially harder to game, but it does not
create evidence.

Still required before Paper A is externally validated:

- #804 sandbox acceptance for local untrusted-patch recomputation;
- a frozen S3 ingestion/stage-assignment manifest;
- the power-planning implementation and digest;
- an eligible independent verifier family;
- raw confirmatory verdicts;
- retained negative/error records;
- exact-head reproduction of the final analysis;
- paper/CLAIM_EVIDENCE_MAP.md update only after the result exists.

## 15. Provenance

This amendment was written on 2026-10-11 in response to issue #1023 after
reviewing the merged v1 preregistration and the later S3 plan (#971/#978/#979/#980).

It is AI-assisted research design under maintainer direction. It is not
independent peer review. Its purpose is to reduce researcher degrees of freedom
before outcome collection, not to strengthen the result after seeing it.
