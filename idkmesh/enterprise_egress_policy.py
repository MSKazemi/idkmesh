"""Classification-vs-destination egress policy for E5 (#672).

``enterprise_data_policy`` answers the profile-level questions (may this class
go to an approved provider? is this host allowlisted?) from *function
arguments*. This module adds the missing declarative input: a strict, reviewable
egress policy document that names each permitted destination, its trust zone
and the **exact data classes** it may receive, and an evaluator that combines
that document with the enterprise control profile.

The evaluator is deny-by-default and non-compensating:

* the destination must be on the policy (an unlisted host is admitted only when
  the profile explicitly leaves egress open, and then for ``public`` data only);
* the class must be admitted by the profile *and* listed for that destination.
  Classes are listed explicitly, never as a ceiling, so a destination cleared
  for ``restricted`` is not thereby cleared for any other class and a permissive
  entry for ``public`` never excuses ``restricted``;
* a destination in the ``external_provider`` zone additionally needs the
  profile's external-processing flag for that exact class and an approved
  provider id (delegated to ``decide_external_processing``);
* an ``external_public`` destination (package index, documentation host) may
  receive ``public`` data only, enforced when the policy is loaded.

Everything here is pure policy evaluation. It performs no DNS resolution, no
network I/O, reads no environment variable and no secret value, and grants no
runtime authority: an allow is evidence for a later enforcement point, not an
action. Hostnames are exact; IP literals, single-label names, wildcards, URLs
and ports are rejected rather than normalised.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from idkmesh.enterprise_data_policy import (
    DATA_CLASSES,
    DataPolicyDecision,
    decide_egress,
    decide_external_processing,
    normalize_host,
)
from idkmesh.enterprise_profile import (
    EnterpriseProfileError,
    validate_enterprise_profile,
)
from idkmesh.enterprise_secret_scan import scan_for_secrets


POLICY_KIND = "idkmesh-enterprise-egress-policy"
POLICY_VERSION = "0.1"
DECISION_KIND = "idkmesh-enterprise-classified-egress-decision"
ZONES = ("internal", "external_provider", "external_public")
MAX_DESTINATIONS = 256

_ROOT_FIELDS = frozenset(
    {"kind", "schema_version", "policy_id", "semantics", "destinations"}
)
_SEMANTICS_FIELDS = frozenset({"policy_role", "grants_runtime_authority"})
_DESTINATION_FIELDS = frozenset(
    {"destination_id", "host", "zone", "allowed_classes", "provider_id"}
)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_RANK = {name: index for index, name in enumerate(DATA_CLASSES)}


class EgressPolicyError(ValueError):
    """An egress policy document is malformed. Carries a code and a JSON path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path}: {message}")


@dataclass(frozen=True)
class EgressDestination:
    """One validated destination row."""

    destination_id: str
    host: str
    zone: str
    allowed_classes: frozenset[str]
    provider_id: str | None


@dataclass(frozen=True)
class EgressPolicy:
    """A validated egress policy plus the digest of its canonical form."""

    policy_id: str
    destinations: tuple[EgressDestination, ...]
    digest: str

    def destination_for(self, host: str) -> EgressDestination | None:
        for destination in self.destinations:
            if destination.host == host:
                return destination
        return None

    def hosts(self) -> tuple[str, ...]:
        return tuple(destination.host for destination in self.destinations)

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(
            destination.provider_id
            for destination in self.destinations
            if destination.provider_id is not None
        )

    def matrix(self) -> dict[str, dict[str, bool]]:
        """Static policy-only view: host -> class -> listed for that host.

        This ignores the profile; it is for review and documentation, not an
        authorization decision.
        """

        return {
            destination.host: {
                name: name in destination.allowed_classes for name in DATA_CLASSES
            }
            for destination in self.destinations
        }


def _fail(code: str, path: str, message: str) -> EgressPolicyError:
    return EgressPolicyError(code, path, message)


