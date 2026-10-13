"""Release metadata and provenance record for C14-F (#609).

This module binds a *proposed* release (tag, target commit, distributable
artifact digests) to the public-safe run evidence (C14-D projections) that the
release references, and renders that binding as deterministic JSON and as draft
release notes. It is a metadata record, nothing more:

* it creates no tag, no GitHub Release, and no attestation, and makes no file,
  network, or GitHub call;
* it never claims that a release or an attestation exists
  (``publication_state`` is always ``metadata_only``; attestation is C14-G);
* the target commit and the artifact digests are caller-supplied assertions and
  are recorded as such: nothing here verifies them against Git or the build;
* run evidence is referenced, not proven contained in the release commit
  (squash merges rewrite SHAs, so ancestry cannot be inferred offline);
* the record carries no timestamps because the public projection has none, and
  none are invented;
* it grants no dispatch, verification, human-decision, canonical-state-write,
  Git-push, integration, merge, tag, release, or attestation authority and
  makes no functional-correctness claim.

Every run projection is re-validated through the shared C14-D/C14-E validators
before any of its fields reach the record.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Mapping

from idkmesh.github_pages_site import (
    MAX_RUNS,
    GitHubPagesSiteError,
    validate_public_projection,
)
from idkmesh.work_unit_binding import canonical_digest


_SCHEMA_VERSION = "0.1"
_KIND = "idkmesh-github-release-provenance"
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_REVISION_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ARTIFACT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
# Run IDs reach Markdown, so the release record is stricter than Pages (which
# only HTML-escapes): no backticks, brackets, whitespace, or braces.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_STATE_RE = re.compile(r"[a-z][a-z_]{0,63}\Z")
_ATTEMPT_ID_RE = _RUN_ID_RE
_WORK_UNIT_ID_RE = _RUN_ID_RE

MAX_ARTIFACTS = 100
MAX_JSON_BYTES = 1024 * 1024

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "repository",
        "release",
        "artifacts",
        "evidence",
        "attestation",
        "claims",
        "authority",
        "record_digest",
    }
)
_RELEASE_KEYS = frozenset({"tag", "target_commit", "publication_state"})
_ARTIFACT_KEYS = frozenset({"name", "digest"})
_EVIDENCE_KEYS = frozenset(
    {
        "run_id",
        "run_state",
        "work_unit_id",
        "work_unit_version",
        "work_unit_digest",
        "run_source_revision",
        "evidence_report_digest",
        "human_decision_status",
        "human_decision_record_digest",
        "projection_digest",
        "candidates",
    }
)
_PR_CANDIDATE_KEYS = frozenset({"attempt_id", "type", "number", "head_sha"})
_BUNDLE_CANDIDATE_KEYS = frozenset({"attempt_id", "type", "digest"})
_NULLABLE_DIGESTS = frozenset(
    {"evidence_report_digest", "human_decision_record_digest"}
)
_PUBLICATION_STATE = "metadata_only"
_ATTESTATION = {
    "status": "not_claimed",
    "owner": "C14-G",
    "artifact_attestation_present": False,
}
_CLAIMS = {
    "release_published": False,
    "tag_created": False,
    "attestation_present": False,
    "target_commit_verified_against_git": False,
    "artifact_digests_verified_against_build": False,
    "run_evidence_proven_contained_in_release": False,
    "functional_correctness": False,
}
_AUTHORITY = {
    "dispatch": False,
    "verification": False,
    "human_decision": False,
    "canonical_state_write": False,
    "git_push": False,
    "integration": False,
    "merge": False,
    "tag_creation": False,
    "release_creation": False,
    "attestation": False,
}

_NOT_CLAIMED = (
    "No Git tag or GitHub Release has been created by this record.",
    "No artifact attestation exists or is claimed (C14-G owns attestation).",
    "The target commit and artifact digests are caller-supplied and were not "
    "verified against Git or a build.",
    "Referenced runs are not proven to be contained in the target commit.",
    "A digest, a verifier recommendation, or this record does not prove "
    "functional correctness.",
)


class GitHubReleaseProvenanceError(ValueError):
    """Fail-closed release-provenance error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GitHubReleaseProvenanceError(message)


