# README live-front-door refresh — 2026-08-28

## Context

The repository-side GitHub Pages front door was merged in PR #194, but GitHub Pages, repository description, topics, Discussions, and homepage configuration still require owner/admin settings through issue #173.

That makes `README.md` the public front door that is already live for every visitor today.

## Finding

A live audit found that the README's bounded-task section had become stale:

- it advertised issue #27 as an open coding/modeling starter even though #27 is completed;
- it sent expert reviewers to historical PR #91 even though the current canonical-node review gate is issue #138 against PR #159;
- only issues #24 and #167 currently carry both `good first issue` and remain open.

This is a discoverability defect: the repository explicitly says the front door should show open work rather than historical work, but its highest-visibility file violated that rule.

## Correction

The README now advertises only verified-live contribution surfaces:

1. #24 — 15-minute newcomer-path audit;
2. #167 — independent IDKGraph orphan-cohort review, including real reviewer-minute evidence;
3. #138 — expert independent review of PR #159 canonical-node runtime evidence.

Issue #27 was moved into the completed Bootstrap Cohort provenance list rather than deleted from history.

## Guardrail

No replacement coding seed was invented merely to preserve category symmetry. The current ACE evidence still shows no external bootstrap descendant, so the project should prefer a small truthful starter inventory over generating more issues for appearance or activity metrics.

## Community impact

This change reduces the probability that a newcomer follows a closed task or an obsolete review target. The next useful growth signal remains an external human reaching one of the bounded live surfaces and leaving an inspectable claim, question, review, or contribution.

Related: #10, #24, #109, #138, #167, #173, PR #194.
