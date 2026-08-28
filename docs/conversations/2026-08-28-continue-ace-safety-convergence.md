# Project Conversation — Continue ACE Safety Convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Context

After the real-worker lane was reduced to controlled Docker acceptance #37, the continuation rechecked the independent P0 protection lane rather than stopping at the external runtime blocker.

Public GitHub branch metadata still reported:

```text
main = fb2fafdc1d5e27fea6d213e6ecad27b152ecdd03
protected: false
protection.enabled: false
required_status_checks.enforcement_level: off
```

The repository now contains more executable orchestration, verifier, evaluator, node, and self-evolution surfaces, so the absence of a GitHub-enforced integration boundary is increasingly important.

## 1. Initial review target and convergence correction

PR #51 initially appeared to be the active consolidated ACE safety PR, with a green `ACE safety contract` and mergeable state.

An independent source review of its privileged `pull_request_target` workflow found three security gaps that were not covered by the existing regression test:

1. `branch.protected == true` alone was being treated as sufficient authorization for ACE reproductive actuation;
2. legacy ledger migration could promote a convincing title/body look-alike without requiring a trusted repository-associated author or unique candidate;
3. `ACE_STATE` accepted any JSON object that parsed, with default merging/coercion rather than validating controller semantics.

The first fix attempt was made on PR #51's branch. Before reopening/using that PR, the public #35 discussion was checked and revealed an explicit convergence decision:

> PR #51 was closed unmerged because its protection guard and PR #62's ACE metadata threat-model hardening were superseded by fresh convergence PR #98.

PR #51 was therefore **not reopened**. The follow-up security changes were ported atomically onto PR #98, preserving the project's convergence-over-duplication rule.

## 2. Why `protected: true` is not sufficient authorization

GitHub's coarse branch `protected` boolean can become true when some ruleset/protection applies. It does not by itself prove that the intended IDKMesh integration contract exists:

- pull-request-based integration;
- stable required checks;
- force-push/deletion restrictions;
- independent review appropriate to risk;
- narrow/auditable bypass policy.

Automatically enabling ACE reproduction on any transition to `protected: true` could therefore convert a partial/weak configuration into stronger autonomy by accident.

### Hardened rule

PR #98 now requires two gates:

```text
actuationAllowed =
  mainProtected
  AND
  explicitActuationOptIn
```

where:

```text
explicitActuationOptIn =
  ACE_AUTONOMOUS_ACTUATION_ENABLED == "true"
```

The repository variable is an explicit **post-verification opt-in**. It must remain disabled while protection is absent, incomplete, untested, or under repair.

Either failed gate forces ACE into fail-closed `CONSOLIDATE` behavior and disables the automatic Growth Seed reproductive actuator while preserving the evidence ledger.

## 3. Canonical ledger identity now fails closed on ambiguity

The ACE ledger is controller memory, not ordinary free-form documentation.

PR #98 now requires:

- at most one open `ace:ledger`-labelled issue;
- multiple labelled ledgers => hard failure for human repair;
- legacy migration only when no labelled ledger exists;
- a legacy candidate must have the canonical title, an `ACE_STATE` block, and trusted `author_association` (`OWNER`, `MEMBER`, or `COLLABORATOR`);
- multiple trusted legacy candidates => hard failure instead of arbitrarily selecting the oldest.

This prevents an external issue author from pre-creating a convincing ledger-shaped issue and having it silently promoted to controller state.

## 4. ACE controller state now receives semantic validation

JSON parsing is not sufficient for control state.

`ACE_STATE` now fails closed unless it has:

- supported `version == 1`;
- canonical ISO `updated_at` timestamp;
- no implausibly future timestamp;
- finite non-negative `credit`;
- finite non-negative `review_load`;
- non-negative safe-integer `total_events`;
- plain-object `counts`;
- bounded count-key syntax;
- non-negative safe-integer count values.

The workflow no longer performs:

```text
{ ...defaultState, ...JSON.parse(state) }
```

for retained controller memory.

Missing or semantically invalid state stops the privileged workflow and preserves the public evidence for explicit repair rather than silently resetting/coercing it.

