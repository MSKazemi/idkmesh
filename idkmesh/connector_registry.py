"""Provider-neutral connector driver registry for C1-C (#613).

The registry maps the pair (connector kind, driver id) to one implementation
object. It deliberately does not perform routing, probing, provider I/O, secret
materialization, or worker execution. Those remain separate control-plane
stages.

Static driver capabilities describe what a driver implementation can support in
principle. They are not a live health/probe result and do not make a configured
connector dispatchable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from idkmesh.connector_profiles import ConnectorConfig
from idkmesh.connector_routing import CONNECTOR_KINDS, RISK_ORDER, TIER_ORDER


class ConnectorRegistryError(ValueError):
    """Registry failure with a stable machine-readable error code."""

    def __init__(self, code: str, kind: str, driver_id: str, message: str) -> None:
        self.code = code
        self.kind = kind
        self.driver_id = driver_id
        super().__init__(f"{code} for {kind}/{driver_id}: {message}")


@dataclass(frozen=True)
class DriverCapabilities:
    """Static capabilities declared by one driver implementation."""

    capability_tiers: frozenset[str] = field(default_factory=frozenset)
    task_classes: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    candidate_types: frozenset[str] = field(default_factory=frozenset)
    max_risk: str = "low"
    external_processing: bool = False

    def __post_init__(self) -> None:
        for name in ("capability_tiers", "task_classes", "tools", "candidate_types"):
            value = getattr(self, name)
            if isinstance(value, str):
                raise ValueError(f"{name} must be a collection of strings, not a string")
            try:
                items = frozenset(value)
            except TypeError as exc:
                raise ValueError(f"{name} must be a collection of strings") from exc
            if any(not isinstance(item, str) or not item for item in items):
                raise ValueError(f"{name} must contain only non-empty strings")
            object.__setattr__(self, name, items)

        unknown_tiers = sorted(set(self.capability_tiers) - set(TIER_ORDER))
        if unknown_tiers:
            raise ValueError(
                "unknown capability tier(s): " + ", ".join(unknown_tiers)
            )
        if self.max_risk not in RISK_ORDER:
            raise ValueError(f"unknown max_risk: {self.max_risk}")
        if type(self.external_processing) is not bool:
            raise ValueError("external_processing must be a boolean")

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-serializable declaration."""

        return {
            "tiers": sorted(self.capability_tiers, key=TIER_ORDER.__getitem__),
            "task_classes": sorted(self.task_classes),
            "tools": sorted(self.tools),
            "candidate_types": sorted(self.candidate_types),
            "max_risk": self.max_risk,
            "external_processing": self.external_processing,
        }


class ConnectorDriver(Protocol):
    """Minimum driver metadata boundary required by the registry."""

    kind: str
    driver_id: str
    driver_version: str

    def declared_capabilities(self, config: ConnectorConfig) -> DriverCapabilities:
        """Return static implementation capabilities for this configuration."""


@dataclass(frozen=True)
class DriverDescriptor:
    kind: str
    driver_id: str
    driver_version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "driver": self.driver_id,
            "version": self.driver_version,
        }


