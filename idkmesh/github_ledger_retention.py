"""Retention and reference policy for the C9 GitHub-native ledger (slice C9-H).

GitHub Actions artifacts, logs and caches have finite retention; the ledger
branch does not expire. C9-A..G therefore store only compact, digest-bound
evidence references on the ledger. This module states, and checks, the policy that
keeps the two honest:

* **Durable and mandatory.** Ledger records, admission records and the compact
  candidate / ResultManifest / VerificationResult / Human Decision references
  are never expired, compacted or rewritten. :func:`check_run_retention` reports
  which of them a run in its recovered state must already carry, and which
  carried references cannot be interpreted after the raw copy is gone (no
  repository-relative path, a malformed digest, or a path that points into a
  transient runner location).
* **Transient and expirable.** Raw Actions artifacts, logs, caches, provider
  transcripts and raw candidate bundles may expire, but only when
  :func:`plan_artifact_expiry` finds that (a) the kind is classified, (b) the
  artifact is older than the policy minimum, (c) its run is not still being
  observed, and (d) it is not the **sole copy** of evidence the ledger
  references: a raw artifact whose digest is referenced by the ledger but is not
  known to be present in the durable store is retained.
* **Bounded growth without rewriting.** :func:`assess_ledger_size` reports ledger
  size against warn/limit thresholds. The only remedy it ever names is an
  operator decision to start a new shard; deleting, compacting or rewriting
  ledger history is not a remedy this policy offers.

Everything here is a pure, advisory function. It deletes nothing, calls no
GitHub API, reads no clock (the caller passes ``now``), and grants no dispatch,
verification, acceptance, integration or merge authority.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Any

from idkmesh.github_evidence_link import DurableGitHubEvidenceLinkError, _path as _safe_path
from idkmesh.github_ledger_recovery import RecoveredRunState

SCHEMA_VERSION = "github-ledger-retention-policy-v0.1"

#: Evidence that is retained for the life of the ledger and never expired.
DURABLE_KINDS = frozenset(
    {
        "ledger_record",
        "admission_record",
        "candidate_reference",
        "result_manifest",
        "verification_result",
        "human_decision_record",
    }
)
#: Raw material that may expire once the compact reference is durable.
TRANSIENT_KINDS = frozenset(
    {
        "actions_artifact",
        "actions_log",
        "actions_cache",
        "provider_transcript",
        "raw_candidate_bundle",
    }
)

# Run states in which a compact reference must already be recorded. Derived from
# the Product Spine invariants: ``evidence_ready`` onward requires an evidence
# report and ``decided`` requires a Human Decision Record.
_CANDIDATE_STATES = frozenset(
    {
        "candidate_observed", "normalized", "verification_requested", "verification_error",
        "evidence_ready", "awaiting_human_decision", "decided",
    }
)
_MANIFEST_STATES = _CANDIDATE_STATES - {"candidate_observed"}
_VERIFIED_STATES = frozenset({"evidence_ready", "awaiting_human_decision", "decided"})

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_ARTIFACT_ID = 256
_MAX_DAYS = 3650
_MAX_BYTES = 1 << 50

_DEFAULT_TRANSIENT_SEGMENTS = frozenset(
    {"_temp", "_work", "_actions", "actions-artifacts", "artifacts", "runner", "tmp", "cache"}
)
_DEFAULT_REQUIRE_PATH = frozenset({"result_manifest", "verification_result", "human_decision_record"})


class LedgerRetentionError(ValueError):
    """The policy, an inventory entry or a clock value is malformed."""

    code = "retention_invalid"

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {message}")


def _bounded_int(value: Any, field_name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise LedgerRetentionError(
            "invalid_policy", f"{field_name} must be an integer in [{low}, {high}]"
        )
    return value


def _name_set(value: Any, field_name: str, allowed: frozenset[str] | None) -> frozenset[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        raise LedgerRetentionError("invalid_policy", f"{field_name} must be a list of strings")
    items = list(value)
    for item in items:
        if not isinstance(item, str) or not item or "/" in item or len(item) > 64:
            raise LedgerRetentionError("invalid_policy", f"{field_name} holds an invalid entry")
        if allowed is not None and item not in allowed:
            raise LedgerRetentionError("invalid_policy", f"{field_name}: unknown kind {item!r}")
    return frozenset(items)


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Declared retention limits. These are IDKMesh policy values, not claims
    about what GitHub itself retains."""

    #: Raw artifacts are never expired before this age.
    transient_min_age_days: int = 30
    #: Durable kinds whose reference must carry a repository-relative path.
    require_storage_path: frozenset[str] = _DEFAULT_REQUIRE_PATH
    #: Path segments that mark a transient runner location, never a durable one.
    transient_path_segments: frozenset[str] = _DEFAULT_TRANSIENT_SEGMENTS
    ledger_warn_bytes: int = 100 * 1024 * 1024
    ledger_limit_bytes: int = 500 * 1024 * 1024

    def __post_init__(self) -> None:
        _bounded_int(self.transient_min_age_days, "transient_min_age_days", 1, _MAX_DAYS)
        _bounded_int(self.ledger_warn_bytes, "ledger_warn_bytes", 1, _MAX_BYTES)
        _bounded_int(self.ledger_limit_bytes, "ledger_limit_bytes", 1, _MAX_BYTES)
        if self.ledger_warn_bytes >= self.ledger_limit_bytes:
            raise LedgerRetentionError(
                "invalid_policy", "ledger_warn_bytes must be below ledger_limit_bytes"
            )
        _name_set(self.require_storage_path, "require_storage_path", DURABLE_KINDS)
        _name_set(self.transient_path_segments, "transient_path_segments", None)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> RetentionPolicy:
        """Strict parse: unknown keys and a wrong ``schema_version`` are refused."""

        if not isinstance(data, Mapping):
            raise LedgerRetentionError("invalid_policy", "policy must be an object")
        known = {
            "schema_version", "transient_min_age_days", "require_storage_path",
            "transient_path_segments", "ledger_warn_bytes", "ledger_limit_bytes",
        }
        unknown = sorted(set(data) - known)
        if unknown:
            raise LedgerRetentionError("invalid_policy", f"unknown fields: {unknown}")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise LedgerRetentionError("invalid_policy", f"schema_version must be {SCHEMA_VERSION}")
        kwargs: dict[str, Any] = {}
        for name in ("transient_min_age_days", "ledger_warn_bytes", "ledger_limit_bytes"):
            if name in data:
                kwargs[name] = data[name]
        if "require_storage_path" in data:
            kwargs["require_storage_path"] = _name_set(
                data["require_storage_path"], "require_storage_path", DURABLE_KINDS
            )
        if "transient_path_segments" in data:
            kwargs["transient_path_segments"] = _name_set(
                data["transient_path_segments"], "transient_path_segments", None
            )
        return cls(**kwargs)


