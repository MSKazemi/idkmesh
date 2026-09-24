"""Compose Jules worker lifecycle into bounded candidate readiness.

This application service is the first place allowed to advance a completed Jules
Session from worker_completed to candidate_ready. It does so only after provider
PR outputs have passed the independent SCM CandidateReference binding.

It never performs verification, candidate selection, acceptance, merge, or
integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from idkmesh.candidate_reference import (
    GitHubPullRequestCandidateReference,
)
from idkmesh.connector_errors import ConnectorError
from idkmesh.github_candidate_reader import GitHubPullRequestResolution
from idkmesh.jules_candidates import JulesPullRequestHint
from idkmesh.jules_observation import JulesSessionObservation
from idkmesh.jules_sessions import (
    JulesSessionHandle,
    JulesSessionRequest,
)


_PHASES = {
    "waiting_for_agent",
    "failed",
    "worker_completed",
    "candidate_ready",
}


class JulesSessionCreator(Protocol):
    def create_session(
        self,
        request: JulesSessionRequest,
    ) -> JulesSessionHandle:
        ...


class JulesSessionObserver(Protocol):
    def get_session(
        self,
        session_name: str,
    ) -> JulesSessionObservation:
        ...


class JulesCandidateDiscoverer(Protocol):
    def discover_pull_request_hints(
        self,
        session: JulesSessionHandle,
    ) -> tuple[JulesPullRequestHint, ...]:
        ...


class JulesCandidateBinder(Protocol):
    def resolve_pull_request_hint(
        self,
        hint: JulesPullRequestHint,
    ) -> GitHubPullRequestResolution:
        ...


@dataclass(frozen=True)
class JulesLifecycleSnapshot:
    """One provider-neutral lifecycle observation for a Jules Session."""

    session: JulesSessionHandle
    observation: JulesSessionObservation
    phase: str
    candidate_hints: tuple[JulesPullRequestHint, ...] = ()
    candidates: tuple[GitHubPullRequestResolution, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError("unsupported Jules lifecycle phase")
        if self.phase == "candidate_ready":
            if not self.candidates:
                raise ValueError(
                    "candidate_ready requires at least one exact candidate"
                )
            if len(self.candidates) != len(self.candidate_hints):
                raise ValueError(
                    "candidate_ready requires every hint to be SCM-resolved"
                )
        elif self.candidates:
            raise ValueError(
                "exact candidates may appear only in candidate_ready snapshots"
            )
        if (
            self.candidate_hints
            and self.phase not in {"worker_completed", "candidate_ready"}
        ):
            raise ValueError(
                "candidate hints require worker completion"
            )

    @property
    def candidate_references(
        self,
    ) -> tuple[GitHubPullRequestCandidateReference, ...]:
        return tuple(candidate.reference for candidate in self.candidates)


class JulesLifecycleService:
    """Compose existing C2 boundaries without granting later-stage authority."""

    def __init__(
        self,
        *,
        session_creator: JulesSessionCreator,
        observer: JulesSessionObserver,
        discoverer: JulesCandidateDiscoverer,
        binder: JulesCandidateBinder,
        connection_id: str,
    ) -> None:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError("connection_id must be a non-empty string")
        self._session_creator = session_creator
        self._observer = observer
        self._discoverer = discoverer
        self._binder = binder
        self._connection_id = connection_id

    def start(
        self,
        request: JulesSessionRequest,
    ) -> JulesSessionHandle:
        """Create a Session through the already-guarded Session service."""

        if not isinstance(request, JulesSessionRequest):
            raise ValueError("request must be a JulesSessionRequest")
        handle = self._session_creator.create_session(request)
        if not isinstance(handle, JulesSessionHandle):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules Session creator returned an unexpected handle type.",
                connection_id=self._connection_id,
            )
        return handle

    def inspect(
        self,
        session: JulesSessionHandle,
    ) -> JulesLifecycleSnapshot:
        """Observe one Session and resolve candidates only after completion."""

        if not isinstance(session, JulesSessionHandle):
            raise ValueError("session must be a JulesSessionHandle")

        observation = self._observer.get_session(session.session_name)
        if not isinstance(observation, JulesSessionObservation):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules observer returned an unexpected observation type.",
                connection_id=self._connection_id,
            )
        if (
            observation.session_name != session.session_name
            or observation.session_id != session.session_id
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules lifecycle observation does not match the retained Session handle.",
                connection_id=self._connection_id,
                details={
                    "expected_session": session.session_name,
                    "observed_session": observation.session_name,
                },
            )
        if observation.run_state not in {
            "waiting_for_agent",
            "failed",
            "worker_completed",
        }:
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules observer returned an unsupported run state.",
                connection_id=self._connection_id,
                details={"run_state": observation.run_state},
            )

        if observation.run_state != "worker_completed":
            return JulesLifecycleSnapshot(
                session=session,
                observation=observation,
                phase=observation.run_state,
                warnings=observation.warnings,
            )

        hints = self._discoverer.discover_pull_request_hints(session)
        if not isinstance(hints, tuple) or any(
            not isinstance(hint, JulesPullRequestHint)
            for hint in hints
        ):
            raise ConnectorError(
                code="result_normalization_error",
                message="Jules candidate discoverer returned malformed hints.",
                connection_id=self._connection_id,
            )

        warnings = list(observation.warnings)
        if observation.candidate_output_count != len(hints):
            warnings.append(
                "candidate_output_count_differs_from_unique_hints"
            )

        if not hints:
            warnings.append("worker_completed_without_candidate")
            return JulesLifecycleSnapshot(
                session=session,
                observation=observation,
                phase="worker_completed",
                warnings=tuple(warnings),
            )

        candidates: list[GitHubPullRequestResolution] = []
        for hint in hints:
            if (
                hint.session_name != session.session_name
                or hint.repository.casefold()
                != session.repository.casefold()
            ):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules candidate hint does not match the retained Session identity.",
                    connection_id=self._connection_id,
                )
            resolved = self._binder.resolve_pull_request_hint(hint)
            if not isinstance(resolved, GitHubPullRequestResolution):
                raise ConnectorError(
                    code="result_normalization_error",
                    message="Jules candidate binder returned an unexpected resolution type.",
                    connection_id=self._connection_id,
                )
            candidates.append(resolved)

        return JulesLifecycleSnapshot(
            session=session,
            observation=observation,
            phase="candidate_ready",
            candidate_hints=hints,
            candidates=tuple(candidates),
            warnings=tuple(warnings),
        )
