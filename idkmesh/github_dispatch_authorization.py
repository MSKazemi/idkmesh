"""Trusted actor/role authorization for GitHub dispatch (C5-F).

Authentication of a webhook request does not grant dispatch authority. This
module authorizes only an explicit, maintainer-configured issue-label action.

Authority is bound to:
- configured repository;
- issues/labeled action;
- configured dispatch label;
- numeric GitHub actor ID;
- expected actor login;
- maintainer-owned role;
- optional GitHub App installation ID.

Issue title/body text and issue-author reputation are not authorization inputs.
This module returns a decision only and performs no secret resolution, routing,
dispatch, GitHub mutation, verification, acceptance, push, or merge action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope


_ALLOWED_ROLES = frozenset(
    {
        "owner",
        "maintainer",
        "triager",
        "automation",
    }
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be an integer >= 1")
    return value


@dataclass(frozen=True, slots=True)
class TrustedGitHubActor:
    actor_id: int
    login: str
    role: str

    def __post_init__(self) -> None:
        _positive_int(self.actor_id, "actor_id")
        object.__setattr__(self, "login", _text(self.login, "login"))
        role = _text(self.role, "role").casefold()
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"unsupported trusted actor role: {role}")
        object.__setattr__(self, "role", role)


@dataclass(frozen=True, slots=True)
class GitHubDispatchAuthorizationPolicy:
    repository: str
    dispatch_labels: frozenset[str]
    trusted_actors: tuple[TrustedGitHubActor, ...]
    allowed_roles: frozenset[str] = frozenset(
        {"owner", "maintainer"}
    )
    allowed_installation_ids: frozenset[int] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository",
            _text(self.repository, "repository"),
        )

        if isinstance(self.dispatch_labels, str):
            raise ValueError("dispatch_labels must be a collection")
        labels = frozenset(
            _text(value, "dispatch_label")
            for value in self.dispatch_labels
        )
        if not labels:
            raise ValueError("dispatch_labels must not be empty")
        object.__setattr__(self, "dispatch_labels", labels)

        if not isinstance(self.trusted_actors, tuple) or not self.trusted_actors:
            raise ValueError("trusted_actors must be a non-empty tuple")
        if any(
            not isinstance(actor, TrustedGitHubActor)
            for actor in self.trusted_actors
        ):
            raise ValueError(
                "trusted_actors must contain TrustedGitHubActor values"
            )
        actor_ids = [actor.actor_id for actor in self.trusted_actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("trusted actor IDs must be unique")

        if isinstance(self.allowed_roles, str):
            raise ValueError("allowed_roles must be a collection")
        roles = frozenset(
            _text(value, "allowed_role").casefold()
            for value in self.allowed_roles
        )
        if not roles:
            raise ValueError("allowed_roles must not be empty")
        unknown = sorted(set(roles) - set(_ALLOWED_ROLES))
        if unknown:
            raise ValueError(
                "unsupported allowed role(s): " + ", ".join(unknown)
            )
        object.__setattr__(self, "allowed_roles", roles)

        installations = self.allowed_installation_ids
        if installations is not None:
            if isinstance(installations, (str, bytes)):
                raise ValueError(
                    "allowed_installation_ids must be a collection"
                )
            normalized = frozenset(
                _positive_int(value, "installation_id")
                for value in installations
            )
            if not normalized:
                raise ValueError(
                    "allowed_installation_ids must not be empty when configured"
                )
            object.__setattr__(
                self,
                "allowed_installation_ids",
                normalized,
            )

    def actor_by_id(self, actor_id: int) -> TrustedGitHubActor | None:
        for actor in self.trusted_actors:
            if actor.actor_id == actor_id:
                return actor
        return None

    @property
    def normalized_labels(self) -> frozenset[str]:
        return frozenset(
            label.casefold() for label in self.dispatch_labels
        )


@dataclass(frozen=True, slots=True)
class GitHubDispatchAuthorization:
    authorized: bool
    reasons: tuple[str, ...]
    delivery_id: str
    repository: str
    issue_number: int | None
    actor_id: int
    actor_login: str
    actor_role: str | None
    label_name: str | None
    installation_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "reasons": list(self.reasons),
            "delivery_id": self.delivery_id,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "actor_id": self.actor_id,
            "actor_login": self.actor_login,
            "actor_role": self.actor_role,
            "label_name": self.label_name,
            "installation_id": self.installation_id,
            "secret_resolution_allowed": self.authorized,
            "dispatch_performed": False,
        }


def authorize_github_dispatch(
    envelope: GitHubWebhookEnvelope,
    policy: GitHubDispatchAuthorizationPolicy,
) -> GitHubDispatchAuthorization:
    """Authorize the initial explicit issue-label dispatch lane."""

    if not isinstance(envelope, GitHubWebhookEnvelope):
        raise TypeError("envelope must be GitHubWebhookEnvelope")
    if not isinstance(policy, GitHubDispatchAuthorizationPolicy):
        raise TypeError(
            "policy must be GitHubDispatchAuthorizationPolicy"
        )

    reasons: list[str] = []

    if envelope.repository.casefold() != policy.repository.casefold():
        reasons.append("repository_not_authorized")

    if envelope.event != "issues":
        reasons.append("event_not_dispatchable")
    elif envelope.action != "labeled":
        reasons.append("action_not_dispatchable")

    if envelope.issue_number is None:
        reasons.append("issue_number_missing")

    if (
        envelope.label_name is None
        or envelope.label_name.casefold()
        not in policy.normalized_labels
    ):
        reasons.append("dispatch_label_not_authorized")

    actor = policy.actor_by_id(envelope.sender_id)
    if actor is None:
        reasons.append("actor_id_not_trusted")
        actor_role = None
    else:
        actor_role = actor.role
        if actor.login.casefold() != envelope.sender_login.casefold():
            reasons.append("actor_login_mismatch")
        if actor.role not in policy.allowed_roles:
            reasons.append("actor_role_not_authorized")

    allowed_installations = policy.allowed_installation_ids
    if allowed_installations is not None:
        if envelope.installation_id is None:
            reasons.append("installation_id_missing")
        elif envelope.installation_id not in allowed_installations:
            reasons.append("installation_not_authorized")

    return GitHubDispatchAuthorization(
        authorized=not reasons,
        reasons=tuple(reasons),
        delivery_id=envelope.delivery_id,
        repository=policy.repository,
        issue_number=envelope.issue_number,
        actor_id=envelope.sender_id,
        actor_login=envelope.sender_login,
        actor_role=actor_role,
        label_name=envelope.label_name,
        installation_id=envelope.installation_id,
    )