@dataclass(frozen=True, slots=True)
class GitHubReleaseArtifact:
    """One distributable artifact, identified by name and SHA-256 digest."""

    name: str
    digest: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or _ARTIFACT_NAME_RE.fullmatch(self.name) is None
        ):
            raise GitHubReleaseProvenanceError(
                "artifact name must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
            )
        if (
            not isinstance(self.digest, str)
            or _DIGEST_RE.fullmatch(self.digest) is None
        ):
            raise GitHubReleaseProvenanceError(
                "artifact digest must be sha256:<64 lowercase hex>"
            )


def _check_tag(tag: Any) -> str:
    _require(isinstance(tag, str), "tag must be a string")
    _require(
        _TAG_RE.fullmatch(tag) is not None
        and ".." not in tag
        and not tag.endswith((".", ".lock")),
        "tag must be a plain Git tag name",
    )
    return tag


def _check_text(value: Any, pattern: re.Pattern[str], label: str) -> str:
    _require(
        isinstance(value, str) and pattern.fullmatch(value) is not None,
        f"{label} is not safe for release metadata",
    )
    return value


def _evidence_entry(projection: Mapping[str, Any]) -> dict[str, Any]:
    run = projection["run"]
    candidates: list[dict[str, Any]] = []
    for attempt in sorted(projection["attempts"], key=lambda a: a["order"]):
        candidate = attempt["candidate"]
        if candidate is None:
            continue
        attempt_id = _check_text(
            attempt["attempt_id"], _ATTEMPT_ID_RE, "attempt_id"
        )
        if candidate["type"] == "github_pull_request":
            candidates.append(
                {
                    "attempt_id": attempt_id,
                    "type": "github_pull_request",
                    "number": candidate["number"],
                    "head_sha": candidate["head_sha"],
                }
            )
        else:
            candidates.append(
                {
                    "attempt_id": attempt_id,
                    "type": "artifact_bundle",
                    "digest": candidate["digest"],
                }
            )
    return {
        "run_id": _check_text(run["run_id"], _RUN_ID_RE, "run_id"),
        "run_state": run["state"],
        "work_unit_id": _check_text(
            run["work_unit_id"], _WORK_UNIT_ID_RE, "work_unit_id"
        ),
        "work_unit_version": run["work_unit_version"],
        "work_unit_digest": run["work_unit_digest"],
        "run_source_revision": run["source_revision"],
        "evidence_report_digest": run["evidence_report_digest"],
        "human_decision_status": projection["human_decision_status"],
        "human_decision_record_digest": run["human_decision_record_digest"],
        # Binds this entry to the exact public projection (the same canonical
        # digest as the parsed data/runs/<slug>.json that Pages publishes).
        "projection_digest": canonical_digest(projection),
        "candidates": candidates,
    }


def _record_digest(body: Mapping[str, Any]) -> str:
    return canonical_digest(
        {key: value for key, value in body.items() if key != "record_digest"}
    )


def build_github_release_provenance(
    projections: Iterable[Mapping[str, Any]],
    *,
    repository: str,
    tag: str,
    target_commit: str,
    artifacts: Iterable[GitHubReleaseArtifact] = (),
) -> dict[str, Any]:
    """Return the deterministic release metadata/provenance record.

    ``projections`` are C14-D public-safe projections for ``repository``; each
    is re-validated. ``target_commit`` and ``artifacts`` are caller-supplied
    assertions recorded as such. Nothing is created, published, or attested.
    """

    _require(
        isinstance(repository, str)
        and _REPOSITORY_RE.fullmatch(repository) is not None,
        "repository must be owner/name",
    )
    _check_tag(tag)
    _require(
        isinstance(target_commit, str)
        and _REVISION_RE.fullmatch(target_commit) is not None,
        "target_commit must be an exact 40- or 64-hex Git revision",
    )

    artifact_items = list(artifacts)
    _require(
        len(artifact_items) <= MAX_ARTIFACTS,
        f"at most {MAX_ARTIFACTS} artifacts may be recorded",
    )
    names: set[str] = set()
    for artifact in artifact_items:
        _require(
            isinstance(artifact, GitHubReleaseArtifact),
            "artifacts must be GitHubReleaseArtifact",
        )
        _require(
            artifact.name.casefold() not in names,
            "duplicate artifact name",
        )
        names.add(artifact.name.casefold())

    items = list(projections)
    _require(len(items) <= MAX_RUNS, f"at most {MAX_RUNS} runs may be referenced")
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for projection in items:
        try:
            validate_public_projection(projection, repository)
        except GitHubPagesSiteError as exc:
            raise GitHubReleaseProvenanceError(str(exc)) from exc
        entry = _evidence_entry(projection)
        _require(entry["run_id"] not in seen, "duplicate run_id in release input")
        seen.add(entry["run_id"])
        evidence.append(entry)
    evidence.sort(key=lambda entry: entry["run_id"])

    record: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND,
        "repository": repository,
        "release": {
            "tag": tag,
            "target_commit": target_commit,
            "publication_state": _PUBLICATION_STATE,
        },
        "artifacts": [
            {"name": a.name, "digest": a.digest}
            for a in sorted(artifact_items, key=lambda a: a.name)
        ],
        "evidence": evidence,
        "attestation": dict(_ATTESTATION),
        "claims": dict(_CLAIMS),
        "authority": dict(_AUTHORITY),
    }
    record["record_digest"] = _record_digest(record)
    return record


