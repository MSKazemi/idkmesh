import json
import unittest

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.connector_registry import ConnectorRegistry, ConnectorRegistryError
from idkmesh.openai_compatible_capabilities import (
    ModelCapabilityEvidence,
    OpenAICompatibleModelDriver,
    confirm_model_identity,
)
from idkmesh.openai_compatible_http import OpenAICompatibleProbeResult


def _evidence(**overrides):
    values = {
        "model_id": "model-a",
        "capability_tiers": frozenset({"T1", "T2"}),
        "task_classes": frozenset({"inference", "reasoning"}),
        "routing_tools": frozenset({"model:function_calling"}),
        "context_window_tokens": 32768,
        "max_risk": "medium",
        "external_processing": True,
        "evidence_sources": frozenset({"maintainer_config"}),
        "evidence_refs": ("profile:model-a:v1",),
    }
    values.update(overrides)
    return ModelCapabilityEvidence(**values)


def _config(**overrides):
    raw = {
        "api_version": "idkmesh.io/v1alpha1",
        "id": "model-main",
        "kind": "model",
        "driver": "openai-compatible",
        "enabled": True,
        "settings": {
            "base_url": "https://example.com/v1",
            "model": "model-a",
        },
        "capabilities": {
            "tiers": ["T1", "T2"],
            "task_classes": ["inference", "reasoning"],
            "tools": ["model:function_calling"],
            "candidate_types": ["text"],
            "max_risk": "medium",
        },
        "policy": {
            "task_classes": ["inference", "reasoning"],
            "allowed_risk": ["low", "medium"],
            "external_processing": True,
            "project_spend_usd_max": 0,
        },
    }

    for section, updates in overrides.items():
        if isinstance(updates, dict):
            raw.setdefault(section, {}).update(updates)
        else:
            raw[section] = updates
    return parse_connector_profile_document(raw)[0]


