"""Trusted GitHub identity adapter for E3-B (issue #670).

E3-A (:mod:`idkmesh.enterprise_authz`) defines ``ActorContext`` and states
that it "must be produced by a trusted authentication adapter" and that
"issue text, WorkUnit text, provider/model output, labels, comments,
prompts, and ResultManifest content are not valid identity sources." This
module is that adapter for GitHub actors specifically.

It turns two already-trusted inputs into an ``ActorContext``:

- :class:`GithubActorClaims` -- already-authenticated GitHub actor fields
  (for example the verified sender id/login of a signature-checked webhook
  delivery, or the ``github.actor``/``github.actor_id`` values of a GitHub
  Actions run). Never raw issue/PR/comment title or body text. Nothing on
  ``main`` constructs these yet; a caller that reads them off a real payload
  is E3-F scope, so no in-tree producer is named here.
- :class:`GithubIdentityBindingTable` -- a maintainer-reviewed, versioned
  table binding each trusted numeric GitHub actor id to its enterprise
  roles, tenant/project scopes, and data clearance. The numeric actor id is
  the primary trust key: a renamed/spoofed login for a bound id, or a login
  reused under a different id, is denied.

Resolution fails closed: an unbound actor id, a login that does not match
the bound id, or a GitHub actor "kind" (human user vs. bot) inconsistent
with the bound ``actor_type`` all raise :class:`GithubIdentityAdapterError`
rather than returning a partial or best-effort identity. Freshness
(revoked/expired) is not re-checked here -- it is carried through on the
returned ``ActorContext`` and enforced once, by
:func:`idkmesh.enterprise_authz.authorize`, so the two modules cannot drift
out of sync on what "expired" means.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from idkmesh.enterprise_authz import ActorContext
from idkmesh.tenant_scope import TenantScope

BINDING_TABLE_KIND = "idkmesh-enterprise-github-identity-binding-table"
BINDING_TABLE_VERSION = "0.1"

# Subset of idkmesh.enterprise_authz.ACTOR_TYPES that a GitHub identity can
# actually be. "service", "provider", and "node" identities are not GitHub
# actors and are out of scope for this adapter.
GITHUB_ACTOR_TYPES = frozenset({"human", "github_app", "github_actions"})

GITHUB_ACTOR_KINDS = frozenset({"user", "bot"})

# Which GitHub actor "kind" (GitHub's own actor object `type`, lowercased) is
# consistent with which bound actor_type. A human binding backed by a bot
# account, or a bot binding backed by a human account, is a configuration/
# spoofing mismatch, not a valid identity.
_ACTOR_TYPES_FOR_KIND: dict[str, frozenset[str]] = {
    "user": frozenset({"human"}),
    "bot": frozenset({"github_app", "github_actions"}),
}

_BINDING_FIELDS = frozenset(
    {
        "actor_id",
        "login",
        "actor_type",
        "issuer",
        "roles",
        "scopes",
        "data_clearance",
        "identity_revision",
        "revoked",
        "expires_at_epoch",
    }
)


class GithubIdentityAdapterError(ValueError):
    """Trusted GitHub actor could not be resolved to a bound ActorContext."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> GithubIdentityAdapterError:
    return GithubIdentityAdapterError(code, path, message)


