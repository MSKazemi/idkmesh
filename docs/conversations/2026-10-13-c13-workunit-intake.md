# GitHub issue WorkUnit intake: implementation record (2026-10-13)

**Request:** "Work on an issues and update the docs." Target: [#608](https://github.com/MSKazemi/idkmesh/issues/608), C13-C/D, after inspecting current `main`, issue inventory, PRs and repository instructions.

**Implementation:** strict normalizer of existing GitHub WorkUnit Issue Form headings into the versioned untrusted intake contract; preview combines *only restrictive* scope, risk, classification and external-processing hints with trusted `GitHubIssueWorkPolicy`. Generic issues retain existing preview; malformed form-like input fails closed.

**Docs:** new no-JSON intake walkthrough, contract status, module inventory, executable capability inventory, beginner navigation. **Non-goals:** dispatch, automatic approvals, GitHub Projects synchronization, live agent execution, or schema changes.

**Verification:** `python -m py_compile` on new source/tests and isolated parser/projection smoke passed. Full repo pytest and CI were not runnable in the container because outbound DNS could not access github.com; the GitHub PR checks are authoritative. No human or independent reviewer validation is claimed.

**Community impact:** makes the WorkUnit form accessible to non-JSON users, while explicitly retaining human/independent decision boundaries and reporting malformed requests without leaking issue body content.
