# Work Unit composability profile v0.2

**Status:** experimental reference profile
**Related:** issue #15, issue #3, issue #17

## Outcome

The existing WorkUnit v0.2 contract already carries the candidate fields from
issue #15 and the A2A/MCP binding already round-trips them without loss. This
profile adds the missing executable research surface without changing either
historical WorkUnit schema:

- a five-arm decomposition benchmark contract;
- one canonical coding/testing/research/review WorkUnit DAG;
- deterministic task/evidence graph validation;
- one stable aggregation definition for the issue's primary metrics.

The committed observations are marked `synthetic_fixture`. They test the
benchmark machinery only and **must not be cited as evidence** that formal Work
Units outperform another strategy. A research conclusion requires new
`observed` runs performed by independent workers under controlled context.

## Deliverable audit

| Issue #15 deliverable | Canonical artifact |
| --- | --- |
| versioned Work Unit schema | `schemas/work-unit-v0.2.schema.json` |
| JSON representation | `examples/work-units/phase0-smoke.work-unit.json` |
| task/evidence DAG | `formal_task_evidence_dag` emitted by `experiments/work_unit_decomposition.py` |
| decomposition benchmark | `schemas/decomposition-benchmark-v0.1.schema.json` and the committed fixture |
| decomposition/integration metrics | deterministic aggregation defined below |
| coding/testing/research/review examples | `examples/work-units/composability/` |
| reference validator interface | `validate_benchmark()`, `run_benchmark()`, and the CLI |
| A2A/MCP mapping and round trip | `docs/interoperability/A2A_MCP_MAPPING_V0_1.md` and `interop.bindings` |

The benchmark is intentionally a separate versioned contract. The research
interface can evolve without reinterpreting durable WorkUnit v0.1 or v0.2
artifacts.

## Benchmark arms

Every valid benchmark contains each arm exactly once:

1. `monolithic` — one natural-language task;
2. `human_subtasks` — manually divided task descriptions;
3. `file_module` — ownership divided primarily by repository path;
4. `dependency_dag` — explicit bounded tasks and prerequisite edges;
5. `formal_work_units` — v0.2 contracts with validators and evidence requirements.

The benchmark names worker implementation/revision provenance, and every
observation binds a unique attempt ID to one declared worker. An arm lists its
units and exactly one observation per unit. The reference
validator rejects missing/duplicate strategies, missing/duplicate observations,
unknown workers, duplicate attempts, unknown dependency targets, dependency cycles, repository-path escapes,
schema-invalid WorkUnits, and disagreement between benchmark dependencies and a
formal WorkUnit's `requires` dependencies.

## Reference validator interface

Python callers use:

```python
from experiments.work_unit_decomposition import run_benchmark, validate_benchmark

task_evidence_dag = validate_benchmark(benchmark)
report = run_benchmark(benchmark)
```

The command-line interface is:

```bash
python experiments/work_unit_decomposition.py \
  examples/benchmarks/work-unit-decomposition-v0.1.json \
  --pretty
```

Validation is read-only. The tool does not execute WorkUnit commands, contact
workers, call external services, accept candidates, or integrate changes.

## Task/evidence DAG

Only `requires` dependencies enter the executable task projection. For each
formal WorkUnit `W`:

```text
W --requires--> prerequisite WorkUnit
W --requires_evidence--> declared evidence requirement
```

`informs`, `validates`, `derived_from`, and `blocks` remain useful metadata but
do not become prerequisite edges in this conservative projection. This avoids
inventing execution order from relations whose scheduling direction is not
defined by v0.2. A cycle in the `requires` projection fails closed.

## Metric definitions

All rates are reported in `[0, 1]` and rounded to six decimal places.

| Metric | Deterministic aggregation |
| --- | --- |
| completion success rate | completed unit observations / unit observations |
| integration failure rate | integration-failed unit observations / unit observations |
| merge conflicts | sum of recorded conflict events |
| rework cycles | sum of recorded rework cycles |
| context bytes | sum of bytes supplied to workers |
| cross-worker messages | sum of task-related inter-worker messages |
| hidden-test success rate | hidden tests passed / hidden tests run; `0` when none ran |
| assumption mismatches | sum of observed mismatches |
| dependency violations | sum of attempts performed before declared prerequisites |
| verification seconds | sum of verifier wall-clock seconds |
| human integration minutes | sum of measured human integration time |
| executable without global context rate | units declared not to require global repository context / units |

Real runs should define measurement instructions before execution, preserve raw
per-unit observations, use the same target revision and hidden tests across
arms, randomize or counterbalance assignment, and record worker/model/tool
provenance. A run may use `evidence_class: observed` only when its numbers come
from those executions; changing the label does not itself establish rigor.

## Interoperability boundary

The A2A/MCP mapping remains authoritative. External protocol completion means a
worker execution completed, not that IDKMesh accepted or integrated the result.
The full WorkUnit plus canonical digest travels in the namespaced binding, so
permissions, validators, evidence requirements, uncertainty, budgets, and
provenance remain intact.

## Community impact

Contributors can now compare decomposition approaches with one reviewable input
format and can add real observations without modifying the WorkUnit contract.
The four small examples expose the minimum bounded context for common roles and
make dependency/evidence failures visible before work is dispatched.

## Known limits

- The fixture does not execute agents and provides no scientific result.
- A boolean `global_context_required` is an observed/protocol input, not an
  automatically inferred property.
- v0.2 does not define scheduling direction for every dependency relation, so
  only `requires` is executable here.
- Quality of hidden tests and independence of workers/verifiers remain external
  experimental controls.
