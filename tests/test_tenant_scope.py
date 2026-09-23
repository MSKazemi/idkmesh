"""Tests for enterprise tenant/project scope primitives."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.tenant_scope import (
    ScopedMemoryStore,
    ScopedResourceRef,
    TenantIsolationError,
    TenantScope,
    assert_same_scope,
    parse_resource_ref,
    scoped_idempotency_key,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "enterprise-resource-ref-v0.1.schema.json"
ADVERSARIAL_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "enterprise_scope"
    / "cross-tenant-reference.json"
)
SUBSTITUTION_FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "enterprise_scope"
    / "tenant-id-substitution.json"
)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class TenantScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant_a = TenantScope("tenant-a", "project-main")
        self.tenant_b = TenantScope("tenant-b", "project-main")
        self.project_b = TenantScope("tenant-a", "project-other")

    def test_resource_identity_includes_tenant_and_project(self) -> None:
        ref_a = ScopedResourceRef(self.tenant_a, "run", "run-17")
        ref_tenant_b = ScopedResourceRef(self.tenant_b, "run", "run-17")
        ref_project_b = ScopedResourceRef(self.project_b, "run", "run-17")

        self.assertNotEqual(ref_a.storage_key, ref_tenant_b.storage_key)
        self.assertNotEqual(ref_a.storage_key, ref_project_b.storage_key)
        self.assertIn("/tenant/tenant-a/", ref_a.storage_key)
        self.assertIn("/project/project-main/", ref_a.storage_key)

    def test_idempotency_key_is_stable_and_scope_bound(self) -> None:
        first = scoped_idempotency_key(
            self.tenant_a,
            operation="dispatch",
            logical_key="issue-17",
            payload_digest=DIGEST_A,
        )
        repeated = scoped_idempotency_key(
            self.tenant_a,
            operation="dispatch",
            logical_key="issue-17",
            payload_digest=DIGEST_A,
        )
        other_tenant = scoped_idempotency_key(
            self.tenant_b,
            operation="dispatch",
            logical_key="issue-17",
            payload_digest=DIGEST_A,
        )
        other_project = scoped_idempotency_key(
            self.project_b,
            operation="dispatch",
            logical_key="issue-17",
            payload_digest=DIGEST_A,
        )
        changed_payload = scoped_idempotency_key(
            self.tenant_a,
            operation="dispatch",
            logical_key="issue-17",
            payload_digest=DIGEST_B,
        )

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, other_tenant)
        self.assertNotEqual(first, other_project)
        self.assertNotEqual(first, changed_payload)

    def test_same_resource_id_cannot_bleed_across_tenants(self) -> None:
        store = ScopedMemoryStore()
        store.put(self.tenant_a, "run", "run-17", {"owner": "a"})

        self.assertEqual(
            store.get(self.tenant_a, "run", "run-17"),
            {"owner": "a"},
        )
        self.assertIsNone(store.get(self.tenant_b, "run", "run-17"))
        self.assertIsNone(store.get(self.project_b, "run", "run-17"))

    def test_tenant_id_substitution_fails_ref_access_closed(self) -> None:
        store = ScopedMemoryStore()
        ref = store.put(
            self.tenant_a,
            "candidate",
            "candidate-1",
            {"sha": "abc"},
        )
        substituted = ScopedResourceRef(
            self.tenant_b,
            ref.resource_type,
            ref.resource_id,
        )

        with self.assertRaises(TenantIsolationError) as caught:
            store.get_ref(self.tenant_a, substituted)

        self.assertEqual(caught.exception.code, "scope_mismatch")
        self.assertEqual(caught.exception.path, "resource.scope")
        self.assertEqual(
            store.get_ref(self.tenant_a, ref),
            {"sha": "abc"},
        )

    def test_retained_cross_tenant_substitution_fixture_fails_closed(self) -> None:
        fixture = json.loads(ADVERSARIAL_PATH.read_text(encoding="utf-8"))
        caller = TenantScope(**fixture["caller_scope"])
        ref = parse_resource_ref(fixture["resource_ref"])

        with self.assertRaises(TenantIsolationError) as caught:
            assert_same_scope(caller, ref.scope, path="resource.scope")

        self.assertEqual(caught.exception.code, fixture["expected_error"])

    def test_adversarial_tenant_id_substitution_fixture_fails_closed(self) -> None:
        fixture = json.loads(SUBSTITUTION_FIXTURE_PATH.read_text(encoding="utf-8"))
        caller = TenantScope(**fixture["caller_scope"])
        substituted_ref = parse_resource_ref(fixture["attempted_substitution"])

        store = ScopedMemoryStore()
        original_ref = store.put(caller, substituted_ref.resource_type, substituted_ref.resource_id, {"data": "secret"})

        with self.assertRaises(TenantIsolationError) as caught:
            store.get_ref(caller, substituted_ref)

        self.assertEqual(caught.exception.code, fixture["expected_error"])
        self.assertEqual(store.get_ref(caller, original_ref), {"data": "secret"})

    def test_cross_tenant_delete_cannot_remove_resource(self) -> None:
        store = ScopedMemoryStore()
        ref = store.put(self.tenant_a, "run", "run-17", "value")

        with self.assertRaises(TenantIsolationError):
            store.delete_ref(self.tenant_b, ref)

        self.assertEqual(store.get_ref(self.tenant_a, ref), "value")

    def test_cross_tenant_update_fails_closed(self) -> None:
        store = ScopedMemoryStore()
        ref = store.put(self.tenant_a, "claim", "claim-42", {"status": "active"})

        with self.assertRaises(TenantIsolationError) as caught:
            store.put_ref(self.tenant_b, ref, {"status": "hijacked"})

        self.assertEqual(caught.exception.code, "scope_mismatch")
        self.assertEqual(
            store.get_ref(self.tenant_a, ref),
            {"status": "active"},
        )

    def test_cache_queue_audit_resources_have_tenant_scoped_keys(self) -> None:
        for resource_type in ("run", "claim", "audit", "cache", "queue"):
            ref = ScopedResourceRef(self.tenant_a, resource_type, "item-1")
            self.assertTrue(
                ref.storage_key.startswith(
                    f"idkmesh/scope/v1/tenant/{self.tenant_a.tenant_id}/project/{self.tenant_a.project_id}/resource/{resource_type}/"
                )
            )

    def test_scope_listing_returns_only_own_keyspace(self) -> None:
        store = ScopedMemoryStore()
        store.put(self.tenant_a, "run", "run-a", 1)
        store.put(self.tenant_b, "run", "run-b", 2)

        keys_a = store.keys_for_scope(self.tenant_a)
        keys_b = store.keys_for_scope(self.tenant_b)

        self.assertEqual(len(keys_a), 1)
        self.assertEqual(len(keys_b), 1)
        self.assertNotEqual(keys_a, keys_b)
        self.assertTrue(all("/tenant/tenant-a/" in key for key in keys_a))
        self.assertTrue(all("/tenant/tenant-b/" in key for key in keys_b))

    def test_store_instances_do_not_share_mutable_state(self) -> None:
        first = ScopedMemoryStore()
        second = ScopedMemoryStore()
        first.put(self.tenant_a, "run", "run-17", "value")

        self.assertIsNone(second.get(self.tenant_a, "run", "run-17"))

    def test_resource_ref_round_trip_is_strict(self) -> None:
        ref = ScopedResourceRef(self.tenant_a, "run", "run-17")
        parsed = parse_resource_ref(ref.to_dict())

        self.assertEqual(parsed, ref)

        bad = ref.to_dict()
        bad["tenant_id"] = "../tenant-b"
        with self.assertRaises(TenantIsolationError) as caught:
            parse_resource_ref(bad)
        self.assertEqual(caught.exception.code, "invalid_scope_id")

        unknown = ref.to_dict()
        unknown["admin"] = True
        with self.assertRaises(TenantIsolationError) as extra:
            parse_resource_ref(unknown)
        self.assertEqual(extra.exception.code, "unknown_field")

    def test_assert_same_scope_requires_exact_tenant_and_project(self) -> None:
        assert_same_scope(self.tenant_a, self.tenant_a)

        for other in (self.tenant_b, self.project_b):
            with self.subTest(other=other):
                with self.assertRaises(TenantIsolationError):
                    assert_same_scope(self.tenant_a, other)


@unittest.skipUnless(HAS_JSONSCHEMA, "schema validation requires jsonschema")
class TenantScopeSchemaTests(unittest.TestCase):
    def test_resource_ref_schema_matches_runtime_projection(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        ref = ScopedResourceRef(
            TenantScope("tenant-a", "project-main"),
            "run",
            "run-17",
        )
        Draft202012Validator(schema).validate(ref.to_dict())


if __name__ == "__main__":
    unittest.main()
