"""Trusted enterprise IdP (OIDC/SAML/SSO) identity adapter for E3-C (#670).

E3-A (:mod:`idkmesh.enterprise_authz`) defines ``ActorContext`` and states
that it "must be produced by a trusted authentication adapter" and that
"issue text, WorkUnit text, provider/model output, labels, comments,
prompts, and ResultManifest content are not valid identity sources." This
module is that adapter for an enterprise identity provider reached through
OIDC, SAML, or another SSO protocol.

It turns two already-trusted inputs into an ``ActorContext``:

- :class:`OidcIdentityClaims` -- already-verified IdP claims (an OIDC ID
  token's ``iss``/``sub``/``aud``/``iat``/``exp``, or the equivalent
  normalized fields of a verified SAML assertion). Signature/assertion
  verification happens upstream, before this module ever sees a claim; it
  never re-derives trust from issue/PR/comment text or an unverified token.
  Nothing on ``main`` builds these claims from a live IdP response yet; that
  producer is E3-F scope, same as the GitHub claims producer left open by
  E3-B.
- :class:`OidcIdentityBindingTable` -- a maintainer-reviewed, versioned
  table binding each trusted ``(issuer, subject)`` pair to its
  ``ActorContext`` roles, tenant/project scopes, and data clearance. Unlike
  the GitHub adapter's single numeric actor id, a subject claim (``sub``) is
  only unique within its issuing IdP, so the composite ``(issuer, subject)``
  pair is the primary trust key here.

Resolution fails closed: claims already past their own ``exp`` are rejected
before any table lookup runs (an OIDC/SAML claim is an ephemeral per-session
credential with its own expiry, unlike a durable GitHub actor id); an
unbound ``(issuer, subject)`` pair, or claims whose ``aud`` does not match
the binding's configured relying-party audience, both raise
:class:`OidcIdentityAdapterError` rather than returning a partial or
best-effort identity. Revocation of the underlying identity
(``ActorContext.revoked``) is not re-checked here -- it is carried through on
the returned context and enforced once, by
:func:`idkmesh.enterprise_authz.authorize`, so this adapter and the kernel
cannot disagree about what "revoked" means.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from idkmesh.enterprise_authz import ActorContext
from idkmesh.tenant_scope import TenantScope

BINDING_TABLE_KIND = "idkmesh-enterprise-oidc-identity-binding-table"
BINDING_TABLE_VERSION = "0.1"

# Subset of idkmesh.enterprise_authz.ACTOR_TYPES that an enterprise IdP
# identity can actually be. "github_app", "github_actions", "provider", and
# "node" identities are not IdP-federated actors and are out of scope for
# this adapter.
OIDC_ACTOR_TYPES = frozenset({"human", "service"})

_BINDING_FIELDS = frozenset(
    {
        "issuer",
        "subject",
        "audience",
        "actor_type",
        "roles",
        "scopes",
        "data_clearance",
        "identity_revision",
        "revoked",
        "expires_at_epoch",
    }
)


class OidcIdentityAdapterError(ValueError):
    """Trusted IdP claims could not be resolved to a bound ActorContext."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> OidcIdentityAdapterError:
    return OidcIdentityAdapterError(code, path, message)


def _nonempty_str(value: Any, path: str) -> str:
    """Validate an opaque IdP identifier without normalizing it.

    ``issuer``, ``subject`` and ``audience`` are only ever compared, never
    parsed, so they must match byte for byte. Stripping instead of rejecting
    would fold every leading/trailing variant of the 29 code points
    ``str.strip()`` removes (TAB, NBSP, IDEOGRAPHIC SPACE, U+001F, ...) onto one
    bound identity, and ``audience`` is this adapter's anti-replay check.
    """

    if not isinstance(value, str) or not value:
        raise _fail("invalid_string", path, "must be a non-empty string")
    if value != value.strip():
        raise _fail(
            "invalid_string",
            path,
            "must not carry leading or trailing whitespace; an opaque IdP "
            "identifier is compared exactly",
        )
    if not value.isprintable():
        raise _fail(
            "unprintable_character",
            path,
            "must not contain unprintable characters; an identity string "
            "reaches audit evidence, so zero-width and bidirectional-override "
            "characters are refused rather than normalized",
        )
    return value


