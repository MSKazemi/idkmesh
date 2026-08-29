# Issue #24 newcomer-path audit

**Date:** 2026-08-29

**Scope:** audit the public 15-minute newcomer path and remove one bounded
documentation friction

## Owner request

The project owner asked for a fresh audit of issue #24 only if live GitHub state
showed it was open, unassigned, and not already claimed through comments or a
pull request. The requested work had to begin from the public README, record an
approximately timed newcomer journey, distinguish observed friction from
personal preference, and include a bounded documentation fix when warranted.
Work was required to use an isolated current-`main` worktree and stop at a
focused, non-draft pull request without merging it.

## Coordination and interpretation

Live state showed issue #24 open with no assignee, comments, or related open
pull request. A public intent comment was posted before implementation. Required
repository policies were read first, but the audited journey was then restarted
at the public README and used only public repository and issue context.

The audit treated “at most 15 minutes” as a ceiling rather than a requirement to
consume the full interval. It stopped at about 7 minutes because the contributor
had already found a realistic task and enough workflow guidance to proceed.

## Findings and change

The path surfaced issue #24 in about 2 minutes. The clearest aid was the README's
combination of reassurance that full architecture knowledge was unnecessary and
a short current-task list with a bounded issue.

The main observed hesitation came immediately after task discovery: neither the
front-door list nor the issue explicitly said how to check whether another
contributor was already working on an open, unassigned task. The README now asks
a newcomer to inspect assignees, recent comments, and linked pull requests, then
leave a short intent comment. The detailed audit is preserved in
`docs/community/onboarding-tests/2026-08-29-newcomer-path.md`.

The unfamiliar ACE mechanism was recorded as non-blocking jargon. A possible
issue-filter link for each broad community path was labeled personal preference
and was not added.

## Community impact and provenance

The one-sentence workflow clarification should reduce duplicate effort without
adding an architectural reading prerequisite. Its cost is one additional live
state check before starting work.

The audit, report, and documentation wording were materially prepared with
OpenAI Codex. Public GitHub state, repository files, link targets, the final diff,
and repository checks are the verification boundary; the report does not claim
to represent every newcomer.
