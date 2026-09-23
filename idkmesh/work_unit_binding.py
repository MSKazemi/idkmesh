"""Bind one canonical WorkUnit to the exact Git source revision used for a run.

This product-layer binding reuses the canonical JSON digest convention already
used by the Phase 0 provenance-integrity checks. It does not execute work,
verify a candidate, or grant integration authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


_GIT_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class WorkUnitBindingError(RuntimeError):
    """Raised when task identity or trusted source provenance does not match."""


def canonical_digest(value: Any) -> str:
    """Return the repository's frozen canonical JSON SHA-256 digest."""

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkUnitBindingError(f"{field} must be a non-empty string")
    return value


def _git_revision(value: Any, field: str) -> str:
    revision = _nonempty(value, field)
    if _GIT_REVISION_RE.fullmatch(revision) is None:
        raise WorkUnitBindingError(
            f"{field} must be a 40- or 64-character hexadecimal Git object id"
        )
    return revision.lower()


def _work_unit_identity(work_unit: Any) -> tuple[str, int]:
    if not isinstance(work_unit, dict):
        raise WorkUnitBindingError("work_unit must be a JSON object")

    work_unit_id = _nonempty(work_unit.get("id"), "work_unit.id")
    version = work_unit.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise WorkUnitBindingError("work_unit.version must be an integer >= 1")
    return work_unit_id, version


@dataclass(frozen=True)
class WorkUnitSourceBinding:
    """Immutable binding between task content and its trusted starting revision."""

    work_unit_id: str
    work_unit_version: int
    work_unit_digest: str
    source_revision: str

    def __post_init__(self) -> None:
        _nonempty(self.work_unit_id, "work_unit_id")
        if (
            isinstance(self.work_unit_version, bool)
            or not isinstance(self.work_unit_version, int)
            or self.work_unit_version < 1
        ):
            raise WorkUnitBindingError("work_unit_version must be an integer >= 1")
        if (
            not isinstance(self.work_unit_digest, str)
            or _SHA256_RE.fullmatch(self.work_unit_digest) is None
        ):
            raise WorkUnitBindingError(
                "work_unit_digest must be a lowercase sha256 content digest"
            )
        normalized_revision = _git_revision(
            self.source_revision,
            "source_revision",
        )
        object.__setattr__(self, "source_revision", normalized_revision)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_unit_id": self.work_unit_id,
            "work_unit_version": self.work_unit_version,
            "work_unit_digest": self.work_unit_digest,
            "source_revision": self.source_revision,
        }


def bind_work_unit_source(
    work_unit: dict[str, Any],
    *,
    source_revision: str,
) -> WorkUnitSourceBinding:
    """Bind a schema-valid WorkUnit to one trusted exact Git revision.

    If the WorkUnit already declares provenance.source_revision, the trusted
    revision must match it. An omitted declaration is allowed because the
    admission/execution layer may bind the exact revision later.
    """

    work_unit_id, version = _work_unit_identity(work_unit)
    trusted_revision = _git_revision(source_revision, "source_revision")

    provenance = work_unit.get("provenance")
    if not isinstance(provenance, dict):
        raise WorkUnitBindingError("work_unit.provenance must be a JSON object")

    declared_revision = provenance.get("source_revision")
    if declared_revision is not None:
        normalized_declared = _git_revision(
            declared_revision,
            "work_unit.provenance.source_revision",
        )
        if normalized_declared != trusted_revision:
            raise WorkUnitBindingError(
                "trusted source revision does not match WorkUnit provenance"
            )

    return WorkUnitSourceBinding(
        work_unit_id=work_unit_id,
        work_unit_version=version,
        work_unit_digest=canonical_digest(work_unit),
        source_revision=trusted_revision,
    )


def validate_work_unit_source_binding(
    work_unit: dict[str, Any],
    binding: WorkUnitSourceBinding,
    *,
    source_revision: str | None = None,
) -> None:
    """Fail closed if a retained binding no longer matches task/source identity."""

    if not isinstance(binding, WorkUnitSourceBinding):
        raise WorkUnitBindingError("binding must be a WorkUnitSourceBinding")

    work_unit_id, version = _work_unit_identity(work_unit)
    if work_unit_id != binding.work_unit_id:
        raise WorkUnitBindingError("binding references a different WorkUnit id")
    if version != binding.work_unit_version:
        raise WorkUnitBindingError("binding references a different WorkUnit version")

    digest = canonical_digest(work_unit)
    if digest != binding.work_unit_digest:
        raise WorkUnitBindingError(
            "WorkUnit content changed after source binding"
        )

    if source_revision is not None:
        observed_revision = _git_revision(source_revision, "source_revision")
        if observed_revision != binding.source_revision:
            raise WorkUnitBindingError(
                "observed source revision does not match retained binding"
            )
