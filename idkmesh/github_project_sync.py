"""Offline GitHub Projects field planning and fail-closed apply for C13-F/G (#608).

GitHub Projects is a *view*, never an input to dispatch, verification, human
decision, integration, or merge. This module therefore:

* derives run-state Project field values (state / verification / human
  decision) from a trusted canonical Product Spine run snapshot, reusing the
  display mapping of the run-label projection so labels and Project fields can
  never disagree;
* applies a field plan through a caller-injected writer, idempotently, with a
  canonical-source freshness re-check before every write;
* converts every Projects failure (missing permission, transport error, stale
  source) into a *result*, never an exception that could block WorkUnit
  execution.

There is no GitHub transport, HTTP client or token handling here. The caller
supplies the trusted field ids, the trusted destination item ids, the observed
field values (used only to skip redundant writes), and the writer. The bundled
`GraphQLProjectFieldWriter` only *builds* GitHub Projects V2 GraphQL documents
from a caller-supplied schema snapshot and hands them to an injected
`transport(query, variables)` callable; the transport owns authentication and
the network, and none is provided. Observed Project values are never read to
choose a run state: a manual edit to ``approved`` is overwritten, not honoured.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import re
from typing import Any, Callable, Collection, Mapping, Protocol

from idkmesh.github_run_label_projection import _RUN_LABEL_STATES


PROJECT_RUN_FIELD_KEYS = ("state", "verification", "human_decision")
RUN_PLAN_KIND = "idkmesh-project-run-sync-plan"
ROUTING_PLAN_KIND = "idkmesh-project-routing-sync-plan"

# Plan kind -> key that carries the canonical source digest in that plan.
_PLAN_DIGEST_KEYS = {
    RUN_PLAN_KIND: "canonical_source_digest",
    ROUTING_PLAN_KIND: "routing_digest",
}

_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FIELD_ID_RE = re.compile(r"[A-Za-z0-9_:-]{1,80}\Z")
_ITEM_ID_RE = re.compile(r"[A-Za-z0-9_:=-]{1,128}\Z")
_VALUE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_MAX_ITEMS = 64
_MAX_OBSERVED = 256


class ProjectPermissionError(Exception):
    """Raised by a writer when the token lacks Projects permission."""


class ProjectFieldWriter(Protocol):
    """Caller-supplied transport; must set exactly one field value.

    A writer may additionally define ``preflight(updates)`` (a sequence of
    ``(field_id, value)`` pairs). When present it is called once before any
    canonical read or write and may raise `ProjectSchemaError` to refuse the
    whole plan without a partial write.
    """

    def update_field(self, item_id: str, field_id: str, value: str) -> None: ...


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase sha256:<64 hex> digest")
    return value


def _field_ids(field_ids: object) -> dict[str, str]:
    if not isinstance(field_ids, Mapping) or set(field_ids) != set(PROJECT_RUN_FIELD_KEYS):
        raise ValueError("field_ids must map exactly state/verification/human_decision")
    ids = [field_ids[key] for key in PROJECT_RUN_FIELD_KEYS]
    if any(not isinstance(v, str) or _FIELD_ID_RE.fullmatch(v) is None for v in ids):
        raise ValueError("project field ids must be bounded identifiers")
    if len(set(ids)) != len(ids):
        raise ValueError("project field ids must be distinct")
    return {key: field_ids[key] for key in PROJECT_RUN_FIELD_KEYS}


def plan_github_project_run_fields(
    *,
    run_id: str,
    run_state: str,
    canonical_source_digest: str,
    field_ids: Mapping[str, str],
    observed_fields: Mapping[str, str | None],
    expected_source_digest: str | None = None,
) -> dict[str, Any]:
    """Plan run-state Project field values; never mutate or grant authority.

    `run_state` must come from the trusted canonical store, never from the
    Project item or issue text. `observed_fields` only decides which writes are
    redundant; a differing (possibly manually edited) value is overwritten.
    """
    if not isinstance(run_id, str) or _RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("run_id must be a canonical Product Spine run ID")
    if not isinstance(run_state, str) or run_state not in _RUN_LABEL_STATES:
        raise ValueError("unsupported Product Spine run state")
    _digest(canonical_source_digest, "canonical_source_digest")
    if expected_source_digest is not None:
        _digest(expected_source_digest, "expected_source_digest")
        if expected_source_digest != canonical_source_digest:
            raise ValueError("stale canonical run source digest")
    ids = _field_ids(field_ids)
    if not isinstance(observed_fields, Mapping):
        raise TypeError("observed_fields must be a mapping")
    if len(observed_fields) > _MAX_OBSERVED:
        raise ValueError("observed_fields exceeds the bounded field count")
    if any(
        not isinstance(k, str) or not isinstance(v, (str, type(None)))
        for k, v in observed_fields.items()
    ):
        raise ValueError("observed_fields must contain text or null values")

    phase, verification, human = _RUN_LABEL_STATES[run_state]
    canonical = {"state": phase, "verification": verification, "human_decision": human}
    desired = tuple(
        sorted((ids[key], canonical[key]) for key in PROJECT_RUN_FIELD_KEYS)
    )
    updates = tuple(
        (field_id, value)
        for field_id, value in desired
        if observed_fields.get(field_id) != value
    )
    return {
        "schema_version": "0.1",
        "kind": RUN_PLAN_KIND,
        "run_id": run_id,
        "run_state": run_state,
        "canonical_source_digest": canonical_source_digest,
        "desired_fields": [{"field_id": f, "value": v} for f, v in desired],
        "updates": [{"field_id": f, "value": v} for f, v in updates],
        "noop": len(updates) == 0,
        "project_mutation_performed": False,
        "execution_authority": False,
        "human_decision_authority": False,
        "integration_authority": False,
    }


@dataclass(frozen=True, slots=True)
class ProjectSyncResult:
    """Outcome of one apply attempt. Never raises into WorkUnit execution."""

    status: str  # noop | applied | skipped_unauthorized | aborted_source_changed | failed
    item_id: str
    applied: tuple[str, ...]  # field ids written, in order
    detail: str

    @property
    def ok(self) -> bool:
        return self.status in {"noop", "applied"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "kind": "idkmesh-project-sync-result",
            "status": self.status,
            "item_id": self.item_id,
            "applied_field_ids": list(self.applied),
            "detail": self.detail,
            "execution_authority": False,
            "human_decision_authority": False,
            "integration_authority": False,
        }


def _validated_updates(plan: Mapping[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Strictly re-validate a plan; returns (source_digest, updates)."""
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")
    kind = plan.get("kind")
    digest_key = _PLAN_DIGEST_KEYS.get(kind) if isinstance(kind, str) else None
    if digest_key is None:
        raise ValueError("unsupported Project sync plan kind")
    if plan.get("schema_version") != "0.1":
        raise ValueError("unsupported Project sync plan schema_version")
    for flag in (
        "project_mutation_performed",
        "execution_authority",
        "human_decision_authority",
        "integration_authority",
    ):
        if plan.get(flag) is not False:
            raise ValueError(f"plan flag {flag} must be false")
    source = _digest(plan.get(digest_key), digest_key)

    def pairs(name: str) -> tuple[tuple[str, str], ...]:
        raw = plan.get(name)
        if not isinstance(raw, (list, tuple)) or len(raw) > _MAX_ITEMS:
            raise ValueError(f"plan {name} must be a bounded list")
        out: list[tuple[str, str]] = []
        for entry in raw:
            if not isinstance(entry, Mapping) or set(entry) != {"field_id", "value"}:
                raise ValueError(f"plan {name} entries must hold only field_id/value")
            field_id, value = entry["field_id"], entry["value"]
            if not isinstance(field_id, str) or _FIELD_ID_RE.fullmatch(field_id) is None:
                raise ValueError("plan field_id is not a bounded identifier")
            if not isinstance(value, str) or _VALUE_RE.fullmatch(value) is None:
                raise ValueError("plan value is not a bounded lowercase token")
            out.append((field_id, value))
        if len({f for f, _ in out}) != len(out):
            raise ValueError(f"plan {name} contains duplicate field ids")
        return tuple(out)

    desired = pairs("desired_fields")
    updates = pairs("updates")
    if not set(updates) <= set(desired):
        raise ValueError("plan updates must be a subset of desired_fields")
    if bool(plan.get("noop")) != (len(updates) == 0):
        raise ValueError("plan noop flag disagrees with updates")
    return source, updates