def _object(value: Any, path: str, fields: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise _fail("invalid_type", path, "must be an object with string keys")
    missing = sorted(fields - set(value))
    if missing:
        raise _fail("missing_field", path, f"missing required field(s): {', '.join(missing)}")
    extra = sorted(set(value) - fields)
    if extra:
        raise _fail("unknown_field", path, f"unknown field(s): {', '.join(extra)}")
    return value


def _host(value: Any, path: str) -> str:
    host = normalize_host(value)
    if host is None or host != value:
        raise _fail("invalid_host", path, "must be a lowercase bare DNS hostname")
    labels = host.split(".")
    if len(labels) < 2:
        raise _fail("invalid_host", path, "must be a fully qualified hostname")
    if not labels[-1][0].isalpha():
        raise _fail(
            "invalid_host", path,
            "the final label must start with a letter (IP literals are not destinations)",
        )
    return host


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise _fail("invalid_identifier", path, "must be a well-formed identifier")
    return value


def _classes(value: Any, path: str) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise _fail("invalid_classes", path, "must be a non-empty array")
    if any(not isinstance(item, str) or item not in _RANK for item in value):
        raise _fail("invalid_classes", path, "contains an unknown data class")
    if len(set(value)) != len(value):
        raise _fail("invalid_classes", path, "contains a duplicate data class")
    return frozenset(value)


def _canonical_digest(document: Mapping[str, Any]) -> str:
    text = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def load_egress_policy(document: Any) -> EgressPolicy:
    """Validate ``document`` strictly and return an immutable policy.

    Raises :class:`EgressPolicyError` for any structural or semantic defect,
    including a document that appears to contain a raw credential.
    """

    root = _object(document, "$", _ROOT_FIELDS)
    if root["kind"] != POLICY_KIND:
        raise _fail("invalid_kind", "$.kind", f"must be {POLICY_KIND}")
    if root["schema_version"] != POLICY_VERSION:
        raise _fail("invalid_version", "$.schema_version", f"must be {POLICY_VERSION}")
    policy_id = _identifier(root["policy_id"], "$.policy_id")
    semantics = _object(root["semantics"], "$.semantics", _SEMANTICS_FIELDS)
    if semantics["policy_role"] != "policy_input_only":
        raise _fail("invalid_semantics", "$.semantics.policy_role", "must be policy_input_only")
    if semantics["grants_runtime_authority"] is not False:
        raise _fail(
            "invalid_semantics",
            "$.semantics.grants_runtime_authority",
            "must be false",
        )
    rows = root["destinations"]
    if not isinstance(rows, list) or not rows:
        raise _fail("invalid_destinations", "$.destinations", "must be a non-empty array")
    if len(rows) > MAX_DESTINATIONS:
        raise _fail(
            "too_many_destinations",
            "$.destinations",
            f"at most {MAX_DESTINATIONS} destinations",
        )

    destinations: list[EgressDestination] = []
    seen_ids: set[str] = set()
    seen_hosts: set[str] = set()
    for index, row in enumerate(rows):
        path = f"$.destinations[{index}]"
        required = _DESTINATION_FIELDS - {"provider_id"}
        if isinstance(row, Mapping) and "provider_id" in row:
            required = _DESTINATION_FIELDS
        item = _object(row, path, required)
        destination_id = _identifier(item["destination_id"], f"{path}.destination_id")
        host = _host(item["host"], f"{path}.host")
        zone = item["zone"]
        if not isinstance(zone, str) or zone not in ZONES:
            raise _fail("invalid_zone", f"{path}.zone", f"must be one of {', '.join(ZONES)}")
        allowed = _classes(item["allowed_classes"], f"{path}.allowed_classes")
        provider_id: str | None = None
        if zone == "external_provider":
            if "provider_id" not in item:
                raise _fail(
                    "provider_required", f"{path}.provider_id",
                    "an external_provider destination must name its provider",
                )
            provider_id = _identifier(item["provider_id"], f"{path}.provider_id")
        elif "provider_id" in item:
            raise _fail(
                "provider_not_allowed", f"{path}.provider_id",
                "only an external_provider destination names a provider",
            )
        if zone == "external_public" and allowed != {"public"}:
            raise _fail(
                "external_public_requires_public_only",
                f"{path}.allowed_classes",
                "an external_public destination may receive public data only",
            )
        if destination_id in seen_ids:
            raise _fail("duplicate_destination", f"{path}.destination_id", "duplicate id")
        if host in seen_hosts:
            raise _fail("duplicate_destination", f"{path}.host", "duplicate host")
        seen_ids.add(destination_id)
        seen_hosts.add(host)
        destinations.append(
            EgressDestination(destination_id, host, zone, allowed, provider_id)
        )

    report = scan_for_secrets(document)
    if not report.clean:
        raise _fail(
            "raw_secret_detected" if report.findings else "secret_scan_incomplete",
            "$",
            "policy document failed the raw-secret scan",
        )
    return EgressPolicy(
        policy_id=policy_id,
        destinations=tuple(destinations),
        digest=_canonical_digest(document),
    )


@dataclass(frozen=True)
class ClassifiedEgressDecision:
    """Allow/deny outcome for one (destination, data class) pair."""

    allowed: bool
    code: str
    message: str
    destination_host: str
    data_class: str
    destination_id: str
    policy_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": DECISION_KIND,
            "schema_version": POLICY_VERSION,
            "control": "classified_egress",
            "effect": "allow" if self.allowed else "deny",
            "code": self.code,
            "message": self.message,
            "destination_host": self.destination_host,
            "destination_id": self.destination_id,
            "data_class": self.data_class,
            "policy_digest": self.policy_digest,
            "authority": {
                "executes_action": False,
                "performs_network_io": False,
                "reads_secret_value": False,
                "canonical_state_write": False,
                "merge": False,
            },
        }


