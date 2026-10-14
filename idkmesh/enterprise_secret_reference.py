"""Secret-reference contract for E5 (#672): references, never raw secrets.

Configuration, WorkUnits and audit records may *name* a secret; they must never
*contain* one. This module is the typed form of that rule:

* ``parse_secret_reference`` accepts only a closed set of reference schemes
  (``env:``, ``gh-secret:``, ``secret:``, ``vault:``) with a strict name
  grammar, and rejects everything else -- including any value that looks like
  an inline secret -- with a stable code that never echoes the input;
* each scheme maps to exactly one profile secret backend and one credential
  kind, so the *source* of a secret is a property of the reference the
  maintainers wrote, not something a provider or task can choose;
* ``resolve_secret_alias`` lets a task refer to a secret only by a logical
  alias that a trusted, maintainer-supplied table resolves; an alias that is
  absent resolves to nothing, and text shaped like a reference is just an
  unknown alias;
* ``authorize_reference_use`` composes the reference with the E5 decision
  kernel (``authorize_secret_access``): a secret is usable only after an
  explicit allowed ``dispatch``/``execute`` authorization and only from the
  backend the profile configures;
* ``secret_access_audit_details`` produces the identifiers-only record of that
  decision, verified free of credential shapes before it is returned.

Workload identity (OIDC) is deliberately not a reference scheme: it issues
short-lived tokens at runtime and has no stored secret to name. It is
authorized as credential kind ``workload_identity`` by ``decide_credential``.

This module never reads an environment variable, a vault or any secret value;
it performs no I/O and grants no authority (see ``connector_secrets`` for the
materialization boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from idkmesh.enterprise_data_policy import (
    DataPolicyDecision,
    authorize_secret_access,
)
from idkmesh.enterprise_secret_scan import SecretLeakError, assert_no_secrets


AUDIT_KIND = "idkmesh-enterprise-secret-access-audit-details"
AUDIT_VERSION = "0.1"
MAX_ALIASES = 256

# scheme -> (profile secret backend, credential kind accepted by the kernel)
SCHEME_CONTRACT: Mapping[str, tuple[str, str]] = {
    "env": ("environment", "environment_secret"),
    "gh-secret": ("github_actions", "github_secret"),
    "secret": ("external_secret_manager", "secret_manager_reference"),
    "vault": ("external_secret_manager", "secret_manager_reference"),
}

_REF_RE = re.compile(r"^([a-z][a-z-]{0,15}):([A-Za-z0-9_][A-Za-z0-9_./-]{0,199})\Z")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_ALIAS_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}\Z")


class SecretReferenceContractError(ValueError):
    """A secret reference or alias is invalid. The message never echoes input."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SecretReference:
    """A validated pointer to a secret. It is not, and never holds, the secret."""

    scheme: str
    name: str

    @property
    def canonical(self) -> str:
        return f"{self.scheme}:{self.name}"

    @property
    def backend(self) -> str:
        return SCHEME_CONTRACT[self.scheme][0]

    @property
    def credential_kind(self) -> str:
        return SCHEME_CONTRACT[self.scheme][1]


def parse_secret_reference(value: object) -> SecretReference:
    """Parse ``value`` as a reference or raise :class:`SecretReferenceContractError`.

    Anything that is not exactly ``<scheme>:<name>`` with a supported scheme
    and a conforming name is refused as ``inline_secret_forbidden`` (the safe
    reading of an unrecognised value is that it may be a raw secret), except an
    unsupported but well-shaped scheme prefix, which is ``unsupported_scheme``.
    """

    if not isinstance(value, str) or not value:
        raise SecretReferenceContractError(
            "inline_secret_forbidden", "a secret must be given as a reference"
        )
    match = _REF_RE.fullmatch(value)
    if match is None:
        raise SecretReferenceContractError(
            "inline_secret_forbidden", "value is not a well-formed secret reference"
        )
    scheme, name = match.group(1), match.group(2)
    if scheme not in SCHEME_CONTRACT:
        raise SecretReferenceContractError(
            "unsupported_scheme", "secret reference scheme is not supported"
        )
    if scheme == "env":
        if _ENV_NAME.fullmatch(name) is None:
            raise SecretReferenceContractError(
                "invalid_name", "environment reference name is not a valid variable name"
            )
    else:
        segments = name.split("/")
        if any(segment in ("", ".", "..") for segment in segments):
            raise SecretReferenceContractError(
                "invalid_name", "reference path has an empty or traversal segment"
            )
    reference = SecretReference(scheme, name)
    # A reference that the credential scanner would flag is not a reference.
    try:
        assert_no_secrets({"secret_ref": reference.canonical}, context="secret_reference")
    except SecretLeakError:
        raise SecretReferenceContractError(
            "inline_secret_forbidden", "reference name has the shape of a credential"
        ) from None
    return reference


def resolve_secret_alias(bindings: Mapping[str, str], alias: object) -> SecretReference:
    """Resolve a logical ``alias`` through a trusted binding table.

    ``bindings`` is maintainer-supplied configuration (alias -> reference
    string). The alias is the only thing a task or provider may supply; it can
    select among the references the maintainers already bound, never introduce
    a new source. Every binding value is re-parsed, so a table entry holding a
    raw secret is rejected at use.
    """

    if not isinstance(bindings, Mapping) or len(bindings) > MAX_ALIASES:
        raise SecretReferenceContractError(
            "invalid_bindings", "alias bindings must be a bounded mapping"
        )
    if not isinstance(alias, str) or _ALIAS_RE.fullmatch(alias) is None:
        raise SecretReferenceContractError("invalid_alias", "alias is malformed")
    if alias not in bindings:
        raise SecretReferenceContractError("unknown_alias", "alias is not bound")
    return parse_secret_reference(bindings[alias])


def authorize_reference_use(
    profile: Any,
    reference: SecretReference,
    *,
    authorization: object,
) -> DataPolicyDecision:
    """Authorize use of ``reference`` under ``profile`` after ``authorization``.

    The credential kind and backend come from the reference's scheme, so the
    profile backend must be the one that scheme belongs to. There is no
    parameter through which a request can name a different source.
    """

    if not isinstance(reference, SecretReference) or reference.scheme not in SCHEME_CONTRACT:
        return DataPolicyDecision(
            False, "secret_access", "invalid_reference",
            "secret reference is not a validated SecretReference", "",
        )
    return authorize_secret_access(
        profile,
        authorization=authorization,
        credential_kind=reference.credential_kind,
        requested_backend=reference.backend,
    )


def secret_access_audit_details(
    reference: SecretReference, decision: DataPolicyDecision
) -> dict[str, Any]:
    """Return identifiers-only audit details for one secret-access decision.

    Contains the canonical reference (a name, not a value), scheme, credential
    kind, effect and reason code. It is scanned before return so a regression
    that put credential material here fails closed instead of reaching the
    audit ledger.
    """

    details: dict[str, Any] = {
        "kind": AUDIT_KIND,
        "schema_version": AUDIT_VERSION,
        "secret_ref": reference.canonical,
        "scheme": reference.scheme,
        "credential_kind": reference.credential_kind,
        "effect": "allow" if decision.allowed else "deny",
        "code": decision.code,
        "subject": decision.subject,
        "secret_value_read": False,
    }
    assert_no_secrets(details, context="secret_access_audit_details")
    return details
