"""Tenant/project scope primitives for enterprise IDKMesh state.

This module is an E2 foundation for issue #669. It makes scope explicit in
resource references, durable-key construction, and idempotency derivation.

The in-memory store is a conformance/reference fixture only. It demonstrates
scope-safe lookup behavior without claiming production durability.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

SCOPE_VERSION = "0.1"
RESOURCE_REF_KIND = "idkmesh-enterprise-resource-ref"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TYPE_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TenantIsolationError(ValueError):
    """Stable fail-closed tenant-scope contract error."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> TenantIsolationError:
    return TenantIsolationError(code, path, message)


def _scope_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise _fail(
            "invalid_scope_id",
            path,
            "must be 1-128 characters using letters, digits, '.', '_' or '-' "
            "and start with a letter or digit",
        )
    return value


def _resource_type(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _TYPE_RE.fullmatch(value):
        raise _fail(
            "invalid_resource_type",
            path,
            "must be lowercase, start with a letter, and use only "
            "letters, digits, '.', '_' or '-'",
        )
    return value


def _payload_digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise _fail(
            "invalid_digest",
            path,
            "must be sha256:<64 lowercase hex>",
        )
    return value


@dataclass(frozen=True, slots=True)
class TenantScope:
    tenant_id: str
    project_id: str

    def __post_init__(self) -> None:
        _scope_id(self.tenant_id, "tenant_id")
        _scope_id(self.project_id, "project_id")

    @property
    def storage_prefix(self) -> str:
        return (
            f"idkmesh/scope/v1/tenant/{self.tenant_id}/"
            f"project/{self.project_id}"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
        }


@dataclass(frozen=True, slots=True)
class ScopedResourceRef:
    scope: TenantScope
    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        _resource_type(self.resource_type, "resource_type")
        _scope_id(self.resource_id, "resource_id")

    @property
    def storage_key(self) -> str:
        return (
            f"{self.scope.storage_prefix}/resource/"
            f"{self.resource_type}/{self.resource_id}"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": RESOURCE_REF_KIND,
            "schema_version": SCOPE_VERSION,
            "tenant_id": self.scope.tenant_id,
            "project_id": self.scope.project_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
        }


def parse_resource_ref(value: Any) -> ScopedResourceRef:
    if not isinstance(value, Mapping):
        raise _fail("invalid_type", "$", "resource reference must be an object")

    fields = {
        "kind",
        "schema_version",
        "tenant_id",
        "project_id",
        "resource_type",
        "resource_id",
    }
    missing = sorted(fields - set(value))
    if missing:
        raise _fail("missing_field", "$", "missing: " + ", ".join(missing))
    unknown = sorted(set(value) - fields)
    if unknown:
        raise _fail(
            "unknown_field",
            f"$.{unknown[0]}",
            f"unknown field {unknown[0]!r}",
        )

    if value["kind"] != RESOURCE_REF_KIND:
        raise _fail(
            "invalid_kind",
            "$.kind",
            f"must be {RESOURCE_REF_KIND!r}",
        )
    if value["schema_version"] != SCOPE_VERSION:
        raise _fail(
            "unsupported_version",
            "$.schema_version",
            f"must be {SCOPE_VERSION!r}",
        )

    scope = TenantScope(
        tenant_id=_scope_id(value["tenant_id"], "$.tenant_id"),
        project_id=_scope_id(value["project_id"], "$.project_id"),
    )
    return ScopedResourceRef(
        scope=scope,
        resource_type=_resource_type(
            value["resource_type"], "$.resource_type"
        ),
        resource_id=_scope_id(value["resource_id"], "$.resource_id"),
    )


def assert_same_scope(
    expected: TenantScope,
    actual: TenantScope,
    *,
    path: str = "resource",
) -> None:
    if expected != actual:
        raise _fail(
            "scope_mismatch",
            path,
            "tenant/project scope does not match caller scope",
        )


def scoped_idempotency_key(
    scope: TenantScope,
    *,
    operation: str,
    logical_key: str,
    payload_digest: str,
) -> str:
    """Derive one deterministic idempotency key bound to tenant/project scope."""

    operation_value = _resource_type(operation, "operation")
    logical_value = _scope_id(logical_key, "logical_key")
    digest_value = _payload_digest(payload_digest, "payload_digest")
    canonical = json.dumps(
        {
            "version": 1,
            "tenant_id": scope.tenant_id,
            "project_id": scope.project_id,
            "operation": operation_value,
            "logical_key": logical_value,
            "payload_digest": digest_value,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


class ScopedMemoryStore:
    """Reference keyspace for isolation tests; not a durable production store."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def put(
        self,
        scope: TenantScope,
        resource_type: str,
        resource_id: str,
        value: Any,
    ) -> ScopedResourceRef:
        ref = ScopedResourceRef(scope, resource_type, resource_id)
        self._values[ref.storage_key] = value
        return ref

    def put_ref(
        self,
        caller_scope: TenantScope,
        ref: ScopedResourceRef,
        value: Any,
    ) -> None:
        assert_same_scope(caller_scope, ref.scope, path="resource.scope")
        self._values[ref.storage_key] = value

    def get(
        self,
        scope: TenantScope,
        resource_type: str,
        resource_id: str,
    ) -> Any | None:
        ref = ScopedResourceRef(scope, resource_type, resource_id)
        return self._values.get(ref.storage_key)

    def get_ref(
        self,
        caller_scope: TenantScope,
        ref: ScopedResourceRef,
    ) -> Any | None:
        assert_same_scope(caller_scope, ref.scope, path="resource.scope")
        return self._values.get(ref.storage_key)

    def delete_ref(
        self,
        caller_scope: TenantScope,
        ref: ScopedResourceRef,
    ) -> bool:
        assert_same_scope(caller_scope, ref.scope, path="resource.scope")
        return self._values.pop(ref.storage_key, None) is not None

    def keys_for_scope(self, scope: TenantScope) -> tuple[str, ...]:
        prefix = scope.storage_prefix + "/"
        return tuple(
            sorted(key for key in self._values if key.startswith(prefix))
        )
