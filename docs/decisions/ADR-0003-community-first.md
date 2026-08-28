# ADR-0003: Community-first development

- **Status:** Proposed for adoption with this change
- **Date:** 2026-08-28

## Context

IDKMesh aims to coordinate potentially very large communities of humans, AI agents, and heterogeneous compute. The technical vision depends on participation at a scale that cannot be added after the fact.

The project is also unusually difficult to onboard into because its final product and architecture are intentionally still evolving. Without explicit community design, technical complexity can create an inner circle that understands the system while newcomers cannot find a useful entry point.

The project owner therefore established two related rules:

1. useful IDKMesh project conversations and findings should be preserved in the canonical public repository in a structured form; and
2. community creation and growth are the highest-priority design perspective for repository evolution.

## Decision

Adopt **community-first development** as a project-level invariant.

Every substantial technical, research, governance, tooling, or documentation change should consider how it affects the ability of people to:

- discover the project;
- understand it progressively;
- find a suitable contribution;
- receive useful review;
- reproduce evidence;
- participate without privileged private context;
- grow into review and leadership responsibilities;
- maintain the project over time.

Substantial proposals and pull requests should include a **Community Impact** section.

The repository should maintain standard open-source community-health artifacts including contributor guidance, governance, conduct, security reporting, support, maintainers, and issue/PR templates.

Project conversations should be summarized into discoverable structured records rather than stored as an undifferentiated transcript dump.

## Consequences

### Positive

- Community growth becomes an engineering constraint rather than a later marketing task.
- Newcomer friction becomes visible and actionable.
- Technical decisions must account for review and maintenance scalability.
- Non-code contribution and community stewardship become first-class work.
- Leadership development is designed into the project early.
- The public reasoning history can help contributors understand why the project evolved.

### Costs / risks

- Contributors must spend additional effort on documentation and community impact for significant changes.
- Early governance documents may need frequent revision as the real community grows.
- Community metrics can become harmful if turned into gamified targets.
- Too much process too early could discourage experimentation; therefore the bootstrap model must remain lightweight.

## Alternatives considered

### Build the technology first, community later

Rejected. Large-scale distributed collaboration is itself the product thesis, so a community cannot be treated as a later distribution channel.

### Central founder-led project until technical maturity

Useful temporarily for bootstrap speed but rejected as a long-term model because it creates a single point of organizational failure and prevents the leadership scaling required by the project vision.

### Adopt a complex foundation-style governance immediately

Rejected for now. Governance should reflect the community that actually exists. The initial model is intentionally lightweight and should evolve toward scoped/subproject governance only when contributor activity justifies it.

## Implementation

This ADR is implemented initially through:

- `COMMUNITY.md`
- `CONTRIBUTING.md`
- `GOVERNANCE.md`
- `CODE_OF_CONDUCT.md`
- `SUPPORT.md`
- `SECURITY.md`
- `MAINTAINERS.md`
- `.github/ISSUE_TEMPLATE/`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/community/COMMUNITY_GROWTH_STRATEGY.md`
- the updated `PROJECT_RULES.md`
- a newcomer-oriented section in `README.md`

## Revisit trigger

Revisit this governance design when any of these become true:

- several sustained reviewers/maintainers emerge;
- a subproject has multiple active contributors and distinct ownership;
- founder review becomes a bottleneck;
- community moderation requires dedicated stewards;
- contribution volume grows faster than review capacity.