def _epoch(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("invalid_epoch", path, "must be an integer >= 0")
    return value


def oidc_principal_id(issuer: str, subject: str, actor_type: str) -> str:
    """Derive a stable ``ActorContext.principal_id`` for one IdP identity.

    ``issuer`` and ``subject`` are opaque IdP-controlled strings (a subject
    claim commonly contains characters like ``|`` or ``@`` that
    ``ActorContext``'s identifier charset rejects), so they cannot be
    interpolated into ``principal_id`` directly. Hashing the composite
    ``(issuer, subject)`` trust key keeps the result both charset-safe and
    stable across repeated resolutions of the same identity. The issuer is
    length-prefixed before hashing so the encoding is unambiguous for any
    input: an issuer/subject boundary shift cannot collide two distinct pairs
    onto the same digest, and that holds without depending on which characters
    ``ActorContext``'s identifier charset happens to exclude.
    """

    digest = hashlib.sha256(
        f"{len(issuer)}\x1f{issuer}{subject}".encode("utf-8")
    ).hexdigest()
    return f"oidc:{actor_type}:{digest}"


@dataclass(frozen=True, slots=True)
class OidcIdentityClaims:
    """Already-verified OIDC/SAML/SSO claims for one federated session.

    ``issued_at_epoch``/``expires_at_epoch`` are the claim's own ``iat``/
    ``exp`` (or a verified SAML assertion's equivalent validity window), not
    the long-lived identity's expiry -- that lives on the bound
    ``ActorContext`` and is a separate check performed by
    :func:`idkmesh.enterprise_authz.authorize`.
    """

    issuer: str
    subject: str
    audience: str
    issued_at_epoch: int
    expires_at_epoch: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "issuer", _nonempty_str(self.issuer, "issuer"))
        object.__setattr__(self, "subject", _nonempty_str(self.subject, "subject"))
        object.__setattr__(
            self, "audience", _nonempty_str(self.audience, "audience")
        )
        object.__setattr__(
            self,
            "issued_at_epoch",
            _epoch(self.issued_at_epoch, "issued_at_epoch"),
        )
        object.__setattr__(
            self,
            "expires_at_epoch",
            _epoch(self.expires_at_epoch, "expires_at_epoch"),
        )
        if self.expires_at_epoch <= self.issued_at_epoch:
            raise _fail(
                "invalid_expiry",
                "expires_at_epoch",
                "must be strictly after issued_at_epoch",
            )


@dataclass(frozen=True, slots=True)
class OidcIdentityBinding:
    """One maintainer-reviewed (issuer, subject) -> ActorContext binding."""

    issuer: str
    subject: str
    audience: str
    context: ActorContext

    def __post_init__(self) -> None:
        object.__setattr__(self, "issuer", _nonempty_str(self.issuer, "issuer"))
        object.__setattr__(self, "subject", _nonempty_str(self.subject, "subject"))
        object.__setattr__(
            self, "audience", _nonempty_str(self.audience, "audience")
        )
        if not isinstance(self.context, ActorContext):
            raise _fail("invalid_context", "context", "must be ActorContext")
        if self.context.actor_type not in OIDC_ACTOR_TYPES:
            raise _fail(
                "unsupported_actor_type",
                "context.actor_type",
                "enterprise IdP identity bindings must use one of: "
                + ", ".join(sorted(OIDC_ACTOR_TYPES)),
            )


