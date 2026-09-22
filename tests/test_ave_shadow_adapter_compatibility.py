import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"

shadow_spec = importlib.util.spec_from_file_location(
    "adaptive_policy_shadow",
    TOOLS / "adaptive_policy_shadow.py",
)
shadow = importlib.util.module_from_spec(shadow_spec)
sys.modules[shadow_spec.name] = shadow
assert shadow_spec.loader is not None
shadow_spec.loader.exec_module(shadow)

adapter_spec = importlib.util.spec_from_file_location(
    "ave_shadow_adapter",
    TOOLS / "ave_shadow_adapter.py",
)
adapter = importlib.util.module_from_spec(adapter_spec)
sys.modules[adapter_spec.name] = adapter
assert adapter_spec.loader is not None
adapter_spec.loader.exec_module(adapter)


FIXTURE = ROOT / "results/verification/node-e2e-replay-2026-08-30"


def load(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_historical_canonical_bundle_is_contract_compatible_only():
    """Compatibility test only: the historical outcome is already known.

    This MUST NOT be retained or described as N3 pre-outcome evidence.
    """
    work_unit = load("work-unit.json")
    evaluator_plan = load("evaluator-plan.json")

    assert (
        adapter.canonical_digest(work_unit)
        == evaluator_plan["binding"]["work_unit_digest"]
    )

    verifier_id = evaluator_plan["verifier"]["id"]
    verifier_pool = {
        "schema_version": "0.1",
        "kind": "idkmesh-verifier-observation-pool",
        "repository": "MSKazemi/idkmesh",
        "source_revision": evaluator_plan["binding"]["source_revision"],
        "captured_at": "2026-09-22T12:00:00Z",
        "work_unit_id": work_unit["id"],
        "task_domain": "testing",
        "worker_id": "local/idkmesh-node",
        "reliability_max_age_days": 30,
        "verifier_candidates": [
            {
                "id": verifier_id,
                "family": "deterministic-patch-verifier",
                "provider_family": None,
                "available": True,
                "supported_validator_ids": list(
                    evaluator_plan["required_validator_ids"]
                ),
                "review_units": 1.0,
                "queue_load": 0.0,
                "independence": {
                    "independent_from_worker": True,
                    "shared_model_family": False,
                    "shared_runtime": False,
                },
                "reliability": {
                    "basis": "unknown",
                    "alpha": 1,
                    "beta": 1,
                    "sample_count": 0,
                    "domain": "testing",
                    "observed_at": None,
                    "shift_warning": False,
                    "source_refs": [],
                    "known_bad_probe_trials": 0,
                    "known_bad_probe_breaches": 0,
                },
            }
        ],
        "limitations": [
            "Historical compatibility fixture only; verification outcome was already known before this pool was constructed."
        ],
    }

    plan = adapter.build_ave_shadow_plan(
        repository="MSKazemi/idkmesh",
        work_unit=work_unit,
        evaluator_plan=evaluator_plan,
        verifier_pool=verifier_pool,
        maturity="N2",
        input_refs=[
            "results/verification/node-e2e-replay-2026-08-30/work-unit.json",
            "results/verification/node-e2e-replay-2026-08-30/evaluator-plan.json",
        ],
        evidence_refs=[
            "compatibility-only:not-n3-evidence",
        ],
    )

    assert all(
        gate["status"] == "pass"
        for gate in plan["hard_gates"]
    )
    assert (
        plan["recommendation"]["selected_choice_id"]
        == plan["recommendation"]["baseline_choice_id"]
        == f"portfolio:{verifier_id}"
    )
    assert plan["policy"]["maturity"] == "N2"
    assert plan["authority"]["advisory_only"] is True
    assert plan["authority"]["dispatch"] is False
    assert plan["authority"]["merge"] is False
    assert any(
        "Historical compatibility fixture only" in limitation
        for limitation in plan["limitations"]
    )
