"""Read-only GitHub lifecycle-label projection for C13-E (issue #608).

Only canonical Product Spine run state is projected. Issue text, GitHub
labels, and Projects fields must never be used to authorize dispatch, review,
acceptance, integration, or merge. This module performs no network or writes.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


# Only these three families are owned by this projection. Connector-routing
# labels (e.g. idkmesh:route:) belong to a different projection.
MANAGED_RUN_LABEL_PREFIXES = (
    "idkmesh:work:",
    "idkmesh:verify:",
    "idkmesh:human:",
)

# Explicitly enumerated so a new Product Spine state cannot silently acquire
# optimistic display semantics. A regression test checks this against RUN_STATES.
# Values are display milestones, NOT trust or permission grants.
_RUN_LABEL_STATES: dict[str, tuple[str, str, str]] = {
    "proposed": ("proposal", "not-started", "unrecorded"),
    "previewed": ("proposal", "not-started", "unrecorded"),
    "admission_blocked": ("admission-blocked", "not-started", "unrecorded"),
    "admitted": ("dispatch-admitted", "not-started", "unrecorded"),
    "dispatched": ("dispatched", "not-started", "unrecorded"),
    "attempt_failed": ("attempt-failed", "not-started", "unrecorded"),
    "candidate_observed": ("candidate-observed", "not-started", "unrecorded"),
    "normalized": ("candidate-normalized", "not-started", "unrecorded"),
    "verification_requested": ("verification-pending", "pending", "unrecorded"),
    "verification_error": ("verification-error", "error", "unrecorded"),
    "evidence_ready": ("evidence-ready", "evidence-ready", "unrecorded"),
    "awaiting_human_decision": ("human-decision-pending", "evidence-ready", "pending"),
    "decided": ("human-decision-recorded", "evidence-ready", "recorded"),
    "cancelled": ("cancelled", "unknown", "unknown"),
}
_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_OBSERVED_LABELS = 1000
_MAX_LABEL_LENGTH = 50


def _validate_digest(value: str, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase sha256:<64 hex> digest")
    return value


def _label(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > _MAX_LABEL_LENGTH
        or not value.isprintable()
    ):
        raise ValueError("GitHub labels must be non-empty, printable, <=50 characters")
    return value


def _is_run_managed(label: str) -> bool:
    folded = label.casefold()
    return any(folded.startswith(prefix) for prefix in MANAGED_RUN_LABEL_PREFIXES)


@dataclass(frozen=True, slots=True)
class GitHubRunLabelPlan:
    """Deterministic plan for *display-only* issue labels; no API mutation."""

    run_id: str
    run_state: str
    canonical_source_digest: str
    managed_labels: tuple[str, str, str]
    target_labels: tuple[str, ...]
    add_labels: tuple[str, ...]
    remove_labels: tuple[str, ...]

    @property
    def noop(self) -> bool:
        return not self.add_labels and not self.remove_labels

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "kind": "idkmesh-github-run-label-plan",
            "run_id": self.run_id,
            "run_state": self.run_state,
            "canonical_source_digest": self.canonical_source_digest,
            "managed_labels": list(self.managed_labels),
            "target_labels": list(self.target_labels),
            "add_labels": list(self.add_labels),
            "remove_labels": list(self.remove_labels),
            "noop": self.noop,
            "github_mutation_performed": False,
            "dispatch_authority": False,
            "verification_authority": False,
            "human_decision_authority": False,
            "integration_authority": False,
            "merge_authority": False,
        }


def plan_github_run_labels(
    *,
    run_id: str,
    run_state: str,
    canonical_source_digest: str,
    existing_labels: Iterable[str],
    expected_source_digest: str | None = None,
) -> GitHubRunLabelPlan:
    """Derive C13-E labels from a *trusted canonical run snapshot*.

    A caller must verify the canonical run identity/state/digest, and must
    re-check the digest before making any later GitHub API update. Issue/Project
    content is not a valid source for run_state. This pure function cannot
    establish the provenance or freshness of its caller-supplied snapshot.

    `expected_source_digest` rejects a known stale snapshot. Managed labels
    belong exclusively to this projector; all other namespaces are preserved.
    Existing labels are used only to compute a minimal, idempotent diff.
    """
    if not isinstance(run_id, str) or _RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("run_id must be a canonical Product Spine run ID")
    if not isinstance(run_state, str) or run_state not in _RUN_LABEL_STATES:
        raise ValueError("unsupported Product Spine run state")
    _validate_digest(canonical_source_digest, "canonical_source_digest")
    if expected_source_digest is not None:
        _validate_digest(expected_source_digest, "expected_source_digest")
        if expected_source_digest != canonical_source_digest:
            raise ValueError("stale canonical run source digest")

    phase, verification, human = _RUN_LABEL_STATES[run_state]
    managed = (
        f"idkmesh:work:{phase}",
        f"idkmesh:verify:{verification}",
        f"idkmesh:human:{human}",
    )
    desired = {name.casefold(): name for name in managed}
    if isinstance(existing_labels, (str, bytes)):
        raise ValueError("existing_labels must be an iterable of label strings")
    try:
        iterator = iter(existing_labels)
    except TypeError as exc:
        raise ValueError("existing_labels must be iterable") from exc

    retained: list[str] = []
    removed: list[str] = []
    observed: set[str] = set()
    for index, raw in enumerate(iterator):
        if index >= _MAX_OBSERVED_LABELS:
            raise ValueError("existing_labels exceeds the bounded label count")
        label = _label(raw)
        folded = label.casefold()
        if folded in observed:
            raise ValueError("existing_labels contains case-insensitive duplicates")
        observed.add(folded)
        if _is_run_managed(label) and folded not in desired:
            removed.append(label)
        else:
            retained.append(label)

    added = [name for key, name in desired.items() if key not in observed]
    target = tuple(sorted((*retained, *added), key=str.casefold))
    return GitHubRunLabelPlan(
        run_id=run_id,
        run_state=run_state,
        canonical_source_digest=canonical_source_digest,
        managed_labels=managed,
        target_labels=target,
        add_labels=tuple(sorted(added, key=str.casefold)),
        remove_labels=tuple(sorted(removed, key=str.casefold)),
    )
