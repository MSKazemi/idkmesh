# ADR-0011 — Discovery Surface Completion Without a Pinning Gate

**Status:** Accepted

**Date:** 2026-08-29

## Context

Issue #173 established a P0 discovery-surface checklist for IDKMesh. Repository description, focused topics, GitHub Discussions, the public Pages front door/homepage, and a stable research-preview release are now active and have durable repository evidence.

One acceptance item remained: independently verify that welcome discussion #302 is pinned. The available repository API does not expose a reliable pin mutation/verification surface, so keeping that presentation detail as the sole blocker would leave an otherwise completed discovery activation permanently open unless a separate UI witness is supplied.

The project must not fabricate that witness. At the same time, a pin is not an authority, correctness, security, reproducibility, or external-participation control. It is a presentation affordance.

## Decision

Supersede the **pinned welcome discussion** requirement as a P0 completion gate for issue #173.

Discussion #302 may still be pinned through the GitHub UI as an optional presentation improvement, but the absence of independently observable pin evidence does not block completion of the discovery-surface activation.

This decision does **not** supersede any gate that carries real authority or evidence requirements. In particular it does not substitute for:

- independent review;
- protected integration;
- security controls;
- verified external community participation;
- ACE lineage/descendant evidence.

External first-contact and contributor-conversion evidence remains tracked by #9, #10, #23, and #109 and must remain zero until real external evidence exists.

## Rationale

The distinction is material:

```text
presentation affordance != authority/evidence gate
```

Keeping a non-observable presentation detail as a hard P0 blocker would create stale tracker debt without increasing safety or scientific validity. Conversely, silently marking the pin complete would violate the External Action Handoff principle in ADR-0010.

The professional resolution is therefore to change the requirement explicitly, record why, and leave the optional UI improvement visible without pretending it occurred.

## Consequences

### Positive

- #173 can close on the evidence it was intended to establish: public discovery surfaces are live and reproducibly documented;
- the repository does not fabricate a GitHub UI witness;
- external-participation metrics remain uncompromised;
- optional presentation polish is separated from safety/evidence gates.

### Costs / risks

- discussion #302 may remain unpinned;
- a pinned welcome discussion could still improve first-contact usability and may be performed later;
- the project must continue checking that discovery links stay current.

## Revisit conditions

Revisit if evidence shows that pinning materially affects newcomer conversion, or if GitHub exposes a reliable repository API for pin state and the project chooses to make it an observable operational invariant.

## Implementation references

- `docs/PAGES_SETUP.md`

## References

- issue #173 — discovery-surface activation
- discussion #302 — welcome announcement
- `docs/PAGES_SETUP.md`
- `docs/decisions/ADR-0010-external-action-handoff.md`
- issues #9, #10, #23, #109 — community-growth evidence
