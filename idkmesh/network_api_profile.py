"""Fail-closed security profile primitives for a non-loopback IDKMesh API.

Issue #743 (API-8). The served Control Tower is a loopback, read-only service
whose session token is a local boundary, not an identity. This module is the
dependency-free *enforcement library* a future network listener must call; it
is deliberately not wired into any listener, so importing it changes no served
behaviour. It provides:

- ``parse_network_profile``: strict validation of a declared deployment profile.
  A non-loopback bind is refused unless TLS is declared as terminated by a
  trusted proxy, an authentication adapter other than the local session token is
  named, the Host allowlist is explicit, and the limits are bounded.
- ``NetworkRequestGuard``: peer/proxy trust, ``X-Forwarded-For`` resolution,
  Host allowlist, Origin/CORS/CSRF policy and request-framing normalization
  (the request-smuggling assumptions a proxy and the backend must share).
- ``ServiceTokenVerifier``: digest-only bearer credential registry with
  constant-time comparison, expiry, bounded lifetime, rotation overlap and
  revocation. It produces a principal id, never an ``ActorContext``.
- ``RateLimiter``: bounded token buckets keyed by principal (or client address
  when unauthenticated) that fail closed when the key table is saturated.
- ``authorize_scope`` / ``append_authorization_audit``: map endpoint scopes to
  the existing enterprise authorization kernel and retain every decision.

It is not an identity provider and not an authorization policy. ``ActorContext``
must come from a trusted authentication adapter (#670) and policy evaluation
stays in ``enterprise_authz``. A valid profile is declared input; it is not
evidence that a proxy, TLS or an identity provider is actually deployed.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import threading
from typing import Any, Iterable, Mapping, Sequence

from idkmesh.enterprise_audit import AuditEventInput, LocalEnterpriseAuditLedger
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import ScopedResourceRef

PROFILE_KIND = "idkmesh-network-api-profile"
PROFILE_VERSION = "0.1"

TLS_MODES = frozenset({"loopback_plaintext", "trusted_proxy_terminated"})
AUTH_ADAPTERS = frozenset({"oidc", "mtls", "github_app", "service_token"})
# The loopback session token is named only so it can be refused by name.
LOCAL_SESSION_ADAPTER = "local_session_token"

MAX_BODY_BYTES_CEILING = 8 * 1024 * 1024
DEFAULT_MAX_BODY_BYTES = 1024 * 1024
MAX_FORWARDED_HOPS = 16
MAX_TRUSTED_PROXIES = 64
MAX_ALLOWED_HOSTS = 64
MAX_ALLOWED_ORIGINS = 64
MAX_TOKEN_LIFETIME_CEILING_SECONDS = 90 * 24 * 3600
MAX_BEARER_TOKEN_CHARS = 512
MIN_BEARER_TOKEN_CHARS = 32
MAX_RATE_KEYS_CEILING = 100_000

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Endpoint scope vocabulary from issue #743 -> enterprise kernel action. A scope
# the kernel cannot express maps to ``None`` and is denied rather than guessed:
# ``decisions:write`` needs a kernel action that does not exist yet (#740), and
# ``integration:*`` is ambiguous between the kernel's ``execute`` (run work) and
# ``integrate`` (merge), so neither is assumed.
SCOPE_ACTIONS: Mapping[str, str | None] = {
    "evidence:read": "read",
    "runs:read": "read",
    "connectors:read": "read",
    "connectors:dispatch": "dispatch",
    "decisions:write": None,
    "integration:propose": None,
    "integration:execute": None,
}

_HOST_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
    r"(?::[0-9]{1,5})?$"
)
_ORIGIN_RE = re.compile(
    r"^https://(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)(?::(?P<port>[0-9]{1,5}))?$"
)
_SECRET_REF_RE = re.compile(
    r"^(?:env|github_actions|vault|external_secret_manager):[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$"
)
_IDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}$")
_BEARER_RE = re.compile(r"^Bearer ([A-Za-z0-9._~+/=-]+)$")
_DIGITS_RE = re.compile(r"^[0-9]{1,12}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class NetworkProfileError(ValueError):
    """A profile, request or credential violated the network security profile."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _fail(code: str, message: str) -> NetworkProfileError:
    return NetworkProfileError(code, message)