## 5. Regression contract strengthened

The canonical PR #98 test file now asserts, among other existing invariants:

- privileged workflow has no checkout and no shell `run:` path;
- action dependency is immutable-pinned;
- no `contents: write` permission;
- marker text requires trusted author association;
- canonical ledger identity is unique;
- legacy adoption requires trusted authors and is unambiguous;
- semantic state validation contains finite/safe-integer/canonical-time checks;
- malformed state is not silently merged into defaults;
- scans are paginated;
- dedupe markers require real Growth Seed provenance;
- untrusted PR titles are not copied into generated control text;
- real `main` protection is queried;
- explicit actuation opt-in exists;
- `actuationAllowed = mainProtected && explicitActuationOptIn`.

## 6. Admin runbook and threat model updated

`docs/admin/MAIN_PROTECTION.md` now requires an administrator to:

1. configure real `main` protection;
2. behaviorally test force-push/deletion/direct-integration/check/review behavior;
3. confirm public branch metadata reports protected;
4. only then set `ACE_AUTONOMOUS_ACTUATION_ENABLED=true` if bounded ACE reproduction is intentionally authorized;
5. verify removing either gate returns ACE to fail-closed operation.

The canonical ACE threat model now explicitly includes:

- coarse-protection-signal -> autonomy escalation as a threat;
- ambiguous ledger identity/migration;
- syntactically valid but semantically poisoned controller state;
- protection weakening while an opt-in remains configured.

It continues to prohibit PR-head execution, autonomous merge, secrets, governance mutation, financial/compute authority, and broad recursive generation.

## 7. Changes were ported to the actual convergence PR #98

The follow-up fixes were first constructed on the superseded #51 branch, but after discovering the explicit #98 convergence decision, the relevant blobs were ported in one commit to:

**PR #98:** `Converge ACE workflow security and protected-integration guards`

Commit:

`603a927d16fc5bfc43203131cddad8640fc6157e`

Affected canonical files:

- `.github/workflows/ace-community-growth.yml`;
- `tests/test_ace_workflow_hardening.py`;
- `docs/admin/MAIN_PROTECTION.md`;
- `docs/security/ACE_THREAT_MODEL.md`.

Closed PRs #51 and #62 remain superseded; no competing safety PR was reopened/created.

## 8. Verification evidence

Exact PR #98 head:

`603a927d16fc5bfc43203131cddad8640fc6157e`

Checks:

- **ACE Workflow Hardening Check** — run `33184736597` — success;
- **randomness-lab** — run `33184736786` — success.

PR #98 remains open/mergeable for independent integration. It was not self-merged.

## 9. Issue #35 corrected to the canonical safety path

Issue #35 now references PR #98—not closed #51—as the active repository-side safety surface.

Its remaining acceptance work is explicitly external/admin-owned:

```text
independent review/integrate PR #98
 -> configure GitHub main ruleset/protection
 -> test actual enforcement behavior
 -> verify branch metadata reports protected
 -> optionally enable ACE_AUTONOMOUS_ACTUATION_ENABLED=true
 -> verify both positive and fail-closed gate behavior
```

At the end of this turn, `main` still reported unprotected, so stronger ACE autonomy remains blocked regardless of the opt-in variable.

## Current critical safety state

```text
privileged ACE code-execution boundary     HARDENED in #98
marker / ledger identity boundary           HARDENED in #98
controller-state semantic validation        HARDENED in #98
coarse protection -> autonomy escalation    HARDENED by second opt-in in #98
ACE hardening regression matrix             GREEN on 603a927...
actual GitHub main protection               STILL BLOCKING (#35)
ACE autonomous reproduction                 MUST REMAIN FAIL-CLOSED
```

## Community impact

The added opt-in makes repository administration more legible: a weak/partial protection setting cannot silently switch on autonomous issue reproduction. The ledger/state changes also reduce the chance that an external participant or accidental manual edit turns public issue text into controller authority.

These changes make future ACE experimentation safer without increasing its current public-action budget or authority.