def _decision(
    allowed: bool,
    code: str,
    message: str,
    *,
    host: str = "",
    data_class: str = "",
    destination_id: str = "",
    digest: str = "",
) -> ClassifiedEgressDecision:
    return ClassifiedEgressDecision(
        allowed, code, message, host, data_class, destination_id, digest
    )


def _from_kernel(
    decision: DataPolicyDecision,
    *,
    host: str,
    data_class: str,
    destination_id: str,
    digest: str,
) -> ClassifiedEgressDecision:
    return _decision(
        False,
        decision.code,
        decision.message,
        host=host,
        data_class=data_class,
        destination_id=destination_id,
        digest=digest,
    )


def decide_classified_egress(
    profile: Any,
    policy_document: Any,
    *,
    destination_host: object,
    data_class: object,
) -> ClassifiedEgressDecision:
    """Decide whether ``data_class`` data may be sent to ``destination_host``.

    ``policy_document`` is the raw egress policy and is validated on every
    call, so a stale or mutated object cannot be trusted. Any invalid input
    denies; no exception escapes for a content problem. The returned decision
    echoes the host and class only when they are well-formed.
    """

    try:
        validate_enterprise_profile(profile)
    except EnterpriseProfileError as exc:
        return _decision(False, "invalid_profile", f"enterprise profile failed validation: {exc.code}")
    try:
        policy = load_egress_policy(policy_document)
    except EgressPolicyError as exc:
        return _decision(False, "invalid_egress_policy", f"egress policy failed validation: {exc.code}")

    digest = policy.digest
    host = normalize_host(destination_host)
    if host is None:
        return _decision(
            False, "invalid_destination", "destination is not a bare hostname", digest=digest
        )
    if not isinstance(data_class, str) or data_class not in _RANK:
        return _decision(
            False, "unknown_data_class", "data class is not recognised",
            host=host, digest=digest,
        )
    common = {"host": host, "data_class": data_class, "digest": digest}
    if data_class not in profile["data"]["allowed_classifications"]:
        return _decision(
            False, "class_not_admitted",
            f"profile does not admit {data_class} data at all", **common,
        )

    destination = policy.destination_for(host)
    # Profile-level egress gate (deny-by-default, exact hostname match).
    egress = decide_egress(profile, destination_host=host, allowlist=policy.hosts())
    if destination is None:
        if not egress.allowed:
            return _from_kernel(egress, destination_id="", **common)
        # The profile leaves egress open and the host is not on the policy.
        # An unknown destination is untrusted: public data only.
        if data_class != "public":
            return _decision(
                False, "unlisted_destination_public_only",
                "an unlisted destination may receive public data only", **common,
            )
        return _decision(
            True, "egress_allowed_unlisted_public",
            "profile leaves egress open; public data only", **common,
        )
    if not egress.allowed:  # pragma: no cover - listed hosts are always on the allowlist
        return _from_kernel(egress, destination_id=destination.destination_id, **common)
    ident = destination.destination_id
    if data_class not in destination.allowed_classes:
        return _decision(
            False, "class_not_permitted_for_destination",
            f"destination is not cleared for {data_class} data",
            destination_id=ident, **common,
        )
    if destination.zone == "external_provider":
        processing = decide_external_processing(
            profile,
            data_class=data_class,
            provider_id=destination.provider_id,
            approved_provider_ids=policy.provider_ids(),
        )
        if not processing.allowed:
            return _from_kernel(processing, destination_id=ident, **common)
    return _decision(
        True, "classified_egress_allowed",
        f"{data_class} data may be sent to this {destination.zone} destination",
        destination_id=ident, **common,
    )