# --------------------------------------------------------------------------- profile


def classify_bind_host(host: Any) -> str:
    """Return ``"loopback"`` or ``"non_loopback"``; raise on an unusable value.

    Wildcard binds (``0.0.0.0``, ``::``), any other IP literal and any hostname
    other than ``localhost`` are non-loopback: a name is not resolved here, so
    it cannot be proven to stay on the loopback interface.
    """
    if not isinstance(host, str) or not host or len(host) > 255:
        raise _fail("invalid_bind_host", "bind.host must be a non-empty string")
    if host.lower() == "localhost":
        return "loopback"
    try:
        return "loopback" if ipaddress.ip_address(host).is_loopback else "non_loopback"
    except ValueError:
        pass
    if _HOST_RE.fullmatch(host.lower()) is None or ":" in host:
        raise _fail("invalid_bind_host", "bind.host is neither an IP literal nor a host name")
    return "non_loopback"


def _exact_object(value: Any, path: str, required: frozenset[str], optional: frozenset[str] = frozenset()) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("invalid_type", f"{path} must be an object")
    keys = set(value)
    if any(not isinstance(k, str) for k in keys):
        raise _fail("invalid_type", f"{path} keys must be strings")
    missing = sorted(required - keys)
    if missing:
        raise _fail("missing_field", f"{path} is missing {', '.join(missing)}")
    unknown = sorted(keys - required - optional)
    if unknown:
        raise _fail("unknown_field", f"{path} has unknown field(s): {', '.join(unknown)}")
    return value


