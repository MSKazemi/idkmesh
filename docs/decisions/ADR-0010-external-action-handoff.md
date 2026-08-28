# ADR-0010 — External Action Handoff and Witness Boundary

**Status:** Proposed

**Date:** 2026-08-28

## Context

IDKMesh increasingly combines repository automation, AI-assisted development, verification workflows, community-evolution experiments, and external platform controls.

Some necessary actions cannot be performed by the current agent/tool surface. Examples include repository-admin settings such as GitHub branch protection or rulesets, actions requiring a genuinely independent reviewer, and actions requiring evidence from an external contributor or environment.

The dangerous failure mode is **false completion**: an internal system documents or recommends an external control and then treats the recommendation as if the external control exists.

That would violate the project's verification discipline and the External Witness Gate proposed in the whole-system audit.

## Decision

When a necessary action lies outside the authority or capability of the current actor/tool surface, IDKMesh must **fail open in communication but fail closed in authority**:

```text
required action
    |
    +-- actor can perform it safely and is authorized
    |       -> perform it
    |       -> verify observable result
    |       -> record evidence
    |
    +-- actor cannot perform it / lacks authority / independence
            -> do not claim completion
            -> find an existing canonical tracker
            -> otherwise create one bounded public task
            -> assign or identify the responsible human/role when known
            -> state exact action required
            -> define observable acceptance evidence
            -> link dependent automation/claims to the unresolved gate
            -> keep dependent authority disabled until evidence exists
```

This is the **External Action Handoff invariant**.

## Required properties of a handoff

A handoff is complete only when the repository record contains:

1. **Blocked capability** — what cannot be performed and why.
2. **Responsible boundary** — owner/admin/reviewer/external contributor/other authority needed.
3. **Concrete action** — steps specific enough to execute without reconstructing private chat context.
4. **Acceptance evidence** — an externally observable condition that proves completion.
5. **Dependency behavior** — what remains blocked or fail-closed until completion.
6. **Canonical tracker** — one issue/task rather than duplicate parallel trackers.
7. **Reverification** — after the external action, the repository/automation should re-observe the real state before unblocking anything.

## Non-compensation rule

Internal evidence cannot substitute for an external boundary that is itself part of the claim.

A useful conceptual model is:

```text
M_effective = min(I, W, G, U)
```

where:

- `I` = internal executable evidence;
- `W` = independent witness evidence;
- `G` = externally enforced governance/security evidence;
- `U` = evidence of usefulness or operation outside the system that produced the artifact.

The formula is a research heuristic, not a production score. The architectural property is **non-compensation**: high internal confidence cannot erase a zero at a required external gate.

## Current application: GitHub `main` protection

Issue #35 is the canonical handoff for repository-admin protection of `main`.

Current observed state during this decision:

```text
main protected: false
repository rulesets: none observed
```

Repository-side workflows already fail closed when protection is absent. The remaining action belongs to GitHub repository administration.

Issue #35 therefore contains the owner-action checklist and acceptance evidence. Dependent autonomous repository-write authority remains disabled until GitHub itself reports and behaviorally demonstrates the intended protection state.

## Independent-review application

The same rule applies when a proposal requires independent review.

The proposing actor, its own automation, or another process controlled by the same authority must not manufacture the missing independence by approving its own work under another label.

The correct state is `pending independent witness`, not `verified`.

## Community application

Internal ACE activity, simulation, or capacity recovery is not a verified external community descendant. The community-evolution system must preserve zero external evidence as a legitimate measured state until an actual independent participant produces qualifying evidence.

## Consequences

### Positive

- prevents capability gaps from being hidden behind documentation;
- keeps autonomy bounded by real external controls;
- creates clear owner/admin queues rather than forgotten chat limitations;
- makes tool limitations operationally visible;
- reduces duplicate issues by requiring canonical trackers;
- improves reproducibility because completion is tied to observable evidence.

### Costs

- some work remains visibly blocked;
- humans may need to perform platform/admin/review actions;
- progress can appear slower than systems that self-certify their own gates.

These costs are intentional. Honest blocking is preferred to false completion.

## Revisit conditions

This decision may be refined if IDKMesh later gains a trusted capability that can safely perform a currently external action. Even then, the action must still obey separation-of-authority requirements; gaining API access does not automatically create independent review or independent evidence.

## References

- `PROJECT_RULES.md`
- `docs/audits/2026-08-28-whole-system-first-contact-audit.md`
- `docs/conversations/2026-08-28-propagation-and-owner-admin-action.md`
- issue #35 — protect `main`
- PR #121 — First Contact / External Witness Gate audit
