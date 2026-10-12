"""Freshness-bound authorization decision cache for E3-D (#670).

``enterprise_authz.authorize`` is pure and cheap, but a service that fronts it
with a cache must not turn a past ALLOW into standing authority. This cache
makes that property structural rather than a caller convention:

* the key binds the *whole* normalized actor and approver (not only the
  ``identity_revision`` string), the policy id + revision and a digest of the
  policy rules, and the request's scope/resource/action/risk/data class, so a
  changed, revoked or re-scoped identity or an edited policy is a cache miss
  and forces re-evaluation even if an upstream forgot to bump a revision;
* an entry is only reusable inside ``[evaluated_at, valid_until)`` where
  ``valid_until`` is the earliest of the max age, the actor's expiry and the
  approver's expiry, so an expired identity never keeps cached authority and a
  clock that moves backwards cannot revive an entry;
* ``invalidate_principal`` lets a revocation feed drop entries eagerly.

The cache evaluates and stores policy evidence only. A hit returns the stored
decision re-stamped with the new ``request_id`` and ``evaluated_at_epoch``; it
executes nothing and carries no state-write or merge authority.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any

from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationContractError,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)

DEFAULT_MAX_AGE_SECONDS = 300
DEFAULT_MAX_ENTRIES = 1024


def _canonical_digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def policy_digest(policy: AuthorizationPolicy) -> str:
    """Digest of the policy *content*, independent of its revision label."""

    rules = [
        {
            "action": rule.action,
            "allowed_roles": sorted(rule.allowed_roles),
            "allowed_actor_types": sorted(rule.allowed_actor_types),
            "max_data_classification": rule.max_data_classification,
            "risk_floor": rule.risk_floor,
            "distinct_approval_at_risk": rule.distinct_approval_at_risk,
            "approval_roles": sorted(rule.approval_roles),
            "approval_actor_types": sorted(rule.approval_actor_types),
        }
        for rule in sorted(policy.rules, key=lambda item: item.action)
    ]
    return _canonical_digest(
        {"policy_id": policy.policy_id, "revision": policy.revision, "rules": rules}
    )


def decision_cache_key(
    request: AuthorizationRequest, policy: AuthorizationPolicy
) -> str:
    """Key over everything that can change an authorization outcome.

    ``request_id`` and ``evaluated_at_epoch`` are deliberately excluded; time
    is handled by the entry's validity window instead.
    """

    return _canonical_digest(
        {
            "scope": request.scope.to_dict(),
            "resource": {
                "scope": request.resource.scope.to_dict(),
                "resource_type": request.resource.resource_type,
                "resource_id": request.resource.resource_id,
            },
            "action": request.action,
            "risk": request.risk,
            "data_classification": request.data_classification,
            "actor": request.actor.to_dict(),
            "approver": None if request.approver is None else request.approver.to_dict(),
            "approval_reference": request.approval_reference,
            "policy": policy_digest(policy),
        }
    )


@dataclass(frozen=True, slots=True)
class _Entry:
    decision: AuthorizationDecision
    stored_at_epoch: int
    valid_until_epoch: int
    principals: frozenset[str]


class AuthorizationDecisionCache:
    """Bounded, freshness-checked cache in front of ``authorize``."""

    def __init__(
        self,
        *,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        for name, value in (("max_age_seconds", max_age_seconds), ("max_entries", max_entries)):
            if type(value) is not int or value <= 0:
                raise AuthorizationContractError(
                    "invalid_cache_bound", name, "must be a positive integer"
                )
        self._max_age = max_age_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    def authorize(
        self, request: AuthorizationRequest, policy: AuthorizationPolicy
    ) -> AuthorizationDecision:
        key = decision_cache_key(request, policy)
        now = request.evaluated_at_epoch
        entry = self._entries.get(key)
        if entry is not None:
            if entry.stored_at_epoch <= now < entry.valid_until_epoch:
                self.hits += 1
                self._entries.move_to_end(key)
                return replace(
                    entry.decision,
                    request_id=request.request_id,
                    evaluated_at_epoch=now,
                )
            del self._entries[key]
        self.misses += 1
        decision = authorize(request, policy)
        valid_until = now + self._max_age
        identities: list[ActorContext] = [request.actor]
        if request.approver is not None:
            identities.append(request.approver)
        for identity in identities:
            if identity.expires_at_epoch is not None:
                valid_until = min(valid_until, identity.expires_at_epoch)
        if valid_until > now:
            self._entries[key] = _Entry(
                decision=decision,
                stored_at_epoch=now,
                valid_until_epoch=valid_until,
                principals=frozenset(item.principal_id for item in identities),
            )
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return decision

    def invalidate_principal(self, principal_id: str) -> int:
        """Drop every entry that used ``principal_id`` as actor or approver."""

        doomed = [k for k, e in self._entries.items() if principal_id in e.principals]
        for key in doomed:
            del self._entries[key]
        return len(doomed)

    def clear(self) -> None:
        self._entries.clear()