def apply_github_project_plan(
    plan: Mapping[str, Any],
    *,
    item_id: str,
    trusted_item_ids: Collection[str],
    writer: ProjectFieldWriter,
    read_canonical_digest: Callable[[], str],
) -> ProjectSyncResult:
    """Apply a field plan idempotently, aborting if the canonical source moves.

    Malformed arguments raise (programmer error, before any write). Operational
    Projects failures are returned as a `ProjectSyncResult` so a missing
    permission or outage can never block canonical WorkUnit execution.

    `read_canonical_digest` must re-read the trusted canonical source; it is
    called before the first write and again before every subsequent write. Any
    mismatch aborts without further writes (no mixed-revision view). Exception
    messages from the writer are deliberately not copied into the result.
    """
    source, updates = _validated_updates(plan)
    if not isinstance(item_id, str) or _ITEM_ID_RE.fullmatch(item_id) is None:
        raise ValueError("item_id must be a bounded identifier")
    if isinstance(trusted_item_ids, (str, bytes)) or not isinstance(
        trusted_item_ids, Collection
    ):
        raise ValueError("trusted_item_ids must be a collection of ids")
    if item_id not in trusted_item_ids:
        raise ValueError("item_id is not a trusted destination for this repository")
    if not callable(read_canonical_digest) or not hasattr(writer, "update_field"):
        raise TypeError("writer and read_canonical_digest are required")

    if not updates:
        return ProjectSyncResult("noop", item_id, (), "Project already matches canonical state.")

    preflight = getattr(writer, "preflight", None)
    if callable(preflight):
        try:
            preflight(updates)
        except ProjectSchemaError as exc:
            return ProjectSyncResult(
                "failed", item_id, (),
                f"Project schema snapshot rejects the plan ({type(exc).__name__}); no writes",
            )

    applied: list[str] = []
    for field_id, value in updates:
        try:
            current = read_canonical_digest()
        except Exception as exc:  # canonical store outage: do not write blind
            return ProjectSyncResult(
                "failed", item_id, tuple(applied),
                f"canonical source unreadable ({type(exc).__name__}); no further writes",
            )
        if current != source:
            return ProjectSyncResult(
                "aborted_source_changed", item_id, tuple(applied),
                "canonical source changed during sync; replan from the new revision",
            )
        try:
            writer.update_field(item_id, field_id, value)
        except ProjectPermissionError:
            return ProjectSyncResult(
                "skipped_unauthorized", item_id, tuple(applied),
                "Projects permission unavailable; canonical WorkUnit state is unaffected",
            )
        except Exception as exc:
            return ProjectSyncResult(
                "failed", item_id, tuple(applied),
                f"Project write failed ({type(exc).__name__}); retry replans idempotently",
            )
        applied.append(field_id)
    return ProjectSyncResult("applied", item_id, tuple(applied), "Project fields updated.")