DEFAULT_RETENTION_POLICY = RetentionPolicy()


@dataclass(frozen=True, slots=True)
class RetentionFinding:
    code: str
    #: The evidence slot concerned, e.g. ``result_manifest`` or ``verification_result[1]``.
    slot: str
    message: str


@dataclass(frozen=True, slots=True)
class RetentionReport:
    run_id: str
    state: str
    findings: tuple[RetentionFinding, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.findings


def _check_reference(
    kind: str,
    slot: str,
    ref: tuple[str, str | None],
    policy: RetentionPolicy,
    out: list[RetentionFinding],
) -> None:
    digest, path = ref
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        out.append(RetentionFinding("malformed_digest", slot, "digest is not sha256:<64 hex>"))
    if path is None:
        if kind in policy.require_storage_path:
            out.append(
                RetentionFinding(
                    "unlocatable_reference", slot,
                    f"a {kind} reference needs a repository-relative path to stay interpretable "
                    "after raw artifacts expire",
                )
            )
        return
    try:
        _safe_path(path)
    except DurableGitHubEvidenceLinkError as exc:
        out.append(RetentionFinding("unsafe_path", slot, str(exc)))
        return
    if any(part in policy.transient_path_segments for part in path.split("/")):
        out.append(
            RetentionFinding(
                "transient_locator", slot,
                "path points into a transient runner location, which is not durable evidence",
            )
        )


def check_run_retention(
    state: RecoveredRunState, policy: RetentionPolicy = DEFAULT_RETENTION_POLICY
) -> RetentionReport:
    """Check that a recovered run carries the compact evidence its state requires.

    A ``cancelled`` run is not required to have progressed, but any reference it
    does carry is still checked, and negative evidence is never required to be
    absent.
    """

    out: list[RetentionFinding] = []
    slots: list[tuple[str, str, tuple[str, str | None] | None, bool]] = [
        (
            "candidate_reference", "candidate_reference", state.candidate_reference,
            state.state in _CANDIDATE_STATES,
        ),
        (
            "result_manifest", "result_manifest", state.result_manifest,
            state.state in _MANIFEST_STATES,
        ),
        (
            "human_decision_record", "human_decision_record", state.human_decision_record,
            state.state == "decided",
        ),
    ]
    for kind, slot, ref, required in slots:
        if ref is None:
            if required:
                out.append(
                    RetentionFinding(
                        f"missing_{kind}", slot, f"state {state.state} requires a {kind} reference"
                    )
                )
        else:
            _check_reference(kind, slot, ref, policy, out)

    if state.state in _VERIFIED_STATES and not state.verification_results:
        out.append(
            RetentionFinding(
                "missing_verification_result", "verification_result",
                f"state {state.state} requires at least one verification_result reference",
            )
        )
    for index, ref in enumerate(state.verification_results, start=1):
        _check_reference("verification_result", f"verification_result[{index}]", ref, policy, out)
    return RetentionReport(state.run_id, state.state, tuple(out))


# ---------------------------------------------------------------------------
# Raw-artifact expiry planning
# ---------------------------------------------------------------------------

DECISIONS = frozenset(
    {
        "may_expire",
        "retain_young",
        "retain_active_run",
        "retain_sole_copy",
        "retain_durable_kind",
        "retain_unclassified",
    }
)


@dataclass(frozen=True, slots=True)
class RawArtifact:
    artifact_id: str
    kind: str
    created_at: datetime
    #: Content digest, when known. An artifact without one cannot be referenced
    #: by the ledger and so cannot be a sole copy.
    digest: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.artifact_id, str)
            or not self.artifact_id
            or len(self.artifact_id) > _MAX_ARTIFACT_ID
        ):
            raise LedgerRetentionError("invalid_artifact", "artifact_id must be a bounded string")
        if not isinstance(self.kind, str):
            raise LedgerRetentionError("invalid_artifact", "kind must be a string")
        _aware(self.created_at, "created_at")
        if self.digest is not None and (
            not isinstance(self.digest, str) or not _DIGEST_RE.fullmatch(self.digest)
        ):
            raise LedgerRetentionError("invalid_artifact", "digest must be sha256:<64 hex>")


