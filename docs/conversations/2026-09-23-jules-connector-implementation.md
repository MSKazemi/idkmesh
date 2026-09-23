# 2026-09-23 — Jules connector implementation continuation

## Owner request

The project owner asked to move from planning into implementation of the
agent/model connector architecture.

## Repository state inspected

The existing C1 connector kernel had already been decomposed into stacked PRs
under issue 574. Rather than duplicate those branches, implementation continued
with independent/shared primitives and the Jules connector micro-slices under
issue 575.

## Implementation produced in this turn

- PR 696 — shared stdlib-only connector error vocabulary, JSON envelope, retry
  defaults, and recursive credential/header redaction.
- PR 698 — C2-A Jules HTTP shell using the current v1alpha base URL,
  X-Goog-Api-Key runtime authentication, injected transport, strict JSON,
  bounded responses, timeout handling, and normalized connector errors.
- PR 699 — C2-B exact Jules Source lookup plus GitHub owner/repository and
  starting-branch validation.
- PR 700 — C2-C guarded Session creation with explicit plan approval.
- PR 702 — C2-D Session/Activity observation with provider completion mapped
  only to candidate readiness.
- PR 703 — C2-E explicit operator authorization for plan approval and
  send-message actions.
- C2-F candidate discovery was implemented on
  `connector/c2f-jules-candidate-discovery-20260923`: Jules pull-request output
  is treated only as a candidate locator and still requires SCM head-SHA
  resolution.

## Important provider limitation discovered

Current Jules v1alpha documentation exposes
`sourceContext.githubRepoContext.startingBranch` for Session creation but does
not document a commit-SHA field.

IDKMesh therefore must not claim that Jules natively binds a Session to an exact
Git revision. The implemented C2-C contract requires trusted SCM evidence that
an IDKMesh-controlled starting branch is pinned to the requested revision, then
records the binding method as `scm_pinned_branch`.

This preserves the IDKMesh exact-source invariant without inventing a provider
capability.

## Authority decisions preserved

- connector/provider completion is not verification;
- Jules `COMPLETED` maps only to `candidate_ready`;
- plan approval and messaging require explicit upper-layer authorization;
- Jules Source metadata cannot choose another repository or branch;
- a Jules-created PR URL is not head-SHA evidence;
- GitHub/SCM must resolve and bind the exact PR head before canonical candidate
  normalization;
- no worker/provider path gains merge authority.

## Verification findings

The first PR Gate failures on PRs 696 and 698 came from the repository's
closing-keyword guard interpreting phrases such as "does not close #575" in PR
descriptions. The metadata was corrected and a fresh reopened event was used
because GitHub reruns retain the original event payload.

After that correction, PR 696 passed the required PR Gate. A real C2-A test
failure was then found: URL/query validation `ValueError` exceptions were
inside a transport error catch and were mislabeled as response normalization
failures. The fix moved URL construction outside the transport try boundary and
was propagated through the stacked C2 branches.

Local clone-based pytest could not be used because the execution environment
could not resolve github.com, so exact-head GitHub Actions are the executable
test evidence source.

## Remaining C2 work

C2-G is the only deliberately live/credentialed step:

1. supply Jules API credentials through the secret-resolution boundary;
2. use an already connected Jules GitHub Source;
3. create an SCM-pinned low-risk branch for one bounded WorkUnit;
4. create a Jules Session with plan approval required;
5. observe activities;
6. explicitly approve the plan if appropriate;
7. discover the candidate PR;
8. resolve its exact GitHub head SHA;
9. normalize/verify it through IDKMesh;
10. retain the result without automatic merge.

No live smoke should bypass C1 secret, persistence, routing, or human authority
gates.
