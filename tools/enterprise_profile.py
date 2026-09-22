#!/usr/bin/env python3
"""Deterministic declaration preflight for EnterpriseControlProfile v0.1.

This tool checks structural fields and cross-field enterprise invariants using
only the Python standard library. It does not inspect live GitHub/cloud state,
provision controls, or claim compliance/certification.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping

API_VERSION = "idkmesh.io/v1alpha1"
KIND = "EnterpriseControlProfile"
STATUSES = ("PASS", "WARN", "FAIL")

TOP_LEVEL_FIELDS = {
    "api_version",
    "kind",
    "metadata",
    "deployment",
    "identity",
    "data",
    "secrets",
    "audit",
    "reliability",
    "supply_chain",
    "change_management",
}

REQUIRED_FIELDS = {
    "metadata": {"name", "environment", "enforcement_mode"},
    "deployment": {"profile", "tenant_mode", "tenant_isolation", "network_mode"},
    "identity": {
        "human_identity_source",
        "service_identity",
        "mfa_required",
        "high_risk_separation_of_duties",
    },
    "data": {
        "default_classification",
        "external_processing_allowed_classes",
        "egress_mode",
    },
    "secrets": {
        "backend",
        "workload_identity",
        "long_lived_cloud_keys_allowed",
    },
    "audit": {
        "append_only",
        "integrity",
        "retention_days",
        "external_export_required",
        "actor_policy_revision_required",
    },
    "reliability": {
        "availability_target_percent",
        "rpo_minutes",
        "rto_minutes",
        "restore_test_interval_days",
        "backpressure_required",
    },
    "supply_chain": {
        "immutable_action_pins_required",
        "sbom_required",
        "provenance_attestation_required",
        "vulnerability_response_sla_hours",
    },
    "change_management": {"high_risk_two_person_rule", "break_glass"},
}

ENUMS = {
    ("metadata", "environment"): {"development", "staging", "production"},
    ("metadata", "enforcement_mode"): {"audit", "enforce"},
    ("deployment", "profile"): {"G0", "G1", "G2", "G3"},
    ("deployment", "tenant_mode"): {
        "single_project",
        "single_organization",
        "multi_tenant",
    },
    ("deployment", "tenant_isolation"): {
        "not_applicable",
        "declared",
        "enforced",
    },
    ("deployment", "network_mode"): {
        "public",
        "controlled_egress",
        "private_network",
    },
    ("identity", "human_identity_source"): {
        "github",
        "enterprise_sso",
        "oidc",
        "saml",
    },
    ("identity", "service_identity"): {
        "github_actions",
        "github_app",
        "oidc_workload",
        "managed_identity",
    },
    ("data", "default_classification"): {
        "public",
        "internal",
        "confidential",
        "restricted",
    },
    ("data", "egress_mode"): {"unrestricted", "allowlist", "deny_by_default"},
    ("secrets", "backend"): {
        "github_environment",
        "external_secret_manager",
        "provider_managed",
    },
    ("secrets", "workload_identity"): {
        "none",
        "github_oidc",
        "external_oidc",
        "managed_identity",
    },
    ("audit", "integrity"): {"git_history", "hash_chain", "external_worm"},
}

DATA_CLASSES = {"public", "internal", "confidential", "restricted"}
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
BREAK_GLASS_FIELDS = {
    "enabled",
    "time_bound_minutes",
    "reason_required",
    "audit_required",
}


class EnterpriseProfileError(ValueError):
    """Profile cannot be parsed or structurally inspected."""


@dataclass(frozen=True)
class Finding:
    status: str
    code: str
    message: str

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid finding status: {self.status}")

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "code": self.code,
            "message": self.message,
        }


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EnterpriseProfileError(f"{path} must be an object")
    return value


def _bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise EnterpriseProfileError(f"{path} must be a boolean")
    return value


def _int(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EnterpriseProfileError(
            f"{path} must be an integer >= {minimum}"
        )
    return value


def _number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EnterpriseProfileError(f"{path} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise EnterpriseProfileError(f"{path} must be finite")
    if result < minimum or result > maximum:
        raise EnterpriseProfileError(
            f"{path} must be between {minimum} and {maximum}"
        )
    return result


def _enum(section: str, field: str, value: Any) -> str:
    allowed = ENUMS[(section, field)]
    if not isinstance(value, str) or value not in allowed:
        raise EnterpriseProfileError(
            f"{section}.{field} must be one of: {', '.join(sorted(allowed))}"
        )
    return value


def validate_structure(profile: Any) -> dict[str, Mapping[str, Any]]:
    root = _mapping(profile, "$")
    unknown = sorted(set(root) - TOP_LEVEL_FIELDS)
    if unknown:
        raise EnterpriseProfileError(
            "unknown top-level field(s): " + ", ".join(unknown)
        )

    if root.get("api_version") != API_VERSION:
        raise EnterpriseProfileError(
            f"api_version must equal {API_VERSION}"
        )
    if root.get("kind") != KIND:
        raise EnterpriseProfileError(f"kind must equal {KIND}")

    sections: dict[str, Mapping[str, Any]] = {}
    for section, required in REQUIRED_FIELDS.items():
        value = _mapping(root.get(section), section)
        missing = sorted(required - set(value))
        if missing:
            raise EnterpriseProfileError(
                f"{section} missing required field(s): {', '.join(missing)}"
            )
        unknown_section = sorted(set(value) - required)
        if unknown_section:
            raise EnterpriseProfileError(
                f"{section} has unknown field(s): {', '.join(unknown_section)}"
            )
        sections[section] = value

    metadata = sections["metadata"]
    if (
        not isinstance(metadata["name"], str)
        or NAME_RE.fullmatch(metadata["name"]) is None
    ):
        raise EnterpriseProfileError(
            "metadata.name must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        )
    _enum("metadata", "environment", metadata["environment"])
    _enum("metadata", "enforcement_mode", metadata["enforcement_mode"])

    deployment = sections["deployment"]
    for field in ("profile", "tenant_mode", "tenant_isolation", "network_mode"):
        _enum("deployment", field, deployment[field])

    identity = sections["identity"]
    _enum("identity", "human_identity_source", identity["human_identity_source"])
    _enum("identity", "service_identity", identity["service_identity"])
    _bool(identity["mfa_required"], "identity.mfa_required")
    _bool(
        identity["high_risk_separation_of_duties"],
        "identity.high_risk_separation_of_duties",
    )

    data = sections["data"]
    _enum("data", "default_classification", data["default_classification"])
    _enum("data", "egress_mode", data["egress_mode"])
    classes = data["external_processing_allowed_classes"]
    if not isinstance(classes, list):
        raise EnterpriseProfileError(
            "data.external_processing_allowed_classes must be an array"
        )
    if any(not isinstance(item, str) for item in classes):
        raise EnterpriseProfileError(
            "data.external_processing_allowed_classes must contain strings"
        )
    if len(classes) != len(set(classes)):
        raise EnterpriseProfileError(
            "data.external_processing_allowed_classes contains duplicates"
        )
    unknown_classes = sorted(set(classes) - DATA_CLASSES)
    if unknown_classes:
        raise EnterpriseProfileError(
            "unknown data class(es): " + ", ".join(unknown_classes)
        )

    secrets = sections["secrets"]
    _enum("secrets", "backend", secrets["backend"])
    _enum("secrets", "workload_identity", secrets["workload_identity"])
    _bool(
        secrets["long_lived_cloud_keys_allowed"],
        "secrets.long_lived_cloud_keys_allowed",
    )

    audit = sections["audit"]
    _bool(audit["append_only"], "audit.append_only")
    _enum("audit", "integrity", audit["integrity"])
    _int(audit["retention_days"], "audit.retention_days", minimum=1)
    _bool(audit["external_export_required"], "audit.external_export_required")
    _bool(
        audit["actor_policy_revision_required"],
        "audit.actor_policy_revision_required",
    )

    reliability = sections["reliability"]
    _number(
        reliability["availability_target_percent"],
        "reliability.availability_target_percent",
        minimum=0,
        maximum=100,
    )
    _int(reliability["rpo_minutes"], "reliability.rpo_minutes")
    _int(reliability["rto_minutes"], "reliability.rto_minutes")
    _int(
        reliability["restore_test_interval_days"],
        "reliability.restore_test_interval_days",
        minimum=1,
    )
    _bool(
        reliability["backpressure_required"],
        "reliability.backpressure_required",
    )

    supply = sections["supply_chain"]
    _bool(
        supply["immutable_action_pins_required"],
        "supply_chain.immutable_action_pins_required",
    )
    _bool(supply["sbom_required"], "supply_chain.sbom_required")
    _bool(
        supply["provenance_attestation_required"],
        "supply_chain.provenance_attestation_required",
    )
    _int(
        supply["vulnerability_response_sla_hours"],
        "supply_chain.vulnerability_response_sla_hours",
        minimum=1,
    )

    change = sections["change_management"]
    _bool(
        change["high_risk_two_person_rule"],
        "change_management.high_risk_two_person_rule",
    )
    break_glass = _mapping(change["break_glass"], "change_management.break_glass")
    missing = sorted(BREAK_GLASS_FIELDS - set(break_glass))
    if missing:
        raise EnterpriseProfileError(
            "change_management.break_glass missing required field(s): "
            + ", ".join(missing)
        )
    unknown_break_glass = sorted(set(break_glass) - BREAK_GLASS_FIELDS)
    if unknown_break_glass:
        raise EnterpriseProfileError(
            "change_management.break_glass has unknown field(s): "
            + ", ".join(unknown_break_glass)
        )
    _bool(break_glass["enabled"], "change_management.break_glass.enabled")
    _int(
        break_glass["time_bound_minutes"],
        "change_management.break_glass.time_bound_minutes",
        minimum=1,
    )
    _bool(
        break_glass["reason_required"],
        "change_management.break_glass.reason_required",
    )
    _bool(
        break_glass["audit_required"],
        "change_management.break_glass.audit_required",
    )

    return sections


def evaluate_profile(profile: Any) -> tuple[Finding, ...]:
    sections = validate_structure(profile)

    metadata = sections["metadata"]
    deployment = sections["deployment"]
    identity = sections["identity"]
    data = sections["data"]
    secrets = sections["secrets"]
    audit = sections["audit"]
    reliability = sections["reliability"]
    supply = sections["supply_chain"]
    change = sections["change_management"]
    break_glass = _mapping(
        change["break_glass"], "change_management.break_glass"
    )

    production = metadata["environment"] == "production"
    service_profile = deployment["profile"] in {"G2", "G3"}
    findings: list[Finding] = []

    def add(status: str, code: str, message: str) -> None:
        findings.append(Finding(status, code, message))

    add(
        "PASS" if not production or metadata["enforcement_mode"] == "enforce" else "FAIL",
        "production.enforcement_mode",
        "production profiles require enforcement_mode=enforce",
    )

    if deployment["profile"] == "G3":
        ok = (
            deployment["tenant_mode"] == "multi_tenant"
            and deployment["tenant_isolation"] == "enforced"
        )
        add(
            "PASS" if ok else "FAIL",
            "tenant.g3_isolation",
            "G3 requires multi_tenant mode with enforced tenant isolation",
        )
    else:
        add(
            "PASS"
            if deployment["tenant_mode"] != "multi_tenant"
            else "FAIL",
            "tenant.profile_alignment",
            "shared multi_tenant mode is reserved for G3 in v0.1",
        )

    add(
        "PASS" if not production or identity["mfa_required"] else "FAIL",
        "identity.mfa",
        "production profiles require MFA",
    )
    add(
        "PASS"
        if not production or identity["high_risk_separation_of_duties"]
        else "FAIL",
        "identity.high_risk_sod",
        "production profiles require high-risk separation of duties",
    )
    add(
        "PASS"
        if not production or change["high_risk_two_person_rule"]
        else "FAIL",
        "change.high_risk_two_person",
        "production profiles require a two-person rule for high-risk changes",
    )

    add(
        "PASS"
        if "restricted" not in data["external_processing_allowed_classes"]
        else "FAIL",
        "data.restricted_external_processing",
        "restricted data must not be declared eligible for external processing",
    )
    add(
        "PASS"
        if not production or data["egress_mode"] != "unrestricted"
        else "FAIL",
        "data.production_egress",
        "production profiles must use allowlist or deny_by_default egress",
    )

    add(
        "PASS"
        if not production or not secrets["long_lived_cloud_keys_allowed"]
        else "FAIL",
        "secrets.long_lived_cloud_keys",
        "production profiles must not allow long-lived cloud access keys",
    )
    add(
        "PASS"
        if not production or not service_profile or secrets["workload_identity"] != "none"
        else "FAIL",
        "secrets.service_workload_identity",
        "production G2/G3 profiles require a workload identity",
    )

    add(
        "PASS" if not production or audit["append_only"] else "FAIL",
        "audit.append_only",
        "production profiles require append-only audit semantics",
    )
    add(
        "PASS"
        if not production or audit["actor_policy_revision_required"]
        else "FAIL",
        "audit.actor_policy_revision",
        "production audit must bind actor and policy revision",
    )
    add(
        "PASS"
        if not (production and service_profile)
        or audit["external_export_required"]
        else "FAIL",
        "audit.external_export",
        "production G2/G3 profiles require audit export capability",
    )
    add(
        "PASS" if audit["retention_days"] >= 365 else "WARN",
        "audit.retention",
        "v0.1 recommends at least 365 days of audit retention",
    )

    add(
        "PASS"
        if not production or reliability["backpressure_required"]
        else "FAIL",
        "reliability.backpressure",
        "production profiles require workload/verification backpressure",
    )
    add(
        "PASS"
        if reliability["restore_test_interval_days"] <= 90
        else "WARN",
        "reliability.restore_test_interval",
        "v0.1 recommends restore exercises at least every 90 days",
    )

    add(
        "PASS"
        if not production or supply["immutable_action_pins_required"]
        else "FAIL",
        "supply_chain.immutable_action_pins",
        "production profiles require immutable pins for controlled security/release lanes",
    )
    add(
        "PASS" if not production or supply["sbom_required"] else "FAIL",
        "supply_chain.sbom",
        "production profiles require an SBOM declaration for releases",
    )
    add(
        "PASS"
        if supply["provenance_attestation_required"]
        else "WARN",
        "supply_chain.provenance_attestation",
        "provenance attestation is recommended where platform/release support exists",
    )
    add(
        "PASS"
        if supply["vulnerability_response_sla_hours"] <= 168
        else "WARN",
        "supply_chain.vulnerability_response_sla",
        "v0.1 recommends a vulnerability-response objective of seven days or less",
    )

    if break_glass["enabled"]:
        ok = (
            break_glass["reason_required"]
            and break_glass["audit_required"]
            and break_glass["time_bound_minutes"] > 0
        )
        add(
            "PASS" if ok else "FAIL",
            "change.break_glass",
            "enabled break-glass must be time bounded, reason required, and audited",
        )
    else:
        add(
            "PASS",
            "change.break_glass",
            "break-glass is disabled",
        )

    return tuple(findings)


def summarize(profile: Any) -> dict[str, Any]:
    findings = evaluate_profile(profile)
    counts = {status: 0 for status in STATUSES}
    for finding in findings:
        counts[finding.status] += 1
    return {
        "api_version": API_VERSION,
        "kind": KIND,
        "declaration_ready": counts["FAIL"] == 0,
        "counts": counts,
        "findings": [finding.to_dict() for finding in findings],
        "authority": (
            "declaration preflight only; does not prove observed enforcement, "
            "security certification, execution authority, or merge authority"
        ),
    }


def load_profile(path: str | Path) -> Any:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EnterpriseProfileError(
            f"cannot read profile: {exc.__class__.__name__}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise EnterpriseProfileError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profile", help="path to EnterpriseControlProfile JSON")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit deterministic machine-readable JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = summarize(load_profile(args.profile))
    except EnterpriseProfileError as exc:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "declaration_ready": False,
                        "error": str(exc),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                file=sys.stderr,
            )
        else:
            print(f"enterprise-profile: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(
            "enterprise profile: "
            + ("READY" if result["declaration_ready"] else "NOT READY")
        )
        for finding in result["findings"]:
            print(
                f"{finding['status']} {finding['code']}: {finding['message']}"
            )
        print(result["authority"])

    return 0 if result["declaration_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
