# GitHub WorkUnit Intake v0.1

Status: proposed repository contract for issue #608 (C13-A/C13-B).

## Purpose

The GitHub WorkUnit Issue Form gives humans a structured, no-JSON way to propose bounded work. It is an **intake surface**, not an authority surface and not a canonical WorkUnit by itself.

The machine-readable contract is `config/github-workunit-intake-v0.1.json`. The repository form is `.github/ISSUE_TEMPLATE/06-idkmesh-workunit.yml`. A later parser may project valid fields into a WorkUnit v0.2 preview, but only through trusted project policy.

## Security model

Every submitted field is untrusted issue content. A proposer can describe intent, constraints, and preferences, but cannot use this form to grant capabilities or bypass policy.

In particular, form content MUST NOT directly set:

- network access or a network allowlist;
- secret access;
- process-execution permission;
- project spend or paid fallback;
- executable validator commands;
- dispatch, verification, human-decision, integration, or merge authority.

The existing GitHub issue preview invariant remains authoritative: trusted `GitHubIssueWorkPolicy` controls authority-bearing WorkUnit fields.

## Field semantics

| Field | Purpose | Safe projection rule |
| --- | --- | --- |
| Objective | bounded requested outcome | untrusted task content |
| Task class | planning/routing hint | may classify work only within project policy |
| Expected outputs | expected artifacts/results | advisory output hint |
| Requested allowed paths | desired scope | may only intersect trusted allowed paths; never broaden them |
| Forbidden or sensitive paths | extra exclusions | may only add restrictions |
| Dependencies or blockers | planning context | informational only until independently resolved |
| Acceptance checks | desired validation | verification hint; cannot replace trusted validators |
| Risk hint | proposer risk signal | may raise, never lower, trusted risk |
| Data sensitivity hint | proposer classification signal | may raise, never lower, trusted classification |
| External processing hint | locality/privacy preference | may restrict, never authorize, external processing |
| Human review or decision requirement | review floor | may require more review, never less |
| Preferred connector | operator preference | may rank only connectors already eligible under policy |
| Safety acknowledgement | user-facing boundary reminder | no authority effect |

## Form-to-preview rules for C13-C

When the structured parser is implemented, it should follow these rules:

1. Recognize only the versioned field vocabulary in the canonical contract.
2. Treat edited, duplicated, malformed, or unknown values as untrusted input.
3. Fall back safely to the existing generic issue preview rather than guessing authority.
4. Never union requested allowed paths with project policy. The maximum safe scope is their intersection.
5. Forbidden-path hints may only narrow scope.
6. `low`, `public`, or permissive processing/review hints never downgrade stronger project policy.
7. A preferred connector is evaluated only after normal eligibility/policy checks.
8. The resulting preview remains non-dispatching and requires the same independent verification/human authority boundaries as any other WorkUnit.

## Form-to-Project rules for later C13-F/C13-G

Optional GitHub Project fields are a projection of canonical state for planning and visibility. Manual edits to Project fields must not change canonical WorkUnit, run, verification, decision, or dispatch state.

## Non-goals of v0.1

- no automatic dispatch;
- no secret selection;
- no executable command selection;
- no GitHub admin/ruleset mutation;
- no provider-specific payloads;
- no claim/release state;
- no Project synchronization;
- no replacement for WorkUnit v0.2 or the Product Spine.

## Follow-on

This contract makes C13-C (Issue Form body -> safe WorkUnit preview parser) independently implementable and testable without inventing another field vocabulary.
