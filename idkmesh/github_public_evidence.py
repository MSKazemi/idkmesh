"""Public-safe GitHub evidence projection for C14-D (#609).

This module is a publication filter, not an evidence store. It accepts canonical
Product Spine state plus optional digest-bound candidate/evidence details and
returns a strict whitelist suitable for later read-only GitHub publication.

Raw prompts, logs, provider payloads, error strings, warnings, worker/verifier
identities, artifact locators, secrets, and credentials are never copied into
this projection. The projection grants no dispatch, verification, human
decision, canonical-state-write, Git push, integration, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    CandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.product_spine import ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest


_SCHEMA_VERSION = "0.1"
_KIND = "idkmesh-github-public-evidence"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_RECOMMENDATIONS = frozenset(
    {
        "accept_candidate",
        "reject_candidate",
        "escalate",
        "insufficient_evidence",
    }
)
_EVIDENCE_STATES = frozenset(
    {
        "supported",
        "rejected",
        "inconclusive",
        "worker_error",
        "result_manifest_error",
        "verification_error",
    }
)
_MAX_JSON_BYTES = 128 * 1024
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "repository",
        "run",
        "attempts",
        "evidence_summary",
        "human_decision_status",
        "authority",
        "privacy",
    }
)
_RUN_KEYS = frozenset(
    {
        "run_id",
        "state",
        "work_unit_id",
        "work_unit_version",
        "work_unit_digest",
        "source_revision",
        "evidence_report_digest",
        "human_decision_record_digest",
    }
)
_ATTEMPT_KEYS = frozenset(
    {
        "attempt_id",
        "order",
        "connector_id",
        "state",
        "candidate_reference_digest",
        "candidate",
        "result_manifest_digest",
        "verification_semantic_digest",
        "evidence_state",
        "verifier_recommendation",
    }
)
_PR_CANDIDATE_KEYS = frozenset({"type", "repository", "number", "head_sha", "url"})
_BUNDLE_CANDIDATE_KEYS = frozenset({"type", "digest"})
_SUMMARY_KEYS = frozenset(
    {
        "attempt_count",
        "supported",
        "rejected",
        "inconclusive",
        "control_errors",
        "verification_disagreement",
        "control_failure_present",
    }
)
_AUTHORITY = {
    "dispatch": False,
    "verification": False,
    "human_decision": False,
    "canonical_state_write": False,
    "git_push": False,
    "integration": False,
    "merge": False,
}
_PRIVACY = {
    "data_classification": "public",
    "projection_only": True,
    "raw_evidence_included": False,
    "raw_logs_included": False,
    "raw_prompts_included": False,
    "provider_payloads_included": False,
    "secret_material_included": False,
    "artifact_locator_included": False,
    "worker_or_verifier_identity_included": False,
}


class GitHubPublicEvidenceError(ValueError):
    """Fail-closed publication-filter error."""


@dataclass(frozen=True, slots=True)
class GitHubPublicEvidencePolicy:
    """Trusted publication policy supplied outside issue/worker content."""

    repository: str
    data_classification: str
    public_projection_enabled: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.repository, str)
            or _REPOSITORY_RE.fullmatch(self.repository) is None
        ):
            raise ValueError("repository must be in owner/name form")
        if self.data_classification not in {
            "public",
            "internal",
            "confidential",
            "restricted",
        }:
            raise ValueError("unsupported data_classification")
        if type(self.public_projection_enabled) is not bool:
            raise ValueError("public_projection_enabled must be a boolean")

    def require_publication(self) -> None:
        if self.data_classification != "public":
            raise GitHubPublicEvidenceError(
                "public GitHub evidence projection requires public data classification"
            )
        if not self.public_projection_enabled:
            raise GitHubPublicEvidenceError(
                "public GitHub evidence projection is disabled by trusted policy"
            )


def _candidate_digest(reference: CandidateReference) -> str:
    return canonical_digest(reference.to_dict())


def _normalize_candidates(
    run: ProductSpineRun,
    candidates: Mapping[str, CandidateReference] | None,
    *,
    repository: str,
) -> dict[str, CandidateReference]:
    if candidates is None:
        return {}
    attempts = {attempt.attempt_id: attempt for attempt in run.attempts}
    normalized: dict[str, CandidateReference] = {}
    for attempt_id, reference in candidates.items():
        if attempt_id not in attempts:
            raise GitHubPublicEvidenceError(
                f"candidate targets unknown attempt {attempt_id!r}"
            )
        if not isinstance(
            reference,
            (
                GitHubPullRequestCandidateReference,
                ArtifactBundleCandidateReference,
            ),
        ):
            raise GitHubPublicEvidenceError(
                f"candidate for {attempt_id!r} has unsupported type"
            )
        retained = attempts[attempt_id].candidate_reference_digest
        if retained is None or _candidate_digest(reference) != retained:
            raise GitHubPublicEvidenceError(
                f"candidate for {attempt_id!r} does not match retained digest"
            )
        if (
            isinstance(reference, GitHubPullRequestCandidateReference)
            and reference.repository.casefold() != repository.casefold()
        ):
            raise GitHubPublicEvidenceError(
                "public PR candidate must belong to the publication repository"
            )
        normalized[attempt_id] = reference
    return normalized


def _normalize_evidence(
    run: ProductSpineRun,
    report: Mapping[str, Any] | None,
) -> tuple[dict[str, Mapping[str, Any]], Mapping[str, Any] | None]:
    if report is None:
        return {}, None
    if run.evidence_report_digest is None:
        raise GitHubPublicEvidenceError(
            "evidence report supplied for run without retained evidence digest"
        )
    if (
        report.get("schema_version") != "0.1"
        or report.get("kind") != "idkmesh-run-evidence-report"
    ):
        raise GitHubPublicEvidenceError("unsupported Run Evidence Report")
    if report.get("run_id") != run.run_id:
        raise GitHubPublicEvidenceError(
            "Run Evidence Report run_id does not match retained run"
        )
    work_unit = report.get("work_unit")
    if not isinstance(work_unit, Mapping):
        raise GitHubPublicEvidenceError("Run Evidence Report lacks work_unit")
    if (
        work_unit.get("id") != run.work_unit_id
        or work_unit.get("version") != run.work_unit_version
        or work_unit.get("digest") != run.work_unit_digest
    ):
        raise GitHubPublicEvidenceError(
            "Run Evidence Report WorkUnit binding does not match retained run"
        )
    if canonical_digest(report) != run.evidence_report_digest:
        raise GitHubPublicEvidenceError(
            "Run Evidence Report does not match retained digest"
        )

    report_attempts = report.get("attempts")
    if not isinstance(report_attempts, list):
        raise GitHubPublicEvidenceError(
            "Run Evidence Report attempts must be an array"
        )
    retained = {attempt.attempt_id: attempt for attempt in run.attempts}
    normalized: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(report_attempts):
        if not isinstance(item, Mapping):
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report attempt {index} must be an object"
            )
        attempt_id = item.get("attempt_id")
        if not isinstance(attempt_id, str) or attempt_id not in retained:
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report attempt {index} is not retained"
            )
        if attempt_id in normalized:
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report repeats attempt {attempt_id!r}"
            )
        retained_attempt = retained[attempt_id]
        if item.get("order") != retained_attempt.order:
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report order for {attempt_id!r} does not match"
            )
        if item.get("worker_adapter") != retained_attempt.connector_id:
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report connector for {attempt_id!r} does not match"
            )
        evidence_state = item.get("evidence_state")
        if evidence_state not in _EVIDENCE_STATES:
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report evidence_state for {attempt_id!r} is unsupported"
            )

        worker = item.get("worker")
        if worker is None:
            if retained_attempt.result_manifest_digest is not None:
                raise GitHubPublicEvidenceError(
                    f"Run Evidence Report omits retained ResultManifest for {attempt_id!r}"
                )
        elif not isinstance(worker, Mapping):
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report worker for {attempt_id!r} must be an object or null"
            )
        elif (
            worker.get("result_manifest_digest")
            != retained_attempt.result_manifest_digest
        ):
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report ResultManifest for {attempt_id!r} does not match"
            )

        verifier = item.get("verifier")
        if verifier is None:
            if retained_attempt.verification_semantic_digest is not None:
                raise GitHubPublicEvidenceError(
                    f"Run Evidence Report omits retained verification for {attempt_id!r}"
                )
        elif not isinstance(verifier, Mapping):
            raise GitHubPublicEvidenceError(
                f"Run Evidence Report verifier for {attempt_id!r} must be an object or null"
            )
        else:
            if (
                verifier.get("verification_semantic_digest")
                != retained_attempt.verification_semantic_digest
            ):
                raise GitHubPublicEvidenceError(
                    f"Run Evidence Report verification for {attempt_id!r} does not match"
                )
            if verifier.get("recommendation") not in _RECOMMENDATIONS:
                raise GitHubPublicEvidenceError(
                    f"Run Evidence Report recommendation for {attempt_id!r} is unsupported"
                )
        normalized[attempt_id] = item

    if set(normalized) != set(retained):
        raise GitHubPublicEvidenceError(
            "Run Evidence Report attempt set does not match retained run"
        )

    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        raise GitHubPublicEvidenceError(
            "Run Evidence Report summary must be an object"
        )
    required_summary = {
        "attempt_count",
        "supported",
        "rejected",
        "inconclusive",
        "control_errors",
        "verification_disagreement",
        "control_failure_present",
    }
    if set(summary) != required_summary:
        raise GitHubPublicEvidenceError(
            "Run Evidence Report summary fields do not match v0.1 contract"
        )
    return normalized, summary


def _safe_candidate(
    reference: CandidateReference | None,
) -> dict[str, Any] | None:
    if reference is None:
        return None
    if isinstance(reference, GitHubPullRequestCandidateReference):
        return {
            "type": "github_pull_request",
            "repository": reference.repository,
            "number": reference.number,
            "head_sha": reference.head_sha,
            "url": reference.canonical_url,
        }
    return {
        "type": "artifact_bundle",
        "digest": reference.digest,
    }


def _safe_summary(
    summary: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if summary is None:
        return None
    result = {
        "attempt_count": summary["attempt_count"],
        "supported": summary["supported"],
        "rejected": summary["rejected"],
        "inconclusive": summary["inconclusive"],
        "control_errors": summary["control_errors"],
        "verification_disagreement": summary["verification_disagreement"],
        "control_failure_present": summary["control_failure_present"],
    }
    count_keys = (
        "attempt_count",
        "supported",
        "rejected",
        "inconclusive",
        "control_errors",
    )
    if (
        any(
            isinstance(result[key], bool) or not isinstance(result[key], int)
            for key in count_keys
        )
        or any(result[key] < 0 for key in count_keys)
        or type(result["verification_disagreement"]) is not bool
        or type(result["control_failure_present"]) is not bool
    ):
        raise GitHubPublicEvidenceError(
            "Run Evidence Report summary contains invalid value types"
        )
    return result


def build_github_public_evidence_projection(
    run: ProductSpineRun,
    *,
    policy: GitHubPublicEvidencePolicy,
    candidates: Mapping[str, CandidateReference] | None = None,
    evidence_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a strict public-safe whitelist over canonical run/evidence state."""

    if not isinstance(run, ProductSpineRun):
        raise GitHubPublicEvidenceError("run must be a ProductSpineRun")
    if not isinstance(policy, GitHubPublicEvidencePolicy):
        raise GitHubPublicEvidenceError(
            "policy must be GitHubPublicEvidencePolicy"
        )
    policy.require_publication()
    if run.project_id.casefold() != policy.repository.casefold():
        raise GitHubPublicEvidenceError(
            "run project_id does not match publication repository"
        )

    bound_candidates = _normalize_candidates(
        run,
        candidates,
        repository=policy.repository,
    )
    bound_evidence, report_summary = _normalize_evidence(
        run,
        evidence_report,
    )

    attempts: list[dict[str, Any]] = []
    for attempt in run.attempts:
        evidence_attempt = bound_evidence.get(attempt.attempt_id)
        evidence_state = None
        recommendation = None
        if evidence_attempt is not None:
            evidence_state = evidence_attempt["evidence_state"]
            verifier = evidence_attempt.get("verifier")
            if isinstance(verifier, Mapping):
                recommendation = verifier["recommendation"]
        attempts.append(
            {
                "attempt_id": attempt.attempt_id,
                "order": attempt.order,
                "connector_id": attempt.connector_id,
                "state": attempt.state,
                "candidate_reference_digest": (
                    attempt.candidate_reference_digest
                ),
                "candidate": _safe_candidate(
                    bound_candidates.get(attempt.attempt_id)
                ),
                "result_manifest_digest": attempt.result_manifest_digest,
                "verification_semantic_digest": (
                    attempt.verification_semantic_digest
                ),
                "evidence_state": evidence_state,
                "verifier_recommendation": recommendation,
            }
        )

    decision_status = "not_recorded"
    if run.human_decision_record_digest is not None:
        decision_status = "recorded"
    elif run.evidence_report_digest is not None:
        decision_status = "pending"

    return {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND,
        "repository": policy.repository,
        "run": {
            "run_id": run.run_id,
            "state": run.state,
            "work_unit_id": run.work_unit_id,
            "work_unit_version": run.work_unit_version,
            "work_unit_digest": run.work_unit_digest,
            "source_revision": run.source_revision,
            "evidence_report_digest": run.evidence_report_digest,
            "human_decision_record_digest": (
                run.human_decision_record_digest
            ),
        },
        "attempts": attempts,
        "evidence_summary": _safe_summary(report_summary),
        "human_decision_status": decision_status,
        "authority": dict(_AUTHORITY),
        "privacy": dict(_PRIVACY),
    }


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    path: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise GitHubPublicEvidenceError(
            f"projection {path} does not match the v0.1 public whitelist"
        )
    return value