# --------------------------------------------------------------------------
# GraphQL document builder (no network, no token): the C13-G live-writer seam.
# --------------------------------------------------------------------------

SCHEMA_SNAPSHOT_KIND = "idkmesh-project-schema-snapshot"

# Fixed document. Every dynamic value travels as a GraphQL *variable*; nothing
# is ever interpolated into this string.
UPDATE_FIELD_VALUE_MUTATION = (
    "mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, "
    "$value: ProjectV2FieldValue!) {\n"
    "  updateProjectV2ItemFieldValue(input: {projectId: $projectId, "
    "itemId: $itemId, fieldId: $fieldId, value: $value}) {\n"
    "    projectV2Item { id }\n"
    "  }\n"
    "}\n"
)

FIELD_DATA_TYPES = ("single_select", "text", "number", "date")
_MAX_SCHEMA_FIELDS = 64
_MAX_FIELD_OPTIONS = 64
_NUMBER_RE = re.compile(r"[0-9]{1,15}\Z")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
# GraphQL `errors[].type` values meaning "this token may not do that".
_PERMISSION_ERROR_TYPES = frozenset({"FORBIDDEN", "INSUFFICIENT_SCOPES", "UNAUTHORIZED"})

ProjectTransport = Callable[[str, dict[str, Any]], Mapping[str, Any]]


