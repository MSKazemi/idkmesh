# Community and ACE Index

This directory holds the community-growth strategy, its measurement models, and
the **ACE** (Autocatalytic Community Evolution) design stack, plus the bounded
evidence records produced against them.

Read the authority line first. Every ACE layer below declares itself
experimental, shadow-mode, proposed, or offline, and
the Phase-B activation gate below states **"Authority: none by
itself"** and that a controller cannot activate itself. Nothing in this directory
grants an autonomous actuator. The presence of a complete design stack is not
evidence that the stack is switched on.

The layers are separate on purpose: causal evidence, denominator inventory, and
value/cost measurement must not collapse into one object. The ordering below is
the one the documents themselves describe.

## Strategy and measurement models

- [Community Growth Strategy](COMMUNITY_GROWTH_STRATEGY.md) — why community
  growth is a parallel product/systems problem rather than a post-engineering
  marketing phase, and the contribution forms it needs.
- [Community Growth Dynamics](COMMUNITY_GROWTH_DYNAMICS.md) — research model and
  measurement specification; turns growth into a dynamical-system problem over an
  explicit community state, rather than stars or raw contributor count.
- [ACE: GitHub-Constrained Self-Improving Community](ACE_GITHUB_CONSTRAINED_EVOLUTION.md)
  — working design for the next ACE iteration under real GitHub constraints
  (issues, PRs, labels, Actions, API limits), explicitly not publicity
  automation.
- [ACE Activity Metabolism](ACE_ACTIVITY_METABOLISM.md) — the composition rule
  that turns repository activity into verified capability, knowledge, repair, or
  reproductive opportunity. Activity itself is not fitness.

## ACE evidence and control layers

Ordered from raw observation to the gate that could, in principle, leave shadow
mode. Each is narrow by design and cites the issues it was built against.

- [ACE Cohort Observer v0](ACE_COHORT_OBSERVER.md) — experimental,
  metadata-only observability. Separates activity, cohort exposure, candidate
  work, and causal evidence. Built against #40.
- [ACE Lineage Protocol v0.1](ACE_LINEAGE_PROTOCOL.md) — the smallest
  GitHub-native record for a `verified parent -> Growth Seed -> candidate
  descendant -> verification -> verified descendant` chain. Lineage evidence
  only, not a database or an actuator. Related: #10, #23, #25, #27.
- [ACE Live Carrying-Capacity Model](ACE_CAPACITY_MODEL.md) — proposed bootstrap
  model; makes the ecological capacity gate depend on **current recoverable**
  review pressure instead of a cumulative event counter.
- [ACE Generation Evidence Interface](ACE_GENERATION_EVIDENCE_INTERFACE.md) —
  Phase-A / shadow-controller interface holding parents, lineage receipts, and
  measurement as three independent layers. Related: #25, #40, #57.
- [ACE Phase-B Activation Gate](ACE_ACTIVATION_GATE.md) — experimental,
  fail-closed, offline conjunctive rule for whether the repository is allowed and
  evidenced well enough to leave shadow mode. No authority by itself.

## Bounded experiments and evidence records

Dated records measured against the designs above. Each is a snapshot at its
stated window or revision, not current status.

- [ACE Bootstrap Experiment — Cohort 1](ACE_BOOTSTRAP_EXPERIMENT.md) — active
  bootstrap experiment over the 2026-08-28 to 2026-09-27 window, five Growth
  Seeds; public state tracked in issue #23.
- [Newcomer Path Audit](onboarding-tests/2026-08-29-newcomer-path.md) —
  2026-08-29 first-contact walk from the public README at `63e4acc` to a
  realistic bounded task, with approximate navigation times.
- [Task Decomposition: IDKGraph P0 Repository Observatory](task-decompositions/idkgraph-p0-observatory.md)
  — splits research track #20 into exactly five independently claimable
  microtasks; produced for Growth Seed #28.

## Adding a document

State the document's status and authority in its own header, place evidence
records under `onboarding-tests/` or `task-decompositions/` rather than at the
directory root, and add one line to the group above that it belongs to. A new ACE
layer must say what it does **not** authorize.
