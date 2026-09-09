# Do the gates check what they claim? — 2026-09-02

**Baseline revision:** `31b8f18`.

Read this as a snapshot. Each result below was produced by breaking something on
purpose and observing whether the gate noticed; re-run the mutations to re-derive
them.

## What was inspected, and why

A gate that passes tells you nothing unless it can fail. A green check is
evidence only to the extent the check would have gone red had the property it
names been violated — and a gate whose message overstates what it verified is
worse than no gate, because it converts an unchecked property into a printed
assurance.

Each Phase 0 gate was therefore mutation-tested: introduce the exact defect the
gate claims to catch, and record whether it caught it.

## Result

| Gate | Mutation introduced | Outcome |
|---|---|---|
| `scripts/check_links.py` | a Markdown link to a non-existent file | **caught**, exit 1 |
| `experiments/harness.py validate` | a valid work unit passed where an invalid one is expected | **caught**, exit 2 |
| `experiments/harness.py validate` | an invalid result manifest passed where a valid one is expected | **caught**, exit 2 |
| `experiments/provenance_integrity.py --self-test` | a valid verification result used as the negative fixture | **caught**, exit 2 |
| `experiments/local_verifier.py self-test` | the good candidate root passed as the bad one | **caught**, exit 2 |
| `experiments/harness.py validate` | `schemas/goal-graph.schema.json` made an invalid JSON Schema | **missed** — printed `OK: schemas valid`, exit 0 |

Five of six behaved as advertised. The negative fixtures are real negatives, and
the self-tests genuinely fail when their negative case stops being negative.

## The gap

`OK: schemas valid` covered five schemas, not thirty-two.
`experiments/harness.py` names work-unit-v0.2, experiment-manifest-v0.1,
experiment-result-v0.1, result-manifest-v0.1 and verification-result-v0.1, and
`Draft202012Validator.check_schema` runs on those alone. Setting

```json
"type": "not-a-valid-type",
"properties": "should-be-an-object"
```

in `schemas/goal-graph.schema.json` left the gate reporting success.

A JSON-syntax check does not close this: a structurally invalid schema is
normally still valid JSON, so `python -m json.tool` accepts it too.

The consequence is quiet rather than loud. `jsonschema` may accept an unknown
keyword and silently constrain nothing, so the first symptom is an instance
passing a check that stopped checking — which matters here because
[`../../schemas/`](../../schemas/) is the machine-readable protocol truth the
verification claims rest on.

**All 32 schemas were valid at this revision.** The finding is missing coverage,
not a broken contract.

## What changed

`tests/test_schema_validity.py` meta-validates every schema in
[`../../schemas/`](../../schemas/), judging each by the dialect its own `$schema`
declares. It is itself mutation-tested against an invalid schema and invalid
JSON.

## Two negative results worth recording

Neither produced a change; both are recorded because "we looked and found
nothing" is only useful if someone can see what was looked at.

**No workflow step masks its own failure.** Across all 49 workflows there is no
`continue-on-error`, and no `|| true`. The two `set +e` uses
(`branch-convergence-audit.yml`, `evolution-loop.yml`) both capture `$STATUS`
immediately, restore `set -e`, and exit non-zero except on an explicitly
special-cased API rate limit.

**No test passes without asserting anything.** An AST sweep over all 1548 test
functions found 12 with no `assert` statement, no `assertX(...)` call and no
`with` block. All 12 were read: each asserts by raising — `run_acceptance_checks()`,
`self_test()`, `Draft202012Validator(...).validate(...)`, `json.dumps(...)` — so
the test fails if the call raises.

The sweep itself needed two corrections before it was trustworthy, which is the
same lesson this audit is about: the first version did not count
`raise AssertionError(...)` as an assertion and reported 14, two of which
(`test_blind_spot_may_not_exceed_the_marginal_error_rate`,
`test_invalid_budget_shape_fails_closed`) were using exactly that form. A
detector that overstates is as misleading as a gate that understates.

## Limits of this audit

Only the Phase 0 gates listed above were mutation-tested. Whether each gate
checks the property it *should* check, as opposed to the property it *claims* to
check, is a separate question this audit does not answer.
