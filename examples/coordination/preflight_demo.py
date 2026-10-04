"""Reproduce blocked -> ready -> small/strong route advice using synthetic evidence.

No network, credentials, worker execution, verification or integration occurs.
"""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from idkmesh.connector_routing import ConnectorProfile, RoutingDecision
from idkmesh.coordination_preflight import (
    DependencyGraph, DependencyProjection, EffortEstimate, PrerequisiteObservation,
    coordination_preflight,
)
from idkmesh.tenant_scope import TenantScope


def demo() -> dict:
    scope = TenantScope("demo", "synthetic-project")
    units = []
    for name in ("research", "coding", "testing", "review"):
        unit = json.loads((ROOT / f"examples/work-units/composability/{name}.work-unit.json").read_text())
        unit["provenance"]["source_revision"] = "a" * 40
        units.append(unit)
    graph = DependencyGraph(scope, units, source_revisions={unit["id"]: "a" * 40 for unit in units})
    projection = DependencyProjection(graph)
    estimate = EffortEstimate(1, "low", "low", 60, 2, 1, "synthetic demo declaration")
    decision = RoutingDecision("T1", "agent_candidate")
    connectors = [ConnectorProfile("small-demo", "agent", "offline", capability_tiers={"T1"}),
                  ConnectorProfile("strong-demo", "agent", "offline", capability_tiers={"T3"})]
    coding = "issue15/example/coding"
    blocked = coordination_preflight(projection, coding, estimate, decision, connectors)
    research = "issue15/example/research"
    projection.observe(PrerequisiteObservation(
        scope, "synthetic-event-1", 1, graph.bindings[research], "integrated",
        projection.readiness()[research].inputs_digest,
        integrated_revision="b" * 40, artifacts_digest="sha256:" + "c" * 64,
        verification_reference="synthetic:verifier-fixture", integration_reference="synthetic:human-decision-fixture",
    ))
    ready = coordination_preflight(projection, coding, estimate, decision, connectors)
    complex_estimate = EffortEstimate(8, "low", "high", 600, 10, 5, "synthetic demo declaration")
    strong = coordination_preflight(projection, coding, complex_estimate, decision, connectors)
    return {"evidence_class": "synthetic_fixture", "blocked": blocked, "ready_small": ready, "ready_strong": strong}


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
