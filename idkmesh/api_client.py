"""Dependency-free Python client for the local IDKMesh Control Tower API.

API-11A (#746) intentionally covers the stable read/inspection surfaces only:
capability status, evidence inspection, the resource-oriented read model
(runs, run attempts, retained run evidence, derived WorkUnits and projects),
and keyset-paginated event listings. Human-decision recording is deliberately
absent until the authenticated mutation adapter (#740) exists.

The current Control Tower is loopback-only, so this client refuses non-loopback
base URLs rather than risking disclosure of the local session token.

The client performs exactly one HTTP request per method call. It never retries,
follows redirects, records human decisions, dispatches work, writes canonical
state, pushes Git, or merges.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
import re
from typing import Any, Generic, Mapping, TypeVar
from urllib.parse import quote, urlencode, urlsplit

from idkmesh import __version__
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.service_runtime import REQUEST_ID_HEADER
from idkmesh.work_unit_binding import canonical_digest

JSON_MEDIA_TYPE = "application/json"
V1_MEDIA_TYPE = "application/vnd.idkmesh.control-tower.v1+json"
CONTENT_DIGEST_HEADER = "X-IDKMesh-Content-Digest"
API_VERSION = "v1"
MAX_LIST_LIMIT = 200

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_TOKEN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-._~"
)

T = TypeVar("T")


class ControlTowerClientError(RuntimeError):
    """Base class for stable client-side failure categories."""


class ClientConfigurationError(ControlTowerClientError):
    """The client configuration is unsafe or invalid."""


class TransportError(ControlTowerClientError):
    """The one attempted HTTP exchange could not complete."""


class ProtocolError(ControlTowerClientError):
    """The server response does not satisfy the published transport contract."""


class IntegrityError(ProtocolError):
    """A digest-bound response or embedded evidence object failed verification."""


class ApiResponseError(ControlTowerClientError):
    """A schema-shaped IDKMesh API error response."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool,
        details: Mapping[str, Any] | None,
        request_id: str,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = dict(details or {})
        self.request_id = request_id
        super().__init__(f"HTTP {status_code} {code}: {message}")


@dataclass(frozen=True)
class ResponseMetadata:
    """Operational metadata retained for every successful API response."""

    status_code: int
    request_id: str
    content_digest: str


@dataclass(frozen=True)
class ApiResult(Generic[T]):
    """One typed value plus the response metadata needed for correlation."""

    value: T
    metadata: ResponseMetadata

    @property
    def request_id(self) -> str:
        return self.metadata.request_id


@dataclass(frozen=True)
class ListPage:
    """One bounded keyset-paginated page from a list endpoint.

    ``next_cursor`` stays opaque: clients must echo it verbatim and never
    construct or interpret cursors themselves.
    """

    items: tuple[dict[str, Any], ...]
    next_cursor: str | None
    limit: int


# The first list surface was the event listing; keep the name as a stable alias.
EventPage = ListPage