class ProjectSchemaError(ValueError):
    """The schema snapshot is malformed, or does not cover a planned write."""


class ProjectGraphQLError(RuntimeError):
    """A GraphQL response reported failure or was not the expected shape.

    The message is a fixed string: no response body, error text or variable
    value is ever copied into it.
    """


@dataclass(frozen=True, slots=True)
class _FieldSchema:
    data_type: str
    options: tuple[tuple[str, str], ...]  # (value token, option id); single_select only


def _bounded_id(value: object, name: str) -> str:
    if not isinstance(value, str) or _FIELD_ID_RE.fullmatch(value) is None:
        raise ProjectSchemaError(f"{name} must be a bounded identifier")
    return value


def _parse_schema_snapshot(snapshot: object) -> tuple[str, dict[str, _FieldSchema]]:
    """Strictly validate a caller-supplied Project schema snapshot."""
    if not isinstance(snapshot, Mapping):
        raise ProjectSchemaError("schema snapshot must be a mapping")
    if set(snapshot) != {"schema_version", "kind", "project_id", "fields"}:
        raise ProjectSchemaError("schema snapshot has unexpected or missing keys")
    if snapshot["schema_version"] != "0.1" or snapshot["kind"] != SCHEMA_SNAPSHOT_KIND:
        raise ProjectSchemaError("unsupported schema snapshot kind or version")
    project_id = _bounded_id(snapshot["project_id"], "project_id")
    raw_fields = snapshot["fields"]
    if (
        not isinstance(raw_fields, (list, tuple))
        or not 0 < len(raw_fields) <= _MAX_SCHEMA_FIELDS
    ):
        raise ProjectSchemaError("schema snapshot fields must be a bounded non-empty list")
    fields: dict[str, _FieldSchema] = {}
    seen_ids: set[str] = {project_id}
    for entry in raw_fields:
        if not isinstance(entry, Mapping) or set(entry) != {"field_id", "data_type", "options"}:
            raise ProjectSchemaError("schema field entries must hold field_id/data_type/options")
        field_id = _bounded_id(entry["field_id"], "field_id")
        data_type = entry["data_type"]
        if data_type not in FIELD_DATA_TYPES:
            raise ProjectSchemaError("unsupported field data_type")
        if field_id in seen_ids:
            raise ProjectSchemaError("schema ids must be unique")
        seen_ids.add(field_id)
        raw_options = entry["options"]
        if not isinstance(raw_options, (list, tuple)) or len(raw_options) > _MAX_FIELD_OPTIONS:
            raise ProjectSchemaError("field options must be a bounded list")
        if (data_type == "single_select") != (len(raw_options) > 0):
            raise ProjectSchemaError("only single_select fields carry (and require) options")
        options: list[tuple[str, str]] = []
        for option in raw_options:
            if not isinstance(option, Mapping) or set(option) != {"value", "option_id"}:
                raise ProjectSchemaError("option entries must hold only value/option_id")
            value, option_id = option["value"], option["option_id"]
            if not isinstance(value, str) or _VALUE_RE.fullmatch(value) is None:
                raise ProjectSchemaError("option value is not a bounded lowercase token")
            _bounded_id(option_id, "option_id")
            if option_id in seen_ids:
                raise ProjectSchemaError("schema ids must be unique")
            seen_ids.add(option_id)
            options.append((value, option_id))
        if len({v for v, _ in options}) != len(options):
            raise ProjectSchemaError("duplicate option value in a field")
        fields[field_id] = _FieldSchema(data_type, tuple(options))
    return project_id, fields