def _int_in(value: Any, path: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise _fail("invalid_value", f"{path} must be an integer in [{low}, {high}]")
    return value


def _bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _fail("invalid_type", f"{path} must be boolean")
    return value


def _str_list(value: Any, path: str, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > limit:
        raise _fail("invalid_type", f"{path} must be an array of at most {limit} strings")
    if any(not isinstance(item, str) for item in value):
        raise _fail("invalid_type", f"{path} must contain only strings")
    if len(set(value)) != len(value):
        raise _fail("duplicate_entry", f"{path} must not repeat entries")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    principal_requests_per_minute: int
    principal_burst: int
    anonymous_requests_per_minute: int
    anonymous_burst: int
    max_tracked_keys: int


@dataclass(frozen=True, slots=True)
class NetworkApiProfile:
    profile_id: str
    bind_host: str
    bind_port: int
    exposure: str
    tls_mode: str
    trusted_proxies: tuple[Any, ...]
    auth_adapter: str
    issuer: str
    token_registry_ref: str | None
    max_token_lifetime_seconds: int
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]
    max_body_bytes: int
    rate_limit: RateLimitConfig
    record_denials: bool = True
    break_glass_enabled: bool = False

    @property
    def is_network_exposed(self) -> bool:
        return self.exposure == "non_loopback"


def parse_network_profile(raw: Any) -> NetworkApiProfile:
    """Validate a declared profile; any violation raises ``NetworkProfileError``.

    Loopback profiles may keep the local session token. A non-loopback bind
    additionally requires every item below; none has a permissive default.
    """
    root = _exact_object(
        raw,
        "profile",
        frozenset({"kind", "schema_version", "profile_id", "bind", "tls", "authentication", "request_policy", "audit"}),
        frozenset({"secrets", "break_glass"}),
    )
    if root["kind"] != PROFILE_KIND:
        raise _fail("invalid_kind", f"kind must be {PROFILE_KIND}")
    if root["schema_version"] != PROFILE_VERSION:
        raise _fail("unsupported_version", f"schema_version must be {PROFILE_VERSION}")
    profile_id = root["profile_id"]
    if not isinstance(profile_id, str) or _IDENT_RE.fullmatch(profile_id) is None:
        raise _fail("invalid_identifier", "profile_id is not a valid identifier")

    bind = _exact_object(root["bind"], "bind", frozenset({"host", "port"}))
    exposure = classify_bind_host(bind["host"])
    port = _int_in(bind["port"], "bind.port", 1, 65535)

    tls = _exact_object(root["tls"], "tls", frozenset({"mode"}), frozenset({"trusted_proxies"}))
    tls_mode = tls["mode"]
    if not isinstance(tls_mode, str) or tls_mode not in TLS_MODES:
        # Native in-process TLS is not implemented; it is refused, not assumed.
        raise _fail("unsupported_tls_mode", f"tls.mode must be one of {sorted(TLS_MODES)}")
    proxies: tuple[Any, ...] = ()
    if tls_mode == "trusted_proxy_terminated":
        proxies = _parse_proxies(tls.get("trusted_proxies"))
    elif "trusted_proxies" in tls:
        raise _fail("proxy_without_termination", "trusted_proxies requires tls.mode trusted_proxy_terminated")
    if exposure == "non_loopback" and tls_mode != "trusted_proxy_terminated":
        raise _fail("tls_required", "a non-loopback bind requires TLS terminated by a trusted proxy")

    auth = _exact_object(
        root["authentication"],
        "authentication",
        frozenset({"adapter", "issuer", "credential_transport"}),
        frozenset({"max_token_lifetime_seconds"}),
    )
    adapter = auth["adapter"]
    if adapter == LOCAL_SESSION_ADAPTER:
        if exposure == "non_loopback":
            raise _fail(
                "session_token_not_authentication",
                "the local session token is not an identity and cannot authenticate a non-loopback service",
            )
    elif not isinstance(adapter, str) or adapter not in AUTH_ADAPTERS:
        raise _fail("unknown_auth_adapter", f"authentication.adapter must be one of {sorted(AUTH_ADAPTERS)}")
    issuer = auth["issuer"]
    if not isinstance(issuer, str) or _IDENT_RE.fullmatch(issuer) is None:
        raise _fail("invalid_identifier", "authentication.issuer is not a valid identifier")
    if auth["credential_transport"] != "authorization_header":
        # Ambient (cookie) credentials would need a CSRF-token design; refused.
        raise _fail("unsupported_credential_transport", "only authorization_header credentials are supported")
    lifetime = _int_in(
        auth.get("max_token_lifetime_seconds", 3600),
        "authentication.max_token_lifetime_seconds",
        1,
        MAX_TOKEN_LIFETIME_CEILING_SECONDS,
    )

    secrets_block = root.get("secrets", {})
    secrets_obj = _exact_object(secrets_block, "secrets", frozenset(), frozenset({"token_registry_ref"}))
    registry_ref = secrets_obj.get("token_registry_ref")
    if registry_ref is not None and (
        not isinstance(registry_ref, str) or _SECRET_REF_RE.fullmatch(registry_ref) is None
    ):
        raise _fail("literal_secret", "secrets.token_registry_ref must be a secret reference, never a value")
    if adapter == "service_token" and registry_ref is None:
        raise _fail("missing_secret_reference", "service_token authentication requires secrets.token_registry_ref")

    policy = _exact_object(
        root["request_policy"],
        "request_policy",
        frozenset({"allowed_hosts", "max_body_bytes", "rate_limit"}),
        frozenset({"allowed_origins"}),
    )
    hosts = _parse_hosts(policy["allowed_hosts"])
    if exposure == "non_loopback" and not hosts:
        raise _fail("host_allowlist_required", "a non-loopback bind requires an explicit Host allowlist")
    origins = _parse_origins(policy.get("allowed_origins", []))
    body = _int_in(policy["max_body_bytes"], "request_policy.max_body_bytes", 1, MAX_BODY_BYTES_CEILING)
    limits = _parse_rate_limit(policy["rate_limit"])

    audit = _exact_object(root["audit"], "audit", frozenset({"record_denials"}))
    if _bool(audit["record_denials"], "audit.record_denials") is not True:
        raise _fail("denials_must_be_audited", "audit.record_denials must be true")

    break_glass = root.get("break_glass", {"enabled": False})
    bg = _exact_object(break_glass, "break_glass", frozenset({"enabled"}))
    if _bool(bg["enabled"], "break_glass.enabled"):
        raise _fail("break_glass_unsupported", "break-glass is not implemented and cannot be enabled")

    return NetworkApiProfile(
        profile_id=profile_id,
        bind_host=bind["host"],
        bind_port=port,
        exposure=exposure,
        tls_mode=tls_mode,
        trusted_proxies=proxies,
        auth_adapter=adapter,
        issuer=issuer,
        token_registry_ref=registry_ref,
        max_token_lifetime_seconds=lifetime,
        allowed_hosts=hosts,
        allowed_origins=origins,
        max_body_bytes=body,
        rate_limit=limits,
    )


def _parse_proxies(value: Any) -> tuple[Any, ...]:
    entries = _str_list(value, "tls.trusted_proxies", MAX_TRUSTED_PROXIES)
    if not entries:
        raise _fail("trusted_proxies_required", "trusted_proxy_terminated requires at least one trusted proxy")
    networks = []
    for entry in entries:
        try:
            net = ipaddress.ip_network(entry, strict=True)
        except ValueError as exc:
            raise _fail("invalid_proxy", "a trusted proxy entry is not a CIDR or IP") from exc
        if net.prefixlen == 0:
            raise _fail("proxy_too_broad", "a trusted proxy range must not cover the whole address space")
        networks.append(net)
    return tuple(networks)


def _parse_hosts(value: Any) -> frozenset[str]:
    entries = _str_list(value, "request_policy.allowed_hosts", MAX_ALLOWED_HOSTS)
    for entry in entries:
        if entry != entry.lower() or _HOST_RE.fullmatch(entry) is None:
            raise _fail("invalid_host", "an allowed host must be a lowercase DNS name with optional port")
        _check_port(entry.partition(":")[2])
    return frozenset(entries)


def _check_port(port: str) -> None:
    if port and not (port.isascii() and 1 <= int(port) <= 65535):
        raise _fail("invalid_host", "port out of range")


def _parse_origins(value: Any) -> frozenset[str]:
    entries = _str_list(value, "request_policy.allowed_origins", MAX_ALLOWED_ORIGINS)
    for entry in entries:
        match = _ORIGIN_RE.fullmatch(entry)
        if match is None:
            raise _fail("invalid_origin", "an allowed origin must be an exact https origin (no wildcard, null, path)")
        _check_port(match.group("port") or "")
    return frozenset(entries)


def _parse_rate_limit(value: Any) -> RateLimitConfig:
    obj = _exact_object(
        value,
        "request_policy.rate_limit",
        frozenset({
            "principal_requests_per_minute",
            "principal_burst",
            "anonymous_requests_per_minute",
            "anonymous_burst",
            "max_tracked_keys",
        }),
    )
    return RateLimitConfig(
        principal_requests_per_minute=_int_in(obj["principal_requests_per_minute"], "rate_limit.principal_requests_per_minute", 1, 6000),
        principal_burst=_int_in(obj["principal_burst"], "rate_limit.principal_burst", 1, 1000),
        anonymous_requests_per_minute=_int_in(obj["anonymous_requests_per_minute"], "rate_limit.anonymous_requests_per_minute", 1, 600),
        anonymous_burst=_int_in(obj["anonymous_burst"], "rate_limit.anonymous_burst", 1, 100),
        max_tracked_keys=_int_in(obj["max_tracked_keys"], "rate_limit.max_tracked_keys", 16, MAX_RATE_KEYS_CEILING),
    )


# --------------------------------------------------------------------------- operator check report

CHECK_REPORT_KIND = "idkmesh-network-api-profile-check"
CHECK_REPORT_VERSION = "0.1"

# What ``parse_network_profile`` verifies (id, description). Printed by
# ``idkmesh api-network-profile check --explain`` so a green result is read as
# "the declaration is well formed", never as "the deployment is safe".
CHECKS_PERFORMED: tuple[tuple[str, str], ...] = (
    ("structure", "strict JSON object: kind, schema_version, no missing or unknown fields, correct types"),
    ("bind_exposure", "bind host classified loopback or non-loopback (names are never resolved, so a name is non-loopback)"),
    ("tls_termination", "a non-loopback bind declares TLS terminated by a trusted proxy; in-process TLS is refused; proxy ranges must not cover the whole address space"),
    ("auth_adapter", "a non-loopback bind names oidc, mtls, github_app or service_token; the local session token is refused by name"),
    ("credential_transport", "credentials travel only in the Authorization header"),
    ("secret_references", "the token registry is a secret reference (env:, github_actions:, vault:, external_secret_manager:), never a literal value"),
    ("host_allowlist", "a non-loopback bind has an explicit lowercase Host allowlist without wildcards"),
    ("cors_origins", "each allowed origin is an exact https origin: no wildcard, null, http or path"),
    ("bounded_limits", "body size, token lifetime and rate-limit values are present and within fixed ceilings"),
    ("denial_audit", "audit.record_denials is true"),
    ("break_glass", "break-glass cannot be enabled (it is not implemented)"),
)

# What a green result does NOT establish. Keep in step with the specification's
# "Not implemented" section.
CHECKS_NOT_PERFORMED: tuple[tuple[str, str], ...] = (
    ("listener_wiring", "no served listener calls the request guard, token verifier or rate limiter; nothing here starts or inspects a server"),
    ("tls_verification", "no certificate, proxy, DNS name or connection is contacted or verified; the profile only records the assumption"),
    ("identity_provider", "no identity provider or credential-to-ActorContext adapter exists or is checked"),
    ("secret_resolution", "secret references are checked for shape only; whether the secret exists or is strong is not checked"),
    ("per_process_state", "revocation and rate-limit state are per-process; sharing them across replicas is not implemented or checked"),
    ("authority_matrix", "the human decision to adopt the proposed endpoint authority matrix is not made or checked"),
    ("first_violation_only", "validation stops at the first violation; fix it and run the check again to see the next one"),
)


def _safe_reason_message(error: NetworkProfileError) -> str:
    """The library message, with operator-supplied names removed.

    Every other message is a fixed string. Unknown field names come from the
    file under test, so they are not echoed back.
    """
    if error.code == "unknown_field":
        return error.message.partition(": ")[0]
    return error.message


def check_network_profile(raw: Any, *, explain: bool = False) -> dict[str, Any]:
    """Validate a declared profile and describe the outcome; never raises.

    Pure and offline: no listener is started, no file, network or clock is
    touched, and no value from ``raw`` is echoed except a validated
    ``profile_id`` and the derived exposure summary. ``deployment_approval`` is
    always ``False``: a valid profile is declared input, not a deployment.
    """
    reason: dict[str, str] | None = None
    profile: dict[str, Any] | None = None
    try:
        parsed = parse_network_profile(raw)
    except NetworkProfileError as exc:
        reason = {"code": exc.code, "message": _safe_reason_message(exc)}
    except Exception:  # noqa: BLE001 - fail closed on any shape the parser did not anticipate
        reason = {"code": "unexpected_profile_shape", "message": "the profile could not be validated"}
    else:
        profile = {
            "allowed_host_count": len(parsed.allowed_hosts),
            "allowed_origin_count": len(parsed.allowed_origins),
            "auth_adapter": parsed.auth_adapter,
            "bind_port": parsed.bind_port,
            "exposure": parsed.exposure,
            "profile_id": parsed.profile_id,
            "tls_mode": parsed.tls_mode,
            "trusted_proxy_count": len(parsed.trusted_proxies),
        }
    report: dict[str, Any] = {
        "deployment_approval": False,
        "kind": CHECK_REPORT_KIND,
        "profile": profile,
        "reason": reason,
        "schema_version": CHECK_REPORT_VERSION,
        "status": "valid" if reason is None else "refused",
    }
    if explain:
        report["checks_not_performed"] = [{"id": i, "description": d} for i, d in CHECKS_NOT_PERFORMED]
        report["checks_performed"] = [{"id": i, "description": d} for i, d in CHECKS_PERFORMED]
    return report


def render_check_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"


def render_check_report_text(report: Mapping[str, Any]) -> str:
    lines = [f"network API profile: {str(report['status']).upper()}"]
    reason = report["reason"]
    if reason is not None:
        lines.append(f"reason: {reason['code']}: {reason['message']}")
    profile = report["profile"]
    if profile is not None:
        for key in sorted(profile):
            lines.append(f"{key}: {profile[key]}")
    lines.append(
        "a valid result means the declaration is well formed; it is not a deployment approval "
        "(run with --explain for the checks that are not performed)"
    )
    if "checks_performed" in report:
        lines.append("checks performed:")
        lines.extend(f"  - {c['id']}: {c['description']}" for c in report["checks_performed"])
        lines.append("checks NOT performed:")
        lines.extend(f"  - {c['id']}: {c['description']}" for c in report["checks_not_performed"])
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- request guard


@dataclass(frozen=True, slots=True)
class CorsDecision:
    allowed: bool
    headers: Mapping[str, str]


class NetworkRequestGuard:
    """Stateless request-level checks derived from one validated profile."""

    def __init__(self, profile: NetworkApiProfile) -> None:
        if not isinstance(profile, NetworkApiProfile):
            raise _fail("invalid_profile", "guard requires a validated NetworkApiProfile")
        self._profile = profile

    @property
    def profile(self) -> NetworkApiProfile:
        return self._profile

    def _is_trusted_proxy(self, address: Any) -> bool:
        return any(address in net for net in self._profile.trusted_proxies if net.version == address.version)

    @staticmethod
    def _ip(text: str) -> Any:
        try:
            return ipaddress.ip_address(text.strip())
        except ValueError as exc:
            raise _fail("invalid_address", "not an IP address") from exc

    def check_peer(self, peer_ip: str) -> None:
        """Reject direct connections that bypass the TLS-terminating proxy."""
        peer = self._ip(peer_ip)
        if self._profile.tls_mode == "trusted_proxy_terminated" and not self._is_trusted_proxy(peer):
            raise _fail("untrusted_peer", "connection did not come from a trusted proxy")

    def resolve_client_address(self, peer_ip: str, forwarded_for: Sequence[str] = ()) -> str:
        """Return the client address, trusting X-Forwarded-For only from trusted proxies.

        The chain is walked right to left; the first hop that is not a trusted
        proxy is the client, so a client cannot prepend a forged address.
        """
        peer = self._ip(peer_ip)
        if not self._is_trusted_proxy(peer):
            # Forwarded headers from an untrusted peer are ignored, never believed.
            return str(peer)
        hops: list[str] = []
        for header in forwarded_for:
            if not isinstance(header, str):
                raise _fail("invalid_forwarded_for", "X-Forwarded-For must be a string")
            hops.extend(part for part in header.split(","))
        if len(hops) > MAX_FORWARDED_HOPS:
            raise _fail("forwarded_chain_too_long", "X-Forwarded-For has too many hops")
        for text in reversed(hops):
            addr = self._ip(text)
            if not self._is_trusted_proxy(addr):
                return str(addr)
        return str(peer)

    def check_host(self, host_header: str | None) -> str:
        if not isinstance(host_header, str) or host_header != host_header.strip() or host_header != host_header.lower():
            raise _fail("host_not_allowed", "Host header missing or not normalized")
        if host_header not in self._profile.allowed_hosts:
            raise _fail("host_not_allowed", "Host header is not on the allowlist")
        return host_header

    def check_origin(
        self,
        method: str,
        host: str,
        origin: str | None,
        sec_fetch_site: str | None = None,
    ) -> CorsDecision:
        """Apply the CORS/CSRF policy. Cross-origin access is denied by default.

        Credentials travel only in the ``Authorization`` header (never ambient),
        which is why no CSRF token exists; the Origin check is the second layer
        for browsers. A request that declares itself cross-site is refused
        unless its Origin is explicitly allowlisted.
        """
        if not isinstance(method, str) or not method.isalpha() or not method.isupper():
            raise _fail("invalid_method", "method must be an upper-case token")
        if origin is None:
            if sec_fetch_site == "cross-site":
                raise _fail("origin_not_allowed", "cross-site request without Origin")
            return CorsDecision(True, {})
        if origin not in self._profile.allowed_origins:
            same_origin = origin == f"https://{host}" and host in self._profile.allowed_hosts
            if not same_origin:
                raise _fail("origin_not_allowed", "Origin is not allowlisted")
            return CorsDecision(True, {})
        return CorsDecision(
            True,
            {
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Max-Age": "600",
            },
        )

    def check_framing(self, headers: Iterable[tuple[str, str]]) -> int:
        """Normalize body framing and return the declared body length (0 if none).

        The backend rejects, rather than reinterprets, every shape that proxies
        and origins are known to disagree on: both Content-Length and
        Transfer-Encoding, repeated or list-valued Content-Length, signs, spaces
        and non-digits. Chunked bodies are unsupported by this profile.
        """
        lengths: list[str] = []
        for name, value in headers:
            lowered = name.lower()
            if lowered == "transfer-encoding":
                raise _fail("transfer_encoding_unsupported", "Transfer-Encoding is not accepted")
            if lowered == "content-length":
                lengths.append(value)
        if not lengths:
            return 0
        if len(lengths) != 1 or _DIGITS_RE.fullmatch(lengths[0]) is None:
            raise _fail("invalid_content_length", "Content-Length must appear once as plain digits")
        size = int(lengths[0])
        if size > self._profile.max_body_bytes:
            raise _fail("body_too_large", "request body exceeds the profile limit")
        return size


# --------------------------------------------------------------------------- credentials


def new_service_token() -> str:
    """Return a high-entropy bearer token; only its digest should be stored."""
    return secrets.token_urlsafe(32)


def digest_service_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_bearer(authorization: str | None) -> str:
    """Extract a bearer token or raise a uniform ``invalid_credentials`` error."""
    if authorization is None or len(authorization) > MAX_BEARER_TOKEN_CHARS + 7:
        raise _fail("invalid_credentials", "credentials rejected")
    match = _BEARER_RE.fullmatch(authorization)
    if match is None or not MIN_BEARER_TOKEN_CHARS <= len(match.group(1)) <= MAX_BEARER_TOKEN_CHARS:
        raise _fail("invalid_credentials", "credentials rejected")
    return match.group(1)


@dataclass(frozen=True, slots=True)
class ServiceTokenRecord:
    token_id: str
    principal_id: str
    digest_sha256: str
    not_before_epoch: int
    expires_at_epoch: int
    revoked: bool = False

    def __post_init__(self) -> None:
        for name in ("token_id", "principal_id"):
            if _IDENT_RE.fullmatch(getattr(self, name)) is None:
                raise _fail("invalid_identifier", f"{name} is not a valid identifier")
        if _HEX64_RE.fullmatch(self.digest_sha256) is None:
            raise _fail("invalid_digest", "digest_sha256 must be 64 lowercase hex characters")
        if type(self.not_before_epoch) is not int or type(self.expires_at_epoch) is not int:
            raise _fail("invalid_type", "validity bounds must be integers")
        if self.expires_at_epoch <= self.not_before_epoch:
            raise _fail("invalid_validity", "expires_at_epoch must be after not_before_epoch")
        if type(self.revoked) is not bool:
            raise _fail("invalid_type", "revoked must be boolean")


@dataclass(frozen=True, slots=True)
class TokenAuthentication:
    """A verified credential. Carries no token material and no authority."""

    token_id: str
    principal_id: str
    expires_at_epoch: int


class ServiceTokenVerifier:
    """Immutable digest registry. Rotation adds a record; revocation returns a new verifier."""

    def __init__(self, records: Sequence[ServiceTokenRecord], *, max_lifetime_seconds: int) -> None:
        _int_in(max_lifetime_seconds, "max_lifetime_seconds", 1, MAX_TOKEN_LIFETIME_CEILING_SECONDS)
        ids = [r.token_id for r in records]
        digests = [r.digest_sha256 for r in records]
        if len(set(ids)) != len(ids) or len(set(digests)) != len(digests):
            raise _fail("duplicate_token", "token ids and digests must be unique")
        for record in records:
            if record.expires_at_epoch - record.not_before_epoch > max_lifetime_seconds:
                raise _fail("lifetime_exceeded", f"token {record.token_id} exceeds the maximum lifetime")
        self._records = tuple(records)
        self._max_lifetime = max_lifetime_seconds

    def __repr__(self) -> str:  # never expose digests
        return f"ServiceTokenVerifier(records={len(self._records)})"

    def revoked(self, token_id: str) -> "ServiceTokenVerifier":
        if token_id not in {r.token_id for r in self._records}:
            raise _fail("unknown_token", "no such token id")
        return ServiceTokenVerifier(
            tuple(
                ServiceTokenRecord(r.token_id, r.principal_id, r.digest_sha256, r.not_before_epoch, r.expires_at_epoch, True)
                if r.token_id == token_id else r
                for r in self._records
            ),
            max_lifetime_seconds=self._max_lifetime,
        )

    def authenticate(self, token: str, now_epoch: int) -> TokenAuthentication:
        """Compare against every record in constant time, then judge the match."""
        presented = digest_service_token(token).encode("ascii")
        matched: ServiceTokenRecord | None = None
        for record in self._records:  # no early exit: timing is independent of the match position
            if hmac.compare_digest(presented, record.digest_sha256.encode("ascii")):
                matched = record
        if matched is None:
            raise _fail("invalid_credentials", "credentials rejected")
        if matched.revoked:
            raise _fail("credential_revoked", "credential has been revoked")
        if not matched.not_before_epoch <= now_epoch < matched.expires_at_epoch:
            raise _fail("credential_expired", "credential is outside its validity window")
        return TokenAuthentication(matched.token_id, matched.principal_id, matched.expires_at_epoch)


# --------------------------------------------------------------------------- rate limit


@dataclass(frozen=True, slots=True)
class RateDecision:
    allowed: bool
    retry_after_seconds: int
    reason: str = "ok"


def rate_limit_key(principal_id: str | None, client_address: str) -> str:
    """Authenticated callers are limited per principal, others per client address."""
    return f"p:{principal_id}" if principal_id is not None else f"ip:{client_address}"


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """Thread-safe token buckets with a hard cap on tracked keys.

    When the table is full only fully-refilled (idle) buckets are evicted. If
    none are, new keys are refused, so a flood of distinct source addresses
    cannot reset anyone's limit.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._buckets: "OrderedDict[str, _Bucket]" = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, authenticated: bool, now: float) -> RateDecision:
        per_minute, burst = (
            (self._config.principal_requests_per_minute, self._config.principal_burst)
            if authenticated
            else (self._config.anonymous_requests_per_minute, self._config.anonymous_burst)
        )
        rate = per_minute / 60.0
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._config.max_tracked_keys and not self._evict_idle(now, rate, burst):
                    return RateDecision(False, 1, "rate_limiter_saturated")
                bucket = _Bucket(float(burst), now)
                self._buckets[key] = bucket
            else:
                elapsed = max(0.0, now - bucket.updated)
                bucket.tokens = min(float(burst), bucket.tokens + elapsed * rate)
                bucket.updated = now
                self._buckets.move_to_end(key)
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return RateDecision(True, 0)
            wait = (1.0 - bucket.tokens) / rate
            return RateDecision(False, max(1, int(wait) + (0 if wait == int(wait) else 1)), "rate_limited")

    def _evict_idle(self, now: float, rate: float, burst: int) -> bool:
        for key, bucket in self._buckets.items():  # oldest first
            if min(float(burst), bucket.tokens + max(0.0, now - bucket.updated) * rate) >= burst:
                del self._buckets[key]
                return True
        return False


# --------------------------------------------------------------------------- authorization + audit


def authorize_scope(
    *,
    request_id: str,
    api_scope: str,
    actor: ActorContext,
    resource: ScopedResourceRef,
    policy: AuthorizationPolicy,
    now_epoch: int,
    data_classification: str = "internal",
    risk: str = "low",
) -> AuthorizationDecision:
    """Evaluate an endpoint scope through the enterprise kernel; deny what it cannot express."""
    if api_scope not in SCOPE_ACTIONS:
        raise _fail("unknown_scope", "endpoint scope is not part of the scope vocabulary")
    action = SCOPE_ACTIONS[api_scope]
    if action is None:
        raise _fail("scope_not_defined", f"{api_scope} has no enterprise kernel action; denied")
    return authorize(
        AuthorizationRequest(
            request_id=request_id,
            scope=resource.scope,
            resource=resource,
            actor=actor,
            action=action,
            risk=risk,
            data_classification=data_classification,
            evaluated_at_epoch=now_epoch,
        ),
        policy,
    )


def append_authorization_audit(
    ledger: LocalEnterpriseAuditLedger,
    *,
    actor: ActorContext,
    service: ActorContext,
    decision: AuthorizationDecision,
    occurred_at_epoch: int,
    resource_revision: str,
    served: bool,
) -> dict[str, Any]:
    """Retain one authorization decision, denials included, in the audit ledger."""
    if decision.effect == "deny":
        outcome = "denied"
    elif decision.effect == "requires_approval":
        outcome = "not_executed"
    else:
        outcome = "succeeded" if served else "not_executed"
    return ledger.append(
        AuditEventInput(
            occurred_at_epoch=occurred_at_epoch,
            actor=actor,
            service=service,
            decision=decision,
            resource_revision=resource_revision,
            outcome=outcome,
        )
    )
