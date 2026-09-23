"""Enterprise Control Profile v0.1 parsing and semantic validation.

The JSON Schema in schemas/enterprise-control-profile-v0.1.schema.json is the
published structural contract. This module provides a dependency-free runtime
boundary for core IDKMesh installations and enforces cross-field constraints
that are awkward or undesirable to encode as one large JSON Schema condition.

A valid profile is declared policy input only. It is not evidence that controls
are deployed and it grants no runtime authority.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

PROFILE_KIND = "idkmesh-enterprise-control-profile"
PROFILE_VERSION = "0.1"

_DEPLOYMENT_PROFILES = frozenset(
    {
        "g0_local_operator",
        "g1_github_native_team",
        "g2_self_hosted_team",
        "g3_multi_tenant_service",
    }
)
_TENANT_SCOPES = frozenset({"single_project", "single_org", "multi_tenant"})
_COORDINATORS = frozenset(
    {"local_process", "github_actions_ephemeral", "long_lived_service"}
)
_HUMAN_SOURCES = frozenset(
    {"local_trusted_operator", "github", "oidc", "saml", "external"}
)
_SERVICE_SOURCES = frozenset(
    {"process", "github_actions", "oidc", "mtls", "external"}
)
_DATA_CLASSES = frozenset({"public", "internal", "confidential", "restricted"})
_SECRET_BACKENDS = frozenset(
    {
        "none",
        "environment",
        "github_actions",
        "oidc_workload_identity",
        "external_secret_manager",
    }
)

_ROOT_FIELDS = frozenset(
    {
        "kind",
        "schema_version",
        "profile_id",
        "semantics",
        "deployment",
        "identity",
        "authority",
        "data",
        "secrets",
        "audit",
        "reliability",
        "supply_chain",
        "change_management",
        "enforcement",
    }
)

_SECTION_FIELDS = {
    "semantics": frozenset(
        {"profile_role", "control_evidence", "grants_runtime_authority"}
    ),
    "deployment": frozenset(
        {
            "profile",
            "tenant_scope",
            "remote_api_enabled",
            "coordinator_lifecycle",
            "canonical_code_authority",
        }
    ),
    "identity": frozenset(
        {
            "human_source",
            "service_source",
            "high_risk_distinct_approval",
            "break_glass_enabled",
        }
    ),
    "authority": frozenset(
        {
            "worker_can_merge",
            "verifier_can_merge",
            "worker_can_modify_policy",
            "integration_authority",
        }
    ),
    "data": frozenset(
        {
            "default_classification",
            "allowed_classifications",
            "external_processing",
            "egress_default",
        }
    ),
    "external_processing": _DATA_CLASSES,
    "secrets": frozenset(
        {
            "backend",
            "long_lived_cloud_keys_allowed",
            "raw_secret_material_in_work_units",
            "raw_secret_material_in_evidence",
        }
    ),
    "audit": frozenset(
        {"enabled", "tamper_evident_required", "retention_days", "export"}
    ),
    "reliability": frozenset(
        {
            "availability_target",
            "rpo_minutes",
            "rto_minutes",
            "backups_required",
            "restore_test_required",
        }
    ),
    "supply_chain": frozenset(
        {
            "immutable_action_pins_required",
            "sbom_required",
            "provenance_required",
            "vulnerability_response_sla_hours",
        }
    ),
    "change_management": frozenset(
        {
            "protected_integration_required",
            "policy_change_approval_required",
            "break_glass_reason_required",
        }
    ),
    "enforcement": frozenset(
        {"mode", "unknown_control_behavior", "startup_profile_validation"}
    ),
}


class EnterpriseProfileError(ValueError):
    """Stable fail-closed enterprise profile validation error."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> EnterpriseProfileError:
    return EnterpriseProfileError(code, path, message)


def _reject_constant(token: str) -> Any:
    raise _fail("invalid_json_number", "$", f"non-finite value {token!r}")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _fail("duplicate_key", "$", f"duplicate key {key!r}")
        result[key] = value
    return result


