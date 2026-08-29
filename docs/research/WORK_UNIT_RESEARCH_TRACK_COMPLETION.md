# Work Unit Research Track — protocol status map

Issue: #15

This record maps the formal Work Unit research questions onto the repository's current executable contracts and separates the completed protocol-definition foundation from the empirical acceptance work that still keeps issue #15 open.

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

PR #248 subsequently added the five-arm decomposition benchmark contract, strict validator, canonical coding/testing/research/review WorkUnit DAG, metrics, and a deliberately synthetic fixture. That infrastructure establishes the experimental surface; it does not establish which decomposition strategy is better.

## Research hypotheses mapped to executable evidence

### H1 — explicit contracts reduce integration ambiguity

Implemented structurally. WorkUnit -> ResultManifest -> EvaluatorPlan -> VerificationResult now forms a typed evidence path, and the repository validates exact digest/provenance bindings between these objects. Worker success is explicitly separated from independent acceptance.

This hypothesis remains open empirically: the repository should measure integration failure/rework against less-structured task descriptions rather than treating the contract's existence as proof of benefit.

### H2 — an optimal Work Unit granularity exists

Open empirically. The repository has the five-arm decomposition benchmark machinery needed to compare decomposition strategies, but the checked-in observations are synthetic infrastructure data. Controlled runs by independently assigned workers with bounded context and shared hidden tests are still required.

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
| decomposition benchmark | complete as experimental infrastructure via #248 |
| decomposition/integration metrics | defined; real comparative measurements remain |
| example Work Units | present across benchmark, node, verifier, and experiment fixtures |
| reference validator interface | implemented through schema harnesses, EvaluatorPlan, and independent verifier path |

## Architectural decision

Do not create a new Work Unit protocol merely because issue #15 remains open.

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

## What remains before issue #15 can close

Issue #15's own current evidence ledger requires genuine controlled comparative runs rather than synthetic fixtures alone. Closure therefore still requires, at minimum:

- independently assigned workers across the five decomposition arms;
- bounded and comparable context budgets;
- shared hidden tests/evaluation criteria;
- measured integration failures/rework and context/coordination costs;
- analysis that does not assume any decomposition strategy is superior before outcomes are observed.

Additional hypotheses remain intentionally open, including the causal effect of explicit assumptions/uncertainty and the effect of task/evidence DAGs on verifier cost and human integration minutes.

Any future breaking Work Unit change should require evidence that v0.2 cannot represent a necessary invariant and should use a new schema version rather than silently changing v0.2 semantics.

## Status conclusion

The **protocol-definition and benchmark-infrastructure foundation is complete enough to run the research**, but **issue #15 is not complete**. Its remaining acceptance criterion is empirical: execute the controlled independent-worker comparison and retain the measured evidence. This distinction prevents protocol churn while preserving the falsifiable research question.
