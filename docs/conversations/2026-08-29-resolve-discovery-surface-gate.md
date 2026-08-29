# Resolve one open issue professionally and integrate it

**Date:** 2026-08-29

## Project owner request

The project owner asked ChatGPT to inspect an IDKMesh issue, solve it in a proper and professional way, and merge the resulting change to `main` if repository policy permits.

## Repository inspection

Open issues were reviewed with attention to whether their remaining gates were actually satisfiable by the available authority. Issues requiring a genuinely independent human reviewer (#138, #151, #167) were deliberately not self-certified. Issue #173 was selected because its remaining acceptance rule explicitly allowed either independent observation that discussion #302 is pinned **or** superseding that pin requirement by a documented decision.

Repository evidence already recorded for #173 showed that the substantive discovery surfaces are live: description, focused topics, Discussions, welcome discussion, Pages/homepage, HTTPS, and the first research-preview release. The remaining pin state was not observable/mutable through the available repository API.

A second concrete defect was found in `docs/PAGES_SETUP.md`: it still described Pages as only prepared/pending even though the repository had already activated and verified it.

## Resolution

The change:

1. updates `docs/PAGES_SETUP.md` to reflect the live verified state while retaining a recovery/reverification runbook;
2. adds ADR-0011, which explicitly supersedes discussion pinning as a **P0 completion gate** while retaining it as optional presentation polish;
3. preserves external-participation and independent-review gates unchanged rather than using the decision to weaken evidence requirements.

The key distinction is:

```text
presentation affordance != authority/evidence gate
```

This follows ADR-0010: do not fabricate an external witness. Instead, change a requirement explicitly when the requirement is determined not to carry the authority/evidence property the tracker originally assigned to it.

## Community impact

The update reduces stale tracker/runbook state and makes the public discovery status easier for contributors to interpret. It does not claim an external contributor exists, does not create Cohort 2, and does not replace any independent review, security, protected-integration, or verified-descendant gate.

## Integration discipline

The work is being performed on a branch and through a pull request against protected `main`. Required branch checks must pass before merge. Issue #173 should be closed only after the decision is integrated into `main`.