def _exact(value: Any, keys: frozenset[str], path: str) -> Mapping[str, Any]:
    _require(
        isinstance(value, Mapping) and set(value) == keys,
        f"release record {path} does not match the v0.1 shape",
    )
    return value


def _fixed(value: Any, expected: Mapping[str, Any], path: str) -> None:
    _exact(value, frozenset(expected), path)
    _require(
        all(
            type(value[key]) is type(expected[key]) and value[key] == expected[key]
            for key in expected
        ),
        f"release record {path} must be the fixed v0.1 value",
    )


def validate_github_release_provenance(record: Mapping[str, Any]) -> None:
    """Fail closed unless ``record`` is exactly a v0.1 release record."""

    _require(isinstance(record, Mapping), "release record must be a mapping")
    _require(
        record.get("schema_version") == _SCHEMA_VERSION
        and record.get("kind") == _KIND,
        "not a GitHub release provenance v0.1 record",
    )
    _exact(record, _TOP_LEVEL_KEYS, "root")
    _require(
        isinstance(record["repository"], str)
        and _REPOSITORY_RE.fullmatch(record["repository"]) is not None,
        "repository must be owner/name",
    )
    release = _exact(record["release"], _RELEASE_KEYS, "release")
    _check_tag(release["tag"])
    _require(
        isinstance(release["target_commit"], str)
        and _REVISION_RE.fullmatch(release["target_commit"]) is not None,
        "target_commit must be an exact Git revision",
    )
    _require(
        release["publication_state"] == _PUBLICATION_STATE,
        "publication_state must be metadata_only",
    )
    artifacts = record["artifacts"]
    _require(
        isinstance(artifacts, list) and len(artifacts) <= MAX_ARTIFACTS,
        "artifacts must be a bounded list",
    )
    names = []
    for index, artifact in enumerate(artifacts):
        _exact(artifact, _ARTIFACT_KEYS, f"artifacts[{index}]")
        GitHubReleaseArtifact(artifact["name"], artifact["digest"])
        names.append(artifact["name"])
    _require(
        names == sorted(names) and len({n.casefold() for n in names}) == len(names),
        "artifacts must be unique and sorted by name",
    )
    evidence = record["evidence"]
    _require(
        isinstance(evidence, list) and len(evidence) <= MAX_RUNS,
        "evidence must be a bounded list",
    )
    run_ids = []
    for index, entry in enumerate(evidence):
        path = f"evidence[{index}]"
        _exact(entry, _EVIDENCE_KEYS, path)
        run_ids.append(_check_text(entry["run_id"], _RUN_ID_RE, "run_id"))
        _check_text(entry["work_unit_id"], _WORK_UNIT_ID_RE, "work_unit_id")
        _check_text(entry["run_state"], _STATE_RE, "run_state")
        _check_text(
            entry["human_decision_status"], _STATE_RE, "human_decision_status"
        )
        _require(
            type(entry["work_unit_version"]) is int,
            f"{path} work_unit_version must be an integer",
        )
        _require(
            isinstance(entry["run_source_revision"], str)
            and _REVISION_RE.fullmatch(entry["run_source_revision"]) is not None,
            f"{path} run_source_revision must be an exact Git revision",
        )
        for key in (
            "work_unit_digest",
            "evidence_report_digest",
            "human_decision_record_digest",
            "projection_digest",
        ):
            value = entry[key]
            _require(
                (value is None and key in _NULLABLE_DIGESTS)
                or (
                    isinstance(value, str)
                    and _DIGEST_RE.fullmatch(value) is not None
                ),
                f"{path} {key} must be a sha256 digest",
            )
        candidates = entry["candidates"]
        _require(isinstance(candidates, list), f"{path} candidates must be a list")
        for cindex, candidate in enumerate(candidates):
            cpath = f"{path}.candidates[{cindex}]"
            _require(isinstance(candidate, Mapping), f"{cpath} must be an object")
            _check_text(candidate.get("attempt_id"), _ATTEMPT_ID_RE, "attempt_id")
            if candidate.get("type") == "github_pull_request":
                _exact(candidate, _PR_CANDIDATE_KEYS, cpath)
                _require(
                    type(candidate["number"]) is int and candidate["number"] > 0,
                    f"{cpath} number must be a positive integer",
                )
                _require(
                    isinstance(candidate["head_sha"], str)
                    and _REVISION_RE.fullmatch(candidate["head_sha"]) is not None,
                    f"{cpath} head_sha must be an exact Git revision",
                )
            else:
                _exact(candidate, _BUNDLE_CANDIDATE_KEYS, cpath)
                _require(
                    candidate["type"] == "artifact_bundle"
                    and isinstance(candidate["digest"], str)
                    and _DIGEST_RE.fullmatch(candidate["digest"]) is not None,
                    f"{cpath} is not a valid artifact bundle candidate",
                )
    _require(
        run_ids == sorted(run_ids) and len(set(run_ids)) == len(run_ids),
        "evidence must be unique and sorted by run_id",
    )
    _fixed(record["attestation"], _ATTESTATION, "attestation")
    _fixed(record["claims"], _CLAIMS, "claims")
    _fixed(record["authority"], _AUTHORITY, "authority")
    _require(
        record["record_digest"] == _record_digest(record),
        "record_digest does not match the record content",
    )


