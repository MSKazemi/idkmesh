# Decisions Index

This directory holds the project's Architecture Decision Records. An ADR states a
decision, the context that forced it, and the consequences accepted with it, **as
of its stated date**. Together with
[`../../PROJECT_RULES.md`](../../PROJECT_RULES.md) these are the canonical
current authority: where a finding, audit, or research note disagrees with an
ADR, the ADR wins.

[`../../DECISIONS.md`](../../DECISIONS.md) is a different artifact — a
chronological prose log of project decisions, including many too small to need an
ADR. It is not an index of this directory.

This index is exhaustive: every record below is covered by
`tests/test_documentation_directory_index.py`, so a new ADR that is never linked
here fails the suite. That guard exists because the IDKGraph observatory reports
a document only when *no* inbound link exists anywhere, so a decision linked from
some unrelated page but missing from its own index stays invisible.

## Accepted

- [ADR-0004 — Build the Verified Swarm Runner as the first reference product](ADR-0004-verified-swarm-runner-first-product.md)
  — the first reference product is a Git-native runner that executes candidate
  workers in isolated worktrees, verifies independently, and reports for human
  review. It explicitly does **not** auto-merge. *(Accepted for the next
  implementation cycle, 2026-08-28.)*
- [ADR-0006 — Zero-Project-Spend Compute](ADR-0006-zero-project-spend-compute.md)
  — a repository-level compute policy pinned at `project_spend_usd_max = 0`.
  *(2026-08-28.)*
- [ADR-0007 — Independent verification and verification debt as control-plane primitives](ADR-0007-verification-debt-backpressure.md)
  — an independent `VerificationResult` is a separate protocol object, and
  unverified work applies backpressure rather than accumulating silently.
  *(Accepted for experimentation, 2026-08-28.)*
- [ADR-0008 — Verification Uses Independent Evidence, Not Raw Vote Count](ADR-0008-independent-evidence-verification.md)
  — verification treats *estimated independent information* as the relevant
  quantity rather than reviewer, model, or account count, and aggregation must
  never erase the underlying raw evidence. *(2026-08-28. See the numbering note
  below.)*
- [ADR-0008 — Evaluator Sovereignty](ADR-0008-evaluator-sovereignty.md)
  — adopts Evaluator Sovereignty as an invariant: the evaluator's control data is
  a verifier-owned `EvaluatorPlan`, cryptographically bound to the WorkUnit digest
  and kept outside the candidate workspace. *(2026-08-28. See the numbering note
  below.)*
- [ADR-0009 — Evaluator Sovereignty](ADR-0009-evaluator-sovereignty.md)
  — adopts the same invariant with an expanded set of binding requirements, added
  after PR #72 established the first executable local verifier. This is the
  version cited by [`../../DECISIONS.md`](../../DECISIONS.md). *(2026-08-28.)*
- [ADR-0011 — Discovery Surface Completion Without a Pinning Gate](ADR-0011-discovery-surface-completion.md)
  — supersedes the pinned-welcome-discussion requirement as a P0 completion gate
  for issue #173, without weakening any gate that carries real authority or
  evidence requirements. *(2026-08-29.)*

## Proposed and experimental

These record a default hypothesis the project builds on, not a settled contract.

- [ADR-0002 — Fractal Autonomous Cells for Scalability](ADR-0002-fractal-autonomous-cells.md)
  — adopts `node -> cell -> fabric/region -> global federation` as the default
  scaling topology hypothesis. *(Proposed / default hypothesis, 2026-08-28.)*
- [ADR-0003 — Community-first development](ADR-0003-community-first.md)
  — makes the effect on people's ability to discover, understand, and join the
  project a standing consideration for substantial changes. *(Proposed for
  adoption, 2026-08-28.)*
- [ADR-0005 — IDKGraph and Guarded Self-Evolution](ADR-0005-idkgraph-and-guarded-self-evolution.md)
  — proposes a typed temporal directed hypergraph as the canonical semantic
  project model, with specialized formal projections derived from it.
  *(Proposed / experimental, 2026-08-28.)*
- [ADR-0010 — External Action Handoff and Witness Boundary](ADR-0010-external-action-handoff.md)
  — when an action lies outside the current actor's authority, the system must
  fail open in communication but fail closed in authority, rather than treating a
  recommendation as if the external control existed. *(Proposed, 2026-08-28.)*

## Numbering integrity

Two observations that a reader of this directory should not have to discover by
listing it. Both are recorded here rather than resolved, because renumbering or
re-statusing an accepted decision changes the project's own record and is the
owner's call.

1. **The number 0008 is used twice**, by two unrelated decisions —
   `ADR-0008-independent-evidence-verification.md` and
   `ADR-0008-evaluator-sovereignty.md`, both linked above. An ADR number is meant
   to be a stable identifier, so "ADR-0008" is currently ambiguous in any citation
   that does not also give the title.
2. **Evaluator Sovereignty exists twice**, as `ADR-0008-evaluator-sovereignty.md`
   and `ADR-0009-evaluator-sovereignty.md`. Both are marked Accepted, both
   are dated 2026-08-28, and both open with the same sentence — "Adopt
   **Evaluator Sovereignty** as an IDKMesh invariant" — but they state different
   requirement lists, ADR-0009's being the longer. Neither record says it
   supersedes the other. `DECISIONS.md` cites only ADR-0009.

There is also no ADR-0001; the sequence begins at 0002.
