"""Enterprise data, egress and credential decision kernel for E5 (#672).

The enterprise control profile (``enterprise_profile.py``) *declares* data
classes, external-processing eligibility, an egress default, a secret backend
and a long-lived-key switch. Nothing consumed those declarations. This module
turns them into pure, fail-closed allow/deny decisions:

* ``decide_external_processing`` -- may data of a class leave the trust
  boundary for a named provider;
* ``decide_egress`` -- may a worker reach a destination host;
* ``decide_credential`` -- may a kind of credential be used under the profile;
* ``authorize_secret_access`` -- secret access only after an explicit
  ``enterprise_authz`` allow decision, with the source chosen by the profile and
  never by provider or task text.

Everything here is evidence-producing policy evaluation. It performs no network
I/O, reads no environment variables and no secret values, grants no runtime
authority, and a decision never executes, merges or accepts anything. Each
decision serialises to a fixed shape that carries identifiers and reason codes
only, so it can be recorded in the audit ledger without secret material.

Eligibility is non-compensating: the check for one data class never reads the
flag of another, and nothing in a request (quality, cost, urgency) is an input.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from idkmesh.enterprise_authz import AuthorizationDecision
from idkmesh.enterprise_profile import (
    EnterpriseProfileError,
    validate_enterprise_profile,
)


POLICY_VERSION = "0.1"
DECISION_KIND = "idkmesh-enterprise-data-policy-decision"

DATA_CLASSES = ("public", "internal", "confidential", "restricted")
# Secret materialization follows an allowed side-effecting stage (see the
# authorization flow in ENTERPRISE_AUTHORIZATION_V0_1): an allow for ``read``,
# ``claim``, ``verify`` or ``audit_export`` must never unlock a secret.
SECRET_ACCESS_ACTIONS = frozenset({"dispatch", "execute"})
CREDENTIAL_KINDS = (
    "workload_identity",
    "secret_manager_reference",
    "github_secret",
    "environment_secret",
    "long_lived_cloud_key",
)

# Credential kind -> the profile secret backend that supplies it. The long-lived
# cloud key is handled separately because it is an orthogonal profile switch.
_KIND_BACKEND = {
    "workload_identity": "oidc_workload_identity",
    "secret_manager_reference": "external_secret_manager",
    "github_secret": "github_actions",
    "environment_secret": "environment",
}

_HOST_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")


@dataclass(frozen=True)
class DataPolicyDecision:
    """One allow/deny outcome with a stable machine-readable code."""

    allowed: bool
    control: str
    code: str
    message: str
    subject: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": DECISION_KIND,
            "schema_version": POLICY_VERSION,
            "control": self.control,
            "effect": "allow" if self.allowed else "deny",
            "code": self.code,
            "message": self.message,
            "subject": self.subject,
            "authority": {
                "executes_action": False,
                "reads_secret_value": False,
                "canonical_state_write": False,
                "merge": False,
            },
        }


def _deny(control: str, code: str, message: str, subject: str = "") -> DataPolicyDecision:
    return DataPolicyDecision(False, control, code, message, subject)


def _allow(control: str, code: str, message: str, subject: str = "") -> DataPolicyDecision:
    return DataPolicyDecision(True, control, code, message, subject)


def _safe_subject(value: object) -> str:
    """Return the value only if it is a well-formed identifier, else a marker.

    Decisions are recordable, so untrusted text must never be echoed back.
    """

    if isinstance(value, str) and _ID_RE.fullmatch(value):
        return value
    return "<invalid>"


def _profile_or_deny(
    profile: Any, control: str
) -> tuple[Mapping[str, Any] | None, DataPolicyDecision | None]:
    try:
        validate_enterprise_profile(profile)
    except EnterpriseProfileError as exc:
        return None, _deny(
            control,
            "invalid_profile",
            f"enterprise profile failed validation: {exc.code}",
        )
    return profile, None


_MAX_POLICY_LIST_ENTRIES = 256


def _bounded_policy_entries(values: object) -> list[object] | None:
    """Reject scalar/mapping and unbounded inputs instead of iterating text.

    These are explicit policy collections, not trusted strings or provider
    payloads. Arbitrary iterables are accepted only up to a finite ceiling.
    """
    if isinstance(values, (str, bytes, Mapping)):
        return None
    try:
        items = []
        for value in values:
            if len(items) == _MAX_POLICY_LIST_ENTRIES:
                return None
            items.append(value)
    except (TypeError, ValueError, RuntimeError):
        return None
    return items


def decide_external_processing(
    profile: Any,
    *,
    data_class: object,
    provider_id: object,
    approved_provider_ids: Iterable[str],
) -> DataPolicyDecision:
    """Decide whether ``data_class`` may be processed by an external provider.

    Denies unless the profile admits the class, the profile's own flag for that
    exact class is true, and the provider is explicitly approved. An unknown
    class, an unlisted provider or an invalid profile all deny.
    """

    control = "external_processing"
    subject = _safe_subject(provider_id)
    valid, denial = _profile_or_deny(profile, control)
    if valid is None:
        return denial
    if not isinstance(data_class, str) or data_class not in DATA_CLASSES:
        return _deny(control, "unknown_data_class", "data class is not recognised", subject)
    data = valid["data"]
    if data_class not in data["allowed_classifications"]:
        return _deny(
            control,
            "class_not_admitted",
            f"profile does not admit {data_class} data at all",
            subject,
        )
    if data["external_processing"][data_class] is not True:
        return _deny(
            control,
            "external_processing_forbidden",
            f"profile forbids external processing of {data_class} data",
            subject,
        )
    if subject == "<invalid>":
        return _deny(control, "invalid_provider", "provider id is malformed", subject)
    entries = _bounded_policy_entries(approved_provider_ids)
    if entries is None or any(
        not isinstance(item, str) or _ID_RE.fullmatch(item) is None
        for item in entries
    ):
        return _deny(
            control,
            "invalid_approved_providers",
            "approved provider ids must be a bounded collection of identifiers",
            subject,
        )
    if provider_id not in frozenset(entries):
        return _deny(
            control,
            "provider_not_approved",
            "provider is not on the approved external-processing list",
            subject,
        )
    return _allow(
        control,
        "external_processing_allowed",
        f"{data_class} data may be processed by the approved provider",
        subject,
    )


def normalize_host(value: object) -> str | None:
    """Return a lowercase DNS hostname, or None for anything else.

    URLs, ports, userinfo, paths, wildcards, whitespace and empty labels are
    rejected rather than trimmed, so a crafted destination cannot masquerade as
    an allowlisted one.
    """

    if not isinstance(value, str) or not value or len(value) > 253:
        return None
    host = value[:-1] if value.endswith(".") else value
    host = host.lower()
    labels = host.split(".")
    if not all(_HOST_LABEL.fullmatch(label) for label in labels):
        return None
    return host


def decide_egress(
    profile: Any,
    *,
    destination_host: object,
    allowlist: Iterable[str],
) -> DataPolicyDecision:
    """Decide whether a worker may reach ``destination_host``.

    With ``egress_default == "deny"`` only an exact, normalised allowlist entry
    is admitted; wildcards are never expanded. A malformed allowlist entry
    denies everything (fail closed) rather than being skipped.
    """

    control = "egress"
    valid, denial = _profile_or_deny(profile, control)
    if valid is None:
        return denial
    host = normalize_host(destination_host)
    if host is None:
        return _deny(control, "invalid_destination", "destination is not a bare hostname")
    raw_entries = _bounded_policy_entries(allowlist)
    if raw_entries is None:
        return _deny(
            control, "invalid_allowlist",
            "allowlist must be a bounded collection of hostnames", host,
        )
    entries = []
    for entry in raw_entries:
        normalized = normalize_host(entry)
        if normalized is None:
            return _deny(
                control,
                "invalid_allowlist",
                "allowlist contains a non-hostname entry",
                host,
            )
        entries.append(normalized)
    if valid["data"]["egress_default"] == "allow":
        return _allow(
            control,
            "egress_allowed_by_profile_default",
            "profile does not deny egress by default",
            host,
        )
    if host in entries:
        return _allow(control, "egress_allowlisted", "destination is allowlisted", host)
    return _deny(
        control,
        "egress_denied_by_default",
        "destination is not on the egress allowlist",
        host,
    )


def decide_credential(profile: Any, *, credential_kind: object) -> DataPolicyDecision:
    """Decide whether a credential kind is permitted by the profile.

    The kind must be supplied by the profile's own secret backend. A long-lived
    cloud key is additionally gated by ``long_lived_cloud_keys_allowed`` and is
    never available under an OIDC workload-identity or ``none`` backend.
    """

    control = "credential"
    valid, denial = _profile_or_deny(profile, control)
    if valid is None:
        return denial
    if not isinstance(credential_kind, str) or credential_kind not in CREDENTIAL_KINDS:
        return _deny(control, "unknown_credential_kind", "credential kind is not recognised")
    secrets = valid["secrets"]
    backend = secrets["backend"]
    if backend == "none":
        return _deny(
            control,
            "no_secret_backend",
            "profile configures no secret backend",
            credential_kind,
        )
    if credential_kind == "long_lived_cloud_key":
        if secrets["long_lived_cloud_keys_allowed"] is not True:
            return _deny(
                control,
                "long_lived_keys_forbidden",
                "profile forbids long-lived cloud keys",
                credential_kind,
            )
        if backend == "oidc_workload_identity":
            return _deny(
                control,
                "long_lived_keys_forbidden",
                "workload-identity backend does not issue long-lived keys",
                credential_kind,
            )
        return _allow(
            control,
            "long_lived_key_permitted",
            "profile explicitly permits long-lived cloud keys",
            credential_kind,
        )
    if _KIND_BACKEND[credential_kind] != backend:
        return _deny(
            control,
            "credential_not_from_profile_backend",
            "credential kind does not match the profile secret backend",
            credential_kind,
        )
    return _allow(
        control,
        "credential_permitted",
        "credential kind is supplied by the profile secret backend",
        credential_kind,
    )


def authorize_secret_access(
    profile: Any,
    *,
    authorization: object,
    credential_kind: object,
    requested_backend: object = None,
) -> DataPolicyDecision:
    """Permit secret access only after authorization, from the profile's source.

    ``authorization`` must be an ``AuthorizationDecision`` whose effect is
    ``allow`` (``requires_approval`` is not enough) and whose action is
    ``dispatch`` or ``execute`` (``SECRET_ACCESS_ACTIONS``). ``requested_backend`` is the
    place untrusted provider/task text would land: any value other than the
    profile's own backend is denied, and a matching value is still only
    corroboration -- the source always comes from the profile. The decision
    contains no secret value and reads none.
    """

    control = "secret_access"
    if not isinstance(authorization, AuthorizationDecision):
        return _deny(
            control,
            "authorization_required",
            "secret access requires a prior authorization decision",
        )
    if authorization.effect != "allow":
        return _deny(
            control,
            "authorization_not_allowed",
            f"authorization effect is {authorization.effect}",
            _safe_subject(authorization.request_id),
        )
    if authorization.action not in SECRET_ACCESS_ACTIONS:
        return _deny(
            control,
            "authorization_action_not_permitted",
            "only an allowed dispatch or execute decision can unlock a secret",
            _safe_subject(authorization.request_id),
        )
    valid, denial = _profile_or_deny(profile, control)
    if valid is None:
        return denial
    backend = valid["secrets"]["backend"]
    if requested_backend is not None and requested_backend != backend:
        return _deny(
            control,
            "untrusted_source_selection",
            "secret source is chosen by the profile, not by the request",
            _safe_subject(authorization.request_id),
        )
    credential = decide_credential(valid, credential_kind=credential_kind)
    if not credential.allowed:
        return _deny(
            control,
            credential.code,
            credential.message,
            _safe_subject(authorization.request_id),
        )
    return _allow(
        control,
        "secret_access_permitted",
        f"authorized access from the {backend} backend",
        _safe_subject(authorization.request_id),
    )