def _strict_object(
    value: Any,
    path: str,
    fields: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("invalid_type", path, "must be an object")
    missing = sorted(fields - set(value))
    if missing:
        raise _fail("missing_field", path, "missing: " + ", ".join(missing))
    unknown = sorted(set(value) - fields)
    if unknown:
        raise _fail(
            "unknown_field",
            f"{path}.{unknown[0]}",
            f"unknown field {unknown[0]!r}",
        )
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail("invalid_type", path, "must be a non-empty string")
    return value


def _enum(value: Any, path: str, allowed: frozenset[str]) -> str:
    text = _string(value, path)
    if text not in allowed:
        raise _fail(
            "invalid_value",
            path,
            "must be one of: " + ", ".join(sorted(allowed)),
        )
    return text


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _fail("invalid_type", path, "must be a boolean")
    return value


def _integer(
    value: Any,
    path: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail("invalid_type", path, "must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        limit = f">= {minimum}"
        if maximum is not None:
            limit += f" and <= {maximum}"
        raise _fail("invalid_value", path, f"must be {limit}")
    return value


def _number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("invalid_type", path, "must be a finite number")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise _fail(
            "invalid_value",
            path,
            f"must be finite and between {minimum} and {maximum}",
        )
    return number


def _exact(value: Any, expected: Any, path: str) -> None:
    if value != expected or type(value) is not type(expected):
        raise _fail("invalid_value", path, f"must be {expected!r}")


def _profile_id(value: Any) -> str:
    text = _string(value, "$.profile_id")
    alphanumeric = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
    )
    allowed = alphanumeric | set("._-")
    if len(text) > 128 or text[0] not in alphanumeric or any(
        char not in allowed for char in text
    ):
        raise _fail(
            "invalid_value",
            "$.profile_id",
            "must be 1-128 characters using letters, digits, '.', '_' or '-'",
        )
    return text


def validate_enterprise_profile(profile: Any) -> None:
    """Validate v0.1 structure plus non-compensating semantic constraints."""

    root = _strict_object(profile, "$", _ROOT_FIELDS)
    _exact(root["kind"], PROFILE_KIND, "$.kind")
    _exact(root["schema_version"], PROFILE_VERSION, "$.schema_version")
    _profile_id(root["profile_id"])

    semantics = _strict_object(
        root["semantics"], "$.semantics", _SECTION_FIELDS["semantics"]
    )
    _exact(semantics["profile_role"], "policy_input_only", "$.semantics.profile_role")
    _exact(
        semantics["control_evidence"],
        "declared_not_observed",
        "$.semantics.control_evidence",
    )
    _exact(
        semantics["grants_runtime_authority"],
        False,
        "$.semantics.grants_runtime_authority",
    )

    deployment = _strict_object(
        root["deployment"], "$.deployment", _SECTION_FIELDS["deployment"]
    )
    mode = _enum(
        deployment["profile"],
        "$.deployment.profile",
        _DEPLOYMENT_PROFILES,
    )
    tenant_scope = _enum(
        deployment["tenant_scope"],
        "$.deployment.tenant_scope",
        _TENANT_SCOPES,
    )
    remote_api = _boolean(
        deployment["remote_api_enabled"],
        "$.deployment.remote_api_enabled",
    )
    lifecycle = _enum(
        deployment["coordinator_lifecycle"],
        "$.deployment.coordinator_lifecycle",
        _COORDINATORS,
    )
    _exact(
        deployment["canonical_code_authority"],
        "github_protected_integration",
        "$.deployment.canonical_code_authority",
    )

    identity = _strict_object(
        root["identity"], "$.identity", _SECTION_FIELDS["identity"]
    )
    human_source = _enum(
        identity["human_source"], "$.identity.human_source", _HUMAN_SOURCES
    )
    service_source = _enum(
        identity["service_source"],
        "$.identity.service_source",
        _SERVICE_SOURCES,
    )
    distinct_approval = _boolean(
        identity["high_risk_distinct_approval"],
        "$.identity.high_risk_distinct_approval",
    )
    break_glass = _boolean(
        identity["break_glass_enabled"],
        "$.identity.break_glass_enabled",
    )

    authority = _strict_object(
        root["authority"], "$.authority", _SECTION_FIELDS["authority"]
    )
    for field in (
        "worker_can_merge",
        "verifier_can_merge",
        "worker_can_modify_policy",
    ):
        _exact(authority[field], False, f"$.authority.{field}")
    _enum(
        authority["integration_authority"],
        "$.authority.integration_authority",
        frozenset(
            {
                "github_protected_integration",
                "external_human_or_governance",
            }
        ),
    )

    data = _strict_object(root["data"], "$.data", _SECTION_FIELDS["data"])
    default_classification = _enum(
        data["default_classification"],
        "$.data.default_classification",
        _DATA_CLASSES,
    )
    allowed_raw = data["allowed_classifications"]
    if not isinstance(allowed_raw, list) or not allowed_raw:
        raise _fail(
            "invalid_type",
            "$.data.allowed_classifications",
            "must be a non-empty array",
        )
    allowed = [
        _enum(
            item,
            f"$.data.allowed_classifications[{index}]",
            _DATA_CLASSES,
        )
        for index, item in enumerate(allowed_raw)
    ]
    if len(allowed) != len(set(allowed)):
        raise _fail(
            "duplicate_value",
            "$.data.allowed_classifications",
            "must not contain duplicates",
        )
    if default_classification not in allowed:
        raise _fail(
            "contradictory_profile",
            "$.data.default_classification",
            "default classification must be in allowed_classifications",
        )
    processing = _strict_object(
        data["external_processing"],
        "$.data.external_processing",
        _SECTION_FIELDS["external_processing"],
    )
    for name in sorted(_DATA_CLASSES):
        _boolean(processing[name], f"$.data.external_processing.{name}")
    egress_default = _enum(
        data["egress_default"],
        "$.data.egress_default",
        frozenset({"deny", "allow"}),
    )

    secrets = _strict_object(
        root["secrets"], "$.secrets", _SECTION_FIELDS["secrets"]
    )
    secret_backend = _enum(
        secrets["backend"], "$.secrets.backend", _SECRET_BACKENDS
    )
    long_lived_keys = _boolean(
        secrets["long_lived_cloud_keys_allowed"],
        "$.secrets.long_lived_cloud_keys_allowed",
    )
    _exact(
        secrets["raw_secret_material_in_work_units"],
        False,
        "$.secrets.raw_secret_material_in_work_units",
    )
    _exact(
        secrets["raw_secret_material_in_evidence"],
        False,
        "$.secrets.raw_secret_material_in_evidence",
    )

    audit = _strict_object(root["audit"], "$.audit", _SECTION_FIELDS["audit"])
    audit_enabled = _boolean(audit["enabled"], "$.audit.enabled")
    tamper_evident = _boolean(
        audit["tamper_evident_required"],
        "$.audit.tamper_evident_required",
    )
    _integer(
        audit["retention_days"],
        "$.audit.retention_days",
        minimum=1,
        maximum=36500,
    )
    audit_export = _enum(
        audit["export"],
        "$.audit.export",
        frozenset({"none", "file", "siem", "archive"}),
    )

    reliability = _strict_object(
        root["reliability"],
        "$.reliability",
        _SECTION_FIELDS["reliability"],
    )
    _number(
        reliability["availability_target"],
        "$.reliability.availability_target",
        minimum=0.0,
        maximum=1.0,
    )
    _integer(
        reliability["rpo_minutes"],
        "$.reliability.rpo_minutes",
        minimum=0,
    )
    _integer(
        reliability["rto_minutes"],
        "$.reliability.rto_minutes",
        minimum=0,
    )
    backups_required = _boolean(
        reliability["backups_required"],
        "$.reliability.backups_required",
    )
    restore_test_required = _boolean(
        reliability["restore_test_required"],
        "$.reliability.restore_test_required",
    )

    supply_chain = _strict_object(
        root["supply_chain"],
        "$.supply_chain",
        _SECTION_FIELDS["supply_chain"],
    )
    immutable_pins = _boolean(
        supply_chain["immutable_action_pins_required"],
        "$.supply_chain.immutable_action_pins_required",
    )
    sbom_required = _boolean(
        supply_chain["sbom_required"],
        "$.supply_chain.sbom_required",
    )
    provenance_required = _boolean(
        supply_chain["provenance_required"],
        "$.supply_chain.provenance_required",
    )
    _integer(
        supply_chain["vulnerability_response_sla_hours"],
        "$.supply_chain.vulnerability_response_sla_hours",
        minimum=1,
        maximum=8760,
    )

    change = _strict_object(
        root["change_management"],
        "$.change_management",
        _SECTION_FIELDS["change_management"],
    )
    protected_integration = _boolean(
        change["protected_integration_required"],
        "$.change_management.protected_integration_required",
    )
    policy_approval = _boolean(
        change["policy_change_approval_required"],
        "$.change_management.policy_change_approval_required",
    )
    break_glass_reason = _boolean(
        change["break_glass_reason_required"],
        "$.change_management.break_glass_reason_required",
    )

    enforcement = _strict_object(
        root["enforcement"],
        "$.enforcement",
        _SECTION_FIELDS["enforcement"],
    )
    enforcement_mode = _enum(
        enforcement["mode"],
        "$.enforcement.mode",
        frozenset({"audit", "enforce"}),
    )
    unknown_behavior = _enum(
        enforcement["unknown_control_behavior"],
        "$.enforcement.unknown_control_behavior",
        frozenset({"warn", "fail"}),
    )
    _exact(
        enforcement["startup_profile_validation"],
        True,
        "$.enforcement.startup_profile_validation",
    )

    # Cross-field, non-compensating constraints.
    if tamper_evident and not audit_enabled:
        raise _fail(
            "contradictory_profile",
            "$.audit",
            "tamper-evident audit cannot be required while audit is disabled",
        )
    if audit_export != "none" and not audit_enabled:
        raise _fail(
            "contradictory_profile",
            "$.audit.export",
            "audit export requires audit.enabled=true",
        )
    if break_glass and (not audit_enabled or not break_glass_reason):
        raise _fail(
            "contradictory_profile",
            "$.identity.break_glass_enabled",
            "break-glass requires audit and a mandatory reason",
        )
    if secret_backend == "oidc_workload_identity" and long_lived_keys:
        raise _fail(
            "contradictory_profile",
            "$.secrets.long_lived_cloud_keys_allowed",
            "OIDC workload identity cannot simultaneously allow long-lived cloud keys",
        )
    if enforcement_mode == "enforce" and unknown_behavior != "fail":
        raise _fail(
            "contradictory_profile",
            "$.enforcement.unknown_control_behavior",
            "enforce mode must fail closed on unknown controls",
        )
    if not protected_integration:
        raise _fail(
            "contradictory_profile",
            "$.change_management.protected_integration_required",
            "enterprise profiles require protected integration",
        )

    if mode == "g0_local_operator":
        expected = {
            "tenant_scope": (tenant_scope, "single_project"),
            "remote_api_enabled": (remote_api, False),
            "coordinator_lifecycle": (lifecycle, "local_process"),
            "human_source": (human_source, "local_trusted_operator"),
            "service_source": (service_source, "process"),
        }
    elif mode == "g1_github_native_team":
        expected = {
            "remote_api_enabled": (remote_api, False),
            "coordinator_lifecycle": (lifecycle, "github_actions_ephemeral"),
            "human_source": (human_source, "github"),
            "service_source": (service_source, "github_actions"),
        }
        if tenant_scope not in {"single_project", "single_org"}:
            raise _fail(
                "contradictory_profile",
                "$.deployment.tenant_scope",
                "G1 requires single_project or single_org scope",
            )
        if egress_default != "deny":
            raise _fail(
                "contradictory_profile",
                "$.data.egress_default",
                "G1 must deny egress by default",
            )
    elif mode == "g2_self_hosted_team":
        expected = {
            "remote_api_enabled": (remote_api, True),
            "coordinator_lifecycle": (lifecycle, "long_lived_service"),
        }
        if tenant_scope not in {"single_project", "single_org"}:
            raise _fail(
                "contradictory_profile",
                "$.deployment.tenant_scope",
                "G2 requires single_project or single_org scope",
            )
        if human_source == "local_trusted_operator":
            raise _fail(
                "contradictory_profile",
                "$.identity.human_source",
                "G2 requires federated or external human identity",
            )
        if service_source in {"process", "github_actions"}:
            raise _fail(
                "contradictory_profile",
                "$.identity.service_source",
                "G2 requires workload/service identity stronger than process identity",
            )
        if not backups_required or not restore_test_required:
            raise _fail(
                "contradictory_profile",
                "$.reliability",
                "G2 requires backups and restore testing",
            )
        if egress_default != "deny":
            raise _fail(
                "contradictory_profile",
                "$.data.egress_default",
                "G2 must deny egress by default",
            )
    else:
        expected = {
            "tenant_scope": (tenant_scope, "multi_tenant"),
            "remote_api_enabled": (remote_api, True),
            "coordinator_lifecycle": (lifecycle, "long_lived_service"),
        }
        if human_source == "local_trusted_operator":
            raise _fail(
                "contradictory_profile",
                "$.identity.human_source",
                "G3 requires federated or external human identity",
            )
        if service_source in {"process", "github_actions"}:
            raise _fail(
                "contradictory_profile",
                "$.identity.service_source",
                "G3 requires federated workload/service identity",
            )
        if not distinct_approval:
            raise _fail(
                "contradictory_profile",
                "$.identity.high_risk_distinct_approval",
                "G3 requires distinct approval for high-risk operations",
            )
        if not audit_enabled or not tamper_evident:
            raise _fail(
                "contradictory_profile",
                "$.audit",
                "G3 requires enabled tamper-evident audit",
            )
        if not backups_required or not restore_test_required:
            raise _fail(
                "contradictory_profile",
                "$.reliability",
                "G3 requires backups and restore testing",
            )
        if egress_default != "deny":
            raise _fail(
                "contradictory_profile",
                "$.data.egress_default",
                "G3 must deny egress by default",
            )
        if not (immutable_pins and sbom_required and provenance_required):
            raise _fail(
                "contradictory_profile",
                "$.supply_chain",
                "G3 requires immutable pins, SBOM, and provenance",
            )

    for name, (actual, required) in expected.items():
        if actual != required:
            path = {
                "tenant_scope": "$.deployment.tenant_scope",
                "remote_api_enabled": "$.deployment.remote_api_enabled",
                "coordinator_lifecycle": "$.deployment.coordinator_lifecycle",
                "human_source": "$.identity.human_source",
                "service_source": "$.identity.service_source",
            }[name]
            raise _fail(
                "contradictory_profile",
                path,
                f"{mode} requires {required!r}",
            )

    if mode in {"g1_github_native_team", "g2_self_hosted_team", "g3_multi_tenant_service"}:
        if not distinct_approval:
            raise _fail(
                "contradictory_profile",
                "$.identity.high_risk_distinct_approval",
                f"{mode} requires distinct approval for high-risk operations",
            )
        if not audit_enabled:
            raise _fail(
                "contradictory_profile",
                "$.audit.enabled",
                f"{mode} requires audit",
            )
        if not policy_approval:
            raise _fail(
                "contradictory_profile",
                "$.change_management.policy_change_approval_required",
                f"{mode} requires approval for policy changes",
            )


def parse_enterprise_profile_text(
    text: str,
    *,
    source: str = "enterprise control profile",
) -> dict[str, Any]:
    """Parse and validate one strict enterprise profile JSON document."""

    text = text.removeprefix("\ufeff")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise _fail(
            "invalid_json",
            source,
            f"line {exc.lineno}, column {exc.colno}",
        ) from exc
    except EnterpriseProfileError as exc:
        raise _fail(exc.code, source, str(exc)) from exc

    validate_enterprise_profile(value)
    return value


def load_enterprise_profile(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise _fail(
            "profile_read_error",
            str(source),
            exc.__class__.__name__,
        ) from exc
    return parse_enterprise_profile_text(text, source=str(source))
