"""Operator-gated Jules actions for C2-E (#575).

Plan approval and user messaging mutate a live Jules Session. They therefore
require explicit authorization evidence supplied by a trusted upper control
plane. Session state, issue text, or provider requests cannot self-authorize
these actions.

The returned receipt deliberately omits message content.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from idkmesh.connector_errors import ConnectorError


_SESSION_RE = re.compile(r"sessions/[^/]+\Z")
_ACTIONS = {"approve_plan", "send_message"}


class JulesActionClient(Protocol):
    def post_json(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST one Jules JSON request."""


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _session_name(value: str) -> str:
    if not isinstance(value, str) or _SESSION_RE.fullmatch(value) is None:
        raise ValueError("session_name must match sessions/{session}")
    return value


@dataclass(frozen=True)
class OperatorActionAuthorization:
    """Upper-layer evidence authorizing one concrete mutable Jules action."""

    authorization_id: str
    actor: str
    action: str
    session_name: str
    approved: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authorization_id",
            _nonempty(self.authorization_id, "authorization_id"),
        )
        object.__setattr__(self, "actor", _nonempty(self.actor, "actor"))
        object.__setattr__(self, "session_name", _session_name(self.session_name))
        if self.action not in _ACTIONS:
            raise ValueError("unsupported Jules operator action")
        if type(self.approved) is not bool:
            raise ValueError("approved must be a boolean")


@dataclass(frozen=True)
class JulesActionReceipt:
    session_name: str
    action: str
    authorization_id: str
    actor: str
    provider_acknowledged: bool = True


class JulesOperatorActionService:
    """Execute mutable Jules actions only with matching explicit authorization."""

    def __init__(self, client: JulesActionClient, *, connection_id: str) -> None:
        self._connection_id = _nonempty(connection_id, "connection_id")
        self._client = client

    def _authorize(
        self,
        *,
        session_name: str,
        expected_action: str,
        authorization: OperatorActionAuthorization,
    ) -> None:
        session = _session_name(session_name)
        if (
            not authorization.approved
            or authorization.action != expected_action
            or authorization.session_name != session
        ):
            raise ConnectorError(
                code="policy_denied",
                message="Jules operator action lacks matching explicit authorization.",
                connection_id=self._connection_id,
                details={
                    "authorization_id": authorization.authorization_id,
                    "expected_action": expected_action,
                    "authorized_action": authorization.action,
                    "expected_session": session,
                    "authorized_session": authorization.session_name,
                    "approved": authorization.approved,
                },
            )

    def approve_plan(
        self,
        session_name: str,
        *,
        authorization: OperatorActionAuthorization,
    ) -> JulesActionReceipt:
        session = _session_name(session_name)
        self._authorize(
            session_name=session,
            expected_action="approve_plan",
            authorization=authorization,
        )
        self._client.post_json(f"/{session}:approvePlan", body={})
        return JulesActionReceipt(
            session_name=session,
            action="approve_plan",
            authorization_id=authorization.authorization_id,
            actor=authorization.actor,
        )

    def send_message(
        self,
        session_name: str,
        *,
        prompt: str,
        authorization: OperatorActionAuthorization,
    ) -> JulesActionReceipt:
        session = _session_name(session_name)
        message = _nonempty(prompt, "prompt")
        self._authorize(
            session_name=session,
            expected_action="send_message",
            authorization=authorization,
        )
        self._client.post_json(
            f"/{session}:sendMessage",
            body={"prompt": message},
        )
        return JulesActionReceipt(
            session_name=session,
            action="send_message",
            authorization_id=authorization.authorization_id,
            actor=authorization.actor,
        )