class ConnectorRegistry:
    """Deterministic registry keyed by connector kind and driver id."""

    def __init__(self) -> None:
        self._drivers: dict[tuple[str, str], ConnectorDriver] = {}

    def register(self, driver: ConnectorDriver) -> None:
        kind = getattr(driver, "kind", "")
        driver_id = getattr(driver, "driver_id", "")
        version = getattr(driver, "driver_version", "")

        if not isinstance(kind, str) or kind not in CONNECTOR_KINDS:
            raise ConnectorRegistryError(
                "unknown_connector_kind", str(kind), str(driver_id), "unsupported kind"
            )
        if not isinstance(driver_id, str) or not driver_id.strip():
            raise ConnectorRegistryError(
                "invalid_driver_id", kind, str(driver_id), "driver id must be non-empty"
            )
        if not isinstance(version, str) or not version.strip():
            raise ConnectorRegistryError(
                "invalid_driver_version", kind, driver_id, "driver version must be non-empty"
            )
        if not callable(getattr(driver, "declared_capabilities", None)):
            raise ConnectorRegistryError(
                "invalid_driver_interface",
                kind,
                driver_id,
                "driver must implement declared_capabilities(config)",
            )

        key = (kind, driver_id)
        if key in self._drivers:
            raise ConnectorRegistryError(
                "duplicate_driver", kind, driver_id, "driver is already registered"
            )
        self._drivers[key] = driver

    def resolve(self, kind: str, driver_id: str) -> ConnectorDriver:
        if kind not in CONNECTOR_KINDS:
            raise ConnectorRegistryError(
                "unknown_connector_kind", kind, driver_id, "unsupported kind"
            )
        try:
            return self._drivers[(kind, driver_id)]
        except KeyError as exc:
            raise ConnectorRegistryError(
                "unknown_driver", kind, driver_id, "no driver registered for this kind"
            ) from exc

    def resolve_config(self, config: ConnectorConfig) -> ConnectorDriver:
        return self.resolve(config.kind, config.driver)

    def descriptors(self) -> tuple[DriverDescriptor, ...]:
        return tuple(
            DriverDescriptor(
                kind=kind,
                driver_id=driver_id,
                driver_version=driver.driver_version,
            )
            for (kind, driver_id), driver in sorted(self._drivers.items())
        )


@dataclass(frozen=True)
class StaticFakeDriver:
    """Offline fake driver used only for connector contract tests."""

    kind: str
    driver_id: str
    driver_version: str
    capabilities: DriverCapabilities

    def declared_capabilities(self, config: ConnectorConfig) -> DriverCapabilities:
        if config.kind != self.kind or config.driver != self.driver_id:
            raise ConnectorRegistryError(
                "driver_config_mismatch",
                config.kind,
                config.driver,
                f"resolved driver expects {self.kind}/{self.driver_id}",
            )
        return self.capabilities


def fake_scm_driver() -> StaticFakeDriver:
    return StaticFakeDriver(
        kind="scm",
        driver_id="fake-scm",
        driver_version="0.1",
        capabilities=DriverCapabilities(
            capability_tiers=frozenset({"T0"}),
            task_classes=frozenset({"scm"}),
            tools=frozenset({"git"}),
            candidate_types=frozenset({"repository_reference"}),
            max_risk="medium",
            external_processing=False,
        ),
    )


def fake_agent_driver() -> StaticFakeDriver:
    return StaticFakeDriver(
        kind="agent",
        driver_id="fake-agent",
        driver_version="0.1",
        capabilities=DriverCapabilities(
            capability_tiers=frozenset({"T1", "T2"}),
            task_classes=frozenset({"coder", "docs", "tests"}),
            tools=frozenset({"git", "pytest"}),
            candidate_types=frozenset({"artifact_bundle", "github_pull_request"}),
            max_risk="medium",
            external_processing=False,
        ),
    )


def fake_model_driver() -> StaticFakeDriver:
    return StaticFakeDriver(
        kind="model",
        driver_id="fake-model",
        driver_version="0.1",
        capabilities=DriverCapabilities(
            capability_tiers=frozenset({"T1", "T2", "T3"}),
            task_classes=frozenset({"inference", "reasoning"}),
            tools=frozenset(),
            candidate_types=frozenset({"text"}),
            max_risk="medium",
            external_processing=True,
        ),
    )


def fake_execution_driver() -> StaticFakeDriver:
    return StaticFakeDriver(
        kind="execution",
        driver_id="fake-execution",
        driver_version="0.1",
        capabilities=DriverCapabilities(
            capability_tiers=frozenset({"T0"}),
            task_classes=frozenset({"execution"}),
            tools=frozenset({"python", "shell"}),
            candidate_types=frozenset({"command_result"}),
            max_risk="medium",
            external_processing=False,
        ),
    )


def build_fake_registry() -> ConnectorRegistry:
    """Return one offline registry covering all four connector kinds."""

    registry = ConnectorRegistry()
    for driver in (
        fake_scm_driver(),
        fake_agent_driver(),
        fake_model_driver(),
        fake_execution_driver(),
    ):
        registry.register(driver)
    return registry
