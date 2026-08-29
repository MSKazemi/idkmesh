# Audits Index

This directory holds bounded reviews and evidence snapshots. Each record states
what was inspected, at which revision, and what was concluded **at that moment**.

Read every record here as a snapshot, never as current status. Repository state,
open pull requests, branch protection, and issue status all move; an audit is
retained because it preserves what was inspected and why a decision changed, not
because its situational claims are still true. Current authority lives in
[`../decisions/`](../decisions/), [`../specifications/README.md`](../specifications/README.md),
[`../architecture/README.md`](../architecture/README.md), and
[`../../PROJECT_RULES.md`](../../PROJECT_RULES.md).

Each entry below carries the baseline the record itself declares. Four records
declare no explicit baseline revision; that is noted rather than invented.

## Repository-wide state audits

Whole-repository snapshots, ordered by date.

- [IDKMesh Repository Audit](2026-08-28-repository-audit.md) — 2026-08-28;
  no declared baseline revision. Coherence and contributor-readiness review at
  the transition from research/design toward an executable system.
- [Repository Check — Current State](2026-08-28-repository-check-current.md) —
  2026-08-28; `main` at `8614a669`. Executable-contract phase reached, first
  real worker runtime not yet on `main`.
- [Full Repository Convergence Audit](2026-08-28-full-repository-convergence-audit.md)
  — 2026-08-28; no declared baseline revision. Convergence state after the
  Verified Swarm Runner, ACE safety/evidence stack, and mathematical foundations
  landed, plus the recommended integration sequence.
- [Whole-System, Long-Horizon Audit](2026-08-28-whole-system-first-contact-audit.md)
  — 2026-08-28; baseline `e86fec87`. Argues the scarce resource is independent
  contact with reality. Self-declared as a proposal, not a status claim.
- [Repository-Wide Code/Documentation Correctness Audit](2026-08-29-repository-wide-code-doc-correctness-audit.md)
  — 2026-08-29; baseline `649df7b7`. Structural correctness pass across code,
  contracts, README, and navigation documentation.

## Targeted subsystem and question audits

Each answers one bounded question rather than surveying the repository.

- [Continuous Branch-Creation Audit](2026-08-29-continuous-branch-creation-audit.md)
  — 2026-08-29; no declared baseline revision. Answers whether any in-repository
  automation continuously creates branches. Negative result, with the read-only
  permissions of the nearest workflows recorded as the evidence.
- [Evolution Control-Plane Independent Audit](2026-08-29-evolution-control-plane-independent-audit.md)
  — 2026-08-29; initial pass against `origin/main` at `566bee13`. Read-only
  review for issue #151. Explicitly AI-assisted independence, not human or
  organizational independence.

## IDKGraph P1 warning-triage records

Bounded classification passes for issue #152. Each freezes a source revision,
classifies a named cohort, and reports a measured observatory delta. None treats
a lower warning count as a standalone objective. Later passes do not edit earlier
records; a superseded baseline is corrected by a new record, not in place.

- [Orphan Warning Cohort 1 Classification](2026-08-28-idkgraph-p1-orphan-cohort-1.md)
  — frozen revision `d0bafb7f`; seeded 15-document sample drawn before
  classification so the cohort cannot be cherry-picked.
- [Accepted-ADR Linkage Triage](2026-08-28-idkgraph-p1-adr-linkage-triage.md) —
  baseline PR #149; reviews all five original
  `accepted_decision_without_document_link` warnings.
- [ADR-0011 Accepted-Decision Linkage Review](2026-08-29-idkgraph-p1-adr-0011-linkage.md)
  — baseline `7f28bc3c`; continuation pass for the single warning that appeared
  after the record above, and a measurement of how far the #152 baseline had
  drifted.

## Adding an audit

State the date and the exact baseline revision in the document, give the file a
dated name, and add one line to the group above that it belongs to. Do not edit
an existing audit to reflect later repository state — write a new record that
names what changed.