@dataclass(frozen=True, slots=True)
class OidcIdentityBindingTable:
    """A reviewed, duplicate-free set of enterprise IdP identity bindings."""

    bindings: tuple[OidcIdentityBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise _fail("invalid_bindings", "bindings", "must be a non-empty tuple")
        if any(
            not isinstance(binding, OidcIdentityBinding)
            for binding in self.bindings
        ):
            raise _fail(
                "invalid_bindings",
                "bindings",
                "must contain OidcIdentityBinding values",
            )
        keys = [(binding.issuer, binding.subject) for binding in self.bindings]
        if len(keys) != len(set(keys)):
            raise _fail(
                "duplicate_subject",
                "bindings",
                "(issuer, subject) pairs must be unique",
            )

    def by_issuer_subject(
        self, issuer: str, subject: str
    ) -> OidcIdentityBinding | None:
        """Look a binding up by (issuer, subject), applying no trust check.

        This is table access, not authentication. The returned binding
        carries a complete ``ActorContext``, so using it directly skips the
        claim-expiry and audience checks that make a claim trustworthy.
        :func:`actor_context_from_oidc` is the only trust boundary in this
        module; call that instead unless you are inspecting the table
        itself.
        """

        return next(
            (
                binding
                for binding in self.bindings
                if binding.issuer == issuer and binding.subject == subject
            ),
            None,
        )


def actor_context_from_oidc(
    claims: OidcIdentityClaims,
    table: OidcIdentityBindingTable,
    *,
    now_epoch: int,
) -> ActorContext:
    """Resolve already-verified IdP claims to a reviewed ``ActorContext``.

    Fails closed with :class:`OidcIdentityAdapterError` for claims already
    expired at ``now_epoch``, an ``(issuer, subject)`` pair with no reviewed
    binding, or claims whose ``audience`` does not match the binding's
    configured relying-party audience. Revocation of the underlying identity
    is not evaluated here; it is carried on the returned ``ActorContext`` for
    :func:`idkmesh.enterprise_authz.authorize` to enforce.
    """

    if not isinstance(claims, OidcIdentityClaims):
        raise _fail("invalid_claims", "claims", "must be OidcIdentityClaims")
    if not isinstance(table, OidcIdentityBindingTable):
        raise _fail("invalid_table", "table", "must be OidcIdentityBindingTable")
    now_epoch = _epoch(now_epoch, "now_epoch")

    if now_epoch < claims.issued_at_epoch:
        raise _fail(
            "claims_not_yet_valid",
            "issued_at_epoch",
            "evaluation time precedes the claims' own issued_at_epoch, so "
            "either the caller's clock is stale or the claims are post-dated",
        )
    if now_epoch >= claims.expires_at_epoch:
        raise _fail(
            "claims_expired",
            "expires_at_epoch",
            "OIDC/SAML/SSO claims are expired",
        )

    binding = table.by_issuer_subject(claims.issuer, claims.subject)
    if binding is None:
        raise _fail(
            "unknown_subject",
            "subject",
            "no reviewed binding exists for this issuer/subject pair",
        )
    if binding.audience != claims.audience:
        raise _fail(
            "audience_mismatch",
            "audience",
            "claims audience does not match the bound relying-party audience",
        )
    return binding.context


def parse_identity_binding_table(value: Any) -> OidcIdentityBindingTable:
    """Parse a maintainer-reviewed binding-table document.

    Structural errors (missing/unknown fields, wrong ``kind``/
    ``schema_version``, an unsupported ``actor_type``, duplicate
    ``(issuer, subject)`` pairs) raise :class:`OidcIdentityAdapterError`.
    Field-level identity errors (an unknown role, an invalid data clearance,
    ...) are validated by :class:`idkmesh.enterprise_authz.ActorContext`
    itself and surface as
    :class:`idkmesh.enterprise_authz.AuthorizationContractError`, so the two
    contracts cannot silently drift apart.
    """

    if not isinstance(value, Mapping):
        raise _fail("invalid_type", "$", "binding table must be an object")
    top_fields = {"kind", "schema_version", "bindings"}
    missing = sorted(top_fields - set(value))
    if missing:
        raise _fail("missing_field", "$", "missing: " + ", ".join(missing))
    unknown = sorted(set(value) - top_fields)
    if unknown:
        raise _fail("unknown_field", f"$.{unknown[0]}", "unknown field")
    if value["kind"] != BINDING_TABLE_KIND:
        raise _fail("invalid_kind", "$.kind", f"must be {BINDING_TABLE_KIND!r}")
    if value["schema_version"] != BINDING_TABLE_VERSION:
        raise _fail(
            "unsupported_version",
            "$.schema_version",
            f"must be {BINDING_TABLE_VERSION!r}",
        )

    raw_bindings = value["bindings"]
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise _fail("invalid_bindings", "$.bindings", "must be a non-empty array")

    bindings: list[OidcIdentityBinding] = []
    for index, item in enumerate(raw_bindings):
        path = f"$.bindings[{index}]"
        if not isinstance(item, Mapping):
            raise _fail("invalid_type", path, "must be an object")
        item_missing = sorted(_BINDING_FIELDS - set(item))
        if item_missing:
            raise _fail(
                "missing_field", path, "missing: " + ", ".join(item_missing)
            )
        item_unknown = sorted(set(item) - _BINDING_FIELDS)
        if item_unknown:
            raise _fail(
                "unknown_field", f"{path}.{item_unknown[0]}", "unknown field"
            )

        actor_type = item["actor_type"]
        if actor_type not in OIDC_ACTOR_TYPES:
            raise _fail(
                "unsupported_actor_type",
                f"{path}.actor_type",
                "enterprise IdP identity bindings must use one of: "
                + ", ".join(sorted(OIDC_ACTOR_TYPES)),
            )

        raw_scopes = item["scopes"]
        if not isinstance(raw_scopes, list) or not raw_scopes:
            raise _fail(
                "invalid_scopes", f"{path}.scopes", "must be a non-empty array"
            )
        scopes: list[TenantScope] = []
        for scope_index, scope_item in enumerate(raw_scopes):
            if not isinstance(scope_item, Mapping) or set(scope_item) != {
                "tenant_id",
                "project_id",
            }:
                raise _fail(
                    "invalid_scope",
                    f"{path}.scopes[{scope_index}]",
                    "scope must contain only tenant_id and project_id",
                )
            scopes.append(
                TenantScope(
                    tenant_id=scope_item["tenant_id"],
                    project_id=scope_item["project_id"],
                )
            )

        issuer = _nonempty_str(item["issuer"], f"{path}.issuer")
        subject = _nonempty_str(item["subject"], f"{path}.subject")
        audience = _nonempty_str(item["audience"], f"{path}.audience")

        # Field-level identity errors (unknown role, invalid data clearance,
        # ...) are intentionally left to raise ActorContext's own
        # AuthorizationContractError unwrapped, so this contract cannot
        # silently drift from idkmesh.enterprise_authz's.
        context = ActorContext(
            principal_id=oidc_principal_id(issuer, subject, actor_type),
            actor_type=actor_type,
            issuer=issuer,
            roles=frozenset(item["roles"])
            if isinstance(item["roles"], list)
            else item["roles"],
            scopes=tuple(scopes),
            data_clearance=item["data_clearance"],
            identity_revision=item["identity_revision"],
            authenticated=True,
            revoked=item["revoked"],
            expires_at_epoch=item["expires_at_epoch"],
        )

        bindings.append(
            OidcIdentityBinding(
                issuer=issuer,
                subject=subject,
                audience=audience,
                context=context,
            )
        )

    return OidcIdentityBindingTable(bindings=tuple(bindings))
