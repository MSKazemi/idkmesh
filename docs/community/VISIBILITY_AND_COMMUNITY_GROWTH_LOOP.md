# Visibility + Community Self-Growth Loop

**Status:** implementation direction with a read-only v0.1 observatory.

IDKMesh should improve itself along several independent axes. Repository correctness is
only one of them. A project can have excellent architecture and still fail if nobody
can discover it, understand it, try it, contribute to it, or become a reviewer.

The growth controller therefore needs a vector, not one score:

```text
SelfGrowth_t = [
  product_usefulness,
  verification_strength,
  engineering_velocity,
  discoverability,
  community_acquisition,
  contributor_retention,
  reviewer_and_leader_capacity,
  adoption_and_integrations
]
```

A high value on one axis must not hide a severe deficit on another.

## The external growth funnel

The public growth loop should be measured as a funnel:

```text
search / AI answer / article / referral / GitHub topic
        |
        v
discover IDKMesh
        |
        v
understand the value proposition
        |
        v
visit docs / repository
        |
        v
star / watch / fork / try the CLI
        |
        v
open question / claim starter issue / reproduce experiment
        |
        v
first verified contribution
        |
        v
second contribution
        |
        v
recurring contributor
        |
        v
reviewer / subsystem steward
        |
        v
maintainer / community multiplier
```

Stars and forks belong near the top of this funnel. They matter because they measure
interest and distribution, but they are **not** evidence of software correctness or
community health by themselves.

## Current v0.1 observable

The repository now contains:

- `scripts/visibility_observatory.py`;
- `tests/test_visibility_observatory.py`;
- `.github/workflows/visibility-observatory.yml`.

The scheduled workflow is read-only. It records:

### GitHub discovery

- stars;
- forks;
- subscribers/watchers;
- repository topics.

### Community acquisition

- external human commit contributors visible through GitHub's contributors endpoint;
- whether the bounded contributor page saturated;
- an explicit note that commit attribution misses reviewers, researchers, issue
  participants, documenters, and other contribution forms.

### Technical SEO / AEO

Every hand-authored HTML page is checked for:

- title;
- meta description;
- canonical URL;
- Open Graph title;
- Open Graph description;
- Open Graph image;
- JSON-LD;
- exactly one H1;
- absence of `noindex`.

It also validates that `docs/sitemap.xml` exists and is a valid URL set.

The output deliberately records important gaps that cannot yet be measured from a
read-only repository workflow:

- search impressions;
- non-branded query coverage;
- referring domains and independent external mentions;
- website -> repository conversion;
- website -> first-contribution conversion;
- AI-answer-engine citations.

Those gaps should become integrations, not guessed values.

## Multi-axis controller rule

The self-growth controller should diagnose where the funnel is leaking.

Examples:

| Observation | Likely bottleneck | Bounded response |
| --- | --- | --- |
| pages are not indexable | technical SEO | repair canonical/meta/sitemap/structured data |
| technical SEO is healthy but non-branded impressions are low | discovery/authority | publish evidence-backed intent pages and earn genuine external references |
| impressions are high but click-through is low | positioning | test titles/descriptions and clarify the concrete user value |
| visits/stars rise but few people try the tool | activation | shorten runnable quickstart and improve demo |
| many stars but few first contributions | onboarding | create smaller starter tasks and clearer contribution lanes |
| first contributions occur but almost nobody returns | retention | reduce review latency and create second-step tasks |
| contributors grow but reviewer queue saturates | carrying capacity | stop acquisition pressure and recruit/enable reviewers |
| contributors depend on one maintainer | leadership | delegate bounded ownership and document stewardship paths |

The controller should prefer the smallest reversible experiment capable of resolving
the current bottleneck.

## SEO is a first-class self-improvement axis

The September 2026 SEO audit found the site technically healthy while external
authority remained weak. That is exactly the situation where a static SEO audit is
not enough.

IDKMesh should maintain a **search-demand map** around problems it can actually help
with. Initial intent clusters are:

1. AI agent verification;
2. multi-agent orchestration;
3. coding-agent evaluation;
4. AI code review reliability;
5. LLM agent reliability and provenance;
6. verifier independence / correlated reviewers;
7. GitHub AI-agent automation;
8. model and agent routing;
9. human + AI collaborative software engineering;
10. collective intelligence for software development.

The target should eventually be a maintained **100-query portfolio**: roughly ten
useful queries/intent variants per cluster. This is not permission to create 100 thin
keyword pages.

For each query, store:

```text
query
intent
target audience
best canonical page
evidence/result that page can support
current index status
impressions
clicks
average position
external citations/backlinks
AI-answer-engine citation observations
next experiment
```

The portfolio should be updated from actual search-console and external evidence when
those integrations exist.

## Content architecture for search and AI answers

A useful search page should answer one real question exceptionally well.

Preferred structure:

```text
direct answer
 -> why the problem matters
 -> runnable example
 -> measured IDKMesh evidence
 -> limitations / when it does not apply
 -> comparison to adjacent approaches
 -> links to experiment/code
 -> contribution path
```

High-value page families include:

- "What is AI agent verification?";
- "How do you verify coding-agent output?";
- "Why majority voting among AI reviewers can fail";
- "How to measure independent reviewers";
- "AI agent orchestration vs verification";
- "How to route GitHub issues to different coding agents/models";
- "How to use multiple coding agents without giving them merge authority";
- reproducible experiment/result pages;
- comparison pages grounded in documented features rather than promotional scoring.

The project should favor distinctive evidence that other people want to cite. Search
authority compounds more naturally when IDKMesh produces useful measurements,
benchmarks, tools, and diagrams than when it publishes generic AI articles.

## Authority and anti-Goodhart boundaries

These statements must remain true:

```text
star             != correctness
fork             != verified adoption
page view        != useful contribution
search ranking   != technical quality
mention          != endorsement
first PR         != retained contributor
AI citation      != truth
```

At the same time:

```text
ignoring stars, impressions, referrals, and contributor acquisition
    != healthy anti-Goodhart design
```

They are legitimate **observables of discovery**. They should influence discovery and
community experiments, but never verification or merge decisions.

Forbidden growth tactics include:

- fake or purchased stars;
- automated unsolicited spam;
- manufactured backlinks;
- mass low-value SEO pages;
- misleading comparisons;
- fake community accounts;
- hiding negative results to make the project appear stronger.

## Community reproduction goal

A large cluster/community requires more than acquisition. It requires reproduction.

The useful long-term chain is:

```text
one verified contribution
 -> clearer knowledge / interface / experiment
 -> one or more easier follow-up opportunities
 -> another person completes one
 -> that person can later help review or guide others
```

The growth metric therefore needs both reach and depth:

```text
Reach =
  search discovery
  + external mentions
  + GitHub interest

Depth =
  first contributors
  -> recurring contributors
  -> independent reviewers
  -> subsystem stewards
```

A healthy system increases Reach **and** converts a growing fraction of that reach into
Depth without exceeding review capacity.

## Next implementation slices

### V1 — repository-visible acquisition observatory

Implemented in this branch:

- stars/forks/subscribers;
- external commit-contributor count;
- static SEO/AEO coverage;
- sitemap validation;
- scheduled evidence artifact.

### V2 — search analytics adapters

**Partially implemented in this branch.**

Google Search Console now has a read-only adapter in
`scripts/search_console_snapshot.py`. When repository credentials are configured, the
weekly visibility workflow collects aggregate query+page observations, separates
branded from non-branded discovery, and joins exact query observations to the
portfolio. Setup is documented in
[`docs/admin/SEARCH_VISIBILITY_ANALYTICS.md`](../admin/SEARCH_VISIBILITY_ANALYTICS.md).

Bing remains intentionally pending. Microsoft's current documentation states that the
legacy SOAP/POX APIs were retired on 2026-08-31; IDKMesh should implement the current
REST contract only after it can be verified without guessing. Optional
privacy-respecting site analytics are also still open.

Store aggregated query/page observations only. Do not ingest user-level browsing data.

### V3 — 100-query intent portfolio

**Implemented as a hypothesis seed in this branch.**

`config/discovery-query-portfolio-v0.1.json` contains exactly 10 intent clusters with
10 unique non-branded query hypotheses each. Every cluster maps to an existing
canonical page and repository evidence. `scripts/discovery_query_portfolio.py` and
its tests fail closed on branding, duplicates, missing targets, missing evidence, or
count drift.

The checked-in 100 queries are not claimed search-volume evidence. Search Console/Bing
observations should reweight or replace hypotheses only after empirical data exists.

### V4 — authority graph

Observe genuine external references:

- independent technical articles;
- research citations;
- ecosystem documentation links;
- awesome lists/directories;
- conference/community mentions;
- package/tool references.

Prefer independently earned references over self-post counts.

### V5 — funnel attribution

Join, at aggregate level:

```text
query/referral
 -> docs/repo visit
 -> GitHub interaction
 -> contribution
 -> verified contribution
 -> recurrence
```

This is where IDKMesh can begin learning which discovery work produces durable
community capacity rather than transient attention.

### V6 — bounded growth experiments

**Bootstrap selector implemented in this branch.**

`scripts/visibility_growth_selector.py` consumes the static visibility observation,
query-portfolio report, optional Search Console evidence, and
`config/visibility-growth-policy-v0.1.json`. It emits exactly one bounded
recommendation from the currently observable bottleneck.

Current experiment types include:

- repair one deterministic technical SEO/AEO defect;
- connect Search Console before making content decisions;
- investigate weak non-branded discovery;
- improve one high-impression/low-CTR search snippet;
- recalibrate one intent cluster from observed queries;
- improve one visitor-to-first-contribution path;
- expand authority/referral measurement.

The current thresholds are explicitly labeled hand-authored bootstrap priors and must
be calibrated from future evidence. The selector cannot publish content, perform
outreach, create issues, mutate branches, or merge changes.

Future versions should add a deliberate no-op when evidence does not justify an
experiment and should consume V4/V5 authority/funnel evidence when those layers exist.

## Success criterion

The aim is not merely "more stars."

A much better north-star statement is:

> **Increase the number of people who independently discover IDKMesh and become
> recurring producers or reviewers of verified useful work, while keeping verification
> and governance capacity healthy.**

That is the external/community half of a genuinely self-improving repository.