def _reject_json_constant(token: str) -> Any:
    raise ProtocolError(f"response contains non-standard JSON constant {token!r}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"response contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError(
            f"response body is not UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc
    try:
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"response body is not valid JSON ({exc})") from exc
    if not isinstance(value, dict):
        raise ProtocolError("response JSON root must be an object")
    return value


def _resource_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ClientConfigurationError(f"{field} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ClientConfigurationError(
            f"{field} must not contain ASCII control characters"
        )
    return value


def _optional_filter(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _resource_id(value, field)


def _list_limit(limit: int) -> int:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not (1 <= limit <= MAX_LIST_LIMIT)
    ):
        raise ClientConfigurationError(
            f"limit must be an integer between 1 and {MAX_LIST_LIMIT}"
        )
    return limit


def _list_query(
    *,
    limit: int,
    cursor: str | None,
    filters: Mapping[str, str | None],
) -> list[tuple[str, str]]:
    """Build one bounded list query string; validation happens before I/O."""
    query_items: list[tuple[str, str]] = [("limit", str(_list_limit(limit)))]
    if cursor is not None:
        query_items.append(("cursor", _resource_id(cursor, "cursor")))
    query_items.extend(
        (name, value)
        for name, value in (
            (name, _optional_filter(value, name))
            for name, value in filters.items()
        )
        if value is not None
    )
    return query_items


class ControlTowerClient:
    """Official client for stable Control Tower v1 read/inspect methods.

    timeout is mandatory by construction. The current API profile is local
    only, so base_url must use HTTP with host 127.0.0.1 or localhost and may
    contain only an optional port.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float,
    ) -> None:
        if not isinstance(base_url, str) or not base_url:
            raise ClientConfigurationError("base_url must be a non-empty string")
        parsed = urlsplit(base_url)
        if parsed.scheme != "http":
            raise ClientConfigurationError(
                "local Control Tower base_url must use http"
            )
        if parsed.username is not None or parsed.password is not None:
            raise ClientConfigurationError(
                "base_url must not contain user information"
            )
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ClientConfigurationError(
                "local Control Tower base_url must target loopback"
            )
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ClientConfigurationError(
                "base_url must contain only scheme, loopback host, and optional port"
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise ClientConfigurationError("base_url contains an invalid port") from exc
        self._port = 80 if port is None else port
        self._connect_host = "127.0.0.1"

        if (
            not isinstance(token, str)
            or not (32 <= len(token) <= 4096)
            or any(char not in _SAFE_TOKEN_CHARS for char in token)
        ):
            raise ClientConfigurationError(
                "token must be 32-4096 characters from the documented safe ASCII alphabet"
            )
        self._token = token

        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or float(timeout) <= 0.0
        ):
            raise ClientConfigurationError(
                "timeout must be a finite number greater than zero"
            )
        self._timeout = float(timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
    ) -> ApiResult[dict[str, Any]]:
        headers = {
            "Accept": JSON_MEDIA_TYPE,
            TOKEN_HEADER: self._token,
            "User-Agent": f"idkmesh-python-client/{__version__}",
        }
        body: bytes | None = None
        if payload is not None:
            try:
                body = json.dumps(
                    dict(payload),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ClientConfigurationError(
                    f"request payload is not strict JSON: {exc}"
                ) from exc
            headers["Content-Type"] = JSON_MEDIA_TYPE

        connection = http.client.HTTPConnection(
            self._connect_host,
            self._port,
            timeout=self._timeout,
        )
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise TransportError(
                f"{method} {path} failed without retry: {exc}"
            ) from exc
        finally:
            connection.close()

        media_type = (response.getheader("Content-Type") or "").split(";", 1)[0]
        if media_type not in {JSON_MEDIA_TYPE, V1_MEDIA_TYPE}:
            raise ProtocolError(
                f"unexpected response media type {media_type!r}"
            )

        request_id = response.getheader(REQUEST_ID_HEADER)
        if (
            not isinstance(request_id, str)
            or _REQUEST_ID_RE.fullmatch(request_id) is None
        ):
            raise ProtocolError(
                f"missing or invalid {REQUEST_ID_HEADER} response header"
            )

        content_digest = response.getheader(CONTENT_DIGEST_HEADER)
        if (
            not isinstance(content_digest, str)
            or _DIGEST_RE.fullmatch(content_digest) is None
        ):
            raise ProtocolError(
                f"missing or invalid {CONTENT_DIGEST_HEADER} response header"
            )

        document = _json_object(raw)
        actual_digest = canonical_digest(document)
        if actual_digest != content_digest:
            raise IntegrityError(
                "response content digest mismatch: "
                f"header={content_digest} computed={actual_digest}"
            )

        metadata = ResponseMetadata(
            status_code=response.status,
            request_id=request_id,
            content_digest=content_digest,
        )

        if response.status >= 400:
            self._raise_api_error(document, metadata)
        if not (200 <= response.status < 300):
            raise ProtocolError(
                f"unexpected HTTP success status {response.status}"
            )
        return ApiResult(value=document, metadata=metadata)

    @staticmethod
    def _raise_api_error(
        document: Mapping[str, Any],
        metadata: ResponseMetadata,
    ) -> None:
        if (
            document.get("kind") != "idkmesh-api-error"
            or document.get("ok") is not False
            or not isinstance(document.get("error"), Mapping)
        ):
            raise ProtocolError(
                f"HTTP {metadata.status_code} did not carry an IDKMesh error envelope"
            )
        error = document["error"]
        code = error.get("code")
        message = error.get("message")
        retryable = error.get("retryable")
        details = error.get("details")
        if (
            not isinstance(code, str)
            or not code
            or not isinstance(message, str)
            or not message
            or type(retryable) is not bool
            or (details is not None and not isinstance(details, Mapping))
        ):
            raise ProtocolError("IDKMesh error envelope has invalid fields")
        raise ApiResponseError(
            status_code=metadata.status_code,
            code=code,
            message=message,
            retryable=retryable,
            details=details,
            request_id=metadata.request_id,
        )

    @staticmethod
    def _expect_kind(
        result: ApiResult[dict[str, Any]],
        *,
        kind: str,
    ) -> ApiResult[dict[str, Any]]:
        if result.value.get("kind") != kind:
            raise ProtocolError(
                f"expected response kind {kind!r}, got {result.value.get('kind')!r}"
            )
        return result

    @staticmethod
    def _expect_identity(actual: Any, expected: str, field: str) -> None:
        """Fail closed unless the response names the requested resource."""
        if actual != expected:
            raise ProtocolError(
                f"response {field} does not match the request: "
                f"expected {expected!r}, got {actual!r}"
            )

    def _list_document(
        self,
        resource: str,
        query_items: list[tuple[str, str]],
    ) -> ApiResult[ListPage]:
        """Fetch and strictly parse one ``idkmesh-list`` page document."""
        raw = self._request(
            "GET",
            f"/api/{API_VERSION}/{resource}?{urlencode(query_items)}",
        )
        document = raw.value
        if document.get("kind") != "idkmesh-list":
            raise ProtocolError(
                f"expected response kind 'idkmesh-list', got {document.get('kind')!r}"
            )
        items = document.get("items")
        page = document.get("page")
        if not isinstance(items, list) or not isinstance(page, Mapping):
            raise ProtocolError("list response has invalid page structure")
        next_cursor = page.get("next_cursor")
        applied_limit = page.get("limit")
        if next_cursor is not None and (
            not isinstance(next_cursor, str) or not next_cursor
        ):
            raise ProtocolError("list next_cursor must be null or non-empty")
        if (
            isinstance(applied_limit, bool)
            or not isinstance(applied_limit, int)
            or applied_limit < 1
        ):
            raise ProtocolError("list limit is invalid")
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ProtocolError(
                    f"list item {index} must be a JSON object"
                )
            normalized_items.append(dict(item))
        return ApiResult(
            value=ListPage(
                items=tuple(normalized_items),
                next_cursor=next_cursor,
                limit=applied_limit,
            ),
            metadata=raw.metadata,
        )

    def status(self) -> ApiResult[dict[str, Any]]:
        """Return authenticated capability/status discovery plus request ID."""
        return self._expect_kind(
            self._request("GET", f"/api/{API_VERSION}/status"),
            kind="idkmesh-control-tower-status",
        )

    def inspect_run_evidence(
        self,
        report: Mapping[str, Any],
    ) -> ApiResult[dict[str, Any]]:
        """Validate one supplied Run Evidence Report and verify its snapshot."""
        if not isinstance(report, Mapping):
            raise ClientConfigurationError("report must be a mapping")
        result = self._expect_kind(
            self._request(
                "POST",
                f"/api/{API_VERSION}/run-evidence/inspect",
                payload=report,
            ),
            kind="idkmesh-control-tower-inspection-response",
        )
        snapshot = result.value.get("snapshot")
        expected = result.value.get("snapshot_digest")
        if (
            not isinstance(snapshot, Mapping)
            or not isinstance(expected, str)
            or _DIGEST_RE.fullmatch(expected) is None
        ):
            raise ProtocolError(
                "inspection response is missing a digest-bound snapshot"
            )
        actual = canonical_digest(snapshot)
        if actual != expected:
            raise IntegrityError(
                "inspection snapshot digest mismatch: "
                f"reported={expected} computed={actual}"
            )
        return result

    def get_run(self, run_id: str) -> ApiResult[dict[str, Any]]:
        """Read one durable Product Spine run without altering it."""
        encoded = quote(_resource_id(run_id, "run_id"), safe="/:")
        result = self._expect_kind(
            self._request("GET", f"/api/{API_VERSION}/runs/{encoded}"),
            kind="idkmesh-control-tower-run-response",
        )
        run = result.value.get("run")
        if not isinstance(run, Mapping):
            raise ProtocolError("run response is missing its run resource")
        self._expect_identity(run.get("run_id"), run_id, "run.run_id")
        return result

    def get_run_evidence(
        self,
        run_id: str,
    ) -> ApiResult[dict[str, Any]]:
        """Read retained evidence and independently verify its canonical digest."""
        encoded = quote(_resource_id(run_id, "run_id"), safe="/:")
        result = self._expect_kind(
            self._request(
                "GET",
                f"/api/{API_VERSION}/runs/{encoded}/evidence",
            ),
            kind="idkmesh-control-tower-run-evidence-response",
        )
        self._expect_identity(result.value.get("run_id"), run_id, "run_id")
        report = result.value.get("evidence_report")
        expected = result.value.get("evidence_report_digest")
        if (
            not isinstance(report, Mapping)
            or not isinstance(expected, str)
            or _DIGEST_RE.fullmatch(expected) is None
        ):
            raise ProtocolError(
                "run evidence response is missing its canonical evidence binding"
            )
        actual = canonical_digest(report)
        if actual != expected:
            raise IntegrityError(
                "retained evidence digest mismatch: "
                f"reported={expected} computed={actual}"
            )
        return result

    def get_run_attempts(self, run_id: str) -> ApiResult[dict[str, Any]]:
        """Read one run's attempt rows without altering the run."""
        encoded = quote(_resource_id(run_id, "run_id"), safe="/:")
        result = self._expect_kind(
            self._request(
                "GET",
                f"/api/{API_VERSION}/runs/{encoded}/attempts",
            ),
            kind="idkmesh-control-tower-run-attempts-response",
        )
        self._expect_identity(result.value.get("run_id"), run_id, "run_id")
        if not isinstance(result.value.get("attempts"), list):
            raise ProtocolError("run attempts response has invalid attempts")
        return result

    def list_runs(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        state: str | None = None,
        project_id: str | None = None,
    ) -> ApiResult[ListPage]:
        """Return one bounded run page; exact-match filters, opaque cursors.

        ``state`` is matched exactly and an unrecognized value fails with
        ``invalid_state`` from the server (API Conventions v0.1 section 11);
        the client deliberately keeps no state vocabulary of its own.
        """
        return self._list_document(
            "runs",
            _list_query(
                limit=limit,
                cursor=cursor,
                filters={"state": state, "project_id": project_id},
            ),
        )

    def get_work_unit(self, work_unit_id: str) -> ApiResult[dict[str, Any]]:
        """Read one derived WorkUnit resource (counts and revisions only)."""
        encoded = quote(_resource_id(work_unit_id, "work_unit_id"), safe="/:")
        result = self._expect_kind(
            self._request("GET", f"/api/{API_VERSION}/work-units/{encoded}"),
            kind="idkmesh-control-tower-work-unit-response",
        )
        resource = result.value.get("work_unit")
        if not isinstance(resource, Mapping):
            raise ProtocolError(
                "work-unit response is missing its work_unit resource"
            )
        self._expect_identity(resource.get("id"), work_unit_id, "work_unit.id")
        return result

    def list_work_units(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        project_id: str | None = None,
    ) -> ApiResult[ListPage]:
        """Return one bounded WorkUnit page; ordered by WorkUnit id."""
        return self._list_document(
            "work-units",
            _list_query(
                limit=limit,
                cursor=cursor,
                filters={"project_id": project_id},
            ),
        )

    def list_connections(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ApiResult[ListPage]:
        """Return one bounded page of secret-free connector metadata.

        Items are the public-safe connection resources persisted by
        ``idkmesh connections import``, ordered by connection id; no filters.
        """
        return self._list_document(
            "connections",
            _list_query(limit=limit, cursor=cursor, filters={}),
        )

    def get_project(self, project_id: str) -> ApiResult[dict[str, Any]]:
        """Read one derived project summary (zero-filled run-state counts)."""
        encoded = quote(_resource_id(project_id, "project_id"), safe="/:")
        result = self._expect_kind(
            self._request("GET", f"/api/{API_VERSION}/projects/{encoded}"),
            kind="idkmesh-control-tower-project-response",
        )
        resource = result.value.get("project")
        if not isinstance(resource, Mapping):
            raise ProtocolError(
                "project response is missing its project resource"
            )
        self._expect_identity(
            resource.get("project_id"), project_id, "project.project_id"
        )
        return result

    def list_events(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
        work_unit_id: str | None = None,
        event_type: str | None = None,
    ) -> ApiResult[ListPage]:
        """Return one bounded event page; cursors stay opaque to the client."""
        return self._list_document(
            "events",
            _list_query(
                limit=limit,
                cursor=cursor,
                filters={
                    "project_id": project_id,
                    "run_id": run_id,
                    "work_unit_id": work_unit_id,
                    "event_type": event_type,
                },
            ),
        )


__all__ = [
    "ApiResponseError",
    "ApiResult",
    "ClientConfigurationError",
    "ControlTowerClient",
    "ControlTowerClientError",
    "EventPage",
    "IntegrityError",
    "ListPage",
    "ProtocolError",
    "ResponseMetadata",
    "TransportError",
]
