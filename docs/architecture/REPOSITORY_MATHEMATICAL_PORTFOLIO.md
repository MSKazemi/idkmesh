# Repository Mathematical Portfolio

**Status:** executable advisory v0.1  
**Date:** 2026-08-28  
**Authority:** read-only observation and attention allocation

## Purpose

`MATHEMATICAL_EVOLUTION_KERNEL.md` defines reusable mathematical primitives. This layer applies those primitives to the repository's live public work portfolio so the mathematics affects what IDKMesh examines next rather than remaining only a library/demo.

It answers a bounded question:

> Given the current open issues, pull requests, explicit dependency statements, and latest trusted repository-health checkpoint, where is attention or experimentation most informative now?

It does **not** answer:

- which change is correct;
- which PR should be approved;
- which issue should be closed;
- which branch should be merged;
- whether a contributor or agent is trustworthy.

Those remain downstream verification/governance decisions.

---

## 1. Observable repository state

The GitHub Action builds a public snapshot from GitHub CLI/API data:

```text
open issues
+ open pull requests
+ titles / bodies / labels
+ comment counts
+ authors
+ timestamps
+ explicit dependency phrases
+ latest trusted Bayesian evolution-health checkpoint
```

No private repository data, secrets, or external services are required.

The raw snapshot is ephemeral because it contains untrusted issue and pull-request
text. The retained checkpoint stores the derived feature vectors, rankings,
state, report, and policy; exact-input replay requires reacquiring the public
source data or an explicitly governed future evidence contract.

---

## 2. Strategy partition

Each open item is mapped transparently into one experimental strategy class:

```text
community
exploration
maintenance
product
safety
verification
```

The mapping uses versioned keyword lists in:

`state/repository-portfolio-policy.json`

This is a deterministic semantic heuristic, not a learned ontology. Ties are resolved deterministically and all coefficients remain reviewable data.

The partition lets IDKMesh ask both:

1. which individual items are Pareto-interesting? and
2. is the repository over-concentrating attention in one mode of work?

---

## 3. Transparent proxy vector

For each issue or pull request `i`, the observer constructs

```text
z_i = (
  impact,
  information_gain,
  unlock,
  diversity,
  risk,
  cost,
  review_burden
).
```

The first four are maximized; the last three are minimized.

These values are **transparent proxies**, not causal truth.

Examples of the v0 signals include:

- `impact`: explicit priority labels, verification/safety signals, age, and current health need;
- `information_gain`: unresolved-information proxy from sparse discussion/body evidence;
- `unlock`: only explicit dependency graph reachability;
- `diversity`: rarity of strategy/author within the live open portfolio;
- `risk`: security/risk/bug/high-priority signals;
- `cost`: body/discussion/large-change proxies;
- `review_burden`: discussion, risk, size, and age proxies.

All bounded mathematical features used by Pareto ranking are normalized to `[0,1]`.

The policy file is intentionally separate from code so the repository can later calibrate or replace these proxies using measured outcomes.

---

## 4. Explicit dependency graph and unlock value

The observer deliberately refuses to infer dependencies from arbitrary `#123` references.

It creates an edge only for explicit phrases:

```text
blocked by #N
 depends on #N
 requires #N
 blocks #N
```

Semantics:

```text
"issue A blocked by #B"  => B -> A
"issue A depends on #B" => B -> A
"issue A requires #B"   => B -> A
"issue A blocks #B"     => A -> B
```

For open-issue graph distance `d(i,j)`, the kernel computes discounted downstream unlock:

```text
Unlock(i) = sum_j value(j) * exp(-lambda * d(i,j)).
```

The result is normalized within the current portfolio before Pareto ranking.

This makes prerequisite/bridge tasks visible while preserving a strict epistemic rule: **missing dependency evidence is not invented graph structure**.

---

## 5. Pareto / NSGA-II attention frontier

The controller does not collapse the portfolio immediately into one score.

Candidate `a` dominates `b` only when `a` is no worse in every configured objective and strictly better in at least one.

The observer therefore computes:

1. non-dominated Pareto fronts;
2. NSGA-II crowding distance inside each front;
3. a diagnostic scalar opportunity only as a deterministic tie-break/explanation aid.

This prevents a high-impact/high-risk item from being silently equated with a lower-impact/low-risk item through one arbitrary scalar weight.

Pull-request results are explicitly called **review-attention candidates**, not approvals.

---

## 6. Diversity and portfolio concentration

For strategy counts `n_k`, define normalized Shannon entropy:

```text
H = -sum p_k log2(p_k) / log2(K).
```

Low entropy means current open work is concentrated in a small subset of strategy classes.

The controller also compares the current open-issue strategy distribution `P` with the previous attention mixture `Q` using Jensen-Shannon divergence:

```text
JSD(P,Q)
 = 1/2 KL(P || M) + 1/2 KL(Q || M),
M = (P+Q)/2.
```

