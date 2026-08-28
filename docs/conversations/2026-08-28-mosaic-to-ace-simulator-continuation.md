# Conversation record — MOSAIC to executable ACE simulation

- **Date:** 2026-08-28
- **Repository:** `MSKazemi/idkmesh`
- **Related proposal:** [`IDKIP-0002: IDK-MOSAIC`](../../idkips/0002-idk-mosaic-living-collective-intelligence.md)
- **Related issue:** [#27 — Growth Seed: build a tiny ACE population simulator](https://github.com/MSKazemi/idkmesh/issues/27)
- **Status:** Implementation proposed on a review branch; not autonomously merged.

## Questions / instructions from the project owner

The preceding project discussion asked whether mechanisms and formulas from biology, politics, society, psychology, physics, mathematics, economics, and computer science could be integrated into a new adaptive method for IDKMesh. That discussion produced the draft IDK-MOSAIC meta-algorithm.

The project owner then asked:

> `https://github.com/MSKazemi/idkmesh continue`

The instruction was interpreted as permission to continue the most concrete next step in the public repository rather than adding another theory-only document.

## Assistant output / proposed interpretation

The repository was inspected for the smallest existing executable task related to the new ideas. Issue #27 was selected because it already asks for a deterministic ACE population simulator with:

- `R_community`;
- logistic carrying capacity;
- decaying reproductive credit;
- under-reproduction, healthy-reproduction, and overload scenarios;
- a demonstration that maximizing raw activity can perform worse than capacity-governed growth.

This is a useful bridge from the broader MOSAIC design to executable evidence because ACE and MOSAIC share several mechanisms: branching control, carrying capacity, evolutionary strategy allocation, stigmergic work creation, and verification-limited growth.

## Implementation artifacts

A branch named `feat/ace-population-simulator` was created with:

1. `experiments/ace_population_sim.py`
   - Python standard library only;
   - deterministic fixed-seed simulation;
   - governed vs raw reproduction policies;
   - three required scenarios;
   - text, JSON, and CSV summaries;
   - CLI overrides for `K`, `tau`, decay, spawn rate, verification probability, review capacity, initial seeds, steps, and novelty scale;
   - finite-window `R_community` estimate based on verified descendant work;
   - `--check` acceptance assertions.

2. `experiments/README.md`
   - newcomer-oriented run commands;
   - explanation of the scenarios and policies;
   - explicit warning that the model is illustrative rather than empirical evidence.

3. `.github/workflows/ace-simulator-check.yml`
   - runs the deterministic acceptance check on relevant pull requests and changes to `main`.

## Local verification before repository publication

The script was syntax-compiled and run repeatedly with the default seed `20260828`. Repeated output was byte-for-byte deterministic.

Default qualitative results observed before publication:

```text
under-reproduction / governed:
  activity=11, verified=5, R=0.200, final review load=0

healthy-reproduction / governed:
  activity=205, verified=179, R=0.977, final review load=0, peak review load=5

overload / governed:
  activity=125, verified=103, final review load=5, peak review load=8

overload / raw:
  activity=202, verified=103, final review load=82, peak review load=82
```

The overload comparison is deliberately important: under the illustrative parameters, the raw policy creates **77 more activity events** while producing the **same 103 verified outputs**, and leaves a much larger review backlog. This satisfies the issue's requirement to demonstrate a case where maximizing raw activity is worse than capacity-governed growth.

These numbers are deterministic properties of the toy model and **must not be presented as empirical measurements of open-source communities**.

## Decisions

1. **Implement before extending theory.** Use issue #27 as the immediate executable evidence step.
2. **Keep the simulator standalone.** Do not couple it to the existing `jsonschema` experiment harness.
3. **Compare a governed and an intentionally naive raw policy.** This makes the carrying-capacity hypothesis falsifiable.
4. **Do not auto-merge.** Publish the implementation as a pull request so code and assumptions receive independent review.
5. **Do not yet fold the full MOSAIC controller into this starter issue.** Adaptive temperature, correlation-aware verification, strategy populations, and polycentric cells should be follow-up experiments after the minimal ACE model is reviewed.

## Open questions

- Is the finite-window implementation of `R_community` the best executable proxy for verified descendant reproduction?
- Should capacity suppress credit, spawn actuation, or only one of the two?
- How should real review load be estimated from GitHub data without rewarding activity volume?
- Which simulator parameters could eventually be calibrated from public repository histories?
- Should the next experiment add the optional replicator-mutator strategy selection from ACE and IDK-MOSAIC?
- Can adaptive MOSAIC temperature reduce both community stagnation and overload better than the fixed ACE governor?

## Community impact

This change creates a runnable contribution surface that requires only Python and no network access. It gives researchers and newcomers a small system they can modify, falsify, reproduce, or extend without understanding the entire IDKMesh architecture.

The model is intentionally labeled as illustrative to reduce the risk that attractive biology/physics analogies are mistaken for evidence. The reviewable PR and CI check also keep AI-generated implementation volume behind an explicit verification gate.
