"""Capability evidence for OpenAI-compatible model connectors.

C3-G keeps model capability claims explicit and reviewable. Model names are not
used as heuristics for capability tiers, context windows, tool support, or risk.

The evidence object can be confirmed against an OpenAI-compatible /models probe,
then exposed through the existing DriverCapabilities contract. A raw model
connector remains kind="model" and never becomes an agent/coding authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from idkmesh.connector_errors import ConnectorError
from idkmesh.connector_profiles import ConnectorConfig
from idkmesh.connector_registry import (
    ConnectorRegistryError,
    DriverCapabilities,
)
from idkmesh.connector_routing import RISK_ORDER, TIER_ORDER
from idkmesh.openai_compatible_http import OpenAICompatibleProbeResult


_ALLOWED_TASK_CLASSES = frozenset({"inference", "reasoning"})
_ALLOWED_ROUTING_TOOLS = frozenset(
    {
        "model:function_calling",
        "model:structured_output",
        "model:vision_input",
    }
)
_ALLOWED_EVIDENCE_SOURCES = frozenset(
    {
        "maintainer_config",
        "provider_documentation",
        "benchmark",
        "probe",
    }
)

# Sources that name an artifact outside this repository. Claiming one without a
# reference would let a capability record advertise external provenance that
# nothing points at, so at least one evidence_ref is required.
#
# "maintainer_config" is self-referencing (the profile is the artifact) and
# "probe" is machine-derived, with its scope carried by model_observed.
_CITED_EVIDENCE_SOURCES = frozenset({"provider_documentation", "benchmark"})


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_set(value: object, field: str) -> frozenset[str]:
    if isinstance(value, str):
        raise ValueError(f"{field} must be a collection of strings, not a string")
    try:
        items = frozenset(value)
    except TypeError as exc:
        raise ValueError(f"{field} must be a collection of strings") from exc
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{field} must contain only non-empty strings")
    return frozenset(item.strip() for item in items)


@dataclass(frozen=True)
class ModelCapabilityEvidence:
    """One reviewable model capability declaration with provenance."""

    model_id: str
    capability_tiers: frozenset[str]
    task_classes: frozenset[str]
    routing_tools: frozenset[str]
    context_window_tokens: int | None
    max_risk: str
    external_processing: bool
    evidence_sources: frozenset[str]
    evidence_refs: tuple[str, ...] = ()
    model_observed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _nonempty(self.model_id, "model_id"))
        tiers = _string_set(self.capability_tiers, "capability_tiers")
        unknown_tiers = sorted(set(tiers) - set(TIER_ORDER))
        if unknown_tiers:
            raise ValueError(
                "unknown capability tier(s): " + ", ".join(unknown_tiers)
            )
        if not tiers:
            raise ValueError("capability_tiers must not be empty")
        object.__setattr__(self, "capability_tiers", tiers)

        task_classes = _string_set(self.task_classes, "task_classes")
        if not task_classes:
            raise ValueError("task_classes must not be empty")
        unknown_tasks = sorted(set(task_classes) - set(_ALLOWED_TASK_CLASSES))
        if unknown_tasks:
            raise ValueError(
                "unsupported model task class(es): " + ", ".join(unknown_tasks)
            )
        object.__setattr__(self, "task_classes", task_classes)

        routing_tools = _string_set(self.routing_tools, "routing_tools")
        unknown_tools = sorted(set(routing_tools) - set(_ALLOWED_ROUTING_TOOLS))
        if unknown_tools:
            raise ValueError(
                "unsupported model routing tool(s): " + ", ".join(unknown_tools)
            )
        object.__setattr__(self, "routing_tools", routing_tools)

        if self.context_window_tokens is not None:
            if (
                isinstance(self.context_window_tokens, bool)
                or not isinstance(self.context_window_tokens, int)
                or self.context_window_tokens < 1
            ):
                raise ValueError(
                    "context_window_tokens must be an integer >= 1 or None"
                )

        if self.max_risk not in RISK_ORDER:
            raise ValueError(f"unknown max_risk: {self.max_risk}")
        if type(self.external_processing) is not bool:
            raise ValueError("external_processing must be a boolean")
        if type(self.model_observed) is not bool:
            raise ValueError("model_observed must be a boolean")

        sources = _string_set(self.evidence_sources, "evidence_sources")
        if not sources:
            raise ValueError("evidence_sources must not be empty")
        unknown_sources = sorted(set(sources) - set(_ALLOWED_EVIDENCE_SOURCES))
        if unknown_sources:
            raise ValueError(
                "unknown evidence source(s): " + ", ".join(unknown_sources)
            )
        object.__setattr__(self, "evidence_sources", sources)

        refs = tuple(_nonempty(item, "evidence_ref") for item in self.evidence_refs)
        if not refs and sources & _CITED_EVIDENCE_SOURCES:
            cited = ", ".join(sorted(sources & _CITED_EVIDENCE_SOURCES))
            raise ValueError(
                f"evidence_refs must cite at least one artifact for source(s): {cited}"
            )
        object.__setattr__(self, "evidence_refs", refs)

    def to_driver_capabilities(self) -> DriverCapabilities:
        """Project evidence into the merged connector capability contract."""

        return DriverCapabilities(
            capability_tiers=self.capability_tiers,
            task_classes=self.task_classes,
            tools=self.routing_tools,
            candidate_types=frozenset({"text"}),
            max_risk=self.max_risk,
            external_processing=self.external_processing,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "tiers": sorted(self.capability_tiers, key=TIER_ORDER.__getitem__),
            "task_classes": sorted(self.task_classes),
            "routing_tools": sorted(self.routing_tools),
            "context_window_tokens": self.context_window_tokens,
            "max_risk": self.max_risk,
            "external_processing": self.external_processing,
            "evidence_sources": sorted(self.evidence_sources),
            "evidence_refs": list(self.evidence_refs),
            "model_observed": self.model_observed,
        }


def confirm_model_identity(
    evidence: ModelCapabilityEvidence,
    probe: OpenAICompatibleProbeResult,
) -> ModelCapabilityEvidence:
    """Confirm only model identity/availability from a /models probe.

    A probe never upgrades tier, context, task, tool, or risk claims.
    """

    if probe.configured_model != evidence.model_id:
        raise ConnectorError(
            code="configuration_error",
            message="Capability evidence model does not match the probed model.",
            connection_id=probe.connection_id,
            details={
                "evidence_model": evidence.model_id,
                "configured_model": probe.configured_model,
            },
        )
    if not probe.model_available or evidence.model_id not in probe.observed_models:
        raise ConnectorError(
            code="configuration_error",
            message="Capability evidence model was not observed by the endpoint.",
            connection_id=probe.connection_id,
            details={"model_id": evidence.model_id},
        )
    return replace(
        evidence,
        evidence_sources=evidence.evidence_sources | {"probe"},
        model_observed=True,
    )


class OpenAICompatibleModelDriver:
    """Registry driver backed by explicit per-model capability evidence."""

    kind = "model"
    driver_id = "openai-compatible"
    driver_version = "0.1"

    def __init__(self, evidence_by_model: Mapping[str, ModelCapabilityEvidence]):
        if not isinstance(evidence_by_model, Mapping) or not evidence_by_model:
            raise ValueError("evidence_by_model must be a non-empty mapping")

        normalized: dict[str, ModelCapabilityEvidence] = {}
        for model_id, evidence in evidence_by_model.items():
            key = _nonempty(model_id, "model_id")
            if not isinstance(evidence, ModelCapabilityEvidence):
                raise ValueError(
                    "evidence_by_model values must be ModelCapabilityEvidence"
                )
            if evidence.model_id != key:
                raise ValueError("evidence mapping key must match evidence.model_id")
            normalized[key] = evidence
        self._evidence_by_model = normalized

    def capability_evidence(self, config: ConnectorConfig) -> ModelCapabilityEvidence:
        self._validate_config_identity(config)
        model = config.settings.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ConnectorRegistryError(
                "model_setting_missing",
                config.kind,
                config.driver,
                "settings.model must be a non-empty string",
            )
        try:
            evidence = self._evidence_by_model[model]
        except KeyError as exc:
            raise ConnectorRegistryError(
                "capability_evidence_missing",
                config.kind,
                config.driver,
                f"no capability evidence registered for model {model}",
            ) from exc

        self._reject_profile_overclaim(config, evidence)
        return evidence

    def declared_capabilities(self, config: ConnectorConfig) -> DriverCapabilities:
        """Merge the profile declaration with the evidence ceiling.

        An empty profile collection means *inherit the evidence*, not *deny*:
        ConnectorConfig cannot distinguish "capabilities.tools omitted" from
        "capabilities.tools: []", so a profile cannot subtract a single tool or
        candidate type here. Narrowing that far belongs in the routing policy,
        which is evaluated separately.
        """

        evidence = self.capability_evidence(config)
        tiers = config.capability_tiers or evidence.capability_tiers
        task_classes = config.task_classes or evidence.task_classes
        tools = config.tools or evidence.routing_tools
        candidate_types = config.candidate_types or frozenset({"text"})
        max_risk = min(
            (config.max_risk, evidence.max_risk),
            key=RISK_ORDER.__getitem__,
        )
        return DriverCapabilities(
            capability_tiers=tiers,
            task_classes=task_classes,
            tools=tools,
            candidate_types=candidate_types,
            max_risk=max_risk,
            external_processing=evidence.external_processing,
        )

    def _validate_config_identity(self, config: ConnectorConfig) -> None:
        if config.kind != self.kind or config.driver != self.driver_id:
            raise ConnectorRegistryError(
                "driver_config_mismatch",
                config.kind,
                config.driver,
                f"resolved driver expects {self.kind}/{self.driver_id}",
            )

    def _reject_profile_overclaim(
        self,
        config: ConnectorConfig,
        evidence: ModelCapabilityEvidence,
    ) -> None:
        checks = (
            (
                "tiers",
                config.capability_tiers,
                evidence.capability_tiers,
            ),
            (
                "task_classes",
                config.task_classes,
                evidence.task_classes,
            ),
            (
                "tools",
                config.tools,
                evidence.routing_tools,
            ),
            (
                "candidate_types",
                config.candidate_types,
                frozenset({"text"}),
            ),
        )
        for name, claimed, supported in checks:
            unsupported = sorted(set(claimed) - set(supported))
            if unsupported:
                raise ConnectorRegistryError(
                    "profile_capability_overclaim",
                    config.kind,
                    config.driver,
                    f"{name} exceed evidence: {', '.join(unsupported)}",
                )

        if RISK_ORDER[config.max_risk] > RISK_ORDER[evidence.max_risk]:
            raise ConnectorRegistryError(
                "profile_capability_overclaim",
                config.kind,
                config.driver,
                "max_risk exceeds capability evidence",
            )

        if config.external_processing != evidence.external_processing:
            raise ConnectorRegistryError(
                "external_processing_mismatch",
                config.kind,
                config.driver,
                "profile external_processing must match capability evidence",
            )
