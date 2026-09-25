"""Tests for the E3-C trusted enterprise IdP (OIDC/SAML/SSO) adapter (#670)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.enterprise_identity_oidc import (
    OidcIdentityAdapterError,
    OidcIdentityBinding,
    OidcIdentityBindingTable,
    OidcIdentityClaims,
    actor_context_from_oidc,
    oidc_principal_id,
    parse_identity_binding_table,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "enterprise-oidc-identity-binding-v0.1.schema.json"
EXAMPLE = ROOT / "examples" / "enterprise" / "oidc-identity-bindings.example.json"

ISSUER = "https://idp.example.com/"
SUBJECT = "auth0|maintainer-alice"
AUDIENCE = "idkmesh-enterprise-console"
NOW = 1790168400


def _context(
    principal=None,
    *,
    actor_type="human",
    roles=("worker",),
    scope=TenantScope("tenant-a", "project-main"),
    clearance="confidential",
    revoked=False,
    expires=None,
    revision="oidc-identity:1",
) -> ActorContext:
    return ActorContext(
        principal_id=principal
        if principal is not None
        else oidc_principal_id(ISSUER, SUBJECT, actor_type),
        actor_type=actor_type,
        issuer=ISSUER,
        roles=frozenset(roles),
        scopes=(scope,),
        data_clearance=clearance,
        identity_revision=revision,
        authenticated=True,
        revoked=revoked,
        expires_at_epoch=expires,
    )


def _claims(
    *,
    issuer=ISSUER,
    subject=SUBJECT,
    audience=AUDIENCE,
    issued_at=NOW - 300,
    expires_at=NOW + 300,
) -> OidcIdentityClaims:
    return OidcIdentityClaims(
        issuer=issuer,
        subject=subject,
        audience=audience,
        issued_at_epoch=issued_at,
        expires_at_epoch=expires_at,
    )


def _table(*bindings: OidcIdentityBinding) -> OidcIdentityBindingTable:
    if not bindings:
        bindings = (
            OidcIdentityBinding(
                issuer=ISSUER,
                subject=SUBJECT,
                audience=AUDIENCE,
                context=_context(),
            ),
        )
    return OidcIdentityBindingTable(bindings=bindings)


class OidcIdentityClaimsTests(unittest.TestCase):
    def test_rejects_empty_issuer(self):
        with self.assertRaises(OidcIdentityAdapterError):
            OidcIdentityClaims(
                issuer="  ",
                subject=SUBJECT,
                audience=AUDIENCE,
                issued_at_epoch=NOW,
                expires_at_epoch=NOW + 1,
            )

    def test_rejects_empty_subject(self):
        with self.assertRaises(OidcIdentityAdapterError):
            OidcIdentityClaims(
                issuer=ISSUER,
                subject="",
                audience=AUDIENCE,
                issued_at_epoch=NOW,
                expires_at_epoch=NOW + 1,
            )

    def test_rejects_negative_epoch(self):
        with self.assertRaises(OidcIdentityAdapterError):
            OidcIdentityClaims(
                issuer=ISSUER,
                subject=SUBJECT,
                audience=AUDIENCE,
                issued_at_epoch=-1,
                expires_at_epoch=NOW,
            )

    def test_rejects_expiry_not_after_issued_at(self):
        for issued, expires in ((NOW, NOW), (NOW, NOW - 1)):
            with self.subTest(issued=issued, expires=expires):
                with self.assertRaises(OidcIdentityAdapterError) as ctx:
                    OidcIdentityClaims(
                        issuer=ISSUER,
                        subject=SUBJECT,
                        audience=AUDIENCE,
                        issued_at_epoch=issued,
                        expires_at_epoch=expires,
                    )
                self.assertEqual(ctx.exception.code, "invalid_expiry")

    def test_strips_surrounding_whitespace(self):
        claims = OidcIdentityClaims(
            issuer="  " + ISSUER + "  ",
            subject="  " + SUBJECT + "  ",
            audience="  " + AUDIENCE + "  ",
            issued_at_epoch=NOW,
            expires_at_epoch=NOW + 1,
        )
        self.assertEqual(claims.issuer, ISSUER)
        self.assertEqual(claims.subject, SUBJECT)
        self.assertEqual(claims.audience, AUDIENCE)


class ActorContextFromOidcTests(unittest.TestCase):
    def test_known_human_subject_resolves_to_bound_context(self):
        table = _table()
        context = actor_context_from_oidc(_claims(), table, now_epoch=NOW)
        self.assertEqual(context.actor_type, "human")
        self.assertEqual(
            context.principal_id,
            oidc_principal_id(ISSUER, SUBJECT, "human"),
        )

    def test_known_service_subject_resolves(self):
        table = _table(
            OidcIdentityBinding(
                issuer=ISSUER,
                subject="service-account|billing-sync",
                audience="idkmesh-enterprise-service",
                context=_context(
                    principal="oidc:service:issuer:billing-sync",
                    actor_type="service",
                    roles=("worker",),
                    clearance="internal",
                ),
            )
        )
        claims = _claims(
            subject="service-account|billing-sync",
            audience="idkmesh-enterprise-service",
        )
        context = actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(context.actor_type, "service")

    def test_unknown_subject_is_denied(self):
        table = _table()
        claims = _claims(subject="auth0|nobody")
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(ctx.exception.code, "unknown_subject")

    def test_unknown_issuer_for_a_known_subject_is_denied(self):
        """The trust key is the (issuer, subject) pair, not subject alone.

        A subject string is only unique within its issuing IdP, so a claim
        naming a known subject under an unbound issuer must not resolve
        against a different issuer's binding for that same subject text.
        """

        table = _table()
        claims = _claims(issuer="https://a-different-idp.example.org/")
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(ctx.exception.code, "unknown_subject")

    def test_audience_mismatch_is_denied(self):
        table = _table()
        claims = _claims(audience="some-other-relying-party")
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(ctx.exception.code, "audience_mismatch")

    def test_claims_already_expired_are_denied_before_lookup(self):
        table = _table()
        claims = _claims(issued_at=NOW - 600, expires_at=NOW - 1)
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(ctx.exception.code, "claims_expired")

    def test_claims_expiring_exactly_at_now_are_denied(self):
        table = _table()
        claims = _claims(issued_at=NOW - 600, expires_at=NOW)
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            actor_context_from_oidc(claims, table, now_epoch=NOW)
        self.assertEqual(ctx.exception.code, "claims_expired")

    def test_revoked_binding_still_resolves_but_fails_in_authorize(self):
        scope = TenantScope("tenant-a", "project-main")
        table = _table(
            OidcIdentityBinding(
                issuer=ISSUER,
                subject=SUBJECT,
                audience=AUDIENCE,
                context=_context(scope=scope, revoked=True),
            )
        )
        context = actor_context_from_oidc(_claims(), table, now_epoch=NOW)
        self.assertTrue(context.revoked)

        request = AuthorizationRequest(
            request_id="request:1",
            scope=scope,
            resource=ScopedResourceRef(scope, "candidate", "candidate-1"),
            actor=context,
            action="claim",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=NOW,
        )
        decision = authorize(request, AuthorizationPolicy.enterprise_baseline())
        self.assertEqual(decision.effect, "deny")
        self.assertEqual(decision.code, "actor_revoked")

    def test_expired_identity_is_denied_by_authorize_at_evaluation_time(self):
        """Identity expiry (durable) is distinct from claims expiry (session).

        The claims here are still fresh at NOW, but the *bound identity's*
        expires_at_epoch has already passed -- enterprise_authz.authorize, not
        this adapter, is what must catch that.
        """

        scope = TenantScope("tenant-a", "project-main")
        table = _table(
            OidcIdentityBinding(
                issuer=ISSUER,
                subject=SUBJECT,
                audience=AUDIENCE,
                context=_context(scope=scope, expires=NOW - 1),
            )
        )
        context = actor_context_from_oidc(_claims(), table, now_epoch=NOW)
        request = AuthorizationRequest(
            request_id="request:1",
            scope=scope,
            resource=ScopedResourceRef(scope, "candidate", "candidate-1"),
            actor=context,
            action="claim",
            risk="low",
            data_classification="internal",
            evaluated_at_epoch=NOW,
        )
        decision = authorize(request, AuthorizationPolicy.enterprise_baseline())
        self.assertEqual(decision.effect, "deny")
        self.assertEqual(decision.code, "actor_expired")

    def test_rejects_wrong_type_claims_or_table(self):
        table = _table()
        claims = _claims()
        with self.assertRaises(OidcIdentityAdapterError):
            actor_context_from_oidc({"issuer": ISSUER}, table, now_epoch=NOW)
        with self.assertRaises(OidcIdentityAdapterError):
            actor_context_from_oidc(claims, {"bindings": []}, now_epoch=NOW)

    def test_rejects_invalid_now_epoch(self):
        table = _table()
        with self.assertRaises(OidcIdentityAdapterError):
            actor_context_from_oidc(_claims(), table, now_epoch=-1)


class OidcIdentityBindingTableTests(unittest.TestCase):
    def test_rejects_duplicate_issuer_subject_pairs(self):
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            OidcIdentityBindingTable(
                bindings=(
                    OidcIdentityBinding(
                        issuer=ISSUER,
                        subject=SUBJECT,
                        audience=AUDIENCE,
                        context=_context(),
                    ),
                    OidcIdentityBinding(
                        issuer=ISSUER,
                        subject=SUBJECT,
                        audience="a-different-audience",
                        context=_context(principal="oidc:human:x:y"),
                    ),
                )
            )
        self.assertEqual(ctx.exception.code, "duplicate_subject")

    def test_same_subject_under_different_issuers_is_allowed(self):
        table = OidcIdentityBindingTable(
            bindings=(
                OidcIdentityBinding(
                    issuer=ISSUER,
                    subject=SUBJECT,
                    audience=AUDIENCE,
                    context=_context(principal="oidc:human:a:s"),
                ),
                OidcIdentityBinding(
                    issuer="https://another-idp.example.net/",
                    subject=SUBJECT,
                    audience=AUDIENCE,
                    context=_context(principal="oidc:human:b:s"),
                ),
            )
        )
        self.assertIsNotNone(table.by_issuer_subject(ISSUER, SUBJECT))
        self.assertIsNotNone(
            table.by_issuer_subject("https://another-idp.example.net/", SUBJECT)
        )

    def test_rejects_empty_bindings(self):
        with self.assertRaises(OidcIdentityAdapterError):
            OidcIdentityBindingTable(bindings=())

    def test_binding_rejects_non_idp_actor_type(self):
        github_actions_context = ActorContext(
            principal_id="gha:x",
            actor_type="github_actions",
            issuer="github.com",
            roles=frozenset({"dispatcher"}),
            scopes=(TenantScope("tenant-a", "project-main"),),
            data_clearance="internal",
            identity_revision="rev:1",
        )
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            OidcIdentityBinding(
                issuer=ISSUER,
                subject=SUBJECT,
                audience=AUDIENCE,
                context=github_actions_context,
            )
        self.assertEqual(ctx.exception.code, "unsupported_actor_type")

    def test_by_issuer_subject_returns_none_for_unknown_pair(self):
        table = _table()
        self.assertIsNone(table.by_issuer_subject(ISSUER, "auth0|nobody"))


class ParseIdentityBindingTableTests(unittest.TestCase):
    def _document(self, **overrides):
        document = {
            "kind": "idkmesh-enterprise-oidc-identity-binding-table",
            "schema_version": "0.1",
            "bindings": [
                {
                    "issuer": ISSUER,
                    "subject": SUBJECT,
                    "audience": AUDIENCE,
                    "actor_type": "human",
                    "roles": ["owner"],
                    "scopes": [
                        {"tenant_id": "tenant-a", "project_id": "project-main"}
                    ],
                    "data_clearance": "restricted",
                    "identity_revision": "oidc-identity:1",
                    "revoked": False,
                    "expires_at_epoch": None,
                }
            ],
        }
        document.update(overrides)
        return document

    def test_round_trips_a_valid_document(self):
        table = parse_identity_binding_table(self._document())
        binding = table.by_issuer_subject(ISSUER, SUBJECT)
        self.assertIsNotNone(binding)
        self.assertEqual(binding.audience, AUDIENCE)
        self.assertEqual(binding.context.actor_type, "human")

    def test_rejects_missing_top_level_field(self):
        document = self._document()
        del document["schema_version"]
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "missing_field")

    def test_rejects_unknown_top_level_field(self):
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(extra="nope"))
        self.assertEqual(ctx.exception.code, "unknown_field")

    def test_rejects_wrong_kind(self):
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(kind="wrong"))
        self.assertEqual(ctx.exception.code, "invalid_kind")

    def test_rejects_unsupported_version(self):
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(schema_version="0.2"))
        self.assertEqual(ctx.exception.code, "unsupported_version")

    def test_rejects_empty_bindings_array(self):
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(bindings=[]))
        self.assertEqual(ctx.exception.code, "invalid_bindings")

    def test_rejects_duplicate_issuer_subject_pairs_in_document(self):
        document = self._document()
        document["bindings"] = document["bindings"] * 2
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "duplicate_subject")

    def test_rejects_non_idp_actor_type_in_document(self):
        document = self._document()
        document["bindings"][0]["actor_type"] = "github_actions"
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "unsupported_actor_type")

    def test_missing_binding_field_is_reported(self):
        document = self._document()
        del document["bindings"][0]["roles"]
        with self.assertRaises(OidcIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "missing_field")

    def test_unknown_role_propagates_as_authorization_contract_error(self):
        document = self._document()
        document["bindings"][0]["roles"] = ["made_up_role"]
        with self.assertRaises(AuthorizationContractError):
            parse_identity_binding_table(document)

    def test_invalid_data_clearance_propagates_as_authorization_contract_error(self):
        document = self._document()
        document["bindings"][0]["data_clearance"] = "top-secret"
        with self.assertRaises(AuthorizationContractError):
            parse_identity_binding_table(document)


@unittest.skipUnless(HAS_JSONSCHEMA, "schema validation requires jsonschema")
class CommittedExampleTests(unittest.TestCase):
    def test_example_validates_against_the_schema(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
        self.assertEqual([], [error.message for error in errors])

    def test_example_parses_into_a_working_binding_table(self):
        document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        table = parse_identity_binding_table(document)
        alice = table.by_issuer_subject(ISSUER, "auth0|maintainer-alice")
        self.assertIsNotNone(alice)
        self.assertEqual(alice.context.actor_type, "human")
        billing = table.by_issuer_subject(ISSUER, "service-account|billing-sync")
        self.assertIsNotNone(billing)
        self.assertEqual(billing.context.actor_type, "service")
        self.assertEqual(
            sorted(binding.context.actor_type for binding in table.bindings),
            ["human", "human", "service"],
            "the committed example must exercise every enterprise IdP actor "
            "type the schema accepts, so a declared-but-unused lane cannot "
            "go stale.",
        )


if __name__ == "__main__":
    unittest.main()
