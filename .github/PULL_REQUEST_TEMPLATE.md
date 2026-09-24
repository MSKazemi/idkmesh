<!--
SMALL CHANGE? A typo, a wording fix, a translation, a broken link, a one-line
correction: fill in Summary and the Checklist, then delete the sections you do
not need. They will not be held against you.

The longer sections below exist for changes that carry a claim -- new code, an
experiment, a contract change, anything a reviewer has to take on trust. They
are not a toll on a first contribution.
-->

## Summary

What does this change do?

## Problem / motivation

What problem, question, or hypothesis does it address?

## Evidence and verification

How did you check the change? Include tests, reproduction steps, references, experiment results, or reasoning appropriate to the contribution.

## Related work / ACE lineage (optional)

Link the issue(s) this work addresses. If this pull request is a candidate response to an ACE Growth Seed, include a line such as `ACE-Seed: #24` so the public cohort observer can associate the candidate with its seed.

Put issue numbers on `Refs:` by default. Leave `Closes:` blank unless merging
this pull request should actually close the issue — and when it should, write
nothing on that line but the reference itself, in the form `Closes: #<issue>`
(separate several with commas). GitHub only recognizes a closing keyword when it
sits immediately next to the issue number: extra words in between (including a
parenthetical disclaimer such as "does not close", or instructional text left
over from this template) silently prevent the auto-close. Evidence PRs that
must leave a review gate open belong on `Refs:` instead, with `Closes:` left
blank. `tools/closing_keyword_guard.py` exempts this line only while it carries
nothing but references, so prose written after the colon is still reported.

- Refs:
- Closes:
- ACE-Seed:

## API contract change (if applicable)

For API changes, identify the owning API issue and complete the applicable checks.

- API issue / domain owner:
- Method/path or public object:
- Request/response schema updated:
- OpenAPI updated:
- Compatibility class: additive / clarification / deprecation / breaking
- Authority ceiling unchanged or explicitly reviewed:
- Authentication/authorization impact:
- Idempotency/concurrency semantics (mutations):
- Limits/rate/timeout impact:
- New stable error codes:
- Runtime response validated against advertised schema:
- Backwards-compatibility check:

## Community Impact

For non-trivial changes, describe the effect on newcomers, contributors, reviewers, maintainers, documentation, accessibility, governance, or participation prerequisites.

- Easier/harder to understand:
- Easier/harder to contribute:
- New maintenance/review burden:
- Documentation/onboarding updated:

## AI/tool provenance

If AI tools materially generated code, tests, research, or documentation, note the tool/model if known and what was independently verified by the contributor.

## Risks / limitations

What is intentionally not solved? What could fail?

## Checklist

- [ ] The change is focused enough to review.
- [ ] I have not included secrets or sensitive personal information.
- [ ] Relevant tests/evidence/documentation are included.
- [ ] I have stated uncertainty and known limitations.
- [ ] I considered Community Impact for a non-trivial change.
- [ ] Security implications have been considered where relevant.
