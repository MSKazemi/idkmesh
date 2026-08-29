#!/usr/bin/env python3
"""Additive EvaluatorPlan v0.3 runner with explicit substring semantics.

This module deliberately leaves `evaluator_plan_runner.py` and EvaluatorPlan
v0.1/v0.2 untouched. It reuses the canonical runner's binding/authority guards
through a compatibility projection, then dispatches only the new v0.3 semantic
contract to deterministic patch verifier v0.2.0.

The compatibility projection is validation-only. VerificationResult provenance
is bound to the exact original v0.3 EvaluatorPlan digest, never to the projected
v0.2 object.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

import evaluator_plan_runner as base_runner
import local_verifier
import patch_verifier_v020
from provenance_integrity import canonical_digest, validate_integrity

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PLAN_SCHEMA = ROOT / "schemas" / "evaluator-plan-v0.3.schema.json"
RUNNER_VERSION = "0.3"
PATCH_VALIDATOR_IDS = {"result-manifest-schema", "independent-review"}


class EvaluatorPlanV03Error(RuntimeError):
    """Raised when v0.3 evaluator control data is invalid or unsafe."""


def load_plan(path: Path) -> dict[str, Any]:
    plan = local_verifier.load_json(path)
    local_verifier.validate_schema(plan, EVALUATOR_PLAN_SCHEMA, "EvaluatorPlan v0.3")
    patch_verifier_v020.validate_policy(operational_policy(plan))
    return plan


def backend_name(plan: dict[str, Any]) -> str:
    if plan.get("schema_version") == "0.3" and plan.get("backend", {}).get("type") == "unified_diff":
        return "unified_diff"
    raise EvaluatorPlanV03Error("EvaluatorPlan v0.3 does not select unified_diff")


def operational_policy(plan: dict[str, Any]) -> dict[str, Any]:
    backend_name(plan)
    return {
        "schema_version": "0.3",
        "id": plan["id"],
        "candidate_artifact_id": plan["candidate_artifact_id"],
        "backend": copy.deepcopy(plan["backend"]),
    }


def _compat_v02_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Project v0.3 onto v0.2 only to reuse binding/authority validation."""

    projected = copy.deepcopy(plan)
    projected["schema_version"] = "0.2"
    projected["verifier"]["adapter_version"] = "0.1.1"
    backend = projected["backend"]
    backend.pop("required_added_substrings", None)
    backend["required_added_text"] = ["__IDKMESH_V03_BINDING_VALIDATION_ONLY__"]
    return projected


def validate_plan_binding(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    plan: dict[str, Any],
    plan_path: Path,
    candidate_root: Path,
) -> None:
    local_verifier.validate_schema(plan, EVALUATOR_PLAN_SCHEMA, "EvaluatorPlan v0.3")
    if set(plan["required_validator_ids"]) != PATCH_VALIDATOR_IDS:
        raise EvaluatorPlanV03Error(
            "EvaluatorPlan v0.3 unified_diff requires exactly result-manifest-schema and independent-review"
        )
    patch_verifier_v020.validate_policy(operational_policy(plan))

    # Reuse the canonical v0.2 runner's exact WorkUnit/source/result binding,
    # validator coverage, verifier-distinctness, and candidate-root authority
    # guards without teaching v0.2 a new semantic meaning.
    base_runner.validate_plan_binding(
        work_unit=work_unit,
        worker_result=worker_result,
        plan=_compat_v02_plan(plan),
        plan_path=plan_path,
        candidate_root=candidate_root,
    )


def verify_with_plan(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    plan: dict[str, Any],
    candidate_root: Path,
    plan_path: Path,
) -> dict[str, Any]:
    validate_plan_binding(
        work_unit=work_unit,
        worker_result=worker_result,
        plan=plan,
        plan_path=plan_path,
        candidate_root=candidate_root,
    )

    result = patch_verifier_v020.verify_patch_candidate(
        work_unit=work_unit,
        worker_result=worker_result,
        policy=operational_policy(plan),
        candidate_root=candidate_root,
        policy_path=plan_path,
    )
    if result["verifier"] != plan["verifier"]:
        raise EvaluatorPlanV03Error(
            "underlying verifier identity/version differs from bound EvaluatorPlan v0.3"
        )

    result_check_ids = {
        check["id"] for check in result["checks"] if check.get("required") is True
    }
    if result_check_ids != set(plan["required_validator_ids"]):
        raise EvaluatorPlanV03Error(
            "VerificationResult required checks differ from EvaluatorPlan v0.3 required_validator_ids"
        )

    plan_digest = canonical_digest(plan)
    result["provenance"]["verifier_config_digest"] = plan_digest
    result.setdefault("extensions", {})["org.idkmesh.evaluator_plan.id"] = plan["id"]
    result["extensions"]["org.idkmesh.evaluator_plan.digest"] = plan_digest
    result["extensions"]["org.idkmesh.evaluator_plan.visibility"] = plan["visibility"]
    result["extensions"]["org.idkmesh.evaluator_plan.execution_mode"] = plan["execution_mode"]
    result["extensions"]["org.idkmesh.evaluator_plan.backend"] = backend_name(plan)
    result["extensions"]["org.idkmesh.evaluator_plan.runner_version"] = RUNNER_VERSION
    result["extensions"]["org.idkmesh.evaluator_plan.semantic_contract"] = (
        patch_verifier_v020.SEMANTIC_MODE
    )

    local_verifier.validate_schema(
        result, local_verifier.VERIFICATION_RESULT_SCHEMA, "VerificationResult"
    )
    validate_integrity(work_unit, worker_result, result)
    return result


def run_fixture(
    *,
    work_unit_path: Path,
    result_manifest_path: Path,
    candidate_root: Path,
    plan_path: Path,
) -> dict[str, Any]:
    return verify_with_plan(
        work_unit=local_verifier.load_json(work_unit_path),
        worker_result=local_verifier.load_json(result_manifest_path),
        plan=load_plan(plan_path),
        candidate_root=candidate_root,
        plan_path=plan_path,
    )


def cmd_verify(args: argparse.Namespace) -> int:
    work_unit_path = local_verifier.resolve_repo_path(args.work_unit)
    result_manifest_path = local_verifier.resolve_repo_path(args.result_manifest)
    candidate_root = local_verifier.resolve_repo_path(args.candidate_root)
    plan_path = local_verifier.resolve_repo_path(args.evaluator_plan)
    output_path = local_verifier.resolve_output_path(args.output)

    plan = load_plan(plan_path)
    if plan["policy"]["require_output_outside_candidate_root"]:
        base_runner.ensure_outside(output_path, candidate_root, "VerificationResult output")

    result = run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=result_manifest_path,
        candidate_root=candidate_root,
        plan_path=plan_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{result['status']}: wrote {output_path}; "
        f"recommendation={result['decision_support']['recommendation']} "
        f"evaluator_plan={plan['id']} semantic={patch_verifier_v020.SEMANTIC_MODE}"
    )
    return 0 if result["status"] == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-unit", required=True)
    parser.add_argument("--result-manifest", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--evaluator-plan", required=True)
    parser.add_argument(
        "--output",
        required=True,
        help="Repository-relative generated evidence path under results/.",
    )
    args = parser.parse_args()
    return cmd_verify(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        EvaluatorPlanV03Error,
        base_runner.EvaluatorPlanError,
        local_verifier.VerifierError,
        OSError,
        KeyError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
