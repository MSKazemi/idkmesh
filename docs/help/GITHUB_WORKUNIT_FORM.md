# GitHub WorkUnit Issue Form: no-JSON path

**Issue:** [#608](https://github.com/MSKazemi/idkmesh/issues/608) — C13-C/D
**Status:** experimental pure Python API; not a CLI command or an automatic dispatch workflow.

## For a newcomer

1. Open [New GitHub issue](https://github.com/MSKazemi/idkmesh/issues/new/choose) and select **IDKMesh WorkUnit request**.
2. Describe one task under **Objective**. Choose a task class, list expected outputs, provide requested repository-relative paths, and list checks that would prove completion.
3. Choose honest risk, sensitivity, external-processing and human-review hints. Never paste secrets. These are requester hints, not GitHub or IDKMesh permissions.
4. Submit the issue; it is still a **proposal**, not an approved task. A maintainer/operator must supply trusted repository policy and a precise Git source revision for a preview.

For example, request a documentation fix, list `docs/BEGINNER_GUIDE.md` as the requested allowed path, `.github/**` as forbidden, and “links pass the repository checker” under acceptance checks. If trusted policy grants only `tests/**`, the preview **rejects** the incompatible path; submitting this form never enlarges policy.

## For Python integrations (experimental, no live provider calls)

```python
from idkmesh.github_issue_preview import GitHubIssueWorkPolicy
from idkmesh.github_issue_source import GitHubRestIssueSource
from idkmesh.github_workunit_intake import preview_github_workunit_form

snapshot = GitHubRestIssueSource().get_issue_snapshot(
    repository="MSKazemi/idkmesh", issue_number=123,
)
policy = GitHubIssueWorkPolicy(
    repository="MSKazemi/idkmesh",
    allowed_paths=("docs/**", "tests/**"),
    forbidden_paths=(".github/**",),
)
preview = preview_github_workunit_form(
    snapshot, source_revision="0123456789abcdef0123456789abcdef01234567",
    policy=policy,
)
print(preview.to_dict())
```

The exact revision in the example is a placeholder: supply an actual trusted 40- or 64-character Git commit SHA. The issue fetch is read-only. A normal non-form issue produces the existing generic preview; a malformed recognized WorkUnit form raises `ConnectorError(code="policy_denied")` with a bounded reason code, not the raw issue text.

## Trust and implementation limits

* Only the fixed GitHub Issue Form heading order, dropdown vocabulary and acknowledgement are accepted. Optional blank fields use GitHub's `_No response_` marker.
* Paths must be repository-relative. Requested allowed scopes must be provable subsets of trusted policy: exact matches, literal descendants or `subdir/**` under a trusted `dir/**`. Complex unprovable glob intersections are rejected rather than guessed.
* The parser only proposes a WorkUnit; it cannot grant dispatch, secrets, new validators, connector choice, external processing, merge rights, or human approval. Risk/classification hints may raise floors; forbidden paths and external-processing restrictions can only tighten policy.
* Expected outputs, acceptance checks, dependencies, and preferred connector remain untrusted data in the namespaced WorkUnit extension, not runnable commands or resolved dependencies.
* Denying network within this preview is not a replacement for enforcement by a real sandbox/egress policy. Never give the returned preview to an untrusted executor without downstream hard admission.
* GitHub Projects state sync (C13-E/G), end-to-end automation, and project-admin operations are **not implemented** by this slice. Form normalization is not wired into the general dispatcher yet.
* Test the parser using `python -m pytest -q tests/test_github_workunit_intake.py`.

See [intake contract](../specifications/GITHUB_WORKUNIT_INTAKE_V0_1.md), [WorkUnit schema](../../schemas/work-unit-v0.2.schema.json), and [beginner guide](../BEGINNER_GUIDE.md).
