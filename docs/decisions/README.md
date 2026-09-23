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
- [ADR-0012 — Real Schema Verification Is an Optional Extra, Not a Base Dependency](ADR-0012-optional-verification-dependency.md)
  — `jsonschema` becomes a `pip install idkmesh[verify]` optional extra rather
  than a base dependency; `dependencies = []` stays unchanged, and
  `experiments/local_verifier.py` fails with an actionable message when the
  extra is missing. *(2026-09-21.)*

- [ADR-0016 — One API Architecture, Separate Authority Boundaries](ADR-0016-one-api-architecture-separate-authority.md)
  — adopts one canonical domain/application-service API architecture, `/api/v1`
  product namespace, separate local/network security profiles, and an explicit
  boundary between human decision recording and integration execution.
  *(2026-09-23.)*
- [ADR-0017 — Local Coding Agents Require an Enforced Sandbox Boundary](ADR-0017-local-agents-require-sandbox.md)
  — makes `sandbox_required=true` a runtime precondition: local coding agents
  must execute through an enforcing sandbox backend, with no raw-process
  fallback, and candidates are captured outside worker authority.
  *(2026-09-23.)*

## Proposed and experimental

- [ADR-0013 — GitHub-First, Server-Optional Deployment](ADR-0013-github-first-server-optional-deployment.md)
  — makes the target GitHub repository the default control plane for the first external-project product profile, with a durable Git-native run ledger and an evidence-gated path to an optional service only when scale/latency/tenancy requires it. *(Proposed for adoption, 2026-09-22.)*


These record a default hypothesis the project builds on, not a settled contract.

- [ADR-0014 — Enterprise Controls Are an Overlay; G0 Remains the Default](ADR-0014-enterprise-control-plane-baseline.md)
  — keeps GitHub-first G0/G1 as the normal product path while making enterprise
  tenancy, identity, audit, recovery, supply-chain, and optional G2/G3 service
  controls explicit and evidence-gated. *(Proposed for adoption, 2026-09-22.)*
- [ADR-0015 — Normalize Candidate Identity into ResultManifest Without Pretending Reference Digests Are Content Verification](ADR-0015-candidate-reference-result-manifest-normalization.md)
  — keeps ResultManifest v0.1 provider-neutral by hashing the canonical CandidateReference envelope, explicitly separating candidate identity from byte-level verification. *(Proposed / experimental, 2026-09-23.)*

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
- [ADR-0013 — Separate Provider Completion from Candidate Readiness](ADR-0013-provider-completion-candidate-readiness.md)
  — provider/worker completion is only an execution observation; `candidate_ready`
  requires a separately normalized, immutable candidate reference. *(Proposed,
  2026-09-23.)*

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
- [ADR-0013: Cross-disciplinary policies behind hard gates](ADR-0013-cross-disciplinary-policies-behind-hard-gates.md)
