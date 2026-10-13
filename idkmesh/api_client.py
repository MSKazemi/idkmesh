"""Dependency-free Python client for the local IDKMesh Control Tower API.

API-11A (#746) intentionally covers the stable read/inspection surfaces only:
capability status, evidence inspection, the resource-oriented read model
(runs, run attempts, retained run evidence, derived WorkUnits and projects),
keyset-paginated event listings, and one bounded read of the Server-Sent
Events stream (``stream_events``). Human-decision recording is deliberately
absent until the authenticated mutation adapter (#740) exists.

The current Control Tower is loopback-only, so this client refuses non-loopback
base URLs rather than risking disclosure of the local session token.

The client performs exactly one HTTP request per method call. It never retries,
reconnects, follows redirects, records human decisions, dispatches work, writes
canonical state, pushes Git, or merges. An event stream ends when the server,
the caller or a client-side bound ends it; resuming is the caller's decision,
made with the documented ``Last-Event-ID`` sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
import re
import socket
import time
from typing import Any, Generic, Iterator, Mapping, TypeVar
from urllib.parse import quote, urlencode, urlsplit

from idkmesh import __version__
from idkmesh.api_observability import METRICS_KIND
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.service_runtime import REQUEST_ID_HEADER, SSE_MAX_STREAM_SECONDS
from idkmesh.work_unit_binding import canonical_digest

JSON_MEDIA_TYPE = "application/json"
V1_MEDIA_TYPE = "application/vnd.idkmesh.control-tower.v1+json"
CONTENT_DIGEST_HEADER = "X-IDKMesh-Content-Digest"
API_VERSION = "v1"
MAX_LIST_LIMIT = 200
STREAM_MEDIA_TYPE = "text/event-stream"
# One SSE line and one whole frame are each bounded; the largest legitimate
# frame is a single ``data:`` line carrying one event envelope.
MAX_STREAM_FRAME_BYTES = 1_048_576
MIN_STREAM_FRAME_BYTES = 256
MAX_STREAM_FRAME_BYTES_CEILING = 16_777_216
MAX_STREAM_FRAME_LINES = 16
MAX_STREAM_ERROR_BODY_BYTES = 1_048_576
MAX_STREAM_SEQUENCE = 10**18 - 1  # Last-Event-ID is at most 18 ASCII digits
# Client-side wall-clock bound: the server's own maximum stream lifetime plus
# a margin, so a misbehaving server cannot hold the caller open forever.
DEFAULT_STREAM_MAX_SECONDS = SSE_MAX_STREAM_SECONDS + 15.0

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STREAM_SEQUENCE_RE = re.compile(r"^[0-9]{1,18}$")
_STREAM_RETRY_RE = re.compile(r"^[0-9]{1,9}$")
_STREAM_END_RE = re.compile(
    r"^stream-ended reason=(max-duration|shutdown|store-error)$"
)
_EVENT_ID_RE = re.compile(r"^evt-[0-9]{12}$")
_EVENT_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "event_id",
        "sequence",
        "occurred_at",
        "event_type",
        "principal",
        "authority_class",
        "project_id",
        "work_unit_id",
        "run_id",
        "attempt_id",
        "source_revision",
        "evidence_reference",
        "payload",
        "payload_digest",
    }
)
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


def _json_object(raw: bytes, what: str = "response body") -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError(
            f"{what} is not UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc
    try:
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"{what} is not valid JSON ({exc})") from exc
    except RecursionError as exc:
        # Totality: pathological nesting is a protocol error, never a raw
        # RecursionError escaping to the transport layer.
        raise ProtocolError(
            f"{what} JSON nesting is too deep") from exc
    if not isinstance(value, dict):
        raise ProtocolError(f"{what} JSON root must be an object")
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


def _positive_seconds(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise ClientConfigurationError(
            f"{field} must be a finite number greater than zero"
        )
    return float(value)


@dataclass(frozen=True)
class StreamedEvent:
    """One validated event delivered by ``ControlTowerClient.stream_events``.

    ``event`` is the full ``idkmesh-event`` envelope; ``sequence`` is the value
    to send back as ``last_event_id`` to resume after this event.
    """

    sequence: int
    event_type: str
    event: dict[str, Any]


class EventStream:
    """One open, bounded, strictly parsed Server-Sent Events response.

    Iterate it to receive ``StreamedEvent`` values in strictly increasing
    ``sequence`` order. It is a context manager: leaving the ``with`` block (or
    calling ``close()``) releases the connection, and so the server's stream
    slot, at once. Any failure closes the stream before the exception
    propagates. It is not thread-safe.

    Delivery is at-least-once across *connections* (dedupe on ``event_id``);
    inside one stream the order is checked, so a repeated or older sequence is
    a ``ProtocolError``. When iteration stops, ``end_reason`` says why:
    ``max-duration``, ``shutdown`` or ``store-error`` (the server's own
    ``stream-ended`` marker), or ``client-max-events`` / ``client-max-seconds``
    (a bound you set). The stream never reconnects; to resume, open a new one
    with ``last_event_id=stream.last_event_id``.
    """

    def __init__(
        self,
        *,
        response: http.client.HTTPResponse,
        sock: socket.socket,
        request_id: str,
        idle_timeout: float,
        max_frame_bytes: int,
        max_events: int | None,
        deadline: float,
        last_event_id: int | None,
        filters: Mapping[str, str],
    ) -> None:
        self._response = response
        self._sock = sock
        self._idle_timeout = idle_timeout
        self._max_frame_bytes = max_frame_bytes
        self._max_events = max_events
        self._deadline = deadline
        self._filters = dict(filters)
        self._delivered = 0
        self._closed = False
        self.request_id = request_id
        self.retry_ms: int | None = None
        self.end_reason: str | None = None
        self.last_event_id = last_event_id

    def __iter__(self) -> Iterator[StreamedEvent]:
        return self

    def __enter__(self) -> "EventStream":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the connection; safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        for closer in (self._response.close, self._sock.close):
            try:
                closer()
            except OSError:
                pass

    def __next__(self) -> StreamedEvent:
        if self._closed:
            raise StopIteration
        try:
            event = self._next_event()
        except BaseException:
            self.close()
            raise
        if event is None:
            self.close()
            raise StopIteration
        return event

    def _finish(self, reason: str) -> None:
        self.end_reason = reason

    def _next_event(self) -> StreamedEvent | None:
        while True:
            if self._max_events is not None and self._delivered >= self._max_events:
                self._finish("client-max-events")
                return None
            lines = self._read_frame()
            if lines is None:
                return None
            fields = self._parse_fields(lines)
            if fields is None:
                continue
            if fields == "end":
                return None
            return self._event_from_fields(fields)

    def _read_line(self) -> bytes | None:
        """One LF-terminated line without its terminator; None at clean EOF."""
        limit = self._max_frame_bytes
        try:
            line = self._response.readline(limit + 1)
        except (OSError, http.client.HTTPException) as exc:
            if isinstance(exc, socket.timeout) and time.monotonic() >= self._deadline:
                raise _Deadline() from exc
            if isinstance(exc, socket.timeout):
                raise TransportError(
                    "event stream was idle for longer than idle_timeout; "
                    f"resume with last_event_id={self.last_event_id!r}"
                ) from exc
            raise TransportError(f"event stream read failed: {exc}") from exc
        if not line:
            return None
        if len(line) > limit:
            raise ProtocolError(
                f"event stream line exceeds the {limit}-byte frame bound"
            )
        if not line.endswith(b"\n"):
            raise ProtocolError("event stream ended inside a line")
        return line[:-1]

    def _read_frame(self) -> list[str] | None:
        """Lines of the next frame, or None when iteration should stop."""
        lines: list[str] = []
        total = 0
        while True:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self._finish("client-max-seconds")
                return None
            self._sock.settimeout(min(self._idle_timeout, remaining))
            try:
                raw = self._read_line()
            except _Deadline:
                self._finish("client-max-seconds")
                return None
            if raw is None:
                if lines:
                    raise ProtocolError("event stream ended inside a frame")
                raise TransportError(
                    "event stream closed without a stream-ended marker; "
                    f"resume with last_event_id={self.last_event_id!r}"
                )
            total += len(raw) + 1
            if total > self._max_frame_bytes:
                raise ProtocolError(
                    f"event stream frame exceeds the {self._max_frame_bytes}-byte bound"
                )
            if raw == b"":
                if not lines:
                    raise ProtocolError("event stream sent an empty frame")
                return lines
            if len(lines) >= MAX_STREAM_FRAME_LINES:
                raise ProtocolError("event stream frame has too many lines")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProtocolError(
                    f"event stream line is not UTF-8 ({exc.reason} at byte {exc.start})"
                ) from exc
            if "\r" in text:
                raise ProtocolError("event stream line contains a carriage return")
            lines.append(text)

    def _parse_fields(self, lines: list[str]) -> dict[str, str] | str | None:
        """Interpret one frame. None: skip it; "end": stop; dict: event fields."""
        if all(line.startswith(":") for line in lines):
            if len(lines) != 1:
                raise ProtocolError("event stream comment frame has several lines")
            comment = lines[0][1:]
            comment = comment[1:] if comment.startswith(" ") else comment
            if comment == "keepalive":
                return None
            match = _STREAM_END_RE.fullmatch(comment)
            if match is None:
                raise ProtocolError(
                    f"unexpected event stream comment {comment[:60]!r}"
                )
            self._finish(match.group(1))
            return "end"
        fields: dict[str, str] = {}
        for line in lines:
            name, separator, value = line.partition(":")
            if not separator or name not in {"id", "event", "data", "retry"}:
                raise ProtocolError(
                    f"unexpected event stream field {name[:40]!r}"
                )
            if name in fields:
                raise ProtocolError(f"duplicate event stream field {name!r}")
            fields[name] = value[1:] if value.startswith(" ") else value
        if "retry" in fields:
            if (
                len(fields) != 1
                or self.retry_ms is not None
                or self._delivered
                or _STREAM_RETRY_RE.fullmatch(fields["retry"]) is None
            ):
                raise ProtocolError("invalid or misplaced event stream retry hint")
            self.retry_ms = int(fields["retry"])
            return None
        if set(fields) != {"id", "event", "data"}:
            raise ProtocolError(
                "event frame must carry exactly one id, event and data field"
            )
        return fields

    def _event_from_fields(self, fields: Mapping[str, str]) -> StreamedEvent:
        if _STREAM_SEQUENCE_RE.fullmatch(fields["id"]) is None:
            raise ProtocolError("event stream id is not a sequence number")
        sequence = int(fields["id"])
        if sequence < 1:
            raise ProtocolError("event stream sequence must be at least 1")
        if self.last_event_id is not None and sequence <= self.last_event_id:
            raise ProtocolError(
                f"event stream sequence {sequence} is not after "
                f"{self.last_event_id}"
            )
        envelope = _json_object(
            fields["data"].encode("utf-8"), what="event stream data frame"
        )
        keys = set(envelope)
        if keys != _EVENT_KEYS:
            raise ProtocolError(
                "event envelope keys do not match the idkmesh-event schema: "
                f"missing={sorted(_EVENT_KEYS - keys)} extra={sorted(keys - _EVENT_KEYS)}"
            )
        event_type = envelope["event_type"]
        event_id = envelope["event_id"]
        if (
            envelope["schema_version"] != "0.1"
            or envelope["kind"] != "idkmesh-event"
            or not isinstance(event_id, str)
            or _EVENT_ID_RE.fullmatch(event_id) is None
            or type(envelope["sequence"]) is not int
            or envelope["sequence"] != sequence
            or not isinstance(event_type, str)
            or not event_type
            or event_type != fields["event"]
            or not isinstance(envelope["payload"], Mapping)
        ):
            raise ProtocolError(
                "event frame fields disagree with its idkmesh-event envelope"
            )
        for name, expected in self._filters.items():
            if envelope.get(name) != expected:
                raise ProtocolError(
                    f"event {name} does not match the requested filter"
                )
        expected_digest = envelope["payload_digest"]
        if (
            not isinstance(expected_digest, str)
            or _DIGEST_RE.fullmatch(expected_digest) is None
        ):
            raise ProtocolError("event payload_digest is invalid")
        actual_digest = canonical_digest(envelope["payload"])
        if actual_digest != expected_digest:
            raise IntegrityError(
                "event payload digest mismatch: "
                f"reported={expected_digest} computed={actual_digest}"
            )
        self.last_event_id = sequence
        self._delivered += 1
        return StreamedEvent(
            sequence=sequence, event_type=event_type, event=envelope
        )


class _Deadline(Exception):
    """Internal: the client-side wall-clock bound fired during a read."""


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

        self._timeout = _positive_seconds(timeout, "timeout")

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

        return self._decode_response(response, raw)

    def _decode_response(
        self,
        response: http.client.HTTPResponse,
        raw: bytes,
    ) -> ApiResult[dict[str, Any]]:
        """Validate one fully read JSON response; raise the typed taxonomy."""
        # Media types are case-insensitive and RFC 9110 field values tolerate
        # optional whitespace, so normalize exactly the way the server side
        # does before deciding. Genuinely wrong media types (HTML from a
        # misconfigured proxy, empty values) still fail closed as ProtocolError.
        media_type = (
            (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        )
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

    def get_openapi(self) -> ApiResult[dict[str, Any]]:
        """Download the machine-readable definition of the *running* API.

        The document is the OpenAPI 3.x description served by this exact
        Control Tower build (``GET /api/v1/openapi.json``), so integrators
        can discover the live surface without reading server code. It has no
        IDKMesh ``kind`` envelope; the client instead checks the OpenAPI
        version marker and the ``info`` / ``paths`` structure and fails
        closed with ``ProtocolError`` otherwise.
        """
        result = self._request("GET", f"/api/{API_VERSION}/openapi.json")
        document = result.value
        version = document.get("openapi")
        if not isinstance(version, str) or not version.startswith("3."):
            raise ProtocolError("openapi response has no OpenAPI 3.x version")
        if not isinstance(document.get("info"), Mapping) or not isinstance(
            document.get("paths"), Mapping
        ):
            raise ProtocolError("openapi response is missing info or paths")
        return result

    def get_metrics(self) -> ApiResult[dict[str, Any]]:
        """Read the fixed-cardinality, privacy-safe operational metrics."""
        return self._expect_kind(
            self._request("GET", f"/api/{API_VERSION}/metrics"),
            kind=METRICS_KIND,
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

    def stream_events(
        self,
        *,
        idle_timeout: float,
        last_event_id: int | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
        work_unit_id: str | None = None,
        event_type: str | None = None,
        max_events: int | None = None,
        max_seconds: float | None = None,
        max_frame_bytes: int = MAX_STREAM_FRAME_BYTES,
    ) -> EventStream:
        """Open one bounded read of ``GET /api/v1/events/stream`` (SSE).

        Exactly one HTTP request is made and the stream is never reopened;
        the returned ``EventStream`` ends when the server, you or a bound ends
        it. Without ``last_event_id`` it starts at the live tail; with it, it
        replays every event whose sequence is greater, then follows live
        events. To resume after an end, open a new stream with the old one's
        ``last_event_id`` (delivery is at-least-once: dedupe on ``event_id``).

        ``idle_timeout`` is mandatory: the longest wait for the next byte.
        The server sends a keepalive every 15 s, so use at least 20 for an
        otherwise quiet stream. ``max_seconds`` (default: the server's 300 s
        stream lifetime plus a margin) and ``max_events`` end the stream from
        the client side; ``max_frame_bytes`` bounds every line and frame.
        Errors the server reports before streaming (bad token, bad filter,
        ``too_many_streams``) raise ``ApiResponseError``.
        """
        idle = _positive_seconds(idle_timeout, "idle_timeout")
        lifetime = _positive_seconds(
            DEFAULT_STREAM_MAX_SECONDS if max_seconds is None else max_seconds,
            "max_seconds",
        )
        if last_event_id is not None and (
            isinstance(last_event_id, bool)
            or not isinstance(last_event_id, int)
            or not (0 <= last_event_id <= MAX_STREAM_SEQUENCE)
        ):
            raise ClientConfigurationError(
                "last_event_id must be a non-negative integer of at most 18 digits"
            )
        if max_events is not None and (
            isinstance(max_events, bool)
            or not isinstance(max_events, int)
            or max_events < 1
        ):
            raise ClientConfigurationError("max_events must be a positive integer")
        if (
            isinstance(max_frame_bytes, bool)
            or not isinstance(max_frame_bytes, int)
            or not (MIN_STREAM_FRAME_BYTES <= max_frame_bytes <= MAX_STREAM_FRAME_BYTES_CEILING)
        ):
            raise ClientConfigurationError(
                "max_frame_bytes must be an integer between "
                f"{MIN_STREAM_FRAME_BYTES} and {MAX_STREAM_FRAME_BYTES_CEILING}"
            )
        filters = {
            name: value
            for name, value in (
                ("project_id", _optional_filter(project_id, "project_id")),
                ("run_id", _optional_filter(run_id, "run_id")),
                ("work_unit_id", _optional_filter(work_unit_id, "work_unit_id")),
                ("event_type", _optional_filter(event_type, "event_type")),
            )
            if value is not None
        }
        path = f"/api/{API_VERSION}/events/stream"
        if filters:
            path = f"{path}?{urlencode(list(filters.items()))}"
        headers = {
            "Accept": STREAM_MEDIA_TYPE,
            TOKEN_HEADER: self._token,
            "User-Agent": f"idkmesh-python-client/{__version__}",
        }
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)

        started = time.monotonic()
        connection = http.client.HTTPConnection(
            self._connect_host,
            self._port,
            timeout=self._timeout,
        )
        sock: socket.socket | None = None
        response: http.client.HTTPResponse | None = None
        opened = False
        try:
            try:
                connection.request("GET", path, headers=headers)
                # getresponse() detaches the socket from the connection for a
                # close-delimited body, so keep our own reference first.
                sock = connection.sock
                response = connection.getresponse()
                if response.status != 200:
                    raw = response.read(MAX_STREAM_ERROR_BODY_BYTES + 1)
            except (OSError, http.client.HTTPException) as exc:
                raise TransportError(
                    f"GET {path.split('?', 1)[0]} failed without retry: {exc}"
                ) from exc
            if response.status != 200:
                if len(raw) > MAX_STREAM_ERROR_BODY_BYTES:
                    raise ProtocolError("event stream error body is too large")
                self._decode_response(response, raw)
                raise ProtocolError(
                    f"event stream answered HTTP {response.status}, expected 200"
                )
            media_type = (
                (response.getheader("Content-Type") or "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if media_type != STREAM_MEDIA_TYPE:
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
            if sock is None:
                raise TransportError("event stream connection was not established")
            stream = EventStream(
                response=response,
                sock=sock,
                request_id=request_id,
                idle_timeout=idle,
                max_frame_bytes=max_frame_bytes,
                max_events=max_events,
                deadline=started + lifetime,
                last_event_id=last_event_id,
                filters=filters,
            )
            opened = True
            return stream
        finally:
            if not opened:
                for closer in (
                    getattr(response, "close", None),
                    getattr(sock, "close", None),
                    connection.close,
                ):
                    if closer is not None:
                        try:
                            closer()
                        except OSError:
                            pass


__all__ = [
    "ApiResponseError",
    "ApiResult",
    "ClientConfigurationError",
    "ControlTowerClient",
    "ControlTowerClientError",
    "EventPage",
    "EventStream",
    "IntegrityError",
    "ListPage",
    "ProtocolError",
    "ResponseMetadata",
    "StreamedEvent",
    "TransportError",
]
