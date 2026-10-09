# GitHub WorkUnit Intake v0.1

**Status:** experimental field contract  
**Issue:** #608, C13-A  
**Schema:** `schemas/github-workunit-intake-v0.1.schema.json`  
**Authority:** untrusted planning input only

## Purpose

This contract freezes the normalized field vocabulary for a future GitHub
Issue Form that lets a newcomer request bounded work without writing raw
WorkUnit JSON.

It deliberately stops before C13-B/C13-C:

- it does **not** generate an Issue Form;
- it does **not** parse an issue body;
- it does **not** create a canonical WorkUnit;
- it does **not** route or dispatch work.

A valid intake document means only that untrusted requester input has a known
shape.

## Trust boundary

GitHub issue authors, comments, labels, Projects fields, and form values are
untrusted content. Valid structure is not authorization.

The intake object can suggest narrower or stricter behavior, but cannot grant
authority. In particular it cannot:

- introduce or resolve secret references;
- carry a raw secret as an authorization input;
- set executable commands or workflow templates;
- broaden filesystem or network permissions;
- lower computed risk;
- downgrade data classification;
- waive required review or a human decision;
- select a connector merely because one is preferred;
- authorize dispatch, verification, acceptance, merge, or integration.

A requester may still paste sensitive text into an ordinary text field. This
schema cannot make arbitrary issue text secret-safe; downstream surfaces must
continue to treat all issue text as untrusted and apply their normal
redaction/data-handling policy.

## Stable normalized fields

C13-B should use these names as the semantic field IDs of the generated form.
C13-C may normalize presentation-specific text into this object, but must not
change their meaning.

| Field | Meaning | Authority rule |
| --- | --- | --- |
| `objective` | What the requester wants accomplished. | Content only. |
| `task_class` | Work category aligned with WorkUnit v0.2 `kind`. | Does not choose a worker/model. |
| `expected_outputs` | Human-readable expected artifacts/outcomes. | Does not authorize writes. |
| `requested_allowed_paths` | Requested write-scope hints. | Trusted policy must intersect/narrow; never copy as authority. |
| `requested_forbidden_paths` | Requested exclusions. | Trusted policy may add stricter exclusions. |
| `dependencies` | References that require, block, or inform this request. | Planning graph input only. |
| `acceptance_checks` | Human-readable requested checks. | Never executable command authority. |
| `risk_hint` | Requester's risk estimate. | Policy may raise risk; hint cannot lower it. |
| `external_processing_hint` | Whether requester permits/prefers external processing. | `allowed` is not permission. |
| `data_sensitivity_hint` | Requester's data-classification estimate. | Policy may raise sensitivity; hint cannot lower it. |
| `human_review_hint` | Required/preferred/unspecified human review. | Cannot waive policy-required review. |
| `preferred_connector_hint` | Optional connector preference. | Advisory only; routing remains canonical. |
| `authority_ceiling` | Machine-readable all-false authority statement. | Every flag is fixed to `false`. |

The normalized object also carries:

- `schema_version = "0.1"`;
- `kind = "idkmesh-github-workunit-intake"`.

## Task class alignment

`task_class` intentionally uses the same vocabulary as WorkUnit v0.2
`kind`:

- `coding`;
- `testing`;
- `review`;
- `benchmarking`;
- `documentation`;
- `research`;
- `integration`;
- `governance`;
- `other`.

The contracts remain different objects. Matching vocabulary is not permission
to copy the intake object directly into a WorkUnit.

## Dependencies

A normalized dependency has:

- `reference`: an issue, WorkUnit, URL, or other human-readable reference;
- `relation`: `requires`, `blocked_by`, or `informs`.

C13-C owns any future raw textarea syntax. This contract intentionally does not
bless arbitrary issue text as a canonical dependency edge.

## Required policy composition

A future intake-to-preview implementation must apply trusted repository/project
policy after parsing. At minimum:

```text
requested allowed paths
  -> intersect with trusted project scope
  -> subtract trusted forbidden/sensitive paths

risk hint
  -> combine with trusted analysis/policy
  -> never reduce risk

data sensitivity hint
  -> combine with trusted classification
  -> never downgrade sensitivity

preferred connector hint
  -> optional routing preference input
  -> hard routing/authority gates still win
```

If the request conflicts with policy, the preview should warn or fail closed;
it must not silently broaden policy to satisfy the issue.

## Versioning

This is a v0.1 experimental contract. Once C13-B/C13-C consume it, incompatible
field or meaning changes require a new schema version rather than silently
rewriting durable issue semantics.

## Next slices

- **C13-B:** generate the GitHub Issue Form from this field contract.
- **C13-C:** parse/normalize the form into this contract and then produce a
  policy-bounded WorkUnit preview.
- **C13-D:** prove incomplete/malicious form content cannot broaden authority.

Those slices must reuse this contract rather than creating a second intake
vocabulary.

## C13-B Issue Form

### Purpose

The GitHub WorkUnit Issue Form gives humans a structured, no-JSON way to propose bounded work. It is an **intake surface**, not an authority surface and not a canonical WorkUnit by itself.

The machine-readable contract is `config/github-workunit-intake-v0.1.json`. The repository form is `.github/ISSUE_TEMPLATE/06-idkmesh-workunit.yml`. A later parser may project valid fields into a WorkUnit v0.2 preview, but only through trusted project policy.

### Security model

Every submitted field is untrusted issue content. A proposer can describe intent, constraints, and preferences, but cannot use this form to grant capabilities or bypass policy.

In particular, form content MUST NOT directly set:

- network access or a network allowlist;
- secret access;
- process-execution permission;
- project spend or paid fallback;
- executable validator commands;
- dispatch, verification, human-decision, integration, or merge authority.

The existing GitHub issue preview invariant remains authoritative: trusted `GitHubIssueWorkPolicy` controls authority-bearing WorkUnit fields.

### Field semantics

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

### Form-to-preview rules for C13-C

When the structured parser is implemented, it should follow these rules:

1. Recognize only the versioned field vocabulary in the canonical contract.
2. Treat edited, duplicated, malformed, or unknown values as untrusted input.
3. Fall back safely to the existing generic issue preview rather than guessing authority.
4. Never union requested allowed paths with project policy. The maximum safe scope is their intersection.
5. Forbidden-path hints may only narrow scope.
6. `low`, `public`, or permissive processing/review hints never downgrade stronger project policy.
7. A preferred connector is evaluated only after normal eligibility/policy checks.
8. The resulting preview remains non-dispatching and requires the same independent verification/human authority boundaries as any other WorkUnit.

### Form-to-Project rules for later C13-F/C13-G

Optional GitHub Project fields are a projection of canonical state for planning and visibility. Manual edits to Project fields must not change canonical WorkUnit, run, verification, decision, or dispatch state.

### Non-goals of v0.1

- no automatic dispatch;
- no secret selection;
- no executable command selection;
- no GitHub admin/ruleset mutation;
- no provider-specific payloads;
- no claim/release state;
- no Project synchronization;
- no replacement for WorkUnit v0.2 or the Product Spine.

### Follow-on

This contract makes C13-C (Issue Form body -> safe WorkUnit preview parser) independently implementable and testable without inventing another field vocabulary.