This provides a bounded measure of portfolio-attention mismatch without assuming that uniform work distribution is always optimal.

---

## 7. Bayesian health need -> multiplicative attention weights

The latest trusted `IDKMesh Evolution Loop` checkpoint provides posterior health means.

For positive health dimension `d`:

```text
need_d = max(0, (target_d - current_d) / scale_d).
```

For `risk_debt`, lower is better:

```text
need_risk = max(0, (current_risk - target_risk) / scale_risk).
```

Each strategy maps to a small set of health dimensions. The resulting strategy need is used as an **attention signal** in multiplicative weights:

```text
w_k' proportional to w_k * exp(eta * need_k).
```

An exploration floor prevents any strategy from disappearing entirely.

Important interpretation:

> `need_k` is not causal reward. It says the current repository state suggests more attention to that dimension, not that past work in that strategy caused improvement.

---

## 8. UCB exploration focus

The portfolio also maintains a tiny trusted-main checkpoint of how many times each strategy has been selected for exploration attention.

For strategy `k`:

```text
UCB_k = current_opportunity_k
        + c * sqrt(log(total_pulls + 1) / pulls_k).
```

An unseen strategy receives infinite initial exploration priority.

`current_opportunity_k` is the best current bounded opportunity proxy among live candidates in that strategy.

This gives IDKMesh a principled answer to:

> Which under-explored strategy should receive the next bounded experiment or human inspection?

It does not auto-create or execute that experiment.

---

## 9. Persistent but non-authoritative GitHub memory

The workflow uses the same safe checkpoint pattern proven by the Bayesian evolution observer.

For trusted default-branch runs:

```text
successful main portfolio run N
  -> repository-portfolio-checkpoint-v2-N artifact

main portfolio run N+1
  -> Actions API finds a successful allowlisted trusted-event run
  -> exact artifact, provenance manifest, size, and SHA-256 verify
  -> actions/download-artifact restores state
  -> update strategy weights / UCB counts
  -> publish checkpoint N+1
```

The workflow also downloads the latest trusted Bayesian evolution checkpoint to compute health needs.

Ordinary PR runs can test the code and produce artifacts, but their event type is
explicitly excluded from trusted future-state selection. A selected artifact that
cannot be downloaded or validated aborts rather than silently resetting to seed.

Permissions remain:

```text
contents: read
issues: read
pull-requests: read
actions: read
```

There is no GitHub write token surface in this workflow.

---

## 10. GitHub-native loop

The `Repository Mathematical Portfolio` Action runs on:

- relevant code/policy pushes and PRs;
- issue lifecycle/label changes;
- manual dispatch;
- a twice-weekly scheduled audit.

Execution:

```text
checkout
 -> compile + invariant tests
 -> restore trusted portfolio checkpoint when on main
 -> restore latest trusted Bayesian health checkpoint
 -> gh issue list / gh pr list
 -> normalize public snapshot
 -> classify strategies
 -> explicit dependency graph
 -> Pareto fronts + crowding + unlock
 -> entropy/JSD
 -> multiplicative attention update
 -> UCB exploration focus
 -> JSON + Markdown report
 -> retain derived state/report/policy artifact; discard raw snapshot
 -> GitHub job summary
```

The raw input snapshot is deliberately ephemeral. Retained derived features and
checkpoint provenance support bounded calibration without preserving issue or PR bodies;
exact replay requires reacquiring the public snapshot or a separately governed evidence contract.

---

## 11. Safety and epistemic invariants

1. A high Pareto rank is not correctness evidence.
2. A high UCB value is not approval authority.
3. Strategy attention weights are not causal policy rewards.
4. Generic issue references do not become dependency edges.
5. Missing labels/metadata do not justify invented semantics.
6. No issue, PR, label, assignee, branch, review, or merge is mutated.
7. Trusted persistent state comes only from successful allowlisted-event workflow artifacts with exact run-bound names, verified manifests, and valid semantic state.
8. Branch protection and independent verification remain external hard governance gates.
9. Every proxy coefficient is versioned and reviewable.
10. Calibration against delayed real outcomes is preferable to adding more unmeasured heuristics.

---

## 12. Calibration path

This layer intentionally creates the data required for a stronger next generation.

Each retained artifact contains:

```text
exact policy
+ Bayesian health checkpoint reference
+ checkpoint provenance and SHA-256 integrity manifest
+ candidate feature vectors
+ Pareto fronts
+ dependency edges
+ attention mixture
+ UCB focus
```

It intentionally excludes the raw repository snapshot and its issue/PR bodies,
as specified by `EVOLUTION_ARTIFACT_MINIMIZATION.md`.

Future delayed outcomes can then be joined to these historical states, including:

- issue closure/re-open time;
- PR merge/revert/regression outcomes;
- verifier disagreement;
- review latency and burden;
- contributor retention;
- benchmark movement;
- security findings;
- verified useful work delivered.

That permits empirical calibration of the proxy model rather than endlessly hand-tuning formulas.
