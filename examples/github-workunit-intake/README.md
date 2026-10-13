# Synthetic GitHub WorkUnit intake examples

These fixtures accompany the [no-JSON newcomer walkthrough](../../docs/help/GITHUB_WORKUNIT_FORM.md) for issue #608 (C13-H). They do not represent an observed GitHub issue or any permission to dispatch work.

- `project/.idkmesh/project.json`: trusted local project policy used by the read-only CLI
- `issue-valid.json`: structured form that narrows to one documentation file and one test
- `issue-unchecked.json`: malformed acknowledgement; parser falls back to the generic trusted policy preview
- `issue-out-of-scope.json`: valid form requesting a forbidden scope; preview refuses

Run the guided command from the repository root. The default source revision in the regression test is an **offline synthetic format-valid SHA**, not an observed Git revision; the guide instead uses `git rev-parse HEAD`. No network, token, model, or GitHub administration permissions are needed for the fixture test.
