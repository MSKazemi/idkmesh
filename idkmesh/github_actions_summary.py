"""Pure GitHub Actions step-summary renderer for Product Spine runs.

C14-A is a presentation boundary only. This module formats already-retained
Product Spine, CandidateReference, and Run Evidence Report data as bounded
Markdown suitable for ``$GITHUB_STEP_SUMMARY``. It performs no filesystem,
network, GitHub, verification, human-decision, or integration mutation.

Optional candidate/evidence details are accepted only when they bind back to
canonical digests already retained by the Product Spine projection. Display
input therefore cannot broaden authority or silently replace canonical state.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    CandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.product_spine import ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest

_MAX_SUMMARY_BYTES = 64 * 1024
_MAX_URL_LENGTH = 2048


class GitHubActionsSummaryError(ValueError):
    """Fail-closed error for inconsistent or unsafe summary inputs."""


def _safe_text(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value:
        raise GitHubActionsSummaryError(f"{field} must be a non-empty string")
    if len(value) > max_length:
        raise GitHubActionsSummaryError(f"{field} exceeds maximum length")
    if any((ord(char) < 32 and char not in {"\t", "\n", "\r"}) or ord(char) == 127 for char in value):
        raise GitHubActionsSummaryError(f"{field} contains unsupported control characters")
    normalized = " ".join(value.splitlines())
    return escape(normalized, quote=False).replace("|", "\\|").replace("`", "'")


def _safe_url(value: object, *, field: str) -> str:
    text = _safe_text(value, field=field, max_length=_MAX_URL_LENGTH)
    if not (text.startswith("https://github.com/") or text.startswith("https://raw.githubusercontent.com/")):
        raise GitHubActionsSummaryError(
            f"{field} must use an https GitHub URL for the public Actions summary"
        )
    return text


def _short_digest(value: str | None) -> str:
    if value is None:
        return "—"
    return f"`{value[:18]}…`"


def _candidate_digest(reference: CandidateReference) -> str:
    return canonical_digest(reference.to_dict())


def _normalize_candidates(
    run: ProductSpineRun,
    candidates: Mapping[str, CandidateReference] | None,
) -> dict[str, CandidateReference]:
    if candidates is None:
        return {}
    attempt_by_id = {attempt.attempt_id: attempt for attempt in run.attempts}
    normalized: dict[str, CandidateReference] = {}
    for attempt_id, reference in candidates.items():
        if attempt_id not in attempt_by_id:
            raise GitHubActionsSummaryError(
                f"candidate reference targets unknown attempt {attempt_id!r}"
            )
        if not isinstance(
            reference,
            (GitHubPullRequestCandidateReference, ArtifactBundleCandidateReference),
        ):
            raise GitHubActionsSummaryError(
                f"candidate reference for {attempt_id!r} has unsupported type"
            )
        retained_digest = attempt_by_id[attempt_id].candidate_reference_digest
        if retained_digest is None:
            raise GitHubActionsSummaryError(
                f"attempt {attempt_id!r} has no retained candidate reference digest"
            )
        if _candidate_digest(reference) != retained_digest:
            raise GitHubActionsSummaryError(
                f"candidate reference for {attempt_id!r} does not match retained digest"
            )
        normalized[attempt_id] = reference
    return normalized


def _normalize_evidence_report(
    run: ProductSpineRun,
    report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if report is None:
        return {}
    if run.evidence_report_digest is None:
        raise GitHubActionsSummaryError(
            "evidence report was supplied but the run has no retained evidence report digest"
        )
    if report.get("schema_version") != "0.1" or report.get("kind") != "idkmesh-run-evidence-report":
        raise GitHubActionsSummaryError("unsupported Run Evidence Report")
    if report.get("run_id") != run.run_id:
        raise GitHubActionsSummaryError("Run Evidence Report run_id does not match the Product Spine run")
    work_unit = report.get("work_unit")
    if not isinstance(work_unit, Mapping) or work_unit.get("digest") != run.work_unit_digest:
        raise GitHubActionsSummaryError("Run Evidence Report WorkUnit digest does not match the Product Spine run")
    if canonical_digest(report) != run.evidence_report_digest:
        raise GitHubActionsSummaryError("Run Evidence Report digest does not match the retained digest")

    attempts = report.get("attempts")
    if not isinstance(attempts, list):
        raise GitHubActionsSummaryError("Run Evidence Report attempts must be an array")
    run_attempts = {attempt.attempt_id: attempt for attempt in run.attempts}
    normalized: dict[str, Mapping[str, Any]] = {}
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, Mapping):
            raise GitHubActionsSummaryError(
                f"Run Evidence Report attempts[{index}] must be an object"
            )
        attempt_id = attempt.get("attempt_id")
        if not isinstance(attempt_id, str) or attempt_id not in run_attempts:
            raise GitHubActionsSummaryError(
                f"Run Evidence Report attempts[{index}] does not bind to a retained attempt"
            )
        if attempt_id in normalized:
            raise GitHubActionsSummaryError(
                f"Run Evidence Report repeats attempt {attempt_id!r}"
            )
        retained = run_attempts[attempt_id]
        worker = attempt.get("worker")
        if isinstance(worker, Mapping) and (
            worker.get("result_manifest_digest") != retained.result_manifest_digest
        ):
            raise GitHubActionsSummaryError(
                f"Run Evidence Report ResultManifest for {attempt_id!r} does not match the retained attempt"
            )
        verifier = attempt.get("verifier")
        if isinstance(verifier, Mapping) and (
            verifier.get("verification_semantic_digest")
            != retained.verification_semantic_digest
        ):
            raise GitHubActionsSummaryError(
                f"Run Evidence Report verification for {attempt_id!r} does not match the retained attempt"
            )
        normalized[attempt_id] = attempt
    if set(normalized) != set(run_attempts):
        raise GitHubActionsSummaryError(
            "Run Evidence Report attempt set does not match the retained Product Spine attempts"
        )
    return normalized


def _candidate_cell(reference: CandidateReference | None) -> str:
    if reference is None:
        return "retained digest only"
    if isinstance(reference, GitHubPullRequestCandidateReference):
        label = f"PR #{reference.number} @ {reference.head_sha[:12]}"
        return f"[{_safe_text(label, field='candidate label')}]({_safe_url(reference.canonical_url, field='candidate URL')})"
    return f"artifact bundle {_short_digest(reference.digest)}"


def _evidence_verifier_cell(
    attempt: Any,
    evidence_attempt: Mapping[str, Any] | None,
) -> str:
    if evidence_attempt is not None:
        verifier = evidence_attempt.get("verifier")
        if isinstance(verifier, Mapping):
            recommendation = verifier.get("recommendation")
            if isinstance(recommendation, str) and recommendation:
                return _safe_text(recommendation, field="verifier recommendation")
    if attempt.verification_semantic_digest is not None:
        return _short_digest(attempt.verification_semantic_digest)
    return "—"


def _human_decision_state(run: ProductSpineRun) -> str:
    if run.human_decision_record_digest is not None:
        return f"recorded {_short_digest(run.human_decision_record_digest)}"
    if run.state in {"evidence_ready", "awaiting_human_decision"}:
        return "pending explicit human/governance decision"
    return "not yet recorded"


def render_github_actions_summary(
    run: ProductSpineRun,
    *,
    candidates: Mapping[str, CandidateReference] | None = None,
    evidence_report: Mapping[str, Any] | None = None,
    durable_evidence_url: str | None = None,
) -> str:
    """Render deterministic, authority-safe Markdown for a GitHub Actions summary.

    ``run`` is the canonical operational projection. Optional candidate and
    report objects only enrich presentation after exact digest binding checks.
    The function returns Markdown; callers decide whether and where to publish
    it.
    """

    if not isinstance(run, ProductSpineRun):
        raise GitHubActionsSummaryError("run must be a ProductSpineRun")

    bound_candidates = _normalize_candidates(run, candidates)
    bound_report = _normalize_evidence_report(run, evidence_report)
    evidence_url = (
        _safe_url(durable_evidence_url, field="durable_evidence_url")
        if durable_evidence_url is not None
        else None
    )

    lines = [
        "## IDKMesh run summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Run | `{run.run_id}` |",
        f"| State | `{run.state}` |",
        f"| WorkUnit | `{run.work_unit_id}` v{run.work_unit_version} |",
        f"| WorkUnit digest | `{run.work_unit_digest}` |",
        f"| Base source revision | `{run.source_revision}` |",
        f"| Authority mode | `{run.authority_mode}` |",
        f"| Human decision | {_human_decision_state(run)} |",
        f"| Evidence report | {_short_digest(run.evidence_report_digest)} |",
        "",
        "### Attempts",
        "",
        "| Attempt | Connector | State | Candidate | ResultManifest | Verification |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    if not run.attempts:
        lines.append("| — | — | no attempt yet | — | — | — |")
    else:
        for attempt in run.attempts:
            evidence_attempt = bound_report.get(attempt.attempt_id)
            lines.append(
                "| "
                + " | ".join(
                    (
                        f"`{attempt.attempt_id}`",
                        f"`{attempt.connector_id}`",
                        f"`{attempt.state}`",
                        _candidate_cell(bound_candidates.get(attempt.attempt_id)),
                        _short_digest(attempt.result_manifest_digest),
                        _evidence_verifier_cell(attempt, evidence_attempt),
                    )
                )
                + " |"
            )

    check_sections: list[str] = []
    for attempt in run.attempts:
        evidence_attempt = bound_report.get(attempt.attempt_id)
        if evidence_attempt is None:
            continue
        verifier = evidence_attempt.get("verifier")
        if not isinstance(verifier, Mapping):
            continue
        checks = verifier.get("checks")
        if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
            continue
        rendered_checks: list[str] = []
        for index, check in enumerate(checks):
            if not isinstance(check, Mapping):
                raise GitHubActionsSummaryError(
                    f"verifier check {index} for {attempt.attempt_id!r} must be an object"
                )
            check_id = _safe_text(check.get("id"), field="check.id")
            status = _safe_text(check.get("status"), field="check.status")
            required = check.get("required")
            if not isinstance(required, bool):
                raise GitHubActionsSummaryError("check.required must be a boolean")
            rendered_checks.append(
                f"- `{check_id}` — `{status}` ({'required' if required else 'advisory'})"
            )
        if rendered_checks:
            check_sections.extend(
                [
                    "",
                    f"#### Checks — `{attempt.attempt_id}`",
                    *rendered_checks,
                ]
            )

    lines.extend(check_sections)
    lines.extend(
        [
            "",
            "### Authority boundary",
            "",
            "- Canonical-state write: **blocked**",
            "- Git push: **blocked**",
            "- Merge: **blocked**",
            "- Automatic candidate selection: **blocked**",
            "",
            "### Evidence",
            "",
        ]
    )
    if evidence_url is None:
        lines.append("Durable evidence link: not supplied to this renderer.")
    else:
        lines.append(f"Durable evidence: [open retained evidence]({evidence_url})")
    lines.extend(
        [
            "",
            "> Presentation only. Worker completion, verification recommendation, human decision, and integration authority remain separate.",
        ]
    )

    rendered = "\n".join(lines) + "\n"
    if len(rendered.encode("utf-8")) > _MAX_SUMMARY_BYTES:
        raise GitHubActionsSummaryError(
            f"rendered Actions summary exceeds {_MAX_SUMMARY_BYTES} UTF-8 bytes"
        )
    return rendered