def _require_whitelisted_shape(projection: Mapping[str, Any]) -> None:
    """Reject any mapping that is not exactly the v0.1 whitelist shape.

    The renderer is the publication boundary, so it must not serialize a
    hand-built or mutated mapping that smuggles extra fields, relaxed
    authority, or weakened privacy flags past the projection builder.
    """

    _require_exact_keys(projection, _TOP_LEVEL_KEYS, "root")
    _require_exact_keys(projection["run"], _RUN_KEYS, "run")
    attempts = projection["attempts"]
    if not isinstance(attempts, list):
        raise GitHubPublicEvidenceError("projection attempts must be a list")
    for index, attempt in enumerate(attempts):
        attempt = _require_exact_keys(
            attempt, _ATTEMPT_KEYS, f"attempts[{index}]"
        )
        candidate = attempt["candidate"]
        if candidate is not None:
            expected = (
                _PR_CANDIDATE_KEYS
                if isinstance(candidate, Mapping)
                and candidate.get("type") == "github_pull_request"
                else _BUNDLE_CANDIDATE_KEYS
            )
            _require_exact_keys(
                candidate, expected, f"attempts[{index}].candidate"
            )
    if projection["evidence_summary"] is not None:
        _require_exact_keys(
            projection["evidence_summary"], _SUMMARY_KEYS, "evidence_summary"
        )
    if dict(_require_exact_keys(
        projection["authority"], frozenset(_AUTHORITY), "authority"
    )) != _AUTHORITY or any(
        type(flag) is not bool for flag in projection["authority"].values()
    ):
        raise GitHubPublicEvidenceError(
            "projection authority must be the fixed all-false ceiling"
        )
    if dict(_require_exact_keys(
        projection["privacy"], frozenset(_PRIVACY), "privacy"
    )) != _PRIVACY or any(
        type(projection["privacy"][key]) is not bool
        for key in _PRIVACY
        if key != "data_classification"
    ):
        raise GitHubPublicEvidenceError(
            "projection privacy flags must match the fixed public profile"
        )


def render_github_public_evidence_json(
    projection: Mapping[str, Any],
) -> str:
    """Render deterministic bounded JSON for a later GitHub publication step."""

    if not isinstance(projection, Mapping):
        raise GitHubPublicEvidenceError("projection must be a mapping")
    if (
        projection.get("schema_version") != _SCHEMA_VERSION
        or projection.get("kind") != _KIND
    ):
        raise GitHubPublicEvidenceError(
            "projection is not GitHub public evidence v0.1"
        )
    _require_whitelisted_shape(projection)
    rendered = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    if len(rendered.encode("utf-8")) > _MAX_JSON_BYTES:
        raise GitHubPublicEvidenceError(
            f"public evidence projection exceeds {_MAX_JSON_BYTES} UTF-8 bytes"
        )
    return rendered
