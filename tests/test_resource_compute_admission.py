import copy
import datetime as dt
import unittest

from scripts.resource_compute_admission import AdmissionError, admit, validate_bindings

TODAY = dt.date(2026, 8, 28)


def registry():
    return {
        "version": 1,
        "observed_at": "2026-08-28",
        "offers": [
            {
                "id": "github-actions-public-standard",
                "status": "available",
                "kind": "compute",
                "capabilities": [
                    "git",
                    "python",
                    "docker",
                    "network",
                    "independent_verification",
                    "ephemeral_vm",
                ],
                "project_cost_usd": 0,
                "security": {"repo_write_authority": False, "merge_authority": False},
                "source": {"checked_at": "2026-08-28", "max_age_days": 30},
            },
            {
                "id": "gemini-api-free",
                "status": "conditional",
                "kind": "agent",
                "capabilities": ["llm", "code_analysis", "text_generation", "network"],
                "project_cost_usd": 0,
                "security": {"repo_write_authority": False, "merge_authority": False},
                "source": {"checked_at": "2026-08-28", "max_age_days": 14},
            },
        ],
    }


def bindings():
    return {
        "version": 1,
        "bindings": [
            {
                "id": "github-public-ci-v0",
                "resource_id": "github-actions-public-standard",
                "provider": "github-actions",
                "allowed_cost_classes": ["public_project_ci"],
                "required_resource_capabilities": ["git", "python", "ephemeral_vm"],
                "allowed_capabilities": [
                    "json-schema-validation",
                    "deterministic-local-execution",
                    "linux",
                    "python",
                ],
                "offer_id_prefix": "github-",
                "enabled": True,
                "terms_eligible": True,
                "authorization_scope": "legitimate public-repository CI/testing only",
                "reviewed_at": "2026-08-28",
                "max_age_days": 30,
            }
        ],
    }


def pool():
    return {
        "schema_version": "0.1",
        "offers": [
            {
                "id": "github-public-ci",
                "provider": "github-actions",
                "cost_class": "public_project_ci",
                "project_cost_usd": 0,
                "available": True,
                "trust": "trusted",
                "capabilities": [
                    "json-schema-validation",
                    "deterministic-local-execution",
                    "linux",
                    "python",
                ],
                "resources": {"cpu_cores": 2, "memory_mb": 7168, "disk_mb": 14000, "gpu": False},
                "expected_wait_seconds": 20,
                "success_probability": 0.98,
                "independence_group": "github-hosted",
            },
            {
                "id": "paid-cloud-fast",
                "provider": "generic-paid-cloud",
                "cost_class": "paid",
                "project_cost_usd": 0.04,
                "available": True,
                "trust": "attested",
                "capabilities": ["linux", "python"],
                "resources": {"cpu_cores": 16, "memory_mb": 65536, "disk_mb": 200000, "gpu": True},
                "expected_wait_seconds": 0,
                "success_probability": 0.999,
                "independence_group": "paid-cloud",
            },
        ],
    }


class ResourceComputeAdmissionTests(unittest.TestCase):
    def test_admits_fresh_bound_zero_cost_offer_only(self):
        admitted, report = admit(registry(), bindings(), pool(), TODAY)
        self.assertEqual([x["id"] for x in admitted["offers"]], ["github-public-ci"])
        self.assertEqual(report["admitted"][0]["resource_id"], "github-actions-public-standard")
        self.assertEqual(report["rejected"][0]["offer_id"], "paid-cloud-fast")

    def test_stale_registry_evidence_fails_closed(self):
        value = registry()
        value["offers"][0]["source"]["checked_at"] = "2026-06-01"
        admitted, report = admit(value, bindings(), pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("resource evidence stale", " ".join(report["rejected"][0]["reasons"]))

    def test_future_dated_registry_evidence_fails_closed(self):
        value = registry()
        value["offers"][0]["source"]["checked_at"] = "2026-08-29"
        admitted, report = admit(value, bindings(), pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("resource evidence future-dated", " ".join(report["rejected"][0]["reasons"]))

    def test_future_dated_registry_observation_fails_closed(self):
        value = registry()
        value["observed_at"] = "2026-08-29"
        with self.assertRaisesRegex(AdmissionError, "registry observed_at future-dated"):
            admit(value, bindings(), pool(), TODAY)

    def test_stale_local_binding_review_fails_closed(self):
        value = bindings()
        value["bindings"][0]["reviewed_at"] = "2026-06-01"
        admitted, report = admit(registry(), value, pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("binding review stale", " ".join(report["rejected"][0]["reasons"]))

    def test_future_dated_binding_review_fails_closed(self):
        value = bindings()
        value["bindings"][0]["reviewed_at"] = "2026-08-29"
        admitted, report = admit(registry(), value, pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("binding review future-dated", " ".join(report["rejected"][0]["reasons"]))

    def test_missing_required_resource_capability_fails_closed(self):
        value = registry()
        value["offers"][0]["capabilities"].remove("ephemeral_vm")
        admitted, report = admit(value, bindings(), pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn(
            "resource evidence missing required capabilities: ephemeral_vm",
            report["rejected"][0]["reasons"],
        )

    def test_capability_expansion_is_rejected(self):
        value = pool()
        value["offers"][0]["capabilities"].append("cuda")
        admitted, report = admit(registry(), bindings(), value, TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("capability exceeds binding allowlist", " ".join(report["rejected"][0]["reasons"]))

    def test_unavailable_offer_is_rejected(self):
        value = pool()
        value["offers"][0]["available"] = False
        admitted, report = admit(registry(), bindings(), value, TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("concrete offer unavailable", report["rejected"][0]["reasons"])

    def test_agent_resource_cannot_bind_as_direct_compute(self):
        value = bindings()
        value["bindings"][0]["resource_id"] = "gemini-api-free"
        admitted, report = admit(registry(), value, pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("bound resource is not a direct compute class", report["rejected"][0]["reasons"])

    def test_ambiguous_binding_is_rejected(self):
        value = bindings()
        second = copy.deepcopy(value["bindings"][0])
        second["id"] = "github-public-ci-v0-duplicate"
        value["bindings"].append(second)
        admitted, report = admit(registry(), value, pool(), TODAY)
        self.assertEqual(admitted["offers"], [])
        self.assertIn("ambiguous matching bindings", report["rejected"][0]["reasons"])

    def test_invalid_binding_fails_validation(self):
        value = bindings()
        value["bindings"][0]["terms_eligible"] = "yes"
        with self.assertRaises(AdmissionError):
            validate_bindings(value)

    def test_binding_requires_resource_capability_evidence(self):
        value = bindings()
        value["bindings"][0]["required_resource_capabilities"] = []
        with self.assertRaisesRegex(AdmissionError, "required_resource_capabilities required"):
            validate_bindings(value)


if __name__ == "__main__":
    unittest.main()
