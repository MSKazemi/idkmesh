# IDKMesh Improvement Proposals (IDKIPs)

IDKIPs are the lightweight public mechanism for proposing significant changes to IDKMesh architecture, protocols, governance, interoperability, security boundaries, or experimental policy.

IDKMesh intentionally begins with uncertainty. The goal of the IDKIP process is therefore **not** to force early consensus. It is to make alternatives, assumptions, evidence, dissent, and decisions inspectable.

## When an IDKIP is appropriate

Use an IDKIP when a proposal materially changes one or more of:

- core protocol or schema;
- worker/agent interoperability;
- verification/integration policy;
- distributed-state model;
- security or trust assumptions;
- governance or contributor authority;
- compatibility guarantees;
- major subsystem boundaries;
- project-wide metrics or experimental policy.

A normal bug fix, documentation improvement, small refactor, benchmark contribution, or isolated plugin usually does not need an IDKIP.

## Lifecycle

```text
Draft
  -> Discussion
  -> Experimental
  -> Accepted

or

Draft/Discussion/Experimental
  -> Rejected / Withdrawn / Superseded
```

### Draft

The author is developing the proposal. Major open questions are allowed.

### Discussion

The proposal is ready for broad criticism and alternatives.

### Experimental

The proposal is sufficiently specified to test. Experimental means **permission to gather evidence**, not permanent architectural approval.

### Accepted

The proposal has enough evidence, implementation experience, and community/maintainer review to become the current project direction.

### Rejected

The project has decided not to adopt the proposal under current conditions. The record remains useful.

### Withdrawn

The author or maintainers stop pursuing the proposal without making a claim that the idea is technically wrong.

### Superseded

A later IDKIP replaces the proposal.

## Required sections

An IDKIP should include:

1. **Summary**
2. **Problem**
3. **Motivation**
4. **Scope / non-goals**
5. **Proposal**
6. **Alternatives considered**
7. **Interoperability / compatibility**
8. **Security / abuse considerations**
9. **Community Impact**
10. **Measurable success criteria**
11. **Experiment / evidence plan**
12. **Dissent / unresolved questions**
13. **Migration / rollback**
14. **Implementation links**

For conceptual proposals, some sections can initially say `TBD`, but the missing evidence must remain visible.

## Evidence rule

Popularity is not sufficient evidence for a technical claim.

Depending on the proposal, evidence can include:

- benchmark results;
- simulations;
- prototypes;
- interoperability tests;
- security analysis;
- reproducibility reports;
- contributor usability tests;
- operational experience;
- external standards/prior art;
- documented negative results.

The stronger and harder-to-reverse the decision, the stronger the expected evidence.

## Competing proposals

Competing IDKIPs may coexist in `Experimental` status.

Where practical, the project should prefer:

```text
competing proposal A
          +
competing proposal B
          |
          v
common benchmark / experiment
          |
          v
evidence-informed decision
```

over arguments based only on preference or authority.

## Decision authority

During bootstrap governance, maintainers are responsible for changing IDKIP status after public review and documented rationale.

As governance becomes distributed, relevant subsystem maintainers/reviewers should participate according to `GOVERNANCE.md`.

No IDKIP may override repository safety, legal, security, or Code of Conduct requirements.

## Community Impact requirement

A technically attractive design can still be harmful if it makes participation or maintenance much harder.

Major IDKIPs should explicitly ask:

- Does this make the project easier or harder to understand?
- Does it create new expert-only bottlenecks?
- Can independent contributors implement compatible components?
- Does it increase maintainer/reviewer burden?
- Does it create a path for new contributors or close one?
- What documentation/migration will people need?

## Numbering

- `0000` is the template.
- New IDKIPs receive the next available integer when they are added to the repository.
- Numbers are never reused after a proposal has been public.

File format:

`idkips/NNNN-short-descriptive-name.md`

## Relationship to ADRs

IDKIPs and Architecture Decision Records have different jobs:

- **IDKIP:** proposal, alternatives, experiment, debate, evidence.
- **ADR:** durable record of a decision that the project actually made.

An accepted IDKIP may result in an ADR. An experimental IDKIP does not imply a final decision.

## Relationship to issues and pull requests

Use a GitHub issue for discussion/task tracking and a pull request for changes, but keep the proposal itself in the repository so it remains versioned and reviewable.

An IDKIP should link to relevant issues, PRs, experiments, and results.

## Current proposals

- [`IDKIP-0001: Interoperability-first Work Contract`](idkips/0001-interoperability-first-work-contract.md)
- [`IDKIP-0002: IDK-MOSAIC — A Living Collective-Intelligence Control Loop`](idkips/0002-idk-mosaic-living-collective-intelligence.md)

## Inspirations

The process is informed by public proposal systems including Bitcoin BIPs, BitTorrent BEPs, Kubernetes KEPs, Python PEPs, and IETF RFC practices, adapted for IDKMesh's experimental and community-first character.