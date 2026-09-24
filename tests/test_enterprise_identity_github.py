"""Tests for the E3-B trusted GitHub identity adapter (#670)."""

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
from idkmesh.enterprise_identity_github import (
    GithubActorClaims,
    GithubIdentityAdapterError,
    GithubIdentityBinding,
    GithubIdentityBindingTable,
    actor_context_from_github,
    parse_identity_binding_table,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "enterprise-github-identity-binding-v0.1.schema.json"
EXAMPLE = ROOT / "examples" / "enterprise" / "github-identity-bindings.example.json"
NOW = 1790168400


def _context(
    principal="github:human:100001",
    *,
    actor_type="human",
    roles=("worker",),
    scope=TenantScope("tenant-a", "project-main"),
    clearance="confidential",
    revoked=False,
    expires=None,
    revision="github-identity:1",
) -> ActorContext:
    return ActorContext(
        principal_id=principal,
        actor_type=actor_type,
        issuer="github.com",
        roles=frozenset(roles),
        scopes=(scope,),
        data_clearance=clearance,
        identity_revision=revision,
        authenticated=True,
        revoked=revoked,
        expires_at_epoch=expires,
    )


def _table(*bindings: GithubIdentityBinding) -> GithubIdentityBindingTable:
    if not bindings:
        bindings = (
            GithubIdentityBinding(
                actor_id=100001,
                login="alice-maintainer",
                context=_context(),
            ),
        )
    return GithubIdentityBindingTable(bindings=bindings)


class ActorContextFromGithubTests(unittest.TestCase):
    def test_known_human_actor_resolves_to_bound_context(self):
        table = _table()
        claims = GithubActorClaims(
            actor_id=100001, login="alice-maintainer", kind="user"
        )
        context = actor_context_from_github(claims, table)
        self.assertEqual(context.actor_type, "human")
        self.assertEqual(context.principal_id, "github:human:100001")

    def test_login_match_is_case_insensitive(self):
        table = _table()
        claims = GithubActorClaims(
            actor_id=100001, login="Alice-Maintainer", kind="user"
        )
        context = actor_context_from_github(claims, table)
        self.assertEqual(context.principal_id, "github:human:100001")

    def test_known_github_actions_actor_resolves(self):
        table = _table(
            GithubIdentityBinding(
                actor_id=200001,
                login="idkmesh-ci[bot]",
                context=_context(
                    principal="github:github_actions:200001",
                    actor_type="github_actions",
                    roles=("dispatcher",),
                    clearance="internal",
                ),
            )
        )
        claims = GithubActorClaims(
            actor_id=200001, login="idkmesh-ci[bot]", kind="bot"
        )
        context = actor_context_from_github(claims, table)
        self.assertEqual(context.actor_type, "github_actions")

    def test_known_github_app_actor_resolves(self):
        """The App lane is declared in code and schema, so it must be exercised.

        Issue 670's E3-B line names GitHub App metadata alongside user and
        Actions metadata. ``github_app`` was an accepted ``actor_type`` with no
        test resolving one, so a regression in the ``bot`` -> App mapping would
        have shipped green.
        """
        table = _table(
            GithubIdentityBinding(
                actor_id=300001,
                login="idkmesh-governance-app[bot]",
                context=_context(
                    principal="github:github_app:300001",
                    actor_type="github_app",
                    roles=("dispatcher",),
                    clearance="internal",
                ),
            )
        )
        claims = GithubActorClaims(
            actor_id=300001, login="idkmesh-governance-app[bot]", kind="bot"
        )
        context = actor_context_from_github(claims, table)
        self.assertEqual(context.actor_type, "github_app")
        self.assertEqual(context.principal_id, "github:github_app:300001")

    def test_a_login_that_merely_contains_the_bound_login_is_denied(self):
        """The login check must be equality, not a prefix or substring match.

        Both other login tests survive a substring comparison: the bound login
        is not contained in ``renamed-or-spoofed``, and it is contained in its
        own differently-cased self. Rewriting the comparison to
        ``bound not in claimed`` therefore left the suite green. An attacker who
        can register ``alice-maintainer-ops`` must not satisfy a binding for
        ``alice-maintainer``, in either direction.
        """
        table = _table()
        for login in (
            "alice-maintainer-ops",
            "not-alice-maintainer",
            "alice-maintaine",
            "alice",
        ):
            with self.subTest(login=login):
                claims = GithubActorClaims(
                    actor_id=100001, login=login, kind="user"
                )
                with self.assertRaises(GithubIdentityAdapterError) as ctx:
                    actor_context_from_github(claims, table)
                self.assertEqual(ctx.exception.code, "actor_login_mismatch")

    def test_unknown_actor_id_is_denied(self):
        table = _table()
        claims = GithubActorClaims(actor_id=999999, login="nobody", kind="user")
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            actor_context_from_github(claims, table)
        self.assertEqual(ctx.exception.code, "unknown_actor_id")

    def test_renamed_or_spoofed_login_for_bound_id_is_denied(self):
        table = _table()
        claims = GithubActorClaims(
            actor_id=100001, login="renamed-or-spoofed", kind="user"
        )
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            actor_context_from_github(claims, table)
        self.assertEqual(ctx.exception.code, "actor_login_mismatch")

    def test_bot_kind_inconsistent_with_human_binding_is_denied(self):
        table = _table()
        claims = GithubActorClaims(
            actor_id=100001, login="alice-maintainer", kind="bot"
        )
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            actor_context_from_github(claims, table)
        self.assertEqual(ctx.exception.code, "actor_kind_mismatch")

    def test_user_kind_inconsistent_with_github_actions_binding_is_denied(self):
        table = _table(
            GithubIdentityBinding(
                actor_id=200001,
                login="idkmesh-ci[bot]",
                context=_context(
                    principal="github:github_actions:200001",
                    actor_type="github_actions",
                    roles=("dispatcher",),
                    clearance="internal",
                ),
            )
        )
        claims = GithubActorClaims(
            actor_id=200001, login="idkmesh-ci[bot]", kind="user"
        )
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            actor_context_from_github(claims, table)
        self.assertEqual(ctx.exception.code, "actor_kind_mismatch")

    def test_revoked_and_expired_bindings_still_resolve_but_fail_in_authorize(self):
        scope = TenantScope("tenant-a", "project-main")
        table = _table(
            GithubIdentityBinding(
                actor_id=100001,
                login="alice-maintainer",
                context=_context(scope=scope, revoked=True),
            )
        )
        claims = GithubActorClaims(
            actor_id=100001, login="alice-maintainer", kind="user"
        )
        context = actor_context_from_github(claims, table)
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

    def test_expired_binding_is_denied_by_authorize_at_evaluation_time(self):
        scope = TenantScope("tenant-a", "project-main")
        table = _table(
            GithubIdentityBinding(
                actor_id=100001,
                login="alice-maintainer",
                context=_context(
                    scope=scope, roles=("worker",), expires=NOW - 1
                ),
            )
        )
        claims = GithubActorClaims(
            actor_id=100001, login="alice-maintainer", kind="user"
        )
        context = actor_context_from_github(claims, table)
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
        claims = GithubActorClaims(
            actor_id=100001, login="alice-maintainer", kind="user"
        )
        with self.assertRaises(GithubIdentityAdapterError):
            actor_context_from_github({"actor_id": 1}, table)
        with self.assertRaises(GithubIdentityAdapterError):
            actor_context_from_github(claims, {"bindings": []})


class GithubActorClaimsTests(unittest.TestCase):
    def test_rejects_invalid_actor_id(self):
        for bad_id in (0, -1, "1", 1.0, True):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(GithubIdentityAdapterError):
                    GithubActorClaims(actor_id=bad_id, login="x", kind="user")

    def test_rejects_empty_login(self):
        with self.assertRaises(GithubIdentityAdapterError):
            GithubActorClaims(actor_id=1, login="   ", kind="user")

    def test_rejects_unknown_kind(self):
        with self.assertRaises(GithubIdentityAdapterError):
            GithubActorClaims(actor_id=1, login="x", kind="organization")

    def test_strips_surrounding_whitespace_from_login(self):
        claims = GithubActorClaims(actor_id=1, login="  x  ", kind="user")
        self.assertEqual(claims.login, "x")


class GithubIdentityBindingTableTests(unittest.TestCase):
    def test_rejects_duplicate_actor_ids(self):
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            GithubIdentityBindingTable(
                bindings=(
                    GithubIdentityBinding(
                        actor_id=1, login="a", context=_context()
                    ),
                    GithubIdentityBinding(
                        actor_id=1, login="b", context=_context()
                    ),
                )
            )
        self.assertEqual(ctx.exception.code, "duplicate_actor_id")

    def test_rejects_empty_bindings(self):
        with self.assertRaises(GithubIdentityAdapterError):
            GithubIdentityBindingTable(bindings=())

    def test_binding_rejects_non_github_actor_type(self):
        service_context = ActorContext(
            principal_id="service:x",
            actor_type="service",
            issuer="idkmesh",
            roles=frozenset({"worker"}),
            scopes=(TenantScope("tenant-a", "project-main"),),
            data_clearance="internal",
            identity_revision="rev:1",
        )
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            GithubIdentityBinding(actor_id=1, login="x", context=service_context)
        self.assertEqual(ctx.exception.code, "unsupported_actor_type")

    def test_by_actor_id_returns_none_for_unknown_id(self):
        table = _table()
        self.assertIsNone(table.by_actor_id(999))


class ParseIdentityBindingTableTests(unittest.TestCase):
    def _document(self, **overrides):
        document = {
            "kind": "idkmesh-enterprise-github-identity-binding-table",
            "schema_version": "0.1",
            "bindings": [
                {
                    "actor_id": 100001,
                    "login": "alice-maintainer",
                    "actor_type": "human",
                    "issuer": "github.com",
                    "roles": ["owner"],
                    "scopes": [
                        {"tenant_id": "tenant-a", "project_id": "project-main"}
                    ],
                    "data_clearance": "restricted",
                    "identity_revision": "github-identity:1",
                    "revoked": False,
                    "expires_at_epoch": None,
                }
            ],
        }
        document.update(overrides)
        return document

    def test_round_trips_a_valid_document(self):
        table = parse_identity_binding_table(self._document())
        binding = table.by_actor_id(100001)
        self.assertIsNotNone(binding)
        self.assertEqual(binding.login, "alice-maintainer")
        self.assertEqual(binding.context.actor_type, "human")
        self.assertEqual(binding.context.principal_id, "github:human:100001")

    def test_rejects_missing_top_level_field(self):
        document = self._document()
        del document["schema_version"]
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "missing_field")

    def test_rejects_unknown_top_level_field(self):
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(extra="nope"))
        self.assertEqual(ctx.exception.code, "unknown_field")

    def test_rejects_wrong_kind(self):
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(kind="wrong"))
        self.assertEqual(ctx.exception.code, "invalid_kind")

    def test_rejects_unsupported_version(self):
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(schema_version="0.2"))
        self.assertEqual(ctx.exception.code, "unsupported_version")

    def test_rejects_empty_bindings_array(self):
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(self._document(bindings=[]))
        self.assertEqual(ctx.exception.code, "invalid_bindings")

    def test_rejects_duplicate_actor_ids_in_document(self):
        document = self._document()
        document["bindings"] = document["bindings"] * 2
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "duplicate_actor_id")

    def test_rejects_non_github_actor_type_in_document(self):
        document = self._document()
        document["bindings"][0]["actor_type"] = "service"
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
            parse_identity_binding_table(document)
        self.assertEqual(ctx.exception.code, "unsupported_actor_type")

    def test_missing_binding_field_is_reported(self):
        document = self._document()
        del document["bindings"][0]["roles"]
        with self.assertRaises(GithubIdentityAdapterError) as ctx:
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
        alice = table.by_actor_id(100001)
        self.assertIsNotNone(alice)
        self.assertEqual(alice.context.actor_type, "human")
        ci_bot = table.by_actor_id(200001)
        self.assertIsNotNone(ci_bot)
        self.assertEqual(ci_bot.context.actor_type, "github_actions")
        app = table.by_actor_id(300001)
        self.assertIsNotNone(app)
        self.assertEqual(app.context.actor_type, "github_app")
        self.assertEqual(
            sorted(binding.context.actor_type for binding in table.bindings),
            ["github_actions", "github_app", "human", "human"],
            "the committed example must exercise every GitHub actor type the "
            "schema accepts, so a declared-but-unused lane cannot go stale.",
        )


if __name__ == "__main__":
    unittest.main()