@dataclass(frozen=True, slots=True)
class ExpiryDecision:
    artifact_id: str
    decision: str
    reason: str

    @property
    def may_expire(self) -> bool:
        return self.decision == "may_expire"


def _aware(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LedgerRetentionError("invalid_time", f"{field_name} must be a timezone-aware datetime")
    return value


def plan_artifact_expiry(
    artifacts: Iterable[RawArtifact],
    *,
    referenced_digests: Collection[str],
    durable_digests: Collection[str],
    now: datetime,
    policy: RetentionPolicy = DEFAULT_RETENTION_POLICY,
    active_run_ids: Collection[str] = (),
) -> tuple[ExpiryDecision, ...]:
    """Decide, per raw artifact, whether it *may* expire. Never expires anything.

    ``referenced_digests`` are digests the ledger points at; ``durable_digests``
    are the subset the caller has confirmed are present in the durable store. A
    referenced digest that is not durable makes the raw artifact the only copy,
    so it is retained. Fail-closed: an unclassified kind, a future ``created_at``
    or an artifact of an active run is retained.
    """

    current = _aware(now, "now")
    min_age = timedelta(days=policy.transient_min_age_days)
    referenced = frozenset(referenced_digests)
    durable = frozenset(durable_digests)
    active = frozenset(active_run_ids)

    decisions: list[ExpiryDecision] = []
    for artifact in artifacts:
        if artifact.kind in DURABLE_KINDS:
            result = ("retain_durable_kind", f"{artifact.kind} is durable evidence and never expires")
        elif artifact.kind not in TRANSIENT_KINDS:
            result = ("retain_unclassified", f"kind {artifact.kind!r} is not classified as transient")
        elif artifact.run_id is not None and artifact.run_id in active:
            result = ("retain_active_run", "its run is still being observed")
        elif artifact.digest is not None and artifact.digest in referenced and artifact.digest not in durable:
            result = (
                "retain_sole_copy",
                "the ledger references this digest and no durable copy is confirmed",
            )
        elif current - artifact.created_at < min_age:
            result = (
                "retain_young",
                f"younger than the {policy.transient_min_age_days}-day minimum "
                "(or created in the future)",
            )
        else:
            result = ("may_expire", "transient, old enough, and not the sole copy of referenced evidence")
        decisions.append(ExpiryDecision(artifact.artifact_id, *result))
    return tuple(decisions)


# ---------------------------------------------------------------------------
# Ledger growth
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LedgerSizeAssessment:
    status: str  # ok | warn | exceeded
    total_bytes: int
    record_count: int
    #: ``none``, ``plan_new_shard`` (warn) or ``operator_decision_new_shard``
    #: (exceeded). Deleting, compacting or rewriting ledger history is never offered.
    action: str


def assess_ledger_size(
    total_bytes: int, record_count: int, policy: RetentionPolicy = DEFAULT_RETENTION_POLICY
) -> LedgerSizeAssessment:
    """Compare ledger size with the policy thresholds. Advisory only."""

    _bounded_int(total_bytes, "total_bytes", 0, _MAX_BYTES)
    _bounded_int(record_count, "record_count", 0, _MAX_BYTES)
    if total_bytes >= policy.ledger_limit_bytes:
        return LedgerSizeAssessment("exceeded", total_bytes, record_count, "operator_decision_new_shard")
    if total_bytes >= policy.ledger_warn_bytes:
        return LedgerSizeAssessment("warn", total_bytes, record_count, "plan_new_shard")
    return LedgerSizeAssessment("ok", total_bytes, record_count, "none")
