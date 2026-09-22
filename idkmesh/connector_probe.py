"""Normalized connector probe contract for C1-D (#614).

A probe is observational only. It reports health and static driver capabilities,
but it does not route, dispatch, execute, materialize secrets, or grant
repository authority.

The contract is deliberately safe for GitHub/CLI publication: probe failures are
structured codes rather than raw provider exception strings.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from idkmesh.connector_profiles import ConnectorConfig
from idkmesh.connector_registry import (
    ConnectorRegistry,
    DriverCapabilities,
    DriverDescriptor,
)

PROBE_STATUSES = {"healthy", "degraded", "unavailable", "disabled"}
FAILURE_KINDS = {
    "configuration",
    "authentication",
    "provider_unavailable",
    "provider_error",
    "driver_error",
}
_SAFE_CODE = re.compile(r"[a-z][a-z0-9_.:-]{0,127}\Z")


def _require_code(value: str, field: str) -> str:
    if not isinstance(value, str) or _SAFE_CODE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a safe symbolic code")
    return value


@dataclass(frozen=True)
class ProbeFailure:
    kind: str
    code: str

    def __post_init__(self) -> None:
        if self.kind not in FAILURE_KINDS:
            raise ValueError(f"unknown probe failure kind: {self.kind}")
        _require_code(self.code, "probe failure code")

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "code": self.code}


@dataclass(frozen=True)
class DriverProbeOutcome:
    status: str
    warnings: tuple[str, ...] = ()
    failure: ProbeFailure | None = None

    def __post_init__(self) -> None:
        if self.status not in PROBE_STATUSES - {"disabled"}:
            raise ValueError(f"unsupported driver probe status: {self.status}")
        for warning in self.warnings:
            _require_code(warning, "probe warning")
        if self.status == "healthy" and self.failure is not None:
            raise ValueError("healthy probe cannot include a failure")
        if self.status == "unavailable" and self.failure is None:
            raise ValueError("unavailable probe requires a failure")


class ProbeCapableDriver(Protocol):
    kind: str
    driver_id: str
    driver_version: str

    def declared_capabilities(self, config: ConnectorConfig) -> DriverCapabilities: ...

    def probe(self, config: ConnectorConfig) -> DriverProbeOutcome: ...


@dataclass(frozen=True)
class ConnectorProbeResult:
    connection_id: str
    status: str
    checked_at: str
    driver: DriverDescriptor
    observed_capabilities: DriverCapabilities
    auth_configured: bool
    warnings: tuple[str, ...] = ()
    failure: ProbeFailure | None = None

    def __post_init__(self) -> None:
        if self.status not in PROBE_STATUSES:
            raise ValueError(f"unknown probe status: {self.status}")
        if not isinstance(self.checked_at, str) or not self.checked_at:
            raise ValueError("checked_at must be a non-empty string")
        for warning in self.warnings:
            _require_code(warning, "probe warning")
        if type(self.auth_configured) is not bool:
            raise ValueError("auth_configured must be a boolean")
        if self.status == "healthy" and self.failure is not None:
            raise ValueError("healthy result cannot include a failure")
        if self.status == "unavailable" and self.failure is None:
            raise ValueError("unavailable result requires a failure")
        if self.status == "disabled" and self.failure is not None:
            raise ValueError("disabled result cannot include a probe failure")

    def to_dict(self) -> dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "status": self.status,
            "checked_at": self.checked_at,
            "driver": self.driver.to_dict(),
            "observed": {
                "capabilities": self.observed_capabilities.to_dict(),
            },
            "auth": {
                "configured": self.auth_configured,
            },
            "warnings": list(self.warnings),
            "failure": self.failure.to_dict() if self.failure else None,
        }


def probe_connector(
    config: ConnectorConfig,
    registry: ConnectorRegistry,
    *,
    checked_at: str,
    secret_available: bool | None = None,
) -> ConnectorProbeResult:
    """Probe one configured connector through the normalized contract.

    Secret availability is a boolean observation only. No secret value crosses
    this boundary.
    """

    if not isinstance(checked_at, str) or not checked_at:
        raise ValueError("checked_at must be a non-empty string")
    if secret_available is not None and type(secret_available) is not bool:
        raise ValueError("secret_available must be a boolean or None")

    driver = registry.resolve_config(config)
    descriptor = DriverDescriptor(
        kind=driver.kind,
        driver_id=driver.driver_id,
        driver_version=driver.driver_version,
    )

    auth_configured = config.secret_ref is None or secret_available is True

    try:
        capabilities = driver.declared_capabilities(config)
    except Exception:
        return ConnectorProbeResult(
            connection_id=config.id,
            status="unavailable",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=DriverCapabilities(),
            auth_configured=auth_configured,
            warnings=(),
            failure=ProbeFailure("driver_error", "capability_declaration_failed"),
        )

    if not config.enabled:
        return ConnectorProbeResult(
            connection_id=config.id,
            status="disabled",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=capabilities,
            auth_configured=auth_configured,
            warnings=(),
            failure=None,
        )

    if config.secret_ref is not None and secret_available is not True:
        return ConnectorProbeResult(
            connection_id=config.id,
            status="unavailable",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=capabilities,
            auth_configured=False,
            warnings=(),
            failure=ProbeFailure("configuration", "secret_unavailable"),
        )

    probe = getattr(driver, "probe", None)
    if not callable(probe):
        return ConnectorProbeResult(
            connection_id=config.id,
            status="unavailable",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=capabilities,
            auth_configured=auth_configured,
            warnings=(),
            failure=ProbeFailure("driver_error", "probe_interface_missing"),
        )

    try:
        outcome = probe(config)
    except Exception:
        return ConnectorProbeResult(
            connection_id=config.id,
            status="unavailable",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=capabilities,
            auth_configured=auth_configured,
            warnings=(),
            failure=ProbeFailure("driver_error", "probe_exception"),
        )

    if not isinstance(outcome, DriverProbeOutcome):
        return ConnectorProbeResult(
            connection_id=config.id,
            status="unavailable",
            checked_at=checked_at,
            driver=descriptor,
            observed_capabilities=capabilities,
            auth_configured=auth_configured,
            warnings=(),
            failure=ProbeFailure("driver_error", "invalid_probe_outcome"),
        )

    return ConnectorProbeResult(
        connection_id=config.id,
        status=outcome.status,
        checked_at=checked_at,
        driver=descriptor,
        observed_capabilities=capabilities,
        auth_configured=auth_configured,
        warnings=outcome.warnings,
        failure=outcome.failure,
    )


class FakeProbeDriver:
    """Deterministic offline driver for probe contract tests."""

    def __init__(
        self,
        *,
        kind: str = "agent",
        driver_id: str = "fake-probe-agent",
        driver_version: str = "0.1",
        capabilities: DriverCapabilities | None = None,
        outcome: DriverProbeOutcome | None = None,
    ) -> None:
        self.kind = kind
        self.driver_id = driver_id
        self.driver_version = driver_version
        self._capabilities = capabilities or DriverCapabilities(
            capability_tiers=frozenset({"T1"}),
            task_classes=frozenset({"coder"}),
            tools=frozenset({"git"}),
            candidate_types=frozenset({"artifact_bundle"}),
            max_risk="low",
            external_processing=False,
        )
        self.outcome = outcome or DriverProbeOutcome(status="healthy")
        self.probe_calls = 0

    def declared_capabilities(self, config: ConnectorConfig) -> DriverCapabilities:
        return self._capabilities

    def probe(self, config: ConnectorConfig) -> DriverProbeOutcome:
        self.probe_calls += 1
        return self.outcome
