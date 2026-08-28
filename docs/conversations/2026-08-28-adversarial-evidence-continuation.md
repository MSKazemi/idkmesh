# Continuation: adversarial evidence envelope

Date: 2026-08-28

User request: continue strengthening `MSKazemi/idkmesh` with a more solid mathematical/algorithmic background and implement the result through GitHub-native automation.

## Canonical precondition

The preceding Anytime Drift Guard merged in PR #212 as:

```text
32a8848b85b108154b0837ba2a550be5c86891ee
```

Its canonical default-branch push workflow `33204353541` completed successfully on that exact commit. The same push's Evolution Loop run was cancelled by the repository's concurrency lineage rather than failing a test.

Before starting the next layer, `main` advanced once more through maintenance PR #215 to:

```text
528690273097a4abc926052eec52dba6cde4f28b
```

A direct GitHub branch read still reported:

```text
protected: false
required status-check enforcement: off
```

The new branch `codex/adversarial-evidence-envelope` was created from that exact canonical commit.

## Gap audit

Repository code search found no implementation of:

- Byzantine/count-contamination aggregation;
- trimmed-mean certificate logic;
- median-of-means aggregation;
- geometric-median aggregation;
- contamination envelopes;
- explicit `max_faults` evidence certification.

PR search did find adversarial **calibration** work (for example inert/Goodhart decoys) and earlier R4 text explicitly warning that contributor-level routing would need Sybil/collusion analysis. That is complementary rather than duplicate: adversarial test fixtures check whether one verifier/evaluator is Goodhartable, while this continuation asks what can still be concluded when some accepted **reports themselves** may be arbitrary.

## Existing correlation model checked

`scripts/evolution_math.py` already contains `bayesian_vote_posterior()`, which weights votes by declared reliability and discounts same-group reviewers using an equicorrelation effective-sample-size factor.

That model is probabilistic and explicitly says it is not proof of independence. It does not provide a worst-case guarantee if a bounded number of accepted reports are arbitrary.

The new layer therefore stays orthogonal:

```text
correlation model:
  how much probabilistic evidence should correlated/reliable reports contribute?

count-contamination model:
  what can be certified even if <= f accepted reports are arbitrary?
```

Neither model is treated as a substitute for the other.

## Mathematical construction selected

For sorted scalar reports

```text
x_(1) <= ... <= x_(n)
```

and a declared maximum of `f < n` arbitrary reports, the unknown honest set has size at least `n-f`.

Define

```text
L_f = mean(x_(1), ..., x_(n-f))
U_f = mean(x_(f+1), ..., x_(n)).
```

Then every admissible honest-set mean lies in

```text
[L_f, U_f].
```

The interval is sharp given only the observed reports and count bound: each endpoint is attained by an admissible assignment that marks the opposite `f` extremes faulty.

This gives a deterministic, distribution-free **report-level** certificate. It makes no independence assumption, but it also makes no external truth claim.

## Decision composition

For threshold `theta` and reviewed margin `gamma`:

```text
support_certified iff L_f > theta + gamma
reject_certified  iff U_f < theta - gamma
otherwise         observe_adversarial_uncertainty
```

The module also compares this robust certificate with the ordinary mean. If the naive mean crosses the threshold but the sharp adversarial envelope does not, the output records:

```text
naive_decision_fragile = true
```

This exposes sensitivity rather than hiding it in a point score.

Hard governance remains conjunctive:

```text
strong robust certificate + hard_guard_ok=false -> guarded
```

## Binary verifier votes

Binary support/reject votes use the same sharp envelope. A strict honest support majority is certified exactly when the lower possible honest support fraction exceeds `1/2`.

The implementation additionally records whether at least one honest support/reject is guaranteed under the fault budget.

## Fault-budget sensitivity

Because `f` is a threat-model parameter rather than observed truth, the module emits a sensitivity curve over fault budgets. The certified interval width is required to be non-decreasing as `f` increases.

## Concurrent human-review work

While this branch was being assembled, `main` advanced again through PR #203 to:

```text
bc5b15541963d1ed2f9ce812f1d7f291628d0c2d
```

That PR adds deterministic validation and descriptive scoring for an **individual human review session** plus provenance/independence disclosures. Its protocol explicitly preserves disagreement and does not interpret agreement as correctness.

This is complementary to the adversarial envelope:

```text
review-session validator:
  is one submitted review structurally/provenance-valid and what descriptive metrics does it contain?

adversarial evidence envelope:
  after several accepted scalar/binary reports exist, what honest-report mean range is guaranteed if <= f reports are arbitrary?
```

The new human-review files do not overlap this branch's five files and do not implement a multi-review fault-budget aggregator.

## Explicit non-goals

The implementation intentionally emits false claims for:

```text
truth_claim
sybil_resistance_claim
byzantine_consensus_claim
```

The fault budget counts **accepted reports**. If one adversary can create unlimited accepted identities, the assumption can fail. Network consensus, equivocation, partitions, identity admission, and contributor governance therefore remain separate problems.

## Reproducibility discipline

The implementation uses explicit left-to-right floating accumulation rather than Python's version-dependent built-in float `sum()` behavior. This carries forward the reproducibility lesson discovered by PR #212's first failed cross-version run.

The companion workflow is designed to run Python 3.11 and 3.13 in one contents-read job, execute the adversarial invariants, generate deterministic JSON twice, compare the payloads byte-for-byte, and publish an explicit content SHA-256.

No issue/PR mutation, merge authority, repository setting change, secret use, or compute activation is introduced.
