# Visibility to contributor funnel: evidence and denominators

**Issue:** #664. **Status:** measurement contract; no user attribution deployed.

The funnel is discovery -> visit -> try -> first interaction -> first verified
contribution -> repeat contribution. Different stages are observed in different
systems; never fabricate individual-level joins across them.

## Stage contract
| Stage | Observable numerator | Limitation |
| --- | --- | --- |
| Search discovery | non-brand impressions | Search Console aggregation and coverage lag |
| Search click | non-brand clicks | cannot identify GitHub user |
| Repo interest | GitHub traffic/views | opt-in, limited retention and sampling |
| First interaction | external issue/PR authors | not necessarily a new visitor |
| Verified contribution | merged contribution with linked verification | review policy differs |
| Repeat contributor | distinct external contributor with second verified contribution | observation window censoring |

Each ratio must declare numerator, denominator, observation window, timezone,
coverage, data owner and missingness. Do not divide independent GSC search
click aggregates by GitHub user counts and call the result a causal conversion.
Use cohort-level ecological comparison explicitly labeled as such.

## Privacy and authority
Collect aggregate counts wherever possible. Do not store IPs, personal search
queries mapped to users, or hidden cross-site identity; no outreach or auto-merge
from a growth score. Stars and citations are discovery indicators, not code
correctness. Independent backlinks need attributable source URLs and observed
timestamps; never infer endorsements.

## Acceptance
Create small known-input fixtures for missing click evidence, duplicate PR
authors, bots, repeated contributors, censored windows and unverified merges.
Unknown stage must remain UNKNOWN, not zero conversions. No optimization
claim until real denominators and windows are auditable.
