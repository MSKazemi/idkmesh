# Stewardship record: undefined HHI for empty collaboration populations

Date: 2026-09-17
Issue: #86
Pull request: #487

This run selected one bounded scientific-correctness slice from the open self-maintaining-network evidence work: the collaboration analyzer previously emitted HHI `0.0` when there were no eligible independent-reviewer or changed-file-owner observations.

The implementation changes the current analyzer contract to `collaboration-observables-v0.2` / `observed-share-hhi-v2`. A non-empty population continues to use `HHI = sum_i s_i^2`. An empty population now emits JSON `null` for `hhi`, `status: undefined_empty_population`, and `uncertainty: undefined_without_observations`. This avoids conflating absence of an observed share vector with the numeric lower-bound interpretation of a highly dispersed non-empty population.

The change is integrated in the existing collaboration-observables path rather than adding a parallel metric. Regression coverage exercises both review and ownership populations, and the existing research documentation explains the contract, limitations, and historical compatibility. The committed v0.1 production artifact remains immutable: its historical `0.0` is documented as an old encoding of an empty reviewer population, not evidence of perfectly distributed review.

No thresholds, health ratings, contributor rankings, causal claims, or policy/merge authority are introduced. PR #487 must satisfy repository CI on its exact head and have no unresolved substantive review or merge blockers before it can be merged. The umbrella issue #86 should remain open after this bounded slice because its broader falsifiable milestones are not completed by this change alone.
