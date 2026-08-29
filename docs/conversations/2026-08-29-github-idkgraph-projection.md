# GitHub activity to IDKGraph implementation

Date: 2026-08-29

## Project-owner request

Select unclaimed issues, solve them professionally in parallel, merge the
accepted changes, push them to the canonical remote, and close only completed
issues.

## Assistant interpretation and action

Issue 46 was selected as one bounded stream. The implementation adds an
offline, deterministic projection from normalized GitHub activity to IDKGraph,
with stable identity, evidence-independence rules, shared-capacity
deduplication, guarded multi-objective ranking, post-decision outcomes, and an
explicitly disabled actuator.

## Decisions

- Natural-language GitHub content remains untrusted data and is represented by
  a digest rather than copied into executable inputs.
- Comments and author self-review never count as independent verification.
- Repeated evidence channels and capacity observations are deduplicated by
  explicit stable keys; conflicting capacity values fail closed.
- Candidate hard guards precede ranking scores.
- The adapter remains offline and advisory in v0.1.

## Verification and limitations

Unit tests cover schema validity, byte-stable replay under shuffled input,
trust handling, independent evidence, shared capacity, conflicting capacity,
ranking guards, and the disabled actuator. The normalized snapshot is an
offline interchange format; collecting live GitHub data and enabling any
write actuator are intentionally outside this change.

## Community impact

The fixture and focused command give contributors a reproducible path that
requires no credentials or paid services. Explicit provenance and conservative
evidence rules reduce reviewer ambiguity without automating repository writes.