class OpenAICompatibleCapabilityEvidenceTests(unittest.TestCase):
    def test_evidence_projects_into_existing_driver_capabilities(self):
        evidence = _evidence()
        capabilities = evidence.to_driver_capabilities()
        self.assertEqual(capabilities.capability_tiers, frozenset({"T1", "T2"}))
        self.assertEqual(
            capabilities.task_classes,
            frozenset({"inference", "reasoning"}),
        )
        self.assertEqual(
            capabilities.tools,
            frozenset({"model:function_calling"}),
        )
        self.assertEqual(capabilities.candidate_types, frozenset({"text"}))
        self.assertTrue(capabilities.external_processing)

    def test_evidence_is_stably_serializable_with_provenance(self):
        rendered = _evidence().to_dict()
        self.assertEqual(rendered["model_id"], "model-a")
        self.assertEqual(rendered["tiers"], ["T1", "T2"])
        self.assertEqual(rendered["context_window_tokens"], 32768)
        self.assertEqual(
            rendered["evidence_sources"],
            ["maintainer_config"],
        )
        json.dumps(rendered, sort_keys=True)

    def test_probe_confirmation_adds_identity_evidence_only(self):
        evidence = _evidence()
        probe = OpenAICompatibleProbeResult(
            connection_id="model-main",
            status="healthy",
            configured_model="model-a",
            observed_models=("model-a", "model-b"),
            model_available=True,
            warnings=(),
        )
        confirmed = confirm_model_identity(evidence, probe)
        self.assertTrue(confirmed.model_observed)
        self.assertIn("probe", confirmed.evidence_sources)
        self.assertEqual(confirmed.capability_tiers, evidence.capability_tiers)
        self.assertEqual(
            confirmed.context_window_tokens,
            evidence.context_window_tokens,
        )
        self.assertEqual(confirmed.routing_tools, evidence.routing_tools)

    def test_probe_cannot_confirm_different_or_missing_model(self):
        evidence = _evidence()
        different = OpenAICompatibleProbeResult(
            connection_id="model-main",
            status="healthy",
            configured_model="model-b",
            observed_models=("model-b",),
            model_available=True,
            warnings=(),
        )
        with self.assertRaisesRegex(Exception, "does not match"):
            confirm_model_identity(evidence, different)

        missing = OpenAICompatibleProbeResult(
            connection_id="model-main",
            status="degraded",
            configured_model="model-a",
            observed_models=("model-b",),
            model_available=False,
            warnings=("configured_model_not_observed",),
        )
        with self.assertRaisesRegex(Exception, "not observed"):
            confirm_model_identity(evidence, missing)

    def test_driver_registers_as_model_openai_compatible(self):
        registry = ConnectorRegistry()
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        registry.register(driver)
        resolved = registry.resolve("model", "openai-compatible")
        self.assertIs(resolved, driver)
        capabilities = resolved.declared_capabilities(_config())
        self.assertEqual(capabilities.capability_tiers, frozenset({"T1", "T2"}))

    def test_profile_can_downscope_evidence_without_reexpansion(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        config = _config(
            capabilities={
                "tiers": ["T1"],
                "task_classes": ["inference"],
                "tools": [],
                "candidate_types": ["text"],
                "max_risk": "low",
            },
            policy={
                "task_classes": ["inference"],
                "allowed_risk": ["low"],
                "external_processing": True,
            },
        )
        capabilities = driver.declared_capabilities(config)
        self.assertEqual(capabilities.capability_tiers, frozenset({"T1"}))
        self.assertEqual(capabilities.task_classes, frozenset({"inference"}))
        self.assertEqual(capabilities.max_risk, "low")
        # An empty profile collection means "inherit the evidence", not "deny":
        # ConnectorConfig represents an omitted and an explicitly empty list
        # identically, so `tools: []` here still resolves to the evidenced tool
        # set. Asserted so the boundary is visible rather than assumed.
        self.assertEqual(config.tools, frozenset())
        self.assertEqual(
            capabilities.tools,
            frozenset({"model:function_calling"}),
        )
        self.assertEqual(capabilities.candidate_types, frozenset({"text"}))

    def test_profile_cannot_upgrade_capability_tier(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        config = _config(
            capabilities={
                "tiers": ["T4"],
                "task_classes": ["inference", "reasoning"],
                "tools": ["model:function_calling"],
                "candidate_types": ["text"],
                "max_risk": "medium",
            }
        )
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(config)
        self.assertEqual(
            caught.exception.code,
            "profile_capability_overclaim",
        )

    def test_profile_cannot_claim_unproven_model_tool(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        config = _config(
            capabilities={
                "tiers": ["T1"],
                "task_classes": ["inference"],
                "tools": ["model:structured_output"],
                "candidate_types": ["text"],
                "max_risk": "low",
            },
            policy={
                "task_classes": ["inference"],
                "allowed_risk": ["low"],
            },
        )
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(config)
        self.assertEqual(
            caught.exception.code,
            "profile_capability_overclaim",
        )

    def test_profile_cannot_hide_external_processing(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        config = _config(policy={"external_processing": False})
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(config)
        self.assertEqual(
            caught.exception.code,
            "external_processing_mismatch",
        )

    def test_missing_model_evidence_fails_closed(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        config = _config(settings={"model": "model-b"})
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(config)
        self.assertEqual(
            caught.exception.code,
            "capability_evidence_missing",
        )

    def test_missing_model_setting_fails_closed(self):
        driver = OpenAICompatibleModelDriver({"model-a": _evidence()})
        raw = {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "model-main",
            "kind": "model",
            "driver": "openai-compatible",
            "enabled": True,
            "policy": {"external_processing": True},
        }
        config = parse_connector_profile_document(raw)[0]
        with self.assertRaises(ConnectorRegistryError) as caught:
            driver.declared_capabilities(config)
        self.assertEqual(caught.exception.code, "model_setting_missing")

    def test_evidence_rejects_unknown_claims_and_bad_context(self):
        with self.assertRaisesRegex(ValueError, "unknown capability"):
            _evidence(capability_tiers=frozenset({"T9"}))
        with self.assertRaisesRegex(ValueError, "unsupported model task"):
            _evidence(task_classes=frozenset({"coder"}))
        with self.assertRaisesRegex(ValueError, "unsupported model routing"):
            _evidence(routing_tools=frozenset({"shell"}))
        with self.assertRaisesRegex(ValueError, "context_window_tokens"):
            _evidence(context_window_tokens=0)

    def test_mapping_key_must_match_evidence_model(self):
        with self.assertRaisesRegex(ValueError, "mapping key"):
            OpenAICompatibleModelDriver({"model-b": _evidence()})

    def test_external_source_claims_require_a_reference(self):
        for source in ("benchmark", "provider_documentation"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "must cite at least one"):
                    _evidence(
                        evidence_sources=frozenset({source}),
                        evidence_refs=(),
                    )

        # maintainer_config is self-referencing and needs no external artifact.
        self.assertEqual(
            _evidence(
                evidence_sources=frozenset({"maintainer_config"}),
                evidence_refs=(),
            ).evidence_refs,
            (),
        )

    def test_probe_confirmation_needs_no_new_reference(self):
        evidence = _evidence(
            evidence_sources=frozenset({"maintainer_config"}),
            evidence_refs=(),
        )
        probe = OpenAICompatibleProbeResult(
            connection_id="model-main",
            status="healthy",
            configured_model="model-a",
            observed_models=("model-a",),
            model_available=True,
            warnings=(),
        )
        confirmed = confirm_model_identity(evidence, probe)
        self.assertIn("probe", confirmed.evidence_sources)
        self.assertEqual(confirmed.evidence_refs, ())


if __name__ == "__main__":
    unittest.main()
