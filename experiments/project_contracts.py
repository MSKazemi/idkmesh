#!/usr/bin/env python3
"""Validate IDKMesh ProjectManifest -> DomainPack -> Core contracts.

This module is intentionally configuration-only. Adapter references are stable
interface identifiers; validating a project never imports or executes an adapter,
worker, model, forge plugin, or project-supplied command.

v0.1 deliberately uses exact compatibility matching. Flexible semver-range
negotiation can be added later only after concrete compatibility evidence exists.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PROJECT_SCHEMA = ROOT / "schemas" / "project-manifest.schema.json"
DOMAIN_SCHEMA = ROOT / "schemas" / "domain-pack.schema.json"
SUPPORTED_CORE_API_VERSION = "0.1"
SUPPORTED_WORK_UNIT_SCHEMA_VERSION = "0.2"
DEFAULT_PROJECTS = (
    "examples/projects/idkmesh-self-improvement.project.json",
    "examples/projects/idkmesh-research-replication.project.json",
)
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class ProjectContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectContractError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectContractError(f"{path} must contain a JSON object")
    return value


def resolve_repo_path(raw: str) -> Path:
    candidate = (ROOT / raw).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ProjectContractError(f"path escapes repository root: {raw}") from exc
    return candidate


def _validator(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_schema(instance: dict[str, Any], schema_path: Path, label: str) -> None:
    errors = sorted(
        _validator(schema_path).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    lines = [f"{label} failed {len(errors)} schema check(s):"]
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        lines.append(f"  - {location}: {error.message}")
    raise ProjectContractError("\n".join(lines))


def _unique_index(items: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = str(item[key])
        if value in result:
            raise ProjectContractError(f"duplicate {label} id: {value}")
        result[value] = item
    return result


def _merge_named_definition(
    target: dict[str, dict[str, Any]],
    key: str,
    value: dict[str, Any],
    label: str,
) -> None:
    previous = target.get(key)
    if previous is None:
        target[key] = value
        return
    if previous != value:
        raise ProjectContractError(
            f"conflicting {label} definition for {key!r} across DomainPacks"
        )


def validate_domain_pack(pack: dict[str, Any], *, label: str = "DomainPack") -> dict[str, Any]:
    _validate_schema(pack, DOMAIN_SCHEMA, label)

    compatibility = pack["core_compatibility"]
    if compatibility["core_api_version"] != SUPPORTED_CORE_API_VERSION:
        raise ProjectContractError(
            f"{label} requires Core API {compatibility['core_api_version']!r}; "
            f"this validator supports exactly {SUPPORTED_CORE_API_VERSION!r}"
        )
    if compatibility["work_unit_schema_version"] != SUPPORTED_WORK_UNIT_SCHEMA_VERSION:
        raise ProjectContractError(
            f"{label} requires WorkUnit schema {compatibility['work_unit_schema_version']!r}; "
            f"this validator supports exactly {SUPPORTED_WORK_UNIT_SCHEMA_VERSION!r}"
        )

    work_kinds = _unique_index(pack["work_unit_kinds"], "kind", f"{label} Work Unit kind")
    policies = _unique_index(
        pack["verification_policies"], "id", f"{label} verification policy"
    )
    _unique_index(pack["worker_roles"], "id", f"{label} worker role")
    risks = _unique_index(pack["risk_classes"], "id", f"{label} risk class")
    adapter_defs = _unique_index(
        pack["adapters"]["definitions"], "id", f"{label} adapter"
    )

    for kind, definition in work_kinds.items():
        policy_ref = definition["required_verification_policy"]
        if policy_ref not in policies:
            raise ProjectContractError(
                f"{label} Work Unit kind {kind!r} references unknown verification policy {policy_ref!r}"
            )
        risk_ref = definition["default_risk_class"]
        if risk_ref not in risks:
            raise ProjectContractError(
                f"{label} Work Unit kind {kind!r} references unknown risk class {risk_ref!r}"
            )

    required = set(pack["adapters"]["required"])
    optional = set(pack["adapters"]["optional"])
    overlap = sorted(required & optional)
    if overlap:
        raise ProjectContractError(
            f"{label} adapters cannot be both required and optional: {', '.join(overlap)}"
        )
    unknown = sorted((required | optional) - set(adapter_defs))
    if unknown:
        raise ProjectContractError(
            f"{label} references undefined adapter(s): {', '.join(unknown)}"
        )

    return pack


def validate_project(project: dict[str, Any], *, label: str = "ProjectManifest") -> dict[str, Any]:
    _validate_schema(project, PROJECT_SCHEMA, label)

    compatibility = project["core_compatibility"]
    if compatibility["core_api_version"] != SUPPORTED_CORE_API_VERSION:
        raise ProjectContractError(
            f"{label} requires unsupported Core API {compatibility['core_api_version']!r}"
        )
    if compatibility["work_unit_schema_version"] != SUPPORTED_WORK_UNIT_SCHEMA_VERSION:
        raise ProjectContractError(
            f"{label} requires unsupported WorkUnit schema {compatibility['work_unit_schema_version']!r}"
        )

    pack_ids: set[str] = set()
    packs: list[dict[str, Any]] = []
    work_kinds: set[str] = set()
    policies: dict[str, dict[str, Any]] = {}
    risks: set[str] = set()
    adapters: dict[str, dict[str, Any]] = {}
    required_adapters: set[str] = set()

    for ref in project["domain_packs"]:
        if ref["id"] in pack_ids:
            raise ProjectContractError(f"{label} repeats DomainPack id {ref['id']!r}")
        pack_ids.add(ref["id"])

        path = resolve_repo_path(ref["path"])
        pack = validate_domain_pack(load_json(path), label=str(path.relative_to(ROOT)))
        if pack["id"] != ref["id"]:
            raise ProjectContractError(
                f"{label} DomainPack id mismatch: reference {ref['id']!r}, document {pack['id']!r}"
            )
        if pack["version"] != ref["version"]:
            raise ProjectContractError(
                f"{label} DomainPack version mismatch for {ref['id']!r}: "
                f"reference {ref['version']!r}, document {pack['version']!r}"
            )
        if pack["core_compatibility"] != compatibility:
            raise ProjectContractError(
                f"{label} and DomainPack {pack['id']!r} require different Core/WorkUnit versions"
            )
        packs.append(pack)

        for definition in pack["work_unit_kinds"]:
            work_kinds.add(definition["kind"])
        for policy in pack["verification_policies"]:
            _merge_named_definition(policies, policy["id"], policy, "verification policy")
        risks.update(definition["id"] for definition in pack["risk_classes"])
        for adapter in pack["adapters"]["definitions"]:
            _merge_named_definition(adapters, adapter["id"], adapter, "adapter")
        required_adapters.update(pack["adapters"]["required"])

    unsupported_kinds = sorted(set(project["allowed_work_unit_kinds"]) - work_kinds)
    if unsupported_kinds:
        raise ProjectContractError(
            f"{label} enables Work Unit kind(s) not supplied by its DomainPacks: "
            + ", ".join(unsupported_kinds)
        )

    default_policy_ref = project["verification"]["default_policy_ref"]
    default_policy = policies.get(default_policy_ref)
    if default_policy is None:
        raise ProjectContractError(
            f"{label} references unknown default verification policy {default_policy_ref!r}"
        )
    project_min = project["verification"]["minimum_independent_verifiers"]
    pack_min = default_policy["minimum_independent_verifiers"]
    if project_min < pack_min:
        raise ProjectContractError(
            f"{label} weakens {default_policy_ref!r}: minimum independent verifiers "
            f"{project_min} < DomainPack requirement {pack_min}"
        )
    if default_policy["human_integration_required"]:
        if not project["verification"]["human_integration_required"]:
            raise ProjectContractError(
                f"{label} weakens {default_policy_ref!r}: human integration is required by the DomainPack"
            )
        if not project["integration_policy"]["human_decision_required"]:
            raise ProjectContractError(
                f"{label} cannot disable the human integration decision required by {default_policy_ref!r}"
            )

    allowed_risks = set(project["risk_policy"]["allowed_risk_classes"])
    unknown_risks = sorted(allowed_risks - risks)
    if unknown_risks:
        raise ProjectContractError(
            f"{label} enables risk class(es) not supplied by its DomainPacks: "
            + ", ".join(unknown_risks)
        )
    max_autonomous = project["risk_policy"]["maximum_autonomous_risk"]
    if max_autonomous != "none" and max_autonomous not in allowed_risks:
        raise ProjectContractError(
            f"{label} maximum autonomous risk {max_autonomous!r} is not in allowed_risk_classes"
        )
    if max_autonomous != "none":
        max_rank = RISK_ORDER[max_autonomous]
        if not any(RISK_ORDER[risk] <= max_rank for risk in allowed_risks):
            raise ProjectContractError(f"{label} has no risk class eligible for its autonomous-risk bound")

    enabled_adapters = set(project["enabled_adapters"])
    unknown_adapters = sorted(enabled_adapters - set(adapters))
    if unknown_adapters:
        raise ProjectContractError(
            f"{label} enables undefined adapter(s): {', '.join(unknown_adapters)}"
        )
    missing_required = sorted(required_adapters - enabled_adapters)
    if missing_required:
        raise ProjectContractError(
            f"{label} omits DomainPack-required adapter(s): {', '.join(missing_required)}"
        )

    if (
        project["integration_policy"]["automatic_merge_allowed"]
        and project["integration_policy"]["human_decision_required"]
    ):
        raise ProjectContractError(
            f"{label} cannot require a human integration decision while also enabling automatic merge"
        )

    return project


def validate_project_path(raw_path: str) -> dict[str, Any]:
    path = resolve_repo_path(raw_path)
    project = load_json(path)
    return validate_project(project, label=str(path.relative_to(ROOT)))


def validate_repository_contracts(
    project_paths: Iterable[str] = DEFAULT_PROJECTS,
    *,
    require_reference_diversity: bool = True,
) -> list[dict[str, Any]]:
    paths = list(project_paths)
    projects = [validate_project_path(path) for path in paths]
    ids = [project["id"] for project in projects]
    if len(ids) != len(set(ids)):
        raise ProjectContractError("project set contains duplicate ProjectManifest ids")
    if require_reference_diversity and len(projects) < 2:
        raise ProjectContractError("reference contract validation requires at least two distinct projects")
    if require_reference_diversity:
        compatibilities = {
            json.dumps(project["core_compatibility"], sort_keys=True) for project in projects
        }
        if len(compatibilities) != 1:
            raise ProjectContractError(
                "reference projects must prove distinct project policy on one exact Core/WorkUnit contract"
            )
    return projects


def _expect_rejected(project: dict[str, Any], contains: str) -> None:
    try:
        validate_project(project, label="negative self-test")
    except ProjectContractError as exc:
        if contains not in str(exc):
            raise ProjectContractError(
                f"negative self-test failed for the wrong reason; expected {contains!r}, got: {exc}"
            ) from exc
        return
    raise ProjectContractError(f"unsafe negative fixture was accepted; expected rejection containing {contains!r}")


def self_test() -> None:
    base = load_json(resolve_repo_path(DEFAULT_PROJECTS[0]))

    bad = copy.deepcopy(base)
    bad["allowed_work_unit_kinds"].append("governance")
    _expect_rejected(bad, "not supplied by its DomainPacks")

    bad = copy.deepcopy(base)
    bad["enabled_adapters"].remove("software.metadata-verifier")
    _expect_rejected(bad, "omits DomainPack-required adapter")

    bad = copy.deepcopy(base)
    bad["core_compatibility"]["core_api_version"] = "9.9"
    _expect_rejected(bad, "unsupported Core API")

    bad = copy.deepcopy(base)
    bad["verification"]["minimum_independent_verifiers"] = 0
    _expect_rejected(bad, "minimum independent verifiers")

    bad = copy.deepcopy(base)
    bad["domain_packs"][0]["version"] = "0.2.0"
    _expect_rejected(bad, "DomainPack version mismatch")

    bad = copy.deepcopy(base)
    bad["domain_packs"][0]["path"] = "../../etc/passwd"
    _expect_rejected(bad, "path escapes repository root")

    projects = validate_repository_contracts()
    if projects[0]["id"] == projects[1]["id"]:
        raise ProjectContractError("reference projects are not distinct")
    if projects[0]["allowed_work_unit_kinds"] == projects[1]["allowed_work_unit_kinds"]:
        raise ProjectContractError("reference projects do not demonstrate policy specialization")


def cmd_validate(args: argparse.Namespace) -> int:
    paths = tuple(args.projects) if args.projects else DEFAULT_PROJECTS
    projects = validate_repository_contracts(
        paths, require_reference_diversity=not bool(args.projects)
    )
    print(
        "OK: ProjectManifest/DomainPack contracts valid for "
        + ", ".join(project["id"] for project in projects)
        + f" on Core API {SUPPORTED_CORE_API_VERSION} / WorkUnit {SUPPORTED_WORK_UNIT_SCHEMA_VERSION}"
    )
    return 0


def cmd_self_test(_: argparse.Namespace) -> int:
    self_test()
    print("OK: ProjectManifest/DomainPack fail-closed composition self-tests passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate project/domain contracts")
    validate.add_argument("projects", nargs="*", help="Optional ProjectManifest paths")
    validate.set_defaults(func=cmd_validate)

    test = sub.add_parser("self-test", help="Run deterministic negative composition tests")
    test.set_defaults(func=cmd_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except ProjectContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
