# Work Unit Research Track — completion map

Issue: #15

This record maps the original formal Work Unit research questions onto the repository's current executable contracts and identifies which parts are complete versus continuing empirical work.

## Current canonical contract

IDKMesh now has a versioned Work Unit lineage:

- `schemas/work-unit-v0.1.schema.json` — initial executable contract;
- `schemas/work-unit-v0.2.schema.json` — current canonical contract;
- `schemas/work-unit.schema.json` — compatibility surface;
- `schemas/result-manifest-v0.1.schema.json` — worker self-report/output contract;
- `schemas/verification-result-v0.1.schema.json` — independent verification contract;
- `schemas/evaluator-plan-v0.2.schema.json` through v0.4 — verifier-owned evaluation commitments;
- `schemas/decomposition-benchmark-v0.1.schema.json` — decomposition experiment surface.

The v0.2 Work Unit carries the fields the research track originally asked to make explicit: stable identity/version, objective, bounded scope, inputs/outputs, dependencies, assumptions, validators/evidence requirements, permissions/security constraints, capability/resource requirements, budgets, provenance, and failure semantics.

## Research hypotheses mapped to executable evidence

### H1 — explicit contracts reduce integration ambiguity

Implemented structurally. WorkUnit -> ResultManifest -> EvaluatorPlan -> VerificationResult now forms a typed evidence path, and the repository validates exact digest/provenance bindings between these objects. Worker success is explicitly separated from independent acceptance.

This hypothesis remains open empirically: the repository should continue measuring integration failure/rework against less-structured task descriptions rather than treating the contract's existence as proof of benefit.

### H2 — an optimal Work Unit granularity exists

Not closed empirically. The repository now has a decomposition benchmark schema suitable for comparing monolithic, human-written, module/file, dependency-DAG, and formal-contract decompositions. The remaining work belongs to experiment execution and measurement, not another Work Unit schema revision.

### H3 — explicit assumptions/uncertainty reduce rework

Representable in the current contract, but not yet established by a dedicated causal experiment. Continue under the mathematical/research program rather than changing the core protocol without evidence.

### H4 — task/evidence DAGs improve independent execution

The repository has typed Goal/graph and evidence contracts plus decomposition experiment machinery. The protocol foundation is sufficient for experiments; whether the DAG structure improves outcomes remains an empirical question.

## Deliverables status

| Original deliverable | Current state |
| --- | --- |
| versioned Work Unit schema | complete: v0.1 + canonical v0.2 |
| JSON/YAML representation | complete through JSON schema and checked-in fixtures |
| task/evidence DAG model | available through Goal/graph + dependency/evidence bindings |
| decomposition benchmark | contract exists; real comparative runs remain research work |
| decomposition/integration metrics | partially available; empirical study remains |
| example Work Units | present across benchmark, node, verifier, and experiment fixtures |
| reference validator interface | implemented through schema harnesses, EvaluatorPlan, and independent verifier path |

## Architectural decision

Do not create a new Work Unit protocol merely because issue #15 remained open.

The correct current boundary is:

```text
Goal / project policy
  -> WorkUnit v0.2
  -> worker adapter
  -> ResultManifest v0.1
  -> verifier-owned EvaluatorPlan
  -> VerificationResult v0.1
  -> explicit integration decision
```

A2A, MCP, OpenHands, mini-SWE-agent, local nodes, and future adapters should map into this semantic contract rather than redefine it.

## What remains research, not protocol debt

The following questions remain intentionally open:

- optimal task granularity by task class;
- causal effect of explicit assumptions and uncertainty;
- context-size versus coordination-cost trade-offs;
- decomposition strategy comparisons on real repository tasks;
- effect of task/evidence DAGs on rework, conflicts, verifier cost, and human integration minutes.

These should be tracked as experiments under the existing research program. Any future breaking Work Unit change should require evidence that v0.2 cannot represent a necessary invariant, and should use a new schema version rather than silently changing v0.2 semantics.

## Completion conclusion

The **protocol-definition objective of issue #15 is complete**. The remaining falsifiable hypotheses are downstream experimental questions and should continue in the research/benchmark issues rather than keeping the core Work Unit definition track open indefinitely.
