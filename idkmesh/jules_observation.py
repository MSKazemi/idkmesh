"""Normalize Jules Session state and immutable Activities for C2-D (#575).

Provider completion is candidate readiness only. This module never emits
verification, acceptance, or integration authority.

The observation layer intentionally retains structural metadata and event kinds,
not raw agent/user message content or patch bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from idkmesh.connector_errors import ConnectorError


_SESSION_RE = re.compile(r"sessions/[^/]+\Z")

_SESSION_STATE_MAP: dict[str, tuple[str, str | None]] = {
    "STATE_UNSPECIFIED": ("waiting_for_agent", None),
    "QUEUED": ("waiting_for_agent", None),
    "PLANNING": ("waiting_for_agent", None),
    "AWAITING_PLAN_APPROVAL": ("waiting_for_agent", "approve_plan"),
    "AWAITING_USER_FEEDBACK": ("waiting_for_agent", "user_feedback"),
    "IN_PROGRESS": ("waiting_for_agent", None),
    "PAUSED": ("waiting_for_agent", "inspect_paused_session"),
    "FAILED": ("failed", None),
    # Provider completion is never verification or integration.
    "COMPLETED": ("candidate_ready", None),
}

_KNOWN_ACTIVITY_FIELDS = (
    "planGenerated",
    "planApproved",
    "userMessaged",
    "agentMessaged",
    "progressUpdated",
    "sessionCompleted",
    "sessionFailed",
)

_ACTIVITY_TYPE = {
    "planGenerated": "plan_generated",
    "planApproved": "plan_approved",
    "userMessaged": "user_messaged",
    "agentMessaged": "agent_messaged",
    "progressUpdated": "progress_updated",
    "sessionCompleted": "session_completed",
    "sessionFailed": "session_failed",
}


class JulesObservationClient(Protocol):
    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """GET one decoded Jules JSON object."""


@dataclass(frozen=True)
class JulesSessionObservation:
    session_name: str
    session_id: str
    provider_state: str
    run_state: str
    action_required: str | None
    candidate_output_count: int
    update_time: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class JulesActivityObservation:
    name: str
    activity_id: str
    event_type: str
    originator: str
    create_time: str
    artifact_count: int
    has_change_set: bool
    plan_id: str | None = None


@dataclass(frozen=True)
class JulesActivityPage:
    activities: tuple[JulesActivityObservation, ...]
    next_page_token: str | None


def _session_name(value: str, connection_id: str) -> str:
    if not isinstance(value, str) or _SESSION_RE.fullmatch(value) is None:
        raise ConnectorError(
            code="configuration_error",
            message="Jules session name is invalid.",
            connection_id=connection_id,
        )
    return value


def _required_string(
    value: Any,
    *,
    field: str,
    connection_id: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed observation metadata.",
            connection_id=connection_id,
            details={"field": field},
        )
    return value


def _optional_string(
    value: Any,
    *,
    field: str,
    connection_id: str,
) -> str | None:
    if value is None:
        return None
    return _required_string(value, field=field, connection_id=connection_id)


def parse_session_observation(
    raw: Mapping[str, Any],
    *,
    expected_session_name: str,
    connection_id: str,
) -> JulesSessionObservation:
    name = _required_string(
        raw.get("name"),
        field="name",
        connection_id=connection_id,
    )
    session_id = _required_string(
        raw.get("id"),
        field="id",
        connection_id=connection_id,
    )
    if name != expected_session_name:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned a different Session than requested.",
            connection_id=connection_id,
            details={
                "requested_session": expected_session_name,
                "observed_session": name,
            },
        )

    provider_state = _required_string(
        raw.get("state"),
        field="state",
        connection_id=connection_id,
    )
    warnings: list[str] = []
    mapped = _SESSION_STATE_MAP.get(provider_state)
    if mapped is None:
        # Jules is alpha. New states fail safely as non-terminal waiting states
        # and require an explicit connector update before they can advance.
        run_state, action_required = "waiting_for_agent", None
        warnings.append("unknown_provider_state")
    else:
        run_state, action_required = mapped
        if provider_state == "STATE_UNSPECIFIED":
            warnings.append("provider_state_unspecified")

    outputs = raw.get("outputs", [])
    if not isinstance(outputs, list):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Session outputs.",
            connection_id=connection_id,
        )
    candidate_output_count = 0
    for index, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Session output metadata.",
                connection_id=connection_id,
                details={"output_index": index},
            )
        if isinstance(output.get("pullRequest"), Mapping):
            candidate_output_count += 1

    return JulesSessionObservation(
        session_name=name,
        session_id=session_id,
        provider_state=provider_state,
        run_state=run_state,
        action_required=action_required,
        candidate_output_count=candidate_output_count,
        update_time=_optional_string(
            raw.get("updateTime"),
            field="updateTime",
            connection_id=connection_id,
        ),
        warnings=tuple(warnings),
    )


def _plan_id_from_activity(
    raw: Mapping[str, Any],
    *,
    event_field: str | None,
    connection_id: str,
) -> str | None:
    if event_field == "planGenerated":
        event = raw[event_field]
        if not isinstance(event, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed plan activity metadata.",
                connection_id=connection_id,
            )
        plan = event.get("plan")
        if not isinstance(plan, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed plan activity metadata.",
                connection_id=connection_id,
            )
        return _required_string(
            plan.get("id"),
            field="planGenerated.plan.id",
            connection_id=connection_id,
        )

    if event_field == "planApproved":
        event = raw[event_field]
        if not isinstance(event, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed plan approval metadata.",
                connection_id=connection_id,
            )
        return _required_string(
            event.get("planId"),
            field="planApproved.planId",
            connection_id=connection_id,
        )
    return None


def parse_activity_observation(
    raw: Mapping[str, Any],
    *,
    session_name: str,
    connection_id: str,
) -> JulesActivityObservation:
    name = _required_string(
        raw.get("name"),
        field="name",
        connection_id=connection_id,
    )
    expected_prefix = session_name + "/activities/"
    if not name.startswith(expected_prefix) or len(name) <= len(expected_prefix):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned an Activity outside the requested Session.",
            connection_id=connection_id,
            details={"requested_session": session_name},
        )

    activity_id = _required_string(
        raw.get("id"),
        field="id",
        connection_id=connection_id,
    )
    originator = _required_string(
        raw.get("originator"),
        field="originator",
        connection_id=connection_id,
    )
    if originator not in {"user", "agent", "system"}:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned an unknown Activity originator.",
            connection_id=connection_id,
            details={"originator": originator},
        )
    create_time = _required_string(
        raw.get("createTime"),
        field="createTime",
        connection_id=connection_id,
    )

    populated_events = [
        field_name
        for field_name in _KNOWN_ACTIVITY_FIELDS
        if field_name in raw and raw[field_name] is not None
    ]
    if len(populated_events) > 1:
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules Activity contains multiple event types.",
            connection_id=connection_id,
            details={"activity_name": name},
        )
    event_field = populated_events[0] if populated_events else None
    event_type = _ACTIVITY_TYPE[event_field] if event_field else "activity"

    artifacts = raw.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ConnectorError(
            code="result_normalization_error",
            message="Jules returned malformed Activity artifacts.",
            connection_id=connection_id,
            details={"activity_name": name},
        )
    has_change_set = False
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Activity artifact metadata.",
                connection_id=connection_id,
                details={"activity_name": name, "artifact_index": index},
            )
        if isinstance(artifact.get("changeSet"), Mapping):
            has_change_set = True

    return JulesActivityObservation(
        name=name,
        activity_id=activity_id,
        event_type=event_type,
        originator=originator,
        create_time=create_time,
        artifact_count=len(artifacts),
        has_change_set=has_change_set,
        plan_id=_plan_id_from_activity(
            raw,
            event_field=event_field,
            connection_id=connection_id,
        ),
    )


class JulesObservationService:
    """Read Session/Activity state without granting acceptance authority."""

    def __init__(self, client: JulesObservationClient, *, connection_id: str) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._client = client
        self._connection_id = connection_id

    def get_session(self, session_name: str) -> JulesSessionObservation:
        session = _session_name(session_name, self._connection_id)
        raw = self._client.get_json("/" + session)
        return parse_session_observation(
            raw,
            expected_session_name=session,
            connection_id=self._connection_id,
        )

    def list_activities(
        self,
        session_name: str,
        *,
        page_size: int = 50,
        page_token: str | None = None,
        create_time: str | None = None,
    ) -> JulesActivityPage:
        session = _session_name(session_name, self._connection_id)
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise ValueError("page_size must be an integer from 1 to 100")

        query: dict[str, str | int] = {"pageSize": page_size}
        if page_token is not None:
            if not isinstance(page_token, str) or not page_token:
                raise ValueError("page_token must be a non-empty string or None")
            query["pageToken"] = page_token
        if create_time is not None:
            if not isinstance(create_time, str) or not create_time:
                raise ValueError("create_time must be a non-empty string or None")
            query["createTime"] = create_time

        raw = self._client.get_json(
            f"/{session}/activities",
            query=query,
        )
        activities_raw = raw.get("activities", [])
        if not isinstance(activities_raw, list):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules returned malformed Activities response.",
                connection_id=self._connection_id,
            )

        activities = tuple(
            parse_activity_observation(
                activity,
                session_name=session,
                connection_id=self._connection_id,
            )
            for activity in activities_raw
        )
        token = _optional_string(
            raw.get("nextPageToken"),
            field="nextPageToken",
            connection_id=self._connection_id,
        )
        return JulesActivityPage(
            activities=activities,
            next_page_token=token,
        )
