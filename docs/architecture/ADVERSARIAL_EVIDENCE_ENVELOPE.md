# Adversarial Evidence Envelope

Status: experimental mathematical control-plane primitive. It is read-only and grants no repository integration authority.

## Purpose

IDKMesh already discounts correlated verification evidence and now has sequential and drift-aware statistical guards. Those mechanisms do **not** answer a different question:

> What if some accepted verifier/agent reports are arbitrary, faulty, compromised, or strategically false?

The Adversarial Evidence Envelope addresses only that report-contamination question. It deliberately uses a deterministic count-bounded model so its central guarantee does not depend on independence, a reliability prior, or a fitted distribution.

It is not a Byzantine consensus protocol, a Sybil-resistance system, or a proof that honest reports are externally correct.

## 1. Model

Observe scalar reports

```text
x_1, ..., x_n in [a,b]
```

and declare a reviewed fault budget

```text
0 <= f < n.
```

The model assumption is only:

```text
at most f accepted reports are arbitrary.
```

Therefore the unknown honest set `H` has size

```text
|H| >= n - f.
```

No stochastic independence is required for the deterministic envelope below.

## 2. Sharp honest-mean envelope

Sort the observed reports:

```text
x_(1) <= x_(2) <= ... <= x_(n).
```

Let

```text
m = n - f.
```

Define

```text
L_f = mean(x_(1), ..., x_(m))
U_f = mean(x_(f+1), ..., x_(n)).
```

Then every possible mean of the honest reports under every corruption assignment of size at most `f` satisfies

```text
L_f <= mean(H) <= U_f.
```

### Why the lower bound holds

Any admissible honest set has size `h >= m`. Among all subsets of size `h`, the smallest possible mean is the mean of the `h` smallest observations. Adding ordered values beyond the first `m` cannot reduce the average below the average of the first `m`, so

```text
mean(H) >= L_f.
```

The upper-bound argument is symmetric.

### Why the interval is sharp

The lower endpoint is attained by the admissible assignment that marks the largest `f` observations faulty, leaving the smallest `n-f` reports honest. The upper endpoint is attained by marking the smallest `f` observations faulty.

Thus, given only the observed scalar reports and the count bound, no uniformly tighter honest-mean interval is possible.

This is the certificate used by the implementation. The ordinary median and `f`-trimmed mean are emitted only as descriptive robust summaries; they are **not** substituted for the sharp envelope proof.

## 3. Threshold certification

For decision threshold `theta` and non-negative margin `gamma`:

```text
support certified  iff L_f > theta + gamma
reject certified   iff U_f < theta - gamma
otherwise          uncertainty remains under the fault budget.
```

The important quantifier is **every**:

- `support_certified` means every admissible honest subset has a mean above the support boundary;
- `reject_certified` means every admissible honest subset has a mean below the reject boundary.

A naive mean can cross a threshold while the adversarial envelope still overlaps it. The implementation records that as `naive_decision_fragile=true` instead of allowing the aggregate to hide sensitivity to one or more arbitrary reporters.

## 4. Binary verifier votes

Binary votes are the special case `x_i in {0,1}`. The same envelope becomes an exact range for the possible honest support fraction.

A strict honest support majority is certified when

```text
L_f > 1/2.
```

Equivalently, if `s` reports support and `r` reject, the worst case marks up to `f` support reports faulty. A support majority is guaranteed when

```text
s - f > r.
```

The implementation also reports weaker facts such as whether at least one honest support is guaranteed (`s > f`).

These are report-set certificates. They are not asynchronous/synchronous Byzantine consensus safety/liveness theorems.

## 5. Fault-budget sensitivity

The fault budget is a model choice and must not disappear into a single score. IDKMesh therefore emits a sensitivity curve

```text
f = 0, 1, 2, ...
  -> [L_f, U_f].
```

As `f` increases:

```text
L_f is non-increasing,
U_f is non-decreasing,
U_f - L_f is non-decreasing.
```

This makes the cost of stronger adversarial assumptions visible. A decision that survives only `f=0` is qualitatively different from one that survives several arbitrary reports.

## 6. Relationship to correlation-aware Bayesian aggregation

Correlation and arbitrary contamination are orthogonal failure modes.

The existing `bayesian_vote_posterior()` in `scripts/evolution_math.py` discounts evidence according to declared reviewer reliability, group membership, and within-group correlation. That is a probabilistic model and can be useful when those assumptions are credible.

The adversarial envelope instead asks:

```text
without trusting any distribution or reliability model,
what can still be certified if <= f accepted reports are arbitrary?
```

Neither subsumes the other:

- correlated honest reviewers can all make the same mistake; the count-contamination envelope does not make them independent;
- a low-correlation model does not protect against a verifier whose report is intentionally arbitrary;
- a report can be both correlated and faulty.

Future composition should preserve both uncertainty channels rather than convert one into the other.

## 7. Sybil and identity boundary

The guarantee is indexed by **accepted reports**, so its validity depends on the upstream admission statement `at most f accepted reports are arbitrary`.

If one adversary can mint unlimited accepted identities/reports, the fault-count assumption is false. This module therefore explicitly emits:

```text
sybil_resistance_claim = false
```

Identity diversity, independence provenance, rate limits, stake/cost, proof-of-personhood, hardware attestation, or other Sybil defenses are separate mechanisms and require separate threat models.

## 8. Governance non-compensation

A strong adversarial certificate cannot compensate for a failed repository hard guard:

```text
hard_guard_ok = false
    -> GUARDED
```

Even when `support_certified` is mathematically true, the operational decision remains `guarded` if the governance boundary is not satisfied.

A positive result can only nominate an `experiment_candidate`; it cannot merge, approve, activate compute, rewrite canonical evidence, or change repository settings.

## 9. Limitations

The envelope certifies the mean of the **honest reports**, not external truth. If all honest verifiers share the same bug or corrupted benchmark, the envelope can be narrow and still be wrong about the world.

It also does not model:

- temporal non-stationarity — use the Anytime Drift Guard;
- optional stopping — use the Sequential Evidence Kernel;
- unknown verifier correlation — use/extend the correlation-aware evidence model;
- adaptive identity creation or collusion above the declared `f` budget;
- vector-valued gradients or high-dimensional Byzantine optimization;
- distributed-consensus message scheduling, equivocation, or network partitions.

## Executable surfaces

- `scripts/adversarial_evidence_guard.py` — sharp mean envelope, threshold/binary certificates, and fault-budget sensitivity;
- `tests/test_adversarial_evidence_guard.py` — exhaustive sharpness, fragility, robust support/reject, binary, monotonicity, hard-guard, and fail-closed invariants;
- `.github/workflows/adversarial-evidence-envelope.yml` — pinned, contents-read, cross-interpreter deterministic CI.
