#!/usr/bin/env python3
"""Run canonical IDKMesh verifier backends through a bound EvaluatorPlan.

This is a guard/control layer, not a second verifier implementation. It binds
verifier-owned deterministic policy to an exact WorkUnit and source revision,
checks exact required-validator coverage, then delegates candidate evaluation to
the versioned verifier adapters under ``experiments/``.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import local_verifier
import substring_patch_verifier
import transformation_patch_verifier
from provenance_integrity import canonical_digest, validate_integrity

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PLAN_SCHEMAS = {
    "0.1": ROOT / "schemas" / "evaluator-plan-v0.1.schema.json",
    "0.2": ROOT / "schemas" / "evaluator-plan-v0.2.schema.json",
    "0.3": ROOT / "schemas" / "evaluator-plan-v0.3.schema.json",
    "0.4": ROOT / "schemas" / "evaluator-plan-v0.4.schema.json",
}
RUNNER_VERSION = "0.4"
JSON_VALIDATOR_IDS = {
    "artifact-digest",
    "candidate-scope",
    "independent-acceptance",
}
PATCH_VALIDATOR_IDS = {
    "result-manifest-schema",
    "independent-review",
}


class EvaluatorPlanError(RuntimeError):
    """Raised when evaluator control data is invalid or not independent."""


def ensure_outside(candidate: Path, boundary: Path, label: str) -> None:
    candidate_resolved = candidate.resolve()
    boundary_resolved = boundary.resolve()
    try:
        candidate_resolved.relative_to(boundary_resolved)
    except ValueError:
        return
    raise EvaluatorPlanError(f"{label} must remain outside the candidate workspace")


def load_plan(path: Path) -> dict[str, Any]:
    plan = local_verifier.load_json(path)
    version = plan.get("schema_version")
    schema = EVALUATOR_PLAN_SCHEMAS.get(str(version))
    if schema is None:
        raise EvaluatorPlanError(f"unsupported EvaluatorPlan schema_version: {version!r}")
    local_verifier.validate_schema(plan, schema, f"EvaluatorPlan v{version}")
    return plan


def required_work_unit_validators(work_unit: dict[str, Any]) -> set[str]:
    return {
        item["id"]
        for item in work_unit["validators"]
        if item.get("required") is True
    }


def backend_name(plan: dict[str, Any]) -> str:
    if plan["schema_version"] == "0.1":
        return "json_exact"
    if plan["schema_version"] == "0.2" and plan.get("backend", {}).get("type") == "unified_diff":
        return "unified_diff"
    if plan["schema_version"] == "0.3" and plan.get("backend", {}).get("type") == "unified_diff":
        return "unified_diff_substring"
    if plan["schema_version"] == "0.4" and plan.get("backend", {}).get("type") == "unified_diff":
        return "unified_diff_transform"
    raise EvaluatorPlanError("EvaluatorPlan does not select a supported verifier backend")


def supported_validator_ids(plan: dict[str, Any]) -> set[str]:
    backend = backend_name(plan)
    if backend == "json_exact":
        return set(JSON_VALIDATOR_IDS)
    if backend in {"unified_diff", "unified_diff_substring", "unified_diff_transform"}:
        return set(PATCH_VALIDATOR_IDS)
    raise EvaluatorPlanError(f"unsupported evaluator backend: {backend}")


def operational_policy(plan: dict[str, Any]) -> dict[str, Any]:
    """Translate a bound EvaluatorPlan into the canonical verifier backend policy."""

    backend = backend_name(plan)
    if backend == "json_exact":
        return {
            "schema_version": "0.1",
            "id": plan["id"],
            "candidate_artifact_id": plan["candidate_artifact_id"],
            "allowed_files": plan["allowed_files"],
            "max_candidate_bytes": plan["max_candidate_bytes"],
            "required_json": plan["required_json"],
        }
    if backend == "unified_diff":
        return {
            "schema_version": "0.2",
            "id": plan["id"],
            "candidate_artifact_id": plan["candidate_artifact_id"],
            "backend": copy.deepcopy(plan["backend"]),
        }
    if backend == "unified_diff_substring":
        return {
            "schema_version": "0.3",
            "id": plan["id"],
            "candidate_artifact_id": plan["candidate_artifact_id"],
            "backend": copy.deepcopy(plan["backend"]),
        }
    if backend == "unified_diff_transform":
        return {
            "schema_version": "0.4",
            "id": plan["id"],
            "candidate_artifact_id": plan["candidate_artifact_id"],
            "backend": copy.deepcopy(plan["backend"]),
        }
    raise EvaluatorPlanError(f"unsupported evaluator backend: {backend}")


def validate_plan_binding(
    *,
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    plan: dict[str, Any],
    plan_path: Path,
    candidate_root: Path,
) -> None:
    local_verifier.validate_schema(work_unit, local_verifier.WORK_UNIT_SCHEMA, "Work Unit")
    local_verifier.validate_schema(
        worker_result,
        local_verifier.RESULT_MANIFEST_SCHEMA,
        "ResultManifest",
    )
    version = str(plan.get("schema_version"))
    schema = EVALUATOR_PLAN_SCHEMAS.get(version)
    if schema is None:
        raise EvaluatorPlanError(f"unsupported EvaluatorPlan schema_version: {version!r}")
    local_verifier.validate_schema(plan, schema, f"EvaluatorPlan v{version}")

    binding = plan["binding"]
    if binding["work_unit_id"] != work_unit["id"]:
        raise EvaluatorPlanError("EvaluatorPlan is bound to a different WorkUnit id")
    if binding["work_unit_version"] != work_unit["version"]:
        raise EvaluatorPlanError("EvaluatorPlan is bound to a different WorkUnit version")

    observed_work_unit_digest = canonical_digest(work_unit)
    if binding["work_unit_digest"] != observed_work_unit_digest:
        raise EvaluatorPlanError(
            "EvaluatorPlan WorkUnit digest binding does not match canonical WorkUnit content"
        )

    expected_revision = binding["source_revision"]
    work_unit_revision = work_unit.get("provenance", {}).get("source_revision")
    if work_unit_revision is not None and work_unit_revision != expected_revision:
        raise EvaluatorPlanError(
            "EvaluatorPlan source revision differs from WorkUnit provenance"
        )
    if worker_result["provenance"]["source_revision"] != expected_revision:
        raise EvaluatorPlanError(
            "EvaluatorPlan source revision differs from ResultManifest provenance"
        )

    required_ids = required_work_unit_validators(work_unit)
    plan_ids = set(plan["required_validator_ids"])
    if plan_ids != required_ids:
        missing = sorted(required_ids - plan_ids)
        extra = sorted(plan_ids - required_ids)
        raise EvaluatorPlanError(
            "EvaluatorPlan validator coverage must exactly match required WorkUnit validators; "
            f"missing={missing}, extra={extra}"
        )

    supported = supported_validator_ids(plan)
    if plan_ids != supported:
        missing = sorted(plan_ids - supported)
        extra = sorted(supported - plan_ids)
        raise EvaluatorPlanError(
            "selected evaluator backend does not exactly implement the bound required validators; "
            f"unsupported_required={missing}, backend_extra={extra}"
        )

    requested_ids = set(worker_result["verification_request"]["expected_validator_ids"])
    if not required_ids.issubset(requested_ids):
        raise EvaluatorPlanError(
            "ResultManifest verification request omits required WorkUnit validators: "
            + ", ".join(sorted(required_ids - requested_ids))
        )

    if plan["policy"]["require_verifier_distinct_from_worker"]:
        if plan["verifier"]["id"] == worker_result["worker"]["id"]:
            raise EvaluatorPlanError("EvaluatorPlan verifier id collides with worker id")

    if plan["policy"]["require_plan_outside_candidate_root"]:
        ensure_outside(plan_path, candidate_root, "EvaluatorPlan")


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

    policy = operational_policy(plan)
    backend = backend_name(plan)
    if backend == "json_exact":
        result = local_verifier.verify_candidate(
            work_unit=work_unit,
            worker_result=worker_result,
            policy=policy,
            candidate_root=candidate_root,
            policy_path=plan_path,
        )
    elif backend == "unified_diff":
        result = local_verifier.verify_patch_candidate(
            work_unit=work_unit,
            worker_result=worker_result,
            policy=policy,
            candidate_root=candidate_root,
            policy_path=plan_path,
        )
    elif backend == "unified_diff_substring":
        result = substring_patch_verifier.verify_patch_candidate(
            work_unit=work_unit,
            worker_result=worker_result,
            policy=policy,
            candidate_root=candidate_root,
            policy_path=plan_path,
        )
    elif backend == "unified_diff_transform":
        result = transformation_patch_verifier.verify_patch_candidate(
            work_unit=work_unit,
            worker_result=worker_result,
            policy=policy,
            candidate_root=candidate_root,
            policy_path=plan_path,
        )
    else:
        raise EvaluatorPlanError(f"unsupported evaluator backend: {backend}")

    if result["verifier"] != plan["verifier"]:
        raise EvaluatorPlanError(
            "underlying verifier identity/version differs from the bound EvaluatorPlan"
        )

    result_check_ids = {
        check["id"] for check in result["checks"] if check.get("required") is True
    }
    if result_check_ids != set(plan["required_validator_ids"]):
        raise EvaluatorPlanError(
            "VerificationResult required checks differ from EvaluatorPlan required_validator_ids"
        )

    plan_digest = canonical_digest(plan)
    result["provenance"]["verifier_config_digest"] = plan_digest
    result.setdefault("extensions", {})["org.idkmesh.evaluator_plan.id"] = plan["id"]
    result["extensions"]["org.idkmesh.evaluator_plan.digest"] = plan_digest
    result["extensions"]["org.idkmesh.evaluator_plan.visibility"] = plan["visibility"]
    result["extensions"]["org.idkmesh.evaluator_plan.execution_mode"] = plan["execution_mode"]
    result["extensions"]["org.idkmesh.evaluator_plan.backend"] = backend
    result["extensions"]["org.idkmesh.evaluator_plan.runner_version"] = RUNNER_VERSION

    local_verifier.validate_schema(
        result,
        local_verifier.VERIFICATION_RESULT_SCHEMA,
        "VerificationResult",
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


def expect_plan_error(label: str, func: Any) -> None:
    try:
        func()
    except (EvaluatorPlanError, local_verifier.VerifierError):
        return
    raise EvaluatorPlanError(f"self-test expected {label} to fail closed")


def cmd_verify(args: argparse.Namespace) -> int:
    work_unit_path = local_verifier.resolve_repo_path(args.work_unit)
    result_manifest_path = local_verifier.resolve_repo_path(args.result_manifest)
    candidate_root = local_verifier.resolve_repo_path(args.candidate_root)
    plan_path = local_verifier.resolve_repo_path(args.evaluator_plan)
    output_path = local_verifier.resolve_output_path(args.output)

    plan = load_plan(plan_path)
    if plan["policy"]["require_output_outside_candidate_root"]:
        ensure_outside(output_path, candidate_root, "VerificationResult output")

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
        f"evaluator_plan={plan['id']} backend={backend_name(plan)}"
    )
    return 0 if result["status"] == "passed" else 1


def cmd_self_test(args: argparse.Namespace) -> int:
    work_unit_path = local_verifier.resolve_repo_path(args.work_unit)
    plan_path = local_verifier.resolve_repo_path(args.evaluator_plan)
    good_result_path = local_verifier.resolve_repo_path(args.good_result_manifest)
    good_candidate_root = local_verifier.resolve_repo_path(args.good_candidate_root)
    bad_result_path = local_verifier.resolve_repo_path(args.bad_result_manifest)
    bad_candidate_root = local_verifier.resolve_repo_path(args.bad_candidate_root)

    expect_plan_error(
        "canonical repository verification output",
        lambda: local_verifier.resolve_output_path("README.md"),
    )
    allowed_output = local_verifier.resolve_output_path(
        "results/verification/evaluator-plan-self-test.json"
    )
    if allowed_output.relative_to(ROOT).parts[0] != "results":
        raise EvaluatorPlanError("results/ output path guard rejected its own invariant")

    work_unit = local_verifier.load_json(work_unit_path)
    plan = load_plan(plan_path)
    good_worker = local_verifier.load_json(good_result_path)
    bad_worker = local_verifier.load_json(bad_result_path)

    good = verify_with_plan(
        work_unit=work_unit,
        worker_result=good_worker,
        plan=plan,
        candidate_root=good_candidate_root,
        plan_path=plan_path,
    )
    bad = verify_with_plan(
        work_unit=work_unit,
        worker_result=bad_worker,
        plan=plan,
        candidate_root=bad_candidate_root,
        plan_path=plan_path,
    )
    if good["status"] != "passed":
        raise EvaluatorPlanError("known-good bound evaluator fixture did not pass")
    if bad["status"] != "failed":
        raise EvaluatorPlanError("known-bad bound evaluator fixture did not fail")
    if good["provenance"]["verifier_config_digest"] != canonical_digest(plan):
        raise EvaluatorPlanError("VerificationResult did not preserve the full EvaluatorPlan digest")

    wrong_digest = copy.deepcopy(plan)
    wrong_digest["binding"]["work_unit_digest"] = "sha256:" + "0" * 64
    expect_plan_error(
        "wrong WorkUnit digest binding",
        lambda: verify_with_plan(
            work_unit=work_unit,
            worker_result=good_worker,
            plan=wrong_digest,
            candidate_root=good_candidate_root,
            plan_path=plan_path,
        ),
    )

    wrong_revision = copy.deepcopy(plan)
    wrong_revision["binding"]["source_revision"] = "wrong-revision"
    expect_plan_error(
        "wrong source revision binding",
        lambda: verify_with_plan(
            work_unit=work_unit,
            worker_result=good_worker,
            plan=wrong_revision,
            candidate_root=good_candidate_root,
            plan_path=plan_path,
        ),
    )

    missing_validator = copy.deepcopy(plan)
    missing_validator["required_validator_ids"] = missing_validator["required_validator_ids"][:-1]
    expect_plan_error(
        "incomplete validator coverage",
        lambda: verify_with_plan(
            work_unit=work_unit,
            worker_result=good_worker,
            plan=missing_validator,
            candidate_root=good_candidate_root,
            plan_path=plan_path,
        ),
    )

    colliding_worker = copy.deepcopy(good_worker)
    colliding_worker["worker"]["id"] = plan["verifier"]["id"]
    expect_plan_error(
        "worker/verifier identity collision",
        lambda: verify_with_plan(
            work_unit=work_unit,
            worker_result=colliding_worker,
            plan=plan,
            candidate_root=good_candidate_root,
            plan_path=plan_path,
        ),
    )

    with tempfile.TemporaryDirectory(prefix="idkmesh-evaluator-plan-") as raw:
        temp_root = Path(raw)
        temp_candidate = temp_root / "candidate"
        shutil.copytree(good_candidate_root, temp_candidate)
        candidate_owned_plan = temp_candidate / "evaluator-plan.json"
        candidate_owned_plan.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        expect_plan_error(
            "candidate-owned evaluator plan",
            lambda: verify_with_plan(
                work_unit=work_unit,
                worker_result=good_worker,
                plan=plan,
                candidate_root=temp_candidate,
                plan_path=candidate_owned_plan,
            ),
        )
        expect_plan_error(
            "verification output inside candidate workspace",
            lambda: ensure_outside(
                temp_candidate / "verification-result.json",
                temp_candidate,
                "VerificationResult output",
            ),
        )

    print(
        "OK: bound EvaluatorPlan v0.1 accepts/rejects JSON fixtures and fails closed on "
        "WorkUnit digest drift, source-revision drift, validator-coverage loss, identity collision, "
        "candidate-owned evaluator control, candidate-local output, and canonical output targets"
    )
    return 0


def cmd_patch_self_test(args: argparse.Namespace) -> int:
    work_unit_path = local_verifier.resolve_repo_path(args.work_unit)
    plan_path = local_verifier.resolve_repo_path(args.evaluator_plan)
    work_unit = local_verifier.load_json(work_unit_path)
    plan = load_plan(plan_path)

    good_root = local_verifier.resolve_repo_path(args.good_candidate_root)
    wrong_root = local_verifier.resolve_repo_path(args.wrong_candidate_root)
    forbidden_root = local_verifier.resolve_repo_path(args.forbidden_candidate_root)
    good_worker = local_verifier.load_json(good_root / "result-manifest.json")
    wrong_worker = local_verifier.load_json(wrong_root / "result-manifest.json")
    forbidden_worker = local_verifier.load_json(forbidden_root / "result-manifest.json")

    good = verify_with_plan(
        work_unit=work_unit,
        worker_result=good_worker,
        plan=plan,
        candidate_root=good_root,
        plan_path=plan_path,
    )
    wrong = verify_with_plan(
        work_unit=work_unit,
        worker_result=wrong_worker,
        plan=plan,
        candidate_root=wrong_root,
        plan_path=plan_path,
    )
    forbidden = verify_with_plan(
        work_unit=work_unit,
        worker_result=forbidden_worker,
        plan=plan,
        candidate_root=forbidden_root,
        plan_path=plan_path,
    )

    if good["status"] != "passed" or good["decision_support"]["recommendation"] != "accept_candidate":
        raise EvaluatorPlanError("known-good patch fixture was not supported")
    expected_checks = {"result-manifest-schema", "independent-review"}
    if {check["id"] for check in good["checks"] if check["required"]} != expected_checks:
        raise EvaluatorPlanError("patch VerificationResult does not preserve WorkUnit validator ids")
    if wrong["status"] != "failed" or wrong["decision_support"]["recommendation"] != "reject_candidate":
        raise EvaluatorPlanError("scope-valid semantically wrong patch was not rejected")
    if any(finding["category"] == "scope" for finding in wrong["findings"]):
        raise EvaluatorPlanError("wrong-semantic fixture should fail semantics without a scope violation")
    if forbidden["status"] != "failed" or not any(
        finding["category"] == "scope" for finding in forbidden["findings"]
    ):
        raise EvaluatorPlanError("forbidden-path patch was not independently rejected for scope")

    forged = copy.deepcopy(good_worker)
    forged["produced_artifacts"][0]["digest"] = "sha256:" + "0" * 64
    forged_result = verify_with_plan(
        work_unit=work_unit,
        worker_result=forged,
        plan=plan,
        candidate_root=good_root,
        plan_path=plan_path,
    )
    if forged_result["status"] != "failed" or not any(
        finding["category"] == "provenance" for finding in forged_result["findings"]
    ):
        raise EvaluatorPlanError("forged patch digest was not independently rejected")

    wrong_binding = copy.deepcopy(plan)
    wrong_binding["binding"]["work_unit_digest"] = "sha256:" + "0" * 64
    expect_plan_error(
        "patch EvaluatorPlan binding drift",
        lambda: verify_with_plan(
            work_unit=work_unit,
            worker_result=good_worker,
            plan=wrong_binding,
            candidate_root=good_root,
            plan_path=plan_path,
        ),
    )

    print(
        "OK: EvaluatorPlan v0.2 patch backend independently supports a good patch, rejects a "
        "scope-valid semantic failure, rejects forbidden-path and forged-digest candidates, "
        "preserves exact WorkUnit validator ids, and fails closed on binding drift"
    )
    return 0


def cmd_semantic_version_self_test(args: argparse.Namespace) -> int:
    """Prove v0.2 exact-line and v0.3 substring semantics differ by version only."""

    work_unit_path = local_verifier.resolve_repo_path(args.work_unit)
    candidate_root = local_verifier.resolve_repo_path(args.candidate_root)
    worker_path = candidate_root / "result-manifest.json"
    legacy_plan_path = local_verifier.resolve_repo_path(args.legacy_evaluator_plan)
    substring_plan_path = local_verifier.resolve_repo_path(args.substring_evaluator_plan)

    work_unit = local_verifier.load_json(work_unit_path)
    worker = local_verifier.load_json(worker_path)
    legacy_plan = load_plan(legacy_plan_path)
    substring_plan = load_plan(substring_plan_path)

    if legacy_plan["schema_version"] != "0.2":
        raise EvaluatorPlanError("legacy semantic contrast plan is not EvaluatorPlan v0.2")
    if substring_plan["schema_version"] != "0.3":
        raise EvaluatorPlanError("substring semantic contrast plan is not EvaluatorPlan v0.3")

    legacy = verify_with_plan(
        work_unit=work_unit,
        worker_result=worker,
        plan=legacy_plan,
        candidate_root=candidate_root,
        plan_path=legacy_plan_path,
    )
    substring = verify_with_plan(
        work_unit=work_unit,
        worker_result=worker,
        plan=substring_plan,
        candidate_root=candidate_root,
        plan_path=substring_plan_path,
    )

    if legacy["status"] != "failed" or legacy["decision_support"]["recommendation"] != "reject_candidate":
        raise EvaluatorPlanError(
            "EvaluatorPlan v0.2 fragment contrast must fail under unchanged exact added-line semantics"
        )
    if not any(finding["category"] == "correctness" for finding in legacy["findings"]):
        raise EvaluatorPlanError("legacy exact-line contrast failure lacks correctness evidence")
    if legacy["verifier"]["adapter_version"] != "0.1.1":
        raise EvaluatorPlanError("legacy v0.2 plan did not preserve patch verifier v0.1.1")

    if substring["status"] != "passed" or substring["decision_support"]["recommendation"] != "accept_candidate":
        raise EvaluatorPlanError(
            "EvaluatorPlan v0.3 fragment contrast must pass under explicit added-line substring semantics"
        )
    if substring["verifier"]["adapter_version"] != "0.2.0":
        raise EvaluatorPlanError("v0.3 plan did not select patch verifier v0.2.0")
    if substring.get("extensions", {}).get(
        "org.idkmesh.local_verifier.semantic_match_mode"
    ) != "added_line_substring_all":
        raise EvaluatorPlanError("v0.3 VerificationResult omitted explicit semantic match mode")
    if not any(
        evidence["id"] == "added-substring-semantic-observation"
        for evidence in substring["evidence"]
    ):
        raise EvaluatorPlanError("v0.3 VerificationResult omitted substring semantic evidence")

    def evidence_digest(result: dict[str, Any], evidence_id: str) -> str:
        matches = [
            evidence["digest"] for evidence in result["evidence"] if evidence["id"] == evidence_id
        ]
        if len(matches) != 1:
            raise EvaluatorPlanError(f"expected one {evidence_id} evidence item")
        return matches[0]

    legacy_patch_digest = evidence_digest(legacy, "candidate-patch-hash")
    substring_patch_digest = evidence_digest(substring, "candidate-patch-hash")
    if legacy_patch_digest != substring_patch_digest:
        raise EvaluatorPlanError("semantic contrast did not evaluate the same candidate patch bytes")

    if legacy["provenance"]["verifier_config_digest"] != canonical_digest(legacy_plan):
        raise EvaluatorPlanError("legacy VerificationResult did not bind exact v0.2 plan digest")
    if substring["provenance"]["verifier_config_digest"] != canonical_digest(substring_plan):
        raise EvaluatorPlanError("substring VerificationResult did not bind exact v0.3 plan digest")

    print(
        "OK: the same patch and fragment fail under EvaluatorPlan v0.2 / verifier v0.1.1 "
        "exact-line semantics and pass under EvaluatorPlan v0.3 / verifier v0.2.0 explicit "
        "single-added-line substring semantics; both results retain exact plan provenance"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Run a canonical verifier backend through a bound EvaluatorPlan.")
    verify.add_argument("--work-unit", required=True)
    verify.add_argument("--result-manifest", required=True)
    verify.add_argument("--candidate-root", required=True)
    verify.add_argument("--evaluator-plan", required=True)
    verify.add_argument("--output", required=True, help="Repository-relative generated evidence path under results/.")
    verify.set_defaults(func=cmd_verify)

    self_test = sub.add_parser("self-test", help="Run deterministic EvaluatorPlan v0.1 JSON binding safety tests.")
    self_test.add_argument("--work-unit", default="examples/work-units/local-verifier-smoke.work-unit.json")
    self_test.add_argument("--evaluator-plan", default="verification/fixtures/verifier-smoke-evaluator-plan.json")
    self_test.add_argument("--good-result-manifest", default="examples/verifier/good/result-manifest.json")
    self_test.add_argument("--good-candidate-root", default="examples/verifier/good/candidate-root")
    self_test.add_argument("--bad-result-manifest", default="examples/verifier/bad/result-manifest.json")
    self_test.add_argument("--bad-candidate-root", default="examples/verifier/bad/candidate-root")
    self_test.set_defaults(func=cmd_self_test)

    patch_test = sub.add_parser("patch-self-test", help="Run EvaluatorPlan v0.2 unified-diff backend safety tests.")
    patch_test.add_argument("--work-unit", default="examples/work-units/patch-verifier-smoke.work-unit.json")
    patch_test.add_argument("--evaluator-plan", default="verification/fixtures/patch-smoke-evaluator-plan-v0.2.json")
    patch_test.add_argument("--good-candidate-root", default="examples/verifier/patch/good")
    patch_test.add_argument("--wrong-candidate-root", default="examples/verifier/patch/wrong-semantic")
    patch_test.add_argument("--forbidden-candidate-root", default="examples/verifier/patch/forbidden")
    patch_test.set_defaults(func=cmd_patch_self_test)

    semantic_test = sub.add_parser(
        "semantic-version-self-test",
        help="Prove v0.2 exact-line behavior remains unchanged while v0.3 adds explicit substring semantics.",
    )
    semantic_test.add_argument("--work-unit", default="examples/work-units/patch-verifier-smoke.work-unit.json")
    semantic_test.add_argument("--candidate-root", default="examples/verifier/patch/good")
    semantic_test.add_argument(
        "--legacy-evaluator-plan",
        default="verification/fixtures/patch-fragment-exact-evaluator-plan-v0.2.json",
    )
    semantic_test.add_argument(
        "--substring-evaluator-plan",
        default="verification/fixtures/patch-fragment-substring-evaluator-plan-v0.3.json",
    )
    semantic_test.set_defaults(func=cmd_semantic_version_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (
        EvaluatorPlanError,
        local_verifier.VerifierError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
