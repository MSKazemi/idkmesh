"""Read-only validation of a break-glass grant document (E3-E operator check, #670).

``idkmesh break-glass check`` answers one narrow question about a stored grant
document: is it a well-formed, grantable E3-E grant, and is it inside its
window at a caller-supplied instant? It never issues, stores, revokes or
approves a grant and never evaluates an authorization decision.

**A valid grant is not an authorization.** Passing this check says nothing
about whether any request would be allowed: that is decided only by
:func:`idkmesh.enterprise_break_glass.authorize_with_break_glass`, which
re-checks identity revision, policy revision, revocation, scope, clearance and
executor separation on every use. This module imports none of that machinery.

Safety properties:

* Validation is delegated to the library's own strict
  :func:`~idkmesh.enterprise_break_glass.parse_break_glass_grant`; nothing is
  re-implemented, so the check cannot drift from the grant contract.
* The clock is never read. Without ``now_epoch`` the window is reported as
  ``not_evaluated`` rather than guessed.
* The report never echoes free text from the document. ``reason`` is
  excluded entirely; reason codes come from a fixed vocabulary; a path is
  emitted only when it is a known grant field name (an unknown key is
  reported as ``$``); and a ``value`` is attached only when it belongs to the
  library's closed action/role/risk/data-class vocabularies.
* Output is stable: sorted keys, compact separators, reasons sorted.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from idkmesh.enterprise_authz import ACTIONS, DATA_CLASSES, ROLES, RISKS
from idkmesh.enterprise_break_glass import (
    _GRANT_FIELDS,
    GRANTABLE_ACTIONS,
    GRANTABLE_ROLES,
    MAX_GRANTED_DATA_CLASS,
    MAX_GRANTED_RISK,
    BreakGlassError,
    parse_break_glass_grant,
)

CHECK_REPORT_KIND = "idkmesh-break-glass-check-report"
CHECK_REPORT_VERSION = "0.1"

WINDOW_NOT_EVALUATED = "not_evaluated"
WINDOW_WITHIN = "within"
WINDOW_NOT_YET_VALID = "not_yet_valid"
WINDOW_EXPIRED = "expired"

NOTICE = (
    "A valid break-glass grant is not an authorization. This check evaluates "
    "no authorization decision, issues nothing, stores nothing and reads no "
    "clock; only authorize_with_break_glass decides a request."
)

# Specific, stable codes for the requests no grant may make.
CODE_ACTION_NOT_GRANTABLE = "action_not_grantable"
CODE_ROLE_NOT_GRANTABLE = "role_not_grantable"
CODE_RISK_ABOVE_CEILING = "risk_above_ceiling"
CODE_DATA_CLASS_ABOVE_CEILING = "data_class_above_ceiling"
CODE_WINDOW_NOT_YET_VALID = "break_glass_not_yet_valid"
CODE_WINDOW_EXPIRED = "break_glass_expired"
CODE_UNREADABLE_SHAPE = "invalid_type"
CODE_DUPLICATE_VALUE = "duplicate_value"

_KNOWN_FIELDS = frozenset(_GRANT_FIELDS)
_RISK_RANK = {value: index for index, value in enumerate(RISKS)}
_DATA_RANK = {value: index for index, value in enumerate(DATA_CLASSES)}
# Library codes for a value outside a grantable set, replaced by the specific
# codes above whenever the document's own values allow naming them.
_GENERIC_NOT_GRANTABLE = "value_not_grantable"


@dataclass(frozen=True, slots=True)
class CheckReason:
    """One stable refusal reason; never carries free text from the document."""

    code: str
    path: str
    value: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"code": self.code, "path": self.path}
        if self.value is not None:
            result["value"] = self.value
        return result

    def sort_key(self) -> tuple[str, str, str]:
        return (self.code, self.path, self.value or "")


@dataclass(frozen=True, slots=True)
class GrantCheckReport:
    """Outcome of :func:`check_break_glass_grant_document`."""

    well_formed: bool
    requests_non_grantable: bool
    window_status: str
    now_epoch: int | None
    reasons: tuple[CheckReason, ...]
    grant: Mapping[str, Any] | None
    grant_digest: str | None

    @property
    def ok(self) -> bool:
        return (
            self.well_formed
            and not self.requests_non_grantable
            and self.window_status not in (WINDOW_NOT_YET_VALID, WINDOW_EXPIRED)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": CHECK_REPORT_KIND,
            "schema_version": CHECK_REPORT_VERSION,
            "ok": self.ok,
            "well_formed": self.well_formed,
            "requests_non_grantable": self.requests_non_grantable,
            "window": {
                "status": self.window_status,
                "now_epoch": self.now_epoch,
            },
            "grant_digest": self.grant_digest,
            "grant": None if self.grant is None else dict(self.grant),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "is_authorization": False,
            "evaluates_authorization": False,
            "writes_anything": False,
            "notice": NOTICE,
        }


def _safe_path(raw: str) -> str:
    """Return a path made only of known grant field names, else ``$``."""

    field = raw[2:] if raw.startswith("$.") else raw
    return f"$.{field}" if field in _KNOWN_FIELDS else "$"


def _scan_non_grantable(document: Mapping[str, Any]) -> list[CheckReason]:
    """Name every non-grantable request, even when the document is malformed."""

    found: list[CheckReason] = []
    roles = document.get("granted_roles")
    if isinstance(roles, list):
        for item in roles:
            if isinstance(item, str) and item in ROLES and item not in GRANTABLE_ROLES:
                found.append(
                    CheckReason(CODE_ROLE_NOT_GRANTABLE, "$.granted_roles", item)
                )
    actions = document.get("actions")
    if isinstance(actions, list):
        for item in actions:
            if (
                isinstance(item, str)
                and item in ACTIONS
                and item not in GRANTABLE_ACTIONS
            ):
                found.append(
                    CheckReason(CODE_ACTION_NOT_GRANTABLE, "$.actions", item)
                )
    risk = document.get("max_risk")
    if (
        isinstance(risk, str)
        and risk in _RISK_RANK
        and _RISK_RANK[risk] > _RISK_RANK[MAX_GRANTED_RISK]
    ):
        found.append(CheckReason(CODE_RISK_ABOVE_CEILING, "$.max_risk", risk))
    data = document.get("max_data_classification")
    if (
        isinstance(data, str)
        and data in _DATA_RANK
        and _DATA_RANK[data] > _DATA_RANK[MAX_GRANTED_DATA_CLASS]
    ):
        found.append(
            CheckReason(
                CODE_DATA_CLASS_ABOVE_CEILING, "$.max_data_classification", data
            )
        )
    return found


def _scan_duplicates(document: Mapping[str, Any]) -> list[CheckReason]:
    """Flag a repeated member in ``granted_roles`` / ``actions`` (schema: unique)."""

    found: list[CheckReason] = []
    for field in ("granted_roles", "actions"):
        items = document.get(field)
        if (
            isinstance(items, list)
            and all(isinstance(item, str) for item in items)
            and len(set(items)) != len(items)
        ):
            found.append(CheckReason(CODE_DUPLICATE_VALUE, f"$.{field}"))
    return found


def _grant_summary(grant: Any) -> dict[str, Any]:
    """Validated, non-free-text fields only; ``reason`` is deliberately absent."""

    return {
        "grant_id": grant.grant_id,
        "incident_id": grant.incident_id,
        "scope": grant.scope.to_dict(),
        "granted_roles": sorted(grant.granted_roles),
        "actions": sorted(grant.actions),
        "max_risk": grant.max_risk,
        "max_data_classification": grant.max_data_classification,
        "policy_id": grant.policy_id,
        "policy_revision": grant.policy_revision,
        "issued_at_epoch": grant.issued_at_epoch,
        "expires_at_epoch": grant.expires_at_epoch,
        "window_seconds": grant.expires_at_epoch - grant.issued_at_epoch,
    }


def check_break_glass_grant_document(
    value: Any, *, now_epoch: int | None = None
) -> GrantCheckReport:
    """Validate a parsed grant document; never raises for a bad document.

    ``now_epoch`` is the only notion of "now": it is never read from the clock.
    Raises :class:`ValueError` only for an invalid ``now_epoch`` argument.
    """

    if now_epoch is not None and (
        isinstance(now_epoch, bool) or not isinstance(now_epoch, int) or now_epoch < 0
    ):
        raise ValueError("now_epoch must be an integer >= 0")

    reasons: list[CheckReason] = []
    specific = _scan_non_grantable(value) if isinstance(value, Mapping) else []
    specific_paths = {reason.path for reason in specific}
    duplicates = _scan_duplicates(value) if isinstance(value, Mapping) else []
    grant = None
    try:
        grant = parse_break_glass_grant(value)
    except BreakGlassError as exc:
        path = _safe_path(exc.path)
        if exc.code == _GENERIC_NOT_GRANTABLE and path in specific_paths:
            pass  # already named precisely by the scan
        else:
            reasons.append(CheckReason(exc.code, path))
    except (TypeError, ValueError):
        # An unhashable or otherwise unexpected shape inside a list field.
        reasons.append(CheckReason(CODE_UNREADABLE_SHAPE, "$"))
    reasons.extend(specific)
    if duplicates:
        # parse_break_glass_grant collapses a list into a frozenset before its
        # own uniqueness check, so a repeated member would pass it; the JSON
        # schema (uniqueItems) rejects it, so this check does too.
        reasons.extend(duplicates)
        grant = None

    window = WINDOW_NOT_EVALUATED
    summary = None
    digest = None
    if grant is not None:
        summary = _grant_summary(grant)
        digest = grant.digest
        if now_epoch is not None:
            if now_epoch < grant.issued_at_epoch:
                window = WINDOW_NOT_YET_VALID
                reasons.append(CheckReason(CODE_WINDOW_NOT_YET_VALID, "$.issued_at_epoch"))
            elif now_epoch >= grant.expires_at_epoch:
                window = WINDOW_EXPIRED
                reasons.append(CheckReason(CODE_WINDOW_EXPIRED, "$.expires_at_epoch"))
            else:
                window = WINDOW_WITHIN

    unique = sorted(set(reasons), key=CheckReason.sort_key)
    return GrantCheckReport(
        well_formed=grant is not None,
        requests_non_grantable=bool(specific),
        window_status=window,
        now_epoch=now_epoch,
        reasons=tuple(unique),
        grant=summary,
        grant_digest=digest,
    )


def render_check_report_json(report: GrantCheckReport) -> str:
    """Stable compact JSON (sorted keys, trailing newline); no free text."""

    return json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"


def render_check_report_text(report: GrantCheckReport) -> str:
    """Human-readable summary; names codes and ids, never the reason text."""

    lines = [
        "Break-glass grant check",
        f"result: {'ok' if report.ok else 'refused'}",
        f"well formed: {'yes' if report.well_formed else 'no'}",
        "requests non-grantable action/role/ceiling: "
        f"{'yes' if report.requests_non_grantable else 'no'}",
        f"window: {report.window_status}",
    ]
    if report.now_epoch is not None:
        lines.append(f"now epoch: {report.now_epoch}")
    if report.grant is not None:
        grant = report.grant
        lines.append(f"grant id: {grant['grant_id']}")
        lines.append(f"incident id: {grant['incident_id']}")
        lines.append(
            f"scope: {grant['scope']['tenant_id']}/{grant['scope']['project_id']}"
        )
        lines.append("roles: " + ",".join(grant["granted_roles"]))
        lines.append("actions: " + ",".join(grant["actions"]))
        lines.append(
            f"ceilings: risk<={grant['max_risk']} "
            f"data<={grant['max_data_classification']}"
        )
        lines.append(
            f"window epochs: {grant['issued_at_epoch']}..{grant['expires_at_epoch']}"
        )
        lines.append(f"grant digest: {report.grant_digest}")
    if report.reasons:
        lines.append("reasons:")
        for reason in report.reasons:
            suffix = f" ({reason.value})" if reason.value is not None else ""
            lines.append(f"  - {reason.code} at {reason.path}{suffix}")
    lines.append("is authorization: no")
    lines.append(NOTICE)
    return "\n".join(lines) + "\n"
