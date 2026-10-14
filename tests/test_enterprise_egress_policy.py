"""Tests for the E5 classified-egress policy and secret-reference contract (#672)."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from idkmesh.enterprise_authz import AuthorizationDecision
from idkmesh.enterprise_egress_policy import (
    EgressPolicyError,
    decide_classified_egress,
    load_egress_policy,
)
from idkmesh.enterprise_secret_reference import (
    SecretReferenceContractError,
    authorize_reference_use,
    parse_secret_reference,
    resolve_secret_alias,
    secret_access_audit_details,
)
from idkmesh.enterprise_secret_scan import scan_for_secrets

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text("utf-8"))


G1 = load("examples/enterprise/g1-github-native.example.json")
G2 = load("examples/enterprise/g2-self-hosted.example.json")
POLICY = load("examples/enterprise/egress-policy.example.json")

INTERNAL = "artifacts.corp.example"
PROVIDER = "api.provider-a.example"
PUBLIC = "packages.registry.example"


def profile(**overrides):
    """G2 profile with every class admitted; apply ``data`` overrides."""
    result = deepcopy(G2)
    for key, value in overrides.items():
        result["data"][key] = value
    return result


def with_provider_classes(classes, external=None):
    """Policy + profile where the provider destination lists ``classes``."""
    policy = deepcopy(POLICY)
    policy["destinations"][1]["allowed_classes"] = list(classes)
    prof = deepcopy(G2)
    for name in classes:
        prof["data"]["external_processing"][name] = (
            True if external is None else external
        )
    return prof, policy


def decide(prof, policy, host, data_class):
    return decide_classified_egress(
        prof, policy, destination_host=host, data_class=data_class
    )


class PolicyLoadTests(unittest.TestCase):
    def test_example_loads_and_digest_is_deterministic(self) -> None:
        first = load_egress_policy(POLICY)
        second = load_egress_policy(deepcopy(POLICY))
        self.assertEqual(first.digest, second.digest)
        self.assertTrue(first.digest.startswith("sha256:"))
        self.assertEqual(len(first.destinations), 3)

    def test_digest_changes_with_any_edit(self) -> None:
        edited = deepcopy(POLICY)
        edited["destinations"][1]["allowed_classes"] = ["public", "internal"]
        self.assertNotEqual(
            load_egress_policy(POLICY).digest, load_egress_policy(edited).digest
        )

    def test_matrix_is_policy_only_and_explicit(self) -> None:
        matrix = load_egress_policy(POLICY).matrix()
        self.assertEqual(
            matrix[PROVIDER],
            {"public": True, "internal": False, "confidential": False, "restricted": False},
        )
        self.assertTrue(all(matrix[INTERNAL].values()))

    def assert_rejected(self, mutate, code: str) -> None:
        document = deepcopy(POLICY)
        mutate(document)
        with self.assertRaises(EgressPolicyError) as ctx:
            load_egress_policy(document)
        self.assertEqual(ctx.exception.code, code)

    def test_structural_defects_are_rejected(self) -> None:
        cases = [
            (lambda d: d.update(kind="other"), "invalid_kind"),
            (lambda d: d.update(schema_version="9.9"), "invalid_version"),
            (lambda d: d.update(extra=1), "unknown_field"),
            (lambda d: d.pop("destinations"), "missing_field"),
            (lambda d: d.update(destinations=[]), "invalid_destinations"),
            (lambda d: d.update(destinations="x"), "invalid_destinations"),
            (lambda d: d["semantics"].update(grants_runtime_authority=True), "invalid_semantics"),
            (lambda d: d["semantics"].update(policy_role="enforcer"), "invalid_semantics"),
            (lambda d: d.update(policy_id="bad id"), "invalid_identifier"),
            (lambda d: d["destinations"][0].update(zone="dmz"), "invalid_zone"),
            (lambda d: d["destinations"][0].update(allowed_classes=[]), "invalid_classes"),
            (lambda d: d["destinations"][0].update(allowed_classes=["secret"]), "invalid_classes"),
            (lambda d: d["destinations"][0].update(allowed_classes=["public", "public"]), "invalid_classes"),
            (lambda d: d["destinations"][0].update(extra=1), "unknown_field"),
        ]
        for mutate, code in cases:
            with self.subTest(code=code):
                self.assert_rejected(mutate, code)

    def test_non_mapping_documents_are_rejected(self) -> None:
        for bad in (None, [], "policy", 7, {1: "x"}):
            with self.subTest(bad=bad):
                with self.assertRaises(EgressPolicyError):
                    load_egress_policy(bad)

    def test_hosts_must_be_exact_lowercase_fqdns(self) -> None:
        for host in (
            "*.corp.example", "https://a.corp.example", "a.corp.example:443",
            "user@a.corp.example", "A.Corp.Example", "a.corp.example.", "localhost",
            "10.0.0.1", "a b.corp.example", "", "a..corp.example", "-a.corp.example",
            "a.corp.example/path", "a.corp.1", 5, None,
        ):
            with self.subTest(host=host):
                self.assert_rejected(
                    lambda d, h=host: d["destinations"][0].update(host=h), "invalid_host"
                )

    def test_duplicate_ids_and_hosts_are_rejected(self) -> None:
        self.assert_rejected(
            lambda d: d["destinations"][1].update(destination_id="internal-artifact-store"),
            "duplicate_destination",
        )
        self.assert_rejected(
            lambda d: d["destinations"][1].update(host=INTERNAL), "duplicate_destination"
        )

    def test_provider_id_rules_follow_the_zone(self) -> None:
        self.assert_rejected(lambda d: d["destinations"][1].pop("provider_id"), "provider_required")
        self.assert_rejected(
            lambda d: d["destinations"][0].update(provider_id="provider-a"),
            "provider_not_allowed",
        )
        self.assert_rejected(
            lambda d: d["destinations"][1].update(provider_id="bad id"), "invalid_identifier"
        )

    def test_external_public_cannot_receive_non_public_data(self) -> None:
        for classes in (["internal"], ["public", "restricted"]):
            with self.subTest(classes=classes):
                self.assert_rejected(
                    lambda d, c=classes: d["destinations"][2].update(allowed_classes=c),
                    "external_public_requires_public_only",
                )

    def test_destination_count_is_bounded(self) -> None:
        document = deepcopy(POLICY)
        document["destinations"] = [
            {
                "destination_id": f"d{i}",
                "host": f"h{i}.corp.example",
                "zone": "internal",
                "allowed_classes": ["public"],
            }
            for i in range(257)
        ]
        with self.assertRaises(EgressPolicyError) as ctx:
            load_egress_policy(document)
        self.assertEqual(ctx.exception.code, "too_many_destinations")

    def test_a_raw_credential_in_the_policy_is_rejected_without_echo(self) -> None:
        token = "ghp_" + "a1B2c3D4" * 5
        document = deepcopy(POLICY)
        document["destinations"][0]["destination_id"] = "x"
        document["policy_id"] = "ok"
        document["semantics"]["note"] = token  # unknown field first
        with self.assertRaises(EgressPolicyError):
            load_egress_policy(document)
        # Credential in an otherwise-valid string field, e.g. the policy id.
        document = deepcopy(POLICY)
        document["policy_id"] = token
        with self.assertRaises(EgressPolicyError) as ctx:
            load_egress_policy(document)
        self.assertIn(ctx.exception.code, {"raw_secret_detected", "invalid_identifier"})
        self.assertNotIn(token, str(ctx.exception))


class ClassifiedEgressTests(unittest.TestCase):
    def test_internal_destination_receives_every_listed_class(self) -> None:
        for name in ("public", "internal", "confidential", "restricted"):
            with self.subTest(data_class=name):
                result = decide(G2, POLICY, INTERNAL, name)
                self.assertTrue(result.allowed, result.code)
                self.assertEqual(result.code, "classified_egress_allowed")

    def test_provider_destination_public_only_by_default(self) -> None:
        self.assertTrue(decide(G2, POLICY, PROVIDER, "public").allowed)
        for name in ("internal", "confidential", "restricted"):
            with self.subTest(data_class=name):
                result = decide(G2, POLICY, PROVIDER, name)
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "class_not_permitted_for_destination")

    def test_restricted_fails_closed_for_provider_when_profile_forbids(self) -> None:
        # The policy lists restricted for the provider, but the profile flag is
        # false: the profile still wins (no compensation across documents).
        prof, policy = with_provider_classes(["public", "restricted"], external=True)
        prof["data"]["external_processing"]["restricted"] = False
        result = decide(prof, policy, PROVIDER, "restricted")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "external_processing_forbidden")
        self.assertTrue(decide(prof, policy, PROVIDER, "public").allowed)

    def test_profile_flag_alone_does_not_clear_the_destination(self) -> None:
        prof = deepcopy(G2)
        prof["data"]["external_processing"]["confidential"] = True
        result = decide(prof, POLICY, PROVIDER, "confidential")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "class_not_permitted_for_destination")

    def test_eligibility_does_not_compensate_across_classes(self) -> None:
        prof, policy = with_provider_classes(["public", "internal", "confidential"])
        self.assertTrue(decide(prof, policy, PROVIDER, "confidential").allowed)
        self.assertFalse(decide(prof, policy, PROVIDER, "restricted").allowed)

    def test_external_public_destination_receives_public_only(self) -> None:
        self.assertTrue(decide(G2, POLICY, PUBLIC, "public").allowed)
        for name in ("internal", "confidential", "restricted"):
            with self.subTest(data_class=name):
                self.assertFalse(decide(G2, POLICY, PUBLIC, name).allowed)

    def test_unlisted_destination_is_denied_by_default(self) -> None:
        result = decide(G2, POLICY, "evil.example", "public")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "egress_denied_by_default")

    def test_lookalike_destinations_are_denied(self) -> None:
        for host in (
            "artifacts.corp.example.evil.example",
            "evil-artifacts.corp.example",
            "corp.example",
            "sub.artifacts.corp.example",
            "artifacts.corp.example:443",
            "https://artifacts.corp.example",
            "artifacts.corp.example/x",
            "user@artifacts.corp.example",
            "*.corp.example",
            "",
            None,
            7,
            "10.0.0.1",
        ):
            with self.subTest(host=host):
                self.assertFalse(decide(G2, POLICY, host, "public").allowed)

    def test_host_case_and_trailing_dot_normalise_to_the_same_destination(self) -> None:
        self.assertTrue(decide(G2, POLICY, "ARTIFACTS.Corp.Example.", "internal").allowed)

    def test_unknown_or_malformed_data_class_denies(self) -> None:
        for bad in ("top_secret", "", None, 3, ["public"], "PUBLIC"):
            with self.subTest(data_class=bad):
                result = decide(G2, POLICY, INTERNAL, bad)
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "unknown_data_class")

    def test_class_not_admitted_by_profile_denies_even_if_listed(self) -> None:
        prof = profile(allowed_classifications=["public", "internal"])
        prof["data"]["default_classification"] = "internal"
        result = decide(prof, POLICY, INTERNAL, "restricted")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "class_not_admitted")

    def test_open_egress_profile_admits_unlisted_hosts_for_public_only(self) -> None:
        prof = deepcopy(G1)
        prof["deployment"].update(
            profile="g0_local_operator",
            tenant_scope="single_project",
            remote_api_enabled=False,
            coordinator_lifecycle="local_process",
        )
        prof["identity"].update(
            human_source="local_trusted_operator", service_source="process"
        )
        prof["data"]["egress_default"] = "allow"
        verdict = decide(prof, POLICY, "elsewhere.example", "public")
        self.assertTrue(verdict.allowed, verdict.code)
        self.assertEqual(verdict.code, "egress_allowed_unlisted_public")
        for name in ("internal", "confidential", "restricted"):
            with self.subTest(data_class=name):
                other = decide(prof, POLICY, "elsewhere.example", name)
                self.assertFalse(other.allowed)
                self.assertEqual(other.code, "unlisted_destination_public_only")
        # Listed destinations keep their matrix even when egress is open.
        self.assertFalse(decide(prof, POLICY, PROVIDER, "internal").allowed)

    def test_invalid_profile_and_policy_deny(self) -> None:
        self.assertEqual(decide({}, POLICY, INTERNAL, "public").code, "invalid_profile")
        self.assertEqual(decide(None, POLICY, INTERNAL, "public").code, "invalid_profile")
        bad_policy = deepcopy(POLICY)
        bad_policy["destinations"][0]["host"] = "*.corp.example"
        self.assertEqual(
            decide(G2, bad_policy, INTERNAL, "public").code, "invalid_egress_policy"
        )
        self.assertEqual(decide(G2, None, INTERNAL, "public").code, "invalid_egress_policy")

    def test_decision_is_evidence_with_no_authority_and_binds_the_policy(self) -> None:
        result = decide(G2, POLICY, PROVIDER, "public").to_dict()
        self.assertEqual(result["effect"], "allow")
        self.assertEqual(result["destination_id"], "provider-a-api")
        self.assertEqual(result["policy_digest"], load_egress_policy(POLICY).digest)
        self.assertFalse(any(result["authority"].values()))
        self.assertTrue(scan_for_secrets(result).clean)
        denied = decide(G2, POLICY, "evil.example", "public").to_dict()
        self.assertEqual(denied["effect"], "deny")

    def test_decision_never_echoes_untrusted_destination_text(self) -> None:
        payload = "https://user:hunter2hunter2@evil.example/?k=ghp_" + "Z9" * 20
        serialized = json.dumps(decide(G2, POLICY, payload, "public").to_dict())
        self.assertNotIn("hunter2", serialized)
        self.assertNotIn("ghp_", serialized)

    def test_policy_mutation_after_load_cannot_widen_a_later_decision(self) -> None:
        policy = deepcopy(POLICY)
        self.assertFalse(decide(G2, policy, PROVIDER, "internal").allowed)
        policy["destinations"][1]["allowed_classes"].append("internal")
        # The raw document is revalidated on each call; widening the policy
        # still leaves the profile's external-processing flag false.
        result = decide(G2, policy, PROVIDER, "internal")
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, "external_processing_forbidden")


class SecretReferenceTests(unittest.TestCase):
    def test_supported_schemes_parse_with_fixed_backend_and_kind(self) -> None:
        cases = {
            "env:DEPLOY_TOKEN": ("environment", "environment_secret"),
            "gh-secret:DEPLOY_TOKEN": ("github_actions", "github_secret"),
            "secret:team/db/password": ("external_secret_manager", "secret_manager_reference"),
            "vault:kv/data/app": ("external_secret_manager", "secret_manager_reference"),
        }
        for text, (backend, kind) in cases.items():
            with self.subTest(ref=text):
                ref = parse_secret_reference(text)
                self.assertEqual(ref.canonical, text)
                self.assertEqual((ref.backend, ref.credential_kind), (backend, kind))

    def test_inline_secrets_and_malformed_values_are_refused_without_echo(self) -> None:
        token = "ghp_" + "a1B2c3D4" * 5
        values = [
            token,
            "sk-" + "A1b2C3d4" * 6,
            "hunter2",
            "",
            None,
            b"env:X",
            ["env:X"],
            "env:",
            "env: X",
            "env:1BAD",
            "env:A B",
            "env:A\nB",
            "vault:../etc/passwd",
            "vault:a//b",
            "vault:a/./b",
            "vault:/abs",
            "http://user:pw@host/",
            "env:" + "A" * 129,
        ]
        for value in values:
            with self.subTest(value=repr(value)[:20]):
                with self.assertRaises(SecretReferenceContractError) as ctx:
                    parse_secret_reference(value)
                message = str(ctx.exception)
                self.assertNotIn(token, message)
                self.assertNotIn("hunter2", message)

    def test_unknown_schemes_are_unsupported(self) -> None:
        for text in ("ref:thing", "file:/etc/shadow", "aws:key", "oidc:role", "ENV:X"):
            with self.subTest(ref=text):
                with self.assertRaises(SecretReferenceContractError):
                    parse_secret_reference(text)
        with self.assertRaises(SecretReferenceContractError) as ctx:
            parse_secret_reference("file:thing")
        self.assertEqual(ctx.exception.code, "unsupported_scheme")

    def test_credential_shaped_name_inside_a_reference_is_refused(self) -> None:
        token = "ghp_" + "a1B2c3D4" * 5
        with self.assertRaises(SecretReferenceContractError) as ctx:
            parse_secret_reference(f"env:{token}")
        self.assertEqual(ctx.exception.code, "inline_secret_forbidden")
        self.assertNotIn(token, str(ctx.exception))

    def test_alias_resolution_only_selects_among_trusted_bindings(self) -> None:
        bindings = {"deploy-key": "secret:team/deploy", "ci-token": "gh-secret:CI_TOKEN"}
        self.assertEqual(resolve_secret_alias(bindings, "deploy-key").canonical, "secret:team/deploy")
        for alias in ("missing", "env:ATTACKER_VAR", "vault:evil/path", "Deploy-Key", "", None, 5):
            with self.subTest(alias=alias):
                with self.assertRaises(SecretReferenceContractError):
                    resolve_secret_alias(bindings, alias)

    def test_alias_table_holding_a_raw_secret_is_refused_at_use(self) -> None:
        token = "ghp_" + "a1B2c3D4" * 5
        with self.assertRaises(SecretReferenceContractError) as ctx:
            resolve_secret_alias({"k": token}, "k")
        self.assertNotIn(token, str(ctx.exception))

    def test_bindings_must_be_a_bounded_mapping(self) -> None:
        with self.assertRaises(SecretReferenceContractError):
            resolve_secret_alias([("k", "env:X")], "k")  # type: ignore[arg-type]
        big = {f"a{i}": "env:X" for i in range(257)}
        with self.assertRaises(SecretReferenceContractError):
            resolve_secret_alias(big, "a1")


def authz(effect="allow", action="execute") -> AuthorizationDecision:
    return AuthorizationDecision(
        effect=effect, code="test", message="fixture", request_id="req-1",
        principal_id="github:user:alice", action=action, tenant_id="tenant-a",
        project_id="project-main", resource_type="secret", resource_id="ref-1",
        requested_risk="low", effective_risk="low", data_classification="internal",
        policy_id="policy-1", policy_revision="1", identity_revision="identity:1",
        evaluated_at_epoch=1790168400,
    )


class ReferenceAuthorizationTests(unittest.TestCase):
    def profile_with(self, backend: str, long_lived: bool = False) -> dict:
        prof = deepcopy(G2)
        prof["secrets"]["backend"] = backend
        prof["secrets"]["long_lived_cloud_keys_allowed"] = long_lived
        return prof

    def test_reference_is_usable_only_from_the_profile_backend(self) -> None:
        ref = parse_secret_reference("secret:team/db")
        ok = authorize_reference_use(
            self.profile_with("external_secret_manager"), ref, authorization=authz()
        )
        self.assertTrue(ok.allowed, ok.code)
        for backend in ("environment", "github_actions", "oidc_workload_identity", "none"):
            with self.subTest(backend=backend):
                denied = authorize_reference_use(
                    self.profile_with(backend), ref, authorization=authz()
                )
                self.assertFalse(denied.allowed)

    def test_env_reference_is_denied_under_workload_identity_profile(self) -> None:
        denied = authorize_reference_use(
            G2, parse_secret_reference("env:CLOUD_KEY"), authorization=authz()
        )
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.code, "untrusted_source_selection")

    def test_no_prior_allow_means_no_secret(self) -> None:
        prof = self.profile_with("environment")
        ref = parse_secret_reference("env:TOKEN")
        self.assertEqual(
            authorize_reference_use(prof, ref, authorization=None).code,
            "authorization_required",
        )
        self.assertEqual(
            authorize_reference_use(prof, ref, authorization=authz("deny")).code,
            "authorization_not_allowed",
        )
        self.assertEqual(
            authorize_reference_use(prof, ref, authorization=authz("requires_approval")).code,
            "authorization_not_allowed",
        )
        for action in ("read", "claim", "verify", "audit_export"):
            with self.subTest(action=action):
                self.assertEqual(
                    authorize_reference_use(prof, ref, authorization=authz(action=action)).code,
                    "authorization_action_not_permitted",
                )
        self.assertTrue(
            authorize_reference_use(prof, ref, authorization=authz(action="dispatch")).allowed
        )

    def test_non_reference_objects_are_refused(self) -> None:
        for bad in ("env:TOKEN", None, {"scheme": "env", "name": "TOKEN"}):
            with self.subTest(bad=bad):
                result = authorize_reference_use(G2, bad, authorization=authz())  # type: ignore[arg-type]
                self.assertFalse(result.allowed)
                self.assertEqual(result.code, "invalid_reference")

    def test_audit_details_are_identifier_only_and_scan_clean(self) -> None:
        prof = self.profile_with("environment")
        ref = parse_secret_reference("env:TOKEN")
        allowed = authorize_reference_use(prof, ref, authorization=authz())
        details = secret_access_audit_details(ref, allowed)
        self.assertEqual(details["secret_ref"], "env:TOKEN")
        self.assertEqual(details["effect"], "allow")
        self.assertIs(details["secret_value_read"], False)
        self.assertTrue(scan_for_secrets(details).clean)
        denied = authorize_reference_use(prof, ref, authorization=authz("deny"))
        self.assertEqual(secret_access_audit_details(ref, denied)["effect"], "deny")


try:
    import jsonschema
except ImportError:  # pragma: no cover - CI installs jsonschema
    jsonschema = None


@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class SchemaParityTests(unittest.TestCase):
    """The JSON Schema and the Python loader must agree on accept/reject."""

    SCHEMA = load("schemas/enterprise-egress-policy-v0.1.schema.json")

    def schema_accepts(self, document) -> bool:
        validator = jsonschema.Draft202012Validator(self.SCHEMA)
        return not list(validator.iter_errors(document))

    def python_accepts(self, document) -> bool:
        try:
            load_egress_policy(document)
        except EgressPolicyError:
            return False
        return True

    def test_example_is_accepted_by_both(self) -> None:
        self.assertTrue(self.schema_accepts(POLICY))
        self.assertTrue(self.python_accepts(POLICY))

    def test_mutations_agree(self) -> None:
        mutations = {
            "wildcard_host": lambda d: d["destinations"][0].update(host="*.corp.example"),
            "ip_host": lambda d: d["destinations"][0].update(host="10.0.0.1"),
            "uppercase_host": lambda d: d["destinations"][0].update(host="A.corp.example"),
            "bad_zone": lambda d: d["destinations"][0].update(zone="dmz"),
            "empty_classes": lambda d: d["destinations"][0].update(allowed_classes=[]),
            "dup_classes": lambda d: d["destinations"][0].update(allowed_classes=["public", "public"]),
            "provider_missing": lambda d: d["destinations"][1].pop("provider_id"),
            "provider_on_internal": lambda d: d["destinations"][0].update(provider_id="p"),
            "public_zone_non_public": lambda d: d["destinations"][2].update(allowed_classes=["internal"]),
            "authority_true": lambda d: d["semantics"].update(grants_runtime_authority=True),
            "extra_root": lambda d: d.update(extra=1),
            "extra_dest": lambda d: d["destinations"][0].update(extra=1),
            "no_destinations": lambda d: d.update(destinations=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                document = deepcopy(POLICY)
                mutate(document)
                self.assertFalse(self.schema_accepts(document), "schema accepted")
                self.assertFalse(self.python_accepts(document), "python accepted")


if __name__ == "__main__":
    unittest.main()