def render_github_release_provenance_json(record: Mapping[str, Any]) -> str:
    """Render the validated record as deterministic, bounded JSON."""

    validate_github_release_provenance(record)
    rendered = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    _require(
        len(rendered.encode("utf-8")) <= MAX_JSON_BYTES,
        f"release record exceeds {MAX_JSON_BYTES} UTF-8 bytes",
    )
    return rendered


def _cell(value: Any) -> str:
    return "none" if value is None else f"`{value}`"


def render_github_release_notes(record: Mapping[str, Any]) -> str:
    """Render draft release-note Markdown from a validated record.

    Every interpolated value is constrained by the record validator to a
    character set that cannot form Markdown, HTML, Liquid, or ``@`` mentions,
    and identifiers appear only inside code spans.
    """

    validate_github_release_provenance(record)
    release = record["release"]
    lines = [
        f"# Release {release['tag']} (draft metadata, not published)",
        "",
        f"Repository: `{record['repository']}`",
        "",
        f"Target commit (caller supplied): `{release['target_commit']}`",
        "",
        "## Artifacts",
        "",
    ]
    if record["artifacts"]:
        lines += ["| Name | SHA-256 |", "|---|---|"]
        lines += [
            f"| `{a['name']}` | `{a['digest']}` |" for a in record["artifacts"]
        ]
    else:
        lines.append("No artifacts recorded.")
    lines += ["", "## Referenced IDKMesh run evidence", ""]
    if record["evidence"]:
        lines += [
            "| Run | State | Human decision | WorkUnit digest "
            "| Evidence report digest | Projection digest |",
            "|---|---|---|---|---|---|",
        ]
        for entry in record["evidence"]:
            lines.append(
                f"| `{entry['run_id']}` | {entry['run_state']} "
                f"| {entry['human_decision_status']} "
                f"| {_cell(entry['work_unit_digest'])} "
                f"| {_cell(entry['evidence_report_digest'])} "
                f"| {_cell(entry['projection_digest'])} |"
            )
    else:
        lines.append("No run evidence referenced.")
    lines += ["", "## What this record does not claim", ""]
    lines += [f"- {text}" for text in _NOT_CLAIMED]
    lines += ["", f"Record digest: `{record['record_digest']}`", ""]
    return "\n".join(lines)