def _typed_value(schema: _FieldSchema, value: str) -> dict[str, Any]:
    """Map a validated plan token to a `ProjectV2FieldValue` input object."""
    if schema.data_type == "single_select":
        for token, option_id in schema.options:
            if token == value:
                return {"singleSelectOptionId": option_id}
        raise ProjectSchemaError("planned value has no option id in the schema snapshot")
    if schema.data_type == "text":
        return {"text": value}
    if schema.data_type == "number":
        if _NUMBER_RE.fullmatch(value) is None:
            raise ProjectSchemaError("planned value is not a non-negative integer")
        return {"number": float(int(value))}
    if _DATE_RE.fullmatch(value) is None:
        raise ProjectSchemaError("planned value is not an ISO calendar date")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise ProjectSchemaError("planned value is not a real calendar date") from None
    return {"date": value}


class GraphQLProjectFieldWriter:
    """`ProjectFieldWriter` that emits GitHub Projects V2 GraphQL documents.

    Offline by construction: requests leave only through the injected
    ``transport(query, variables) -> response`` callable, which owns the HTTP
    client, authentication and any token. This class holds no credential, reads
    no environment variable and performs no retry.

    Ids come exclusively from the validated ``schema_snapshot``
    (``kind == "idkmesh-project-schema-snapshot"``): an unknown field, or a
    value with no option id, fails closed, and a response must confirm the very
    item that was written. GraphQL ``errors`` of type FORBIDDEN /
    INSUFFICIENT_SCOPES / UNAUTHORIZED raise `ProjectPermissionError`; any other
    error or malformed response raises `ProjectGraphQLError`, both with fixed
    messages so no response body or credential can be echoed.
    """

    def __init__(self, transport: ProjectTransport, schema_snapshot: Mapping[str, Any]) -> None:
        if not callable(transport):
            raise TypeError("transport must be a callable(query, variables)")
        self._transport = transport
        self._project_id, self._fields = _parse_schema_snapshot(schema_snapshot)

    def _variables(self, item_id: str, field_id: str, value: str) -> dict[str, Any]:
        if not isinstance(item_id, str) or _ITEM_ID_RE.fullmatch(item_id) is None:
            raise ProjectSchemaError("item_id must be a bounded identifier")
        if not isinstance(value, str) or _VALUE_RE.fullmatch(value) is None:
            raise ProjectSchemaError("value is not a bounded lowercase token")
        schema = self._fields.get(field_id) if isinstance(field_id, str) else None
        if schema is None:
            raise ProjectSchemaError("field id is not in the schema snapshot")
        return {
            "projectId": self._project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "value": _typed_value(schema, value),
        }

    def preflight(self, updates: Collection[tuple[str, str]]) -> None:
        """Refuse a plan the snapshot cannot fully express, before any write."""
        for field_id, value in updates:
            self._variables("PVTI_preflight", field_id, value)

    def update_field(self, item_id: str, field_id: str, value: str) -> None:
        variables = self._variables(item_id, field_id, value)
        response = self._transport(UPDATE_FIELD_VALUE_MUTATION, variables)
        self._check_response(response, item_id)

    @staticmethod
    def _check_response(response: object, item_id: str) -> None:
        if not isinstance(response, Mapping):
            raise ProjectGraphQLError("GraphQL response was not an object")
        errors = response.get("errors")
        if errors:
            kinds = {
                e["type"]
                for e in (errors if isinstance(errors, (list, tuple)) else ())
                if isinstance(e, Mapping) and isinstance(e.get("type"), str)
            }
            if kinds & _PERMISSION_ERROR_TYPES:
                raise ProjectPermissionError("Projects permission unavailable")
            raise ProjectGraphQLError("GraphQL response reported errors")
        data = response.get("data")
        payload = data.get("updateProjectV2ItemFieldValue") if isinstance(data, Mapping) else None
        item = payload.get("projectV2Item") if isinstance(payload, Mapping) else None
        if not isinstance(item, Mapping) or item.get("id") != item_id:
            raise ProjectGraphQLError("GraphQL response did not confirm the written item")
