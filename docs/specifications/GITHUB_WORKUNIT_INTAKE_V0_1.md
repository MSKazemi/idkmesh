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
