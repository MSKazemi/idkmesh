"""Tests for the fail-closed network API security profile (#743).

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh.enterprise_audit import LocalEnterpriseAuditLedger
from idkmesh.enterprise_authz import ActorContext, AuthorizationPolicy
from idkmesh.network_api_profile import (
    SCOPE_ACTIONS,
    NetworkApiProfile,
    NetworkProfileError,
    NetworkRequestGuard,
    RateLimitConfig,
    RateLimiter,
    ServiceTokenRecord,
    ServiceTokenVerifier,
    append_authorization_audit,
    authorize_scope,
    classify_bind_host,
    digest_service_token,
    new_service_token,
    parse_bearer,
    parse_network_profile,
    rate_limit_key,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

NOW = 1791406800


def network_profile() -> dict:
    return {
        "kind": "idkmesh-network-api-profile",
        "schema_version": "0.1",
        "profile_id": "team-api",
        "bind": {"host": "0.0.0.0", "port": 8443},
        "tls": {"mode": "trusted_proxy_terminated", "trusted_proxies": ["10.0.0.0/24", "fd00::/64"]},
        "authentication": {
            "adapter": "service_token",
            "issuer": "idkmesh.test",
            "credential_transport": "authorization_header",
            "max_token_lifetime_seconds": 3600,
        },
        "secrets": {"token_registry_ref": "env:IDKMESH_TOKEN_REGISTRY"},
        "request_policy": {
            "allowed_hosts": ["api.example.org"],
            "allowed_origins": ["https://ui.example.org"],
            "max_body_bytes": 65536,
            "rate_limit": {
                "principal_requests_per_minute": 60,
                "principal_burst": 5,
                "anonymous_requests_per_minute": 6,
                "anonymous_burst": 2,
                "max_tracked_keys": 16,
            },
        },
        "audit": {"record_denials": True},
    }


def loopback_profile() -> dict:
    raw = network_profile()
    raw["bind"] = {"host": "127.0.0.1", "port": 8765}
    raw["tls"] = {"mode": "loopback_plaintext"}
    raw["authentication"] = {
        "adapter": "local_session_token",
        "issuer": "idkmesh.local",
        "credential_transport": "authorization_header",
    }
    del raw["secrets"]
    raw["request_policy"]["allowed_hosts"] = []
    return raw


def mutated(path: tuple, value, base=None) -> dict:
    raw = copy.deepcopy(base or network_profile())
    node = raw
    for key in path[:-1]:
        node = node[key]
    if value is DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return raw


DELETE = object()


class ProfileValidationTests(unittest.TestCase):
    def code(self, raw) -> str:
        with self.assertRaises(NetworkProfileError) as ctx:
            parse_network_profile(raw)
        return ctx.exception.code

    def test_valid_network_profile_parses(self) -> None:
        profile = parse_network_profile(network_profile())
        self.assertIsInstance(profile, NetworkApiProfile)
        self.assertTrue(profile.is_network_exposed)
        self.assertEqual(profile.allowed_hosts, frozenset({"api.example.org"}))
        self.assertFalse(profile.break_glass_enabled)

    def test_loopback_profile_may_keep_session_token(self) -> None:
        profile = parse_network_profile(loopback_profile())
        self.assertFalse(profile.is_network_exposed)

    def test_bind_classification(self) -> None:
        for host in ("127.0.0.1", "::1", "localhost", "LOCALHOST", "127.5.5.5"):
            self.assertEqual(classify_bind_host(host), "loopback", host)
        for host in ("0.0.0.0", "::", "10.1.2.3", "api.example.org", "192.168.1.1"):
            self.assertEqual(classify_bind_host(host), "non_loopback", host)
        for bad in ("", None, 5, "bad host", "a" * 300, "exa_mple"):
            with self.assertRaises(NetworkProfileError):
                classify_bind_host(bad)

    def test_non_loopback_without_tls_is_refused(self) -> None:
        raw = mutated(("tls",), {"mode": "loopback_plaintext"})
        self.assertEqual(self.code(raw), "tls_required")

    def test_native_tls_is_not_assumed(self) -> None:
        self.assertEqual(self.code(mutated(("tls", "mode"), "native")), "unsupported_tls_mode")

    def test_session_token_is_not_authentication_on_network(self) -> None:
        raw = mutated(("authentication", "adapter"), "local_session_token")
        self.assertEqual(self.code(raw), "session_token_not_authentication")

    def test_unknown_adapter_and_cookie_transport_refused(self) -> None:
        self.assertEqual(self.code(mutated(("authentication", "adapter"), "none")), "unknown_auth_adapter")
        self.assertEqual(
            self.code(mutated(("authentication", "credential_transport"), "cookie")),
            "unsupported_credential_transport",
        )

    def test_non_loopback_requires_host_allowlist(self) -> None:
        self.assertEqual(self.code(mutated(("request_policy", "allowed_hosts"), [])), "host_allowlist_required")

    def test_host_allowlist_rejects_wildcards_and_garbage(self) -> None:
        for bad in ("*", "*.example.org", "API.example.org", "a b", "x/y", "h:99999", "h:0"):
            self.assertIn(
                self.code(mutated(("request_policy", "allowed_hosts"), [bad])),
                {"invalid_host"},
                bad,
            )

    def test_cors_wildcard_null_http_and_paths_refused(self) -> None:
        for bad in ("*", "null", "http://ui.example.org", "https://ui.example.org/x", "https://*.example.org", "https://u@h"):
            self.assertEqual(
                self.code(mutated(("request_policy", "allowed_origins"), [bad])), "invalid_origin", bad
            )

    def test_proxy_requirements(self) -> None:
        self.assertEqual(
            self.code(mutated(("tls", "trusted_proxies"), [])), "trusted_proxies_required"
        )
        self.assertEqual(self.code(mutated(("tls", "trusted_proxies"), ["0.0.0.0/0"])), "proxy_too_broad")
        self.assertEqual(self.code(mutated(("tls", "trusted_proxies"), ["::/0"])), "proxy_too_broad")
        self.assertEqual(self.code(mutated(("tls", "trusted_proxies"), ["not-an-ip"])), "invalid_proxy")
        self.assertEqual(self.code(mutated(("tls", "trusted_proxies"), ["10.0.0.1/24"])), "invalid_proxy")
        raw = loopback_profile()
        raw["tls"]["trusted_proxies"] = ["10.0.0.1"]
        self.assertEqual(self.code(raw), "proxy_without_termination")

    def test_literal_secret_is_refused(self) -> None:
        for bad in ("hunter2-literal-token-value", "sk-abc123", "env:", "env:bad value"):
            self.assertEqual(
                self.code(mutated(("secrets", "token_registry_ref"), bad)), "literal_secret", bad
            )
        self.assertEqual(self.code(mutated(("secrets",), {})), "missing_secret_reference")

    def test_limits_are_bounded(self) -> None:
        for value in (0, 8 * 1024 * 1024 + 1, True, "1024", -1, 1.5):
            self.assertEqual(
                self.code(mutated(("request_policy", "max_body_bytes"), value)), "invalid_value", value
            )
        for field in ("principal_burst", "anonymous_requests_per_minute", "max_tracked_keys"):
            self.assertEqual(
                self.code(mutated(("request_policy", "rate_limit", field), 10**9)), "invalid_value"
            )

    def test_denial_audit_and_break_glass_cannot_be_disabled(self) -> None:
        self.assertEqual(self.code(mutated(("audit", "record_denials"), False)), "denials_must_be_audited")
        raw = network_profile()
        raw["break_glass"] = {"enabled": True}
        self.assertEqual(self.code(raw), "break_glass_unsupported")

    def test_unknown_and_missing_fields_and_wrong_types_refused(self) -> None:
        self.assertEqual(self.code(mutated(("extra",), 1)), "unknown_field")
        self.assertEqual(self.code(mutated(("bind",), DELETE)), "missing_field")
        self.assertEqual(self.code("not an object"), "invalid_type")
        self.assertEqual(self.code(mutated(("kind",), "other")), "invalid_kind")
        self.assertEqual(self.code(mutated(("schema_version",), "9")), "unsupported_version")
        self.assertEqual(self.code(mutated(("bind", "port"), 70000)), "invalid_value")

    def test_duplicate_entries_refused(self) -> None:
        self.assertEqual(
            self.code(mutated(("request_policy", "allowed_hosts"), ["a.example.org", "a.example.org"])),
            "duplicate_entry",
        )


class RequestGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = NetworkRequestGuard(parse_network_profile(network_profile()))

    def code(self, fn, *args) -> str:
        with self.assertRaises(NetworkProfileError) as ctx:
            fn(*args)
        return ctx.exception.code

    def test_direct_connection_bypassing_proxy_is_refused(self) -> None:
        self.guard.check_peer("10.0.0.7")
        self.guard.check_peer("fd00::5")
        self.assertEqual(self.code(self.guard.check_peer, "203.0.113.9"), "untrusted_peer")
        self.assertEqual(self.code(self.guard.check_peer, "garbage"), "invalid_address")

    def test_forwarded_for_ignored_from_untrusted_peer(self) -> None:
        self.assertEqual(self.guard.resolve_client_address("203.0.113.9", ["198.51.100.1"]), "203.0.113.9")

    def test_forwarded_for_cannot_be_prepended_by_client(self) -> None:
        # client sent "1.1.1.1"; proxy appended the real peer 198.51.100.7
        self.assertEqual(
            self.guard.resolve_client_address("10.0.0.7", ["1.1.1.1, 198.51.100.7"]), "198.51.100.7"
        )
        self.assertEqual(
            self.guard.resolve_client_address("10.0.0.7", ["1.1.1.1", "198.51.100.7, 10.0.0.9"]),
            "198.51.100.7",
        )

    def test_forwarded_for_malformed_or_oversized_is_refused(self) -> None:
        self.assertEqual(
            self.code(self.guard.resolve_client_address, "10.0.0.7", ["not-an-ip"]), "invalid_address"
        )
        self.assertEqual(
            self.code(self.guard.resolve_client_address, "10.0.0.7", [",".join(["8.8.8.8"] * 17)]),
            "forwarded_chain_too_long",
        )
        self.assertEqual(
            self.code(self.guard.resolve_client_address, "10.0.0.7", [5]), "invalid_forwarded_for"
        )

    def test_forwarded_for_all_trusted_falls_back_to_peer(self) -> None:
        self.assertEqual(self.guard.resolve_client_address("10.0.0.7", ["10.0.0.8"]), "10.0.0.7")

    def test_host_allowlist(self) -> None:
        self.assertEqual(self.guard.check_host("api.example.org"), "api.example.org")
        for bad in (None, "", "API.example.org", "api.example.org ", "evil.example", "api.example.org:8443",
                    "api.example.org,evil.example", "localhost", "127.0.0.1"):
            self.assertEqual(self.code(self.guard.check_host, bad), "host_not_allowed", bad)

    def test_cross_origin_denied_by_default_and_allowlisted_origin_granted(self) -> None:
        host = "api.example.org"
        self.assertEqual(self.code(self.guard.check_origin, "POST", host, "https://evil.example"), "origin_not_allowed")
        self.assertEqual(self.code(self.guard.check_origin, "POST", host, "null"), "origin_not_allowed")
        self.assertEqual(self.code(self.guard.check_origin, "POST", host, "http://api.example.org"), "origin_not_allowed")
        self.assertEqual(self.code(self.guard.check_origin, "GET", host, None, "cross-site"), "origin_not_allowed")
        allowed = self.guard.check_origin("POST", host, "https://ui.example.org")
        self.assertEqual(allowed.headers["Access-Control-Allow-Origin"], "https://ui.example.org")
        self.assertEqual(allowed.headers["Vary"], "Origin")
        self.assertNotIn("Access-Control-Allow-Credentials", allowed.headers)
        self.assertNotEqual(allowed.headers["Access-Control-Allow-Origin"], "*")
        same = self.guard.check_origin("POST", host, "https://api.example.org")
        self.assertEqual(dict(same.headers), {})
        self.assertEqual(dict(self.guard.check_origin("POST", host, None).headers), {})
        self.assertEqual(self.code(self.guard.check_origin, "post", host, None), "invalid_method")

    def test_framing_smuggling_shapes_are_refused(self) -> None:
        g = self.guard.check_framing
        self.assertEqual(g([("Host", "x")]), 0)
        self.assertEqual(g([("content-length", "12")]), 12)
        for headers, code in (
            ([("Content-Length", "5"), ("Transfer-Encoding", "chunked")], "transfer_encoding_unsupported"),
            ([("Transfer-Encoding", "chunked")], "transfer_encoding_unsupported"),
            ([("Transfer-Encoding", " chunked")], "transfer_encoding_unsupported"),
            ([("Content-Length", "5"), ("content-length", "5")], "invalid_content_length"),
            ([("Content-Length", "5, 5")], "invalid_content_length"),
            ([("Content-Length", "+5")], "invalid_content_length"),
            ([("Content-Length", "-1")], "invalid_content_length"),
            ([("Content-Length", " 5")], "invalid_content_length"),
            ([("Content-Length", "0x10")], "invalid_content_length"),
            ([("Content-Length", "5\n")], "invalid_content_length"),
            ([("Content-Length", "٥")], "invalid_content_length"),
            ([("Content-Length", "")], "invalid_content_length"),
            ([("Content-Length", "65537")], "body_too_large"),
        ):
            self.assertEqual(self.code(g, headers), code, headers)


class BearerAndVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token = new_service_token()
        self.record = ServiceTokenRecord(
            "tok-1", "service:ci", digest_service_token(self.token), NOW - 10, NOW + 1000
        )
        self.verifier = ServiceTokenVerifier([self.record], max_lifetime_seconds=3600)

    def code(self, fn, *args) -> str:
        with self.assertRaises(NetworkProfileError) as ctx:
            fn(*args)
        return ctx.exception.code

    def test_valid_token_authenticates_without_exposing_material(self) -> None:
        auth = self.verifier.authenticate(self.token, NOW)
        self.assertEqual(auth.principal_id, "service:ci")
        self.assertNotIn(self.token, repr(auth))
        self.assertNotIn(self.record.digest_sha256, repr(self.verifier))

    def test_wrong_empty_padded_and_unicode_tokens_rejected_uniformly(self) -> None:
        for bad in ("", "x" * 43, self.token + " ", self.token[:-1], self.token.upper(), "é" * 40, "\x00" * 40):
            self.assertEqual(self.code(self.verifier.authenticate, bad, NOW), "invalid_credentials")

    def test_validity_window_enforced(self) -> None:
        self.assertEqual(self.code(self.verifier.authenticate, self.token, NOW - 11), "credential_expired")
        self.assertEqual(self.code(self.verifier.authenticate, self.token, NOW + 1000), "credential_expired")
        self.verifier.authenticate(self.token, NOW + 999)

    def test_revocation_is_immediate_and_non_mutating(self) -> None:
        revoked = self.verifier.revoked("tok-1")
        self.assertEqual(self.code(revoked.authenticate, self.token, NOW), "credential_revoked")
        self.verifier.authenticate(self.token, NOW)  # original value object unchanged
        self.assertEqual(self.code(self.verifier.revoked, "missing"), "unknown_token")

    def test_rotation_overlap_and_lifetime_cap(self) -> None:
        new = new_service_token()
        rotated = ServiceTokenVerifier(
            [self.record, ServiceTokenRecord("tok-2", "service:ci", digest_service_token(new), NOW, NOW + 2000)],
            max_lifetime_seconds=3600,
        )
        self.assertEqual(rotated.authenticate(new, NOW).token_id, "tok-2")
        self.assertEqual(rotated.authenticate(self.token, NOW).token_id, "tok-1")
        self.assertEqual(rotated.revoked("tok-1").authenticate(new, NOW).token_id, "tok-2")
        with self.assertRaises(NetworkProfileError) as ctx:
            ServiceTokenVerifier([self.record], max_lifetime_seconds=500)
        self.assertEqual(ctx.exception.code, "lifetime_exceeded")

    def test_registry_construction_is_validated(self) -> None:
        with self.assertRaises(NetworkProfileError):
            ServiceTokenVerifier([self.record, self.record], max_lifetime_seconds=3600)
        for kwargs in (
            dict(digest_sha256="ABC"),
            dict(digest_sha256="g" * 64),
            dict(expires_at_epoch=NOW - 100),
            dict(principal_id="bad principal"),
        ):
            base = dict(
                token_id="t", principal_id="p", digest_sha256="a" * 64, not_before_epoch=NOW, expires_at_epoch=NOW + 5
            )
            base.update(kwargs)
            with self.assertRaises(NetworkProfileError):
                ServiceTokenRecord(**base)

    def test_bearer_parsing(self) -> None:
        self.assertEqual(parse_bearer("Bearer " + self.token), self.token)
        for bad in (None, "", "bearer " + self.token, "Basic " + self.token, "Bearer", "Bearer " + "a" * 31,
                    "Bearer " + "a" * 600, "Bearer a b" + "c" * 40, "Bearer " + self.token + "\r\nX: y",
                    " Bearer " + self.token):
            self.assertEqual(self.code(parse_bearer, bad), "invalid_credentials", repr(bad)[:30])

    def test_comparison_visits_every_record_with_constant_time_primitive(self) -> None:
        records = [
            ServiceTokenRecord(f"tok-{i}", "service:ci", digest_service_token(f"t{i}" * 20), NOW, NOW + 100)
            for i in range(5)
        ]
        verifier = ServiceTokenVerifier(records, max_lifetime_seconds=3600)
        import idkmesh.network_api_profile as module

        with mock.patch.object(module.hmac, "compare_digest", wraps=module.hmac.compare_digest) as spy:
            verifier.authenticate("t0" * 20, NOW)  # match is the FIRST record
        self.assertEqual(spy.call_count, 5)


class RateLimiterTests(unittest.TestCase):
    def config(self, keys: int = 16) -> RateLimitConfig:
        return RateLimitConfig(60, 3, 6, 2, keys)

    def test_burst_then_refill(self) -> None:
        limiter = RateLimiter(self.config())
        for _ in range(3):
            self.assertTrue(limiter.check("p:a", True, 0.0).allowed)
        denied = limiter.check("p:a", True, 0.0)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reason, "rate_limited")
        self.assertEqual(denied.retry_after_seconds, 1)
        self.assertTrue(limiter.check("p:a", True, 1.0).allowed)

    def test_keys_are_independent_and_anonymous_is_stricter(self) -> None:
        limiter = RateLimiter(self.config())
        self.assertTrue(limiter.check("ip:1.1.1.1", False, 0).allowed)
        self.assertTrue(limiter.check("ip:1.1.1.1", False, 0).allowed)
        self.assertFalse(limiter.check("ip:1.1.1.1", False, 0).allowed)
        self.assertTrue(limiter.check("ip:2.2.2.2", False, 0).allowed)
        self.assertEqual(rate_limit_key("service:ci", "1.1.1.1"), "p:service:ci")
        self.assertEqual(rate_limit_key(None, "1.1.1.1"), "ip:1.1.1.1")

    def test_saturation_fails_closed_without_resetting_limits(self) -> None:
        limiter = RateLimiter(self.config(keys=16))
        for i in range(16):
            self.assertTrue(limiter.check(f"ip:{i}", False, 0).allowed)
        # table full of non-idle buckets: a new key is refused, not admitted by eviction
        refused = limiter.check("ip:new", False, 0)
        self.assertFalse(refused.allowed)
        self.assertEqual(refused.reason, "rate_limiter_saturated")
        # a victim near its limit is not reset by the flood
        self.assertTrue(limiter.check("ip:0", False, 0).allowed)
        self.assertFalse(limiter.check("ip:0", False, 0).allowed)
        # once buckets refill they are idle and may be evicted
        self.assertTrue(limiter.check("ip:new", False, 600).allowed)

    def test_clock_going_backwards_does_not_mint_tokens(self) -> None:
        limiter = RateLimiter(self.config())
        for _ in range(3):
            limiter.check("p:a", True, 100.0)
        self.assertFalse(limiter.check("p:a", True, 50.0).allowed)

    def test_thread_safety_never_exceeds_burst(self) -> None:
        limiter = RateLimiter(self.config())
        results: list[bool] = []

        def hit() -> None:
            results.append(limiter.check("p:shared", True, 0.0).allowed)

        threads = [threading.Thread(target=hit) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(results), 3)


class AuthorizationAndAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = TenantScope("tenant-a", "project-main")
        self.other = TenantScope("tenant-b", "project-main")
        self.policy = AuthorizationPolicy.enterprise_baseline()
        self.resource = ScopedResourceRef(self.scope, "run", "run-1")
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def actor(self, roles=("auditor",), scopes=None, actor_type="human", **kw) -> ActorContext:
        return ActorContext(
            principal_id="user:alice",
            actor_type=actor_type,
            issuer="idkmesh.test",
            roles=frozenset(roles),
            scopes=scopes or (self.scope,),
            data_clearance="restricted",
            identity_revision="identity:1",
            **kw,
        )

    def service(self) -> ActorContext:
        return ActorContext(
            principal_id="service:audit-writer",
            actor_type="service",
            issuer="idkmesh.test",
            roles=frozenset({"auditor"}),
            scopes=(self.scope,),
            data_clearance="restricted",
            identity_revision="identity:service:1",
        )

    def decide(self, scope_name, actor=None, resource=None):
        return authorize_scope(
            request_id="req:1",
            api_scope=scope_name,
            actor=actor or self.actor(),
            resource=resource or self.resource,
            policy=self.policy,
            now_epoch=NOW,
        )

    def test_scope_vocabulary_matches_kernel(self) -> None:
        from idkmesh.enterprise_authz import ACTIONS

        for scope, action in SCOPE_ACTIONS.items():
            self.assertTrue(action is None or action in ACTIONS, scope)
        self.assertEqual(
            set(SCOPE_ACTIONS),
            {"evidence:read", "runs:read", "decisions:write", "connectors:read",
             "connectors:dispatch", "integration:propose", "integration:execute"},
        )

    def test_read_scope_allows_bound_actor(self) -> None:
        self.assertEqual(self.decide("runs:read").effect, "allow")

    def test_inexpressible_and_unknown_scopes_fail_closed(self) -> None:
        for scope in ("decisions:write", "integration:propose", "integration:execute"):
            with self.assertRaises(NetworkProfileError) as ctx:
                self.decide(scope)
            self.assertEqual(ctx.exception.code, "scope_not_defined")
        with self.assertRaises(NetworkProfileError) as ctx:
            self.decide("admin:*")
        self.assertEqual(ctx.exception.code, "unknown_scope")

    def test_dispatch_requires_dispatcher_role(self) -> None:
        self.assertEqual(self.decide("connectors:dispatch").effect, "deny")
        self.assertEqual(
            self.decide("connectors:dispatch", actor=self.actor(roles=("dispatcher",))).effect, "allow"
        )

    def test_cross_tenant_actor_denied(self) -> None:
        decision = self.decide("runs:read", actor=self.actor(scopes=(self.other,)))
        self.assertEqual(decision.effect, "deny")

    def test_revoked_and_unauthenticated_denied(self) -> None:
        self.assertEqual(self.decide("runs:read", actor=self.actor(revoked=True)).effect, "deny")
        self.assertEqual(self.decide("runs:read", actor=self.actor(authenticated=False)).effect, "deny")
        self.assertEqual(
            self.decide("runs:read", actor=self.actor(expires_at_epoch=NOW)).effect, "deny"
        )

    def test_denials_are_retained_in_audit_ledger(self) -> None:
        path = Path(self.tmp.name) / "audit.sqlite3"
        with LocalEnterpriseAuditLedger(path) as ledger:
            denied_actor = self.actor(scopes=(self.other,))
            denied = self.decide("runs:read", actor=denied_actor)
            event = append_authorization_audit(
                ledger, actor=denied_actor, service=self.service(), decision=denied,
                occurred_at_epoch=NOW + 1, resource_revision="a" * 40, served=False,
            )
            self.assertEqual(event["outcome"], "denied")
            allowed = self.decide("runs:read")
            event2 = append_authorization_audit(
                ledger, actor=self.actor(), service=self.service(), decision=allowed,
                occurred_at_epoch=NOW + 2, resource_revision="a" * 40, served=True,
            )
            self.assertEqual(event2["outcome"], "succeeded")
            event3 = append_authorization_audit(
                ledger, actor=self.actor(), service=self.service(), decision=allowed,
                occurred_at_epoch=NOW + 3, resource_revision="a" * 40, served=False,
            )
            self.assertEqual(event3["outcome"], "not_executed")
            self.assertNotIn("token", str(event).lower().replace("tenant", ""))


if __name__ == "__main__":
    unittest.main()
