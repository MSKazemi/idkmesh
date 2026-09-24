"""Explicit authorization policy for the initial GitHub dispatch lane.

C5-D separates authenticated webhook identity from dispatch authority.

The first automatic lane is deliberately narrow:
- issues event only;
- labeled action only;
- one of the configured dispatch labels;
- one explicitly trusted actor login;
- one configured repository;
- allowed sender type.

Issue title/body/comment text never grants authority. The issue author's
association is informational unless project policy explicitly restricts it.
This module returns an authorization decision only and performs no dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from idkmesh.github_webhook_ingress import GitHubWebhookEnvelope


_ALLOWED_ASSOCIATIONS = frozenset(
    {
        "COLLABORATOR",
        "CONTRIBUTOR",
        "FIRST_TIMER",
        "FIRST_TIME_CONTRIBUTOR",
        "MANNEQUIN",
        "MEMBER",
        "NONE",
        "OWNER",
    }
)


def _nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_set(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> frozenset[str]:
    if isinstance(value, str):
        raise ValueError(f"{field_name} must be a collection of strings")
    try:
        items = frozenset(value)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a collection of strings") from exc
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    normalized = frozenset(item.strip() for item in items)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


@dataclass(frozen=True)
class GitHubDispatchAuthorizationPolicy:
    repository: str
    dispatch_labels: frozenset[str]
    trusted_actor_logins: frozenset[str]
    allowed_sender_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"User"})
    )
    allowed_issue_author_associations: frozenset[str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository",
            _nonempty(self.repository, "repository"),
        )
        labels = _string_set(self.dispatch_labels, "dispatch_labels")
        actors = _string_set(
            self.trusted_actor_logins,
            "trusted_actor_logins",
        )
        sender_types = _string_set(
            self.allowed_sender_types,
            "allowed_sender_types",
        )
        object.__setattr__(self, "dispatch_labels", labels)
        object.__setattr__(self, "trusted_actor_logins", actors)
        object.__setattr__(self, "allowed_sender_types", sender_types)

        associations = self.allowed_issue_author_associations
        if associations is not None:
            normalized = _string_set(
                associations,
                "allowed_issue_author_associations",
                allow_empty=True,
            )
            normalized = frozenset(item.upper() for item in normalized)
            unknown = sorted(set(normalized) - set(_ALLOWED_ASSOCIATIONS))
            if unknown:
                raise ValueError(
                    "unknown issue author association(s): "
                    + ", ".join(unknown)
                )
            object.__setattr__(
                self,
                "allowed_issue_author_associations",
                normalized,
            )

    @property
    def normalized_labels(self) -> frozenset[str]:
        return frozenset(label.casefold() for label in self.dispatch_labels)

    @property
    def normalized_actors(self) -> frozenset[str]:
        return frozenset(actor.casefold() for actor in self.trusted_actor_logins)


@dataclass(frozen=True)
class GitHubDispatchAuthorization:
    authorized: bool
    reasons: tuple[str, ...]
    repository: str
    delivery_id: str
    issue_number: int | None
    actor_login: str
    label_name: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "authorized": self.authorized,
            "reasons": list(self.reasons),
            "repository": self.repository,
            "delivery_id": self.delivery_id,
            "issue_number": self.issue_number,
            "actor_login": self.actor_login,
            "label_name": self.label_name,
        }


def authorize_github_issue_dispatch(
    envelope: GitHubWebhookEnvelope,
    policy: GitHubDispatchAuthorizationPolicy,
) -> GitHubDispatchAuthorization:
    """Authorize only the configured explicit issue-label dispatch lane."""

    if not isinstance(envelope, GitHubWebhookEnvelope):
        raise ValueError("envelope must be GitHubWebhookEnvelope")
    if not isinstance(policy, GitHubDispatchAuthorizationPolicy):
        raise ValueError("policy must be GitHubDispatchAuthorizationPolicy")

    reasons: list[str] = []

    if envelope.repository.casefold() != policy.repository.casefold():
        reasons.append("repository_not_authorized")

    if envelope.event != "issues":
        reasons.append("event_not_dispatchable")
    elif envelope.action != "labeled":
        reasons.append("action_not_dispatchable")

    if envelope.subject_number is None:
        reasons.append("issue_number_missing")

    if (
        envelope.label_name is None
        or envelope.label_name.casefold() not in policy.normalized_labels
    ):
        reasons.append("dispatch_label_not_configured")

    if envelope.sender_type not in policy.allowed_sender_types:
        reasons.append("sender_type_not_trusted")

    if envelope.sender_login.casefold() not in policy.normalized_actors:
        reasons.append("actor_not_trusted")

    associations = policy.allowed_issue_author_associations
    if associations is not None:
        if (
            envelope.author_association is None
            or envelope.author_association.upper() not in associations
        ):
            reasons.append("issue_author_association_not_allowed")

    return GitHubDispatchAuthorization(
        authorized=not reasons,
        reasons=tuple(reasons),
        repository=policy.repository,
        delivery_id=envelope.delivery_id,
        issue_number=envelope.subject_number,
        actor_login=envelope.sender_login,
        label_name=envelope.label_name,
    )
