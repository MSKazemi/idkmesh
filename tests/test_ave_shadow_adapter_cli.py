import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).parents[1] / "tools"

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

cli_spec = importlib.util.spec_from_file_location(
    "ave_shadow_adapter_cli",
    TOOLS / "ave_shadow_adapter_cli.py",
)
cli = importlib.util.module_from_spec(cli_spec)
sys.modules[cli_spec.name] = cli
assert cli_spec.loader is not None
cli_spec.loader.exec_module(cli)


SOURCE = "3" * 40


def work_unit():
    value = {
        "schema_version": "0.2",
        "id": "cli/work-unit",
        "version": 1,
        "kind": "testing",
        "security": {"risk_class": "low"},
        "budget": {
            "project_spend_usd_max": 0,
            "paid_fallback_allowed": False,
        },
        "verification_policy": {
            "strategy": "all_required",
            "independent_from_worker": True,
            "minimum_independent_verifiers": 1,
        },
        "validators": [
            {
                "id": "schema-check",
                "type": "schema",
                "required": True,
            }
        ],
        "provenance": {"source_revision": SOURCE},
    }
    return value


def evaluator_plan(wu):
    return {
        "schema_version": "0.4",
        "id": "verification/cli-plan",
        "binding": {
            "work_unit_id": wu["id"],
            "work_unit_version": wu["version"],
            "work_unit_digest": adapter.canonical_digest(wu),
            "source_revision": SOURCE,
        },
        "verifier": {
            "id": "existing-verifier",
            "type": "system",
            "adapter": "test",
            "adapter_version": "1",
        },
        "required_validator_ids": ["schema-check"],
        "policy": {
            "require_verifier_distinct_from_worker": True,
        },
    }


def verifier_pool(wu):
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-verifier-observation-pool",
        "repository": "MSKazemi/idkmesh",
        "source_revision": SOURCE,
        "captured_at": "2026-09-22T12:00:00Z",
        "work_unit_id": wu["id"],
        "task_domain": "testing",
        "worker_id": "worker-1",
        "reliability_max_age_days": 30,
        "verifier_candidates": [
            {
                "id": "candidate-verifier",
                "family": "family-a",
                "provider_family": None,
                "available": True,
                "supported_validator_ids": ["schema-check"],
                "review_units": 1,
                "queue_load": 0,
                "independence": {
                    "independent_from_worker": True,
                    "shared_model_family": False,
                    "shared_runtime": False,
                },
                "reliability": {
                    "basis": "live_outcomes",
                    "alpha": 6,
                    "beta": 4,
                    "sample_count": 8,
                    "domain": "testing",
                    "observed_at": "2026-09-21T12:00:00Z",
                    "shift_warning": False,
                    "source_refs": ["live-history"],
                    "known_bad_probe_trials": 2,
                    "known_bad_probe_breaches": 0,
                },
            }
        ],
        "limitations": ["test fixture only"],
    }


class AVEShadowAdapterCLITests(unittest.TestCase):
    def test_cli_refuses_output_created_after_initial_check(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wu = work_unit()
            work_path = root / "work.json"
            plan_path = root / "evaluator.json"
            pool_path = root / "pool.json"
            output_path = root / "shadow.json"
            work_path.write_text(json.dumps(wu), encoding="utf-8")
            plan_path.write_text(json.dumps(evaluator_plan(wu)), encoding="utf-8")
            pool_path.write_text(json.dumps(verifier_pool(wu)), encoding="utf-8")
            original_open = Path.open

            def raced_open(path, mode="r", *args, **kwargs):
                if path == output_path and mode == "x":
                    output_path.write_text("existing evidence\n", encoding="utf-8")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", raced_open):
                self.assertEqual(
                    cli.main([
                        "--work-unit", str(work_path),
                        "--evaluator-plan", str(plan_path),
                        "--verifier-pool", str(pool_path),
                        "--output", str(output_path),
                    ]),
                    2,
                )
            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing evidence\n")

    def test_cli_writes_frozen_plan_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wu = work_unit()
            paths = {
                "work": root / "work.json",
                "plan": root / "evaluator.json",
                "pool": root / "pool.json",
                "output": root / "shadow.json",
            }
            paths["work"].write_text(
                json.dumps(wu),
                encoding="utf-8",
            )
            paths["plan"].write_text(
                json.dumps(evaluator_plan(wu)),
                encoding="utf-8",
            )
            paths["pool"].write_text(
                json.dumps(verifier_pool(wu)),
                encoding="utf-8",
            )

            argv = [
                "--work-unit",
                str(paths["work"]),
                "--evaluator-plan",
                str(paths["plan"]),
                "--verifier-pool",
                str(paths["pool"]),
                "--maturity",
                "N3",
                "--input-ref",
                "fixture:cli",
                "--output",
                str(paths["output"]),
            ]
            self.assertEqual(cli.main(argv), 0)
            plan = json.loads(
                paths["output"].read_text(encoding="utf-8")
            )
            self.assertEqual(plan["policy"]["id"], "ave-core")
            self.assertEqual(plan["policy"]["maturity"], "N3")
            self.assertFalse(plan["authority"]["dispatch"])
            self.assertFalse(plan["authority"]["merge"])

            self.assertEqual(cli.main(argv), 2)

    def test_cli_abstention_is_still_written_as_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wu = work_unit()
            plan = evaluator_plan(wu)
            plan["binding"]["work_unit_digest"] = (
                "sha256:" + "0" * 64
            )
            work_path = root / "work.json"
            plan_path = root / "evaluator.json"
            pool_path = root / "pool.json"
            output_path = root / "shadow.json"
            work_path.write_text(json.dumps(wu), encoding="utf-8")
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            pool_path.write_text(
                json.dumps(verifier_pool(wu)),
                encoding="utf-8",
            )
            self.assertEqual(
                cli.main(
                    [
                        "--work-unit",
                        str(work_path),
                        "--evaluator-plan",
                        str(plan_path),
                        "--verifier-pool",
                        str(pool_path),
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            result = json.loads(
                output_path.read_text(encoding="utf-8")
            )
            self.assertIsNone(
                result["recommendation"]["selected_choice_id"]
            )
            self.assertTrue(
                any(
                    gate["status"] == "fail"
                    for gate in result["hard_gates"]
                )
            )


if __name__ == "__main__":
    unittest.main()