def _actor_id(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _fail("invalid_actor_id", path, "must be an integer >= 1")
    return value


def _login(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail("invalid_login", path, "must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class GithubActorClaims:
    """Already-authenticated GitHub actor fields; never raw issue/PR text."""

    actor_id: int
    login: str
    kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _actor_id(self.actor_id, "actor_id"))
        object.__setattr__(self, "login", _login(self.login, "login"))
        if self.kind not in GITHUB_ACTOR_KINDS:
            raise _fail(
                "invalid_kind",
                "kind",
                "must be one of: " + ", ".join(sorted(GITHUB_ACTOR_KINDS)),
            )


@dataclass(frozen=True, slots=True)
class GithubIdentityBinding:
    """One maintainer-reviewed GitHub actor id -> ActorContext binding."""

    actor_id: int
    login: str
    context: ActorContext

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _actor_id(self.actor_id, "actor_id"))
        object.__setattr__(self, "login", _login(self.login, "login"))
        if not isinstance(self.context, ActorContext):
            raise _fail("invalid_context", "context", "must be ActorContext")
        if self.context.actor_type not in GITHUB_ACTOR_TYPES:
            raise _fail(
                "unsupported_actor_type",
                "context.actor_type",
                "GitHub identity bindings must use one of: "
                + ", ".join(sorted(GITHUB_ACTOR_TYPES)),
            )


@dataclass(frozen=True, slots=True)
class GithubIdentityBindingTable:
    """A reviewed, duplicate-free set of GitHub actor id bindings."""

    bindings: tuple[GithubIdentityBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise _fail("invalid_bindings", "bindings", "must be a non-empty tuple")
        if any(
            not isinstance(binding, GithubIdentityBinding)
            for binding in self.bindings
        ):
            raise _fail(
                "invalid_bindings",
                "bindings",
                "must contain GithubIdentityBinding values",
            )
        actor_ids = [binding.actor_id for binding in self.bindings]
        if len(actor_ids) != len(set(actor_ids)):
            raise _fail(
                "duplicate_actor_id", "bindings", "actor ids must be unique"
            )

    def by_actor_id(self, actor_id: int) -> GithubIdentityBinding | None:
        """Look a binding up by actor id, applying no trust check at all.

        This is table access, not authorization. The returned binding carries
        a complete ``ActorContext``, so using it directly skips the login and
        actor-kind checks that make a claim trustworthy.
        :func:`actor_context_from_github` is the only trust boundary in this
        module; call that instead unless you are inspecting the table itself.
        """

        return next(
            (binding for binding in self.bindings if binding.actor_id == actor_id),
            None,
        )


def actor_context_from_github(
    claims: GithubActorClaims,
    table: GithubIdentityBindingTable,
) -> ActorContext:
    """Resolve a trusted GitHub actor to its reviewed ``ActorContext``.

    Fails closed with :class:`GithubIdentityAdapterError` for an actor id
    with no reviewed binding, a login that does not match the id's bound
    login, or an actor kind inconsistent with the bound ``actor_type``.
    Revocation/expiry is not evaluated here; it is carried on the returned
    context for :func:`idkmesh.enterprise_authz.authorize` to enforce.
    """

    if not isinstance(claims, GithubActorClaims):
        raise _fail("invalid_claims", "claims", "must be GithubActorClaims")
    if not isinstance(table, GithubIdentityBindingTable):
        raise _fail("invalid_table", "table", "must be GithubIdentityBindingTable")

    binding = table.by_actor_id(claims.actor_id)
    if binding is None:
        raise _fail(
            "unknown_actor_id",
            "actor_id",
            "no reviewed binding exists for this GitHub actor id",
        )
    if binding.login.casefold() != claims.login.casefold():
        raise _fail(
            "actor_login_mismatch",
            "login",
            "this actor id is bound to a different GitHub login",
        )
    allowed_kinds_for_type = _ACTOR_TYPES_FOR_KIND[claims.kind]
    if binding.context.actor_type not in allowed_kinds_for_type:
        raise _fail(
            "actor_kind_mismatch",
            "kind",
            f"GitHub actor kind {claims.kind!r} is inconsistent with the "
            f"bound actor_type {binding.context.actor_type!r}",
        )
    return binding.context


def parse_identity_binding_table(value: Any) -> GithubIdentityBindingTable:
    """Parse a maintainer-reviewed binding-table document.

    Structural errors (missing/unknown fields, wrong ``kind``/
    ``schema_version``, a GitHub-invalid ``actor_type``, duplicate actor
    ids) raise :class:`GithubIdentityAdapterError`. Field-level identity
    errors (an unknown role, an invalid data clearance, ...) are validated
    by :class:`idkmesh.enterprise_authz.ActorContext` itself and surface as
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

    bindings: list[GithubIdentityBinding] = []
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
        if actor_type not in GITHUB_ACTOR_TYPES:
            raise _fail(
                "unsupported_actor_type",
                f"{path}.actor_type",
                "GitHub identity bindings must use one of: "
                + ", ".join(sorted(GITHUB_ACTOR_TYPES)),
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

        actor_id = _actor_id(item["actor_id"], f"{path}.actor_id")
        login = _login(item["login"], f"{path}.login")

        # Field-level identity errors (unknown role, invalid data clearance,
        # ...) are intentionally left to raise ActorContext's own
        # AuthorizationContractError unwrapped, so this contract cannot
        # silently drift from idkmesh.enterprise_authz's.
        context = ActorContext(
            principal_id=f"github:{actor_type}:{actor_id}",
            actor_type=actor_type,
            issuer=item["issuer"],
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
            GithubIdentityBinding(actor_id=actor_id, login=login, context=context)
        )

    return GithubIdentityBindingTable(bindings=tuple(bindings))
